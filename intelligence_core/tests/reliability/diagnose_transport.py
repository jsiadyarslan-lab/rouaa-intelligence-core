"""V2 §2 — Transport root cause diagnostic.

Instruments the GET /v1/intelligence path with per-stage latency measurement:

  GET /v1/intelligence
      ↓
  store open                              ← stage A
      ↓
  store.iter("events")                    ← stage B (full scan)
      ↓
  for each event in page:                 ← stage C (per-event cost)
      build_intelligence_object():
          for each fact in snapshot:
              store.fact_row()             ← full facts.jsonl scan
              store.latest_by_id("representations")  ← full scan
              store.latest_by_id("documents")        ← full scan
              [e for e in store.iter("evidence") if ...]  ← full scan
              store.latest_by_id("sources")          ← full scan
      ↓
  json.dumps + send                       ← stage D

Measures p50/p95/p99 for each stage across 10 requests against scale_50_store.
"""
from __future__ import annotations
import json
import os
import sys
import time
import statistics
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from intelligence_core.store import AppendOnlyStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id


def measure_stage(label: str, fn, samples: list):
    t0 = time.perf_counter()
    result = fn()
    dt_ms = (time.perf_counter() - t0) * 1000
    samples.append(dt_ms)
    return result


def percentile(values, p):
    if not values:
        return 0
    s = sorted(values)
    k = int(len(s) * p / 100)
    if k >= len(s):
        k = len(s) - 1
    return s[k]


def diagnose(store_root: str, n_requests: int = 10, limit: int = 50):
    """Run n_requests measurements against the store and report per-stage latencies."""
    print(f"\n=== Transport Diagnostic ===")
    print(f"Store: {store_root}")
    print(f"Requests: {n_requests}, limit: {limit}")

    # Stage samples
    stages = defaultdict(list)
    total_times = []

    for i in range(n_requests):
        t_start = time.perf_counter()

        # Stage A: open store
        store = measure_stage("A_open_store", lambda: AppendOnlyStore(store_root), stages["A_open_store"])

        # Stage B: iter events
        events = measure_stage("B_iter_events", lambda: list(store.iter("events")), stages["B_iter_events"])

        # Sort by (derived_at, event_id, event_version)
        t0 = time.perf_counter()
        events.sort(key=lambda e: (e.get("derived_at", ""), e.get("event_id", ""), e.get("event_version", 0)))
        stages["B_sort"].append((time.perf_counter() - t0) * 1000)

        # Paginate
        page = events[:limit]

        # Stage C: build IOs (per-event)
        t0 = time.perf_counter()
        objects = []
        for ev in page:
            try:
                # Inside this: store.fact_row, store.latest_by_id x3, evidence scan
                io = build_intelligence_object(store, ev, source_name="Source")
                objects.append(io.to_dict())
            except Exception as e:
                pass
        stages["C_build_ios"].append((time.perf_counter() - t0) * 1000)

        # Stage D: serialize
        t0 = time.perf_counter()
        response = {"objects": objects, "next_cursor": None, "count": len(objects)}
        _ = json.dumps(response, default=str)
        stages["D_serialize"].append((time.perf_counter() - t0) * 1000)

        total_times.append((time.perf_counter() - t_start) * 1000)

    # Report
    print(f"\n--- Per-stage latency (ms) ---")
    print(f"{'Stage':<30} {'p50':>10} {'p95':>10} {'p99':>10} {'min':>10} {'max':>10}")
    for stage in ["A_open_store", "B_iter_events", "B_sort", "C_build_ios", "D_serialize"]:
        s = stages[stage]
        if not s:
            continue
        print(f"{stage:<30} {percentile(s,50):>10.2f} {percentile(s,95):>10.2f} "
              f"{percentile(s,99):>10.2f} {min(s):>10.2f} {max(s):>10.2f}")

    print(f"\n--- Total request latency (ms) ---")
    print(f"p50={percentile(total_times,50):.2f} p95={percentile(total_times,95):.2f} "
          f"p99={percentile(total_times,99):.2f} min={min(total_times):.2f} max={max(total_times):.2f}")

    # Cost breakdown
    print(f"\n--- Cost breakdown ---")
    total_avg = statistics.mean(total_times)
    for stage in ["A_open_store", "B_iter_events", "B_sort", "C_build_ios", "D_serialize"]:
        s = stages[stage]
        if not s:
            continue
        avg = statistics.mean(s)
        pct = (avg / total_avg) * 100 if total_avg else 0
        print(f"  {stage:<30} {avg:>8.2f}ms  ({pct:>5.1f}%)")

    # Per-event cost
    n_events_per_req = len(page)
    per_event_cost = statistics.mean(stages["C_build_ios"]) / n_events_per_req if n_events_per_req else 0
    print(f"\nPer-event build cost: {per_event_cost:.2f}ms ({n_events_per_req} events/page)")

    # Store stats
    print(f"\n--- Store stats ---")
    store = AppendOnlyStore(store_root)
    for coll in ["events", "facts", "evidence", "documents", "representations", "sources"]:
        try:
            n = sum(1 for _ in store.iter(coll))
            print(f"  {coll:<20} {n:>6} rows")
        except Exception:
            print(f"  {coll:<20} ERROR")

    return {
        "total_p50": percentile(total_times, 50),
        "total_p95": percentile(total_times, 95),
        "total_p99": percentile(total_times, 99),
        "stages": {k: {"p50": percentile(v, 50), "p95": percentile(v, 95), "p99": percentile(v, 99)} for k, v in stages.items()},
    }


if __name__ == "__main__":
    store_root = sys.argv[1] if len(sys.argv) > 1 else "scale_50_store"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    result = diagnose(store_root, n, limit)
    print(f"\n=== Diagnosis complete ===")
    print(json.dumps(result, indent=2))
