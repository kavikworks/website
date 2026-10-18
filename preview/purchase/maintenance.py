"""Explicit local maintenance; no approved business policy or automatic job.

No deletion happens unless the caller supplies positive retention windows.
Unresolved obligations and holds take precedence. Hashed replay tombstones are
retained separately from deleted brief/report content.
"""
from dataclasses import dataclass
from datetime import timedelta
import re
import secrets

from .model import PreviewError, digest, parse, stamp
from .payment_contracts import snapshot_matches


@dataclass(frozen=True)
class RetentionPolicy:
    unpaid_days: int | None = None
    delivered_days: int | None = None
    empty_session_days: int | None = None

    def __post_init__(self):
        for value in (self.unpaid_days, self.delivered_days, self.empty_session_days):
            if value is not None and (type(value) is not int or not 1 <= value <= 3650):
                raise ValueError("POSITIVE_EXPLICIT_RETENTION_WINDOW_REQUIRED")


def initialize_maintenance(db, now):
    # Additive migration. Unknown historical activity starts a fresh clock, so
    # opening an older preview database cannot cause immediate content deletion.
    for table, column in (("sessions", "created_at"), ("orders", "touched_at"),
                          ("cases", "last_delivered_at")):
        if column not in {row[1] for row in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
    db.execute("UPDATE sessions SET created_at=? WHERE created_at IS NULL", (stamp(now),))
    db.execute("UPDATE orders SET touched_at=? WHERE touched_at IS NULL", (stamp(now),))
    db.execute("UPDATE cases SET last_delivered_at=? WHERE last_delivered_at IS NULL AND delivered_at IS NOT NULL", (stamp(now),))
    db.executescript("""
        CREATE TABLE IF NOT EXISTS recovery_rotations(
            old_hash TEXT PRIMARY KEY,new_hash TEXT NOT NULL,order_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS retention_holds(order_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS retired_keys(
            kind TEXT NOT NULL,key_hash TEXT NOT NULL,PRIMARY KEY(kind,key_hash));
    """)


def rotate_recovery(store, token, replacement):
    # The caller retains the proposed new token before requesting rotation.
    # Losing the response therefore does not lose access or require storing raw
    # bearer credentials. A retry proves possession of both exact token values.
    if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", v)
           for v in (token, replacement)) or token == replacement:
        raise PreviewError("INVALID_RECOVERY_ROTATION", "Use two distinct private local recovery codes.", 400)
    old_hash, new_hash = digest(token), digest(replacement)
    with store.tx() as db:
        prior = db.execute("SELECT * FROM recovery_rotations WHERE old_hash=?", (old_hash,)).fetchone()
        if prior:
            row = db.execute("SELECT * FROM orders WHERE id=? AND session_hash=?", (prior["order_id"], new_hash)).fetchone()
            if prior["new_hash"] != new_hash or not row:
                raise PreviewError("RECOVERY_NOT_FOUND", "That private recovery code was not found.", 404)
            csrf = db.execute("SELECT csrf FROM sessions WHERE token_hash=?", (new_hash,)).fetchone()[0]
            return replacement, csrf
        order = store._owned(db, token)
        if db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (new_hash,)).fetchone():
            raise PreviewError("RECOVERY_CONFLICT", "That replacement is already in use.")
        csrf = secrets.token_urlsafe(24)
        db.execute("INSERT INTO sessions(token_hash,csrf,created_at) VALUES(?,?,?)", (new_hash, csrf, stamp(store.clock())))
        db.execute("UPDATE orders SET session_hash=? WHERE id=?", (new_hash, order["id"]))
        db.execute("INSERT INTO recovery_rotations VALUES(?,?,?)", (old_hash, new_hash, order["id"]))
        db.execute("DELETE FROM sessions WHERE token_hash=?", (old_hash,))
        return replacement, csrf


def _closed_unpaid_evidence(store, db, order, now):
    for row in db.execute("SELECT id FROM provider_sessions WHERE order_id=?", (order["id"],)).fetchall():
        try:
            snapshot = store.provider.retrieve(db, row["id"], now)
        except PreviewError:
            return False
        if not snapshot_matches(snapshot, order["id"], row["id"]):
            return False
        if not ((snapshot.get("status"), snapshot.get("payment_status")) in
                {("expired", "unpaid"), ("complete", "failed")}):
            return False
    return True


