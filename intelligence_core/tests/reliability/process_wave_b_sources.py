"""V2 §6 — Process Wave B qualified sources through Core.

Process ≥50 production-ready/qualified sources through Core pipeline.
Target: produce real IOs from new Wave B sources.
"""
from __future__ import annotations
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.source_network.registry import SourceRegistry
from intelligence_core.tests.reliability.process_html_sources import process_html_source
from intelligence_core.tests.reliability.process_new_sources import process_new_source, SOURCE_ID_MAP, ORIGINAL_SOURCES
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.contracts import Institution
from urllib.parse import urlsplit


def run_wave_b_processing(store_root: str = "real_corpus_store_new",
                           registry_root: str = "source_registry",
                           max_workers: int = 8,
                           max_sources: int = 60):
    """Process Wave B qualified sources through Core."""
    print(f"\n{'='*70}")
    print(f"V2 §6 — Process Wave B qualified sources through Core")
    print(f"{'='*70}")

    store_root_final = f"{store_root}_waveb"
    if Path(store_root_final).exists():
        shutil.rmtree(store_root_final)
    shutil.copytree(store_root, store_root_final)

    from intelligence_core.cached_store import CachedStore
    from intelligence_core.store import AppendOnlyStore
    store = CachedStore(AppendOnlyStore(store_root_final))

    existing_events = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing_events}")

    src_registry = SourceRegistry(registry_root)
    # Get Wave B qualified sources
    wave_b_qualified = [
        r for r in src_registry.all()
        if r.discovery_wave == "B"
        and r.qualification_status in ("QUALIFIED", "PRODUCTION_READY")
    ]
    print(f"  Wave B qualified sources: {len(wave_b_qualified)}")
    print(f"  Processing up to {max_sources} sources...")

    # Set up institution registry
    institution_registry = InstitutionRegistry()
    for r in src_registry.all():
        website = r.canonical_url
        parts = urlsplit(website)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            inst = Institution(
                institution_id=r.institution_id, legal_entity=r.institution_name,
                jurisdiction=r.country, institutional_class=r.source_class,
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                institution_registry.add_institution(inst)
            except Exception:
                pass

    run_id = f"wave-b-{int(time.time())}"
    t_start = time.perf_counter()

    sources_to_process = wave_b_qualified[:max_sources]
    results = [None] * len(sources_to_process)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, r in enumerate(sources_to_process):
            # Choose processor based on acquisition method
            if r.acquisition_method in ("RSS", "ATOM"):
                futures[executor.submit(process_new_source, store, institution_registry, r, run_id)] = i
            else:
                futures[executor.submit(process_html_source, store, institution_registry, r, run_id)] = i

        for future in as_completed(futures):
            i = futures[future]
            try:
                result = future.result(timeout=60)
                results[i] = result
                n_ios = len(result.get("intelligence_objects", []))
                docs = result.get("documents_processed", 0)
                facts = result.get("facts_extracted", 0)
                src_id = result.get("source_id", "?")
                err = result.get("failure_reason") or "-"
                print(f"  [{i+1:2d}/{len(sources_to_process)}] {src_id:<25} docs={docs:2d} facts={facts:3d} ios={n_ios:3d} err={err}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")
                results[i] = {"source_id": sources_to_process[i].source_id,
                              "intelligence_objects": [],
                              "failure_reason": str(e)[:100]}

    elapsed = time.perf_counter() - t_start
    total_new_ios = sum(len(r.get("intelligence_objects", [])) for r in results if r)
    final_events = sum(1 for _ in store.iter("events"))
    new_events_count = final_events - existing_events

    print(f"\n--- Results ---")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Sources processed: {len([r for r in results if r and not r.get('skipped')])}")
    print(f"  New IOs produced: {total_new_ios}")
    print(f"  Final total events: {final_events}")
    print(f"  New events added: {new_events_count}")

    # Save results
    out = {
        "schema_version": "1.0",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store_root": store_root_final,
        "starting_events": existing_events,
        "final_events": final_events,
        "new_events": new_events_count,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    out_path = Path("intelligence_core/tests/reliability/wave_b_processing_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return final_events, new_events_count, store_root_final


if __name__ == "__main__":
    final, new, store_root = run_wave_b_processing(max_sources=60)
    if new >= 25:
        print(f"\n  ✓ PASS: {new} new real IOs (≥25 target)")
    else:
        print(f"\n  ⚠ {new} new real IOs (< 25 target)")
