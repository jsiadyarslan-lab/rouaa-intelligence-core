"""Phase 1 — Local contract server fixture for deterministic development.

Provides a mock Core server implementing the same read API as contract_api.py
but with hardcoded IntelligenceObject data from validated sources (FDIC, ISTAT, DFSA).

This allows the News adapter to be developed without Railway or live Core.

NO Core internals exposed. NO token required (local dev only).
"""
from __future__ import annotations
import json
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional


# ── Mock IntelligenceObject data ──

MOCK_OBJECTS = [
    {
        "io_id": "io_fdic_2026_001",
        "version": 1,
        "event_id": "evt_fdic_2026_001",
        "event_version": 1,
        "headline": "FDIC Regulatory Enforcement Action",
        "created_at": "2026-08-13T18:10:04Z",
        "institution_id": "INST-FDIC-US-1",
        "source_id": "SRC-FDIC-1",
        "event_type": "regulatory_enforcement",
        "document_ref": {
            "document_id": "DOC-FDIC-2026-001",
            "canonical_url": "https://www.fdic.gov/news/press-releases/2026/2026-001.html",
        },
        "chain": [
            {
                "fact": {
                    "fact_id": "FACT-FDIC-001",
                    "fact_version": 1,
                    "metric": "penalty_amount",
                    "value": "$1.5 million",
                },
                "evidence": [
                    {
                        "evidence_id": "EV-FDIC-001",
                        "excerpt": "agreed to pay a civil money penalty of $1.5 million",
                        "representation_id": "REP-FDIC-001",
                    }
                ],
                "representation": {
                    "representation_id": "REP-FDIC-001",
                    "content_sha256": "abc123def456",
                },
                "document": {
                    "document_id": "DOC-FDIC-2026-001",
                    "canonical_url": "https://www.fdic.gov/news/press-releases/2026/2026-001.html",
                },
                "source": {
                    "source_id": "SRC-FDIC-1",
                    "institution_id": "INST-FDIC-US-1",
                },
            }
        ],
        "quality_metadata": {
            "provenance_complete": True,
            "confidence_score": 0.85,
            "reproducible": True,
        },
    },
    {
        "io_id": "io_istat_2026_001",
        "version": 1,
        "event_id": "evt_istat_2026_001",
        "event_version": 1,
        "headline": "ISTAT Statistical Release",
        "created_at": "2026-08-13T08:00:58Z",
        "institution_id": "INST-ISTAT-IT-1",
        "source_id": "SRC-ISTAT-1",
        "event_type": "statistical_release",
        "document_ref": {
            "document_id": "DOC-ISTAT-2026-001",
            "canonical_url": "https://www.istat.it/en/archivio/2026-001",
        },
        "chain": [
            {
                "fact": {
                    "fact_id": "FACT-ISTAT-001",
                    "fact_version": 1,
                    "metric": "inflation_rate",
                    "value": "0.3%",
                },
                "evidence": [
                    {
                        "evidence_id": "EV-ISTAT-001",
                        "excerpt": "The consumer price index increased by 0.3%",
                        "representation_id": "REP-ISTAT-001",
                    }
                ],
                "representation": {
                    "representation_id": "REP-ISTAT-001",
                    "content_sha256": "def789ghi012",
                },
                "document": {
                    "document_id": "DOC-ISTAT-2026-001",
                    "canonical_url": "https://www.istat.it/en/archivio/2026-001",
                },
                "source": {
                    "source_id": "SRC-ISTAT-1",
                    "institution_id": "INST-ISTAT-IT-1",
                },
            }
        ],
        "quality_metadata": {
            "provenance_complete": True,
            "confidence_score": 0.85,
            "reproducible": True,
        },
    },
    {
        "io_id": "io_istat_2026_002",
        "version": 2,
        "event_id": "evt_istat_2026_001",
        "event_version": 2,
        "headline": "ISTAT Statistical Release (CORRECTED)",
        "created_at": "2026-08-13T10:00:00Z",
        "institution_id": "INST-ISTAT-IT-1",
        "source_id": "SRC-ISTAT-1",
        "event_type": "statistical_release",
        "document_ref": {
            "document_id": "DOC-ISTAT-2026-002",
            "canonical_url": "https://www.istat.it/en/archivio/2026-002",
        },
        "chain": [
            {
                "fact": {
                    "fact_id": "FACT-ISTAT-001",
                    "fact_version": 2,
                    "metric": "inflation_rate",
                    "value": "0.4%",
                    "supersedes": "FACT-ISTAT-001:v1",
                },
                "evidence": [
                    {
                        "evidence_id": "EV-ISTAT-002",
                        "excerpt": "The consumer price index increased by 0.4% (corrected)",
                        "representation_id": "REP-ISTAT-002",
                    }
                ],
                "representation": {
                    "representation_id": "REP-ISTAT-002",
                    "content_sha256": "xyz999abc888",
                },
                "document": {
                    "document_id": "DOC-ISTAT-2026-002",
                    "canonical_url": "https://www.istat.it/en/archivio/2026-002",
                },
                "source": {
                    "source_id": "SRC-ISTAT-1",
                    "institution_id": "INST-ISTAT-IT-1",
                },
            }
        ],
        "quality_metadata": {
            "provenance_complete": True,
            "confidence_score": 0.90,
            "reproducible": True,
        },
    },
    {
        "io_id": "io_dfsa_2026_001",
        "version": 1,
        "event_id": "evt_dfsa_2026_001",
        "event_version": 1,
        "headline": "DFSA Regulatory Enforcement Action",
        "created_at": "2026-08-14T12:00:00Z",
        "institution_id": "INST-DFSA-AE-1",
        "source_id": "SRC-DFSA-1",
        "event_type": "regulatory_enforcement",
        "document_ref": {
            "document_id": "DOC-DFSA-2026-001",
            "canonical_url": "https://www.dfsa.ae/en/News/2026-001",
        },
        "chain": [
            {
                "fact": {
                    "fact_id": "FACT-DFSA-001",
                    "fact_version": 1,
                    "metric": "penalty_amount",
                    "value": "AED 2.5 million",
                },
                "evidence": [
                    {
                        "evidence_id": "EV-DFSA-001",
                        "excerpt": "penalty of AED 2.5 million imposed",
                        "representation_id": "REP-DFSA-001",
                    }
                ],
                "representation": {
                    "representation_id": "REP-DFSA-001",
                    "content_sha256": "dfs456lmn789",
                },
                "document": {
                    "document_id": "DOC-DFSA-2026-001",
                    "canonical_url": "https://www.dfsa.ae/en/News/2026-001",
                },
                "source": {
                    "source_id": "SRC-DFSA-1",
                    "institution_id": "INST-DFSA-AE-1",
                },
            }
        ],
        "quality_metadata": {
            "provenance_complete": True,
            "confidence_score": 0.80,
            "reproducible": True,
        },
    },
]


