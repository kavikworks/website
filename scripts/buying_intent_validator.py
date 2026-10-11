"""Offline, deterministic buying-intent research evaluation; no external actions.

Input annotations are reviewer assertions, not independently verified by this
program. This module deliberately has no collector, sender, or classifier API.
"""

import argparse
import copy
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SCHEMA_VERSION = "1.0"
RUBRIC_VERSION = "offline-1.0"
SECTORS = ("HVAC", "PLUMBING", "ELECTRICAL", "ROOFING", "RESTORATION",
           "LANDSCAPING_EXTERIOR")
WORKFLOWS = ("ESTIMATE_FOLLOW_UP", "SCHEDULING", "DISPATCH", "LEAD_RESPONSE",
             "INBOX_HANDLING", "CALLBACK")
VERIFICATION = ("VERIFIED", "UNVERIFIED", "UNKNOWN")
ACCESS = ("ALLOWED", "DENIED", "UNVERIFIED", "NOT_ATTEMPTED", "UNKNOWN")
CLASSES = {"EXPLICIT_BUYER_REQUEST": 3, "DEMONSTRATED_OPERATIONAL_PAIN": 2,
           "INDIRECT_EVIDENCE": 1, "INSUFFICIENT_SIGNAL": 0}


def field(kind, default=None, choices=None):
    return (kind, default, choices)


# Closed schema: absent fields become explicit null/UNKNOWN, never passing gates.
RECORD_SCHEMA = {
    "synthetic_fixture": field("bool", False),
    "source": {
        "url": field("url"), "record_id": field("text"),
        "type": field("enum", "UNKNOWN", ("COMPANY_STATEMENT", "JOB_LISTING",
            "REVIEW", "FORUM", "AGGREGATOR", "INTAKE_FEATURE", "VENDOR", "UNKNOWN")),
        "permission": {
            "state": field("enum", "UNKNOWN", ("ALLOWED", "DENIED", "UNKNOWN")),
            "purpose": field("enum", "UNKNOWN", ("BUYING_INTENT_RESEARCH", "OTHER", "UNKNOWN")),
            "basis_url": field("url"), "checked_at": field("date"),
            "reviewer": field("text"), "restrictions": field("list", []),
        },
        "manual_access_state": field("enum", "UNKNOWN", ACCESS),
        "automated_access_state": field("enum", "UNKNOWN", ACCESS),
        "access_method": field("enum", "UNKNOWN", ("MANUAL_READER", "MANUAL_DIRECT",
            "APPROVED_API", "SYNTHETIC", "UNKNOWN")),
        "license_reference": field("text"), "access_constraints": field("list", []),
        "constraints_state": field("enum", "UNKNOWN", VERIFICATION),
    },
    "dates": {key: field("date") for key in ("observed_at", "retrieved_at",
        "source_updated_at", "snapshot_at", "direct_verified_at", "expires_at")},
    "identity": {
        "business_name": field("text"), "domain": field("domain"),
        "state": field("enum", "UNKNOWN", VERIFICATION),
        "confidence": field("enum", "UNKNOWN", ("HIGH", "MEDIUM", "LOW", "UNKNOWN")),
        "evidence_url": field("url"),
        "author_role": field("enum", "UNKNOWN", ("OWNER", "MANAGER",
            "BUSINESS_REPRESENTATIVE", "CUSTOMER", "THIRD_PARTY", "ANONYMOUS", "UNKNOWN")),
        "author_state": field("enum", "UNKNOWN", VERIFICATION),
        "author_evidence_url": field("url"),
    },
    "fit": {
        "sector": field("enum", "UNKNOWN", SECTORS + ("OTHER", "UNKNOWN")),
        "sector_evidence_url": field("url"), "sector_exclusion_reason": field("text"),
        "location_claim": field("text"),
        "geography": field("enum", "UNKNOWN", ("ELIGIBLE", "OUTSIDE", "UNKNOWN")),
        "geographic_basis_url": field("url"),
        "scope": field("enum", "UNKNOWN", ("IN_SCOPE", "REGULATED", "EMERGENCY", "OUTSIDE", "UNKNOWN")),
    },
    "evidence": {
        "text": field("text"), "kind": field("enum", "UNKNOWN", ("OBSERVED", "INFERRED", "UNKNOWN")),
        "category": field("enum", "UNKNOWN", ("BUYER_REQUEST", "OPERATIONAL_PAIN",
            "THIRD_PARTY_COMPLAINT", "STAFFING", "INTAKE_FEATURE", "VENDOR_PROMOTION", "OTHER", "UNKNOWN")),
        "workflow": field("enum", "UNKNOWN", WORKFLOWS + ("OTHER", "UNKNOWN")),
        "explicit_help_request": field("bool"), "concrete_problem": field("bool"),
        "attribution_state": field("enum", "UNKNOWN", VERIFICATION),
        "original_state": field("enum", "UNKNOWN", VERIFICATION),
        "verification_state": field("enum", "UNKNOWN", VERIFICATION + ("CONFLICT",)),
        "verification_url": field("url"), "uncertainty_reasons": field("list", []),
    },
    "service_hypothesis": field("text"),
    "suppression": {
        "state": field("enum", "NOT_CHECKED", ("CLEAR", "SUPPRESSED", "UNKNOWN", "NOT_CHECKED")),
        "checked_at": field("date"), "evidence_reference": field("text"),
    },
    "lineage": {
        "original_source_url": field("url"), "original_source_record_id": field("text"),
        "is_repost": field("bool", False),
    },
    "access_error": {
        "code": field("enum", "NONE", ("NONE", "429", "TIMEOUT", "ROBOTS_REJECTED")),
        "attempts": field("integer", 0),
        "retry_state": field("enum", "NOT_ATTEMPTED", ("NOT_ATTEMPTED", "DEFERRED", "EXHAUSTED", "DO_NOT_RETRY")),
        "retry_after_seconds": field("number"),
    },
    "measurement": {
        "query_id": field("text"), "source_hit_count": field("integer"),
        "source_hit_coverage": field("enum", "UNKNOWN", ("COMPLETE", "PARTIAL", "UNKNOWN")),
        "review_minutes_actual": field("number"),
        "review_time_coverage": field("enum", "UNKNOWN", ("COMPLETE", "PARTIAL", "UNKNOWN")),
        "cost_observed": field("number"),
        "cost_coverage": field("enum", "UNKNOWN", ("COMPLETE", "PARTIAL", "UNKNOWN")),
        "currency": field("text"),
    },
}


