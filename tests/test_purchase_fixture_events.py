"""Synthetic signature, replay and provider-authority integration contracts."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview.purchase.fixture_events import FixtureEventError, apply_fixture_event, verify_fixture_event
from preview.purchase.model import Store
from preview.purchase.payment_contracts import DEFAULT_BINDING

# This literal cannot be used as any provider credential or endpoint secret.
KEY = b"TEST_ONLY_signature_contract_fixture_key_20261018"
SESSION = "fake_cs_ord_" + "a" * 32 + "_1"
NOW = datetime(2026, 10, 19, 16, tzinfo=timezone.utc)


def body(session=SESSION, **changes):
    value = {"id": "fixture_evt_one", "type": "checkout.session.completed",
             "account": DEFAULT_BINDING.account, "environment": DEFAULT_BINDING.environment,
             "livemode": False, "fixture": True, "data": {"object": {"id": session}}}
    value.update(changes)
    return json.dumps(value, separators=(",", ":")).encode()


def signed(raw, timestamp=None, key=KEY):
    timestamp = int(NOW.timestamp()) if timestamp is None else timestamp
    signature = hmac.new(key, str(timestamp).encode() + b"." + raw, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


class SignatureBoundary(unittest.TestCase):
    def test_valid_explicit_fixture_and_raw_bytes(self):
        raw = body()
        value = verify_fixture_event(raw, signed(raw), KEY, NOW)
        self.assertEqual((value.event_id, value.session_id), ("fixture_evt_one", SESSION))

    def test_tampered_body_fails_before_dispatch(self):
        raw = body()
        with self.assertRaisesRegex(FixtureEventError, "MISMATCH"):
            verify_fixture_event(raw + b" ", signed(raw), KEY, NOW)

    def test_timestamp_tampering_stale_and_future_are_rejected(self):
        raw = body()
        for delta in (-301, 301):
            with self.assertRaisesRegex(FixtureEventError, "TOLERANCE"):
                verify_fixture_event(raw, signed(raw, int(NOW.timestamp()) + delta), KEY, NOW)
        with self.assertRaisesRegex(FixtureEventError, "MISMATCH"):
            verify_fixture_event(raw, signed(raw).replace(str(int(NOW.timestamp())), str(int(NOW.timestamp()) - 1)), KEY, NOW)

    def test_clock_and_key_must_be_explicit_synthetic_inputs(self):
        raw = body()
        for key in (b"ordinary_nonfixture_key_that_must_be_rejected", b"TEST_ONLY_short", "TEST_ONLY_not_bytes"):
            with self.assertRaises(FixtureEventError):
                verify_fixture_event(raw, signed(raw), key, NOW)
        with self.assertRaises(FixtureEventError):
            verify_fixture_event(raw, signed(raw), KEY, NOW.replace(tzinfo=None))

    def test_signature_rotation_accepts_a_matching_v1_without_accepting_v0(self):
        raw = body(); valid = signed(raw)
        event = verify_fixture_event(raw, valid + ",v1=" + "0" * 64, KEY, NOW)
        self.assertEqual(event.event_id, "fixture_evt_one")
        with self.assertRaises(FixtureEventError):
            verify_fixture_event(raw, valid.replace("v1=", "v0="), KEY, NOW)

    def test_duplicate_timestamp_missing_or_malformed_signature_fails(self):
        raw = body()
        for header in (signed(raw) + f",t={int(NOW.timestamp())}", "", "t=bad,v1=x", signed(raw) + ",extra=1", "x" * 2049):
            with self.assertRaises(FixtureEventError):
                verify_fixture_event(raw, header, KEY, NOW)

    def test_oversized_nonbytes_and_invalid_json_fail_closed(self):
        for raw in (b"x" * 16385, "not bytes", b""):
            with self.assertRaises(FixtureEventError):
                verify_fixture_event(raw, "", KEY, NOW)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":', b'[]'):
            with self.assertRaises(FixtureEventError):
                verify_fixture_event(raw, signed(raw), KEY, NOW)

    def test_live_events_and_missing_fixture_marker_are_never_accepted(self):
        for changes in ({"livemode": True}, {"livemode": 0}, {"fixture": False}, {"fixture": 1}):
            raw = body(**changes)
            with self.assertRaises(FixtureEventError):
                verify_fixture_event(raw, signed(raw), KEY, NOW)

    def test_unknown_type_real_shaped_ids_and_extra_fields_are_rejected(self):
        for changes in ({"type": "invoice.paid"}, {"type": []}, {"id": "ordinary_event"},
                        {"private_brief": "TEST_ONLY_EXCLUDED_FIELD"},
                        {"data": {"object": {"id": SESSION, "payment_status": "paid"}}},
                        {"data": {"object": {"id": "not_a_fake_session"}}}):
            raw = body(**changes)
            with self.assertRaises(FixtureEventError):
                verify_fixture_event(raw, signed(raw), KEY, NOW)

    def test_signed_foreign_account_or_environment_is_rejected(self):
        for changes in ({"account": "TEST_ONLY_FOREIGN"}, {"environment": "TEST_ONLY_OTHER"}):
            raw = body(**changes)
            with self.assertRaisesRegex(FixtureEventError, "ACCOUNT_ENVIRONMENT_MISMATCH"):
                verify_fixture_event(raw, signed(raw), KEY, NOW)

    def test_errors_do_not_echo_keys_signatures_or_body(self):
        raw = body(); header = signed(raw, key=b"TEST_ONLY_wrong_signature_fixture_key")
        try:
            verify_fixture_event(raw, header, KEY, NOW)
        except FixtureEventError as error:
            self.assertEqual(str(error), "FIXTURE_SIGNATURE_MISMATCH")
            self.assertNotIn(KEY.decode(), str(error))
            self.assertNotIn(header, str(error))
            self.assertNotIn(raw.decode(), str(error))


class FixtureIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "fixture.sqlite3", clock=lambda: NOW)
        self.token, _ = self.store.session()
        self.store.submit(self.token, {"workflow": "QUOTE_REQUEST", "tools": "TEST_ONLY shared inbox",
            "handoff": "TEST_ONLY: capture quote requests and assign an office owner.",
            "admin_only": True, "one_workflow": True, "no_sensitive_data": True,
            "written_plan_only": True, "submission_key": "TEST_ONLY_SIGNATURE_SUBMISSION"})
        self.store.checkout(self.token, True)
        with self.store.tx() as db:
            self.session_id = db.execute("SELECT provider_id FROM orders").fetchone()[0]

    def apply(self, **changes):
        raw = body(self.session_id, **changes)
        return apply_fixture_event(self.store, raw, signed(raw), KEY, NOW)

    def count(self):
        with self.store.tx() as db:
            return db.execute("SELECT count(*) FROM cases").fetchone()[0]

    def test_signed_success_label_cannot_make_unpaid_provider_state_paid(self):
        order = self.apply(type="checkout.session.async_payment_succeeded")
        self.assertEqual(order["payment_status"], "unpaid")
        self.assertEqual(self.count(), 0)

    def test_authoritative_paid_snapshot_creates_one_case_without_page_return(self):
        with self.store.tx() as db:
            self.store.provider.simulate(db, self.session_id, "paid", NOW)
        order = self.apply()
        self.assertEqual(order["case"]["state"], "DRAFTING")
        self.assertEqual(self.count(), 1)

    def test_duplicate_and_reordered_signed_events_do_not_duplicate_or_regress_case(self):
        self.store.pay(self.token, "paid")
        for changes in ({}, {}, {"id": "fixture_evt_old_failure", "type": "checkout.session.async_payment_failed"},
                        {"id": "fixture_evt_old_expiry", "type": "checkout.session.expired"}):
            self.apply(**changes)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.store.current(self.token)["state"], "PAID")

    def test_invalid_signature_has_no_event_or_case_side_effect(self):
        raw = body(self.session_id)
        with self.assertRaises(FixtureEventError):
            apply_fixture_event(self.store, raw, signed(raw)[:-1] + "x", KEY, NOW)
        with self.store.tx() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.assertEqual(self.count(), 0)

    def test_valid_signed_event_cannot_authorize_foreign_provider_snapshot(self):
        with self.store.tx() as db:
            original = self.store.provider.simulate(db, self.session_id, "paid", NOW)
        for field in ("account", "environment"):
            with self.store.tx() as db:
                db.execute("UPDATE orders SET state='CHECKOUT_OPEN'")
                snapshot = {**original, field: "TEST_ONLY_FOREIGN"}
                self.store.provider.save(db, snapshot)
            self.apply(id="fixture_evt_" + field)
            self.assertEqual(self.count(), 0)
            self.assertEqual(self.store.current(self.token)["state"], "PAYMENT_REVIEW")

    def test_authoritative_numeric_and_immutable_payment_fields_fail_closed(self):
        with self.store.tx() as db:
            original = self.store.provider.simulate(db, self.session_id, "paid", NOW)
        for changes in ({"quantity": True}, {"tax_cents": False}, {"amount_total": 1},
                        {"currency": "eur"}, {"order_id": "ord_" + "f" * 32},
                        {"status": []}, {"payment_status": {}}, {"environment": None},
                        {"payment_id": ""}, {"paid_at": "not-a-date"},
                        {"paid_at": "2026-10-19T16:00:00"},
                        {"paid_at": (NOW + timedelta(seconds=1)).isoformat()}):
            with self.store.tx() as db:
                db.execute("UPDATE orders SET state='CHECKOUT_OPEN'")
                self.store.provider.save(db, {**original, **changes})
            self.store.reconcile_all()
            self.assertEqual(self.count(), 0)
            self.assertNotEqual(self.store.current(self.token)["payment_status"], "paid")

    def test_fixture_verification_and_dispatch_use_no_network(self):
        with patch("socket.socket", side_effect=AssertionError("No network allowed")):
            self.apply()


if __name__ == "__main__":
    unittest.main()
