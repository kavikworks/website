import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import buying_intent_review as adapter

FIXTURES = json.loads((ROOT / "tests/fixtures/buying-intent-review-synthetic.json").read_text())


def merge(base, changes):
    result = copy.deepcopy(base)
    for key, value in changes.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else copy.deepcopy(value)
    return result


def entry(template="OWNER", changes=None):
    base = merge(FIXTURES["base_document"]["records"][0], FIXTURES["entry_templates"][template])
    return merge(base, changes or {})


def document(records=None, changes=None):
    result = copy.deepcopy(FIXTURES["base_document"])
    if records is not None:
        result["records"] = copy.deepcopy(records)
    return merge(result, changes or {})


def new_business(index, template="OWNER"):
    domain = f"test-only-{index}.example"
    return entry(template, {"record": {
        "source": {"url": f"https://{domain}/request", "record_id": f"TEST_ONLY-{index}"},
        "identity": {"domain": domain, "business_name": f"TEST_ONLY business {index}",
                     "evidence_url": f"https://{domain}/identity", "author_evidence_url": f"https://{domain}/owner"},
        "evidence": {"verification_url": f"https://{domain}/request"},
        "fit": {"sector_evidence_url": f"https://{domain}/services"},
    }})


class ManualReviewContracts(unittest.TestCase):
    def test_all_synthetic_fixture_contracts_and_no_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            for case in FIXTURES["cases"]:
                with self.subTest(case=case["name"]):
                    source = document([entry(case["template"], case["entry_overrides"])], case["document_overrides"])
                    before = copy.deepcopy(source)
                    result = adapter.evaluate_document(source)
                    self.assertEqual(source, before)
                    self.assertEqual(result, adapter.evaluate_document(source))
                    row, = result["records"]
                    expected = case["expected"]
                    for name in ("disposition", "lane", "audit_only"):
                        self.assertEqual(row[name], expected[name], row["reasons"])
                    for name in ("signal_class", "evidence_strength_0_to_3"):
                        self.assertEqual(row["validator_evaluation"][name], expected[name], row["reasons"])
                    self.assertTrue(set(expected["reasons"]) <= set(row["reasons"]), row["reasons"])
                    self.assertFalse(row["send_ready"])
                    self.assertEqual(row["desk_checks_required"], list(adapter.DESK_CHECKS))
                    self.assertTrue(row["synthetic_fixture"])
                    self.assertFalse(result["send_ready"])
                    self.assertFalse(result["collector_ready"])
                    self.assertFalse(result["pilot_started"])
                    self.assertEqual(result["summary"]["nonsynthetic_review_candidate_businesses"], 0)
                    self.assertIsNone(result["summary"]["observed_cost_total"])
                    self.assertIsNone(result["summary"]["review_minutes_total"])

    def test_permission_purposes_are_explicit_and_not_borrowed(self):
        for template, purpose in (("OWNER", "BUYING_INTENT_RESEARCH"), ("RECRUITING", "TRIGGER_RESEARCH"), ("FIT", "FIT_RESEARCH")):
            row, = adapter.evaluate_document(document([entry(template)]))["records"]
            self.assertEqual(row["disposition"], "REVIEW_CANDIDATE")
            self.assertEqual(row["required_permission_purpose"], purpose)
            self.assertEqual(row["provenance"]["source"]["permission"]["purpose"], purpose)
            for wrong in set(adapter.PURPOSES) - {purpose, "UNKNOWN"}:
                source = entry(template, {"record": {"source": {"permission": {"purpose": wrong}}}})
                row, = adapter.evaluate_document(document([source]))["records"]
                self.assertTrue(row["audit_only"])
                self.assertEqual(row["disposition"], "EXCLUDED")
                self.assertIsNone(row["business_id"])

    def test_restricted_inputs_never_emit_business_claim_or_inference(self):
        for state in ("DENIED", "UNKNOWN"):
            source = entry(changes={"record": {"source": {"permission": {"state": state}},
                "evidence": {"text": "TEST_ONLY_RESTRICTED_CONTENT"}, "service_hypothesis": "TEST_ONLY_RESTRICTED_INFERENCE"},
                "review": {"recruiting": {"role_title": "TEST_ONLY_RESTRICTED_ROLE"}}})
            result = adapter.evaluate_document(document([source, entry()]))
            self.assertEqual(result["review_candidate_ids"], [])
            for row in result["records"]:
                self.assertTrue(row["audit_only"])
                self.assertIsNone(row["business_id"])
                for key in ("provenance", "evidence", "inference", "review_annotations"):
                    self.assertNotIn(key, row)
            serialized = json.dumps(result)
            for secret in ("TEST_ONLY_RESTRICTED_CONTENT", "TEST_ONLY_RESTRICTED_INFERENCE", "TEST_ONLY_RESTRICTED_ROLE", "business_name", "Fixture Contractor"):
                self.assertNotIn(secret, serialized)

    def test_recruiting_and_widget_never_gain_intent_strength(self):
        for template in ("RECRUITING", "INTAKE"):
            for sector in adapter.validator.SECTORS:
                source = entry(template, {"record": {"fit": {"sector": sector}}})
                row, = adapter.evaluate_document(document([source]))["records"]
                self.assertEqual(row["validator_evaluation"]["signal_class"], "INSUFFICIENT_SIGNAL")
                self.assertEqual(row["validator_evaluation"]["evidence_strength_0_to_3"], 0)
                self.assertFalse(row["validator_evaluation"]["qualified_research"])
                self.assertNotEqual(row["lane"], "EXPLICIT_BUYING_INTENT")

    def test_contradictory_non_intent_source_type_fails_closed(self):
        for source_type in ("JOB_LISTING", "INTAKE_FEATURE"):
            source = entry(changes={"record": {"source": {"type": source_type}}})
            with self.assertRaisesRegex(adapter.validator.ValidationError, "incompatible non-intent source type"):
                adapter.evaluate_document(document([source]))

    def test_duplicate_wrapper_conflicts_cannot_depend_on_order(self):
        pairs = [
            [entry(), entry(changes={"review": {"geography_scope": "PROPOSED_ONLY"}})],
            [entry(), entry(changes={"review": {"country_code": "UNKNOWN"}})],
            [entry("RECRUITING"), entry("RECRUITING", {"review": {"recruiting": {"relevance": "IRRELEVANT"}}})],
            [entry("RECRUITING"), entry("RECRUITING", {"review": {"recruiting": {"relevance": "UNKNOWN"}}})],
        ]
        for pair in pairs:
            summaries = []
            for records in (pair, list(reversed(pair))):
                result = adapter.evaluate_document(document(records))
                self.assertEqual(result["review_candidate_ids"], [])
                self.assertTrue(all("DUPLICATE_REVIEW_ANNOTATIONS_UNRESOLVED" in row["reasons"] for row in result["records"]))
                summaries.append(result["summary"])
            self.assertEqual(*summaries)

    def test_deleted_and_failed_source_metadata_in_audit_rows_still_gates_source(self):
        for error, status in (("TIMEOUT", "DELETED"), ("TIMEOUT", "ACTIVE"), ("ROBOTS_REJECTED", "ACTIVE")):
            failed = entry(changes={"record": {"access_error": {"code": error, "attempts": 1,
                "retry_state": "DO_NOT_RETRY" if error == "ROBOTS_REJECTED" else "DEFERRED"},
                "evidence": {"text": "TEST_ONLY_RESTRICTED_CONTENT"}}, "review": {"source_status": status}})
            for records in ([entry(), failed], [failed, entry()]):
                result = adapter.evaluate_document(document(records))
                self.assertEqual(result["review_candidate_ids"], [])
                self.assertNotIn("TEST_ONLY_RESTRICTED_CONTENT", json.dumps(result))
                self.assertTrue(all("SOURCE_ACCESS_RECHECK_REQUIRED" in row["reasons"] for row in result["records"]))
                if status == "DELETED" or error == "ROBOTS_REJECTED":
                    self.assertTrue(all(row["disposition"] == "EXCLUDED" for row in result["records"]))

    def test_duplicate_sources_and_businesses_and_lane_priority(self):
        records = [entry(), entry(), entry("RECRUITING"), new_business(2, "FIT")]
        forward = adapter.evaluate_document(document(records))
        reverse = adapter.evaluate_document(document(list(reversed(records))))
        self.assertEqual(forward["review_candidate_ids"], reverse["review_candidate_ids"])
        self.assertEqual(forward["summary"], reverse["summary"])
        self.assertEqual(len(forward["review_candidate_ids"]), 2)
        selected = {row["review_id"]: row for row in forward["records"] if row["disposition"] == "REVIEW_CANDIDATE"}
        self.assertEqual([selected[key]["lane"] for key in forward["review_candidate_ids"]], ["EXPLICIT_BUYING_INTENT", "FIT_ONLY"])
        self.assertEqual(len({row["business_id"] for row in selected.values()}), 2)
        self.assertTrue(any("DUPLICATE_BUSINESS" in row["reasons"] for row in forward["records"]))
        self.assertTrue(any("DUPLICATE_SIGNAL" in row["reasons"] for row in forward["records"]))

    def test_source_business_identity_conflict_holds_every_candidate(self):
        other = new_business(3)
        other["record"]["source"] = copy.deepcopy(entry()["record"]["source"])
        result = adapter.evaluate_document(document([entry(), other]))
        self.assertEqual(result["review_candidate_ids"], [])
        self.assertTrue(all("SOURCE_BUSINESS_IDENTITY_CONFLICT" in row["reasons"] for row in result["records"]))

    def test_business_exclusions_geography_and_suppression_are_conservative(self):
        for change in ({"review": {"exclusion_state": "EXCLUDED"}},
                       {"review": {"exclusion_state": "UNKNOWN"}},
                       {"record": {"fit": {"geography": "OUTSIDE"}}},
                       {"record": {"suppression": {"state": "UNKNOWN"}}},
                       {"record": {"suppression": {"state": "SUPPRESSED"}}}):
            result = adapter.evaluate_document(document([entry(), entry("RECRUITING", change)]))
            self.assertEqual(result["review_candidate_ids"], [], change)

    def test_audit_only_business_exclusions_still_block_without_revealing_identity(self):
        restricted = [{"source": {"permission": {"state": "DENIED"}}},
                      {"source": {"permission": {"state": "UNKNOWN"}}},
                      {"access_error": {"code": "TIMEOUT", "attempts": 1, "retry_state": "DEFERRED"}}]
        for restriction in restricted:
            for state in ("EXCLUDED", "UNKNOWN"):
                source = entry("RECRUITING", {"record": merge(restriction, {
                    "evidence": {"text": "TEST_ONLY_RESTRICTED_CONTENT"},
                    "service_hypothesis": "TEST_ONLY_RESTRICTED_INFERENCE"}),
                    "review": {"exclusion_state": state}})
                for records in ([entry(), source], [source, entry()]):
                    result = adapter.evaluate_document(document(records))
                    self.assertEqual(result["review_candidate_ids"], [])
                    self.assertNotIn("TEST_ONLY_RESTRICTED_CONTENT", json.dumps(result))
                    self.assertNotIn("TEST_ONLY_RESTRICTED_INFERENCE", json.dumps(result))
                    for row in result["records"]:
                        if row["audit_only"]:
                            self.assertIsNone(row["business_id"])
                            self.assertNotIn("provenance", row)
                            self.assertNotIn("evidence", row)
                            self.assertNotIn("inference", row)
                    if state == "EXCLUDED":
                        self.assertTrue(all(row["disposition"] == "EXCLUDED" for row in result["records"]))

    def test_contradictory_countries_do_not_pick_the_attractive_source(self):
        other = entry("RECRUITING", {"review": {"country_code": "OTHER"}})
        result = adapter.evaluate_document(document([entry(), other]))
        self.assertEqual(result["review_candidate_ids"], [])
        self.assertTrue(all("BUSINESS_COUNTRY_CONFLICT" in row["reasons"] for row in result["records"]))

    def test_newer_lineage_holds_old_claim(self):
        newer = entry(changes={"record": {"dates": {"observed_at": "2026-10-16"},
            "evidence": {"text": "TEST_ONLY: Owner requests review of a newer follow-up process."}}})
        result = adapter.evaluate_document(document([entry(), newer]))
        self.assertEqual(len(result["review_candidate_ids"]), 1)
        self.assertTrue(any(row["validator_evaluation"]["supersedes"] for row in result["records"]))
        self.assertTrue(any("SUPERSEDED_RECHECK_REQUIRED" in row["reasons"] for row in result["records"]))

    def test_stable_ids_canonicalization_and_retrieval_does_not_create_claim(self):
        original = adapter.evaluate_document(document())["records"][0]
        variant = entry(changes={"record": {"source": {"url": "https://WWW.FIXTURE-CONTRACTOR.EXAMPLE:443/request?utm_source=test#fragment"},
            "identity": {"domain": "WWW.FIXTURE-CONTRACTOR.EXAMPLE"},
            "dates": {"retrieved_at": "2026-10-16", "direct_verified_at": "2026-10-16"}}})
        row, = adapter.evaluate_document(document([variant]))["records"]
        for key in ("source_id", "business_id", "review_id"):
            self.assertEqual(original[key], row[key])

    def test_nationwide_approval_is_explicit_and_proposals_do_not_override_facts(self):
        eligible = entry(changes={"record": {"fit": {"location_claim": "TEST_ONLY fictional US location outside the former local territory", "geography": "ELIGIBLE"}}})
        row, = adapter.evaluate_document(document([eligible]))["records"]
        self.assertEqual(row["disposition"], "REVIEW_CANDIDATE")
        proposed = document([eligible], {"geography_policy": {"approval_state": "PROPOSED"}, "proposed_geography": "TEST_ONLY US nationwide"})
        result = adapter.evaluate_document(proposed)
        self.assertEqual(result["review_candidate_ids"], [])
        self.assertFalse(result["geography_policy_applies_to_live_controls"])
        for state in ("UNKNOWN", "OUTSIDE"):
            outside = entry(changes={"record": {"fit": {"geography": state}}})
            row, = adapter.evaluate_document(document([outside], {"proposed_geography": "TEST_ONLY entire US"}))["records"]
            self.assertNotEqual(row["disposition"], "REVIEW_CANDIDATE")

    def test_queue_bound_is_deterministic_and_is_not_a_send_cadence(self):
        records = [new_business(i) for i in range(6)]
        result = adapter.evaluate_document(document(records, {"review_limit": 2}))
        other = adapter.evaluate_document(document(list(reversed(records)), {"review_limit": 2}))
        self.assertEqual(result["review_candidate_ids"], other["review_candidate_ids"])
        self.assertEqual(len(result["review_candidate_ids"]), 2)
        self.assertEqual(sum("REVIEW_LIMIT_REACHED" in row["reasons"] for row in result["records"]), 4)
        self.assertNotIn("messages_per_day", result)
        self.assertTrue(all(not row["send_ready"] for row in result["records"]))

    def test_evidence_and_inference_are_separate(self):
        source = entry(changes={"record": {"evidence": {"text": "TEST_ONLY_OBSERVED_FACT"}, "service_hypothesis": "TEST_ONLY_INFERENCE"}})
        row, = adapter.evaluate_document(document([source]))["records"]
        self.assertIn("TEST_ONLY_OBSERVED_FACT", json.dumps(row["evidence"]))
        self.assertNotIn("TEST_ONLY_INFERENCE", json.dumps(row["evidence"]))
        self.assertEqual(row["inference"]["service_hypothesis"], "TEST_ONLY_INFERENCE")

    def test_null_measurements_and_coverage_are_preserved_without_invented_totals(self):
        result = adapter.evaluate_document(document())
        row, = result["records"]
        self.assertIsNone(row["measurement"]["cost_observed"])
        self.assertIsNone(row["measurement"]["review_minutes_actual"])
        self.assertEqual(row["measurement"]["cost_coverage"], "UNKNOWN")
        self.assertEqual(row["measurement"]["review_time_coverage"], "UNKNOWN")
        self.assertEqual(result["summary"]["cost_coverage"], "NOT_AGGREGATED")
        self.assertEqual(result["summary"]["review_time_coverage"], "NOT_AGGREGATED")

    def test_missing_review_fields_and_legacy_required_unknowns_do_not_pass(self):
        for name in ("source_status", "geography_scope", "country_code", "country_basis_url", "exclusion_state", "exclusion_reference"):
            source = entry()
            del source["review"][name]
            self.assertEqual(adapter.evaluate_document(document([source]))["review_candidate_ids"], [], name)
        for group, name in (("dates", "observed_at"), ("dates", "retrieved_at"), ("dates", "direct_verified_at"),
                            ("identity", "state"), ("identity", "confidence"), ("fit", "geography"), ("suppression", "state")):
            source = entry("RECRUITING")
            del source["record"][group][name]
            self.assertEqual(adapter.evaluate_document(document([source]))["review_candidate_ids"], [], (group, name))

    def test_schema_and_bounds_fail_closed_without_echoing_values(self):
        invalid = [document(changes={"review_limit": True}), document(changes={"review_limit": 101}),
                   document(changes={"records": [entry()] * 101}), document(changes={"send_ready": True}),
                   document(changes={"schema_version": "PRIVATE_SENTINEL"}),
                   document(changes={"proposed_geography": "x" * 201}),
                   document([entry(changes={"review": {"source_status": "PRIVATE_SENTINEL"}})]),
                   document([entry(changes={"record": {"synthetic_fixture": False}})]),
                   document(changes={"run_id": "PRIVATE_SENTINEL" * adapter.MAX_INPUT_BYTES})]
        for source in invalid:
            with self.assertRaises(adapter.validator.ValidationError) as raised:
                adapter.evaluate_document(source)
            self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))
        with self.assertRaises(adapter.validator.ValidationError):
            adapter.validator.evaluate_document(document())

    def test_cli_local_and_stdin_no_files_written_and_errors_are_redacted(self):
        command = [sys.executable, str(ROOT / "scripts/buying_intent_review.py")]
        serialized = json.dumps(document())
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "test-only-input.json"
            source.write_text(serialized)
            before = {p.name: p.read_bytes() for p in Path(folder).iterdir()}
            first = subprocess.run(command + [str(source)], capture_output=True, text=True)
            second = subprocess.run(command, input=serialized, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
            self.assertEqual(before, {p.name: p.read_bytes() for p in Path(folder).iterdir()})
        for invalid in ('{"PRIVATE_SENTINEL":', '{"x":1,"x":2}', '{"x":NaN}', "x" * (adapter.MAX_INPUT_BYTES + 1)):
            failed = subprocess.run(command, input=invalid, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, "")
            self.assertFalse(json.loads(failed.stderr)["send_ready"])
            self.assertNotIn("PRIVATE_SENTINEL", failed.stderr)


if __name__ == "__main__":
    unittest.main()
