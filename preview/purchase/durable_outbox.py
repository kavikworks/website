"""Offline cross-database fault harness. No HTTP, Stripe SDK or worker job.

The fake endpoint commits separately from the outbox. Unknown outcomes retain
their operation key and payload hash; a retry reconciles before acting. This
demonstrates contracts, not real provider idempotency or distributed atomicity.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3

from .payment_contracts import DEFAULT_BINDING, FixtureBinding


class ContractError(ValueError):
    """Static code only, never payload/provider exception text."""


class OutcomeUnknown(Exception):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


def instant(now):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ContractError("EXPLICIT_AWARE_CLOCK_REQUIRED")
    return now.astimezone(timezone.utc).isoformat()


@contextmanager
def transaction(path):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def private_database(path):
    raw = Path(path).expanduser()
    resolved = raw.resolve()
    if raw.is_symlink() or any((p / ".git").exists() for p in (resolved.parent, *resolved.parents)):
        raise ContractError("PRIVATE_DATABASE_OUTSIDE_GIT_REQUIRED")
    # Parent directory is caller-owned; do not change its permissions or inspect
    # any other files. Only synthetic state belongs in these local databases.
    with resolved.open("a"):
        pass
    resolved.chmod(0o600)
    return resolved


def validate_request(operation_id, kind, payload, binding):
    if not isinstance(operation_id, str) or not re.fullmatch(r"TEST_ONLY_[A-Za-z0-9_-]{8,100}", operation_id):
        raise ContractError("SYNTHETIC_OPERATION_ID_REQUIRED")
    fields = {"CREATE_CHECKOUT": {"order_id"}, "EXPIRE_CHECKOUT": {"session_id"},
              "DELIVER_REPORT": {"case_id", "report"}}
    if (not isinstance(kind, str) or kind not in fields or not isinstance(payload, dict)
            or set(payload) != {"fixture", "account", "environment"} | fields[kind]
            or payload["fixture"] is not True or payload["account"] != binding.account
            or payload["environment"] != binding.environment):
        raise ContractError("SYNTHETIC_CONFIGURED_REQUEST_REQUIRED")
    key = "order_id" if kind == "CREATE_CHECKOUT" else "session_id" if kind == "EXPIRE_CHECKOUT" else "case_id"
    pattern = r"ord_[0-9a-f]{32}" if key == "order_id" else r"fake_cs_[0-9a-f]{24}" if key == "session_id" else r"TEST_ONLY_CASE_[A-Za-z0-9_]{1,80}"
    if not isinstance(payload[key], str) or not re.fullmatch(pattern, payload[key]):
        raise ContractError("SYNTHETIC_RESOURCE_ID_REQUIRED")
    if kind == "DELIVER_REPORT" and (not isinstance(payload["report"], str)
            or not payload["report"].startswith("TEST_ONLY") or not 9 <= len(payload["report"]) <= 16000):
        raise ContractError("SYNTHETIC_REPORT_REQUIRED")
    return hashed(encoded(payload))


class FakeEndpoint:
    """A second SQLite database, not a network/provider adapter.

    faults is test-only injection: lookup, execute_before, execute_after.
    The latter commits the effect then loses its response.
    """
    def __init__(self, path, binding=DEFAULT_BINDING):
        if type(binding) is not FixtureBinding:
            raise ContractError("SYNTHETIC_BINDING_REQUIRED")
        self.path, self.binding, self.faults = private_database(path), binding, []
        with transaction(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS effects(operation_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,receipt TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS resources(id TEXT PRIMARY KEY,state TEXT NOT NULL,content_hash TEXT)")

    def _fault(self, stage):
        if self.faults and self.faults[0] == stage:
            self.faults.pop(0)
            raise OutcomeUnknown()

    def lookup(self, operation_id, payload_hash):
        self._fault("lookup")
        with transaction(self.path) as db:
            row = db.execute("SELECT * FROM effects WHERE operation_id=?", (operation_id,)).fetchone()
            if not row:
                return None  # Authoritative absence in this fake endpoint only.
            if row["payload_hash"] != payload_hash:
                raise ContractError("ENDPOINT_IDEMPOTENCY_CONFLICT")
            receipt = json.loads(row["receipt"])
            if receipt["kind"] == "EXPIRE_CHECKOUT":
                session = db.execute("SELECT * FROM resources WHERE id=?", (receipt["resource_id"],)).fetchone()
                if not session or session["state"] not in {"expired", "open", "paid", "processing"}:
                    raise OutcomeUnknown()
                # A historical expiry receipt is not current nonpayable proof.
                receipt["status"] = "expired" if session["state"] == "expired" else "retained"
            if receipt["kind"] == "DELIVER_REPORT":
                artifact = db.execute("SELECT * FROM resources WHERE id=?", (receipt["resource_id"],)).fetchone()
                if not artifact or artifact["state"] != "delivered" or artifact["content_hash"] != receipt["content_hash"]:
                    raise OutcomeUnknown()  # No readback, no delivery assertion.
            return receipt

    def execute(self, operation_id, kind, payload):
        payload_hash = validate_request(operation_id, kind, payload, self.binding)
        self._fault("execute_before")
        with transaction(self.path) as db:
            prior = db.execute("SELECT * FROM effects WHERE operation_id=?", (operation_id,)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise ContractError("ENDPOINT_IDEMPOTENCY_CONFLICT")
                return  # Response is never used as fulfillment evidence.
            content_hash = None
            if kind == "CREATE_CHECKOUT":
                resource_id, state = "fake_cs_" + hashed(operation_id)[:24], "open"
                db.execute("INSERT INTO resources VALUES(?,?,NULL)", (resource_id, state))
            elif kind == "EXPIRE_CHECKOUT":
                resource_id = payload["session_id"]
                source = db.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
                if not source:
                    raise ContractError("UNKNOWN_FAKE_SESSION")
                state = "retained" if source["state"] in {"paid", "processing"} else "expired"
                if state == "expired":
                    db.execute("UPDATE resources SET state='expired' WHERE id=?", (resource_id,))
            else:
                resource_id, state = "fake_artifact_" + hashed(operation_id)[:24], "delivered"
                content_hash = hashed(payload["report"])
                db.execute("INSERT INTO resources VALUES(?,?,?)", (resource_id, state, content_hash))
            receipt = {"operation_id": operation_id, "kind": kind, "payload_hash": payload_hash,
                       "account": self.binding.account, "environment": self.binding.environment,
                       "resource_id": resource_id, "status": state, "content_hash": content_hash}
            db.execute("INSERT INTO effects VALUES(?,?,?)", (operation_id, payload_hash, encoded(receipt)))
        self._fault("execute_after")


class DurableOutbox:
    LEASE_SECONDS = 60
    MAX_ATTEMPTS = 5

    def __init__(self, path, endpoint, clock, binding=DEFAULT_BINDING):
        if type(endpoint) is not FakeEndpoint or type(binding) is not FixtureBinding:
            raise ContractError("LOCAL_FAKE_ENDPOINT_REQUIRED")
        instant(clock())
        self.path = private_database(path)
        if self.path == endpoint.path:
            raise ContractError("SEPARATE_TRANSACTION_BOUNDARIES_REQUIRED")
        self.endpoint, self.clock, self.binding = endpoint, clock, binding
        with transaction(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS outbox(
                operation_id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload_hash TEXT NOT NULL,
                payload TEXT,state TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
                not_before TEXT NOT NULL,lease_until TEXT,claim TEXT,last_error TEXT,
                result TEXT,confirmed_at TEXT)""")

    def plan(self, operation_id, kind, payload):
        payload_hash = validate_request(operation_id, kind, payload, self.binding)
        with transaction(self.path) as db:
            prior = db.execute("SELECT * FROM outbox WHERE operation_id=?", (operation_id,)).fetchone()
            if prior:
                if prior["kind"] != kind or prior["payload_hash"] != payload_hash:
                    raise ContractError("OUTBOX_IDEMPOTENCY_CONFLICT")
            else:
                db.execute("INSERT INTO outbox(operation_id,kind,payload_hash,payload,state,not_before) VALUES(?,?,?,?,'PENDING',?)",
                           (operation_id, kind, payload_hash, encoded(payload), instant(self.clock())))
        return self.status(operation_id)

    def status(self, operation_id):
        with transaction(self.path) as db:
            row = db.execute("SELECT * FROM outbox WHERE operation_id=?", (operation_id,)).fetchone()
            if not row:
                raise ContractError("OPERATION_NOT_FOUND")
            result = json.loads(row["result"]) if row["result"] else None
            confirmed = row["state"] == "CONFIRMED"
            current_readback = confirmed
            if confirmed and row["kind"] in {"EXPIRE_CHECKOUT", "DELIVER_REPORT"}:
                try:
                    current = self.endpoint.lookup(operation_id, row["payload_hash"])
                    keys = ("operation_id", "kind", "payload_hash", "account", "environment", "resource_id", "content_hash")
                    current_readback = isinstance(current, dict) and all(current.get(k) == result.get(k) for k in keys)
                    states = {"expired", "retained"} if row["kind"] == "EXPIRE_CHECKOUT" else {"delivered"}
                    current_readback = current_readback and isinstance(current.get("status"), str) and current["status"] in states
                    if current_readback:
                        result = current
                except (OutcomeUnknown, ContractError):
                    current_readback = False
            return {"operation_id": row["operation_id"], "state": row["state"],
                    "attempts": row["attempts"], "last_error": row["last_error"], "result": result,
                    "current_readback_verified": current_readback,
                    "capacity_may_release": confirmed and current_readback and row["kind"] == "EXPIRE_CHECKOUT" and result["status"] == "expired",
                    "delivery_confirmed": confirmed and current_readback and row["kind"] == "DELIVER_REPORT"}

    def _valid_receipt(self, row, receipt):
        if not isinstance(receipt, dict):
            return False
        if not isinstance(receipt.get("status"), str):
            return False
        expected = {"operation_id": row["operation_id"], "kind": row["kind"],
                    "payload_hash": row["payload_hash"], "account": self.binding.account,
                    "environment": self.binding.environment}
        if any(receipt.get(k) != v for k, v in expected.items()):
            return False
        payload = json.loads(row["payload"])
        if row["kind"] == "CREATE_CHECKOUT":
            return receipt.get("resource_id") == "fake_cs_" + hashed(row["operation_id"])[:24] and receipt.get("status") == "open"
        if row["kind"] == "EXPIRE_CHECKOUT":
            return receipt.get("resource_id") == payload["session_id"] and receipt.get("status") in {"expired", "retained"}
        return (receipt.get("resource_id") == "fake_artifact_" + hashed(row["operation_id"])[:24]
                and receipt.get("status") == "delivered" and receipt.get("content_hash") == hashed(payload["report"]))

    def run_one(self):
        now = self.clock()
        with transaction(self.path) as db:
            row = db.execute("""SELECT * FROM outbox WHERE
                (state IN ('PENDING','UNKNOWN') AND not_before<=?) OR
                (state='IN_FLIGHT' AND lease_until<=?) ORDER BY not_before,operation_id LIMIT 1""",
                (instant(now), instant(now))).fetchone()
            if not row:
                return None
            if row["attempts"] >= self.MAX_ATTEMPTS:
                db.execute("UPDATE outbox SET state='REVIEW_REQUIRED',claim=NULL,lease_until=NULL WHERE operation_id=?", (row["operation_id"],))
                return self._minimal(row, "REVIEW_REQUIRED")
            claim = secrets.token_hex(16)
            db.execute("UPDATE outbox SET state='IN_FLIGHT',attempts=attempts+1,claim=?,lease_until=? WHERE operation_id=?",
                       (claim, instant(now + timedelta(seconds=self.LEASE_SECONDS)), row["operation_id"]))
        # No application transaction spans the endpoint call. A process crash
        # here leaves a durable lease; its successor reconciles the same key.
        error, receipt = None, None
        try:
            receipt = self.endpoint.lookup(row["operation_id"], row["payload_hash"])
            if receipt is None:
                self.endpoint.execute(row["operation_id"], row["kind"], json.loads(row["payload"]))
                receipt = self.endpoint.lookup(row["operation_id"], row["payload_hash"])
            if not self._valid_receipt(row, receipt):
                error = "AUTHORITATIVE_RECEIPT_MISMATCH"
        except OutcomeUnknown:
            error = "OUTCOME_UNKNOWN"
        except ContractError:
            error = "CONTRACT_RECONCILIATION_REQUIRED"
        attempts = row["attempts"] + 1
        state = "CONFIRMED" if error is None else "UNKNOWN" if error == "OUTCOME_UNKNOWN" and attempts < self.MAX_ATTEMPTS else "REVIEW_REQUIRED"
        with transaction(self.path) as db:
            db.execute("""UPDATE outbox SET state=?,last_error=?,result=?,confirmed_at=?,
                not_before=?,claim=NULL,lease_until=NULL WHERE operation_id=? AND claim=? AND state='IN_FLIGHT'""",
                (state, error, encoded(receipt) if state == "CONFIRMED" else None,
                 instant(self.clock()) if state == "CONFIRMED" else None,
                 instant(self.clock() + timedelta(seconds=min(1800, 60 * 2 ** (attempts - 1)))),
                 row["operation_id"], claim))
        return self.status(row["operation_id"])

    @staticmethod
    def _minimal(row, state):
        return {"operation_id": row["operation_id"], "state": state}

    def reconcile_review(self, operation_id):
        """Readback only after bounded retries; never re-execute an exhausted job."""
        with transaction(self.path) as db:
            row = db.execute("SELECT * FROM outbox WHERE operation_id=? AND state='REVIEW_REQUIRED'", (operation_id,)).fetchone()
        if not row:
            raise ContractError("REVIEW_REQUIRED")
        receipt = self.endpoint.lookup(operation_id, row["payload_hash"])
        if receipt is not None and self._valid_receipt(row, receipt):
            with transaction(self.path) as db:
                db.execute("UPDATE outbox SET state='CONFIRMED',last_error=NULL,result=?,confirmed_at=? WHERE operation_id=? AND state='REVIEW_REQUIRED'",
                           (encoded(receipt), instant(self.clock()), operation_id))
        return self.status(operation_id)

    def retire_confirmed_payloads(self, days):
        if type(days) is not int or not 1 <= days <= 3650:
            raise ContractError("POSITIVE_EXPLICIT_RETENTION_WINDOW_REQUIRED")
        with transaction(self.path) as db:
            rows = db.execute("SELECT operation_id FROM outbox WHERE state='CONFIRMED' AND payload IS NOT NULL AND confirmed_at<=?",
                              (instant(self.clock() - timedelta(days=days)),)).fetchall()
        count = 0
        for row in rows:
            if not self.status(row["operation_id"])["current_readback_verified"]:
                continue  # A historical delivery/expiry must not hide lost readback.
            with transaction(self.path) as db:
                count += db.execute("UPDATE outbox SET payload=NULL WHERE operation_id=? AND state='CONFIRMED' AND payload IS NOT NULL",
                                    (row["operation_id"],)).rowcount
        return count
