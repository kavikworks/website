"""Synthetic, deterministic lifecycle contracts; no real payment or customer data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview.purchase.model import FakeProvider, PreviewError, Store, validate_brief


def brief(index=0, **changes):
    result = {"workflow": "QUOTE_REQUEST", "tools": "TEST_ONLY shared inbox and spreadsheet",
              "handoff": "TEST_ONLY: keep estimate requests together and assign an office owner.",
              "admin_only": True, "one_workflow": True, "no_sensitive_data": True,
              "written_plan_only": True, "submission_key": f"TEST_ONLY_SUBMISSION_{index:016d}"}
    result.update(changes)
    return result


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 10, 19, 16, tzinfo=timezone.utc)
        self.store = Store(Path(self.temp.name) / "preview.sqlite3", clock=lambda: self.now)
        self.token, self.csrf = self.store.session()

    def setting(self, key, changes):
        with self.store.tx() as db:
            value = json.loads(db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()[0])
            value.update(changes)
            db.execute("UPDATE settings SET value=? WHERE key=?", (json.dumps(value), key))

    def snapshot(self, session_id=None, **changes):
        with self.store.tx() as db:
            if session_id is None:
                session_id = db.execute("SELECT provider_id FROM orders LIMIT 1").fetchone()[0]
            value = json.loads(db.execute("SELECT snapshot FROM provider_sessions WHERE id=?", (session_id,)).fetchone()[0])
            value.update(changes)
            self.store.provider.save(db, value)
            return value

    def count(self, table):
        with self.store.tx() as db:
            return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def open(self, index=0, token=None):
        token = token or self.token
        self.store.submit(token, brief(index))
        return self.store.checkout(token, True)

    def paid(self):
        self.open()
        return self.store.pay(self.token, "paid")

    def delivered(self):
        order = self.paid()
        for action in ("draft", "qa_pass", "deliver"):
            order = self.store.operate(order["id"], action)
        return order

    def one_slot(self):
        with self.store.tx() as db:
            cap = json.loads(db.execute("SELECT value FROM settings WHERE key='capacity'").fetchone()[0])
        days = sorted(cap["calendar"])
        calendar = {day: {"production": 0, "qa": 0} for day in days}
        calendar[days[0]] = {"production": 180, "qa": 45}
        calendar[days[5]] = {"production": 45, "qa": 20}
        self.setting("capacity", {"calendar": calendar})
        return days

    def test_supported_workflows_progress_without_email_or_owner_gate(self):
        for index, workflow in enumerate(("QUOTE_REQUEST", "LEASING_INQUIRY", "ADMIN_INBOX")):
            token, _ = self.store.session()
            order = self.store.submit(token, brief(index, workflow=workflow))
            self.assertEqual((order["scope_status"], order["state"]), ("ELIGIBLE", "RESERVED"))
            self.assertTrue(order["delivery_date"])
            self.store.checkout(token, True)
            paid = self.store.pay(token, "paid")
            self.assertEqual(paid["case"]["state"], "DRAFTING")
        self.assertEqual(self.count("cases"), 3)

    def test_missing_fields_and_invalid_types_are_rejected_without_persistence(self):
        for change in ({"tools": ""}, {"handoff": "short"}, {"workflow": []},
                       {"admin_only": "yes"}, {"submission_key": "bad"}, {"tools": "x" * 121},
                       {"handoff": "x\x00" * 20}):
            with self.assertRaises(PreviewError):
                self.store.submit(self.token, brief(**change))
        payload = brief(); payload.pop("handoff")
        with self.assertRaises(PreviewError):
            self.store.submit(self.token, payload)
        self.assertEqual(self.count("orders"), 0)

    def test_ambiguous_and_unsupported_scope_never_offer_checkout(self):
        for index, changes in enumerate(({"workflow": "OTHER"}, {"one_workflow": False},
                                        {"handoff": "TEST_ONLY: make medical diagnosis decisions automatically."},
                                        {"written_plan_only": False}, {"no_sensitive_data": False})):
            token, _ = self.store.session()
            order = self.store.submit(token, brief(index, **changes))
            self.assertIn(order["state"], {"NEEDS_REVIEW", "UNSUPPORTED"})
            self.assertIsNone(order["delivery_date"])
            with self.assertRaises(PreviewError):
                self.store.checkout(token, True)
        self.assertEqual(self.count("provider_sessions"), 0)

    def test_duplicate_submit_and_response_loss_recover_same_order(self):
        first = self.store.submit(self.token, brief())
        self.assertEqual(first, self.store.submit(self.token, brief()))
        self.assertEqual(first, self.store.current(self.token))
        recovered, _ = self.store.recover(self.token)
        self.assertEqual(first, self.store.current(recovered))
        self.assertEqual(self.count("orders"), 1)
        self.assertEqual(self.count("allocations"), 6)
        with self.assertRaises(PreviewError):
            self.store.submit(self.token, brief(tools="TEST_ONLY changed tools"))

    def test_persistence_survives_process_restart(self):
        first = self.open()
        restarted = Store(self.store.path, clock=lambda: self.now)
        self.assertEqual(first, restarted.current(self.token))
        self.assertEqual(self.token, restarted.recover(self.token)[0])

    def test_capacity_exhaustion_and_concurrent_reservations_are_atomic(self):
        self.one_slot()
        tokens = [self.store.session()[0] for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda args: self.store.submit(args[1], brief(args[0])), enumerate(tokens)))
        self.assertEqual(sorted(order["state"] for order in results), ["CAPACITY_UNAVAILABLE", "RESERVED"])

    def test_open_payable_invitations_and_paid_obligations_reduce_capacity(self):
        for kind in ("PAID", "OPEN_INVITATION", "RESERVED_COMMITMENT"):
            days = self.one_slot()
            with self.store.tx() as db:
                db.execute("DELETE FROM obligations")
                db.execute("INSERT INTO obligations VALUES(?,?,?,?,?)", ("TEST_ONLY_OBLIGATION", kind, days[0], 180, 45))
            token, _ = self.store.session()
            order = self.store.submit(token, brief(len(kind)))
            self.assertEqual(order["state"], "CAPACITY_UNAVAILABLE")

    def test_unknown_stale_qa_delivery_or_incident_capacity_fails_closed(self):
        for index, change in enumerate(({"inventory_complete": False}, {"qa_available": False},
                                        {"private_delivery_ready": False}, {"material_incident": True},
                                        {"valid_until": "2026-10-18T00:00:00+00:00"},
                                        {"calendar": {"bad": {"production": -1}}})):
            with self.store.tx() as db:
                db.execute("DELETE FROM settings WHERE key IN ('capacity','provider')")
                self.store.seed_demo(db)
            self.setting("capacity", change)
            token, _ = self.store.session()
            self.assertEqual(self.store.submit(token, brief(index))["state"], "CAPACITY_UNAVAILABLE")

    def test_no_arbitrary_two_order_cap(self):
        for index in range(6):
            token, _ = self.store.session()
            self.assertEqual(self.store.submit(token, brief(index))["state"], "RESERVED")

    def test_invalid_external_obligation_effort_cannot_increase_capacity(self):
        days = self.one_slot()
        with self.store.tx() as db:
            db.execute("INSERT INTO obligations VALUES(?,?,?,?,?)", ("TEST_ONLY_BAD_EFFORT", "OPEN_INVITATION", days[0], -180, 0))
        self.assertEqual(self.store.submit(self.token, brief())["state"], "CAPACITY_UNAVAILABLE")

    def test_payment_unavailable_fails_closed_without_losing_intake(self):
        self.setting("provider", {"available": False})
        order = self.store.submit(self.token, brief())
        self.assertEqual(order["state"], "PAYMENT_UNAVAILABLE")
        self.assertIsNone(order["reservation_state"])
        self.assertEqual(self.count("orders"), 1)
        self.assertEqual(self.count("provider_sessions"), 0)

    def test_checkout_terms_and_creation_idempotency(self):
        self.store.submit(self.token, brief())
        with self.assertRaises(PreviewError):
            self.store.checkout(self.token, False)
        self.now += timedelta(minutes=20)
        opened = self.store.checkout(self.token, True)
        self.assertEqual(opened, self.store.checkout(self.token, True))
        self.assertEqual(self.count("provider_sessions"), 1)
        self.assertEqual(datetime.fromisoformat(opened["checkout_expires_at"]), self.now + timedelta(minutes=30))

    def test_abandonment_stays_reserved_until_authoritative_expiry(self):
        self.one_slot(); self.open()
        self.store.pay(self.token, "abandon")
        self.assertEqual(self.store.current(self.token)["reservation_state"], "HELD")
        self.now += timedelta(minutes=31)
        self.store.reconcile_all()
        order = self.store.current(self.token)
        self.assertEqual((order["state"], order["reservation_state"]), ("EXPIRED", "RELEASED"))
        fresh, _ = self.store.session()
        self.assertEqual(self.store.submit(fresh, brief(9))["state"], "RESERVED")

    def test_reserved_but_never_opened_checkout_expires(self):
        self.store.submit(self.token, brief())
        self.now += timedelta(minutes=31)
        self.store.reconcile_all()
        self.assertEqual(self.store.current(self.token)["state"], "EXPIRED")

    def test_unknown_verification_never_releases_expired_capacity(self):
        self.open(); self.setting("provider", {"available": False})
        self.now += timedelta(hours=2)
        self.store.reconcile_all()
        self.assertEqual(self.store.current(self.token)["reservation_state"], "HELD")
        with self.assertRaises(PreviewError):
            self.store.retry(self.token)

    def test_failed_payment_can_retry_same_order_without_reopening_old_checkout(self):
        first = self.open()
        self.store.pay(self.token, "failed")
        old = self.snapshot()["id"]
        retried = self.store.retry(self.token)
        self.assertEqual(first["id"], retried["id"])
        self.store.checkout(self.token, True)
        self.assertEqual(self.count("provider_sessions"), 2)
        self.store.event("TEST_ONLY_OLD_FAILURE", old)
        paid = self.store.pay(self.token, "paid")
        self.assertEqual(paid["state"], "PAID")
        self.assertEqual(self.count("cases"), 1)
        with self.assertRaises(PreviewError):
            self.store.retry(self.token)

    def test_processing_payment_retains_capacity_past_checkout_expiry(self):
        first = self.open()
        self.store.pay(self.token, "processing")
        self.now += timedelta(hours=2)
        self.store.reconcile_all()
        pending = self.store.current(self.token)
        self.assertEqual((pending["state"], pending["reservation_state"]), ("PAYMENT_PENDING", "HELD"))
        self.assertEqual(self.count("cases"), 0)
        settled = self.store.operate(first["id"], "settle_payment")
        self.assertEqual(settled["case"]["state"], "DRAFTING")

    def test_final_payment_without_browser_return_recovers_one_case(self):
        self.open()
        with self.store.tx() as db:
            order = db.execute("SELECT * FROM orders").fetchone()
            self.store.provider.simulate(db, order["provider_id"], "paid", self.now)
        restarted = Store(self.store.path, clock=lambda: self.now)
        restarted.reconcile_all()
        restarted.reconcile_all()
        self.assertEqual(restarted.current(self.token)["case"]["state"], "DRAFTING")
        self.assertEqual(self.count("cases"), 1)

    def test_duplicate_concurrent_and_reordered_events_create_one_case(self):
        self.paid(); session_id = self.snapshot()["id"]
        events = ["TEST_ONLY_PAID", "TEST_ONLY_PAID", "TEST_ONLY_OLD_COMPLETE", "TEST_ONLY_OLD_FAILED"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda event: self.store.event(event, session_id), events))
        self.assertEqual(self.count("cases"), 1)
        self.assertEqual(self.store.current(self.token)["state"], "PAID")
        self.store.pay(self.token, "failed")
        self.assertEqual(self.store.current(self.token)["state"], "PAID")

    def test_wrong_amount_currency_order_quantity_or_mode_is_never_paid(self):
        first = self.open(); original = self.snapshot()
        for changes in ({"amount_total": 1}, {"currency": "eur"}, {"quantity": 2},
                        {"livemode": True}, {"order_id": "TEST_ONLY_WRONG_ORDER"}):
            with self.store.tx() as db:
                db.execute("UPDATE orders SET state='CHECKOUT_OPEN',reasons='[]'")
            self.snapshot(**{**original, **changes, "payment_status": "paid", "status": "complete"})
            self.store.reconcile_all()
            self.assertEqual(self.store.current(self.token)["state"], "PAYMENT_REVIEW")
            self.assertEqual(self.store.current(self.token)["payment_status"], "unpaid")
            self.assertEqual(self.count("cases"), 0)

    def test_paid_after_released_capacity_creates_review_obligation_not_auto_delivery(self):
        self.open(); self.now += timedelta(hours=1); self.store.reconcile_all()
        self.snapshot(status="complete", payment_status="paid", paid_at=self.now.isoformat(), payment_id="fake_pi_TEST_ONLY_LATE")
        self.store.reconcile_all()
        order = self.store.current(self.token)
        self.assertEqual(order["state"], "PAYMENT_REVIEW")
        self.assertEqual(order["case"]["state"], "PAYMENT_REVIEW")
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "draft")

    def test_case_requires_separate_qa_before_private_delivery(self):
        order = self.paid()
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "deliver")
        self.store.operate(order["id"], "draft", actor="TEST_ONLY_DRAFTER")
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "qa_pass", actor="TEST_ONLY_DRAFTER")
        self.store.operate(order["id"], "qa_fail")
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "deliver")
        self.store.operate(order["id"], "draft")
        self.store.operate(order["id"], "qa_pass")
        self.setting("capacity", {"private_delivery_ready": False})
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "deliver")
        self.setting("capacity", {"private_delivery_ready": True})
        delivered = self.store.operate(order["id"], "deliver")
        self.assertTrue(delivered["case"]["report_available"])
        report = self.store.report(self.token)
        for section in ("Workflow map", "Capture fields", "Three editable templates", "Setup instructions", "Acceptance tests"):
            self.assertIn(section, report)

    def test_revision_keeps_published_report_until_new_independent_qa_and_delivery(self):
        order = self.delivered(); previous = self.store.report(self.token)
        self.store.revision(self.token, "TEST_ONLY: clarify who owns a request when the office is closed.")
        self.store.operate(order["id"], "revision_draft")
        self.assertEqual(self.store.report(self.token), previous)
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "revision_deliver")
        self.store.operate(order["id"], "qa_fail")
        self.store.operate(order["id"], "revision_draft")
        self.store.operate(order["id"], "revision_qa_pass")
        self.assertEqual(self.store.report(self.token), previous)
        self.store.operate(order["id"], "revision_deliver")
        self.assertNotEqual(self.store.report(self.token), previous)
        with self.assertRaises(PreviewError):
            self.store.revision(self.token, "TEST_ONLY: a second clarification should not be accepted.")

    def test_revision_window_and_missing_report_are_enforced(self):
        with self.assertRaises(PreviewError):
            self.store.report(self.token)
        self.delivered()
        self.now += timedelta(days=7, seconds=1)
        with self.assertRaises(PreviewError):
            self.store.revision(self.token, "TEST_ONLY: clarification outside the seven-day request window.")

    def test_core_cannot_use_network_or_an_external_provider(self):
        with patch("socket.socket", side_effect=AssertionError("External network forbidden")):
            self.paid()
        with self.assertRaises(ValueError):
            Store(self.store.path, provider=object())

    def test_readiness_is_rechecked_before_checkout_without_double_counting(self):
        self.one_slot()
        order = self.store.submit(self.token, brief())
        self.setting("capacity", {"qa_available": False})
        with self.assertRaises(PreviewError):
            self.store.checkout(self.token, True)
        self.assertEqual(self.count("provider_sessions"), 0)
        self.setting("capacity", {"qa_available": True})
        self.assertEqual(self.store.checkout(self.token, True)["state"], "CHECKOUT_OPEN")

    def test_delayed_payment_with_past_promise_is_one_review_obligation(self):
        self.open(); self.store.pay(self.token, "processing")
        self.now += timedelta(days=14)
        order = self.store.operate(self.store.current(self.token)["id"], "settle_payment")
        self.assertEqual((order["state"], order["payment_status"], order["case"]["state"]), ("PAYMENT_REVIEW", "paid", "PAYMENT_REVIEW"))
        self.store.reconcile_all()
        self.assertEqual(self.count("cases"), 1)
        with self.assertRaises(PreviewError):
            self.store.operate(order["id"], "draft")

    def test_adjudication_and_ambiguous_semantics_do_not_pass_acknowledgments(self):
        for handoff in ("TEST_ONLY: decide whether applicants qualify for a lease and automatically reject them.",
                        "TEST_ONLY: approve mortgage loans using supplied application information.",
                        "TEST_ONLY: please make our entire business work better."):
            result = validate_brief(brief(handoff=handoff))
            self.assertNotEqual(result[2], "ELIGIBLE")

    def test_safe_precheckout_edit_replans_one_order_and_old_replays_do_not_overwrite(self):
        self.one_slot()
        original = brief(workflow="OTHER")
        first = self.store.submit(self.token, original)
        changed = self.store.submit(self.token, brief(1))
        self.assertEqual(first["id"], changed["id"])
        self.assertEqual(changed["state"], "RESERVED")
        self.assertEqual(self.count("orders"), 1)
        self.assertEqual(self.store.submit(self.token, original), changed)
        self.assertEqual(self.count("allocations"), 6)
        self.store.checkout(self.token, True)
        with self.assertRaises(PreviewError):
            self.store.submit(self.token, brief(2))

    def test_out_of_scope_revision_cannot_expand_paid_scope(self):
        self.delivered()
        with self.assertRaises(PreviewError):
            self.store.revision(self.token, "TEST_ONLY: implement and monitor my live accounts instead.")


if __name__ == "__main__":
    unittest.main()
