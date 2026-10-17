"""Bounded offline manual-evidence review queues; no discovery or sending.

All facts, permissions and verification states are caller assertions. The
adapter evaluates them; it never independently verifies a source or business.
"""

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import sys

import buying_intent_validator as validator


SCHEMA_VERSION = "manual-review-1.0"
MAX_RECORDS = 100
MAX_INPUT_BYTES = 1024 * 1024
MAX_REVIEW_LIMIT = MAX_RECORDS
LANES = ("EXPLICIT_BUYING_INTENT", "TRIGGER_PLUS_FIT", "FIT_ONLY")
PURPOSES = ("BUYING_INTENT_RESEARCH", "TRIGGER_RESEARCH", "FIT_RESEARCH", "OTHER", "UNKNOWN")
DESK_CHECKS = ("CURRENT_SUPPRESSION", "APPROVAL", "CADENCE", "EXCLUSIVE_MAIL_CONTROL")

# This independent input schema extends only permission purpose. Never change
# the legacy schema or teach its classifier that recruiting establishes pain.
RECORD_SCHEMA = copy.deepcopy(validator.RECORD_SCHEMA)
RECORD_SCHEMA["source"]["permission"]["purpose"] = validator.field("enum", "UNKNOWN", PURPOSES)
REVIEW_SCHEMA = {
    "source_status": validator.field("enum", "UNKNOWN", ("ACTIVE", "DELETED", "UNKNOWN")),
    "geography_scope": validator.field("enum", "UNKNOWN", ("CURRENT_POLICY", "PROPOSED_ONLY", "UNKNOWN")),
    "country_code": validator.field("enum", "UNKNOWN", ("US", "OTHER", "UNKNOWN")),
    "country_basis_url": validator.field("url"),
    "exclusion_state": validator.field("enum", "UNKNOWN", ("CLEAR", "EXCLUDED", "UNKNOWN")),
    "exclusion_reference": validator.field("text"),
    "recruiting": {
        "relevance": validator.field("enum", "UNKNOWN", ("RELEVANT", "IRRELEVANT", "UNKNOWN")),
        "role_title": validator.field("text"),
        "observed_responsibilities": validator.field("list", []),
        "basis_url": validator.field("url"),
    },
}
GEOGRAPHY_SCHEMA = {
    "scope": validator.field("enum", "UNKNOWN", ("US_NATIONWIDE", "REVIEWER_DEFINED", "UNKNOWN")),
    "approval_state": validator.field("enum", "UNKNOWN", ("APPROVED", "PROPOSED", "UNKNOWN")),
    "approval_reference": validator.field("text"),
}


