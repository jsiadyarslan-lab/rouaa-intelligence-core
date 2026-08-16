"""D9 — append-only store. JSONL collections + content-addressed blobs.

No update/delete APIs exist by design: state changes are NEW rows (D2).
Current view = last row per logical id (max version where versioned).
"""
from __future__ import annotations
import json
import os
from pathlib import Path

COLLECTIONS = ("institutions", "sources", "documents", "representations",
               "retrieval_events", "facts", "events", "evidence",
               "intelligence_objects", "deliveries", "audit")


class AppendOnlyStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(exist_ok=True)

    def _path(self, collection: str) -> Path:
        if collection not in COLLECTIONS:
            raise ValueError(f"unknown collection {collection}")
        return self.root / f"{collection}.jsonl"

    def append(self, collection: str, record: dict) -> dict:
        with open(self._path(collection), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def iter(self, collection: str):
        p = self._path(collection)
        if not p.exists():
            return
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def write_blob(self, sha256: str, data: bytes) -> str:
        loc = self.root / "blobs" / sha256
        if not loc.exists():          # idempotent: same content stored once
            loc.write_bytes(data)
        return str(loc)

    def read_blob(self, sha256: str) -> bytes:
        return (self.root / "blobs" / sha256).read_bytes()

    # --- current views -------------------------------------------------
    def latest_by_id(self, collection: str, id_field: str) -> dict:
        latest: dict = {}
        for row in self.iter(collection):
            latest[row[id_field]] = row          # last row wins (append-only)
        return latest

    def fact_versions(self, fact_id: str) -> list:
        rows = [r for r in self.iter("facts") if r["fact_id"] == fact_id]
        return sorted(rows, key=lambda r: r["fact_version"])

    def current_fact(self, fact_id: str) -> dict | None:
        vs = self.fact_versions(fact_id)
        return vs[-1] if vs else None

    def event_versions(self, event_id: str) -> list:
        rows = [r for r in self.iter("events") if r["event_id"] == event_id]
        return sorted(rows, key=lambda r: r["event_version"])

    def current_event(self, event_id: str) -> dict | None:
        vs = self.event_versions(event_id)
        return vs[-1] if vs else None

    def fact_row(self, fact_id: str, fact_version: int) -> dict | None:
        for r in self.fact_versions(fact_id):
            if r["fact_version"] == fact_version:
                return r
        return None

    def audit(self, type_: str, payload: dict) -> dict:
        return self.append("audit", {"type": type_, **payload})