class ValidationError(ValueError):
    """Contains only schema paths/reasons; never echoes untrusted input values."""


def parse_date(value):
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.combine(datetime.strptime(value, "%Y-%m-%d").date(),
                                time.max, timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def predates(value, reference):
    """Use exact instants only when both assertions include timestamp precision."""
    left, right = parse_date(value), parse_date(reference)
    if any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", item) for item in (value, reference)):
        return left.date() < right.date()
    return left < right


def canonical_domain(value):
    host = value.strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or "." not in host:
        raise ValueError("invalid hostname")
    if any(not part or part.startswith("-") or part.endswith("-") for part in host.split(".")):
        raise ValueError("invalid hostname")
    return host


def canonical_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("public HTTP(S) URL required")
    host = canonical_domain(parts.hostname)
    port = parts.port
    netloc = host if port in (None, 80 if parts.scheme.lower() == "http" else 443) else f"{host}:{port}"
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if not k.lower().startswith("utm_") and k.lower() not in ("gclid", "fbclid", "msclkid"))
    # Preserve scheme, path case, meaningful query parameters and trailing slash.
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", urlencode(query), ""))


def normalize_fields(data, schema, path="record"):
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: expected object")
    unknown = set(data) - set(schema)
    if unknown:
        raise ValidationError(f"{path}: unrecognized fields")
    result = {}
    for key, spec in schema.items():
        at = f"{path}.{key}"
        if isinstance(spec, dict):
            result[key] = normalize_fields(data.get(key, {}), spec, at)
            continue
        kind, default, choices = spec
        value = copy.deepcopy(data.get(key, default))
        # Null enums become UNKNOWN (or NOT_CHECKED); null is never ALLOWED/CLEAR.
        if value is None:
            if kind == "enum":
                value = default
            elif default is not None:
                raise ValidationError(f"{at}: null is not allowed")
            else:
                result[key] = None
                continue
        try:
            if kind in ("text", "date", "url", "domain", "enum"):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError()
                value = value.strip()
                if kind == "enum":
                    value = value.upper()
                    if value not in choices:
                        raise ValueError()
                elif kind == "date":
                    parse_date(value)
                elif kind == "url":
                    canonical_url(value)
                elif kind == "domain":
                    value = canonical_domain(value)
            elif kind == "bool" and type(value) is not bool:
                raise ValueError()
            elif kind in ("number", "integer"):
                if type(value) not in (int, float) or value < 0:
                    raise ValueError()
                if type(value) is int and value > 2**53 - 1:
                    raise ValueError()
                if type(value) is float and not math.isfinite(value):
                    raise ValueError()
                if kind == "integer" and type(value) is not int:
                    raise ValueError()
            elif kind == "list":
                if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                    raise ValueError()
                value = sorted(set(x.strip() for x in value))
        except (ValueError, TypeError):
            raise ValidationError(f"{at}: invalid {kind}") from None
        result[key] = value
    if re.fullmatch(r"records\[\d+\]", path):
        source = result["source"]
        source["canonical_url"] = canonical_url(source["url"]) if source["url"] else None
        error = result["access_error"]
        if error["attempts"] > 2:
            raise ValidationError(f"{path}.access_error.attempts: at most two simulated attempts")
        if error["code"] == "ROBOTS_REJECTED" and error["retry_state"] != "DO_NOT_RETRY":
            raise ValidationError(f"{path}.access_error.retry_state: robots rejection forbids retry")
    return result


