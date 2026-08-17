"""V2 §6 — CachedStore: in-memory indices for O(1) lookups.

Wraps AppendOnlyStore with:
  - Pre-built {id: row} dicts per collection (built once on first access)
  - O(1) latest_by_id() lookups (was O(N) full scan)
  - O(1) fact_row() lookups by (fact_id, fact_version)
  - O(1) event_versions() lookup by event_id
  - Cached iter() — list materialized once, refreshed on append
  - Append() invalidates only the affected collection's cache

Semantics preserved EXACTLY:
  - Append-only behavior unchanged (writes go to underlying store)
  - last-row-wins semantics for latest_by_id unchanged
  - fact_version / event_version ordering unchanged
  - blob storage unchanged

This is a TRANSPORT OPTIMIZATION — no contract changes, no semantic caching,
no consumer-specific caching. Cache invalidation respects event/version changes
naturally: a new (event_id, event_version) pair produces a new io_id, which is
a different cache key.
"""
from __future__ import annotations

import threading
from typing import Iterator
from .store import AppendOnlyStore, COLLECTIONS


class CachedStore:
    """AppendOnlyStore wrapper with in-memory indices for O(1) lookups.

    All read methods return identical results to AppendOnlyStore.
    All write methods delegate to the underlying store + invalidate the
    relevant cache entry.
    """

    def __init__(self, store: AppendOnlyStore):
        self._store = store
        self._lock = threading.RLock()
        # Per-collection cache:
        #   _cache[coll] = list of ALL rows (in append order)
        #   _by_id[coll] = {id_field_value: last_row} (last-wins)
        self._cache: dict[str, list[dict]] = {}
        self._by_id: dict[str, dict[str, dict]] = {}
        # Specialized indices
        self._fact_versions: dict[str, list[dict]] = {}  # fact_id → versions sorted asc
        self._event_versions: dict[str, list[dict]] = {}  # event_id → versions sorted asc
        self._io_id_index: dict[str, dict] = {}  # io_id → event_row
        self._loaded: set[str] = set()

    # ── Load / refresh a collection ──

    def _load(self, collection: str):
        """Materialize a collection into memory (idempotent)."""
        if collection in self._loaded:
            return
        with self._lock:
            if collection in self._loaded:  # double-check
                return
            rows = list(self._store.iter(collection))
            self._cache[collection] = rows
            # Build latest_by_id index
            id_field = self._id_field(collection)
            if id_field:
                by_id = {}
                for row in rows:
                    if id_field in row:
                        by_id[row[id_field]] = row  # last wins
                self._by_id[collection] = by_id
            # Specialized indices
            if collection == "facts":
                self._fact_versions = {}
                for r in rows:
                    self._fact_versions.setdefault(r["fact_id"], []).append(r)
                for fid in self._fact_versions:
                    self._fact_versions[fid].sort(key=lambda r: r["fact_version"])
            elif collection == "events":
                self._event_versions = {}
                from .identity import io_id as make_io_id
                self._io_id_index = {}
                for r in rows:
                    self._event_versions.setdefault(r["event_id"], []).append(r)
                    # Index by io_id for O(1) single-IO lookups
                    try:
                        ioid = make_io_id(r["event_id"], r["event_version"])
                        self._io_id_index[ioid] = r
                    except Exception:
                        pass
                for eid in self._event_versions:
                    self._event_versions[eid].sort(key=lambda r: r["event_version"])
            self._loaded.add(collection)

    @staticmethod
    def _id_field(collection: str) -> str | None:
        return {
            "institutions": "institution_id",
            "sources": "source_id",
            "documents": "document_id",
            "representations": "representation_id",
            "retrieval_events": "retrieval_event_id",
            "facts": "fact_id",
            "events": "event_id",
            "evidence": "evidence_id",
            "intelligence_objects": "io_id",
            "deliveries": "delivery_id",
            "audit": None,  # no single id
        }.get(collection)

    # ── Read API (semantics identical to AppendOnlyStore) ──

    def iter(self, collection: str) -> Iterator[dict]:
        self._load(collection)
        for row in self._cache.get(collection, []):
            yield row

    def latest_by_id(self, collection: str, id_field: str) -> dict:
        """O(1) lookup — was O(N) full scan per call.

        NOTE: id_field parameter is kept for API compat with AppendOnlyStore,
        but the index is keyed by the collection's canonical id field
        (see _id_field). Callers using non-canonical id fields will fall back
        to a linear scan.
        """
        canonical = self._id_field(collection)
        if canonical == id_field:
            self._load(collection)
            return dict(self._by_id.get(collection, {}))
        # Fallback: linear scan with the requested id_field
        result = {}
        for row in self.iter(collection):
            if id_field in row:
                result[row[id_field]] = row
        return result

    def fact_versions(self, fact_id: str) -> list:
        self._load("facts")
        return list(self._fact_versions.get(fact_id, []))

    def current_fact(self, fact_id: str) -> dict | None:
        vs = self.fact_versions(fact_id)
        return vs[-1] if vs else None

    def fact_row(self, fact_id: str, fact_version: int) -> dict | None:
        """O(log V) lookup — was O(V) scan."""
        vs = self.fact_versions(fact_id)
        # binary search by fact_version
        lo, hi = 0, len(vs)
        while lo < hi:
            mid = (lo + hi) // 2
            if vs[mid]["fact_version"] < fact_version:
                lo = mid + 1
            else:
                hi = mid
        if lo < len(vs) and vs[lo]["fact_version"] == fact_version:
            return vs[lo]
        return None

    def event_versions(self, event_id: str) -> list:
        self._load("events")
        return list(self._event_versions.get(event_id, []))

    def current_event(self, event_id: str) -> dict | None:
        vs = self.event_versions(event_id)
        return vs[-1] if vs else None

    def find_by_io_id(self, io_id: str) -> dict | None:
        """O(1) lookup of event_row by io_id — was O(N) scan in _handle_get_one."""
        self._load("events")
        return self._io_id_index.get(io_id)

    # ── Write API (delegates + invalidates) ──

    def append(self, collection: str, record: dict) -> dict:
        result = self._store.append(collection, record)
        with self._lock:
            # Invalidate this collection's cache (will rebuild on next read)
            if collection in self._loaded:
                self._loaded.discard(collection)
                self._cache.pop(collection, None)
                self._by_id.pop(collection, None)
                if collection == "facts":
                    self._fact_versions = {}
                elif collection == "events":
                    self._event_versions = {}
                    self._io_id_index = {}
        return result

    def write_blob(self, sha256: str, data: bytes) -> str:
        # Blob writes don't affect JSONL collection caches
        return self._store.write_blob(sha256, data)

    def read_blob(self, sha256: str) -> bytes:
        return self._store.read_blob(sha256)

    def audit(self, type_: str, payload: dict) -> dict:
        return self.append("audit", {"type": type_, **payload})

    @property
    def root(self):
        return self._store.root
