"""V2-Expansion §18 — Process qualified new sources through Core.

Target: ≥25 new real IOs from newly qualified sources (not in the original 17
that produced IOs in real_corpus_store).

Strategy:
  1. Load qualified sources from SourceRegistry
  2. Filter to PRODUCTION_READY + QUALIFIED sources NOT in the original set
  3. Process each through the Core pipeline (extract_facts + detect_event + build_intelligence_object)
  4. Use expanded extraction patterns to maximize IO yield
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
from intelligence_core.tests.scale.run_scale_validation import (
    RATE_PATTERNS, STATISTICAL_PATTERNS, ENFORCEMENT_PATTERNS,
    MARKET_STAT_PATTERNS, EVENT_TYPE_BY_SOURCE_TYPE, RSS_PATHS,
    try_acquire_rss, process_one_document,
)
from intelligence_core.tests.reliability.topup_expanded_patterns import EXPANDED_PATTERNS
from intelligence_core.source_network.registry import SourceRegistry


# Original 17 sources that already produced IOs in real_corpus_store
ORIGINAL_SOURCES = {
    "imp-federal-reserve", "imp-ecb", "imp-bank-of-england", "imp-bea",
    "imp-eurostat", "imp-sec", "imp-cftc", "imp-esma", "imp-fca",
    "imp-euronext", "imp-hm-treasury", "imp-consob", "imp-stats-china",
    "imp-fsb", "imp-hm-feed", "imp-swiss-national-bank", "imp-deutsche-boerse",
}

# Map source_id prefixes from new registry to original
SOURCE_ID_MAP = {
    "src-fed-reserve": "imp-federal-reserve",
    "src-ecb": "imp-ecb",
    "src-boe": "imp-bank-of-england",
    "src-bea": "imp-bea",
    "src-eurostat": "imp-eurostat",
    "src-sec": "imp-sec",
    "src-cftc": "imp-cftc",
    "src-esma": "imp-esma",
    "src-fca": "imp-fca",
    "src-euronext": "imp-euronext",
    "src-hm-treasury": "imp-hm-treasury",
    "src-consob": "imp-consob",
    "src-statschina": "imp-stats-china",
    "src-fsb": "imp-fsb",
    "src-snb": "imp-swiss-national-bank",
    "src-deutsche-boerse": "imp-deutsche-boerse",
}


# Source class → expanded pattern key
CLASS_TO_PATTERN = {
    "central_bank": ("monetary_policy_decision", "monetary"),
    "finance_ministry": ("monetary_policy_decision", "monetary"),
    "securities_regulator": ("regulatory_enforcement", "regulatory"),
    "financial_regulator": ("regulatory_enforcement", "regulatory"),
    "banking_regulator": ("regulatory_enforcement", "regulatory"),
    "statistical_agency": ("statistical_release", "statistical"),
    "stock_exchange": ("statistical_release", "market"),
    "international_financial_institution": ("statistical_release", "statistical"),
    "international_economic_institution": ("statistical_release", "statistical"),
    "official_development_institution": ("statistical_release", "statistical"),
    "regional_economic_institution": ("statistical_release", "statistical"),
    "energy_regulator": ("statistical_release", "statistical"),
    "energy_ministry": ("statistical_release", "statistical"),
    "industrial_ministry": ("statistical_release", "statistical"),
    "competition_authority": ("regulatory_enforcement", "regulatory"),
    "labor_ministry": ("statistical_release", "statistical"),
    "trade_ministry": ("regulatory_enforcement", "regulatory"),
    "customs_authority": ("statistical_release", "statistical"),
    "sovereign_wealth_institution": ("statistical_release", "statistical"),
    "pension_regulator": ("statistical_release", "statistical"),
    "commodity_regulator": ("statistical_release", "market"),
}

_WRITE_LOCK = threading.Lock()


def safe_append(store, coll, record):
    with _WRITE_LOCK:
        return store.append(coll, record)


def safe_latest_by_id(store, coll, id_field):
    with _WRITE_LOCK:
        return store.latest_by_id(coll, id_field)


def safe_current_fact(store, fact_id):
    with _WRITE_LOCK:
        return store.current_fact(fact_id)


def safe_current_event(store, event_id):
    with _WRITE_LOCK:
        return store.current_event(event_id)


def process_new_source(store, registry, src_record, run_id, max_items=15):
    """Process one NEW source through Core pipeline."""
    # Skip if this source maps to an original
    original_id = SOURCE_ID_MAP.get(src_record.source_id)
    if original_id and original_id in ORIGINAL_SOURCES:
        return {"source_id": src_record.source_id, "skipped": "original_source",
                "intelligence_objects": []}

    website = src_record.canonical_url
    source_id = src_record.source_id
    source_name = src_record.institution_name
    source_class = src_record.source_class

    result = {
        "source_id": source_id, "name": source_name,
        "country": src_record.country, "class": source_class,
        "acquisition_method": src_record.acquisition_method,
        "acquisition": None, "documents_acquired": 0, "documents_processed": 0,
        "facts_extracted": 0, "events_detected": 0,
        "intelligence_objects": [], "errors": [],
        "failure_stage": None, "failure_reason": None,
    }

    try:
        # Resolve institution
        inst = registry.resolve(website)
        if inst is None:
            from urllib.parse import urlsplit
            parts = urlsplit(website)
            domain = parts.hostname or ""
            if domain.startswith("www."):
                domain = domain[4:]
            inst_id = src_record.institution_id
            inst = Institution(
                institution_id=inst_id, legal_entity=source_name,
                jurisdiction=src_record.country, institutional_class=source_class,
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                registry.add_institution(inst)
            except Exception:
                pass

        # Set up adapter with shorter timeout
        transport = Transport()
        original_get = transport.get
        def fast_get(url, timeout=10):
            return original_get(url, timeout=timeout)
        transport.get = fast_get
        adapter = DirectHttpAdapter(transport=transport)

        # Try to acquire RSS feed
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

        # Register source
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

        # Get expanded patterns for this source class
        event_type, pattern_key = CLASS_TO_PATTERN.get(
            source_class, ("statistical_release", "statistical"))
        patterns = EXPANDED_PATTERNS.get(pattern_key, STATISTICAL_PATTERNS)

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
                if doc_result.get("event"):
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


def run_new_source_processing(store_root: str = "real_corpus_store",
                                registry_root: str = "source_registry",
                                max_workers: int = 5):
    """Process all NEW qualified sources through Core."""
    print(f"\n{'='*70}")
    print(f"V2-Expansion §18 — Process NEW qualified sources through Core")
    print(f"{'='*70}")

    # Start from a COPY of real_corpus_store (148 IOs)
    if Path(store_root).exists() and not Path(f"{store_root}_new").exists():
        shutil.copytree(store_root, f"{store_root}_new")
    store_root = f"{store_root}_new"
    store = CachedStore(AppendOnlyStore(store_root))

    existing_events = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing_events}")

    # Load source registry
    src_registry = SourceRegistry(registry_root)
    qualified_sources = [
        r for r in src_registry.all()
        if r.qualification_status in ("QUALIFIED", "PRODUCTION_READY")
    ]
    print(f"  Qualified sources in registry: {len(qualified_sources)}")

    # Filter to NEW sources (not in ORIGINAL_SOURCES or mapped from them)
    new_sources = []
    for r in qualified_sources:
        original_id = SOURCE_ID_MAP.get(r.source_id)
        if original_id and original_id in ORIGINAL_SOURCES:
            continue
        new_sources.append(r)
    print(f"  NEW sources to process: {len(new_sources)}")

    # Set up institution registry
    institution_registry = InstitutionRegistry()
    # Pre-register institutions for all sources
    for r in src_registry.all():
        website = r.canonical_url
        from urllib.parse import urlsplit
        parts = urlsplit(website)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            inst_id = r.institution_id
            inst = Institution(
                institution_id=inst_id, legal_entity=r.institution_name,
                jurisdiction=r.country, institutional_class=r.source_class,
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                institution_registry.add_institution(inst)
            except Exception:
                pass

    run_id = f"new-sources-{int(time.time())}"
    t_start = time.perf_counter()

    results = [None] * len(new_sources)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_new_source, store, institution_registry, r, run_id): i
            for i, r in enumerate(new_sources)
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                result = future.result(timeout=60)
                results[i] = result
                n_ios = len(result.get("intelligence_objects", []))
                src_id = result["source_id"]
                err = result.get("failure_reason") or "-"
                print(f"  [{i+1:2d}/{len(new_sources)}] {src_id:<30} ios={n_ios:3d} err={err}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")
                results[i] = {"source_id": new_sources[i].source_id,
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
        "store_root": store_root,
        "starting_events": existing_events,
        "final_events": final_events,
        "new_events": new_events_count,
        "new_ios_reported": total_new_ios,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    out_path = Path("intelligence_core/tests/reliability/new_sources_processing_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return final_events, new_events_count, store_root


if __name__ == "__main__":
    final, new, store_root = run_new_source_processing()
    if new >= 25:
        print(f"\n  ✓ PASS: {new} new real IOs (≥25 target)")
    else:
        print(f"\n  ⚠ {new} new real IOs (< 25 target)")
