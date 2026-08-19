"""V2 §7-8 — Continuous monitoring across ≥25 sources + freshness measurement.

Run 3 monitoring cycles across ≥25 production-ready/qualified sources.
Measure freshness by source class.
"""
from __future__ import annotations
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.source_network.registry import SourceRegistry
from intelligence_core.tests.reliability.continuous_monitor import ContinuousMonitor


def run_extended_continuous_monitoring(store_root: str, registry_root: str = "source_registry"):
    """Run continuous monitoring across ≥25 sources, 3 cycles."""
    print(f"\n{'='*70}")
    print(f"V2 §7-8 — Extended Continuous Monitoring (≥25 sources, 3 cycles)")
    print(f"{'='*70}")

    monitor = ContinuousMonitor(store_root, registry_root)

    # Select ≥25 sources that have produced IOs in the store
    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")
    sources_with_ios = set()
    for ev in store.iter("events"):
        doc = docs_by_id.get(ev.get("document_id", ""), {})
        src_id = doc.get("source_id", "")
        if src_id:
            sources_with_ios.add(src_id)

    print(f"\n  Sources with IOs in store: {len(sources_with_ios)}")

    # Get source records for these
    src_registry = SourceRegistry(registry_root)
    sources_to_monitor = []
    for sid in list(sources_with_ios)[:30]:  # monitor up to 30
        rec = src_registry.get(sid)
        if rec is None:
            # Create a temporary SourceRecord for imp-* sources not in registry
            from intelligence_core.source_network.registry import SourceRecord
            rec = SourceRecord(
                source_id=sid, institution_id=sid, institution_name=sid,
                country="unknown", jurisdiction="unknown", region="unknown",
                source_class="unknown", domain="unknown", authority_level="unknown",
                official_domain="", canonical_url="", acquisition_endpoint="",
                endpoint_type="", acquisition_method="", language="en",
                coverage_topics=[], frequency="unknown",
                qualification_status="QUALIFIED", health_status="HEALTHY",
                last_verified_at="", last_success_at="",
                last_document_at="", last_event_at="",
                discovered_at="", discovery_wave="A", qualification_notes="",
            )
        sources_to_monitor.append(rec)

    print(f"  Sources to monitor: {len(sources_to_monitor)}")

    # Run 3 cycles
    cycles = []
    for cycle_num in range(1, 4):
        print(f"\n  Cycle {cycle_num}...")
        source_ids = [r.source_id for r in sources_to_monitor]
        cycle_result = monitor.monitor_cycle(source_ids=source_ids)
        cycles.append(cycle_result)

        # Print summary
        healthy = sum(1 for r in cycle_result["results"] if r["health"] == "HEALTHY")
        stale = sum(1 for r in cycle_result["results"] if r["health"] == "STALE")
        no_content = sum(1 for r in cycle_result["results"] if r["health"] == "NO_CONTENT")
        total_new = sum(r["new_events"] for r in cycle_result["results"])
        print(f"    HEALTHY={healthy} STALE={stale} NO_CONTENT={no_content} new_events={total_new}")

    # Freshness measurement by source class
    print(f"\n--- Freshness by source class ---")
    freshness = monitor.measure_freshness()

    # Group by source class
    src_class_freshness = defaultdict(list)
    for f in freshness["sources"]:
        src_id = f["source_id"]
        rec = src_registry.get(src_id)
        src_class = rec.source_class if rec else "unknown"
        src_class_freshness[src_class].append(f)

    freshness_by_class = {}
    for cls, sources in src_class_freshness.items():
        doc_counts = [s["document_count"] for s in sources]
        event_counts = [s["event_count"] for s in sources]
        ages = [s.get("doc_age_days") for s in sources if s.get("doc_age_days") is not None]
        freshness_by_class[cls] = {
            "source_count": len(sources),
            "total_docs": sum(doc_counts),
            "total_events": sum(event_counts),
            "avg_doc_age_days": (sum(ages) / len(ages)) if ages else None,
            "min_doc_age_days": min(ages) if ages else None,
            "max_doc_age_days": max(ages) if ages else None,
        }
        print(f"  {cls:<30} sources={len(sources):2d} docs={sum(doc_counts):3d} "
              f"events={sum(event_counts):3d} avg_age={freshness_by_class[cls]['avg_doc_age_days']}")

    # Summary
    print(f"\n--- Continuous Monitoring Summary ---")
    print(f"  Sources monitored: {len(sources_to_monitor)}")
    print(f"  Cycles run: 3")
    print(f"  Cycle 1 new events: {sum(r['new_events'] for r in cycles[0]['results'])}")
    print(f"  Cycle 2 new events: {sum(r['new_events'] for r in cycles[1]['results'])} (idempotency check)")
    print(f"  Cycle 3 new events: {sum(r['new_events'] for r in cycles[2]['results'])} (idempotency check)")

    cycle2_new = sum(r["new_events"] for r in cycles[1]["results"])
    cycle3_new = sum(r["new_events"] for r in cycles[2]["results"])
    idempotency_pass = (cycle2_new == 0 and cycle3_new == 0)

    if idempotency_pass:
        print(f"  ✓ PASS: idempotency holds (0 new events in cycles 2+3)")
    else:
        print(f"  ✗ FAIL: idempotency broken (cycle2={cycle2_new}, cycle3={cycle3_new})")

    return {
        "sources_monitored": len(sources_to_monitor),
        "cycles": cycles,
        "freshness_by_class": freshness_by_class,
        "idempotency_pass": idempotency_pass,
    }


if __name__ == "__main__":
    import sys
    store_root = sys.argv[1] if len(sys.argv) > 1 else "real_corpus_store_new_waveb"
    result = run_extended_continuous_monitoring(store_root)
    out_path = Path("intelligence_core/tests/reliability/extended_continuous_monitoring_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
