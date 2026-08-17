"""V2-Real §3 — Expand REAL corpus to ≥100 IOs from real official sources.

Strategy:
  1. Start from scale_50_store (60 real IOs from 14 sources)
  2. Process MORE items per source (max_items=30, was 3 in V1)
  3. Focus on already-working sources (ESMA, FCA, Euronext, ECB, SEC, Fed Reserve, Eurostat)
  4. Try additional sources from WAVE1 manifest
  5. All IOs must come from real HTTP acquisition — no synthetic data

Target: ≥100 REAL_OFFICIAL_SOURCE IOs
"""
from __future__ import annotations
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.acquisition import DirectHttpAdapter, parse_rss_items
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
    calculate_metrics,
)


def load_known_working_sources():
    """Load the 25 sources from scale_50_store that we know were reachable."""
    # These are the sources that were successfully acquired in V1
    sources = [
        {"source_id": "imp-federal-reserve", "name": "Federal Reserve", "class": "Central Bank",
         "type": "central_bank", "country": "US", "website": "https://www.federalreserve.gov"},
        {"source_id": "imp-ecb", "name": "European Central Bank", "class": "Central Bank",
         "type": "central_bank", "country": "EU", "website": "https://www.ecb.europa.eu"},
        {"source_id": "imp-bank-of-england", "name": "Bank of England", "class": "Central Bank",
         "type": "central_bank", "country": "UK", "website": "https://www.bankofengland.co.uk"},
        {"source_id": "imp-bea", "name": "Bureau of Economic Analysis", "class": "Statistical Agency",
         "type": "statistics", "country": "US", "website": "https://www.bea.gov"},
        {"source_id": "imp-eurostat", "name": "Eurostat", "class": "Statistical Agency",
         "type": "statistics", "country": "EU", "website": "https://ec.europa.eu/eurostat"},
        {"source_id": "imp-sec", "name": "SEC", "class": "Financial Regulator",
         "type": "regulator", "country": "US", "website": "https://www.sec.gov"},
        {"source_id": "imp-cftc", "name": "CFTC", "class": "Financial Regulator",
         "type": "regulator", "country": "US", "website": "https://www.cftc.gov"},
        {"source_id": "imp-esma", "name": "ESMA", "class": "Financial Regulator",
         "type": "regulator", "country": "EU", "website": "https://www.esma.europa.eu"},
        {"source_id": "imp-fca", "name": "FCA", "class": "Financial Regulator",
         "type": "regulator", "country": "UK", "website": "https://www.fca.org.uk"},
        {"source_id": "imp-euronext", "name": "Euronext", "class": "Market Infrastructure",
         "type": "exchange", "country": "EU", "website": "https://www.euronext.com"},
        {"source_id": "imp-hm-treasury", "name": "HM Treasury", "class": "Ministry of Finance",
         "type": "ministry", "country": "UK", "website": "https://www.gov.uk"},
        {"source_id": "imp-consob", "name": "CONSOB", "class": "Financial Regulator",
         "type": "regulator", "country": "IT", "website": "https://www.consob.it"},
        {"source_id": "imp-stats-china", "name": "National Bureau of Statistics of China",
         "class": "Statistical Agency", "type": "statistics", "country": "CN",
         "website": "http://www.stats.gov.cn"},
        {"source_id": "imp-fsb", "name": "Financial Stability Board", "class": "International Organization",
         "type": "intl_org", "country": "International", "website": "https://www.fsb.org"},
    ]
    return sources


