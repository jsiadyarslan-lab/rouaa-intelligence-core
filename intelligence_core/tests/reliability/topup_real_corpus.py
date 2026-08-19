"""V2-Real §3 — Round 2: top-up to ≥100 real IOs.

Run another pass on real_corpus_store with:
  - max_items=50 for high-yield sources (euronext, fca, esma, ecb, sec)
  - Retry previously-failed sources
  - Try additional sources from WAVE1 manifest
"""
from __future__ import annotations
import json
import os
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.acquisition import DirectHttpAdapter, Transport, parse_rss_items
from intelligence_core.contracts import (
    Institution, Evidence, Source, Document, Representation,
)
from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.temporal import parse_rfc822_pubdate
from intelligence_core.tests.scale.run_scale_validation import (
    RATE_PATTERNS, STATISTICAL_PATTERNS, ENFORCEMENT_PATTERNS,
    MARKET_STAT_PATTERNS, EVENT_TYPE_BY_SOURCE_TYPE, RSS_PATHS,
    build_institution_registry, try_acquire_rss, process_one_document,
)
from intelligence_core.tests.reliability.expand_real_corpus_parallel import (
    process_one_source_parallel,
)


def load_topup_sources():
    """Sources to top up: high-yield ones with more items, plus additional candidates."""
    sources = [
        # High-yield — process MORE items
        {"source_id": "imp-euronext", "name": "Euronext", "class": "Market Infrastructure",
         "type": "exchange", "country": "EU", "website": "https://www.euronext.com", "max_items": 60},
        {"source_id": "imp-fca", "name": "FCA", "class": "Financial Regulator",
         "type": "regulator", "country": "UK", "website": "https://www.fca.org.uk", "max_items": 60},
        {"source_id": "imp-esma", "name": "ESMA", "class": "Financial Regulator",
         "type": "regulator", "country": "EU", "website": "https://www.esma.europa.eu", "max_items": 60},
        {"source_id": "imp-ecb", "name": "European Central Bank", "class": "Central Bank",
         "type": "central_bank", "country": "EU", "website": "https://www.ecb.europa.eu", "max_items": 60},
        {"source_id": "imp-sec", "name": "SEC", "class": "Financial Regulator",
         "type": "regulator", "country": "US", "website": "https://www.sec.gov", "max_items": 60},
        # Retry previously-failed
        {"source_id": "imp-federal-reserve", "name": "Federal Reserve", "class": "Central Bank",
         "type": "central_bank", "country": "US", "website": "https://www.federalreserve.gov", "max_items": 30},
        {"source_id": "imp-eurostat", "name": "Eurostat", "class": "Statistical Agency",
         "type": "statistics", "country": "EU", "website": "https://ec.europa.eu/eurostat", "max_items": 30},
        # New candidate sources from WAVE1
        {"source_id": "imp-bis", "name": "Bank for International Settlements", "class": "International Organization",
         "type": "intl_org", "country": "International", "website": "https://www.bis.org", "max_items": 30},
        {"source_id": "imp-imf", "name": "International Monetary Fund", "class": "International Organization",
         "type": "intl_org", "country": "International", "website": "https://www.imf.org", "max_items": 30},
        {"source_id": "imp-oecd", "name": "OECD", "class": "International Organization",
         "type": "intl_org", "country": "International", "website": "https://www.oecd.org", "max_items": 30},
        {"source_id": "imp-ec", "name": "European Commission", "class": "Ministry of Finance",
         "type": "ministry", "country": "EU", "website": "https://ec.europa.eu", "max_items": 30},
    ]
    return sources


def run_topup():
    """Top up real_corpus_store to ≥100 real IOs."""
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Round 2: Top-up to ≥100 real IOs")
    print(f"{'='*70}")

    store_root = "real_corpus_store"
    store = CachedStore(AppendOnlyStore(store_root))
    existing_events = sum(1 for _ in store.iter("events"))
    print(f"\n  Starting events: {existing_events}")

    sources = load_topup_sources()
    registry = build_institution_registry(sources)
    run_id = f"real-topup-{int(time.time())}"

    # Process in parallel — each source has its own max_items
    results = [None] * len(sources)
    t_start = time.perf_counter()

    def worker(idx, src):
        max_items = src.get("max_items", 30)
        # Remove the non-standard key before passing
        src_clean = {k: v for k, v in src.items() if k != "max_items"}
        result = process_one_source_parallel(store, registry, src_clean, run_id, max_items=max_items)
        return idx, result

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(worker, i, src) for i, src in enumerate(sources)]
        for future in as_completed(futures):
            try:
                idx, result = future.result(timeout=90)
                results[idx] = result
                n_ios = len(result["intelligence_objects"])
                print(f"  [{idx+1:2d}/{len(sources)}] {sources[idx]['source_id']:<30} "
                      f"ios={n_ios:3d} "
                      f"err={result['failure_reason'] or '-'}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")

    elapsed = time.perf_counter() - t_start
    print(f"\n  Elapsed: {elapsed:.1f}s")

    total_events = sum(1 for _ in store.iter("events"))
    new_events = total_events - existing_events
    print(f"\n  Starting events: {existing_events}")
    print(f"  New events added: {new_events}")
    print(f"  Total events: {total_events}")

    return total_events


if __name__ == "__main__":
    total = run_topup()
    if total >= 100:
        print(f"\n  ✓ PASS: {total} real events (≥100 target)")
    else:
        print(f"\n  ⚠ {total} real events (< 100 target)")