def freshness(record, as_of):
    dates = record["dates"]
    if record["evidence"]["verification_state"] == "CONFLICT":
        return "CONFLICT"
    if dates["expires_at"] and parse_date(dates["expires_at"]) <= as_of:
        return "EXPIRED"
    if not dates["observed_at"]:
        return "UNKNOWN"
    age = (as_of.date() - parse_date(dates["observed_at"]).date()).days
    if age < 0:
        return "UNKNOWN"
    return "CURRENT" if age <= 30 else "RECHECK_REQUIRED" if age <= 90 else "STALE"


def stable_id(record, audit=False):
    source, lineage = record["source"], record["lineage"]
    origin = lineage["original_source_url"] or source["url"]
    origin = canonical_url(origin) if origin else None
    source_id = lineage["original_source_record_id"] or source["record_id"]
    if audit:
        key = [source["canonical_url"], source["permission"], record["access_error"]]
    else:
        text = " ".join((record["evidence"]["text"] or "").split())
        date = record["dates"]["observed_at"]
        key = [record["identity"]["domain"], origin, source_id,
               parse_date(date).isoformat() if date else None, text]
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24]
    return ("audit-" if audit else "signal-") + digest


def classify(record, state):
    e, identity = record["evidence"], record["identity"]
    reasons = []
    if state in ("CONFLICT", "EXPIRED", "STALE"):
        reasons.append("SOURCE_CONFLICT" if state == "CONFLICT" else "SOURCE_" + state)
    if e["kind"] != "OBSERVED":
        reasons.append("OBSERVED_EVIDENCE_REQUIRED")
    if not e["text"]:
        reasons.append("CLAIM_MISSING")
    if identity["state"] != "VERIFIED" or not identity["domain"] or not identity["business_name"]:
        reasons.append("BUSINESS_IDENTITY_UNRESOLVED")
    if identity["confidence"] != "HIGH" or not identity["evidence_url"]:
        reasons.append("BUSINESS_IDENTITY_UNVERIFIED")
    if e["attribution_state"] != "VERIFIED" or identity["author_state"] != "VERIFIED" or not identity["author_evidence_url"]:
        reasons.append("AUTHOR_UNVERIFIED")
    if e["verification_state"] != "VERIFIED" or not e["verification_url"]:
        reasons.append("EVIDENCE_UNVERIFIED")
    if e["workflow"] not in WORKFLOWS:
        reasons.append("WORKFLOW_UNRESOLVED")
    category = e["category"]
    if category == "VENDOR_PROMOTION" or record["source"]["type"] == "VENDOR":
        reasons.append("VENDOR_PROMOTION")
    if category in ("STAFFING", "INTAKE_FEATURE", "OTHER", "UNKNOWN"):
        reasons.append("NO_OPERATIONAL_SIGNAL")
    if reasons:
        return "INSUFFICIENT_SIGNAL", reasons
    if category == "BUYER_REQUEST":
        if identity["author_role"] not in ("OWNER", "MANAGER") or e["explicit_help_request"] is not True:
            return "INSUFFICIENT_SIGNAL", ["VERIFIED_OWNER_MANAGER_REQUEST_REQUIRED"]
        if e["original_state"] != "VERIFIED":
            return "INSUFFICIENT_SIGNAL", ["ORIGINAL_EVIDENCE_UNVERIFIED"]
        return "EXPLICIT_BUYER_REQUEST", ["VERIFIED_OWNER_MANAGER_REQUEST"]
    if category == "OPERATIONAL_PAIN":
        if identity["author_role"] not in ("OWNER", "MANAGER", "BUSINESS_REPRESENTATIVE") or e["concrete_problem"] is not True:
            return "INSUFFICIENT_SIGNAL", ["ATTRIBUTABLE_CONCRETE_PAIN_REQUIRED"]
        if e["original_state"] != "VERIFIED":
            return "INSUFFICIENT_SIGNAL", ["ORIGINAL_EVIDENCE_UNVERIFIED"]
        return "DEMONSTRATED_OPERATIONAL_PAIN", ["ATTRIBUTABLE_OPERATIONAL_PAIN_NO_PURCHASE_INFERRED"]
    if category == "THIRD_PARTY_COMPLAINT" and identity["author_role"] in ("CUSTOMER", "THIRD_PARTY") and e["concrete_problem"] is True:
        return "INDIRECT_EVIDENCE", ["THIRD_PARTY_HYPOTHESIS_ONLY"]
    return "INSUFFICIENT_SIGNAL", ["NO_OPERATIONAL_SIGNAL"]


