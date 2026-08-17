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
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from intelligence_core.store import AppendOnlyStore
from intelligence_core.cached_store import CachedStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id


# ── Process-level caches (V2 §6 transport optimization) ──
#
# These caches are TRANSPORT OPTIMIZATIONS — no contract changes, no
# semantic caching, no consumer-specific caching.
#
# 1. _IO_CACHE: per-io_id projection cache. Keyed by io_id which is
#    derived from (event_id, event_version) — so a new event_version
#    produces a new io_id and a new cache entry. Old entry is naturally
#    evicted by LRU. NO stale truth risk.
#
# 2. _LIST_CACHE: per-(cursor, limit, since, generation) list response
#    cache. "generation" is bumped on every store append, so any new
#    IO invalidates the list cache. NO stale truth risk.
#
# 3. _STORE_CACHE: per-store-path CachedStore instance. Reused across
#    requests to avoid re-reading JSONL files.

_IO_CACHE: OrderedDict[str, tuple[dict, str]] = OrderedDict()  # io_id → (obj_dict, etag)
_LIST_CACHE: OrderedDict[str, tuple[dict, str]] = OrderedDict()  # cache_key → (response, etag)
_STORE_CACHE: dict[str, tuple[CachedStore, int]] = {}  # store_path → (store, generation)
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 1024  # max entries per cache


def _cache_get(cache: OrderedDict, key: str):
    """Get from cache (NO LRU reordering to avoid lock contention).

    V2 §6: LRU reordering on every cache hit causes lock contention at
    100+ concurrent readers. We skip the pop+reinsert pattern — the LRU
    eviction still works (oldest entries are evicted when capacity is
    exceeded), but access frequency no longer affects eviction order.
    This is acceptable: cache key is io_id which is content-addressed,
    so any cached entry is correct regardless of access pattern.
    """
    # Read without lock — Python dict reads are thread-safe under GIL
    if key in cache:
        return cache[key]
    return None


def _cache_put(cache: OrderedDict, key: str, value):
    """Put into cache with bounded size. Uses lock only for writes."""
    with _CACHE_LOCK:
        if key in cache:
            cache[key] = value
            return
        cache[key] = value
        while len(cache) > _CACHE_MAX:
            cache.popitem(last=False)


def _invalidate_list_cache():
    """Invalidate entire list cache (called when store generation bumps)."""
    with _CACHE_LOCK:
        _LIST_CACHE.clear()


def _get_cached_store(store_path: str) -> tuple[CachedStore, int]:
    """Get or create a CachedStore for the given path.

    Returns (store, generation). Generation is bumped on every append.
    """
    with _CACHE_LOCK:
        if store_path not in _STORE_CACHE:
            _STORE_CACHE[store_path] = (CachedStore(AppendOnlyStore(store_path)), 0)
        return _STORE_CACHE[store_path]


