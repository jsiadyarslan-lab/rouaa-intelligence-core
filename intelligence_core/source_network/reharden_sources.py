"""V2 §3 — Re-harden Wave A+B sources for production-ready upgrade.

The Wave A+B sources were qualified with the old (lenient) standard.
Re-apply the hardened production-ready check to upgrade qualified sources
that actually have document retrieval proof.
"""
from __future__ import annotations
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.source_network.registry import SourceRegistry
from intelligence_core.source_network.wave_c_qualification import harden_production_ready


def reharden_existing_sources(registry_root: str = "source_registry"):
    """Re-apply hardened production-ready check to all QUALIFIED sources."""
    print(f"\n{'='*70}")
    print(f"V2 §3 — Re-harden Wave A+B Sources for Production-Ready Upgrade")
    print(f"{'='*70}")

    registry = SourceRegistry(registry_root)
    all_sources = registry.all()

    # Get all QUALIFIED sources (not yet PRODUCTION_READY)
    qualified_sources = [
        r for r in all_sources
        if r.qualification_status == "QUALIFIED"
    ]
    print(f"\n  Total QUALIFIED sources to re-harden: {len(qualified_sources)}")

    t_start = time.perf_counter()
    upgraded = 0
    stayed_qualified = 0
    failed = 0

    def worker(rec):
        return harden_production_ready(rec)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, r) for r in qualified_sources]
        for future in as_completed(futures):
            try:
                rec = future.result(timeout=30)
                if rec.qualification_status == "PRODUCTION_READY":
                    upgraded += 1
                    registry.update(rec.source_id,
                                    qualification_status=rec.qualification_status,
                                    qualification_notes=rec.qualification_notes)
                else:
                    stayed_qualified += 1
            except Exception as e:
                failed += 1

    elapsed = time.perf_counter() - t_start
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  Upgraded to PRODUCTION_READY: {upgraded}")
    print(f"  Stayed QUALIFIED: {stayed_qualified}")
    print(f"  Failed: {failed}")

    # Final stats
    stats = registry.stats()
    print(f"\n--- Final Registry Stats ---")
    print(f"  Total sources: {stats['total_sources']}")
    print(f"  PRODUCTION_READY: {stats['by_qualification'].get('PRODUCTION_READY', 0)}")
    print(f"  QUALIFIED: {stats['by_qualification'].get('QUALIFIED', 0)}")
    print(f"  REQUIRES_REMEDIATION: {stats['by_qualification'].get('REQUIRES_REMEDIATION', 0)}")

    total_pr = stats["by_qualification"].get("PRODUCTION_READY", 0)
    print(f"\n  Target ≥50 production-ready: {total_pr} ({'✓' if total_pr >= 50 else '✗'})")

    return stats


if __name__ == "__main__":
    stats = reharden_existing_sources()