def process_one_source_real(store, registry, adapter, src, run_id, max_items=30):
    """Process one source with higher max_items to extract more IOs."""
    website = src.get("website", "")
    source_id = src.get("source_id", src.get("name", "unknown"))
    source_name = src.get("name", source_id)
    source_type = src.get("type", "")
    result = {
        "source_id": source_id, "name": source_name, "class": src.get("class",""),
        "country": src.get("country",""), "website": website,
        "acquisition": None, "documents_acquired": 0, "documents_processed": 0,
        "documents_with_facts": 0, "facts_extracted": 0,
        "documents_with_events": 0, "events_detected": 0,
        "intelligence_objects": [], "errors": [],
        "failure_stage": None, "failure_reason": None,
    }
    try:
        inst = registry.resolve(website)
        if inst is None:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = "entity_not_resolved"
            return result
        event_type, patterns = EVENT_TYPE_BY_SOURCE_TYPE.get(
            source_type, ("statistical_release", STATISTICAL_PATTERNS))
        rss_fetch = try_acquire_rss(adapter, website)
        if rss_fetch is None:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = "no_rss_feed"
            return result
        result["acquisition"] = {
            "http_status": rss_fetch["retrieval_event"].http_status,
            "bytes": len(rss_fetch["bytes"]),
            "feed_url": rss_fetch["canonical_url"],
        }
        existing_sources = store.latest_by_id("sources", "source_id")
        if source_id not in existing_sources:
            store.append("sources", Source(
                source_id=source_id, institution_id=inst.institution_id,
                source_path=rss_fetch["canonical_url"], source_type="official",
                acquisition_method="direct_http", status="ACTIVE",
            ).to_dict())
        xml_text = rss_fetch["bytes"].decode("utf-8", errors="replace")
        items = parse_rss_items(xml_text)
        result["documents_acquired"] = len(items) if items else 0
        if not items:
            result["failure_stage"] = "DOCUMENT"
            result["failure_reason"] = "no_rss_items"
            return result
        max_items = min(max_items, len(items))
        for item in items[:max_items]:
            if not item.get("link"):
                continue
            doc_result = process_one_document(
                store, adapter, source_id, source_name,
                inst.institution_id, event_type, patterns, item, run_id,
            )
            result["documents_processed"] += 1
            result["facts_extracted"] += doc_result.get("facts_count", 0)
            if doc_result.get("facts_count", 0) > 0:
                result["documents_with_facts"] += 1
            if doc_result.get("event"):
                result["documents_with_events"] += 1
                result["events_detected"] += 1
            if doc_result.get("io_id"):
                result["intelligence_objects"].append(doc_result["io_id"])
            if doc_result.get("error"):
                result["errors"].append(doc_result["error"])
    except Exception as e:
        result["errors"].append({"stage": "PIPELINE", "message": str(e)[:200]})
        if not result["failure_stage"]:
            result["failure_stage"] = "PIPELINE"
            result["failure_reason"] = str(e)[:100]
    return result


def run_real_corpus_expansion(max_items_per_source: int = 30):
    """Expand real corpus by processing more items from already-working sources."""
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Real Corpus Expansion (max_items={max_items_per_source})")
    print(f"{'='*70}")

    # Copy scale_50_store as the base (it already has 60 real IOs)
    store_root = "real_corpus_store"
    if Path(store_root).exists():
        shutil.rmtree(store_root)
    shutil.copytree("scale_50_store", store_root)

    store = CachedStore(AppendOnlyStore(store_root))

    # Count existing real IOs
    existing_events = sum(1 for _ in store.iter("events"))
    print(f"\n  Starting from scale_50_store: {existing_events} existing events")

    sources = load_known_working_sources()
    print(f"  Loaded {len(sources)} known working sources")

    registry = build_institution_registry(sources)
    # Create adapter with shorter timeout (override the default 60s)
    from intelligence_core.acquisition import Transport
    transport = Transport()
    # Monkey-patch the get method to use 15s timeout
    original_get = transport.get
    def fast_get(url, timeout=15):
        return original_get(url, timeout=timeout)
    transport.get = fast_get
    adapter = DirectHttpAdapter(transport=transport)
    run_id = f"real-corpus-{int(time.time())}"

    results = []
    for i, src in enumerate(sources):
        print(f"\n  [{i+1}/{len(sources)}] {src['source_id']} ({src['website']})...")
        result = process_one_source_real(
            store, registry, adapter, src, run_id,
            max_items=max_items_per_source,
        )
        results.append(result)
        ios = len(result["intelligence_objects"])
        print(f"    acq={'Y' if result.get('acquisition') else 'N'} "
              f"docs_proc={result['documents_processed']:2d} "
              f"facts={result['facts_extracted']:3d} "
              f"ios={ios:3d} "
              f"err={result['failure_reason'] or '-'}")

    # Count total real IOs
    total_events = sum(1 for _ in store.iter("events"))
    new_events = total_events - existing_events
    print(f"\n  New events added: {new_events}")
    print(f"  Total events: {total_events}")

    # Save results
    out = {
        "schema_version": "1.0-real",
        "run_id": run_id,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store_root": store_root,
        "max_items_per_source": max_items_per_source,
        "starting_events": existing_events,
        "final_events": total_events,
        "new_events": new_events,
        "results": results,
    }
    out_path = Path(__file__).resolve().parent / "real_corpus_expansion_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return out


if __name__ == "__main__":
    result = run_real_corpus_expansion(max_items_per_source=30)
    if result["final_events"] >= 100:
        print(f"\n  ✓ PASS: {result['final_events']} real events (≥100 target)")
    else:
        print(f"\n  ⚠ {result['final_events']} real events (< 100 target)")
