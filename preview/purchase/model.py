"""Transactional, local-only purchase model with a deliberately fake provider.

No network, email, production scheduler, Stripe credentials, or live checkout.
SQLite models durable intake, payable reservations, authoritative reconciliation,
and independent-role delivery gates. All capacity is fictional preview data.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
from zoneinfo import ZoneInfo

PRICE = {"currency": "USD", "subtotal_cents": 14900, "tax_cents": 0,
         "total_cents": 14900}
WORKFLOWS = {"QUOTE_REQUEST", "LEASING_INQUIRY", "ADMIN_INBOX", "OTHER"}
ACKS = ("admin_only", "one_workflow", "no_sensitive_data", "written_plan_only")
EFFORT = {"PRODUCTION": 120, "CORRECTION": 30, "CONTINGENCY": 30,
          "QA": 45, "REVISION": 45, "REVISION_QA": 20}
DENVER = ZoneInfo("America/Denver")
SENSITIVE_SCOPE = r"\b(password|credentials?|api.?key|ssn|social security|card number|patient|diagnos\w*|medical|legal advice|investment|money movement|emergen\w*|911)\b"
IMPLEMENTATION_SCOPE = r"\b(install\w*|implement\w*|monitor\w*|log.?in|account access|connect my)\b"
DECISION_SCOPE = r"\b(decid\w*|approv\w*|reject\w*|qualif\w*|screen\w*|underwrit\w*|loan\w*|mortgage\w*|credit\w*|eligib\w*|discriminat\w*|evict\w*|prescrib\w*|treatment|background check|rank applicants|transfer funds|send money)\b"


class PreviewError(Exception):
    def __init__(self, code, message, status=409, fields=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.fields = fields or {}


def stamp(value):
    return value.astimezone(timezone.utc).isoformat()


def parse(value):
    return datetime.fromisoformat(value)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def clean_text(value, minimum, maximum):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        return None
    value = value.strip()
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        return None
    return value


def validate_brief(payload):
    expected = {"workflow", "tools", "handoff", "submission_key", *ACKS}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PreviewError("INVALID_BRIEF", "Complete the short brief and confirmations.", 400)
    fields = {}
    if not isinstance(payload["workflow"], str) or payload["workflow"] not in WORKFLOWS:
        fields["workflow"] = "Choose one workflow."
    for key, minimum, maximum in (("tools", 2, 120), ("handoff", 20, 600)):
        if clean_text(payload[key], minimum, maximum) is None:
            fields[key] = f"Use {minimum}–{maximum} characters without control characters."
    if not isinstance(payload["submission_key"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", payload["submission_key"]):
        fields["submission_key"] = "Refresh the page and try again."
    for key in ACKS:
        if type(payload[key]) is not bool:
            fields[key] = "Choose the confirmation."
    if fields:
        raise PreviewError("INVALID_BRIEF", "Check the highlighted brief fields.", 400, fields)
    brief = {key: payload[key].strip() if isinstance(payload[key], str) else payload[key]
             for key in expected - {"submission_key"}}
    text = (brief["tools"] + " " + brief["handoff"]).lower()
    # This intentionally conservative rule set is a preview admission guard,
    # not a semantic classifier or proof that arbitrary free text is safe.
    if not brief["no_sensitive_data"] or re.search(SENSITIVE_SCOPE, text) or re.search(DECISION_SCOPE, text):
        scope, reasons = "UNSUPPORTED", ["SENSITIVE_OR_REGULATED_OR_EMERGENCY_SCOPE"]
    elif not brief["written_plan_only"] or re.search(IMPLEMENTATION_SCOPE, text):
        scope, reasons = "UNSUPPORTED", ["IMPLEMENTATION_OR_ACCESS_NOT_INCLUDED"]
    elif brief["workflow"] == "OTHER" or not brief["admin_only"] or not brief["one_workflow"]:
        scope, reasons = "NEEDS_REVIEW", ["SCOPE_NEEDS_REVIEW"]
    elif not re.search(r"\b(request\w*|inquir\w*|message\w*|email\w*|inbox|handoff|office|owner|detail\w*|status)\b", brief["handoff"].lower()) or not re.search(r"\b(assign\w*|captur\w*|collect\w*|rout\w*|organi[sz]\w*|keep|track\w*|categor\w*|acknowledg\w*|follow.?up|hand.?off)\b", brief["handoff"].lower()):
        scope, reasons = "NEEDS_REVIEW", ["ADMINISTRATIVE_HANDOFF_NOT_CLEAR"]
    else:
        scope, reasons = "ELIGIBLE", []
    return brief, payload["submission_key"], scope, reasons


class FakeProvider:
    """Durable deterministic state machine. It cannot contact a real provider."""
    mode = "LOCAL_FAKE_ONLY"

    def available(self, db):
        return json.loads(db.execute("SELECT value FROM settings WHERE key='provider'").fetchone()[0])["available"]

    def create(self, db, order, now):
        if not self.available(db):
            raise PreviewError("PAYMENT_UNAVAILABLE", "Payment verification is unavailable. No checkout is offered.", 503)
        # An immutable order key makes retried creation return the same session.
        session_id = "fake_cs_" + order["id"] + "_" + str(order["attempt"])
        snapshot = {"id": session_id, "mode": self.mode, "livemode": False,
                    "order_id": order["id"], "amount_total": 14900,
                    "currency": "usd", "quantity": 1, "product": "WORKFLOW_BLUEPRINT",
                    "tax_cents": 0, "status": "open", "payment_status": "unpaid",
                    "payment_id": None, "paid_at": None,
                    "expires_at": order["expires_at"]}
        db.execute("INSERT OR IGNORE INTO provider_sessions VALUES(?,?,?)",
                   (session_id, order["id"], json.dumps(snapshot)))
        return session_id

    def retrieve(self, db, session_id, now):
        if not self.available(db):
            raise PreviewError("PAYMENT_VERIFICATION_UNAVAILABLE", "Payment cannot be verified yet. Your existing reservation is retained.", 503)
        row = db.execute("SELECT snapshot FROM provider_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise PreviewError("PAYMENT_NOT_FOUND", "Payment evidence needs review.")
        result = json.loads(row[0])
        if result["status"] == "open" and parse(result["expires_at"]) <= now:
            result["status"] = "expired"
            self.save(db, result)
        return result

    def save(self, db, snapshot):
        db.execute("UPDATE provider_sessions SET snapshot=? WHERE id=?", (json.dumps(snapshot), snapshot["id"]))

    def simulate(self, db, session_id, outcome, now):
        result = self.retrieve(db, session_id, now)
        if result["payment_status"] == "paid":
            return result  # A stale failure event cannot undo a verified payment.
        if result["payment_status"] == "failed":
            raise PreviewError("CHECKOUT_CLOSED", "That fake payment attempt is closed. Request a fresh reservation.")
        if outcome == "abandon":
            return result  # Still payable; capacity stays reserved until expiry.
        if result["status"] == "expired":
            raise PreviewError("CHECKOUT_EXPIRED", "This checkout has expired. No payment was made.")
        if outcome not in {"paid", "failed", "processing"}:
            raise PreviewError("INVALID_OUTCOME", "Choose a fake payment outcome.", 400)
        result["status"] = "complete"
        result["payment_status"] = outcome
        if outcome == "paid":
            result["payment_id"] = "fake_pi_" + result["order_id"]
            result["paid_at"] = stamp(now)
        self.save(db, result)
        return result


class Store:
    def __init__(self, database, clock=None, provider=None):
        self.path = Path(database)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.provider = provider or FakeProvider()
        if type(self.provider) is not FakeProvider:
            raise ValueError("This preview accepts only its local fake provider")
        with self.tx() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,csrf TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS orders(
                id TEXT PRIMARY KEY,session_hash TEXT UNIQUE NOT NULL REFERENCES sessions(token_hash),
                submission_key TEXT UNIQUE NOT NULL,payload_hash TEXT NOT NULL,brief TEXT NOT NULL,
                scope TEXT NOT NULL,reasons TEXT NOT NULL,state TEXT NOT NULL,
                created_at TEXT NOT NULL,expires_at TEXT,delivery_date TEXT,
                reservation TEXT,payment_status TEXT NOT NULL DEFAULT 'unpaid',provider_id TEXT UNIQUE,
                attempt INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS allocations(
                order_id TEXT NOT NULL REFERENCES orders(id),day TEXT NOT NULL,
                kind TEXT NOT NULL,minutes INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS submissions(
                key TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES orders(id),payload_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS obligations(
                id TEXT PRIMARY KEY,kind TEXT NOT NULL,due_date TEXT NOT NULL,
                production_minutes INTEGER NOT NULL,qa_minutes INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS provider_sessions(
                id TEXT PRIMARY KEY,order_id TEXT NOT NULL,snapshot TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                id TEXT PRIMARY KEY,session_id TEXT NOT NULL,state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cases(
                id TEXT PRIMARY KEY,order_id TEXT UNIQUE NOT NULL REFERENCES orders(id),
                payment_id TEXT UNIQUE NOT NULL,state TEXT NOT NULL,qa_state TEXT NOT NULL,
                draft_author TEXT,qa_reviewer TEXT,report TEXT,published_report TEXT,delivered_at TEXT,
                revision_deadline TEXT,revision_request TEXT,revision_used INTEGER NOT NULL DEFAULT 0);
            """)
            if not db.execute("SELECT 1 FROM settings WHERE key='capacity'").fetchone():
                self.seed_demo(db)
        self.path.chmod(0o600)

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            if db.in_transaction:
                db.commit()
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def seed_demo(self, db):
        now = self.clock()
        today = now.astimezone(DENVER).date()
        calendar = {}
        for delta in range(1, 43):
            day = today + timedelta(days=delta)
            if day.weekday() < 5:
                calendar[day.isoformat()] = {"production": 480, "qa": 120}
        value = {"fictional": True, "valid_until": stamp(now + timedelta(hours=24)),
                 "inventory_complete": True, "qa_available": True,
                 "private_delivery_ready": True, "tax_and_terms_simulated": True,
                 "material_incident": False, "calendar": calendar}
        db.execute("INSERT INTO settings VALUES('capacity',?)", (json.dumps(value),))
        db.execute("INSERT INTO settings VALUES('provider',?)", (json.dumps({"available": True}),))

    def session(self, raw_token=None):
        with self.tx() as db:
            if raw_token and re.fullmatch(r"[A-Za-z0-9_-]{43}", raw_token):
                row = db.execute("SELECT csrf FROM sessions WHERE token_hash=?", (digest(raw_token),)).fetchone()
                if row:
                    return raw_token, row[0]
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            db.execute("INSERT INTO sessions VALUES(?,?)", (digest(token), csrf))
            return token, csrf

    def recover(self, token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise PreviewError("RECOVERY_NOT_FOUND", "That private recovery code was not found.", 404)
        with self.tx() as db:
            if not db.execute("SELECT 1 FROM orders WHERE session_hash=?", (digest(token),)).fetchone():
                raise PreviewError("RECOVERY_NOT_FOUND", "That private recovery code was not found.", 404)
        return self.session(token)

    def _remaining_capacity(self, db, now):
        cap = json.loads(db.execute("SELECT value FROM settings WHERE key='capacity'").fetchone()[0])
        required = ("fictional", "inventory_complete", "qa_available", "private_delivery_ready", "tax_and_terms_simulated")
        if not all(cap.get(key) is True for key in required) or cap.get("material_incident") is not False:
            return None
        try:
            if parse(cap["valid_until"]) <= now or not isinstance(cap["calendar"], dict):
                return None
            for day, slots in cap["calendar"].items():
                datetime.strptime(day, "%Y-%m-%d")
                if set(slots) != {"production", "qa"} or any(type(value) is not int or value < 0 for value in slots.values()):
                    return None
        except (KeyError, ValueError, TypeError):
            return None
        if db.execute("SELECT 1 FROM orders WHERE state='PAYMENT_REVIEW'").fetchone():
            return None  # An unallocated paid obligation cannot disappear.
        calendar = {day: dict(amounts) for day, amounts in cap["calendar"].items()}
        for row in db.execute("SELECT day,kind,SUM(minutes) AS total FROM allocations WHERE active=1 GROUP BY day,kind"):
            if row["day"] not in calendar:
                return None
            lane = "qa" if row["kind"] in {"QA", "REVISION_QA"} else "production"
            calendar[row["day"]][lane] -= row["total"]
        # Existing paid work AND open payable invitations/reserved promises are
        # imported as obligations. Missing/overdue/unknown inventory fails closed.
        today = now.astimezone(DENVER).date()
        for row in db.execute("SELECT * FROM obligations"):
            if row["kind"] not in {"PAID", "OPEN_INVITATION", "RESERVED_COMMITMENT"} or row["due_date"] not in calendar or row["due_date"] < today.isoformat() or any(type(row[key]) is not int or row[key] < 0 for key in ("production_minutes", "qa_minutes")):
                return None
            calendar[row["due_date"]]["production"] -= row["production_minutes"]
            calendar[row["due_date"]]["qa"] -= row["qa_minutes"]
        if any(value < 0 for slots in calendar.values() for value in slots.values()):
            return None
        return calendar

    def _commitment_ready(self, db, order, now):
        if self._remaining_capacity(db, now) is None or order["reservation"] != "HELD" or not order["delivery_date"]:
            return False
        today = now.astimezone(DENVER).date().isoformat()
        if order["delivery_date"] <= today:
            return False
        # Unperformed work cannot borrow a slot that elapsed while payment was
        # processing. This is an exception requiring a new date or refund review.
        return not db.execute("SELECT 1 FROM allocations WHERE order_id=? AND active=1 AND day<?", (order["id"], today)).fetchone()

    def _capacity_plan(self, db, now):
        calendar = self._remaining_capacity(db, now)
        if calendar is None:
            return None
        today = now.astimezone(DENVER).date()
        days = sorted(day for day in calendar if day > today.isoformat())
        # Default five business days is conditional; a later actual sample date
        # is offered when the full effort, revision and QA inventory needs it.
        business_day = today
        for _ in range(5):
            business_day += timedelta(days=1)
            while business_day.weekday() >= 5:
                business_day += timedelta(days=1)
        for due in (day for day in days if day >= business_day.isoformat()):
            remaining = {day: dict(slots) for day, slots in calendar.items()}
            plan = []
            production_days = [day for day in days if day < due]
            last_production = None
            for kind in ("PRODUCTION", "CORRECTION", "CONTINGENCY"):
                needed = EFFORT[kind]
                for day in production_days:
                    take = min(needed, max(0, remaining[day]["production"]))
                    if take:
                        plan.append((day, kind, take)); remaining[day]["production"] -= take
                        needed -= take; last_production = max(last_production or day, day)
                    if not needed:
                        break
                if needed:
                    break
            else:
                qa_day = next((day for day in production_days if day >= last_production and remaining[day]["qa"] >= EFFORT["QA"]), None)
                revision_end = (datetime.fromisoformat(due).date() + timedelta(days=7)).isoformat()
                revision_day = next((day for day in days if due < day <= revision_end and remaining[day]["production"] >= EFFORT["REVISION"] and remaining[day]["qa"] >= EFFORT["REVISION_QA"]), None)
                if qa_day and revision_day:
                    plan += [(qa_day, "QA", EFFORT["QA"]), (revision_day, "REVISION", EFFORT["REVISION"]), (revision_day, "REVISION_QA", EFFORT["REVISION_QA"])]
                    return due, plan
        return None

    def submit(self, token, payload):
        brief, key, scope, reasons = validate_brief(payload)
        payload_hash = digest(json.dumps(brief, sort_keys=True))
        now = self.clock()
        self.reconcile_all()
        with self.tx() as db:
            prior = db.execute("SELECT * FROM submissions WHERE key=?", (key,)).fetchone()
            if prior:
                order = self._order(db, prior["order_id"])
                if prior["payload_hash"] != payload_hash or order["session_hash"] != digest(token):
                    raise PreviewError("IDEMPOTENCY_CONFLICT", "This submission key already belongs to a different brief.")
                return self._public(db, order)
            current = db.execute("SELECT * FROM orders WHERE session_hash=?", (digest(token),)).fetchone()
            if current:
                if current["provider_id"] or current["payment_status"] == "paid" or current["state"] == "PAYMENT_REVIEW":
                    raise PreviewError("BRIEF_LOCKED", "This brief is attached to a checkout. Reconcile it before any scope change.")
                self._release(db, current["id"])
                db.execute("DELETE FROM allocations WHERE order_id=?", (current["id"],))
            order_id = current["id"] if current else "ord_" + secrets.token_hex(16)
            state = scope if scope != "ELIGIBLE" else "RESERVED"
            plan = self._capacity_plan(db, now) if scope == "ELIGIBLE" else None
            if scope == "ELIGIBLE" and not plan:
                state, reasons = "CAPACITY_UNAVAILABLE", ["COMPLETE_CAPACITY_OR_QA_OR_DELIVERY_UNAVAILABLE"]
            if scope == "ELIGIBLE" and not self.provider.available(db):
                state, reasons, plan = "PAYMENT_UNAVAILABLE", ["PAYMENT_VERIFICATION_UNAVAILABLE"], None
            due, allocations = plan if plan else (None, [])
            expires = stamp(now + timedelta(minutes=30)) if plan else None
            if current:
                db.execute("UPDATE orders SET submission_key=?,payload_hash=?,brief=?,scope=?,reasons=?,state=?,expires_at=?,delivery_date=?,reservation=? WHERE id=?",
                           (key, payload_hash, json.dumps(brief), scope, json.dumps(reasons), state, expires, due, "HELD" if plan else None, order_id))
            else:
                db.execute("INSERT INTO orders(id,session_hash,submission_key,payload_hash,brief,scope,reasons,state,created_at,expires_at,delivery_date,reservation) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                           (order_id, digest(token), key, payload_hash, json.dumps(brief), scope, json.dumps(reasons), state, stamp(now), expires, due, "HELD" if plan else None))
            db.execute("INSERT INTO submissions VALUES(?,?,?)", (key, order_id, payload_hash))
            db.executemany("INSERT INTO allocations(order_id,day,kind,minutes) VALUES(?,?,?,?)", [(order_id, *row) for row in allocations])
            return self._public(db, self._order(db, order_id))

    def _order(self, db, order_id):
        row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise PreviewError("ORDER_NOT_FOUND", "No preview order was found.", 404)
        return row

    def _owned(self, db, token):
        row = db.execute("SELECT * FROM orders WHERE session_hash=?", (digest(token),)).fetchone()
        if not row:
            raise PreviewError("ORDER_NOT_FOUND", "No preview order was found.", 404)
        return row

    def _public(self, db, order):
        case = db.execute("SELECT * FROM cases WHERE order_id=?", (order["id"],)).fetchone()
        return {"id": order["id"], "state": order["state"], "scope_status": order["scope"],
                "scope_reasons": json.loads(order["reasons"]), "brief": json.loads(order["brief"]),
                "price": dict(PRICE), "delivery_date": order["delivery_date"],
                "checkout_expires_at": order["expires_at"], "reservation_state": order["reservation"],
                "payment_status": order["payment_status"],
                "case": {"id": case["id"], "state": case["state"], "qa_state": case["qa_state"],
                         "revision_deadline": case["revision_deadline"],
                         "report_available": case["state"] in {"DELIVERED", "REVISION_REQUESTED", "REVISION_READY_FOR_QA", "REVISION_QA_PASS", "REVISION_DELIVERED"}} if case else None}

    def current(self, token):
        with self.tx() as db:
            row = db.execute("SELECT * FROM orders WHERE session_hash=?", (digest(token),)).fetchone()
            return self._public(db, row) if row else None

    def checkout(self, token, accepted):
        if accepted is not True:
            raise PreviewError("TERMS_REQUIRED", "Acknowledge the provisional preview terms.", 400)
        self.reconcile_all()
        with self.tx() as db:
            order = self._owned(db, token)
            if order["state"] not in {"RESERVED", "CHECKOUT_OPEN"} or order["reservation"] != "HELD":
                raise PreviewError("CHECKOUT_UNAVAILABLE", "This order is not eligible for checkout.")
            if parse(order["expires_at"]) <= self.clock():
                raise PreviewError("CHECKOUT_EXPIRED", "The sample reservation has expired.")
            if not self._commitment_ready(db, order, self.clock()):
                raise PreviewError("READINESS_UNAVAILABLE", "Current capacity, QA, delivery or payment readiness cannot support checkout.", 503)
            # No checkout remains payable beyond its capacity reservation.
            if not order["provider_id"]:
                # Real hosted Checkout requires at least 30 minutes at creation.
                # Keep the same reserved work; do not extend an existing session.
                db.execute("UPDATE orders SET expires_at=?,attempt=attempt+1 WHERE id=?",
                           (stamp(self.clock() + timedelta(minutes=30)), order["id"]))
                order = self._order(db, order["id"])
            session_id = self.provider.create(db, order, self.clock())
            db.execute("UPDATE orders SET provider_id=?,state='CHECKOUT_OPEN' WHERE id=?", (session_id, order["id"]))
            return self._public(db, self._order(db, order["id"]))

    def retry(self, token):
        self.reconcile_all()
        with self.tx() as db:
            order = self._owned(db, token)
            if order["state"] not in {"EXPIRED", "PAYMENT_FAILED", "CAPACITY_UNAVAILABLE", "PAYMENT_UNAVAILABLE"} or order["payment_status"] == "paid":
                raise PreviewError("RETRY_UNAVAILABLE", "Reconcile this existing order before another payment attempt.")
            if order["provider_id"]:
                snapshot = self.provider.retrieve(db, order["provider_id"], self.clock())
                if snapshot["payment_status"] == "processing" or snapshot["status"] == "open" or snapshot["payment_status"] == "paid":
                    raise PreviewError("PAYMENT_STILL_PAYABLE", "The previous checkout is not definitively closed.")
            plan = self._capacity_plan(db, self.clock())
            if not plan or not self.provider.available(db):
                raise PreviewError("READINESS_UNAVAILABLE", "Capacity, QA, delivery or payment verification is unavailable. No checkout is offered.", 503)
            due, allocations = plan
            db.execute("DELETE FROM allocations WHERE order_id=? AND active=0", (order["id"],))
            db.executemany("INSERT INTO allocations(order_id,day,kind,minutes) VALUES(?,?,?,?)", [(order["id"], *row) for row in allocations])
            db.execute("UPDATE orders SET state='RESERVED',reservation='HELD',expires_at=?,delivery_date=?,provider_id=NULL,payment_status='unpaid',reasons='[]' WHERE id=?",
                       (stamp(self.clock() + timedelta(minutes=30)), due, order["id"]))
            return self._public(db, self._order(db, order["id"]))

    def _release(self, db, order_id):
        db.execute("UPDATE allocations SET active=0 WHERE order_id=?", (order_id,))
        db.execute("UPDATE orders SET reservation='RELEASED' WHERE id=?", (order_id,))

    def _reconcile(self, db, order, source_session_id=None):
        now = self.clock()
        if order["state"] == "PAYMENT_REVIEW":
            return  # An explicit incident requires review, never silent clearing.
        if not order["provider_id"] and not source_session_id:
            if order["reservation"] == "HELD" and parse(order["expires_at"]) <= now:
                self._release(db, order["id"])
                db.execute("UPDATE orders SET state='EXPIRED' WHERE id=?", (order["id"],))
            return
        session_id = source_session_id or order["provider_id"]
        snapshot = self.provider.retrieve(db, session_id, now)
        if source_session_id and source_session_id != order["provider_id"]:
            if snapshot["payment_status"] == "paid":
                db.execute("UPDATE orders SET state='PAYMENT_REVIEW',reasons=? WHERE id=?", (json.dumps(["OLDER_ATTEMPT_PAYMENT_REQUIRES_RECONCILIATION"]), order["id"]))
            return  # Older failed/expired events cannot regress a new attempt.
        valid = (snapshot["mode"] == "LOCAL_FAKE_ONLY" and snapshot["livemode"] is False
                 and snapshot["id"] == order["provider_id"] and snapshot["order_id"] == order["id"]
                 and snapshot["amount_total"] == 14900 and snapshot["currency"] == "usd"
                 and snapshot["quantity"] == 1 and snapshot["tax_cents"] == 0
                 and snapshot["product"] == "WORKFLOW_BLUEPRINT")
        if not valid:
            db.execute("UPDATE orders SET state='PAYMENT_REVIEW',reasons=? WHERE id=?", (json.dumps(["AUTHORITATIVE_PAYMENT_MISMATCH"]), order["id"]))
            return  # Never release uncertain payable capacity or assert payment.
        status = snapshot["payment_status"]
        if status == "paid":
            if snapshot["status"] != "complete" or not snapshot["payment_id"] or not snapshot["paid_at"] or parse(snapshot["paid_at"]) > now:
                raise PreviewError("PAYMENT_EVIDENCE_INCOMPLETE", "Final payment evidence needs review.")
            existing = db.execute("SELECT * FROM cases WHERE order_id=? OR payment_id=?", (order["id"], snapshot["payment_id"])).fetchall()
            if any(row["order_id"] != order["id"] or row["payment_id"] != snapshot["payment_id"] for row in existing):
                db.execute("UPDATE orders SET state='PAYMENT_REVIEW',reasons=? WHERE id=?", (json.dumps(["IMMUTABLE_PAYMENT_ID_CONFLICT"]), order["id"]))
                return
            if existing and order["payment_status"] == "paid":
                return
            review = not self._commitment_ready(db, order, now)
            case_state = "PAYMENT_REVIEW" if review else "DRAFTING"
            db.execute("INSERT OR IGNORE INTO cases(id,order_id,payment_id,state,qa_state) VALUES(?,?,?,?,?)",
                       ("case_" + order["id"], order["id"], snapshot["payment_id"], case_state, "NOT_STARTED"))
            db.execute("UPDATE orders SET state=?,payment_status='paid' WHERE id=?", ("PAYMENT_REVIEW" if review else "PAID", order["id"]))
        elif order["payment_status"] == "paid":
            return  # Never regress a paid case on stale/failure information.
        elif status == "processing":
            db.execute("UPDATE orders SET state='PAYMENT_PENDING',payment_status='processing' WHERE id=?", (order["id"],))
        elif status == "failed":
            self._release(db, order["id"])
            db.execute("UPDATE orders SET state='PAYMENT_FAILED',payment_status='failed' WHERE id=?", (order["id"],))
        elif snapshot["status"] == "expired":
            self._release(db, order["id"])
            db.execute("UPDATE orders SET state='EXPIRED' WHERE id=?", (order["id"],))

    def event(self, event_id, session_id):
        """Events are wake-ups only. Authoritative provider state is re-read.

        A production adapter would verify webhook signatures before this call;
        this fake implementation is invoked locally, never from public events.
        """
        with self.tx() as db:
            previous = db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if previous and previous["session_id"] != session_id:
                raise PreviewError("EVENT_ID_CONFLICT", "Event association needs review.")
            source = db.execute("SELECT order_id FROM provider_sessions WHERE id=?", (session_id,)).fetchone()
            order = self._order(db, source[0]) if source else None
            if not order:
                raise PreviewError("EVENT_ORDER_UNKNOWN", "Event association needs review.")
            self._reconcile(db, order, session_id)
            db.execute("INSERT OR REPLACE INTO events VALUES(?,?,'RECONCILED')", (event_id, session_id))
            return self._public(db, self._order(db, order["id"]))

    def reconcile_all(self):
        # Explicit startup/event/admission/operator reconciliation; no new cron.
        with self.tx() as db:
            for order in db.execute("SELECT * FROM orders").fetchall():
                try:
                    self._reconcile(db, order)
                except PreviewError:
                    continue  # Preserve reservations when verification is down.

    def pay(self, token, outcome):
        with self.tx() as db:
            order = self._owned(db, token)
            if not order["provider_id"]:
                raise PreviewError("CHECKOUT_UNAVAILABLE", "Open the fake checkout first.")
            self.provider.simulate(db, order["provider_id"], outcome, self.clock())
            session_id = order["provider_id"]
        return self.event("fake_evt_" + secrets.token_hex(12), session_id)

    def all_orders(self):
        with self.tx() as db:
            return [self._public(db, row) for row in db.execute("SELECT * FROM orders ORDER BY created_at")]

    def operate(self, order_id, action, actor=None):
        if action == "reconcile":
            self.reconcile_all()
        elif action == "settle_payment":
            with self.tx() as db:
                order = self._order(db, order_id)
                if not order["provider_id"]:
                    raise PreviewError("CHECKOUT_UNAVAILABLE", "No pending checkout exists.")
                self.provider.simulate(db, order["provider_id"], "paid", self.clock())
            self.event("fake_settle_" + secrets.token_hex(12), order["provider_id"])
        else:
            with self.tx() as db:
                order = self._order(db, order_id)
                case = db.execute("SELECT * FROM cases WHERE order_id=?", (order_id,)).fetchone()
                if not case or order["state"] != "PAID" or order["payment_status"] != "paid" or case["state"] == "PAYMENT_REVIEW":
                    raise PreviewError("CASE_NOT_READY", "A verified, allocated payment is required.")
                reviewer = actor or "preview-independent-reviewer"
                drafter = actor or "preview-drafting-agent"
                if action in {"draft", "revision_draft"}:
                    allowed = {"DRAFTING", "QA_CHANGES"} if action == "draft" else {"REVISION_REQUESTED"}
                    if case["state"] not in allowed:
                        raise PreviewError("INVALID_CASE_TRANSITION", "This draft is not ready for that action.")
                    report = self._report(json.loads(order["brief"]), case["revision_request"])
                    state = "READY_FOR_QA" if action == "draft" else "REVISION_READY_FOR_QA"
                    db.execute("UPDATE cases SET state=?,qa_state='PENDING',draft_author=?,qa_reviewer=NULL,report=? WHERE id=?", (state, drafter, report, case["id"]))
                elif action in {"qa_pass", "qa_fail", "revision_qa_pass"}:
                    expected = {"REVISION_READY_FOR_QA"} if action == "revision_qa_pass" else {"READY_FOR_QA", "REVISION_READY_FOR_QA"} if action == "qa_fail" else {"READY_FOR_QA"}
                    if case["state"] not in expected or reviewer == case["draft_author"]:
                        raise PreviewError("INDEPENDENT_QA_REQUIRED", "A separate reviewer must check the current draft.")
                    state = ("REVISION_REQUESTED" if case["state"] == "REVISION_READY_FOR_QA" else "QA_CHANGES") if action == "qa_fail" else "REVISION_QA_PASS" if action == "revision_qa_pass" else "QA_PASS"
                    db.execute("UPDATE cases SET state=?,qa_state=?,qa_reviewer=? WHERE id=?", (state, "CHANGES_REQUIRED" if action == "qa_fail" else "PASS", reviewer, case["id"]))
                elif action in {"deliver", "revision_deliver"}:
                    expected = "QA_PASS" if action == "deliver" else "REVISION_QA_PASS"
                    cap = json.loads(db.execute("SELECT value FROM settings WHERE key='capacity'").fetchone()[0])
                    if case["state"] != expected or case["qa_state"] != "PASS" or not case["qa_reviewer"] or case["qa_reviewer"] == case["draft_author"] or not case["report"] or cap.get("private_delivery_ready") is not True:
                        raise PreviewError("DELIVERY_GATE_FAILED", "Payment, independent QA and private delivery must pass.")
                    # Local DB write/readback simulates private delivery; not email/Drive.
                    state = "DELIVERED" if action == "deliver" else "REVISION_DELIVERED"
                    delivered = stamp(self.clock()) if action == "deliver" else case["delivered_at"]
                    deadline = stamp(self.clock() + timedelta(days=7)) if action == "deliver" else case["revision_deadline"]
                    db.execute("UPDATE cases SET state=?,published_report=report,delivered_at=?,revision_deadline=? WHERE id=?", (state, delivered, deadline, case["id"]))
                    assert db.execute("SELECT report FROM cases WHERE id=?", (case["id"],)).fetchone()[0] == case["report"]
                else:
                    raise PreviewError("INVALID_ACTION", "Choose an available simulated operator action.", 400)
        with self.tx() as db:
            return self._public(db, self._order(db, order_id))

    @staticmethod
    def _report(brief, revision):
        return f"""TEST_ONLY — fictional Workflow Blueprint\nPrepared with simulated AI assistance and independent-role QA.\n\nOne workflow: {brief['workflow']}\nExisting tools (unverified): {brief['tools']}\nAgreed handoff: {brief['handoff']}\n\nWorkflow map\nRequest -> capture minimum fields -> office owner reviews -> next action -> complete.\n\nCapture fields and routing\nRequest ID, request type, missing information, office owner, next action, status.\nUnclear scope goes to a human. Urgent or sensitive requests stay outside this process.\nDuplicate IDs reuse the existing record. A failed tool leaves a visible pending record.\n\nThree editable templates\n1. Acknowledgement: We received [request]. [Office owner] will review the details.\n2. Missing detail: Please confirm [missing detail] so the office can choose a next step.\n3. Optional follow-up: Is [request] still needed? Stop on any reply or opt-out.\n\nSetup instructions\nCreate one private request register in existing tools. Assign an office owner.\nUse the rules manually before considering a separately scoped integration.\n\nAcceptance tests\nCheck complete, missing, duplicate, replied, opted-out, bounced, draft-present,\nunknown category and unavailable-tool requests. Nothing sends automatically.\n\nOne clarification revision may be requested within seven days of delivery.\nNo implementation, account access, monitoring, regulated decisions or emergency dispatch.\n{('Clarification request: ' + revision) if revision else ''}\n"""

    def report(self, token):
        with self.tx() as db:
            order = self._owned(db, token)
            case = db.execute("SELECT * FROM cases WHERE order_id=?", (order["id"],)).fetchone()
            if not case or case["state"] not in {"DELIVERED", "REVISION_REQUESTED", "REVISION_READY_FOR_QA", "REVISION_QA_PASS", "REVISION_DELIVERED"}:
                raise PreviewError("REPORT_NOT_DELIVERED", "Your private report is not available yet.", 404)
            return case["published_report"]

    def revision(self, token, request):
        request = clean_text(request, 20, 500)
        if request is None:
            raise PreviewError("INVALID_REVISION", "Describe one clarification in 20–500 characters.", 400)
        if any(re.search(pattern, request.lower()) for pattern in (SENSITIVE_SCOPE, IMPLEMENTATION_SCOPE, DECISION_SCOPE)):
            raise PreviewError("REVISION_SCOPE_REVIEW", "That request needs scope review. The included revision clarifies the written plan only.")
        with self.tx() as db:
            order = self._owned(db, token)
            case = db.execute("SELECT * FROM cases WHERE order_id=?", (order["id"],)).fetchone()
            if not case or case["state"] != "DELIVERED" or case["revision_used"] or self.clock() > parse(case["revision_deadline"]):
                raise PreviewError("REVISION_UNAVAILABLE", "The included clarification revision is unavailable or already requested.")
            db.execute("UPDATE cases SET state='REVISION_REQUESTED',revision_used=1,revision_request=? WHERE id=?", (request, case["id"]))
            return self._public(db, order)