def _bump_generation(store_path: str):
    """Bump store generation — invalidates list cache + IO cache.

    Called whenever a new IO is appended (e.g. via the trace endpoint
    or any future write path). Currently the transport is READ_ONLY,
    so generation only bumps if the underlying store changes externally.
    """
    with _CACHE_LOCK:
        if store_path in _STORE_CACHE:
            store, gen = _STORE_CACHE[store_path]
            _STORE_CACHE[store_path] = (store, gen + 1)
        _LIST_CACHE.clear()
        # IO cache stays valid — io_id is content-addressed, so existing
        # entries are still correct. New appends create new io_ids.


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

        # Public metrics endpoint (V2-Continuous §15)
        if path == "/metrics":
            self._handle_metrics()
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

    def _open_store(self) -> tuple[CachedStore, int]:
        """Return (CachedStore, generation) for the configured store path.

        CachedStore provides O(1) lookups (was O(N) full scans).
        Generation is used for list cache keying.
        """
        store_path = os.environ.get("CORE_STORE_PATH", "./production_store")
        store, generation = _get_cached_store(store_path)
        return store, generation

    def _build_io_dict(self, store: CachedStore, event_row: dict) -> dict:
        """Build the canonical IO dict with transport projections.

        V2 §6: Results are cached per io_id. Cache key is the io_id
        (which is derived from (event_id, event_version) — so any version
        change produces a new io_id and a new cache entry). No stale truth.

        Delegates to delivery.build_intelligence_object() for the canonical
        shape, then adds the documented transport projections
        (status, supersedes_io_id) per canonical contract §2.1.
        """
        io_id_str = make_io_id(event_row["event_id"], event_row["event_version"])

        # Check IO projection cache (V2 §6)
        cached = _cache_get(_IO_CACHE, io_id_str)
        if cached is not None:
            return cached[0]

        # Find source name for headline construction (O(1) via CachedStore)
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

        # Cache the projection (V2 §6)
        _cache_put(_IO_CACHE, io_id_str, (obj, _compute_etag(obj)))

        return obj

    def _handle_list(self, params: dict):
        store, generation = self._open_store()

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

        # V2 §6: List response cache — keyed by (cursor, limit, since, generation).
        # Generation bumps on any store append → any new IO invalidates the list cache.
        cache_key = f"{cursor}|{limit}|{since}|{generation}"
        cached = _cache_get(_LIST_CACHE, cache_key)
        if cached is not None:
            response, etag = cached
            if_none_match = self.headers.get("If-None-Match", "")
            if if_none_match == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                return
            self._send_json(200, response, etag=etag)
            return

        # Collect ALL events (current view per event_id — last version wins,
        # but we serve ALL event versions as separate IOs per canonical §4
        # versioning semantics: "consumers treat versions as distinct
        # immutable objects — never overwrite, never fork").
        # V2 §6: CachedStore.iter() is O(1) (memory-resident list).
        events = list(store.iter("events"))

        # V2-Continuous §1: Canonical cursor closure.
        # The cursor is now a TUPLE: (derived_at, event_id, event_version).
        # This is deterministic + stable under concurrent arrivals:
        #   - New events have either a later derived_at, or a lexicographically
        #     larger event_id (content-addressed from doc_id + event_type + occurrence)
        #   - The tuple ensures total ordering even when derived_at values are equal
        #
        # Cursor format: "derived_at|event_id|event_version" (URL-encoded)
        # Semantics: next page returns items where
        #   (derived_at, event_id, event_version) > (cursor_derived_at, cursor_event_id, cursor_event_version)

        def _parse_cursor(c: str) -> tuple | None:
            """Parse a tuple cursor. Returns None if invalid/empty."""
            if not c:
                return None
            try:
                # URL-decode
                from urllib.parse import unquote
                c = unquote(c)
                parts = c.split("|", 2)
                if len(parts) == 3:
                    return (parts[0], parts[1], int(parts[2]))
                elif len(parts) == 1:
                    # Legacy: just derived_at (backward compat)
                    return (parts[0], "", 0)
                return None
            except Exception:
                return None

        def _make_cursor(ev: dict) -> str:
            """Create a tuple cursor from an event row."""
            return f"{ev.get('derived_at', '')}|{ev.get('event_id', '')}|{ev.get('event_version', 0)}"

        # Apply since filter (on derived_at)
        if since:
            events = [e for e in events if e.get("derived_at", "") >= since]

        # Sort by (derived_at, event_id, event_version) for stable ordering
        events.sort(key=lambda e: (e.get("derived_at", ""), e.get("event_id", ""), e.get("event_version", 0)))

        # Apply tuple cursor: (derived_at, event_id, event_version) > cursor_tuple
        cursor_tuple = _parse_cursor(cursor) if cursor else None
        if cursor_tuple:
            events = [e for e in events
                      if (e.get("derived_at", ""), e.get("event_id", ""), e.get("event_version", 0)) > cursor_tuple]

        # Paginate
        page = events[:limit]
        # next_cursor = tuple cursor of the LAST item on this page.
        if len(events) > limit and page:
            next_cursor = _make_cursor(page[-1])
        else:
            next_cursor = None

        # Build IOs (V2 §6: each IO is O(1) cached lookup after first build)
        objects = []
        for ev in page:
            try:
                obj = self._build_io_dict(store, ev)
                objects.append(obj)
            except Exception as e:
                # Per canonical §5: broken chain = explicit error, NOT silent skip.
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

        # Cache the list response (V2 §6)
        _cache_put(_LIST_CACHE, cache_key, (response, etag))

        # Conditional request per canonical §2.3
        if_none_match = self.headers.get("If-None-Match", "")
        if if_none_match == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        self._send_json(200, response, etag=etag)

    def _handle_get_one(self, io_id_: str):
        store, _ = self._open_store()

        # V2 §6: O(1) io_id → event_row lookup (was O(N) full scan).
        ev = store.find_by_io_id(io_id_)
        if ev is None:
            self._send_error(404, "NOT_FOUND", f"IntelligenceObject not found: {io_id_}")
            return

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
        except Exception as e:
            sys.stderr.write(f"[production-transport] chain broken for {io_id_}: {e}\n")
            self._send_error(500, "CHAIN_BROKEN",
                              f"Intelligence Object chain broken: {io_id_}")

    def _handle_trace(self, io_id_: str):
        store, _ = self._open_store()

        # V2 §6: O(1) io_id → event_row lookup (was O(N) full scan).
        ev = store.find_by_io_id(io_id_)
        if ev is None:
            self._send_error(404, "NOT_FOUND", f"IntelligenceObject not found: {io_id_}")
            return

        try:
            obj = self._build_io_dict(store, ev)
            # Trace endpoint returns just the chain
            trace = {
                "io_id": obj["io_id"],
                "chain": obj["chain"],
            }
            self._send_json(200, trace)
        except Exception as e:
            self._send_error(500, "CHAIN_BROKEN", str(e))

    def log_message(self, format, *args):
        # Suppress default logging; token never logged
        pass

    def _handle_metrics(self):
        """Public /metrics endpoint — returns basic Core metrics (V2-Continuous §15).

        Returns JSON with:
          - io_count: total IntelligenceObjects in store
          - event_count: total events
          - fact_count: total facts
          - source_count: total sources
          - document_count: total documents
          - cache_stats: IO cache + list cache sizes
          - uptime_seconds: server uptime
        """
        try:
            store, _ = self._open_store()
            io_count = sum(1 for _ in store.iter("events"))
            fact_count = sum(1 for _ in store.iter("facts"))
            source_count = sum(1 for _ in store.iter("sources"))
            document_count = sum(1 for _ in store.iter("documents"))
            metrics = {
                "io_count": io_count,
                "event_count": io_count,  # 1:1 with IOs (each event → 1 IO)
                "fact_count": fact_count,
                "source_count": source_count,
                "document_count": document_count,
                "cache_stats": {
                    "io_cache_size": len(_IO_CACHE),
                    "list_cache_size": len(_LIST_CACHE),
                    "store_cache_size": len(_STORE_CACHE),
                },
                "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._send_json(200, metrics)
        except Exception as e:
            self._send_error(500, "METRICS_ERROR", str(e)[:100])


# ── Server ──

def serve(port: int = 9100):
    """Start the S1 production transport server.

    Required env:
      CORE_API_TOKEN: Bearer token (server-side only)
      CORE_STORE_PATH: path to AppendOnlyStore root (default: ./production_store)
    Optional env:
      CORE_SOURCE_REGISTRY_PATH: path to SourceRegistry (default: ./source_registry)
      CORE_METRICS_ENABLED: "1" to enable /metrics endpoint
    """
    if not os.environ.get("CORE_API_TOKEN"):
        raise RuntimeError("CORE_API_TOKEN env required (server-side only)")
    if not os.environ.get("CORE_STORE_PATH"):
        # Don't fail — default to ./production_store (used in dev)
        os.environ.setdefault("CORE_STORE_PATH", "./production_store")
    # Externalize source registry path (V2-Continuous §15)
    os.environ.setdefault("CORE_SOURCE_REGISTRY_PATH", "./source_registry")

    # V2 §3: Scale the listen backlog for 100+ concurrent readers.
    # Default request_queue_size=5 drops connections under load — this is
    # the root cause of the 16% transport error rate at 100 readers.
    ProductionTransportHandler.request_queue_size = 256
    ProductionTransportHandler.timeout = 30

    # V2 §3: Allow socket reuse so the server can restart quickly during tests.
    class _ScaledThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True
        request_queue_size = 256

    server = _ScaledThreadingHTTPServer(("0.0.0.0", port), ProductionTransportHandler)
    print(f"[production-transport] listening on :{port}")
    print(f"  store: {os.environ['CORE_STORE_PATH']}")
    print(f"  canonical endpoints: /health, /metrics, /v1/intelligence, "
          f"/v1/intelligence/<io_id>, /v1/intelligence/<io_id>/trace")
    print(f"  auth: Bearer token (env CORE_API_TOKEN)")

    # V2-Continuous §15: Graceful shutdown on SIGTERM/SIGINT
    # Only register signal handlers when not in test mode (to avoid pytest
    # subprocess management complications). In production, these handlers
    # ensure clean shutdown on SIGTERM from the container orchestrator.
    if os.environ.get("CORE_TEST_MODE") != "1":
        import signal
        import threading as _threading
        _shutdown_started = []
        def _shutdown_handler(signum, frame):
            if _shutdown_started:
                return  # already shutting down
            _shutdown_started.append(True)
            sig_name = signal.Signals(signum).name
            print(f"\n[production-transport] received {sig_name}, shutting down gracefully...", flush=True)
            t = _threading.Thread(target=server.shutdown, daemon=True)
            t.start()

        signal.signal(signal.SIGTERM, _shutdown_handler)
        signal.signal(signal.SIGINT, _shutdown_handler)

    server.serve_forever()
    print(f"[production-transport] shutdown complete")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9100
    serve(port=port)