def apply_retention(store, policy):
    if type(policy) is not RetentionPolicy:
        raise ValueError("EXPLICIT_RETENTION_POLICY_REQUIRED")
    now = store.clock()
    store.reconcile_all()
    counts = {"orders_deleted": 0, "sessions_deleted": 0, "held_orders": 0}
    with store.tx() as db:
        for order in db.execute("SELECT * FROM orders").fetchall():
            case = db.execute("SELECT * FROM cases WHERE order_id=?", (order["id"],)).fetchone()
            if db.execute("SELECT 1 FROM retention_holds WHERE order_id=?", (order["id"],)).fetchone():
                counts["held_orders"] += 1
                continue
            eligible = False
            if case:
                if (policy.delivered_days is not None and order["state"] == "PAID"
                        and order["payment_status"] == "paid"
                        and case["state"] in {"DELIVERED", "REVISION_DELIVERED"}
                        and case["qa_state"] == "PASS" and case["last_delivered_at"]
                        and case["revision_deadline"]):
                    anchor = max(parse(case["last_delivered_at"]), parse(case["revision_deadline"]))
                    eligible = now >= anchor + timedelta(days=policy.delivered_days)
            elif (policy.unpaid_days is not None
                  and order["state"] in {"UNSUPPORTED", "NEEDS_REVIEW", "CAPACITY_UNAVAILABLE",
                                         "PAYMENT_UNAVAILABLE", "EXPIRED", "PAYMENT_FAILED"}
                  and order["payment_status"] in {"unpaid", "failed"}
                  and order["reservation"] != "HELD"
                  and now >= parse(order["touched_at"]) + timedelta(days=policy.unpaid_days)):
                eligible = _closed_unpaid_evidence(store, db, order, now)
            if not eligible:
                continue
            # Minimal irreversible dedupe tombstones, no brief/report, raw
            # submission keys, customer/session tokens or event content.
            for row in db.execute("SELECT key FROM submissions WHERE order_id=?", (order["id"],)):
                db.execute("INSERT OR IGNORE INTO retired_keys VALUES('submission',?)", (digest(row["key"]),))
            for row in db.execute("SELECT id FROM provider_sessions WHERE order_id=?", (order["id"],)).fetchall():
                db.execute("INSERT OR IGNORE INTO retired_keys VALUES('provider_session',?)", (digest(row["id"]),))
                for event in db.execute("SELECT id FROM events WHERE session_id=?", (row["id"],)).fetchall():
                    db.execute("INSERT OR IGNORE INTO retired_keys VALUES('event',?)", (digest(event["id"]),))
                db.execute("DELETE FROM events WHERE session_id=?", (row["id"],))
            if case:
                db.execute("INSERT OR IGNORE INTO retired_keys VALUES('payment',?)", (digest(case["payment_id"]),))
            db.execute("DELETE FROM cases WHERE order_id=?", (order["id"],))
            db.execute("DELETE FROM provider_sessions WHERE order_id=?", (order["id"],))
            db.execute("DELETE FROM allocations WHERE order_id=?", (order["id"],))
            db.execute("DELETE FROM submissions WHERE order_id=?", (order["id"],))
            db.execute("DELETE FROM recovery_rotations WHERE order_id=?", (order["id"],))
            db.execute("DELETE FROM orders WHERE id=?", (order["id"],))
            db.execute("DELETE FROM sessions WHERE token_hash=?", (order["session_hash"],))
            counts["orders_deleted"] += 1
            counts["sessions_deleted"] += 1
        if policy.empty_session_days is not None:
            cutoff = stamp(now - timedelta(days=policy.empty_session_days))
            cursor = db.execute("DELETE FROM sessions WHERE created_at<=? AND NOT EXISTS(SELECT 1 FROM orders WHERE session_hash=sessions.token_hash)", (cutoff,))
            counts["sessions_deleted"] += cursor.rowcount
    # SQLite deletion is logical content removal, not secure physical erasure.
    # Backups, filesystem remnants and legal retention require production design.
    return counts
