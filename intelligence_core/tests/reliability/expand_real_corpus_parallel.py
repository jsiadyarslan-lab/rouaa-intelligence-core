"""V2-Real §3 (parallel) — Expand REAL corpus in parallel for speed.

Processes multiple sources concurrently to overcome the serial HTTP bottleneck.
Each source gets max_items=30. Documents are fetched with a 10s timeout.
"""
from __future__ import annotations
import json
import os
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
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


_WRITE_LOCK = threading.Lock()


def safe_append(store, collection, record):
    with _WRITE_LOCK:
        return store.append(collection, record)


def safe_latest_by_id(store, collection, id_field):
    with _WRITE_LOCK:
        return store.latest_by_id(collection, id_field)


def safe_current_fact(store, fact_id):
    with _WRITE_LOCK:
        return store.current_fact(fact_id)


def safe_current_event(store, event_id):
    with _WRITE_LOCK:
        return store.current_event(store, event_id) if False else store.current_event(event_id)


def process_one_source_parallel(store, registry, src, run_id, max_items=30):
    """Process one source — uses shared write lock for store mutations."""
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

        # Use a short-timeout transport
        transport = Transport()
        original_get = transport.get
        def fast_get(url, timeout=10):
            return original_get(url, timeout=timeout)
        transport.get = fast_get
        adapter = DirectHttpAdapter(transport=transport)

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
        existing_sources = safe_latest_by_id(store, "sources", "source_id")
        if source_id not in existing_sources:
            safe_append(store, "sources", Source(
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

        # Process documents serially within the source (but parallel across sources)
        for item in items[:max_items]:
            if not item.get("link"):
                continue
            try:
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
                result["errors"].append({"stage": "DOC", "message": str(e)[:100]})
    except Exception as e:
        result["errors"].append({"stage": "PIPELINE", "message": str(e)[:200]})
        if not result["failure_stage"]:
            result["failure_stage"] = "PIPELINE"
            result["failure_reason"] = str(e)[:100]
    return result


def load_known_working_sources():
    """Load sources known to be reachable from V1."""
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


def run_parallel_real_corpus(max_items=30, max_workers=5):
    """Process all sources in parallel."""
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Parallel Real Corpus Expansion")
    print(f"  max_items={max_items}/source, max_workers={max_workers}")
    print(f"{'='*70}")

    # Start from scale_50_store (60 real IOs already)
    store_root = "real_corpus_store"
    if Path(store_root).exists():
        shutil.rmtree(store_root)
    shutil.copytree("scale_50_store", store_root)

    store = CachedStore(AppendOnlyStore(store_root))
    existing_events = sum(1 for _ in store.iter("events"))
    print(f"\n  Starting from scale_50_store: {existing_events} existing events")

    sources = load_known_working_sources()
    registry = build_institution_registry(sources)
    run_id = f"real-parallel-{int(time.time())}"

    # Process sources in parallel
    results = [None] * len(sources)
    t_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(process_one_source_parallel, store, registry, src, run_id, max_items): i
            for i, src in enumerate(sources)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result(timeout=120)
                results[idx] = result
                print(f"  [{idx+1:2d}/{len(sources)}] {sources[idx]['source_id']:<30} "
                      f"ios={len(result['intelligence_objects']):3d} "
                      f"err={result['failure_reason'] or '-'}")
            except Exception as e:
                print(f"  [{idx+1:2d}/{len(sources)}] {sources[idx]['source_id']:<30} "
                      f"FAILED: {type(e).__name__}: {str(e)[:80]}")
                results[idx] = {
                    "source_id": sources[idx]["source_id"],
                    "intelligence_objects": [],
                    "failure_stage": "EXECUTOR",
                    "failure_reason": str(e)[:100],
                }

    elapsed = time.perf_counter() - t_start
    print(f"\n  Elapsed: {elapsed:.1f}s")

    # Count final
    total_events = sum(1 for _ in store.iter("events"))
    new_events = total_events - existing_events
    print(f"\n  Starting events: {existing_events}")
    print(f"  New events added: {new_events}")
    print(f"  Total events: {total_events}")

    # Save manifest
    out = {
        "schema_version": "1.0-real-parallel",
        "run_id": run_id,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store_root": store_root,
        "max_items_per_source": max_items,
        "max_workers": max_workers,
        "starting_events": existing_events,
        "final_events": total_events,
        "new_events": new_events,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    out_path = Path(__file__).resolve().parent / "real_corpus_parallel_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Manifest saved to: {out_path}")

    return out


if __name__ == "__main__":
    result = run_parallel_real_corpus(max_items=30, max_workers=7)
    if result["final_events"] >= 100:
        print(f"\n  ✓ PASS: {result['final_events']} real events (≥100 target)")
    else:
        print(f"\n  ⚠ {result['final_events']} real events (< 100 target)")