def evaluate_record(record, as_of, mode, index, source_override=None):
    source, permission = record["source"], record["source"]["permission"]
    access_key = "manual_access_state" if mode == "MANUAL" else "automated_access_state"
    denied = permission["state"] == "DENIED" or source[access_key] == "DENIED" or permission["purpose"] == "OTHER"
    error = record["access_error"]["code"] != "NONE"
    unknown_permission = permission["state"] != "ALLOWED"
    # Denied/unknown use and access errors yield no business, claim, or inference.
    if denied or error or unknown_permission or source_override:
        reasons = []
        if permission["state"] == "DENIED": reasons.append("SOURCE_PERMISSION_DENIED")
        elif unknown_permission: reasons.append("SOURCE_PERMISSION_UNKNOWN")
        if permission["purpose"] == "OTHER": reasons.append("SOURCE_PURPOSE_DENIED")
        if source[access_key] == "DENIED": reasons.append("ACCESS_DENIED")
        if error: reasons.append("ACCESS_ERROR_" + record["access_error"]["code"])
        if source_override: reasons.append(source_override["reason"])
        return {
            "input_index": index, "signal_id": stable_id(record, audit=True),
            "synthetic_fixture": record["synthetic_fixture"], "audit_only": True,
            "audit": {"source_url": source["canonical_url"], "permission": permission,
                "manual_access_state": source["manual_access_state"],
                "automated_access_state": source["automated_access_state"],
                "access_method": source["access_method"], "access_error": record["access_error"]},
            "signal_class": "INSUFFICIENT_SIGNAL", "evidence_strength_0_to_3": 0,
            "freshness_state": "UNKNOWN", "gate": "BLOCK" if denied or error or source_override and source_override["gate"] == "BLOCK" else "HOLD",
            "reviewer_disposition": "ACCESS_ERROR" if error else "AUDIT_ONLY",
            "reasons": sorted(set(reasons)), "qualified_research": False, "send_ready": False,
            "duplicate_of": None, "supersedes": [],
        }
    state = freshness(record, as_of)
    signal_class, reasons = classify(record, state)
    blockers, holds = [], []
    fit, e, dates, suppression = record["fit"], record["evidence"], record["dates"], record["suppression"]
    if fit["geography"] == "OUTSIDE": blockers.append("GEOGRAPHY_OUTSIDE")
    elif fit["geography"] == "UNKNOWN": holds.append("GEOGRAPHY_UNKNOWN")
    if fit["sector"] == "OTHER": blockers.append("SECTOR_EXCLUDED")
    elif fit["sector"] == "UNKNOWN": holds.append("SECTOR_UNKNOWN")
    if fit["scope"] in ("REGULATED", "EMERGENCY", "OUTSIDE"): blockers.append("SERVICE_SCOPE_EXCLUDED")
    elif fit["scope"] == "UNKNOWN": holds.append("SERVICE_SCOPE_UNKNOWN")
    if "VENDOR_PROMOTION" in reasons: blockers.append("VENDOR_PROMOTION")
    if state in ("EXPIRED", "STALE"): blockers.append("SOURCE_" + state)
    elif state != "CURRENT": holds.append("FRESHNESS_" + state)
    if suppression["state"] == "SUPPRESSED": blockers.append("SUPPRESSED")
    elif suppression["state"] != "CLEAR": holds.append("SUPPRESSION_" + suppression["state"])
    elif not suppression["checked_at"] or not suppression["evidence_reference"]:
        holds.append("SUPPRESSION_PROVENANCE_MISSING")
    elif parse_date(suppression["checked_at"]).date() != as_of.date():
        holds.append("SUPPRESSION_RECHECK_REQUIRED")
    if source[access_key] != "ALLOWED": holds.append("ACCESS_" + source[access_key])
    if mode == "AUTOMATED" and not source["license_reference"]: holds.append("AUTOMATED_LICENSE_UNVERIFIED")
    if source["access_method"] == "SYNTHETIC" and not record["synthetic_fixture"]:
        holds.append("SYNTHETIC_METHOD_REQUIRES_FIXTURE")
    elif source["access_method"] != "UNKNOWN" and source["access_method"] != "SYNTHETIC":
        methods = ("MANUAL_READER", "MANUAL_DIRECT") if mode == "MANUAL" else ("APPROVED_API",)
        if source["access_method"] not in methods: holds.append("ACCESS_METHOD_MODE_MISMATCH")
    if not all((source["url"], permission["basis_url"], permission["checked_at"],
                permission["reviewer"], dates["retrieved_at"], dates["direct_verified_at"],
                fit["geographic_basis_url"], fit["sector_evidence_url"], fit["location_claim"])):
        holds.append("PROVENANCE_INCOMPLETE")
    if source["access_method"] == "UNKNOWN": holds.append("ACCESS_METHOD_UNKNOWN")
    if source["type"] == "UNKNOWN": holds.append("SOURCE_TYPE_UNKNOWN")
    if (permission["restrictions"] or source["access_constraints"]) and source["constraints_state"] != "VERIFIED":
        holds.append("SOURCE_CONSTRAINTS_UNRESOLVED")
    if permission["purpose"] != "BUYING_INTENT_RESEARCH": holds.append("PERMISSION_PURPOSE_UNRESOLVED")
    if e["original_state"] != "VERIFIED": holds.append("ORIGINAL_EVIDENCE_UNVERIFIED")
    if e["uncertainty_reasons"]: holds.append("UNRESOLVED_UNCERTAINTY")
    if record["lineage"]["is_repost"]:
        holds.append("REPOST_REQUIRES_ORIGINAL")
    if record["lineage"]["original_source_url"] and canonical_url(record["lineage"]["original_source_url"]) != source["canonical_url"] and not record["lineage"]["is_repost"]:
        holds.append("LINEAGE_UNRESOLVED")
    for name, value in dates.items():
        if name != "expires_at" and value and parse_date(value) > as_of:
            holds.append("FUTURE_PROVENANCE_DATE")
    if dates["observed_at"] and any(dates[name] and predates(dates[name], dates["observed_at"])
            for name in ("retrieved_at", "direct_verified_at")):
        holds.append("PROVENANCE_CHRONOLOGY_INCONSISTENT")
    if permission["checked_at"] and parse_date(permission["checked_at"]) > as_of:
        holds.append("FUTURE_PERMISSION_CHECK")
    if suppression["checked_at"] and parse_date(suppression["checked_at"]) > as_of:
        holds.append("FUTURE_SUPPRESSION_CHECK")
    if signal_class not in ("EXPLICIT_BUYER_REQUEST", "DEMONSTRATED_OPERATIONAL_PAIN"):
        holds.append("INDEPENDENT_RESEARCH_REQUIRED")
    disposition = "EXCLUDED" if blockers else "RESEARCH_NEEDED" if holds else "RESEARCH_QUALIFIED"
    if not blockers and mode == "AUTOMATED" and source["automated_access_state"] != "ALLOWED" and source["manual_access_state"] == "ALLOWED":
        disposition = "MANUAL_REVIEW_ONLY"
    return {"input_index": index, "signal_id": stable_id(record),
        "synthetic_fixture": record["synthetic_fixture"], "audit_only": False,
        "normalized": record, "signal_class": signal_class,
        "evidence_strength_0_to_3": CLASSES[signal_class], "freshness_state": state,
        "gate": "BLOCK" if blockers else "HOLD" if holds else "PASS",
        "reviewer_disposition": disposition, "reasons": sorted(set(reasons + blockers + holds)),
        "qualified_research": not blockers and not holds, "send_ready": False,
        "duplicate_of": None, "supersedes": []}


