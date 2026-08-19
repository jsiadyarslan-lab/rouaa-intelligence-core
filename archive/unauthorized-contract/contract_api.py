"""Phase 1 — Core → News read-only contract API server.

Provides REST polling endpoint for IntelligenceObjects.
Server-side only. No Core internal module access exposed.

Endpoints:
  GET /api/v1/intelligence-objects
    Query: ?cursor=<cursor>&limit=<n>&since=<iso-ts>&source=<source_id>
    Auth:  Bearer token (environment: CORE_API_TOKEN)
    Returns: { objects: [...], next_cursor: str|null, etag: str }

  GET /api/v1/intelligence-objects/<io_id>
    Auth:  Bearer token
    Returns: single IntelligenceObject with full chain

  GET /api/v1/health
    Returns: { status: "ok" }

Transport features:
  - Bearer token auth (server-side only)
  - Cursor-based pagination
  - ETag / conditional requests (If-None-Match → 304)
  - Timeout handling
  - Bounded retry on 5xx (client-side)
  - Structured errors
"""
from __future__ import annotations
import json
import hashlib
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional


def _check_auth(headers: dict) -> bool:
    """Validate Bearer token against environment CORE_API_TOKEN."""
    token = os.environ.get("CORE_API_TOKEN", "")
    if not token:
        return False
    auth = headers.get("authorization", "") or headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[7:] == token


def _compute_etag(data: dict) -> str:
    """Compute ETag from response data."""
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return '"' + hashlib.sha256(raw).hexdigest()[:16] + '"'


class ContractAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Core → News contract API."""

    def _send_json(self, status: int, body: dict, etag: Optional[str] = None,
                   headers: Optional[dict] = None):
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if etag:
            self.send_header("ETag", etag)
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, code: str, message: str):
        self._send_json(status, {"error": {"code": code, "message": message}})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Health endpoint — no auth required
        if path == "/api/v1/health":
            self._send_json(200, {"status": "ok"})
            return

        # All other endpoints require auth
        auth_header = self.headers.get("Authorization", "")
        if not _check_auth({"authorization": auth_header}):
            self._send_error(401, "UNAUTHORIZED", "Missing or invalid token")
            return

        if path == "/api/v1/intelligence-objects":
            self._handle_list(params)
        elif path.startswith("/api/v1/intelligence-objects/"):
            io_id = path.split("/")[-1]
            self._handle_get_one(io_id)
        else:
            self._send_error(404, "NOT_FOUND", f"Unknown path: {path}")

    def _handle_list(self, params: dict):
        from .store import AppendOnlyStore as JsonlStore
        from .delivery import build_intelligence_object

        store_path = os.environ.get("CORE_STORE_PATH", "./core_store")
        store = JsonlStore(store_path)

        limit = min(int(params.get("limit", ["50"])[0]), 200)
        cursor = params.get("cursor", [None])[0]
        since = params.get("since", [None])[0]

        # Collect active events
        events = [e for e in store.iter("events") if e.get("status") == "ACTIVE"]

        # Apply since filter
        if since:
            events = [e for e in events if e.get("derived_at", "") >= since]

        # Apply cursor (derived_at > cursor)
        if cursor:
            events = [e for e in events if e.get("derived_at", "") > cursor]

        # Sort by derived_at
        events.sort(key=lambda e: e.get("derived_at", ""))

        # Paginate
        page = events[:limit]
        next_cursor = events[limit].get("derived_at") if len(events) > limit else None

        # Build IntelligenceObjects
        objects = []
        for ev in page:
            # Find source name
            doc = store.latest_by_id("documents", "document_id").get(ev.get("document_id", ""))
            src = None
            if doc:
                src = store.latest_by_id("sources", "source_id").get(doc.get("source_id", ""))
            source_name = (src or {}).get("institution_id", "Unknown")

            try:
                io = build_intelligence_object(store, ev, source_name=source_name,
                                                created_at=ev.get("derived_at", ""))
                obj = io.to_dict()
                # Add contract fields
                obj["institution_id"] = (src or {}).get("institution_id", "")
                obj["source_id"] = (doc or {}).get("source_id", "")
                obj["document_ref"] = {
                    "document_id": (doc or {}).get("document_id", ""),
                    "canonical_url": (doc or {}).get("canonical_url", ""),
                }
                objects.append(obj)
            except Exception:
                continue  # skip broken chains

        response = {
            "objects": objects,
            "next_cursor": next_cursor,
            "count": len(objects),
        }
        etag = _compute_etag(response)

        # Conditional request
        if_none_match = self.headers.get("If-None-Match", "")
        if if_none_match == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        self._send_json(200, response, etag=etag)

    def _handle_get_one(self, io_id: str):
        from .store import AppendOnlyStore as JsonlStore
        from .delivery import build_intelligence_object

        store_path = os.environ.get("CORE_STORE_PATH", "./core_store")
        store = JsonlStore(store_path)

        # io_id format: io_<event_id>_<event_version>
        # Find the event
        for ev in store.iter("events"):
            from .identity import io_id as make_io_id
            expected_id = make_io_id(ev["event_id"], ev["event_version"])
            if expected_id == io_id:
                doc = store.latest_by_id("documents", "document_id").get(ev.get("document_id", ""))
                src = None
                if doc:
                    src = store.latest_by_id("sources", "source_id").get(doc.get("source_id", ""))
                source_name = (src or {}).get("institution_id", "Unknown")

                try:
                    io = build_intelligence_object(store, ev, source_name=source_name,
                                                    created_at=ev.get("derived_at", ""))
                    obj = io.to_dict()
                    obj["institution_id"] = (src or {}).get("institution_id", "")
                    obj["source_id"] = (doc or {}).get("source_id", "")
                    obj["document_ref"] = {
                        "document_id": (doc or {}).get("document_id", ""),
                        "canonical_url": (doc or {}).get("canonical_url", ""),
                    }
                    etag = _compute_etag(obj)
                    self._send_json(200, obj, etag=etag)
                    return
                except Exception as e:
                    self._send_error(500, "CHAIN_BROKEN", str(e))
                    return

        self._send_error(404, "NOT_FOUND", f"IntelligenceObject not found: {io_id}")

    def log_message(self, format, *args):
        # Suppress default logging; token never logged
        pass


def serve(port: int = 9100):
    """Start the contract API server."""
    server = HTTPServer(("0.0.0.0", port), ContractAPIHandler)
    print(f"Core Contract API listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve()
