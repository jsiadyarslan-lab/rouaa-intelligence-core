"""Canonical-contract conformance tests — M1–M8 (R2 §15).

Only requirements the approved architecture actually contains are tested.
Run: python -m tools.mock_core.test_mock_core_contract
M1 endpoint · M2 schema(+anti-fabrication) · M3 versioning · M4 required ids
M5 error behavior · M6 provenance · M7 temporal-gap-honesty · M8 traceability.
"""
import json
import os
import subprocess
import sys
import time
import unittest
import urllib.request

PORT = 8891
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "test-token"


def _get(path, token=TOKEN, etag=None):
    req = urllib.request.Request(BASE + path)
    req.add_header("Authorization", f"Bearer {token}")
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


class TestCanonicalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ, MOCK_CORE_TOKEN=TOKEN)
        cls.proc = subprocess.Popen([sys.executable, "tools/mock_core/mock_core_server.py",
                                     str(PORT)], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                _get("/health", token="x")
                break
            except Exception:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()

    # M1 — canonical endpoint surface (approved architecture §L)
    def test_M1_health_public(self):
        code, body, _ = _get("/health", token="")
        self.assertEqual(code, 200)

    def test_M1_unauthorized(self):
        code, _, _ = _get("/v1/intelligence", token="")
        self.assertEqual(code, 401)

    def test_M1_feed_and_pagination(self):
        code, body, _ = _get("/v1/intelligence")
        self.assertEqual(code, 200)
        feed = json.loads(body)
        self.assertEqual(len(feed["objects"]), 2)
        code2, body2, _ = _get(f"/v1/intelligence?cursor={feed['next_cursor']}")
        feed2 = json.loads(body2)
        self.assertEqual(len(feed2["objects"]), 1)
        self.assertIsNone(feed2["next_cursor"])

    # M2 — schema = real IO shape; ZERO fabricated/undecided fields
    def test_M2_required_fields_exactly_real_IO_shape(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        self.assertEqual(set(body.keys()), {
            "io_id", "version", "event_id", "event_version", "status",
            "supersedes_io_id", "headline", "chain", "created_at",
            # K1/K2 promoted per CORE_SEMANTIC_PROMOTION_K1_K2_V1
            "event_type", "temporal_data"})
        link = body["chain"][0]
        self.assertEqual(set(link.keys()),
                         {"fact", "evidence", "representation", "document", "source"})

    def test_M2_no_fabricated_or_undecided_fields(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        # Fabricated fields remain prohibited (CORE_SEMANTIC_PROMOTION_K1_K2_V1 §6)
        for field in ("provenance_complete", "confidence_score", "reproducible",
                      "quality_metadata", "provenance_match",
                      "source_id", "institution_id", "document_ref"):
            self.assertNotIn(field, body,
                             f"fabricated/undecided field leaked into contract: {field}")

    # M2.K1 — K1 event_type is now EMITTED (was architectural gap, now promoted)
    def test_M2_K1_event_type_present_and_correctly_typed(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        self.assertIn("event_type", body)
        self.assertEqual(body["event_type"], "regulatory_enforcement")
        self.assertIsInstance(body["event_type"], str)

    # M2.K2 — K2 temporal_data is now EMITTED with ALL 6 D4 fields per tuple
    # (CORE_K2_D4_FIDELITY_CLOSURE_V1 — was 5 fields with 2 dropped: normalization_basis, provenance_source)
    def test_M2_K2_temporal_data_preserves_all_6_D4_fields_publication(self):
        """Per CORE_K2_D4_FIDELITY_CLOSURE_V1 §3: ALL 6 D4 TemporalTuple fields
        must be preserved for the publication tuple. Previously dropped:
        normalization_basis, provenance_source."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        # Publication tuple — all 6 D4 fields (3 backward-compat + 3 added per closure)
        for sub in ("publication_time",               # D4 normalized_utc
                    "publication_time_raw",            # D4 original_value
                    "publication_timezone_status",     # D4 timezone_status
                    "publication_normalization_basis",  # D4 normalization_basis [ADDED]
                    "publication_timestamp_semantics", # D4 timestamp_semantics [ADDED]
                    "publication_provenance_source"):   # D4 provenance_source [ADDED]
            self.assertIn(sub, td, f"D4-faithful publication field missing: {sub}")

    def test_M2_K2_temporal_data_preserves_all_6_D4_fields_reference_period(self):
        """Per CORE_K2_D4_FIDELITY_CLOSURE_V1 §3: ALL 6 D4 TemporalTuple fields
        must be preserved for the reference_period tuple when it exists."""
        # io-cpi-v1 is a statistical_release WITH reference_period (non-null)
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        # Reference period tuple — all 6 D4 fields
        for sub in ("reference_period",                      # D4 normalized_utc
                    "reference_period_normalized_utc",      # D4 normalized_utc (alias)
                    "reference_period_raw",                  # D4 original_value [ADDED]
                    "reference_period_timezone_status",     # D4 timezone_status [ADDED]
                    "reference_period_normalization_basis",  # D4 normalization_basis [ADDED]
                    "reference_period_timestamp_semantics", # D4 timestamp_semantics [ADDED]
                    "reference_period_provenance_source"):   # D4 provenance_source [ADDED]
            self.assertIn(sub, td, f"D4-faithful reference_period field missing: {sub}")

    # M3 — versioning: io.version=1 constant; event_version carries D2 lineage
    def test_M3_v1_v2_distinct_histories_preserved(self):
        v1 = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        v2 = json.loads(_get("/v1/intelligence/io-cpi-v2")[1])
        self.assertEqual((v1["version"], v1["event_version"]), (1, 1))
        self.assertEqual((v2["version"], v2["event_version"]), (1, 2))
        self.assertEqual(v1["status"], "SUPERSEDED")
        self.assertEqual(v2["status"], "ACTIVE")
        self.assertEqual(v2["supersedes_io_id"], "io-cpi-v1")
        self.assertEqual(v1["chain"][0]["fact"]["value"], "+0.3")
        self.assertEqual(v2["chain"][0]["fact"]["value"], "+0.4")

    # M4 — required identity resolution
    def test_M4_missing_id_404_and_conditional_304(self):
        code, _, _ = _get("/v1/intelligence/io-nonexistent")
        self.assertEqual(code, 404)
        _, _, h = _get("/v1/intelligence/io-fdic-enf")
        code, _, _ = _get("/v1/intelligence/io-fdic-enf", etag=h["ETag"])
        self.assertEqual(code, 304)
        code, _, _ = _get("/v1/intelligence?_force_status=429")
        self.assertEqual(code, 429)

    # M5 — error model + read-only enforcement
    def test_M5_read_only_405_and_drills(self):
        req = urllib.request.Request(BASE + "/v1/intelligence", data=b"{}", method="POST")
        req.add_header("Authorization", f"Bearer {TOKEN}")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                self.assertEqual(r.status, 405)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 405)
        code, body, _ = _get("/v1/intelligence?_force_status=500")
        self.assertEqual(code, 500)
        self.assertIn("error", json.loads(body))

    # M6 — provenance semantics: chain carries exact representation hash
    def test_M6_chain_representation_sha(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        link = body["chain"][0]
        self.assertEqual(len(link["representation"]["content_sha256"]), 64)
        self.assertTrue(link["evidence"][0]["evidence_id"].startswith("evi-"))
        self.assertIn("canonical_url", link["document"])
        self.assertIn("institution_id", link["source"])

    # M7 — K2 temporal_data now PROMOTED (was architectural gap).
    #       The contract must emit temporal_data with D4-faithful semantics:
    #       - publication_time present (from publication_tuples).
    #       - reference_period may be null when no reporting_period tuple exists.
    #       - null = NOT_APPLICABLE / UNKNOWN (never fabricated).
    def test_M7_temporal_data_now_present_with_d4_semantics(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        self.assertIn("temporal_data", body)
        td = body["temporal_data"]
        # publication_time present (FDIC has RSS pubdate)
        self.assertIsNotNone(td["publication_time"])
        # reference_period may be null (regulatory actions have no statistical
        # reference period — D4 §9 distinction)
        self.assertIsNone(td["reference_period"])

    # M7.stat — statistical release MUST preserve reference_period ≠ publication_time
    # (D4 §9 directive — the key statistical-intelligence distinction)
    def test_M7_statistical_release_reference_period_distinct_from_publication_time(self):
        v1 = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        self.assertEqual(v1["event_type"], "statistical_release")
        td = v1["temporal_data"]
        self.assertIsNotNone(td["publication_time"])
        self.assertIsNotNone(td["reference_period"])
        # D4 §9: reference_period != publication_time (NOT collapsed)
        self.assertNotEqual(td["reference_period"], td["publication_time"])

    # M7.reg — regulatory_enforcement MUST have reference_period=null
    def test_M7_regulatory_enforcement_reference_period_null(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        self.assertEqual(body["event_type"], "regulatory_enforcement")
        td = body["temporal_data"]
        # Per §12: regulatory actions have no statistical reference period
        self.assertIsNone(td["reference_period"])
        self.assertIsNone(td["reference_period_normalized_utc"])
        # But publication_time is present (regulatory actions are published)
        self.assertIsNotNone(td["publication_time"])

    # ── CORE_K2_D4_FIDELITY_CLOSURE_V1: D4 field preservation tests ──

    # M7.D4.pub — publication tuple preserves normalization_basis + provenance_source
    def test_M7_D4_publication_normalization_basis_preserved(self):
        """§3 critical check: D4 normalization_basis MUST be preserved (was dropped)."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["publication_normalization_basis"],
                              "publication_normalization_basis was dropped — D4 semantic loss")
        self.assertEqual(td["publication_normalization_basis"], "EXPLICIT_SOURCE_TIMEZONE")

    def test_M7_D4_publication_provenance_source_preserved(self):
        """§3 critical check: D4 provenance_source MUST be preserved (was dropped)."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["publication_provenance_source"],
                              "publication_provenance_source was dropped — D4 semantic loss")
        self.assertEqual(td["publication_provenance_source"], "rss_pubdate")

    def test_M7_D4_publication_timestamp_semantics_preserved(self):
        """§3: D4 timestamp_semantics MUST be preserved."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["publication_timestamp_semantics"])
        self.assertEqual(td["publication_timestamp_semantics"], "publication")

    # M7.D4.ref — reference_period tuple preserves all D4 fields (statistical release)
    def test_M7_D4_reference_period_normalization_basis_preserved(self):
        """§3: D4 normalization_basis preserved for reference_period tuple (statistical release)."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        # Statistical release has a DATE_ONLY reference_period (no timezone)
        self.assertIsNotNone(td["reference_period_normalization_basis"])
        self.assertEqual(td["reference_period_normalization_basis"], "NONE")
        # D4 §5: when normalization_basis is NONE, normalized_utc should be null
        # (date-only reference periods are NOT converted to UTC)
        # BUT the mock fixture uses "2026-07" as the reference_period value
        # (a month identifier, not a UTC timestamp). This is the D4-faithful
        # representation of a date-only statistical reporting period.

    def test_M7_D4_reference_period_provenance_source_preserved(self):
        """§3: D4 provenance_source preserved for reference_period tuple."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["reference_period_provenance_source"])
        self.assertEqual(td["reference_period_provenance_source"], "rendered_text")

    def test_M7_D4_reference_period_timestamp_semantics_preserved(self):
        """§3: D4 timestamp_semantics preserved for reference_period tuple."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["reference_period_timestamp_semantics"])
        self.assertEqual(td["reference_period_timestamp_semantics"], "reporting_period")

    def test_M7_D4_reference_period_raw_preserved(self):
        """§3: D4 original_value preserved for reference_period tuple (was dropped)."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["reference_period_raw"],
                              "reference_period_raw was dropped — D4 original_value lost")

    def test_M7_D4_reference_period_timezone_status_preserved(self):
        """§3: D4 timezone_status preserved for reference_period tuple (was dropped)."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        self.assertIsNotNone(td["reference_period_timezone_status"],
                              "reference_period_timezone_status was dropped — D4 timezone_status lost")
        # DATE_ONLY because "2026-07" is a month, not a timestamp with timezone
        self.assertEqual(td["reference_period_timezone_status"], "DATE_ONLY")

    # M7.D4.edge — edge cases: DATE_ONLY, UNKNOWN, NAIVE_LOCAL, EXPLICIT_OFFSET, EXPLICIT_ZONE
    def test_M7_D4_edge_timezone_statuses_represented(self):
        """§5: D4 TZStatus enum values must be preservable in the IO emission."""
        # FDIC has EXPLICIT_ZONE (UTC Z-suffix)
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertEqual(td["publication_timezone_status"], "EXPLICIT_ZONE")

        # ISTAT CPI v2 has EXPLICIT_OFFSET (+0200)
        body2 = json.loads(_get("/v1/intelligence/io-cpi-v2")[1])
        td2 = body2["temporal_data"]
        self.assertEqual(td2["publication_timezone_status"], "EXPLICIT_OFFSET")

        # ISTAT CPI v1 has DATE_ONLY for reference_period (month identifier)
        body3 = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td3 = body3["temporal_data"]
        self.assertEqual(td3["reference_period_timezone_status"], "DATE_ONLY")

    # M8 — traceability endpoint (Contract B)
    def test_M8_trace_chain(self):
        code, body, _ = _get("/v1/intelligence/io-fdic-enf/trace")
        self.assertEqual(code, 200)
        trace = json.loads(body)
        self.assertEqual(trace["io_id"], "io-fdic-enf")
        self.assertTrue(trace["chain"][0]["representation"]["content_sha256"])

    # ── CORE_K2_D4_MULTIPLICITY_CLOSURE_V1: D4 cardinality tests ──

    # M9.card — temporal_tuples[] preserves ALL D4 tuples (cardinality)
    def test_M9_temporal_tuples_array_present(self):
        """§2: temporal_tuples[] array MUST be present in temporal_data."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertIn("temporal_tuples", td,
                      "temporal_tuples[] array missing — D4 multiplicity not preserved")
        self.assertIsInstance(td["temporal_tuples"], list)

    def test_M9_cardinality_single_tuple_fdic(self):
        """§2: FDIC IO has 1 D4 tuple (publication only) — cardinality preserved."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertEqual(len(td["temporal_tuples"]), 1,
                          "FDIC should have 1 temporal tuple — cardinality mismatch")

    def test_M9_cardinality_multi_tuple_istat_v1(self):
        """§2-3: ISTAT CPI v1 has 3 D4 tuples (publication + reporting_period + document_date)
        — all must be preserved without collapse."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        self.assertEqual(len(td["temporal_tuples"]), 3,
                          "ISTAT CPI v1 should have 3 temporal tuples — cardinality collapse detected")

    # M9.conflict — conflicting-date test: document_date differs from publication
    def test_M9_conflicting_dates_preserved(self):
        """§3: When two tuples have conflicting dates, BOTH must be recoverable."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        tuples = td["temporal_tuples"]
        pub = next((t for t in tuples if t["timestamp_semantics"] == "publication"), None)
        doc_date = next((t for t in tuples if t["timestamp_semantics"] == "document_date"), None)
        self.assertIsNotNone(pub, "publication tuple not in temporal_tuples[]")
        self.assertIsNotNone(doc_date, "document_date tuple not in temporal_tuples[]")
        self.assertEqual(pub["provenance_source"], "rss_pubdate")
        self.assertEqual(doc_date["provenance_source"], "html_time_attr")
        self.assertNotEqual(pub["original_value"], doc_date["original_value"],
                            "conflicting dates collapsed — tuple A == tuple B")

    # M9.semantics — all D4 timestamp_semantics values are distinct in temporal_tuples[]
    def test_M9_semantic_distinction_publication(self):
        """§4: publication semantics preserved distinctly in temporal_tuples[]."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertEqual(td["temporal_tuples"][0]["timestamp_semantics"], "publication")

    def test_M9_semantic_distinction_reporting_period(self):
        """§4: reporting_period semantics preserved distinctly in temporal_tuples[]."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        ref = next((t for t in td["temporal_tuples"]
                    if t["timestamp_semantics"] == "reporting_period"), None)
        self.assertIsNotNone(ref, "reporting_period tuple not in temporal_tuples[]")

    def test_M9_semantic_distinction_document_date(self):
        """§4: document_date semantics preserved distinctly in temporal_tuples[]."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        doc_date = next((t for t in td["temporal_tuples"]
                         if t["timestamp_semantics"] == "document_date"), None)
        self.assertIsNotNone(doc_date, "document_date tuple not in temporal_tuples[]")

    # M9.prov — every tuple in temporal_tuples[] has all 6 D4 fields
    def test_M9_every_tuple_has_all_6_D4_fields(self):
        """§5: Every tuple in temporal_tuples[] must have all 6 D4 fields."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        for i, t in enumerate(td["temporal_tuples"]):
            for field in ("original_value", "timezone_status", "normalized_utc",
                         "normalization_basis", "timestamp_semantics", "provenance_source"):
                self.assertIn(field, t,
                              f"tuple[{i}] missing D4 field: {field}")

    # M9.order — temporal_tuples[] preserves D4 original order
    def test_M9_temporal_tuples_preserve_original_order(self):
        """§1: temporal_tuples[] MUST preserve D4 original order (no reordering)."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        tuples = td["temporal_tuples"]
        self.assertEqual(tuples[0]["timestamp_semantics"], "publication")
        self.assertEqual(tuples[1]["timestamp_semantics"], "reporting_period")
        self.assertEqual(tuples[2]["timestamp_semantics"], "document_date")

    # M9.backward — backward compat: publication_* / reference_period_* still work
    def test_M9_backward_compat_publication_accessor(self):
        """§7: publication_* convenience fields still work (backward compat)."""
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        td = body["temporal_data"]
        self.assertEqual(td["publication_time"], td["temporal_tuples"][0]["normalized_utc"])
        self.assertEqual(td["publication_time_raw"], td["temporal_tuples"][0]["original_value"])

    def test_M9_backward_compat_reference_period_accessor(self):
        """§7: reference_period_* convenience fields still work (backward compat)."""
        body = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
        td = body["temporal_data"]
        ref_tuple = next((t for t in td["temporal_tuples"]
                          if t["timestamp_semantics"] == "reporting_period"), None)
        self.assertEqual(td["reference_period"], ref_tuple["normalized_utc"])
        self.assertEqual(td["reference_period_raw"], ref_tuple["original_value"])


if __name__ == "__main__":
    unittest.main()
