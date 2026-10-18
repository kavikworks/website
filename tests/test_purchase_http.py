"""Loopback-only synthetic HTTP/privacy/access-control tests."""
from contextlib import redirect_stderr
from datetime import datetime, timezone
import http.client
from http.cookies import SimpleCookie
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview.purchase.server import PreviewServer, private_directory


class Client:
    def __init__(self, server):
        self.port = server.server_address[1]
        self.cookies = {}
        self.csrf = None

    def request(self, path, body=None, method=None, headers=None, raw=False):
        method = method or ("POST" if body is not None else "GET")
        values = {"Cookie": "; ".join(f"{key}={value}" for key, value in self.cookies.items())}
        if body is not None:
            values.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}", "X-Preview-CSRF": self.csrf or ""})
        values.update(headers or {})
        encoded = body if raw else json.dumps(body) if body is not None else None
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(method, path, body=encoded, headers=values)
        response = conn.getresponse()
        payload, status, response_headers = response.read(), response.status, dict(response.getheaders())
        if response_headers.get("Set-Cookie"):
            cookie = SimpleCookie(response_headers["Set-Cookie"])
            self.cookies.update({key: value.value for key, value in cookie.items()})
        conn.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            payload = json.loads(payload)
            if isinstance(payload, dict) and "csrf" in payload:
                self.csrf = payload["csrf"]
        return status, payload, response_headers

    def init(self):
        self.request("/api/current")
        return self


def payload():
    return {"workflow": "ADMIN_INBOX", "tools": "TEST_ONLY shared inbox",
            "handoff": "TEST_ONLY_PRIVATE_MARKER: assign ordinary messages to the office owner.",
            "admin_only": True, "one_workflow": True, "no_sensitive_data": True,
            "written_plan_only": True, "submission_key": "TEST_ONLY_HTTP_SUBMISSION_0001"}


class HttpPrivacy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = PreviewServer(0, self.temp.name, clock=lambda: datetime(2026, 10, 19, 16, tzinfo=timezone.utc))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close)
        self.client = Client(self.server).init()

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.worker.join(timeout=2)

    def test_json_private_no_store_cookie_and_security_headers(self):
        status, data, headers = self.client.request("/api/current")
        self.assertEqual(status, 200)
        self.assertTrue(data["sample_only"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_no_session_origin_or_csrf_cannot_mutate(self):
        stranger = Client(self.server)
        self.assertEqual(stranger.request("/api/brief", payload())[0], 401)
        self.assertEqual(self.client.request("/api/brief", payload(), headers={"Origin": "https://attacker.example"})[0], 403)
        self.assertEqual(self.client.request("/api/brief", payload(), headers={"X-Preview-CSRF": "wrong"})[0], 403)
        self.assertIsNone(self.server.store.current(self.client.cookies["kw_preview"]))

    def test_host_and_url_fields_cannot_bypass_loopback_or_leak_query_data(self):
        self.assertEqual(self.client.request("/api/current", headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.client.request("/order?brief=TEST_ONLY_PRIVATE_MARKER")[0], 400)
        self.assertIn(self.client.request("http://attacker.example/api/current")[0], {400, 403})

    def test_body_limits_closed_schema_duplicate_keys_and_nonfinite_numbers(self):
        for data in ('{"x":1,"x":2}', '{"x":NaN}', '[]'):
            self.assertEqual(self.client.request("/api/brief", data, raw=True)[0], 400)
        self.assertEqual(self.client.request("/api/brief", "x" * 9000, raw=True)[0], 413)
        self.assertEqual(self.client.request("/api/pay", {"outcome": "paid", "amount": 1})[0], 400)

    def test_intake_recovery_and_customer_isolation(self):
        status, first, _ = self.client.request("/api/brief", payload())
        self.assertEqual(status, 200)
        other = Client(self.server).init()
        self.assertIsNone(other.request("/api/current")[1]["order"])
        self.assertEqual(other.request("/api/report")[0], 404)
        self.assertEqual(other.request("/api/operator/orders")[0], 401)
        _, result, _ = self.client.request("/api/recovery", {})
        key = result["recovery_key"]
        self.assertNotIn(key, json.dumps(first["order"]))
        recovered = other.request("/api/recover", {"recovery_key": key})
        self.assertEqual(recovered[1]["order"], first["order"])
        self.assertEqual(other.request("/api/recover", {"recovery_key": "wrong"})[0], 404)

    def test_success_page_return_cannot_mark_an_order_paid(self):
        self.client.request("/api/brief", payload())
        self.client.request("/api/checkout", {"accept_preview_terms": True})
        self.client.request("/order")
        order = self.client.request("/api/current")[1]["order"]
        self.assertEqual(order["state"], "CHECKOUT_OPEN")
        self.assertIsNone(order["case"])

    def test_browser_fake_checkout_paid_case_and_private_report_lifecycle(self):
        self.client.request("/api/brief", payload())
        self.client.request("/api/checkout", {"accept_preview_terms": True})
        status, paid, _ = self.client.request("/api/pay", {"outcome": "paid"})
        self.assertEqual(status, 200)
        self.assertEqual(paid["order"]["case"]["state"], "DRAFTING")
        self.assertEqual(self.client.request("/api/report")[0], 404)
        self.assertEqual(self.client.request("/api/operator/action", {"order_id": paid["order"]["id"], "action": "deliver"})[0], 401)
        operator = Client(self.server).init()
        key = (Path(self.temp.name) / "operator.token").read_text()
        self.assertEqual(operator.request("/api/operator/login", {"token": key})[0], 200)
        for action in ("draft", "qa_pass", "deliver"):
            self.assertEqual(operator.request("/api/operator/action", {"order_id": paid["order"]["id"], "action": action})[0], 200)
        report = self.client.request("/api/report")
        self.assertEqual(report[0], 200)
        self.assertIn("Workflow map", report[1]["text"])
        self.assertEqual(Client(self.server).init().request("/api/report")[0], 404)

    def test_no_secret_brief_or_recovery_code_in_access_logs(self):
        output = io.StringIO()
        with redirect_stderr(output):
            self.client.request("/api/brief", payload())
            self.client.request("/api/recovery", {})
            self.client.request("/api/recover", {"recovery_key": "TEST_ONLY_PRIVATE_MARKER"})
        self.assertEqual(output.getvalue(), "")

    def test_filesystem_and_private_tokens_are_not_http_routes(self):
        for path in ("/.git/config", "/operator.token", "/preview.sqlite3", "/../model.py", "/preview/purchase/model.py", "/.env", "/api/webhook"):
            self.assertEqual(self.client.request(path)[0], 404, path)

    def test_operator_login_is_rate_limited_and_has_separate_cookie(self):
        for _ in range(5):
            self.assertEqual(self.client.request("/api/operator/login", {"token": "bad"})[0], 401)
        self.assertEqual(self.client.request("/api/operator/login", {"token": "bad"})[0], 429)
        self.assertNotIn("kw_operator", self.client.cookies)

    def test_private_storage_is_rejected_inside_repo_and_has_restrictive_modes(self):
        with self.assertRaises(ValueError):
            private_directory(Path(__file__).resolve().parents[1] / "preview-private-data")
        self.assertEqual(Path(self.temp.name).stat().st_mode & 0o777, 0o700)
        for name in ("operator.token", "preview.sqlite3"):
            self.assertEqual((Path(self.temp.name) / name).stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