def evaluate_document(document):
    """Evaluate a frozen offline document. Input order and reruns are repeatable."""
    if not isinstance(document, dict) or set(document) != {"schema_version", "as_of", "run_id", "access_mode", "records"}:
        raise ValidationError("document: expected schema_version, as_of, run_id, access_mode, records only")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("schema_version: unsupported version")
    if document["access_mode"] not in ("MANUAL", "AUTOMATED"):
        raise ValidationError("access_mode: expected MANUAL or AUTOMATED")
    if not isinstance(document["run_id"], str) or not document["run_id"].strip():
        raise ValidationError("run_id: nonempty text required")
    try:
        as_of = parse_date(document["as_of"])
    except (TypeError, ValueError):
        raise ValidationError("as_of: ISO date or timezone-aware datetime required") from None
    if not isinstance(document["records"], list):
        raise ValidationError("records: expected array")
    normalized = [normalize_fields(raw, RECORD_SCHEMA, f"records[{i}]")
                  for i, raw in enumerate(document["records"])]
    access_key = "manual_access_state" if document["access_mode"] == "MANUAL" else "automated_access_state"
    source_overrides = {}
    # A conflicting source-use annotation cannot authorize another claim from
    # that same accessed URL. Reconcile internally before emitting any content;
    # denied identity/claims are never included in output or lineage keys.
    for record in normalized:
        source = record["source"]
        if not source["canonical_url"]: continue
        permission = source["permission"]
        if permission["state"] == "DENIED" or permission["purpose"] == "OTHER" or source[access_key] == "DENIED":
            source_overrides[source["canonical_url"]] = {"gate": "BLOCK", "reason": "SOURCE_PERMISSION_ACCESS_RECONCILIATION_REQUIRED"}
        elif permission["state"] == "UNKNOWN" and source["canonical_url"] not in source_overrides:
            source_overrides[source["canonical_url"]] = {"gate": "HOLD", "reason": "SOURCE_PERMISSION_RECONCILIATION_REQUIRED"}
    rows = [evaluate_record(record, as_of, document["access_mode"], i,
                            source_overrides.get(record["source"]["canonical_url"]))
            for i, record in enumerate(normalized)]
    source_policy_holds = set()
    for record in normalized:
        source, permission = record["source"], record["source"]["permission"]
        if source["canonical_url"] and (source[access_key] != "ALLOWED" or
                not all((permission["basis_url"], permission["checked_at"], permission["reviewer"])) or
                permission["purpose"] != "BUYING_INTENT_RESEARCH" or
                permission["checked_at"] and parse_date(permission["checked_at"]) > as_of or
                (permission["restrictions"] or source["access_constraints"]) and source["constraints_state"] != "VERIFIED" or
                document["access_mode"] == "AUTOMATED" and not source["license_reference"]):
            source_policy_holds.add(source["canonical_url"])
    for row in rows:
        if row["audit_only"]: continue
        if row["normalized"]["source"]["canonical_url"] in source_policy_holds:
            if row["gate"] == "PASS":
                row["gate"], row["reviewer_disposition"], row["qualified_research"] = "HOLD", "RESEARCH_NEEDED", False
            row["reasons"] = sorted(set(row["reasons"] + ["SOURCE_POLICY_RECONCILIATION_REQUIRED"]))
    domain_suppression = defaultdict(list)
    for record in normalized:
        if record["identity"]["domain"]:
            domain_suppression[record["identity"]["domain"]].append(record["suppression"])
    for row in rows:
        if row["audit_only"]: continue
        checks = domain_suppression[row["normalized"]["identity"]["domain"]]
        if any(check["state"] == "SUPPRESSED" for check in checks):
            row["gate"], row["reviewer_disposition"], row["qualified_research"] = "BLOCK", "EXCLUDED", False
            row["reasons"] = sorted(set(row["reasons"] + ["DOMAIN_SUPPRESSED"]))
        elif any(check["state"] != "CLEAR" or not check["checked_at"] or not check["evidence_reference"] or
                 parse_date(check["checked_at"]).date() != as_of.date() or
                 parse_date(check["checked_at"]) > as_of for check in checks):
            if row["gate"] == "PASS":
                row["gate"], row["reviewer_disposition"], row["qualified_research"] = "HOLD", "RESEARCH_NEEDED", False
            row["reasons"] = sorted(set(row["reasons"] + ["DOMAIN_SUPPRESSION_RECONCILIATION_REQUIRED"]))
    groups = defaultdict(list)
    for row in rows:
        if not row["audit_only"]:
            groups[row["signal_id"]].append(row)
    representatives = []
    for group in groups.values():
        # Prefer original source, then strongest gate/provenance. Tie by canonical
        # payload; equivalent repeats choose lowest index without new evidence.
        primary = min(group, key=lambda x: (
            x["normalized"]["lineage"]["is_repost"],
            {"PASS": 0, "HOLD": 1, "BLOCK": 2}[x["gate"]],
            x["normalized"]["source"]["url"] != x["normalized"]["source"]["canonical_url"],
            json.dumps(x["normalized"], sort_keys=True), x["input_index"]))
        # Conflicting evidence or suppression in a duplicate never silently loses.
        blocked = any(x["gate"] == "BLOCK" for x in group)
        if blocked:
            primary["gate"], primary["reviewer_disposition"], primary["qualified_research"] = "BLOCK", "EXCLUDED", False
        elif len(group) > 1 and any(x["gate"] == "HOLD" and set(x["reasons"]) - {
                "REPOST_REQUIRES_ORIGINAL", "VERIFIED_OWNER_MANAGER_REQUEST",
                "ATTRIBUTABLE_OPERATIONAL_PAIN_NO_PURCHASE_INFERRED"} for x in group):
            primary["gate"], primary["reviewer_disposition"], primary["qualified_research"] = "HOLD", "RESEARCH_NEEDED", False
        if any(x["freshness_state"] == "CONFLICT" for x in group):
            primary["signal_class"], primary["evidence_strength_0_to_3"], primary["freshness_state"] = "INSUFFICIENT_SIGNAL", 0, "CONFLICT"
            if not blocked:
                primary["gate"], primary["reviewer_disposition"], primary["qualified_research"] = "HOLD", "RESEARCH_NEEDED", False
        elif any(x["freshness_state"] == "EXPIRED" for x in group):
            primary["signal_class"], primary["evidence_strength_0_to_3"], primary["freshness_state"] = "INSUFFICIENT_SIGNAL", 0, "EXPIRED"
        primary["reasons"] = sorted(set(reason for x in group for reason in x["reasons"]))
        if not primary["normalized"]["lineage"]["is_repost"]:
            primary["reasons"] = [reason for reason in primary["reasons"] if reason != "REPOST_REQUIRES_ORIGINAL"]
        representatives.append(primary)
        for row in group:
            if row is primary: continue
            row["duplicate_of"] = primary["signal_id"]
            row["gate"], row["reviewer_disposition"], row["qualified_research"] = "BLOCK", "DUPLICATE", False
            row["reasons"] = sorted(set(row["reasons"] + ["DUPLICATE_SIGNAL"]))
    versions = defaultdict(list)
    for row in representatives:
        r = row["normalized"]
        origin = r["lineage"]["original_source_url"] or r["source"]["url"]
        key = (r["identity"]["domain"], canonical_url(origin) if origin else None,
               r["lineage"]["original_source_record_id"] or r["source"]["record_id"])
        if key[0] and key[1]: versions[key].append(row)
    for group in versions.values():
        dated = [x for x in group if x["normalized"]["dates"]["observed_at"]]
        dated.sort(key=lambda x: (parse_date(x["normalized"]["dates"]["observed_at"]), x["signal_id"]))
        for newer in dated:
            older = [x for x in dated if parse_date(x["normalized"]["dates"]["observed_at"]) < parse_date(newer["normalized"]["dates"]["observed_at"])]
            newer["supersedes"] = sorted(x["signal_id"] for x in older)
            for old in older:
                if old["gate"] != "BLOCK":
                    old["gate"], old["reviewer_disposition"], old["qualified_research"] = "HOLD", "RESEARCH_NEEDED", False
                old["reasons"] = sorted(set(old["reasons"] + ["SUPERSEDED_RECHECK_REQUIRED"]))
    ranked = sorted((x for x in rows if x["qualified_research"]),
                    key=lambda x: (-x["evidence_strength_0_to_3"], x["signal_id"]))
    unique = [x for x in rows if not x["duplicate_of"]]
    actual = [x for x in ranked if not x["synthetic_fixture"]]
    return {"schema_version": SCHEMA_VERSION, "rubric_version": RUBRIC_VERSION,
        "run_id": document["run_id"], "as_of": document["as_of"],
        "access_mode": document["access_mode"], "mode": "OFFLINE_RESEARCH_ONLY",
        "send_ready": False, "collector_ready": False, "pilot_started": False,
        "records": rows, "ranked_signal_ids": [x["signal_id"] for x in ranked],
        "summary": {"input_rows": len(rows), "unique_signals": len(unique),
            "duplicate_rows": len(rows) - len(unique),
            "synthetic_fixture_rows": sum(x["synthetic_fixture"] for x in rows),
            "qualified_research_signals": len(ranked),
            "qualified_research_businesses": len({x["normalized"]["identity"]["domain"] for x in ranked}),
            "nonsynthetic_qualified_research_signals": len(actual),
            "nonsynthetic_qualified_research_businesses": len({x["normalized"]["identity"]["domain"] for x in actual}),
            "gate_counts": dict(sorted(Counter(x["gate"] for x in rows).items())),
            "reason_counts": dict(sorted(Counter(reason for x in rows for reason in x["reasons"]).items())),
            "observed_cost_total": None, "cost_coverage": "NOT_AGGREGATED",
            "review_minutes_total": None, "review_time_coverage": "NOT_AGGREGATED"}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="local JSON path or - for stdin")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        def reject_constant(_): raise ValidationError("JSON: non-finite number")
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValidationError("JSON: duplicate object key")
                result[key] = value
            return result
        document = json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_keys)
        output = evaluate_document(document)
    except (OSError, ValueError) as exc:
        message = str(exc) if isinstance(exc, ValidationError) else "Cannot read valid local JSON"
        print(json.dumps({"error": message, "send_ready": False}), file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
