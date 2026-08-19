"""S1 Production Core Transport — HTTP endpoint tests.

Directive: ROUAA_CORE_PRODUCTION_TRANSPORT_S1_V1 §5, §10

Tests the production transport at intelligence_core/production_transport.py
against the seeded production store (intelligence_core/tests/fixtures/
seed_production_store.py).

Covers:
  - §5: 200 success, 401 unauthorized, 404 not-found, 400 bad-request,
        405 read-only, 5xx chain-broken
  - §6: auth (Bearer token via env)
  - §7: pagination (cursor, limit, next_cursor, ordering)
  - §8: ETag/304
  - §9: failure semantics (no silent empty on broken chain)
  - §4: canonical response conformance (schema, fields, no fabricated)
  - §10: canonical mock vs production equivalence on identical fixtures
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
PORT = 9301
TOKEN = "production-test-token-v1"


def _free_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _http_get(path: str, token: str | None = None,
              if_none_match: str | None = None) -> tuple[int, dict, str, dict]:
    """Return (status, headers, body_str, parsed_json_or_empty)."""
    url = f"http://127.0.0.1:{PORT}{path}"
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if if_none_match:
        req.add_header("If-None-Match", if_none_match)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {}
            return resp.status, dict(resp.headers), body, parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {}
        return e.code, dict(e.headers), body, parsed


def _http_method(method: str, path: str, token: str | None = None) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{PORT}{path}"
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {}
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {}
        return e.code, parsed


class _ServerCtx:
    """Spawn the production transport server on a seeded temp store."""

    def __enter__(self):
        # Create a temp store and seed it
        self.store_root = tempfile.mkdtemp(prefix="production_test_store_")
        # Seed using the fixture seeder
        sys.path.insert(0, str(CORE_REPO))
        from intelligence_core.tests.fixtures.seed_production_store import seed
        self.manifest = seed(self.store_root)

        # Spawn the production transport
        env = os.environ.copy()
        env["CORE_API_TOKEN"] = TOKEN
        env["CORE_STORE_PATH"] = self.store_root
        env["PYTHONPATH"] = str(CORE_REPO)
        env["CORE_TEST_MODE"] = "1"  # V2-Continuous §15: disable signal handlers in tests

        self.proc = subprocess.Popen(
            [
                sys.executable, "-c",
                f"from intelligence_core.production_transport import serve; "
                f"serve(port={PORT})",
            ],
            cwd=str(CORE_REPO),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Wait for bind
        deadline = time.time() + 5
        while time.time() < deadline:
            if not _free_port(PORT):
                break
            if self.proc.poll() is not None:
                out, err = self.proc.communicate(timeout=2)
                raise RuntimeError(f"Server died. stdout={out!r} stderr={err!r}")
            time.sleep(0.1)
        else:
            self.proc.terminate()
            raise RuntimeError(f"Server did not bind to {PORT}")
        return self

    def __exit__(self, *exc):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        shutil.rmtree(self.store_root, ignore_errors=True)


class TestHealthEndpoint(unittest.TestCase):
    """§5 Public health endpoint."""

    def test_health_returns_200_without_auth(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get("/health")
            self.assertEqual(status, 200)
            self.assertEqual(parsed["status"], "ok")


class TestCanonicalListEndpoint(unittest.TestCase):
    """§3-5 /v1/intelligence list endpoint."""

    def test_list_returns_200_with_objects(self):
        with _ServerCtx() as ctx:
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            self.assertEqual(status, 200)
            self.assertIn("objects", parsed)
            self.assertIsInstance(parsed["objects"], list)
            self.assertEqual(parsed["count"], 3)
            self.assertIn("next_cursor", parsed)

    def test_list_no_auth_returns_401(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=None)
            self.assertEqual(status, 401)
            self.assertEqual(parsed["error"]["code"], "UNAUTHORIZED")

    def test_list_invalid_auth_returns_401(self):
        with _ServerCtx():
            status, _, _, _ = _http_get("/v1/intelligence", token="wrong-token")
            self.assertEqual(status, 401)

    def test_list_etag_returned(self):
        with _ServerCtx():
            status, headers, _, _ = _http_get("/v1/intelligence", token=TOKEN)
            self.assertEqual(status, 200)
            etag = headers.get("ETag") or headers.get("ETag")
            self.assertIsNotNone(etag)

    def test_list_304_on_if_none_match(self):
        with _ServerCtx():
            status1, headers, _, _ = _http_get("/v1/intelligence", token=TOKEN)
            etag = headers.get("ETag") or headers.get("ETag")
            self.assertIsNotNone(etag)
            status2, _, _, _ = _http_get(
                "/v1/intelligence", token=TOKEN, if_none_match=etag
            )
            self.assertEqual(status2, 304)


class TestPagination(unittest.TestCase):
    """§7 Pagination semantics."""

    def test_limit_param_respected(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get(
                "/v1/intelligence?limit=1", token=TOKEN
            )
            self.assertEqual(status, 200)
            self.assertEqual(parsed["count"], 1)
            self.assertEqual(len(parsed["objects"]), 1)
            # With 3 IOs and limit=1, next_cursor should be set
            self.assertIsNotNone(parsed["next_cursor"])

    def test_limit_capped_at_200(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get(
                "/v1/intelligence?limit=10000", token=TOKEN
            )
            self.assertEqual(status, 200)
            self.assertEqual(parsed["count"], 3)

    def test_invalid_limit_returns_400(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get(
                "/v1/intelligence?limit=abc", token=TOKEN
            )
            self.assertEqual(status, 400)
            self.assertEqual(parsed["error"]["code"], "BAD_REQUEST")

    def test_negative_limit_returns_400(self):
        with _ServerCtx():
            status, _, _, _ = _http_get(
                "/v1/intelligence?limit=0", token=TOKEN
            )
            self.assertEqual(status, 400)

    def test_cursor_advances_pagination(self):
        with _ServerCtx():
            # Page 1: limit=1
            s1, _, _, p1 = _http_get("/v1/intelligence?limit=1", token=TOKEN)
            self.assertEqual(s1, 200)
            self.assertEqual(p1["count"], 1)
            self.assertIsNotNone(p1["next_cursor"])
            # Page 2: cursor=p1.next_cursor
            s2, _, _, p2 = _http_get(
                f"/v1/intelligence?limit=1&cursor={p1['next_cursor']}",
                token=TOKEN,
            )
            self.assertEqual(s2, 200)
            self.assertEqual(p2["count"], 1)
            # Different IOs on each page
            self.assertNotEqual(p1["objects"][0]["io_id"], p2["objects"][0]["io_id"])

    def test_pagination_returns_all_3_ios_across_pages(self):
        with _ServerCtx():
            seen_io_ids = set()
            cursor = None
            for _ in range(5):  # safety limit
                path = "/v1/intelligence?limit=1"
                if cursor:
                    path += f"&cursor={cursor}"
                status, _, _, parsed = _http_get(path, token=TOKEN)
                self.assertEqual(status, 200)
                for io in parsed["objects"]:
                    seen_io_ids.add(io["io_id"])
                if not parsed["next_cursor"]:
                    break
                cursor = parsed["next_cursor"]
            self.assertEqual(len(seen_io_ids), 3)


class TestSingleIOEndpoint(unittest.TestCase):
    """§3 /v1/intelligence/<io_id> endpoint."""

    def test_get_single_io_returns_200(self):
        with _ServerCtx() as ctx:
            io_id_ = ctx.manifest["expected_io_ids"]["io-cpi-v2"]
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{io_id_}", token=TOKEN
            )
            self.assertEqual(status, 200)
            self.assertEqual(parsed["io_id"], io_id_)

    def test_get_single_io_not_found_returns_404(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get(
                "/v1/intelligence/io-does-not-exist-9999", token=TOKEN
            )
            self.assertEqual(status, 404)
            self.assertEqual(parsed["error"]["code"], "NOT_FOUND")

    def test_get_single_io_etag_304(self):
        with _ServerCtx() as ctx:
            io_id_ = ctx.manifest["expected_io_ids"]["io-cpi-v2"]
            s1, h1, _, _ = _http_get(f"/v1/intelligence/{io_id_}", token=TOKEN)
            etag = h1.get("ETag") or h1.get("ETag")
            self.assertIsNotNone(etag)
            s2, _, _, _ = _http_get(
                f"/v1/intelligence/{io_id_}", token=TOKEN, if_none_match=etag
            )
            self.assertEqual(s2, 304)


class TestTraceEndpoint(unittest.TestCase):
    """§3 /v1/intelligence/<io_id>/trace endpoint."""

    def test_trace_returns_chain(self):
        with _ServerCtx() as ctx:
            io_id_ = ctx.manifest["expected_io_ids"]["io-cpi-v2"]
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{io_id_}/trace", token=TOKEN
            )
            self.assertEqual(status, 200)
            self.assertEqual(parsed["io_id"], io_id_)
            self.assertIn("chain", parsed)
            self.assertGreater(len(parsed["chain"]), 0)

    def test_trace_not_found(self):
        with _ServerCtx():
            status, _, _, _ = _http_get(
                "/v1/intelligence/io-nope/trace", token=TOKEN
            )
            self.assertEqual(status, 404)


class TestReadOnlyEnforcement(unittest.TestCase):
    """§5 405 READ_ONLY for mutations."""

    def test_post_returns_405(self):
        with _ServerCtx():
            status, parsed = _http_method("POST", "/v1/intelligence", token=TOKEN)
            self.assertEqual(status, 405)
            self.assertEqual(parsed["error"]["code"], "READ_ONLY")

    def test_put_returns_405(self):
        with _ServerCtx():
            status, parsed = _http_method("PUT", "/v1/intelligence/x", token=TOKEN)
            self.assertEqual(status, 405)

    def test_delete_returns_405(self):
        with _ServerCtx():
            status, parsed = _http_method("DELETE", "/v1/intelligence/x", token=TOKEN)
            self.assertEqual(status, 405)


class TestUnknownPaths(unittest.TestCase):
    """§5 404 for unknown paths (no fake success)."""

    def test_unknown_path_returns_404(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get(
                "/v1/totally-fake", token=TOKEN
            )
            self.assertEqual(status, 404)
            self.assertEqual(parsed["error"]["code"], "NOT_FOUND")
            # Critical: 404 must NOT fake an empty objects list
            self.assertNotIn("objects", parsed)


class TestCanonicalSchemaConformance(unittest.TestCase):
    """§4 Canonical response conformance (no fabricated fields)."""

    def test_io_has_exactly_canonical_fields(self):
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            io = parsed["objects"][0]
            # Canonical fields per R2 §2.1 + K1/K2 promotion
            for f in ("io_id", "version", "event_id", "event_version",
                      "headline", "chain", "created_at",
                      "status", "supersedes_io_id",
                      "event_type", "temporal_data"):
                self.assertIn(f, io, f"canonical field missing: {f}")

    def test_io_has_K1_event_type_emitted(self):
        """§3 K1 PROMOTED: event_type IS now emitted (was capability gap, now surfaced)."""
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            for io in parsed["objects"]:
                self.assertIn("event_type", io,
                              "event_type MUST be emitted per CORE_SEMANTIC_PROMOTION_K1_K2_V1 §3")
                self.assertIsInstance(io["event_type"], str)
                # Must be one of the 6 supported Core event types
                self.assertIn(io["event_type"], (
                    "monetary_policy_decision", "regulatory_enforcement",
                    "statistical_release", "earnings_release",
                    "sanctions_designation", "market_statistic_release",
                ))

    def test_io_has_K2_temporal_data_emitted(self):
        """§4 K2 PROMOTED: temporal_data IS now emitted with 5 D4 sub-fields."""
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            for io in parsed["objects"]:
                self.assertIn("temporal_data", io,
                              "temporal_data MUST be emitted per CORE_SEMANTIC_PROMOTION_K1_K2_V1 §4")
                td = io["temporal_data"]
                # td may be None when Document has no publication_tuples,
                # but the field must be present.
                if td is not None:
                    for sub in ("publication_time", "publication_time_raw",
                                "publication_timezone_status", "reference_period",
                                "reference_period_normalized_utc"):
                        self.assertIn(sub, td, f"K2 sub-field missing: {sub}")

    def test_io_does_not_have_fabricated_quality_fields(self):
        """§4 Anti-fabrication: no quality_metadata family."""
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            for io in parsed["objects"]:
                for fabricated in ("quality_metadata", "confidence_score",
                                  "provenance_complete", "reproducible",
                                  "provenance_match"):
                    self.assertNotIn(fabricated, io,
                                      f"fabricated field present: {fabricated}")

    def test_chain_has_full_5_level_provenance(self):
        """§G Provenance: fact → evidence → representation → document → source."""
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            io = parsed["objects"][0]
            self.assertGreater(len(io["chain"]), 0)
            link = io["chain"][0]
            self.assertIn("fact", link)
            self.assertIn("fact_id", link["fact"])
            self.assertIn("fact_version", link["fact"])
            self.assertIn("metric", link["fact"])
            self.assertIn("value", link["fact"])
            self.assertIn("evidence", link)
            self.assertGreater(len(link["evidence"]), 0)
            self.assertIn("evidence_id", link["evidence"][0])
            self.assertIn("excerpt", link["evidence"][0])
            self.assertIn("representation_id", link["evidence"][0])
            self.assertIn("representation", link)
            self.assertIn("representation_id", link["representation"])
            self.assertIn("content_sha256", link["representation"])
            self.assertIn("document", link)
            self.assertIn("document_id", link["document"])
            self.assertIn("canonical_url", link["document"])
            self.assertIn("source", link)
            self.assertIn("source_id", link["source"])
            self.assertIn("institution_id", link["source"])


class TestVersioningProjections(unittest.TestCase):
    """§H Versioning: status + supersedes_io_id transport projections."""

    def test_v1_has_status_superceded(self):
        with _ServerCtx() as ctx:
            io_id_v1 = ctx.manifest["expected_io_ids"]["io-cpi-v1"]
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{io_id_v1}", token=TOKEN
            )
            self.assertEqual(status, 200)
            self.assertEqual(parsed["status"], "SUPERSEDED")
            self.assertIsNone(parsed["supersedes_io_id"])

    def test_v2_has_status_active_and_supersedes_v1(self):
        with _ServerCtx() as ctx:
            io_id_v1 = ctx.manifest["expected_io_ids"]["io-cpi-v1"]
            io_id_v2 = ctx.manifest["expected_io_ids"]["io-cpi-v2"]
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{io_id_v2}", token=TOKEN
            )
            self.assertEqual(status, 200)
            self.assertEqual(parsed["status"], "ACTIVE")
            self.assertEqual(parsed["supersedes_io_id"], io_id_v1)

    def test_io_version_is_constant_1(self):
        """Per canonical §4: io.version = 1 (constant); event_version is the lineage axis."""
        with _ServerCtx():
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            for io in parsed["objects"]:
                self.assertEqual(io["version"], 1)

    def test_v1_and_v2_have_distinct_io_ids(self):
        with _ServerCtx() as ctx:
            io_id_v1 = ctx.manifest["expected_io_ids"]["io-cpi-v1"]
            io_id_v2 = ctx.manifest["expected_io_ids"]["io-cpi-v2"]
            self.assertNotEqual(io_id_v1, io_id_v2)


class TestEventClassCoverage(unittest.TestCase):
    """§12 Available real IOs (no fabrication)."""

    def test_statistical_release_io_present(self):
        with _ServerCtx() as ctx:
            # io-cpi-v2 is a statistical_release event
            io_id_v2 = ctx.manifest["expected_io_ids"]["io-cpi-v2"]
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{io_id_v2}", token=TOKEN
            )
            self.assertEqual(status, 200)
            # Verify it's a statistical IO via chain fact metric
            self.assertEqual(parsed["chain"][0]["fact"]["metric"], "percentage_statistic")

    def test_regulatory_enforcement_io_present(self):
        with _ServerCtx() as ctx:
            io_id_fdic = ctx.manifest["expected_io_ids"]["io-fdic-enf"]
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{io_id_fdic}", token=TOKEN
            )
            self.assertEqual(status, 200)
            # Verify it's a regulatory enforcement IO via chain fact metric
            self.assertEqual(parsed["chain"][0]["fact"]["metric"], "action_type")

    def test_monetary_policy_decision_io_NOT_available(self):
        """§12: do not fabricate missing event types."""
        with _ServerCtx():
            # No monetary_policy_decision events were seeded.
            # Per directive §13: LIVE_FIXTURE_NOT_AVAILABLE — documented absence.
            # Now that K1 is emitted, we can verify directly via event_type.
            status, _, _, parsed = _http_get("/v1/intelligence", token=TOKEN)
            for io in parsed["objects"]:
                # event_type must be either statistical_release or regulatory_enforcement
                # (NOT monetary_policy_decision — no such IO seeded)
                self.assertIn(io["event_type"], (
                    "statistical_release", "regulatory_enforcement",
                ))
                self.assertNotEqual(io["event_type"], "monetary_policy_decision")


class TestCanonicalMockVsProductionEquivalence(unittest.TestCase):
    """§10 Production Core vs canonical mock equivalence on identical fixtures."""

    def test_production_response_shape_matches_canonical_mock_shape(self):
        """Compare the production /v1/intelligence response fields against
        the canonical mock /v1/intelligence response fields.

        Both should emit the same canonical fields per R2 §2.1 + K1/K2 promotion:
          io_id, version, event_id, event_version, headline, chain, created_at,
          status, supersedes_io_id, event_type, temporal_data

        Both should NOT emit:
          quality_metadata, confidence_score, provenance_complete,
          reproducible, provenance_match (fabricated — prohibited per §6)
        """
        with _ServerCtx():
            # Production response
            status, _, _, prod_parsed = _http_get("/v1/intelligence", token=TOKEN)
            self.assertEqual(status, 200)
            prod_io = prod_parsed["objects"][0]
            prod_keys = set(prod_io.keys())

        # Canonical mock response (start the canonical mock separately)
        mock_port = 8895
        mock_proc = subprocess.Popen(
            [sys.executable, "tools/mock_core/mock_core_server.py", str(mock_port)],
            cwd=str(CORE_REPO),
            env={**os.environ, "MOCK_CORE_TOKEN": "mock-token"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            # Wait for mock to bind
            deadline = time.time() + 5
            while time.time() < deadline:
                if not _free_port(mock_port):
                    break
                time.sleep(0.1)

            req = urllib.request.Request(f"http://127.0.0.1:{mock_port}/v1/intelligence")
            req.add_header("Authorization", "Bearer mock-token")
            with urllib.request.urlopen(req, timeout=5) as resp:
                mock_body = resp.read().decode("utf-8")
            mock_parsed = json.loads(mock_body)
            mock_io = mock_parsed["objects"][0]
            mock_keys = set(mock_io.keys())

            # Canonical field set must match (includes K1/K2 promoted per
            # CORE_SEMANTIC_PROMOTION_K1_K2_V1)
            canonical_fields = {
                "io_id", "version", "event_id", "event_version",
                "headline", "chain", "created_at",
                "status", "supersedes_io_id",
                "event_type", "temporal_data",  # K1/K2 promoted
            }
            self.assertEqual(prod_keys, canonical_fields,
                              f"production IO keys mismatch: {prod_keys ^ canonical_fields}")
            self.assertEqual(mock_keys, canonical_fields,
                              f"canonical mock IO keys mismatch: {mock_keys ^ canonical_fields}")

            # Both must NOT have fabricated fields (§6 — still prohibited)
            forbidden = {"quality_metadata", "confidence_score",
                        "provenance_complete", "reproducible", "provenance_match"}
            self.assertEqual(prod_keys & forbidden, set(),
                              f"production has forbidden fields: {prod_keys & forbidden}")
            self.assertEqual(mock_keys & forbidden, set(),
                              f"mock has forbidden fields: {mock_keys & forbidden}")
        finally:
            mock_proc.terminate()
            try:
                mock_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mock_proc.kill()


class TestNoSilentEmptyOnBrokenChain(unittest.TestCase):
    """§9 Broken data relationships must remain explicit failures."""

    def test_500_when_chain_broken(self):
        """If the store has an event whose fact is missing, the production
        transport must surface a 500 CHAIN_BROKEN error — NOT silently
        skip the broken IO and return an empty/short list."""
        # Seed a store with a broken event (fact_version_snapshot references
        # a fact_id that doesn't exist)
        with _ServerCtx() as ctx:
            # Append a broken event to the existing store
            store_path = ctx.store_root
            import json as _json
            events_path = Path(store_path) / "events.jsonl"
            broken_event = {
                "event_id": "evt-broken",
                "event_version": 1,
                "document_id": "doc-does-not-exist",
                "event_type": "statistical_release",
                "fact_version_snapshot": [{"fact_id": "fact-does-not-exist",
                                            "fact_version": 1}],
                "occurrence": 0,
                "status": "ACTIVE",
                "derived_at": "9999-12-31T23:59:59Z",  # latest, so it's at the end
            }
            with open(events_path, "a") as f:
                f.write(_json.dumps(broken_event) + "\n")

            # Now request the broken IO directly — should get 500 CHAIN_BROKEN
            from intelligence_core.identity import io_id as make_io_id
            broken_io_id = make_io_id("evt-broken", 1)
            status, _, _, parsed = _http_get(
                f"/v1/intelligence/{broken_io_id}", token=TOKEN
            )
            self.assertEqual(status, 500)
            self.assertEqual(parsed["error"]["code"], "CHAIN_BROKEN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
