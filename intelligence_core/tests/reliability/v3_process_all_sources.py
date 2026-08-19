"""V2 §6-7 — Process all production-ready sources through Core.

Target: ≥1,000 real official documents processed → ≥500 real IOs.

Process all 91 PRODUCTION_READY sources through Core pipeline with:
  - max_items=50 per RSS source
  - max_docs=20 per HTML source
  - Expanded extraction patterns
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

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.source_network.registry import SourceRegistry
from intelligence_core.tests.reliability.process_html_sources import process_html_source
from intelligence_core.tests.reliability.process_new_sources import process_new_source
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.contracts import Institution
from urllib.parse import urlsplit


def run_v3_processing(store_root: str = "real_corpus_store_new_waveb",
                       registry_root: str = "source_registry",
                       max_workers: int = 8):
    """Process all PRODUCTION_READY sources through Core."""
    print(f"\n{'='*70}")
    print(f"V2 §6-7 — Process All Production-Ready Sources (V3)")
    print(f"{'='*70}")

    store_root_final = "v3_corpus_store"
    if Path(store_root_final).exists():
        shutil.rmtree(store_root_final)
    shutil.copytree(store_root, store_root_final)

    store = CachedStore(AppendOnlyStore(store_root_final))
    existing_events = sum(1 for _ in store.iter("events"))
    existing_docs = sum(1 for _ in store.iter("documents"))
    print(f"  Starting events: {existing_events}")
    print(f"  Starting documents: {existing_docs}")

    src_registry = SourceRegistry(registry_root)
    pr_sources = [
        r for r in src_registry.all()
        if r.qualification_status == "PRODUCTION_READY"
    ]
    print(f"  Production-ready sources to process: {len(pr_sources)}")

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

    run_id = f"v3-processing-{int(time.time())}"
    t_start = time.perf_counter()

    results = [None] * len(pr_sources)

    def worker(idx, r):
        # Use higher max_items for RSS, lower for HTML
        if r.acquisition_method in ("RSS", "ATOM"):
            result = process_new_source(store, institution_registry, r, run_id, max_items=50)
        else:
            result = process_html_source(store, institution_registry, r, run_id, max_docs=20)
        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, i, r) for i, r in enumerate(pr_sources)]
        for future in as_completed(futures):
            i = futures[future]
            try:
                idx, result = future.result(timeout=90)
                results[idx] = result
                n_ios = len(result.get("intelligence_objects", []))
                docs = result.get("documents_processed", 0)
                facts = result.get("facts_extracted", 0)
                src_id = result.get("source_id", "?")
                if n_ios > 0 or docs > 0:
                    print(f"  [{idx+1:2d}/{len(pr_sources)}] {src_id:<30} docs={docs:3d} facts={facts:4d} ios={n_ios:3d}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")
                results[i] = {"source_id": pr_sources[i].source_id,
                              "intelligence_objects": [],
                              "failure_reason": str(e)[:100]}

    elapsed = time.perf_counter() - t_start
    total_new_ios = sum(len(r.get("intelligence_objects", [])) for r in results if r)
    final_events = sum(1 for _ in store.iter("events"))
    final_docs = sum(1 for _ in store.iter("documents"))
    new_events_count = final_events - existing_events
    new_docs_count = final_docs - existing_docs

    print(f"\n--- Results ---")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Sources processed: {len([r for r in results if r and not r.get('skipped')])}")
    print(f"  Sources producing IOs: {len([r for r in results if r and r.get('intelligence_objects')])}")
    print(f"  New documents processed: {new_docs_count}")
    print(f"  New IOs produced: {total_new_ios}")
    print(f"  Final total documents: {final_docs}")
    print(f"  Final total events: {final_events}")

    # Save results
    out = {
        "schema_version": "1.0",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store_root": store_root_final,
        "starting_events": existing_events,
        "starting_documents": existing_docs,
        "final_events": final_events,
        "final_documents": final_docs,
        "new_events": new_events_count,
        "new_documents": new_docs_count,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    out_path = Path("intelligence_core/tests/reliability/v3_processing_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return final_events, final_docs, store_root_final


if __name__ == "__main__":
    final_events, final_docs, store_root = run_v3_processing()
    if final_events >= 500:
        print(f"\n  ✓ PASS: {final_events} real IOs (≥500 target)")
    else:
        print(f"\n  ⚠ {final_events} real IOs (< 500 target)")
    if final_docs >= 1000:
        print(f"  ✓ PASS: {final_docs} real documents (≥1,000 target)")
    else:
        print(f"  ⚠ {final_docs} real documents (< 1,000 target)")
