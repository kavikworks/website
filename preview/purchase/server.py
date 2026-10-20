"""Loopback HTTP demonstration, not a production deployment entrypoint."""
import argparse
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

from .model import PreviewError, Store, digest, stamp

WEB = Path(__file__).parent / "web"
PAGES = {"/", "/checkout", "/order", "/operator"}
ASSETS = {"/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


def private_directory(path):
    raw = Path(path).expanduser()
    resolved = raw.resolve()
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("Private preview data must be outside every Git checkout")
    if raw.is_symlink():
        raise ValueError("Choose a private directory, not a symlink")
    resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
    if resolved.stat().st_uid != os.getuid():
        raise ValueError("Private preview data must be owned by the current user")
    resolved.chmod(0o700)
    for name in ("preview.sqlite3", "operator.token"):
        if (resolved / name).is_symlink():
            raise ValueError("Private preview files must not be symlinks")
    return resolved


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, data_dir, clock=None):
        os.umask(0o077)
        self.data_dir = private_directory(data_dir)
        self.store = Store(self.data_dir / "preview.sqlite3", clock=clock)
        self.store.reconcile_all()  # Recover paid cases even without a browser return.
        keyfile = self.data_dir / "operator.token"
        if not keyfile.exists():
            fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(secrets.token_urlsafe(32))
        self.operator_key = keyfile.read_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", self.operator_key):
            raise ValueError("Invalid private operator key")
        keyfile.chmod(0o600)
        self.operator_sessions = {}
        self.login_failures = []
        super().__init__(("127.0.0.1", port), Handler)

    def handle_error(self, request, client_address):
        pass  # No request bodies, secrets, brief fields, or tracebacks in logs.


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalFakePreview"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _headers(self, status, content_type="application/json; charset=utf-8", cookie=None, length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _json(self, data, status=200, cookie=None):
        encoded = json.dumps(data, allow_nan=False).encode()
        self._headers(status, cookie=cookie, length=len(encoded))
        self.wfile.write(encoded)

    def _fail(self, error):
        self._json({"error": error.code, "message": error.message,
                    "fields": error.fields}, error.status)

    def _path(self):
        port = self.server.server_address[1]
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            raise PreviewError("HOST_REJECTED", "This preview accepts loopback requests only.", 403)
        parts = urlsplit(self.path)
        if parts.query or parts.fragment or parts.scheme or parts.netloc:
            raise PreviewError("URL_FIELDS_REJECTED", "Use the on-page form; private fields do not belong in URLs.", 400)
        return parts.path

    def _cookies(self):
        try:
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            return {key: value.value for key, value in cookies.items()}
        except Exception:
            return {}

    def _customer(self, create=False):
        token = self._cookies().get("kw_preview")
        if not create:
            if not token:
                raise PreviewError("SESSION_REQUIRED", "Reload the preview to establish a private session.", 401)
            with self.server.store.tx() as db:
                row = db.execute("SELECT csrf FROM sessions WHERE token_hash=?", (digest(token),)).fetchone()
                if not row:
                    raise PreviewError("SESSION_REQUIRED", "Reload the preview to establish a private session.", 401)
                return token, row[0]
        return self.server.store.session(token)

    def _current(self, token, csrf):
        return {"mode": "LOCAL_FAKE_PREVIEW", "sample_only": True, "csrf": csrf,
                "server_time": stamp(self.server.store.clock()),
                "order": self.server.store.current(token)}

    def _operator(self):
        token = self._cookies().get("kw_operator", "")
        expires = self.server.operator_sessions.get(digest(token))
        if not expires or expires <= datetime.now(timezone.utc):
            raise PreviewError("OPERATOR_REQUIRED", "Enter the private local operator token.", 401)

    def do_GET(self):
        try:
            path = self._path()
            if path in PAGES:
                self._headers(200, "text/html; charset=utf-8")
                self.wfile.write((WEB / "index.html").read_bytes())
            elif path in ASSETS:
                filename, content_type = ASSETS[path]
                self._headers(200, content_type)
                self.wfile.write((WEB / filename).read_bytes())
            elif path == "/api/current":
                token, csrf = self._customer(create=True)
                self._json(self._current(token, csrf), cookie=f"kw_preview={token}; HttpOnly; SameSite=Strict; Path=/")
            elif path == "/api/report":
                token, _ = self._customer()
                self._json({"text": self.server.store.report(token)})
            elif path == "/api/operator/orders":
                self._operator()
                self._json({"orders": self.server.store.all_orders()})
            else:
                raise PreviewError("NOT_FOUND", "No local preview route was found.", 404)
        except PreviewError as error:
            self._fail(error)
        except Exception:
            self._fail(PreviewError("PREVIEW_UNAVAILABLE", "The local preview is unavailable. No external action occurred.", 503))

    def _body(self, csrf):
        expected_origin = "http://" + self.headers.get("Host", "")
        if self.headers.get("Origin") != expected_origin or not secrets.compare_digest(self.headers.get("X-Preview-CSRF", ""), csrf):
            raise PreviewError("REQUEST_REJECTED", "Reload this local page before trying again.", 403)
        if self.headers.get_content_type() != "application/json":
            raise PreviewError("JSON_REQUIRED", "Use the on-page form.", 415)
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 <= length <= 8192:
            raise PreviewError("BODY_LIMIT", "The preview accepts only a short brief.", 413)
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError()
                value[key] = item
            return value
        def reject_constant(value):
            raise ValueError()
        try:
            body = json.loads(self.rfile.read(length), object_pairs_hook=unique, parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise PreviewError("INVALID_JSON", "Use a valid short JSON request.", 400) from None
        if not isinstance(body, dict):
            raise PreviewError("INVALID_JSON", "Use a JSON object.", 400)
        return body

    def do_POST(self):
        try:
            path = self._path()
            token, csrf = self._customer()
            body = self._body(csrf)
            simple_fields = {"/api/checkout": {"accept_preview_terms"}, "/api/pay": {"outcome"},
                             "/api/revision": {"request"}, "/api/recovery": set(),
                             "/api/recover": {"recovery_key"}, "/api/reconcile": set(),
                             "/api/retry": set(), "/api/operator/login": {"token"},
                             "/api/operator/action": {"order_id", "action"}}
            if path != "/api/brief" and (path not in simple_fields or set(body) != simple_fields[path]):
                raise PreviewError("INVALID_REQUEST", "Use an available on-page action.", 400)
            store = self.server.store
            if path == "/api/brief":
                store.submit(token, body)
            elif path == "/api/checkout":
                store.checkout(token, body["accept_preview_terms"])
            elif path == "/api/pay":
                store.pay(token, body["outcome"])
            elif path == "/api/reconcile":
                store.reconcile_all()
            elif path == "/api/retry":
                store.retry(token)
            elif path == "/api/revision":
                store.revision(token, body["request"])
            elif path == "/api/recovery":
                store.current(token)  # Only return the authenticated browser's key.
                return self._json({"recovery_key": token})
            elif path == "/api/recover":
                token, csrf = store.recover(body["recovery_key"])
                return self._json(self._current(token, csrf), cookie=f"kw_preview={token}; HttpOnly; SameSite=Strict; Path=/")
            elif path == "/api/operator/login":
                now = datetime.now(timezone.utc)
                self.server.login_failures = [time for time in self.server.login_failures if time > now - timedelta(minutes=1)]
                if len(self.server.login_failures) >= 5:
                    raise PreviewError("LOGIN_LIMIT", "Wait a minute before retrying the local operator token.", 429)
                if not isinstance(body["token"], str) or not secrets.compare_digest(body["token"], self.server.operator_key):
                    self.server.login_failures.append(now)
                    raise PreviewError("OPERATOR_REQUIRED", "The local operator token did not match.", 401)
                operator_token = secrets.token_urlsafe(32)
                self.server.operator_sessions[digest(operator_token)] = now + timedelta(hours=1)
                return self._json({"operator": True}, cookie=f"kw_operator={operator_token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600")
            elif path == "/api/operator/action":
                self._operator()
                return self._json({"order": store.operate(body["order_id"], body["action"])})
            return self._json(self._current(token, csrf))
        except PreviewError as error:
            self._fail(error)
        except Exception:
            self._fail(PreviewError("PREVIEW_UNAVAILABLE", "The local preview is unavailable. Existing state is retained; no live action occurred.", 503))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", required=True, help="Private directory outside every Git checkout; fictional data only")
    parser.add_argument("--reconcile-once", action="store_true", help="Reconcile the fake local provider then exit, without a browser")
    args = parser.parse_args(argv)
    server = PreviewServer(args.port, args.data_dir)
    if args.reconcile_once:
        server.server_close()
        print("Local fake-provider reconciliation completed. No network payment or mail action.")
        return
    print(f"PRIVATE FAKE PREVIEW http://127.0.0.1:{server.server_address[1]} — fictional data only; no charges", flush=True)
    print(f"Private operator token file: {server.data_dir / 'operator.token'} (never put it in a URL)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
