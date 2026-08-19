"""V2 §6 — Process remaining HTML sources aggressively.

Many HTML production-ready sources haven't been processed yet because they
need link extraction. This processes them with max_docs=30 to extract
more documents + IOs.
"""
from __future__ import annotations
import json
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


def process_remaining_html(store_root: str = "v3_corpus_store",
                             registry_root: str = "source_registry",
                             max_workers: int = 8):
    """Process all remaining HTML production-ready sources."""
    print(f"\n{'='*70}")
    print(f"V2 §6 — Process Remaining HTML Production-Ready Sources")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    existing_events = sum(1 for _ in store.iter("events"))
    existing_docs = sum(1 for _ in store.iter("documents"))
    print(f"  Starting events: {existing_events}")
    print(f"  Starting documents: {existing_docs}")

    # Find sources not yet in store
    existing_source_ids = set()
    for s in store.iter("sources"):
        existing_source_ids.add(s["source_id"])

    src_registry = SourceRegistry(registry_root)
    # Get HTML production-ready sources NOT yet in store
    html_pr_sources = [
        r for r in src_registry.all()
        if r.qualification_status == "PRODUCTION_READY"
        and r.acquisition_method == "HTML"
        and r.source_id not in existing_source_ids
    ]
    print(f"  Remaining HTML PR sources to process: {len(html_pr_sources)}")

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

    run_id = f"v3-html-{int(time.time())}"
    t_start = time.perf_counter()

    results = [None] * len(html_pr_sources)

    def worker(idx, r):
        result = process_html_source(store, institution_registry, r, run_id, max_docs=30)
        return idx, result

    future_to_idx = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, r in enumerate(html_pr_sources):
            future = executor.submit(worker, i, r)
            future_to_idx[future] = i

        for future in as_completed(future_to_idx):
            i = future_to_idx[future]
            try:
                idx, result = future.result(timeout=60)
                results[idx] = result
                n_ios = len(result.get("intelligence_objects", []))
                docs = result.get("documents_processed", 0)
                facts = result.get("facts_extracted", 0)
                src_id = result.get("source_id", "?")
                if n_ios > 0 or docs > 0:
                    print(f"  [{idx+1:2d}/{len(html_pr_sources)}] {src_id:<30} docs={docs:3d} facts={facts:4d} ios={n_ios:3d}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")

    elapsed = time.perf_counter() - t_start
    final_events = sum(1 for _ in store.iter("events"))
    final_docs = sum(1 for _ in store.iter("documents"))
    new_events = final_events - existing_events
    new_docs = final_docs - existing_docs

    print(f"\n--- Results ---")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  New documents: {new_docs}")
    print(f"  New events: {new_events}")
    print(f"  Final total documents: {final_docs}")
    print(f"  Final total events: {final_events}")

    return final_events, final_docs


if __name__ == "__main__":
    final_events, final_docs = process_remaining_html()
    # Run expanded patterns
    print(f"\n  Running expanded patterns...")
    from intelligence_core.tests.reliability.topup_expanded_patterns import reprocess_with_expanded_patterns
    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    final_events = reprocess_with_expanded_patterns(store)
    final_docs = sum(1 for _ in store.iter("documents"))
    print(f"\n  After expanded patterns: {final_events} events, {final_docs} documents")

    if final_events >= 500:
        print(f"  ✓ PASS: {final_events} real IOs (≥500 target)")
    else:
        print(f"  ⚠ {final_events} real IOs (< 500 target)")
    if final_docs >= 1000:
        print(f"  ✓ PASS: {final_docs} real documents (≥1,000 target)")
    else:
        print(f"  ⚠ {final_docs} real documents (< 1,000 target)")