def identifier(prefix, value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return prefix + hashlib.sha256(payload).hexdigest()[:24]


def required_purpose(record):
    category = record["evidence"]["category"]
    if category == "STAFFING" or record["source"]["type"] == "JOB_LISTING":
        return "TRIGGER_RESEARCH"
    if category in ("BUYER_REQUEST", "OPERATIONAL_PAIN", "THIRD_PARTY_COMPLAINT"):
        return "BUYING_INTENT_RESEARCH"
    return "FIT_RESEARCH"


def legacy_projection(record):
    """Reuse legacy conflict/dedupe gates without borrowing a permission grant.

    The legacy gate engine has one purpose token. Internally translate only a
    matching, explicit adapter purpose to that token. A mismatch becomes denied
    use, and unknown purpose stays unknown. Output always restores the actual
    purpose/permission; this projection never grants buying-intent permission.
    """
    projected = copy.deepcopy(record)
    projected["source"].pop("canonical_url", None)
    permission = projected["source"]["permission"]
    actual = permission["purpose"]
    if actual == "UNKNOWN":
        permission["state"], permission["purpose"] = (
            "DENIED" if permission["state"] == "DENIED" else "UNKNOWN", "UNKNOWN")
    elif actual != required_purpose(record):
        permission["state"], permission["purpose"] = "DENIED", "OTHER"
    else:
        permission["purpose"] = "BUYING_INTENT_RESEARCH"
    return projected


def normalize(document):
    if not isinstance(document, dict):
        raise validator.ValidationError("document: expected object")
    required = {"schema_version", "as_of", "run_id", "input_origin", "records"}
    if not required <= set(document) or set(document) - required - {"review_limit", "proposed_geography", "geography_policy"}:
        raise validator.ValidationError("document: expected manual-review wrapper fields only")
    if document["schema_version"] != SCHEMA_VERSION:
        raise validator.ValidationError("schema_version: unsupported adapter version")
    if document["input_origin"] not in ("OWNER_CURATED", "AUTHORIZED_MANUAL", "SYNTHETIC"):
        raise validator.ValidationError("input_origin: owner-curated, authorized manual or synthetic required")
    if not isinstance(document["run_id"], str) or not document["run_id"].strip():
        raise validator.ValidationError("run_id: nonempty text required")
    try:
        validator.parse_date(document["as_of"])
        size = len(json.dumps(document, allow_nan=False).encode())
    except (ValueError, TypeError, OverflowError):
        raise validator.ValidationError("document: valid dates and finite JSON required") from None
    if size > MAX_INPUT_BYTES:
        raise validator.ValidationError("document: exceeds offline input byte limit")
    records = document["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise validator.ValidationError("records: expected at most 100 manual entries")
    limit = document.get("review_limit", MAX_REVIEW_LIMIT)
    if type(limit) is not int or not 1 <= limit <= MAX_REVIEW_LIMIT:
        raise validator.ValidationError("review_limit: integer from 1 to 100 required")
    proposed = document.get("proposed_geography")
    if proposed is not None and (not isinstance(proposed, str) or not proposed.strip() or len(proposed) > 200):
        raise validator.ValidationError("proposed_geography: at most 200 characters or null")
    geography = validator.normalize_fields(document.get("geography_policy", {}), GEOGRAPHY_SCHEMA, "geography_policy")
    entries = []
    for index, entry in enumerate(records):
        if not isinstance(entry, dict) or set(entry) - {"record", "review"} or "record" not in entry:
            raise validator.ValidationError(f"records[{index}]: expected record and optional review only")
        record = validator.normalize_fields(entry["record"], RECORD_SCHEMA, f"records[{index}]")
        review = validator.normalize_fields(entry.get("review", {}), REVIEW_SCHEMA, f"review[{index}]")
        non_intent = {"JOB_LISTING": "STAFFING", "INTAKE_FEATURE": "INTAKE_FEATURE"}
        source_type = record["source"]["type"]
        if source_type in non_intent and record["evidence"]["category"] != non_intent[source_type]:
            raise validator.ValidationError(f"records[{index}].evidence.category: incompatible non-intent source type")
        if document["input_origin"] == "SYNTHETIC" and not record["synthetic_fixture"]:
            raise validator.ValidationError(f"records[{index}].synthetic_fixture: synthetic input requires fixture flag")
        entries.append((record, review))
    return entries, limit, geography


def make_row(record, review, strict, geography):
    source, permission = record["source"], record["source"]["permission"]
    reasons = set(strict["reasons"])
    expected = required_purpose(record)
    if permission["purpose"] == "UNKNOWN":
        reasons.add("RESEARCH_PURPOSE_UNKNOWN")
    elif permission["purpose"] != expected:
        reasons.add("RESEARCH_PURPOSE_NOT_PERMITTED")
    row = {
        "review_id": identifier("review-", [strict["signal_id"], expected]),
        "source_id": identifier("source-", [source["canonical_url"], source["record_id"]]) if source["canonical_url"] else None,
        "business_id": None, "lane": None,
        "disposition": "EXCLUDED" if strict["gate"] == "BLOCK" else "NEEDS_REVIEW",
        "reasons": [], "send_ready": False, "desk_checks_required": list(DESK_CHECKS),
        "audit_only": strict["audit_only"], "synthetic_fixture": record["synthetic_fixture"],
        "required_permission_purpose": expected,
        "validator_evaluation": {key: copy.deepcopy(strict[key]) for key in (
            "signal_id", "signal_class", "evidence_strength_0_to_3", "freshness_state",
            "gate", "qualified_research", "duplicate_of", "supersedes")},
        "duplicate_business_of": None,
    }
    if strict["audit_only"]:
        row["audit"] = copy.deepcopy(strict["audit"])
        row["audit"]["permission"] = copy.deepcopy(permission)
        row["reasons"] = sorted(reasons)
        return row

    domain = record["identity"]["domain"]
    row["business_id"] = identifier("business-", domain) if domain else None
    category = record["evidence"]["category"]
    strength = strict["signal_class"]
    is_recruiting = category == "STAFFING" or source["type"] == "JOB_LISTING"
    if is_recruiting:
        row["lane"] = "TRIGGER_PLUS_FIT"
        reasons.add("RECRUITING_IS_NOT_BUYING_INTENT")
    elif strength == "EXPLICIT_BUYER_REQUEST":
        row["lane"] = "EXPLICIT_BUYING_INTENT"
    elif category == "BUYER_REQUEST":
        reasons.add("EXPLICIT_INTENT_NOT_VERIFIED")
    else:
        row["lane"] = "FIT_ONLY"
        reasons.add("NO_EXPLICIT_BUYING_INTENT")

    blockers, holds = set(), set()
    if geography["scope"] == "UNKNOWN":
        holds.add("GEOGRAPHY_POLICY_UNKNOWN")
    if geography["approval_state"] != "APPROVED":
        holds.add("GEOGRAPHY_POLICY_NOT_APPROVED")
    elif not geography["approval_reference"]:
        holds.add("GEOGRAPHY_APPROVAL_REFERENCE_MISSING")
    if review["source_status"] == "DELETED":
        blockers.add("SOURCE_DELETED")
    elif review["source_status"] != "ACTIVE":
        holds.add("SOURCE_STATUS_UNKNOWN")
    if review["geography_scope"] != "CURRENT_POLICY":
        holds.add("PROPOSED_GEOGRAPHY_NOT_APPROVED" if review["geography_scope"] == "PROPOSED_ONLY" else "GEOGRAPHY_POLICY_BASIS_UNKNOWN")
    if review["country_code"] == "OTHER":
        blockers.add("COUNTRY_OUTSIDE_US")
    elif review["country_code"] != "US":
        holds.add("COUNTRY_UNKNOWN")
    elif not review["country_basis_url"]:
        holds.add("COUNTRY_BASIS_MISSING")
    if review["exclusion_state"] == "EXCLUDED":
        blockers.add("MANUAL_EXCLUSION")
    elif review["exclusion_state"] != "CLEAR":
        holds.add("EXCLUSION_STATE_UNKNOWN")
    elif not review["exclusion_reference"]:
        holds.add("EXCLUSION_CHECK_REFERENCE_MISSING")

    recruiting = review["recruiting"]
    if is_recruiting:
        if category != "STAFFING":
            holds.add("RECRUITING_CATEGORY_CONFLICT")
        if recruiting["relevance"] == "IRRELEVANT":
            blockers.add("RECRUITING_IRRELEVANT")
        elif recruiting["relevance"] != "RELEVANT":
            holds.add("RECRUITING_RELEVANCE_UNKNOWN")
        if source["type"] != "JOB_LISTING":
            holds.add("RECRUITING_SOURCE_REQUIRED")
        if not all((recruiting["role_title"], recruiting["observed_responsibilities"], recruiting["basis_url"])):
            holds.add("RECRUITING_BASIS_INCOMPLETE")

    # These are the only legacy HOLD reasons a non-intent review lane can waive.
    # Every identity, provenance, permission, fit, conflict, suppression and
    # uncertainty gate is retained. The underlying class and strength stay 0.
    waived = {"NO_OPERATIONAL_SIGNAL", "INDEPENDENT_RESEARCH_REQUIRED"} if category in ("STAFFING", "OTHER", "INTAKE_FEATURE") else set()
    if strict["gate"] == "BLOCK":
        blockers.add("VALIDATOR_BLOCK")
    elif strict["gate"] == "HOLD" and (not waived or set(strict["reasons"]) - waived):
        holds.add("VALIDATOR_REVIEW_REQUIRED")
    if row["lane"] is None:
        holds.add("LANE_UNRESOLVED")
    row["disposition"] = "EXCLUDED" if blockers else "NEEDS_REVIEW" if holds else "REVIEW_CANDIDATE"
    row["reasons"] = sorted(reasons | blockers | holds)
    row["provenance"] = {"source": copy.deepcopy(source), "identity": copy.deepcopy(record["identity"]),
                         "fit": copy.deepcopy(record["fit"]), "suppression_snapshot": copy.deepcopy(record["suppression"])}
    row["evidence"] = {"claim": copy.deepcopy(record["evidence"]), "dates": copy.deepcopy(record["dates"]),
                       "recruiting_role_title": recruiting["role_title"],
                       "recruiting_observed_responsibilities": recruiting["observed_responsibilities"]}
    row["inference"] = {"service_hypothesis": record["service_hypothesis"],
                        "recruiting_relevance": recruiting["relevance"]}
    row["measurement"] = copy.deepcopy(record["measurement"])
    row["review_annotations"] = copy.deepcopy(review)
    return row


def hold_or_exclude(row, reason, exclude=False):
    row["reasons"] = sorted(set(row["reasons"]) | {reason})
    if exclude:
        row["disposition"] = "EXCLUDED"
    elif row["disposition"] != "EXCLUDED":
        row["disposition"] = "NEEDS_REVIEW"


def evaluate_document(document):
    entries, limit, geography = normalize(document)
    legacy = validator.evaluate_document({
        "schema_version": validator.SCHEMA_VERSION, "as_of": document["as_of"],
        "run_id": document["run_id"], "access_mode": "MANUAL",
        "records": [legacy_projection(record) for record, _ in entries],
    })
    rows = [make_row(record, review, strict, geography) for (record, review), strict in zip(entries, legacy["records"])]
    # Legacy duplicate selection cannot see wrapper annotations. Reconcile every
    # wrapper hold/exclusion for the same signal before choosing any candidate.
    signals = defaultdict(list)
    for index, row in enumerate(rows):
        if not row["audit_only"]:
            signals[row["validator_evaluation"]["signal_id"]].append((index, row))
    for group in signals.values():
        if len(group) < 2:
            continue
        primary_index = next(index for index, row in group if not row["validator_evaluation"]["duplicate_of"])
        common = legacy["records"][primary_index]
        snapshots = []
        for index, row in group:
            # Dedupe itself is not a negative annotation. Evaluate every
            # wrapper against the reconciled primary gate before reducing it.
            strict = copy.deepcopy(legacy["records"][index])
            strict["gate"], strict["reasons"] = common["gate"], common["reasons"]
            snapshots.append(make_row(*entries[index], strict, geography))
        if any(snapshot["disposition"] != "REVIEW_CANDIDATE" for snapshot in snapshots):
            exclude = any(snapshot["disposition"] == "EXCLUDED" for snapshot in snapshots)
            reasons = {reason for snapshot in snapshots for reason in snapshot["reasons"]}
            for _, row in group:
                hold_or_exclude(row, "DUPLICATE_REVIEW_ANNOTATIONS_UNRESOLVED", exclude=exclude)
                row["reasons"] = sorted(set(row["reasons"]) | reasons)
    sources, businesses, business_policies = defaultdict(list), defaultdict(list), defaultdict(list)
    for index, row in enumerate(rows):
        source_url = entries[index][0]["source"]["canonical_url"]
        if source_url:
            sources[source_url].append((index, row))
        domain = entries[index][0]["identity"]["domain"]
        if domain:
            # Negative manual policy annotations may block privately by domain,
            # even on a restricted source. Never emit its identity or use it to
            # create/promote a candidate. This matches legacy suppression logic.
            business_policies[identifier("business-", domain)].append((index, row))
        if not row["audit_only"] and row["business_id"]:
            businesses[row["business_id"]].append(row)
    for group in sources.values():
        statuses = [entries[index][1]["source_status"] for index, _ in group]
        if "DELETED" in statuses:
            for _, row in group:
                hold_or_exclude(row, "SOURCE_STATUS_RECONCILIATION_REQUIRED", exclude=True)
        elif any(status != "ACTIVE" for status in statuses):
            for _, row in group:
                hold_or_exclude(row, "SOURCE_STATUS_RECONCILIATION_REQUIRED")
        errors = [entries[index][0]["access_error"]["code"] for index, _ in group]
        if any(error != "NONE" for error in errors):
            for _, row in group:
                hold_or_exclude(row, "SOURCE_ACCESS_RECHECK_REQUIRED", exclude="ROBOTS_REJECTED" in errors)
        ids = defaultdict(set)
        for _, row in group:
            if not row["audit_only"]:
                ids[row["source_id"]].add(row["business_id"])
        if any(len(values) > 1 for values in ids.values()):
            for _, row in group:
                hold_or_exclude(row, "SOURCE_BUSINESS_IDENTITY_CONFLICT")
    for group in business_policies.values():
        reviews = [entries[index][1] for index, _ in group]
        if any(review["exclusion_state"] == "EXCLUDED" for review in reviews):
            for _, row in group:
                hold_or_exclude(row, "BUSINESS_EXCLUDED", exclude=True)
        elif any(review["exclusion_state"] != "CLEAR" or not review["exclusion_reference"] for review in reviews):
            for _, row in group:
                hold_or_exclude(row, "BUSINESS_EXCLUSION_RECONCILIATION_REQUIRED")
        geographies = {entries[index][0]["fit"]["geography"] for index, _ in group}
        if "OUTSIDE" in geographies and "ELIGIBLE" in geographies:
            for _, row in group:
                hold_or_exclude(row, "BUSINESS_GEOGRAPHY_CONFLICT")
        countries = {review["country_code"] for review in reviews}
        if "US" in countries and "OTHER" in countries:
            for _, row in group:
                hold_or_exclude(row, "BUSINESS_COUNTRY_CONFLICT")

    def priority(row):
        return (LANES.index(row["lane"]), row["business_id"], row["source_id"] or "", row["review_id"])

    # One review candidate per business; preserve every source row and reason.
    candidates = []
    for group in businesses.values():
        eligible = sorted((row for row in group if row["disposition"] == "REVIEW_CANDIDATE"), key=priority)
        if eligible:
            candidates.append(eligible[0])
            for duplicate in eligible[1:]:
                duplicate["duplicate_business_of"] = eligible[0]["review_id"]
                hold_or_exclude(duplicate, "DUPLICATE_BUSINESS", exclude=True)
    candidates.sort(key=priority)
    for row in candidates[limit:]:
        hold_or_exclude(row, "REVIEW_LIMIT_REACHED")
    rows.sort(key=lambda row: (row["review_id"], row["disposition"], json.dumps(row, sort_keys=True)))
    return {
        "schema_version": SCHEMA_VERSION, "as_of": document["as_of"], "run_id": document["run_id"],
        "input_origin": document["input_origin"], "mode": "OFFLINE_MANUAL_REVIEW_ONLY",
        "send_ready": False, "collector_ready": False, "pilot_started": False,
        "review_limit": limit, "proposed_geography": document.get("proposed_geography"),
        "geography_policy": geography, "geography_policy_applies_to_live_controls": False,
        "proposed_geography_applies_to_live_policy": False, "desk_checks_required": list(DESK_CHECKS),
        "records": rows, "review_candidate_ids": [row["review_id"] for row in candidates[:limit]],
        "summary": {"input_rows": len(rows), "synthetic_fixture_rows": sum(row["synthetic_fixture"] for row in rows),
                    "disposition_counts": dict(sorted(Counter(row["disposition"] for row in rows).items())),
                    "review_candidate_businesses": len(candidates[:limit]),
                    "nonsynthetic_review_candidate_businesses": sum(not row["synthetic_fixture"] for row in candidates[:limit]),
                    "observed_cost_total": None, "cost_coverage": "NOT_AGGREGATED",
                    "review_minutes_total": None, "review_time_coverage": "NOT_AGGREGATED"},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="local JSON path or - for stdin")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(args.input).open("rb") as stream:
                payload = stream.read(MAX_INPUT_BYTES + 1)
        if len(payload) > MAX_INPUT_BYTES:
            raise validator.ValidationError("document: exceeds offline input byte limit")

        def reject_constant(_):
            raise validator.ValidationError("JSON: non-finite number")

        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise validator.ValidationError("JSON: duplicate object key")
                result[key] = value
            return result

        document = json.loads(payload, parse_constant=reject_constant, object_pairs_hook=unique_keys)
        output = evaluate_document(document)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, validator.ValidationError) else "Cannot read valid local review JSON"
        print(json.dumps({"error": message, "send_ready": False}), file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
