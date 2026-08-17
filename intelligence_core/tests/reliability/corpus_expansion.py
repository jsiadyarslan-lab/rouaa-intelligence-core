"""V2 §10 — Corpus expansion: from 61 → 100+ real IOs.

Strategy:
  1. Load WAVE1+WAVE2 candidate sources (244 sources)
  2. Re-run scale validation with max_items=15 (was 3 in V1, 10 in V1's expansion)
  3. Use the existing scale_50_store as a base
  4. Acquire additional items per source to grow the corpus

If real source acquisition cannot reach 100 IOs, we report the actual
maximum defensible corpus and the exact blocker (per directive §10).
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


def normalize_wave1_to_scale_format(candidates):
    """Convert WAVE1 candidates to the format expected by run_scale_validation."""
    sources = []
    class_to_type = {
        "Central Bank": "central_bank",
        "Statistical Agency": "statistics",
        "Financial Regulator": "regulator",
        "Market Infrastructure": "regulator",
        "Ministry of Finance": "ministry",
        "International Organization": "intl_org",
        "Energy Regulator": "energy",
        "Rating Agency": "rating",
        "Commodity Authority": "commodity",
    }
    for c in candidates:
        if c.get("wave1_selection") != "WAVE1_SELECTED":
            continue
        norm_url = c.get("normalized_url") or c.get("official_url") or ""
        if not norm_url:
            continue
        source_id = c.get("master_source_id", "")
        if not source_id:
            # Try institution name
            inst_name = c.get("institution_name", "")
            if inst_name:
                source_id = "src-" + inst_name.lower().replace(" ", "-")[:30]
            else:
                continue
        institutional_class = c.get("institutional_class", "")
        source_type = class_to_type.get(institutional_class, "other")
        sources.append({
            "source_id": source_id,
            "name": c.get("institution_name", source_id),
            "class": institutional_class,
            "type": source_type,
            "country": c.get("country", ""),
            "country_code": c.get("jurisdiction", ""),
            "website": norm_url,
        })
    return sources


def load_or_build_sources():
    """Load sources from WAVE1 manifest."""
    manifest_path = CORE_REPO / "docs" / "evidence" / "WAVE_1_SELECTION_MANIFEST_V2.json"
    with open(manifest_path) as f:
        m = json.load(f)
    candidates = m["candidates"]
    sources = normalize_wave1_to_scale_format(candidates)
    return sources


def process_one_source_expanded(store, registry, adapter, src, run_id, max_items=15):
    """Process one source, expanding to max_items per source (was 3 in V1)."""
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
        event_type, patterns = EVENT_TYPE_BY_SOURCE_TYPE.get(source_type, ("statistical_release", STATISTICAL_PATTERNS))
        rss_fetch = try_acquire_rss(adapter, website)
        if rss_fetch is None:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = "no_rss_feed"
            return result
        result["acquisition"] = {"http_status": rss_fetch["retrieval_event"].http_status,
                                  "bytes": len(rss_fetch["bytes"]), "feed_url": rss_fetch["canonical_url"]}
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
            doc_result = process_one_document(store, adapter, source_id, source_name,
                                               inst.institution_id, event_type, patterns, item, run_id)
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


def run_corpus_expansion(max_items_per_source: int = 15):
    """Expand the corpus by processing max_items_per_source per acquired source."""
    print(f"\n{'='*70}")
    print(f"V2 §10 — Corpus Expansion (max_items={max_items_per_source}/source)")
    print(f"{'='*70}")

    store_root = "scale_100_store"
    if Path(store_root).exists():
        shutil.rmtree(store_root)
    store = CachedStore(AppendOnlyStore(store_root))

    sources = load_or_build_sources()
    print(f"  Loaded {len(sources)} WAVE1 sources")
    print(f"  By class: {defaultdict(int, {s['class']: 0 for s in sources})}")
    by_class = defaultdict(int)
    for s in sources:
        by_class[s["class"]] += 1
    for k, v in by_class.items():
        print(f"    {k}: {v}")

    registry = build_institution_registry(sources)
    adapter = DirectHttpAdapter()
    run_id = f"corpus-expand-{int(time.time())}"

    results = []
    for i, src in enumerate(sources):
        result = process_one_source_expanded(store, registry, adapter, src, run_id,
                                              max_items=max_items_per_source)
        results.append(result)
        ios = len(result["intelligence_objects"])
        print(f"  [{i+1:3d}/{len(sources)}] {src['source_id'][:30]:30} "
              f"acq={'Y' if result.get('acquisition') else 'N'} "
              f"docs={result['documents_processed']:2d} "
              f"facts={result['facts_extracted']:3d} "
              f"ios={ios:3d} "
              f"err={result['failure_reason'] or '-'}")
        # Small delay to be a good HTTP citizen
        time.sleep(0.2)

    metrics = calculate_metrics(results)
    print(f"\n--- Corpus Expansion Results ---")
    print(f"  Sources attempted:    {metrics['sources_attempted']}")
    print(f"  Sources acquired:     {metrics['sources_acquired']}")
    print(f"  Sources with IOs:     {metrics['sources_with_ios']}")
    print(f"  Documents processed:  {metrics['total_documents_processed']}")
    print(f"  Facts extracted:     {metrics['total_facts_extracted']}")
    print(f"  Events detected:     {metrics['total_events_detected']}")
    print(f"  Intelligence Objects: {metrics['total_intelligence_objects']}")

    # Store stats
    print(f"\n--- Store Stats ---")
    for coll in ["events", "facts", "evidence", "documents", "representations", "sources"]:
        n = sum(1 for _ in store.iter(coll))
        print(f"  {coll:<20} {n:>6}")

    # Save results
    out = {
        "schema_version": "2.0",
        "run_id": run_id,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store_root": str(store_root),
        "max_items_per_source": max_items_per_source,
        "metrics": metrics,
        "results": results,
    }
    out_path = Path(__file__).resolve().parent / "corpus_expansion_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return metrics, store


if __name__ == "__main__":
    metrics, store = run_corpus_expansion(max_items_per_source=15)
    if metrics["total_intelligence_objects"] >= 100:
        print(f"\n  ✓ Corpus target MET: {metrics['total_intelligence_objects']} >= 100 IOs")
    else:
        print(f"\n  ⚠ Corpus target NOT MET: {metrics['total_intelligence_objects']} < 100 IOs")
        print(f"    Gap: {100 - metrics['total_intelligence_objects']} IOs short")
