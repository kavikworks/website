"""Deterministic TEST_ONLY contracts for the offline research evaluator."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/buying_intent_validator.py"
spec = importlib.util.spec_from_file_location("buying_intent_validator", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
FIXTURES = json.loads((ROOT / "tests/fixtures/buying-intent-synthetic.json").read_text())


def merge(base, overrides):
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def document_for(case):
    document = copy.deepcopy(FIXTURES["base_document"])
    record = document["records"][0]
    document["access_mode"] = case["access_mode"]
    document["records"] = [merge(record, case["record_overrides"])]
    document["records"].extend(merge(record, patch) for patch in case["additional_record_overrides"])
    return document


class SyntheticContracts(unittest.TestCase):
    def test_all_fixture_contracts(self):
        self.assertGreaterEqual(len(FIXTURES["cases"]), 24)
        for case in FIXTURES["cases"]:
            with self.subTest(case=case["name"]):
                document = document_for(case)
                before = copy.deepcopy(document)
                result = validator.evaluate_document(document)
                self.assertEqual(document, before)
                self.assertEqual(result, validator.evaluate_document(document))
                self.assertFalse(result["send_ready"])
                self.assertFalse(result["collector_ready"])
                self.assertFalse(result["pilot_started"])
                self.assertEqual(result["summary"]["nonsynthetic_qualified_research_signals"], 0)
                self.assertEqual(len(result["records"]), len(case["expected_records"]))
                for row, expected in zip(result["records"], case["expected_records"]):
                    for key, value in expected.items():
                        if key == "reasons":
                            self.assertTrue(set(value) <= set(row[key]), (case["name"], row[key]))
                        else:
                            self.assertEqual(row[key], value, (case["name"], key))
                    self.assertTrue(row["synthetic_fixture"])
                    self.assertFalse(row["send_ready"])
                    self.assertEqual(row["qualified_research"], row["gate"] == "PASS")
                for key, value in case["expected_summary"].items():
                    self.assertEqual(result["summary"][key], value)

    def test_denial_and_access_errors_do_not_leak_evidence(self):
        for case in FIXTURES["cases"]:
            if case["name"].startswith(("18_", "24", "permission_unknown")):
                with self.subTest(case=case["name"]):
                    row = validator.evaluate_document(document_for(case))["records"][0]
                    self.assertTrue(row["audit_only"])
                    self.assertNotIn("normalized", row)
                    serialized = json.dumps(row)
                    for value in ("TEST_ONLY_RESTRICTED_CONTENT", "TEST_ONLY_RESTRICTED_INFERENCE",
                                  "Fixture Contractor", "business_name", "service_hypothesis"):
                        self.assertNotIn(value, serialized)

    def test_all_six_sectors_only_change_fit(self):
        for sector in validator.SECTORS:
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"][0]["fit"]["sector"] = sector
            row = validator.evaluate_document(document)["records"][0]
            self.assertEqual((row["signal_class"], row["evidence_strength_0_to_3"], row["gate"]),
                             ("EXPLICIT_BUYER_REQUEST", 3, "PASS"))
            document["records"][0]["evidence"]["category"] = "STAFFING"
            row = validator.evaluate_document(document)["records"][0]
            self.assertEqual(row["evidence_strength_0_to_3"], 0)
            self.assertFalse(row["qualified_research"])

    def test_missing_required_fields_never_pass(self):
        required = ["source.url", "source.permission.state", "source.permission.purpose",
            "source.permission.basis_url", "source.permission.checked_at", "source.permission.reviewer",
            "source.manual_access_state", "source.access_method", "source.type", "dates.observed_at",
            "dates.retrieved_at", "dates.direct_verified_at", "identity.business_name", "identity.domain",
            "identity.state", "identity.confidence", "identity.evidence_url", "identity.author_role",
            "identity.author_state", "identity.author_evidence_url", "fit.sector",
            "fit.sector_evidence_url", "fit.location_claim", "fit.geography", "fit.geographic_basis_url",
            "fit.scope", "evidence.text", "evidence.kind", "evidence.category", "evidence.workflow",
            "evidence.explicit_help_request", "evidence.attribution_state", "evidence.original_state",
            "evidence.verification_state", "evidence.verification_url", "suppression.state",
            "suppression.checked_at", "suppression.evidence_reference"]
        for name in required:
            with self.subTest(field=name):
                document = copy.deepcopy(FIXTURES["base_document"])
                target = document["records"][0]
                path = name.split(".")
                for key in path[:-1]: target = target[key]
                del target[path[-1]]
                row = validator.evaluate_document(document)["records"][0]
                self.assertNotEqual(row["gate"], "PASS")
                self.assertTrue(row["reasons"])

    def test_schema_errors_fail_closed_without_echoing_input(self):
        changes = [
            {"evidence": {"explicit_help_request": "PRIVATE_SENTINEL"}},
            {"source": {"permission": {"state": "PRIVATE_SENTINEL"}}},
            {"identity": {"domain": "PRIVATE_SENTINEL"}},
            {"source": {"url": "https://user:PRIVATE_SENTINEL@fixture.example/"}},
            {"dates": {"observed_at": "2026-02-30"}},
            {"dates": {"retrieved_at": "2026-10-11T10:00:00"}},
            {"measurement": {"cost_observed": -1}},
            {"measurement": {"cost_observed": True}},
            {"measurement": {"cost_observed": float("nan")}},
            {"measurement": {"source_hit_count": 10**1000}},
            {"source": {"permission": {"restrictions": "PRIVATE_SENTINEL"}}},
            {"access_error": {"attempts": 3}},
            {"access_error": {"code": "ROBOTS_REJECTED", "retry_state": "DEFERRED"}},
            {"send_ready": True},
        ]
        for change in changes:
            with self.subTest(change=change):
                document = copy.deepcopy(FIXTURES["base_document"])
                document["records"][0] = merge(document["records"][0], change)
                with self.assertRaises(validator.ValidationError) as exc:
                    validator.evaluate_document(document)
                self.assertNotIn("PRIVATE_SENTINEL", str(exc.exception))

    def test_null_measurement_and_coverage_are_preserved(self):
        result = validator.evaluate_document(FIXTURES["base_document"])
        measurement = result["records"][0]["normalized"]["measurement"]
        for name in ("review_minutes_actual", "cost_observed", "source_hit_count", "currency"):
            self.assertIsNone(measurement[name])
        self.assertEqual(measurement["cost_coverage"], "UNKNOWN")
        self.assertEqual(measurement["review_time_coverage"], "UNKNOWN")
        self.assertIsNone(result["summary"]["observed_cost_total"])
        self.assertIsNone(result["summary"]["review_minutes_total"])

    def test_retrieval_or_verification_before_statement_is_held(self):
        for name in ("retrieved_at", "direct_verified_at"):
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"][0]["dates"][name] = "2026-09-01"
            row = validator.evaluate_document(document)["records"][0]
            self.assertEqual(row["gate"], "HOLD")
            self.assertIn("PROVENANCE_CHRONOLOGY_INCONSISTENT", row["reasons"])

    def test_same_day_chronology_uses_available_timestamp_precision(self):
        document = copy.deepcopy(FIXTURES["base_document"])
        dates = document["records"][0]["dates"]
        dates.update(observed_at="2026-10-11T14:00:00Z", retrieved_at="2026-10-11T10:00:00Z",
                     direct_verified_at="2026-10-11T10:00:00Z")
        row = validator.evaluate_document(document)["records"][0]
        self.assertEqual(row["gate"], "HOLD")
        self.assertIn("PROVENANCE_CHRONOLOGY_INCONSISTENT", row["reasons"])
        dates["observed_at"] = "2026-10-11"
        self.assertEqual(validator.evaluate_document(document)["records"][0]["gate"], "PASS")

    def test_url_normalization_preserves_meaningful_identity(self):
        canonical = validator.canonical_url
        self.assertEqual(canonical("https://WWW.FIXTURE.EXAMPLE:443/Case/?b=2&a=1&utm_source=x#f"),
                         "https://fixture.example/Case/?a=1&b=2")
        self.assertNotEqual(canonical("https://fixture.example/?id=1"), canonical("https://fixture.example/?id=2"))
        self.assertNotEqual(canonical("https://fixture.example/Case"), canonical("https://fixture.example/case"))

    def test_original_repost_and_newer_lineage(self):
        for name in ("22_canonical_and_repost_dedupe", "23_newer_lineage_idempotency"):
            case = next(case for case in FIXTURES["cases"] if case["name"] == name)
            document = document_for(case)
            result = validator.evaluate_document(document)
            rows = result["records"]
            if name.startswith("22"):
                self.assertEqual(len({x["signal_id"] for x in rows}), 1)
                self.assertEqual(rows[1]["duplicate_of"], rows[0]["signal_id"])
                self.assertEqual(rows[2]["duplicate_of"], rows[0]["signal_id"])
                self.assertEqual(rows[1]["normalized"]["source"]["url"], document["records"][1]["source"]["url"])
            else:
                self.assertNotEqual(rows[0]["signal_id"], rows[1]["signal_id"])
                self.assertEqual(rows[1]["supersedes"], [rows[0]["signal_id"]])
            document["records"].reverse()
            reversed_result = validator.evaluate_document(document)
            self.assertEqual(result["ranked_signal_ids"], reversed_result["ranked_signal_ids"])
            self.assertEqual(result["summary"], reversed_result["summary"])

    def test_duplicate_suppression_unknown_conflict_are_conservative(self):
        for change in ({"suppression": {"state": "SUPPRESSED"}},
                       {"suppression": {"state": "UNKNOWN"}},
                       {"evidence": {"verification_state": "CONFLICT"}}):
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"].append(merge(document["records"][0], change))
            result = validator.evaluate_document(document)
            self.assertEqual(result["summary"]["qualified_research_signals"], 0)
            self.assertTrue(all(not row["qualified_research"] for row in result["records"]))

    def test_permission_conflicts_strip_all_content_from_same_source(self):
        for state in ("DENIED", "UNKNOWN"):
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"].append(merge(document["records"][0], {"source": {"permission": {"state": state}}}))
            for records in (document["records"], list(reversed(document["records"]))):
                result = validator.evaluate_document(dict(document, records=records))
                self.assertEqual(result["summary"]["qualified_research_signals"], 0)
                self.assertTrue(all(row["audit_only"] for row in result["records"]))
                self.assertNotIn("business_name", json.dumps(result))
                self.assertNotIn("asking for help", json.dumps(result))

    def test_domain_suppression_applies_across_distinct_claims(self):
        for state in ("SUPPRESSED", "UNKNOWN", "NOT_CHECKED"):
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"].append(merge(document["records"][0], {
                "suppression": {"state": state},
                "evidence": {"text": "TEST_ONLY: Owner requests help with a different claim."}}))
            for records in (document["records"], list(reversed(document["records"]))):
                result = validator.evaluate_document(dict(document, records=records))
                self.assertEqual(result["summary"]["qualified_research_businesses"], 0)
                self.assertTrue(all(row["gate"] == ("BLOCK" if state == "SUPPRESSED" else "HOLD")
                                    for row in result["records"]))

    def test_source_policy_unknowns_apply_across_distinct_claims(self):
        for change in ({"permission": {"basis_url": None}},
                       {"manual_access_state": "UNVERIFIED"},
                       {"access_constraints": ["TEST_ONLY unresolved constraint"]}):
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"].append(merge(document["records"][0], {
                "source": change, "evidence": {"text": "TEST_ONLY: A different claim at the same URL."}}))
            result = validator.evaluate_document(document)
            self.assertEqual(result["summary"]["qualified_research_signals"], 0)
            self.assertIn("SOURCE_POLICY_RECONCILIATION_REQUIRED", result["records"][0]["reasons"])

    def test_duplicate_expiry_overrides_strength_and_freshness(self):
        document = copy.deepcopy(FIXTURES["base_document"])
        document["records"].append(merge(document["records"][0], {"dates": {"expires_at": "2026-10-10"}}))
        result = validator.evaluate_document(document)
        representative = next(row for row in result["records"] if not row["duplicate_of"])
        self.assertEqual((representative["signal_class"], representative["evidence_strength_0_to_3"],
                          representative["freshness_state"], representative["gate"]),
                         ("INSUFFICIENT_SIGNAL", 0, "EXPIRED", "BLOCK"))

    def test_access_method_must_match_selected_mode(self):
        document = copy.deepcopy(FIXTURES["base_document"])
        document["access_mode"] = "AUTOMATED"
        document["records"][0]["source"].update(automated_access_state="ALLOWED",
            license_reference="TEST_ONLY authorized API placeholder", access_method="MANUAL_READER")
        row = validator.evaluate_document(document)["records"][0]
        self.assertEqual(row["gate"], "HOLD")
        self.assertIn("ACCESS_METHOD_MODE_MISMATCH", row["reasons"])
        document["records"][0]["source"]["access_method"] = "APPROVED_API"
        self.assertEqual(validator.evaluate_document(document)["records"][0]["gate"], "PASS")
        document["access_mode"] = "MANUAL"
        self.assertEqual(validator.evaluate_document(document)["records"][0]["gate"], "HOLD")

    def test_reposts_alone_are_held(self):
        case = next(case for case in FIXTURES["cases"] if case["name"].startswith("22_"))
        document = document_for(case)
        document["records"] = [document["records"][2]]
        result = validator.evaluate_document(document)
        self.assertEqual(result["records"][0]["gate"], "HOLD")
        self.assertIn("REPOST_REQUIRES_ORIGINAL", result["records"][0]["reasons"])

    def test_expiry_and_contradiction_override_age(self):
        for dates, state in (({"observed_at": "2026-10-10", "expires_at": "2026-10-11"}, "EXPIRED"),
                             ({"observed_at": "2026-01-01"}, "CONFLICT")):
            document = copy.deepcopy(FIXTURES["base_document"])
            document["records"][0]["dates"].update(dates)
            if state == "CONFLICT": document["records"][0]["evidence"]["verification_state"] = "CONFLICT"
            row = validator.evaluate_document(document)["records"][0]
            self.assertEqual(row["freshness_state"], state)
            self.assertEqual(row["evidence_strength_0_to_3"], 0)

    def test_rank_and_business_yield_are_distinct(self):
        document = copy.deepcopy(FIXTURES["base_document"])
        pain = next(case for case in FIXTURES["cases"] if case["name"].startswith("03_"))
        document["records"].append(merge(document["records"][0], pain["record_overrides"]))
        result = validator.evaluate_document(document)
        self.assertEqual(result["summary"]["qualified_research_signals"], 2)
        self.assertEqual(result["summary"]["qualified_research_businesses"], 1)
        self.assertEqual(result["ranked_signal_ids"][0], result["records"][0]["signal_id"])

    def test_no_network_during_evaluation(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            for case in FIXTURES["cases"]:
                validator.evaluate_document(document_for(case))

    def test_cli_local_and_stdin_and_invalid_json(self):
        serialized = json.dumps(FIXTURES["base_document"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test-only.json"
            path.write_text(serialized)
            before = {p.name: p.read_bytes() for p in Path(folder).iterdir()}
            from_file = subprocess.run([sys.executable, str(SCRIPT), str(path)], text=True, capture_output=True)
            from_stdin = subprocess.run([sys.executable, str(SCRIPT)], input=serialized, text=True, capture_output=True)
            self.assertEqual(from_file.returncode, 0, from_file.stderr)
            self.assertEqual(from_stdin.returncode, 0, from_stdin.stderr)
            self.assertEqual(json.loads(from_file.stdout), json.loads(from_stdin.stdout))
            self.assertEqual(before, {p.name: p.read_bytes() for p in Path(folder).iterdir()})
        for invalid in ('{"PRIVATE_SENTINEL":', '{"a":1,"a":2}', '{"a":NaN}'):
            failed = subprocess.run([sys.executable, str(SCRIPT)], input=invalid, text=True, capture_output=True)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, "")
            self.assertFalse(json.loads(failed.stderr)["send_ready"])
            self.assertNotIn("PRIVATE_SENTINEL", failed.stderr)


if __name__ == "__main__":
    unittest.main()
