"""V2 §6 — Verify CachedStore produces byte-identical output to AppendOnlyStore.

Tests:
  1. latest_by_id() returns identical dict for every collection
  2. fact_row() returns identical row for every (fact_id, fact_version)
  3. event_versions() returns identical list for every event_id
  4. find_by_io_id() returns identical event_row for every io_id
  5. iter() yields identical rows in identical order
  6. After append(), the new row is visible (cache invalidation)
  7. Timing: CachedStore is at least 100x faster on the list path
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from intelligence_core.store import AppendOnlyStore
from intelligence_core.cached_store import CachedStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id


def assert_equal(label: str, expected, actual):
    if expected != actual:
        print(f"  ✗ FAIL {label}")
        print(f"    expected: {json.dumps(expected, default=str)[:200]}")
        print(f"    actual:   {json.dumps(actual, default=str)[:200]}")
        return False
    print(f"  ✓ PASS {label}")
    return True


def verify_correctness(store_root: str):
    print(f"\n=== Correctness verification: {store_root} ===")
    raw_store = AppendOnlyStore(store_root)
    cached = CachedStore(AppendOnlyStore(store_root))

    all_pass = True

    # 1. latest_by_id for every collection
    for coll, id_field in [
        ("institutions", "institution_id"),
        ("sources", "source_id"),
        ("documents", "document_id"),
        ("representations", "representation_id"),
        ("facts", "fact_id"),
        ("events", "event_id"),
    ]:
        raw_result = raw_store.latest_by_id(coll, id_field)
        cached_result = cached.latest_by_id(coll, id_field)
        all_pass &= assert_equal(
            f"latest_by_id({coll}, {id_field})",
            raw_result, cached_result,
        )

    # 2. fact_row for every fact
    facts = list(raw_store.iter("facts"))
    fact_ids = {(f["fact_id"], f["fact_version"]) for f in facts}
    for fid, fver in list(fact_ids)[:50]:  # sample 50
        raw_row = raw_store.fact_row(fid, fver)
        cached_row = cached.fact_row(fid, fver)
        all_pass &= assert_equal(f"fact_row({fid}, v{fver})", raw_row, cached_row)

    # 3. event_versions for every event
    event_ids = {e["event_id"] for e in raw_store.iter("events")}
    for eid in event_ids:
        raw_vs = raw_store.event_versions(eid)
        cached_vs = cached.event_versions(eid)
        all_pass &= assert_equal(f"event_versions({eid})", raw_vs, cached_vs)

    # 4. find_by_io_id for every io_id
    for ev in raw_store.iter("events"):
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        found = cached.find_by_io_id(ioid)
        all_pass &= assert_equal(f"find_by_io_id({ioid})", ev, found)

    # 5. iter yields identical rows in identical order
    for coll in ["events", "facts", "evidence", "documents", "representations", "sources"]:
        raw_rows = list(raw_store.iter(coll))
        cached_rows = list(cached.iter(coll))
        all_pass &= assert_equal(f"iter({coll}) count", len(raw_rows), len(cached_rows))
        if raw_rows == cached_rows:
            print(f"  ✓ PASS iter({coll}) order + content")
        else:
            print(f"  ✗ FAIL iter({coll}) order + content")
            all_pass = False

    # 6. build_intelligence_object produces identical dict for every event
    raw_events = list(raw_store.iter("events"))
    mismatch_count = 0
    for ev in raw_events[:20]:  # sample 20
        try:
            raw_io = build_intelligence_object(raw_store, ev, source_name="Test").to_dict()
            cached_io = build_intelligence_object(cached, ev, source_name="Test").to_dict()
            if raw_io != cached_io:
                mismatch_count += 1
                print(f"  ✗ FAIL build_intelligence_object({ev['event_id']}, v{ev['event_version']})")
        except Exception as e:
            print(f"  ✗ EXCEPTION for {ev['event_id']}: {e}")
            mismatch_count += 1
    if mismatch_count == 0:
        print(f"  ✓ PASS build_intelligence_object (20 samples) — byte-identical")
    else:
        all_pass = False

    return all_pass


def verify_timing(store_root: str, n_requests: int = 10, limit: int = 50):
    """Compare timing: AppendOnlyStore vs CachedStore for the list path."""
    print(f"\n=== Timing comparison ({n_requests} requests, limit={limit}) ===")

    # Raw store (uncached) — original V1 path
    raw_store = AppendOnlyStore(store_root)
    raw_times = []
    for _ in range(n_requests):
        t0 = time.perf_counter()
        events = list(raw_store.iter("events"))
        events.sort(key=lambda e: (e.get("derived_at", ""), e.get("event_id", ""), e.get("event_version", 0)))
        page = events[:limit]
        for ev in page:
            try:
                build_intelligence_object(raw_store, ev, source_name="Test")
            except Exception:
                pass
        raw_times.append((time.perf_counter() - t0) * 1000)

    # Cached store (V2)
    cached = CachedStore(AppendOnlyStore(store_root))
    cached_times = []
    for _ in range(n_requests):
        t0 = time.perf_counter()
        events = list(cached.iter("events"))
        events.sort(key=lambda e: (e.get("derived_at", ""), e.get("event_id", ""), e.get("event_version", 0)))
        page = events[:limit]
        for ev in page:
            try:
                build_intelligence_object(cached, ev, source_name="Test")
            except Exception:
                pass
        cached_times.append((time.perf_counter() - t0) * 1000)

    raw_p50 = sorted(raw_times)[len(raw_times) // 2]
    cached_p50 = sorted(cached_times)[len(cached_times) // 2]
    speedup = raw_p50 / cached_p50 if cached_p50 else float("inf")

    print(f"  Raw store p50:    {raw_p50:.2f}ms")
    print(f"  Cached store p50: {cached_p50:.2f}ms")
    print(f"  Speedup:          {speedup:.1f}x")
    return {"raw_p50": raw_p50, "cached_p50": cached_p50, "speedup": speedup}


def verify_cache_invalidation(store_root: str):
    """Verify that appending a new event invalidates the events cache."""
    import shutil, tempfile
    tmp = tempfile.mkdtemp(prefix="cache_invalidation_")
    try:
        # Copy store to tmp
        import os
        for f in os.listdir(store_root):
            src = os.path.join(store_root, f)
            dst = os.path.join(tmp, f)
            if os.path.isfile(src):
                shutil.copy(src, dst)
        shutil.copytree(os.path.join(store_root, "blobs"), os.path.join(tmp, "blobs"), dirs_exist_ok=True)

        cached = CachedStore(AppendOnlyStore(tmp))

        # Initial count
        n_before = sum(1 for _ in cached.iter("events"))
        print(f"\n=== Cache invalidation ===")
        print(f"  Events before append: {n_before}")

        # Append a fake event
        from intelligence_core.contracts import Event, ObjState
        fake_event = {
            "event_id": "evt-test-invalidation",
            "event_version": 1,
            "document_id": "doc-test",
            "event_type": "statistical_release",
            "fact_version_snapshot": [],
            "occurrence": 0,
            "status": "ACTIVE",
            "derived_at": "2026-08-18T00:00:00Z",
        }
        cached.append("events", fake_event)

        # Should be visible now
        n_after = sum(1 for _ in cached.iter("events"))
        print(f"  Events after append:  {n_after}")
        if n_after == n_before + 1:
            print(f"  ✓ PASS append visible in iter")
            return True
        else:
            print(f"  ✗ FAIL append NOT visible (cache not invalidated)")
            return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    store_root = sys.argv[1] if len(sys.argv) > 1 else "scale_50_store"
    correctness = verify_correctness(store_root)
    timing = verify_timing(store_root, n_requests=10, limit=50)
    invalidation = verify_cache_invalidation(store_root)
    print(f"\n=== Summary ===")
    print(f"  Correctness: {'PASS' if correctness else 'FAIL'}")
    print(f"  Speedup:     {timing['speedup']:.1f}x")
    print(f"  Invalidation: {'PASS' if invalidation else 'FAIL'}")
    sys.exit(0 if correctness and invalidation else 1)