def _compute_etag(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return '"' + hashlib.sha256(raw).hexdigest()[:16] + '"'


class MockContractHandler(BaseHTTPRequestHandler):
    """Mock HTTP handler — no auth (local dev only)."""

    def _send_json(self, status: int, body: dict, etag: Optional[str] = None):
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, code: str, message: str):
        self._send_json(status, {"error": {"code": code, "message": message}})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/v1/health":
            self._send_json(200, {"status": "ok"})
            return

        if path == "/api/v1/intelligence-objects":
            self._handle_list(params)
        elif path.startswith("/api/v1/intelligence-objects/"):
            io_id = path.split("/")[-1]
            self._handle_get_one(io_id)
        elif path == "/api/v1/fail/401":
            self._send_error(401, "UNAUTHORIZED", "Mock 401")
        elif path == "/api/v1/fail/500":
            self._send_error(500, "INTERNAL_ERROR", "Mock 500")
        elif path == "/api/v1/fail/timeout":
            # Simulate timeout by not responding (client should timeout)
            import time
            time.sleep(30)
        elif path == "/api/v1/fail/malformed":
            raw = b'{"io_id": "broken", "version": "not-a-number"'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/v1/fail/empty":
            self._send_json(200, {"objects": [], "next_cursor": None, "count": 0})
        else:
            self._send_error(404, "NOT_FOUND", f"Unknown path: {path}")

    def _handle_list(self, params: dict):
        limit = min(int(params.get("limit", ["50"])[0]), 200)
        cursor = params.get("cursor", [None])[0]
        since = params.get("since", [None])[0]

        objects = MOCK_OBJECTS[:]

        if since:
            objects = [o for o in objects if o.get("created_at", "") >= since]

        if cursor:
            objects = [o for o in objects if o.get("created_at", "") > cursor]

        objects.sort(key=lambda o: o.get("created_at", ""))

        page = objects[:limit]
        next_cursor = objects[limit].get("created_at") if len(objects) > limit else None

        response = {
            "objects": page,
            "next_cursor": next_cursor,
            "count": len(page),
        }
        etag = _compute_etag(response)

        if_none_match = self.headers.get("If-None-Match", "")
        if if_none_match == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        self._send_json(200, response, etag=etag)

    def _handle_get_one(self, io_id: str):
        for obj in MOCK_OBJECTS:
            if obj["io_id"] == io_id:
                etag = _compute_etag(obj)
                self._send_json(200, obj, etag=etag)
                return
        self._send_error(404, "NOT_FOUND", f"IntelligenceObject not found: {io_id}")

    def do_POST(self):
        # Simulate 429 rate limit for specific test path
        if self.path == "/api/v1/fail/429":
            self._send_error(429, "RATE_LIMITED", "Too many requests")
        else:
            self._send_error(405, "METHOD_NOT_ALLOWED", "POST not supported")

    def log_message(self, format, *args):
        pass


def serve(port: int = 9101):
    """Start the mock contract server for local development."""
    server = HTTPServer(("127.0.0.1", port), MockContractHandler)
    print(f"Mock Core Contract API listening on 127.0.0.1:{port}")
    print(f"  Mock data: {len(MOCK_OBJECTS)} IntelligenceObjects")
    print(f"  Sources: FDIC, ISTAT (v1+v2 corrected), DFSA")
    print(f"  Failure simulation: /api/v1/fail/401, /fail/500, /fail/timeout, /fail/malformed, /fail/empty, /fail/429")
    server.serve_forever()


if __name__ == "__main__":
    serve()
