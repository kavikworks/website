"""Separate local databases exercise uncertainty, crashes and bounded retry."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview.purchase.durable_outbox import (ContractError, DurableOutbox, FakeEndpoint,
                                             OutcomeUnknown, transaction)
from preview.purchase.payment_contracts import DEFAULT_BINDING, FixtureBinding


class OutboxContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 10, 19, 16, tzinfo=timezone.utc)
        self.endpoint = FakeEndpoint(Path(self.temp.name) / "endpoint.sqlite3")
        self.path = Path(self.temp.name) / "outbox.sqlite3"
        self.box = DurableOutbox(self.path, self.endpoint, lambda: self.now)
        self.payload = {"fixture": True, "account": DEFAULT_BINDING.account,
                        "environment": DEFAULT_BINDING.environment, "order_id": "ord_" + "a" * 32}
        self.key = "TEST_ONLY_CREATE_00000001"

    def plan(self):
        return self.box.plan(self.key, "CREATE_CHECKOUT", self.payload)

    def count(self, table="effects"):
        with transaction(self.endpoint.path) as db:
            return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def next_attempt(self):
        self.now += timedelta(hours=1)
        return self.box.run_one()

    def created(self):
        self.plan()
        return self.box.run_one()["result"]["resource_id"]

    def operation(self, key, kind, **values):
        payload = {"fixture": True, "account": DEFAULT_BINDING.account,
                   "environment": DEFAULT_BINDING.environment, **values}
        self.box.plan(key, kind, payload)
        return payload

    def test_plan_is_durable_without_execution_and_restart_dispatches_once(self):
        self.assertEqual(self.plan()["state"], "PENDING")
        self.assertEqual(self.count(), 0)
        restarted = DurableOutbox(self.path, FakeEndpoint(self.endpoint.path), lambda: self.now)
        self.assertEqual(restarted.run_one()["state"], "CONFIRMED")
        self.assertIsNone(restarted.run_one())
        self.assertEqual(self.plan()["state"], "CONFIRMED")
        self.assertEqual(self.count(), 1)

    def test_response_lost_before_effect_retries_same_operation_after_backoff(self):
        self.plan(); self.endpoint.faults = ["execute_before"]
        first = self.box.run_one()
        self.assertEqual(first["state"], "UNKNOWN")
        self.assertFalse(first["capacity_may_release"])
        self.assertEqual(self.count(), 0)
        self.assertIsNone(self.box.run_one())
        self.assertEqual(self.next_attempt()["state"], "CONFIRMED")
        self.assertEqual(self.count(), 1)

    def test_response_lost_after_committed_effect_reconciles_without_second_create(self):
        self.plan(); self.endpoint.faults = ["execute_after"]
        self.assertEqual(self.box.run_one()["state"], "UNKNOWN")
        self.assertEqual(self.count(), 1)
        with patch.object(self.endpoint, "execute", side_effect=AssertionError("must reconcile first")):
            self.assertEqual(self.next_attempt()["state"], "CONFIRMED")
        self.assertEqual(self.count("resources"), 1)

    def test_process_crash_after_effect_leaves_lease_and_recovers_after_restart(self):
        self.plan(); execute = self.endpoint.execute
        def crash(*args):
            execute(*args)
            raise SystemExit("TEST_ONLY_PROCESS_CRASH")
        with patch.object(self.endpoint, "execute", side_effect=crash):
            with self.assertRaises(SystemExit):
                self.box.run_one()
        self.assertEqual(self.box.status(self.key)["state"], "IN_FLIGHT")
        restarted = DurableOutbox(self.path, FakeEndpoint(self.endpoint.path), lambda: self.now)
        self.assertIsNone(restarted.run_one())
        self.now += timedelta(seconds=61)
        self.assertEqual(restarted.run_one()["state"], "CONFIRMED")
        self.assertEqual(self.count(), 1)

    def test_parallel_workers_do_not_duplicate_external_effect(self):
        self.plan()
        boxes = [DurableOutbox(self.path, FakeEndpoint(self.endpoint.path), lambda: self.now) for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda box: box.run_one(), boxes))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.box.status(self.key)["state"], "CONFIRMED")

    def test_stale_worker_cannot_overwrite_a_newer_claims_confirmation(self):
        self.plan(); execute = self.endpoint.execute
        other = DurableOutbox(self.path, FakeEndpoint(self.endpoint.path), lambda: self.now)
        def slow(*args):
            execute(*args)
            self.now += timedelta(seconds=61)
            self.assertEqual(other.run_one()["state"], "CONFIRMED")
        with patch.object(self.endpoint, "execute", side_effect=slow):
            result = self.box.run_one()
        self.assertEqual((result["state"], result["attempts"]), ("CONFIRMED", 2))
        self.assertEqual(self.count(), 1)

    def test_unknown_lookup_never_attempts_an_unreconciled_execution(self):
        self.plan(); self.endpoint.faults = ["lookup"]
        with patch.object(self.endpoint, "execute", side_effect=AssertionError("unknown is not absent")):
            self.assertEqual(self.box.run_one()["state"], "UNKNOWN")
        self.assertEqual(self.count(), 0)

    def test_retry_budget_stops_without_releasing_or_blind_replaying(self):
        self.plan(); self.endpoint.faults = ["execute_before"] * self.box.MAX_ATTEMPTS
        self.box.run_one()
        for _ in range(self.box.MAX_ATTEMPTS - 1):
            last = self.next_attempt()
        self.assertEqual((last["state"], last["attempts"]), ("REVIEW_REQUIRED", 5))
        self.assertFalse(last["capacity_may_release"])
        self.assertIsNone(self.next_attempt())
        self.assertEqual(self.box.reconcile_review(self.key)["state"], "REVIEW_REQUIRED")
        self.assertEqual(self.count(), 0)

    def test_exhausted_job_can_only_recover_from_actual_readback(self):
        self.plan(); self.endpoint.faults = ["lookup"] * 5
        self.box.run_one()
        for _ in range(4): self.next_attempt()
        self.endpoint.execute(self.key, "CREATE_CHECKOUT", self.payload)
        with patch.object(self.endpoint, "execute", side_effect=AssertionError("review is read-only")):
            self.assertEqual(self.box.reconcile_review(self.key)["state"], "CONFIRMED")
        self.assertEqual(self.count(), 1)

    def test_payload_changes_cannot_reuse_a_pending_or_completed_operation(self):
        self.plan()
        for complete in (False, True):
            if complete: self.box.run_one()
            with self.assertRaisesRegex(ContractError, "IDEMPOTENCY_CONFLICT"):
                self.box.plan(self.key, "CREATE_CHECKOUT", {**self.payload, "order_id": "ord_" + "b" * 32})
        self.assertEqual(self.count(), 1)

    def test_expiry_unknown_retains_capacity_until_authoritative_confirmation(self):
        session_id = self.created()
        self.operation("TEST_ONLY_EXPIRE_00000001", "EXPIRE_CHECKOUT", session_id=session_id)
        self.endpoint.faults = ["execute_after"]
        unknown = self.box.run_one()
        self.assertEqual(unknown["state"], "UNKNOWN")
        self.assertFalse(unknown["capacity_may_release"])
        self.assertTrue(self.next_attempt()["capacity_may_release"])
        self.assertEqual(self.count(), 2)

    def test_paid_or_processing_session_cannot_release_capacity_on_expire(self):
        session_id = self.created()
        for index, state in enumerate(("processing", "paid")):
            with transaction(self.endpoint.path) as db:
                db.execute("UPDATE resources SET state=? WHERE id=?", (state, session_id))
            self.operation(f"TEST_ONLY_EXPIRE_PENDING_{index}", "EXPIRE_CHECKOUT", session_id=session_id)
            result = self.box.run_one()
            self.assertEqual(result["result"]["status"], "retained")
            self.assertFalse(result["capacity_may_release"])

    def test_historical_expiry_receipt_cannot_release_a_now_paid_or_missing_session(self):
        session_id = self.created()
        key = "TEST_ONLY_EXPIRE_STALE_RECEIPT"
        self.operation(key, "EXPIRE_CHECKOUT", session_id=session_id)
        self.endpoint.faults = ["execute_after"]
        self.box.run_one()
        with transaction(self.endpoint.path) as db:
            db.execute("UPDATE resources SET state='paid' WHERE id=?", (session_id,))
        self.assertFalse(self.next_attempt()["capacity_may_release"])
        with transaction(self.endpoint.path) as db:
            db.execute("UPDATE resources SET state='expired' WHERE id=?", (session_id,))
        self.assertTrue(self.box.status(key)["capacity_may_release"])
        with transaction(self.endpoint.path) as db: db.execute("DELETE FROM resources")
        self.assertFalse(self.box.status(key)["capacity_may_release"])

    def test_delivery_response_loss_requires_readback_and_does_not_duplicate_artifact(self):
        self.operation("TEST_ONLY_DELIVERY_00000001", "DELIVER_REPORT", case_id="TEST_ONLY_CASE_ONE", report="TEST_ONLY fictional report")
        self.endpoint.faults = ["execute_after"]
        self.assertFalse(self.box.run_one()["delivery_confirmed"])
        self.assertEqual(self.count("resources"), 1)
        self.assertTrue(self.next_attempt()["delivery_confirmed"])
        self.assertEqual(self.count("resources"), 1)

    def test_missing_private_artifact_readback_does_not_claim_delivery(self):
        self.operation("TEST_ONLY_DELIVERY_00000002", "DELIVER_REPORT", case_id="TEST_ONLY_CASE_TWO", report="TEST_ONLY fictional report")
        self.endpoint.faults = ["execute_after"]
        self.box.run_one()
        with transaction(self.endpoint.path) as db: db.execute("DELETE FROM resources")
        self.assertEqual(self.next_attempt()["state"], "UNKNOWN")
        self.assertFalse(self.box.status("TEST_ONLY_DELIVERY_00000002")["delivery_confirmed"])

    def test_changed_receipt_or_inaccessible_resource_cannot_claim_current_delivery(self):
        key = "TEST_ONLY_DELIVERY_STATUS_CHANGE"
        self.operation(key, "DELIVER_REPORT", case_id="TEST_ONLY_CASE_STATUS", report="TEST_ONLY fictional report")
        self.assertTrue(self.box.run_one()["delivery_confirmed"])
        with transaction(self.endpoint.path) as db:
            receipt = json.loads(db.execute("SELECT receipt FROM effects WHERE operation_id=?", (key,)).fetchone()[0])
            db.execute("UPDATE effects SET receipt=? WHERE operation_id=?", (json.dumps({**receipt, "status": "not_delivered"}), key))
        self.assertFalse(self.box.status(key)["delivery_confirmed"])
        with transaction(self.endpoint.path) as db:
            db.execute("UPDATE effects SET receipt=? WHERE operation_id=?", (json.dumps(receipt), key))
            db.execute("UPDATE resources SET state='inaccessible'")
        self.assertFalse(self.box.status(key)["delivery_confirmed"])
        with transaction(self.endpoint.path) as db: db.execute("UPDATE resources SET state='delivered'")
        self.assertTrue(self.box.status(key)["delivery_confirmed"])

    def test_foreign_authoritative_account_or_environment_requires_review(self):
        for field in ("account", "environment"):
            key = "TEST_ONLY_BINDING_" + field
            self.box.plan(key, "CREATE_CHECKOUT", self.payload)
            self.endpoint.execute(key, "CREATE_CHECKOUT", self.payload)
            with transaction(self.endpoint.path) as db:
                receipt = json.loads(db.execute("SELECT receipt FROM effects WHERE operation_id=?", (key,)).fetchone()[0])
                receipt[field] = "TEST_ONLY_FOREIGN"
                db.execute("UPDATE effects SET receipt=? WHERE operation_id=?", (json.dumps(receipt), key))
            result = self.box.run_one()
            self.assertEqual(result["state"], "REVIEW_REQUIRED")
            self.assertEqual(result["last_error"], "AUTHORITATIVE_RECEIPT_MISMATCH")

    def test_different_configured_endpoint_cannot_receive_the_request(self):
        endpoint = FakeEndpoint(Path(self.temp.name) / "foreign.sqlite3", FixtureBinding(account="TEST_ONLY_OTHER"))
        box = DurableOutbox(self.path, endpoint, lambda: self.now)
        self.plan()
        self.assertEqual(box.run_one()["state"], "REVIEW_REQUIRED")
        with transaction(endpoint.path) as db: self.assertEqual(db.execute("SELECT count(*) FROM effects").fetchone()[0], 0)

    def test_explicit_payload_retirement_preserves_dedupe_and_unresolved_payloads(self):
        self.created()
        self.operation("TEST_ONLY_DELIVERY_RETIRE", "DELIVER_REPORT", case_id="TEST_ONLY_CASE_RETIRE", report="TEST_ONLY report to remove")
        self.now += timedelta(days=31)
        self.assertEqual(self.box.retire_confirmed_payloads(30), 1)
        with transaction(self.path) as db:
            rows = db.execute("SELECT payload,state FROM outbox ORDER BY operation_id").fetchall()
        self.assertIsNone(rows[0]["payload"])
        self.assertIn("TEST_ONLY report to remove", rows[1]["payload"])
        self.assertEqual(self.plan()["state"], "CONFIRMED")
        self.assertEqual(self.count(), 1)

    def test_missing_readback_preserves_even_historically_confirmed_delivery_payload(self):
        key = "TEST_ONLY_DELIVERY_RETENTION_HOLD"
        self.operation(key, "DELIVER_REPORT", case_id="TEST_ONLY_CASE_HOLD", report="TEST_ONLY report still needed")
        self.box.run_one()
        with transaction(self.endpoint.path) as db: db.execute("DELETE FROM resources")
        self.now += timedelta(days=31)
        self.assertEqual(self.box.retire_confirmed_payloads(30), 0)
        with transaction(self.path) as db:
            self.assertIn("TEST_ONLY report still needed", db.execute("SELECT payload FROM outbox").fetchone()[0])

    def test_rejects_real_shaped_inputs_unknown_fields_and_nonfake_adapters(self):
        for change in ({"fixture": False}, {"account": "unapproved_account"}, {"environment": "LIVE"}, {"extra": "TEST_ONLY"}):
            with self.assertRaises(ContractError): self.box.plan(self.key, "CREATE_CHECKOUT", {**self.payload, **change})
        with self.assertRaises(ContractError): DurableOutbox(self.path, object(), lambda: self.now)
        with self.assertRaises(ContractError): DurableOutbox(self.endpoint.path, self.endpoint, lambda: self.now)
        with self.assertRaises(ValueError): FixtureBinding(account="ordinary_account")
        with self.assertRaises(ContractError): self.box.retire_confirmed_payloads(0)

    def test_no_network_and_private_database_modes(self):
        self.plan()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.box.run_one()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.endpoint.path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__": unittest.main()
