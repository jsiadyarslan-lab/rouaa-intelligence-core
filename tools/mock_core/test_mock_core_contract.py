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

    # M2.K2 — K2 temporal_data is now EMITTED with 5 D4 sub-fields
    def test_M2_K2_temporal_data_present_with_5_subfields(self):
        body = json.loads(_get("/v1/intelligence/io-fdic-enf")[1])
        self.assertIn("temporal_data", body)
        td = body["temporal_data"]
        self.assertIsInstance(td, dict)
        # All 5 sub-fields present per directive §4
        for sub in ("publication_time", "publication_time_raw",
                    "publication_timezone_status", "reference_period",
                    "reference_period_normalized_utc"):
            self.assertIn(sub, td, f"K2 sub-field missing: {sub}")

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

    # M8 — traceability endpoint (Contract B)
    def test_M8_trace_chain(self):
        code, body, _ = _get("/v1/intelligence/io-fdic-enf/trace")
        self.assertEqual(code, 200)
        trace = json.loads(body)
        self.assertEqual(trace["io_id"], "io-fdic-enf")
        self.assertTrue(trace["chain"][0]["representation"]["content_sha256"])


if __name__ == "__main__":
    unittest.main()
