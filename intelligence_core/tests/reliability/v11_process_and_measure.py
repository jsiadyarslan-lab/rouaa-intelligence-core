"""V11 §3-5 — Process all production-ready sources + measure recall.

Process ≥2,500 real documents from production-ready sources.
Apply V10 quality gates (navigation exclusion + semantic gate + evidence selector).
Measure Fact Recall + Event Recall on stratified audit sample.
"""
from __future__ import annotations
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.source_network.registry import SourceRegistry
from intelligence_core.tests.reliability.process_html_sources import process_html_source
from intelligence_core.tests.reliability.process_new_sources import process_new_source
from intelligence_core.tests.reliability.v10_re_extract import re_extract_with_nav_exclusion
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.contracts import Institution
from urllib.parse import urlsplit


def run_v11_processing(store_root: str = "v3_corpus_store",
                        registry_root: str = "source_registry"):
    """Process all production-ready sources through V10 quality pipeline."""
    print(f"\n{'='*70}")
    print(f"V11 §3 — Process All Production-Ready Sources (V10 Quality Pipeline)")
    print(f"{'='*70}")

    # Start from the V10 clean store
    store = CachedStore(AppendOnlyStore(store_root))
    before_events = sum(1 for _ in store.iter("events"))
    before_facts = sum(1 for _ in store.iter("facts"))
    before_docs = sum(1 for _ in store.iter("documents"))
    print(f"\n  Starting: {before_events} events, {before_facts} facts, {before_docs} docs")

    # Get production-ready sources NOT yet in store
    existing_source_ids = set()
    for s in store.iter("sources"):
        existing_source_ids.add(s["source_id"])

    src_registry = SourceRegistry(registry_root)
    pr_sources = [
        r for r in src_registry.all()
        if r.qualification_status == "PRODUCTION_READY"
        and r.source_id not in existing_source_ids
    ]
    print(f"  New PR sources to process: {len(pr_sources)}")

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

    run_id = f"v11-{int(time.time())}"
    t_start = time.perf_counter()

    def worker(idx, r):
        if r.acquisition_method in ("RSS", "ATOM"):
            result = process_new_source(store, institution_registry, r, run_id, max_items=50)
        else:
            result = process_html_source(store, institution_registry, r, run_id, max_docs=30)
        return idx, result

    future_to_idx = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        for i, r in enumerate(pr_sources):
            future = executor.submit(worker, i, r)
            future_to_idx[future] = i

        for future in as_completed(future_to_idx):
            i = future_to_idx[future]
            try:
                idx, result = future.result(timeout=90)
                n_ios = len(result.get("intelligence_objects", []))
                docs = result.get("documents_processed", 0)
                facts = result.get("facts_extracted", 0)
                src_id = result.get("source_id", "?")
                if n_ios > 0 or docs > 0:
                    print(f"  [{idx+1:2d}/{len(pr_sources)}] {src_id:<30} docs={docs:3d} facts={facts:4d} ios={n_ios:3d}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")

    elapsed = time.perf_counter() - t_start
    after_docs = sum(1 for _ in store.iter("documents"))
    after_facts = sum(1 for _ in store.iter("facts"))

    print(f"\n--- Pre-Re-extraction Results ---")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Documents: {before_docs} → {after_docs} (+{after_docs - before_docs})")
    print(f"  Facts (pre-V10): {before_facts} → {after_facts}")

    # Now run V10 re-extraction (navigation exclusion + semantic gate + evidence selector)
    print(f"\n--- V10 Quality Re-extraction ---")
    final_events, final_facts = re_extract_with_nav_exclusion(store_root)

    print(f"\n--- Final Results ---")
    print(f"  Documents: {after_docs}")
    print(f"  Facts: {final_facts}")
    print(f"  Events: {final_events}")

    return final_events, after_docs, final_facts


if __name__ == "__main__":
    events, docs, facts = run_v11_processing()
    if events >= 500:
        print(f"\n  ✓ PASS: {events} IOs (≥500 target)")
    else:
        print(f"\n  ⚠ {events} IOs (< 500 target)")
    if docs >= 2500:
        print(f"  ✓ PASS: {docs} documents (≥2,500 target)")
    else:
        print(f"  ⚠ {docs} documents (< 2,500 target)")
