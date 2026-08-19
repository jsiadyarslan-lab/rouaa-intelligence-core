"""V11 §2-3 — Register + qualify Wave D sources + process through Core."""
from __future__ import annotations
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.source_network.registry import SourceRegistry, SourceRecord
from intelligence_core.source_network.discovery_catalog_wave_d import WAVE_D_NEW_SOURCES
from intelligence_core.source_network.qualification import qualify_one_source
from intelligence_core.source_network.wave_c_qualification import harden_production_ready


def run_wave_d_qualification(registry_root: str = "source_registry"):
    print(f"\n{'='*70}")
    print(f"V11 §2 — Wave D Source Registration + Qualification")
    print(f"{'='*70}")

    registry = SourceRegistry(registry_root)
    catalog = WAVE_D_NEW_SOURCES
    print(f"\n  Wave D catalog: {len(catalog)} sources")
    print(f"  Existing in registry: {len(registry.all())}")

    # Register Wave D sources
    new_count = 0
    for entry in catalog:
        rec = SourceRecord(**entry)
        if registry.register(rec):
            new_count += 1
    print(f"  New Wave D sources registered: {new_count}")

    # Qualify in parallel
    wave_d_records = [r for r in registry.all() if r.discovery_wave == "D"]
    print(f"  Qualifying {len(wave_d_records)} Wave D sources...")

    t_start = time.perf_counter()

    def worker(idx, rec):
        rec = qualify_one_source(rec)
        if rec.qualification_status in ("QUALIFIED", "PRODUCTION_READY"):
            rec = harden_production_ready(rec)
        return idx, rec

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i, r) for i, r in enumerate(wave_d_records)]
        for future in as_completed(futures):
            try:
                idx, rec = future.result(timeout=30)
                registry.update(rec.source_id,
                                qualification_status=rec.qualification_status,
                                health_status=rec.health_status,
                                last_verified_at=rec.last_verified_at,
                                last_success_at=rec.last_success_at,
                                qualification_notes=rec.qualification_notes)
            except Exception as e:
                print(f"  FAILED: {e}")

    elapsed = time.perf_counter() - t_start
    stats = registry.stats()
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  Total sources: {stats['total_sources']}")
    print(f"\n  By qualification_status:")
    for k, v in sorted(stats["by_qualification"].items(), key=lambda x: -x[1]):
        print(f"    {k:<25} {v:>3}")

    total_pr = stats["by_qualification"].get("PRODUCTION_READY", 0)
    total_qualified = (stats["by_qualification"].get("QUALIFIED", 0) +
                       stats["by_qualification"].get("PRODUCTION_READY", 0))
    print(f"\n  Target ≥500 sources: {stats['total_sources']} ({'✓' if stats['total_sources'] >= 500 else '✗'})")
    print(f"  Target ≥150 qualified: {total_qualified} ({'✓' if total_qualified >= 150 else '✗'})")
    print(f"  Target ≥150 production-ready: {total_pr}")

    return stats


if __name__ == "__main__":
    stats = run_wave_d_qualification()
