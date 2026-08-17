"""S1 Production Core Transport — canonical /v1/intelligence HTTP server.

Per ROUAA_CORE_INTELLIGENCE_CONTRACT_V1 §1 (R2 restoration):
  Production implementation: was NOT_IMPLEMENTED (staging item S1 under Gate-G).
  This module IMPLEMENTS S1 — the production transport layer.

Architecture (directive §2):
  HTTP route
     ↓
  existing Core delivery logic (delivery.build_intelligence_object)
     ↓
  canonical IntelligenceObject (contracts.IntelligenceObject.to_dict)
     ↓
  canonical serializer (this module adds transport projections only)

Transport projections per canonical §2.1:
  - status: derived from Event.status (ACTIVE | SUPERSEDED)
  - supersedes_io_id: derived from event_version lineage
  (These are NOT fabricated — they are documented projections of real
   store state per canonical contract §2.1.)

Anti-fabrication per canonical §3:
  - NO event_type (architectural capability gap — exists in Event store
    row, NOT surfaced in IO emission)
  - NO temporal_data (architectural capability gap — D4 tuples live on
    Document, NOT surfaced in IO emission)
  - NO quality_metadata / confidence_score / provenance_complete /
    reproducible / provenance_match (fabricated contract fields)

Endpoints:
  GET /health                          → 200 {status:"ok"}       (public)
  GET /v1/intelligence                  → 200 {objects, next_cursor} + ETag
  GET /v1/intelligence/<io_id>          → 200 IO or 404 NOT_FOUND
  POST/PUT/PATCH/DELETE                → 405 READ_ONLY

Auth: Bearer token via env CORE_API_TOKEN (server-side only).
Pagination: cursor + limit (default 50, capped at 200).
ETag/304: supported (canonical §2.3).
Errors: {error:{code, message}} (401/404/405/429/5xx).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from intelligence_core.store import AppendOnlyStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id


# ── Auth ──

def _check_auth(headers: dict) -> bool:
    """Validate Bearer token against env CORE_API_TOKEN."""
    token = os.environ.get("CORE_API_TOKEN", "")
    if not token:
        return False
    auth = headers.get("authorization", "") or headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[len("Bearer "):] == token


# ── ETag ──

def _compute_etag(data: dict) -> str:
    """Compute ETag from response data (canonical §2.3)."""
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return 'W/"' + hashlib.sha256(raw).hexdigest()[:16] + '"'


# ── Transport projections (canonical §2.1) ──

def _derive_status(event_row: dict) -> str:
    """Project Event.status to IO transport field."""
    return event_row.get("status", "ACTIVE")


def _derive_supersedes_io_id(store: AppendOnlyStore, event_row: dict) -> str | None:
    """Project event_version lineage to IO transport field.

    If this event_version > 1, the prior version's io_id is the supersedes_io_id.
    """
    if event_row["event_version"] <= 1:
        return None
    prior_event_versions = [
        e for e in store.event_versions(event_row["event_id"])
        if e["event_version"] < event_row["event_version"]
    ]
    if not prior_event_versions:
        return None
    prior = max(prior_event_versions, key=lambda e: e["event_version"])
    return make_io_id(prior["event_id"], prior["event_version"])


# ── Handler ──

class ProductionTransportHandler(BaseHTTPRequestHandler):
    """HTTP handler for the S1 production /v1/intelligence transport."""

    # ── Low-level send helpers ──

    def _send_json(self, status: int, body: dict, etag: str | None = None,
                   extra_headers: dict | None = None):
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if etag:
            self.send_header("ETag", etag)
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, code: str, message: str):
        self._send_json(status, {"error": {"code": code, "message": message}})

    # ── Route dispatch ──

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Public health endpoint
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        # All other endpoints require auth
        if not _check_auth({"authorization": self.headers.get("Authorization", "")}):
            self._send_error(401, "UNAUTHORIZED", "Missing or invalid token")
            return

        # Canonical endpoints
        if path == "/v1/intelligence":
            self._handle_list(params)
        elif path.startswith("/v1/intelligence/"):
            parts = [p for p in path[len("/v1/intelligence/"):].split("/") if p]
            if not parts:
                self._send_error(404, "NOT_FOUND", "io_id required")
                return
            io_id_ = parts[0]
            if len(parts) == 2 and parts[1] == "trace":
                self._handle_trace(io_id_)
            elif len(parts) == 1:
                self._handle_get_one(io_id_)
            else:
                self._send_error(404, "NOT_FOUND", f"Unknown path: {path}")
        else:
            self._send_error(404, "NOT_FOUND", f"Unknown path: {path}")

    def do_POST(self):
        self._send_error(405, "READ_ONLY", "products cannot mutate Core truth")

    def do_PUT(self):
        self._send_error(405, "READ_ONLY", "products cannot mutate Core truth")

    def do_PATCH(self):
        self._send_error(405, "READ_ONLY", "products cannot mutate Core truth")

    def do_DELETE(self):
        self._send_error(405, "READ_ONLY", "products cannot mutate Core truth")

    # ── Canonical handlers ──

    def _open_store(self) -> AppendOnlyStore:
        store_path = os.environ.get("CORE_STORE_PATH", "./production_store")
        return AppendOnlyStore(store_path)

    def _build_io_dict(self, store: AppendOnlyStore, event_row: dict) -> dict:
        """Build the canonical IO dict with transport projections.

        Delegates to delivery.build_intelligence_object() for the canonical
        shape, then adds the documented transport projections
        (status, supersedes_io_id) per canonical contract §2.1.

        No fabricated fields. No capability-gap fields (event_type,
        temporal_data) — those remain absent per canonical §3.
        """
        # Find source name for headline construction
        doc = store.latest_by_id("documents", "document_id").get(event_row.get("document_id", ""))
        src = None
        if doc:
            src = store.latest_by_id("sources", "source_id").get(doc.get("source_id", ""))
        source_name = (src or {}).get("source_id", "Unknown")

        # Delegate to existing canonical delivery logic
        io = build_intelligence_object(
            store, event_row,
            source_name=source_name,
            created_at=event_row.get("derived_at", ""),
        )
        obj = io.to_dict()

        # Add transport projections per canonical §2.1
        obj["status"] = _derive_status(event_row)
        obj["supersedes_io_id"] = _derive_supersedes_io_id(store, event_row)

        return obj

    def _handle_list(self, params: dict):
        store = self._open_store()

        # Pagination params
        try:
            limit = min(int(params.get("limit", ["50"])[0]), 200)
        except ValueError:
            self._send_error(400, "BAD_REQUEST", "limit must be an integer")
            return
        if limit < 1:
            self._send_error(400, "BAD_REQUEST", "limit must be >= 1")
            return
        cursor = params.get("cursor", [None])[0]
        since = params.get("since", [None])[0]

        # Collect ALL events (current view per event_id — last version wins,
        # but we serve ALL event versions as separate IOs per canonical §4
        # versioning semantics: "consumers treat versions as distinct
        # immutable objects — never overwrite, never fork").
        events = list(store.iter("events"))

        # Apply since filter (on derived_at)
        if since:
            events = [e for e in events if e.get("derived_at", "") >= since]

        # Sort by (derived_at, event_id, event_version) for stable ordering
        events.sort(key=lambda e: (e.get("derived_at", ""), e.get("event_id", ""), e.get("event_version", 0)))

        # Apply cursor: derived_at > cursor
        if cursor:
            events = [e for e in events if e.get("derived_at", "") > cursor]

        # Paginate
        page = events[:limit]
        # next_cursor = derived_at of the LAST item on this page.
        # The next page filters derived_at > next_cursor, so it skips
        # everything we've already returned. Use page[-1] (the last item
        # actually returned), NOT events[limit] (the first item of the
        # next page) — those are different when there's a next page.
        if len(events) > limit and page:
            next_cursor = page[-1].get("derived_at")
        else:
            next_cursor = None

        # Build IOs
        objects = []
        for ev in page:
            try:
                obj = self._build_io_dict(store, ev)
                objects.append(obj)
            except Exception as e:
                # Per canonical §5: broken chain = explicit error, NOT silent skip.
                # We log to stderr and surface a 500 to the client.
                sys.stderr.write(f"[production-transport] chain broken for "
                                 f"{ev.get('event_id','?')} v{ev.get('event_version','?')}: {e}\n")
                self._send_error(500, "CHAIN_BROKEN",
                                  f"Intelligence Object chain broken for "
                                  f"{ev.get('event_id','?')} v{ev.get('event_version','?')}")
                return

        response = {
            "objects": objects,
            "next_cursor": next_cursor,
            "count": len(objects),
        }
        etag = _compute_etag(response)

        # Conditional request per canonical §2.3
        if_none_match = self.headers.get("If-None-Match", "")
        if if_none_match == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        self._send_json(200, response, etag=etag)

    def _handle_get_one(self, io_id_: str):
        store = self._open_store()

        # Find the event whose (event_id, event_version) produces this io_id
        for ev in store.iter("events"):
            expected_id = make_io_id(ev["event_id"], ev["event_version"])
            if expected_id == io_id_:
                try:
                    obj = self._build_io_dict(store, ev)
                    etag = _compute_etag(obj)
                    # Conditional request
                    if_none_match = self.headers.get("If-None-Match", "")
                    if if_none_match == etag:
                        self.send_response(304)
                        self.send_header("ETag", etag)
                        self.end_headers()
                        return
                    self._send_json(200, obj, etag=etag)
                    return
                except Exception as e:
                    sys.stderr.write(f"[production-transport] chain broken for {io_id_}: {e}\n")
                    self._send_error(500, "CHAIN_BROKEN",
                                      f"Intelligence Object chain broken: {io_id_}")
                    return

        self._send_error(404, "NOT_FOUND", f"IntelligenceObject not found: {io_id_}")

    def _handle_trace(self, io_id_: str):
        store = self._open_store()

        for ev in store.iter("events"):
            expected_id = make_io_id(ev["event_id"], ev["event_version"])
            if expected_id == io_id_:
                try:
                    obj = self._build_io_dict(store, ev)
                    # Trace endpoint returns just the chain
                    trace = {
                        "io_id": obj["io_id"],
                        "chain": obj["chain"],
                    }
                    self._send_json(200, trace)
                    return
                except Exception as e:
                    self._send_error(500, "CHAIN_BROKEN", str(e))
                    return

        self._send_error(404, "NOT_FOUND", f"IntelligenceObject not found: {io_id_}")

    def log_message(self, format, *args):
        # Suppress default logging; token never logged
        pass


# ── Server ──

def serve(port: int = 9100):
    """Start the S1 production transport server.

    Required env:
      CORE_API_TOKEN: Bearer token (server-side only)
      CORE_STORE_PATH: path to AppendOnlyStore root (default: ./production_store)
    """
    if not os.environ.get("CORE_API_TOKEN"):
        raise RuntimeError("CORE_API_TOKEN env required (server-side only)")
    if not os.environ.get("CORE_STORE_PATH"):
        # Don't fail — default to ./production_store (used in dev)
        os.environ.setdefault("CORE_STORE_PATH", "./production_store")

    server = ThreadingHTTPServer(("0.0.0.0", port), ProductionTransportHandler)
    print(f"[production-transport] listening on :{port}")
    print(f"  store: {os.environ['CORE_STORE_PATH']}")
    print(f"  canonical endpoints: /health, /v1/intelligence, "
          f"/v1/intelligence/<io_id>, /v1/intelligence/<io_id>/trace")
    print(f"  auth: Bearer token (env CORE_API_TOKEN)")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9100
    serve(port=port)
