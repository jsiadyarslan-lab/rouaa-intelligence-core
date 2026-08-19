"""V2 §5 — Wave B qualification: register + qualify Wave B sources."""
from __future__ import annotations
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.source_network.registry import SourceRegistry, SourceRecord
from intelligence_core.source_network.discovery_catalog_wave_b import get_wave_b_catalog
from intelligence_core.source_network.qualification import qualify_one_source


def run_wave_b_qualification(registry_root: str = "source_registry"):
    print(f"\n{'='*70}")
    print(f"V2 §5 — Wave B Source Qualification")
    print(f"{'='*70}")

    registry = SourceRegistry(registry_root)
    catalog = get_wave_b_catalog()
    print(f"\n  Wave B catalog: {len(catalog)} sources")
    print(f"  Existing in registry: {len(registry.all())}")

    # Register Wave B sources
    new_count = 0
    for entry in catalog:
        rec = SourceRecord(**entry)
        if registry.register(rec):
            new_count += 1
    print(f"  New Wave B sources registered: {new_count}")

    # Qualify in parallel
    all_records = registry.all()
    wave_b_records = [r for r in all_records if r.discovery_wave == "B"]
    print(f"  Qualifying {len(wave_b_records)} Wave B sources...")

    t_start = time.perf_counter()
    results = [None] * len(wave_b_records)

    def worker(idx, rec):
        return idx, qualify_one_source(rec)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i, r) for i, r in enumerate(wave_b_records)]
        for future in as_completed(futures):
            try:
                idx, rec = future.result(timeout=30)
                results[idx] = rec
                registry.update(rec.source_id,
                                qualification_status=rec.qualification_status,
                                health_status=rec.health_status,
                                last_verified_at=rec.last_verified_at,
                                last_success_at=rec.last_success_at,
                                qualification_notes=rec.qualification_notes)
            except Exception as e:
                print(f"  FAILED: {e}")

    elapsed = time.perf_counter() - t_start
    print(f"\n  Elapsed: {elapsed:.1f}s")

    # Combined stats (Wave A + Wave B)
    stats = registry.stats()
    print(f"\n--- Combined Registry Results (Wave A + Wave B) ---")
    print(f"  Total sources: {stats['total_sources']}")
    print(f"\n  By qualification_status:")
    for k, v in sorted(stats["by_qualification"].items(), key=lambda x: -x[1]):
        print(f"    {k:<25} {v:>3}")
    print(f"\n  By health_status:")
    for k, v in sorted(stats["by_health"].items(), key=lambda x: -x[1]):
        print(f"    {k:<25} {v:>3}")
    print(f"\n  By region:")
    for k, v in sorted(stats["by_region"].items(), key=lambda x: -x[1]):
        print(f"    {k:<20} {v:>3}")
    print(f"\n  By source_class:")
    for k, v in sorted(stats["by_source_class"].items(), key=lambda x: -x[1]):
        print(f"    {k:<30} {v:>3}")

    # Wave B specific stats
    wave_b_qualified = sum(1 for r in wave_b_records
                           if r.qualification_status in ("QUALIFIED", "PRODUCTION_READY"))
    wave_b_pr = sum(1 for r in wave_b_records if r.qualification_status == "PRODUCTION_READY")
    print(f"\n--- Wave B specific ---")
    print(f"  Wave B sources: {len(wave_b_records)}")
    print(f"  Wave B qualified: {wave_b_qualified}")
    print(f"  Wave B production-ready: {wave_b_pr}")

    # Check targets
    total = stats["total_sources"]
    total_qualified = (stats["by_qualification"].get("QUALIFIED", 0) +
                       stats["by_qualification"].get("PRODUCTION_READY", 0))
    total_pr = stats["by_qualification"].get("PRODUCTION_READY", 0)

    print(f"\n--- Target check ---")
    print(f"  ≥250 sources: {total} ({'✓' if total >= 250 else '✗'} {total}/250)")
    print(f"  ≥100 qualified: {total_qualified} ({'✓' if total_qualified >= 100 else '✗'} {total_qualified}/100)")
    print(f"  ≥60 production-ready: {total_pr} ({'✓' if total_pr >= 60 else '✗'} {total_pr}/60)")

    # Save report
    report = {
        "schema_version": "1.0",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wave": "B",
        "elapsed_s": round(elapsed, 1),
        "stats": stats,
        "wave_b_count": len(wave_b_records),
        "wave_b_qualified": wave_b_qualified,
        "wave_b_production_ready": wave_b_pr,
        "targets": {
            "sources_250": {"target": 250, "actual": total, "pass": total >= 250},
            "qualified_100": {"target": 100, "actual": total_qualified, "pass": total_qualified >= 100},
            "pr_60": {"target": 60, "actual": total_pr, "pass": total_pr >= 60},
        },
    }
    out_path = Path("intelligence_core/tests/reliability/wave_b_qualification_results.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Report saved to: {out_path}")

    return registry, stats


if __name__ == "__main__":
    registry, stats = run_wave_b_qualification()
