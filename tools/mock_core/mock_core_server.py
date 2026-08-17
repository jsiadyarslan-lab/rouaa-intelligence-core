"""CANONICAL MOCK CORE SERVER — the approved /v1 contract (R2 + K1/K2 promotion).

LOCAL-ONLY development/test reference. Payload discipline (R2 4/7 +
CORE_SEMANTIC_PROMOTION_K1_K2_V1):
  item = REAL Core IntelligenceObject shape (delivery.py, verbatim fields)
       + {status, supersedes_io_id} — transport projection of REAL store
         state (event status / prior event version) per versioning §8.
       + event_type — K1, copied directly from Event.event_type (§3 — no inference).
       + temporal_data — K2, projected from Document.publication_tuples per D4
         (§4-5 — null = NOT_APPLICABLE / UNKNOWN, no fabrication).
  NOTHING else. No quality/confidence fields (exist nowhere in Core).

Run: python tools/mock_core/mock_core_server.py [port]   (MOCK_CORE_TOKEN env; default dev-local-token)
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("MOCK_CORE_TOKEN", "dev-local-token")


def _chain(fact_id, metric, value, ev_id, rep_sha, doc_id, url, src, inst):
    return [{"fact": {"fact_id": fact_id, "fact_version": 1, "metric": metric, "value": value},
             "evidence": [{"evidence_id": ev_id, "excerpt": "...issued 15 orders...", "representation_id": "rep-" + rep_sha[:8]}],
             "representation": {"representation_id": "rep-" + rep_sha[:8], "content_sha256": rep_sha},
             "document": {"document_id": doc_id, "canonical_url": url},
             "source": {"source_id": src, "institution_id": inst}}]


def _temporal(publication_time, publication_time_raw, timezone_status,
              reference_period=None, reference_period_raw=None,
              reference_period_timezone_status=None,
              publication_normalization_basis="EXPLICIT_SOURCE_TIMEZONE",
              publication_provenance_source="rss_pubdate",
              reference_period_normalization_basis=None,
              reference_period_provenance_source=None,
              publication_timestamp_semantics="publication",
              reference_period_timestamp_semantics=None,
              extra_tuples=None):
    """K2 projection per D4 — ALL 6 D4 fields + multiplicity preserved.

    Per CORE_K2_D4_FIDELITY_CLOSURE_V1: all 6 D4 TemporalTuple fields preserved.
    Per CORE_K2_D4_MULTIPLICITY_CLOSURE_V1: temporal_tuples[] preserves ALL
    D4 tuples (including conflicting dates, multiple semantics, etc.).

    null = NOT_APPLICABLE / UNKNOWN (§5 — no fabrication).
    """
    # Build temporal_tuples[] — ALL tuples in order
    tuples = []

    # Always include the publication tuple
    tuples.append({
        "original_value": publication_time_raw,
        "timezone_status": timezone_status,
        "normalized_utc": publication_time,
        "normalization_basis": publication_normalization_basis,
        "timestamp_semantics": publication_timestamp_semantics,
        "provenance_source": publication_provenance_source,
    })

    # Include reference_period tuple if present
    if reference_period is not None:
        tuples.append({
            "original_value": reference_period_raw or reference_period,
            "timezone_status": reference_period_timezone_status or "DATE_ONLY",
            "normalized_utc": reference_period,
            "normalization_basis": reference_period_normalization_basis or "NONE",
            "timestamp_semantics": reference_period_timestamp_semantics or "reporting_period",
            "provenance_source": reference_period_provenance_source or "rendered_text",
        })

    # Include any extra tuples (for multiplicity tests — conflicting dates, etc.)
    if extra_tuples:
        tuples.extend(extra_tuples)

    return {
        # FULL D4 CARDINALITY — all tuples preserved (per MULTIPLICITY_CLOSURE):
        "temporal_tuples": tuples,
        # Publication tuple — backward-compat (K1/K2 promotion):
        "publication_time": publication_time,
        "publication_time_raw": publication_time_raw,
        "publication_timezone_status": timezone_status,
        # Publication tuple — D4-faithful (added per closure — was dropped):
        "publication_normalization_basis": publication_normalization_basis,
        "publication_timestamp_semantics": publication_timestamp_semantics,
        "publication_provenance_source": publication_provenance_source,
        # Reference period tuple — backward-compat (K1/K2 promotion):
        "reference_period": reference_period,
        "reference_period_normalized_utc": reference_period,
        # Reference period tuple — D4-faithful (added per closure — was dropped):
        "reference_period_raw": reference_period_raw,
        "reference_period_timezone_status": reference_period_timezone_status,
        "reference_period_normalization_basis": reference_period_normalization_basis,
        "reference_period_timestamp_semantics": reference_period_timestamp_semantics,
        "reference_period_provenance_source": reference_period_provenance_source,
    }


CPI_URL = "https://www.istat.it/en/press-release/consumer-prices-july-2026"
FDIC_URL = "https://www.fdic.gov/news/press-releases/2026/fdic-publishes-june-enforcement-actions"
FIXTURES = [
    # ISTAT CPI v1 — SUPERSEDED. statistical_release with reference_period (D4 §9 distinction).
    # MULTIPLICITY TEST: this fixture has 3 D4 tuples:
    #   1. publication (from RSS pubdate)
    #   2. reporting_period (statistical reference period — July 2026)
    #   3. document_date (from HTML <time> element — slightly different from RSS)
    # Per CORE_K2_D4_MULTIPLICITY_CLOSURE_V1: all 3 tuples must be preserved
    # in temporal_tuples[] without collapse.
    {"io_id": "io-cpi-v1", "version": 1, "event_id": "evt-cpi", "event_version": 1,
     "status": "SUPERSEDED", "supersedes_io_id": None,
     "headline": "ISTAT Statistical Release",
     "chain": _chain("fact-cpi-mom", "percentage_statistic", "+0.3", "evi-cpi-1",
                     "a" * 64, "doc-istat-cpi", CPI_URL, "ISTAT", "INST-istat-001"),
     "created_at": "2026-08-12T08:00:58Z",
     "event_type": "statistical_release",
     "temporal_data": _temporal(
         publication_time="2026-08-12T08:00:58Z",
         publication_time_raw="Wed, 12 Aug 2026 08:00:58 +0000",
         timezone_status="EXPLICIT_ZONE",
         publication_normalization_basis="EXPLICIT_SOURCE_TIMEZONE",
         publication_provenance_source="rss_pubdate",
         publication_timestamp_semantics="publication",
         # Statistical release reference_period — distinct from publication_time (D4 §9).
         # Full D4 tuple preserved per CORE_K2_D4_FIDELITY_CLOSURE_V1.
         reference_period="2026-07",
         reference_period_raw="2026-07",
         reference_period_timezone_status="DATE_ONLY",
         reference_period_normalization_basis="NONE",
         reference_period_timestamp_semantics="reporting_period",
         reference_period_provenance_source="rendered_text",
         # EXTRA TUPLE: document_date from HTML <time> element (conflicting with RSS pubdate).
         # This tests D4 multiplicity — both dates must be preserved without collapse.
         extra_tuples=[{
             "original_value": "2026-08-12T10:00:00+02:00",
             "timezone_status": "EXPLICIT_OFFSET",
             "normalized_utc": "2026-08-12T08:00:00Z",
             "normalization_basis": "SOURCE_DOCUMENT_METADATA",
             "timestamp_semantics": "document_date",
             "provenance_source": "html_time_attr",
         }])},
    # ISTAT CPI v2 — ACTIVE (correction of v1). Same statistical_release, +0.4.
    {"io_id": "io-cpi-v2", "version": 1, "event_id": "evt-cpi", "event_version": 2,
     "status": "ACTIVE", "supersedes_io_id": "io-cpi-v1",
     "headline": "ISTAT Statistical Release",
     "chain": _chain("fact-cpi-mom", "percentage_statistic", "+0.4", "evi-cpi-2",
                     "c" * 64, "doc-istat-cpi", CPI_URL, "ISTAT", "INST-istat-001"),
     "created_at": "2026-08-13T08:00:00Z",
     "event_type": "statistical_release",
     "temporal_data": _temporal(
         publication_time="2026-08-13T08:00:00Z",
         publication_time_raw="Thu, 13 Aug 2026 10:00:00 +0200",
         timezone_status="EXPLICIT_OFFSET",
         publication_normalization_basis="EXPLICIT_SOURCE_TIMEZONE",
         publication_provenance_source="rss_pubdate",
         publication_timestamp_semantics="publication",
         reference_period="2026-07",
         reference_period_raw="2026-07",
         reference_period_timezone_status="DATE_ONLY",
         reference_period_normalization_basis="NONE",
         reference_period_timestamp_semantics="reporting_period",
         reference_period_provenance_source="rendered_text")},
    # FDIC enforcement — regulatory_enforcement. reference_period=null (per §12).
    {"io_id": "io-fdic-enf", "version": 1, "event_id": "evt-fdic", "event_version": 1,
     "status": "ACTIVE", "supersedes_io_id": None,
     "headline": "FDIC Regulatory Enforcement Action",
     "chain": _chain("fact-enf-1", "action_type", "consent order", "evi-enf-1",
                     "b" * 64, "doc-fdic-enf", FDIC_URL, "FDIC", "INST-fdic-001"),
     "created_at": "2026-07-31T00:00:00Z",
     "event_type": "regulatory_enforcement",
     "temporal_data": _temporal(
         publication_time="2026-07-31T00:00:00Z",
         publication_time_raw="Fri, 31 Jul 2026 00:00:00 +0000",
         timezone_status="EXPLICIT_ZONE",
         publication_normalization_basis="EXPLICIT_SOURCE_TIMEZONE",
         publication_provenance_source="rss_pubdate",
         publication_timestamp_semantics="publication",
         reference_period=None)},
]
BY_ID = {f["io_id"]: f for f in FIXTURES}
ETAGS = {f["io_id"]: 'W/"' + hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()[:16] + '"'
         for f in FIXTURES}


def _feed(cursor: str):
    ids = [f["io_id"] for f in FIXTURES]
    start = 0 if not cursor else (ids.index(cursor) + 1 if cursor in ids else len(ids))
    page = ids[start:start + 2]
    more = start + len(page) < len(ids)
    return {"objects": [dict(BY_ID[i]) for i in page],
            "next_cursor": page[-1] if (page and more) else None}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=None, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())

    def _authed(self):
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def do_GET(self):
        path = self.path.split("?")[0]
        q = self.path.split("?")[1] if "?" in self.path else ""
        params = dict(p.split("=", 1) for p in q.split("&") if "=" in p)
        if path == "/health":
            return self._send(200, {"status": "ok"})
        if not self._authed():
            return self._send(401, {"error": {"code": "UNAUTHORIZED", "message": "token required"}})
        if params.get("_force_status"):
            return self._send(int(params["_force_status"]),
                              {"error": {"code": "FORCED", "message": "drill"}})
        if path == "/v1/intelligence":
            feed_etag = 'W/"feed-v3"'
            if self.headers.get("If-None-Match") == feed_etag:
                return self._send(304, None, {"ETag": feed_etag})
            return self._send(200, _feed(params.get("cursor", "")), {"ETag": feed_etag})
        if path.startswith("/v1/intelligence/"):
            parts = [x for x in path.split("/") if x]
            if parts[-1] == "trace":
                obj = BY_ID.get(parts[-2])
                if not obj:
                    return self._send(404, {"error": {"code": "NOT_FOUND"}})
                return self._send(200, {"io_id": obj["io_id"], "chain": obj["chain"]})
            io_id = parts[-1]
            obj = BY_ID.get(io_id)
            if not obj:
                return self._send(404, {"error": {"code": "NOT_FOUND"}})
            if self.headers.get("If-None-Match") == ETAGS[io_id]:
                return self._send(304, None, {"ETag": ETAGS[io_id]})
            return self._send(200, obj, {"ETag": ETAGS[io_id]})
        return self._send(404, {"error": {"code": "NOT_FOUND"}})

    def do_POST(self):
        self._send(405, {"error": {"code": "READ_ONLY",
                                   "message": "products cannot mutate Core truth"}})

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"[canonical-mock-core] :{port}  (Authorization: Bearer <MOCK_CORE_TOKEN>)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
