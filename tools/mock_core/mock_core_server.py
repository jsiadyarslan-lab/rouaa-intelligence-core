"""CANONICAL MOCK CORE SERVER — the approved /v1 contract, exactly (R2).

LOCAL-ONLY development/test reference. Payload discipline (R2 4/7):
  item = REAL Core IntelligenceObject shape (delivery.py, verbatim fields)
       + {status, supersedes_io_id} — a documented transport projection of
         REAL store state (event status / prior event version) required by
         the architecture's versioning semantics (8).
  NOTHING else. No quality/confidence fields (exist nowhere in Core).
  temporal_data / event_type: deliberately ABSENT — recorded as
  ARCHITECTURAL CAPABILITY GAPS pending a separate Core contract decision.

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


CPI_URL = "https://www.istat.it/en/press-release/consumer-prices-july-2026"
FDIC_URL = "https://www.fdic.gov/news/press-releases/2026/fdic-publishes-june-enforcement-actions"
FIXTURES = [
    {"io_id": "io-cpi-v1", "version": 1, "event_id": "evt-cpi", "event_version": 1,
     "status": "SUPERSEDED", "supersedes_io_id": None,
     "headline": "ISTAT Statistical Release",
     "chain": _chain("fact-cpi-mom", "percentage_statistic", "+0.3", "evi-cpi-1",
                     "a" * 64, "doc-istat-cpi", CPI_URL, "ISTAT", "INST-istat-001"),
     "created_at": "2026-08-12T08:00:58Z"},
    {"io_id": "io-cpi-v2", "version": 1, "event_id": "evt-cpi", "event_version": 2,
     "status": "ACTIVE", "supersedes_io_id": "io-cpi-v1",
     "headline": "ISTAT Statistical Release",
     "chain": _chain("fact-cpi-mom", "percentage_statistic", "+0.4", "evi-cpi-2",
                     "c" * 64, "doc-istat-cpi", CPI_URL, "ISTAT", "INST-istat-001"),
     "created_at": "2026-08-12T08:00:58Z"},
    {"io_id": "io-fdic-enf", "version": 1, "event_id": "evt-fdic", "event_version": 1,
     "status": "ACTIVE", "supersedes_io_id": None,
     "headline": "FDIC Regulatory Enforcement Action",
     "chain": _chain("fact-enf-1", "action_type", "consent order", "evi-enf-1",
                     "b" * 64, "doc-fdic-enf", FDIC_URL, "FDIC", "INST-fdic-001"),
     "created_at": "2026-07-31T00:00:00Z"},
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
