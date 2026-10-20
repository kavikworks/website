"""Recovery rotation, additive migration and explicit retention with fake data."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview.purchase.maintenance import RetentionPolicy
from preview.purchase.model import PreviewError, Store, digest
from test_purchase_preview import brief


class MaintenanceContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 10, 19, 16, tzinfo=timezone.utc)
        self.path = Path(self.temp.name) / "preview.sqlite3"
        self.store = Store(self.path, clock=lambda: self.now)
        self.token, _ = self.store.session()

    def count(self, table):
        with self.store.tx() as db: return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def open(self):
        self.store.submit(self.token, brief())
        return self.store.checkout(self.token, True)

    def delivered(self):
        order = self.open(); self.store.pay(self.token, "paid")
        for action in ("draft", "qa_pass", "deliver"):
            order = self.store.operate(order["id"], action)
        return order

    def test_rotation_revokes_old_access_and_lost_response_recovers_with_proposed_key(self):
        first = self.store.submit(self.token, brief())
        replacement = secrets.token_urlsafe(32)
        result = self.store.rotate_recovery(self.token, replacement)
        restarted = Store(self.path, clock=lambda: self.now)
        self.assertEqual(restarted.recover(replacement)[0], replacement)
        self.assertEqual(restarted.current(replacement), first)
        self.assertIsNone(restarted.current(self.token))
        with self.assertRaises(PreviewError): restarted.recover(self.token)
        self.assertEqual(restarted.rotate_recovery(self.token, replacement), result)
        with self.assertRaises(PreviewError): restarted.rotate_recovery(self.token, secrets.token_urlsafe(32))
        with self.store.tx() as db:
            rows = json.dumps([tuple(row) for row in db.execute("SELECT * FROM recovery_rotations")])
        self.assertNotIn(self.token, rows); self.assertNotIn(replacement, rows)

    def test_rotation_cannot_take_over_another_customer_or_reuse_existing_token(self):
        first = self.store.submit(self.token, brief())
        other, _ = self.store.session(); self.store.submit(other, brief(1))
        with self.assertRaises(PreviewError): self.store.rotate_recovery(self.token, other)
        for replacement in ("bad", self.token, None):
            with self.assertRaises(PreviewError): self.store.rotate_recovery(self.token, replacement)
        self.assertEqual(self.store.current(self.token), first)
        self.assertEqual(self.count("orders"), 2)

    def test_additive_migration_preserves_legacy_session_and_starts_conservative_clock(self):
        legacy = Path(self.temp.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy)) as db:
            db.execute("CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,csrf TEXT NOT NULL)")
            db.execute("INSERT INTO sessions VALUES(?,?)", (digest(self.token), "TEST_ONLY_CSRF"))
            db.commit()
        store = Store(legacy, clock=lambda: self.now)
        self.assertEqual(store.session(self.token), (self.token, "TEST_ONLY_CSRF"))
        self.assertEqual(store.apply_retention(RetentionPolicy(empty_session_days=1))["sessions_deleted"], 0)
        self.now += timedelta(days=1)
        self.assertEqual(store.apply_retention(RetentionPolicy(empty_session_days=1))["sessions_deleted"], 1)

    def test_disabled_or_invalid_retention_never_silently_chooses_a_policy(self):
        self.store.submit(self.token, brief(workflow="OTHER"))
        self.now += timedelta(days=100)
        self.assertEqual(self.store.apply_retention(RetentionPolicy())["orders_deleted"], 0)
        for value in (0, -1, True, 1.5, "30", 3651):
            with self.assertRaises(ValueError): RetentionPolicy(unpaid_days=value)
        with self.assertRaises(ValueError): self.store.apply_retention({"unpaid_days": 30})

    def test_abandoned_content_deletion_preserves_hashed_submission_replay_tombstone(self):
        self.store.submit(self.token, brief(workflow="OTHER"))
        self.now += timedelta(days=30)
        result = self.store.apply_retention(RetentionPolicy(unpaid_days=30))
        self.assertEqual((result["orders_deleted"], self.count("orders"), self.count("sessions")), (1, 0, 0))
        self.assertEqual(self.count("retired_keys"), 1)
        token, _ = self.store.session()
        with self.assertRaisesRegex(PreviewError, "replayed"):
            self.store.submit(token, brief(workflow="OTHER"))
        self.assertEqual(self.count("orders"), 0)

    def test_safe_edit_resets_unpaid_content_clock(self):
        self.store.submit(self.token, brief(workflow="OTHER"))
        self.now += timedelta(days=29)
        self.store.submit(self.token, brief(1, workflow="OTHER"))
        self.now += timedelta(days=1)
        self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=30))["orders_deleted"], 0)
        self.now += timedelta(days=29)
        self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=30))["orders_deleted"], 1)

    def test_unknown_provider_and_processing_payments_are_never_deleted(self):
        self.open(); self.store.pay(self.token, "processing")
        with self.store.tx() as db:
            db.execute("UPDATE settings SET value=? WHERE key='provider'", (json.dumps({"available": False}),))
        self.now += timedelta(days=100)
        self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=1, delivered_days=1))["orders_deleted"], 0)
        self.assertEqual(self.store.current(self.token)["reservation_state"], "HELD")

    def test_closed_unpaid_checkout_requires_current_authoritative_readback(self):
        self.open(); self.store.pay(self.token, "failed")
        self.now += timedelta(days=31)
        with self.store.tx() as db:
            db.execute("UPDATE settings SET value=? WHERE key='provider'", (json.dumps({"available": False}),))
        self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=30))["orders_deleted"], 0)
        with self.store.tx() as db:
            db.execute("UPDATE settings SET value=? WHERE key='provider'", (json.dumps({"available": True}),))
        self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=30))["orders_deleted"], 1)

    def test_paid_drafting_and_revision_obligations_are_not_deleted(self):
        self.open(); self.store.pay(self.token, "paid")
        self.now += timedelta(days=100)
        self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=1, delivered_days=1))["orders_deleted"], 0)
        self.assertEqual(self.count("cases"), 1)

    def test_retention_waits_for_revision_window_and_honors_hold(self):
        order = self.delivered()
        policy = RetentionPolicy(delivered_days=30)
        self.now += timedelta(days=30)
        self.assertEqual(self.store.apply_retention(policy)["orders_deleted"], 0)
        self.store.retention_hold(order["id"], True)
        self.now += timedelta(days=7)
        self.assertEqual(self.store.apply_retention(policy)["held_orders"], 1)
        self.store.retention_hold(order["id"], False)
        self.assertEqual(self.store.apply_retention(policy)["orders_deleted"], 1)
        self.assertEqual(self.count("cases"), 0)
        with self.assertRaises(PreviewError): self.store.recover(self.token)

    def test_pending_revision_is_retained_and_final_revision_restarts_closure_clock(self):
        order = self.delivered()
        self.store.revision(self.token, "TEST_ONLY: clarify the office owner handoff in the plan.")
        self.now += timedelta(days=100)
        policy = RetentionPolicy(delivered_days=30)
        self.assertEqual(self.store.apply_retention(policy)["orders_deleted"], 0)
        for action in ("revision_draft", "revision_qa_pass", "revision_deliver"):
            self.store.operate(order["id"], action)
        self.assertEqual(self.store.apply_retention(policy)["orders_deleted"], 0)
        self.now += timedelta(days=30)
        self.assertEqual(self.store.apply_retention(policy)["orders_deleted"], 1)

    def test_unknown_legacy_final_revision_age_starts_conservative_clock(self):
        self.delivered()
        with self.store.tx() as db:
            db.execute("UPDATE cases SET state='REVISION_DELIVERED',last_delivered_at=NULL")
        self.now += timedelta(days=100)
        restarted = Store(self.path, clock=lambda: self.now)
        self.assertEqual(restarted.apply_retention(RetentionPolicy(delivered_days=30))["orders_deleted"], 0)
        self.now += timedelta(days=30)
        self.assertEqual(restarted.apply_retention(RetentionPolicy(delivered_days=30))["orders_deleted"], 1)

    def test_retirement_prevents_old_event_and_immutable_payment_reuse(self):
        self.delivered()
        with self.store.tx() as db:
            old_session = db.execute("SELECT provider_id FROM orders").fetchone()[0]
            old_payment = db.execute("SELECT payment_id FROM cases").fetchone()[0]
        self.store.event("TEST_ONLY_OLD_EVENT", old_session)
        self.now += timedelta(days=38)
        self.store.apply_retention(RetentionPolicy(delivered_days=30))
        with self.assertRaises(PreviewError): self.store.event("TEST_ONLY_NEW_EVENT", old_session)
        with self.store.tx() as db:
            db.execute("DELETE FROM settings WHERE key IN ('capacity','provider')")
            self.store.seed_demo(db)
        new_token, _ = self.store.session()
        self.store.submit(new_token, brief(2)); self.store.checkout(new_token, True)
        with self.store.tx() as db:
            new_session = db.execute("SELECT provider_id FROM orders").fetchone()[0]
            snapshot = self.store.provider.simulate(db, new_session, "paid", self.now)
            snapshot["payment_id"] = old_payment
            self.store.provider.save(db, snapshot)
        with self.assertRaises(PreviewError): self.store.event("TEST_ONLY_OLD_EVENT", new_session)
        self.store.reconcile_all()
        self.assertEqual(self.store.current(new_token)["state"], "PAYMENT_REVIEW")
        self.assertEqual(self.count("cases"), 0)

    def test_maintenance_is_offline_and_preserves_an_unrelated_customer(self):
        self.store.submit(self.token, brief(workflow="OTHER"))
        self.now += timedelta(days=29)
        other, _ = self.store.session(); expected = self.store.submit(other, brief(1, workflow="OTHER"))
        self.now += timedelta(days=1)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.store.apply_retention(RetentionPolicy(unpaid_days=30))["orders_deleted"], 1)
        self.assertEqual(self.store.current(other), expected)


if __name__ == "__main__": unittest.main()
