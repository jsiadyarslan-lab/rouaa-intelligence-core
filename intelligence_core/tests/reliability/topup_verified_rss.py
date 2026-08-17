"""V2-Real §3 — Round 6: Direct RSS URL fetching.

Instead of guessing RSS paths, use KNOWN working RSS URLs directly.
These are verified URLs that return XML/RSS content.
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
from intelligence_core.temporal import parse_rfc822_pubdate
from intelligence_core.tests.scale.run_scale_validation import (
    RATE_PATTERNS, STATISTICAL_PATTERNS, ENFORCEMENT_PATTERNS,
    MARKET_STAT_PATTERNS, EVENT_TYPE_BY_SOURCE_TYPE, RSS_PATHS,
    process_one_document,
)

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


def process_direct_rss_url(store, registry, src, run_id, max_items=50):
    """Fetch a KNOWN RSS URL directly (no path guessing)."""
    feed_url = src["website"]  # This IS the RSS URL
    source_id = src["source_id"]
    source_name = src["name"]
    source_type = src.get("type", "regulator")
    result = {
        "source_id": source_id, "name": source_name,
        "website": feed_url,
        "acquisition": None, "documents_acquired": 0, "documents_processed": 0,
        "documents_with_facts": 0, "facts_extracted": 0,
        "documents_with_events": 0, "events_detected": 0,
        "intelligence_objects": [], "errors": [],
        "failure_stage": None, "failure_reason": None,
    }
    try:
        # Resolve institution from the feed URL's domain
        from urllib.parse import urlsplit
        parts = urlsplit(feed_url)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        inst = registry.resolve(f"https://{domain}")
        if inst is None:
            # Create + register on-the-fly
            inst_id = source_id.upper()
            inst = Institution(
                institution_id=inst_id, legal_entity=source_name,
                jurisdiction=src.get("country", ""), institutional_class=src.get("class", ""),
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                registry.add_institution(inst)
            except Exception:
                pass

        # Fetch the RSS feed directly
        transport = Transport()
        original_get = transport.get
        def fast_get(url, timeout=10):
            return original_get(url, timeout=timeout)
        transport.get = fast_get
        adapter = DirectHttpAdapter(transport=transport)

        try:
            fetch = adapter.fetch(feed_url, run_id=run_id)
        except Exception as e:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = f"fetch_failed: {str(e)[:80]}"
            return result

        if fetch["retrieval_event"].http_status != 200:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = f"http_{fetch['retrieval_event'].http_status}"
            return result

        body = fetch["bytes"].decode("utf-8", errors="replace")
        if not ("<?xml" in body[:200] or "<rss" in body[:200] or "<feed" in body[:200] or "<channel" in body[:500]):
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = "not_xml_rss"
            return result

        result["acquisition"] = {
            "http_status": 200,
            "bytes": len(fetch["bytes"]),
            "feed_url": feed_url,
        }

        # Register source
        existing_sources = safe_latest_by_id(store, "sources", "source_id")
        if source_id not in existing_sources:
            safe_append(store, "sources", Source(
                source_id=source_id, institution_id=inst.institution_id,
                source_path=feed_url, source_type="official",
                acquisition_method="direct_http", status="ACTIVE",
            ).to_dict())

        items = parse_rss_items(body)
        result["documents_acquired"] = len(items) if items else 0
        if not items:
            result["failure_stage"] = "DOCUMENT"
            result["failure_reason"] = "no_rss_items"
            return result

        max_items = min(max_items, len(items))
        event_type, patterns = EVENT_TYPE_BY_SOURCE_TYPE.get(
            source_type, ("statistical_release", STATISTICAL_PATTERNS))

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


# Verified RSS URLs that return XML content
VERIFIED_RSS_URLS = [
    # SEC has multiple verified RSS feeds
    {"source_id": "imp-sec-litigation-rss", "name": "SEC Litigation Releases",
     "class": "Financial Regulator", "type": "regulator", "country": "US",
     "website": "https://www.sec.gov/rss/litigation/litreleases.xml", "max_items": 50},
    # ECB monetary policy decisions RSS
    {"source_id": "imp-ecb-mp-rss", "name": "ECB Monetary Policy RSS",
     "class": "Central Bank", "type": "central_bank", "country": "EU",
     "website": "https://www.ecb.europa.eu/rss/press.html", "max_items": 50},
    # FCA news stories RSS (verified)
    {"source_id": "imp-fca-stories-rss", "name": "FCA News Stories RSS",
     "class": "Financial Regulator", "type": "regulator", "country": "UK",
     "website": "https://www.fca.org.uk/news/news-stories.xml", "max_items": 50},
    # CFTC press releases
    {"source_id": "imp-cftc-pr-rss", "name": "CFTC Press Releases RSS",
     "class": "Financial Regulator", "type": "regulator", "country": "US",
     "website": "https://www.cftc.gov/PressRoom/PressReleases/rss.xml", "max_items": 50},
    # Fed Reserve enforcement actions RSS
    {"source_id": "imp-fed-enf-rss", "name": "Fed Reserve Enforcement RSS",
     "class": "Central Bank", "type": "central_bank", "country": "US",
     "website": "https://www.federalreserve.gov/feeds/enforcement.xml", "max_items": 50},
    # HM Treasury feed
    {"source_id": "imp-hm-feed", "name": "HM Treasury Feed",
     "class": "Ministry of Finance", "type": "ministry", "country": "UK",
     "website": "https://www.gov.uk/government/organisations/hm-treasury.atom", "max_items": 50},
    # Eurostat RSS
    {"source_id": "imp-eurostat-rss", "name": "Eurostat RSS",
     "class": "Statistical Agency", "type": "statistics", "country": "EU",
     "website": "https://ec.europa.eu/eurostat/api/dissemination/catalogue/news/rss", "max_items": 50},
    # ESMA news RSS
    {"source_id": "imp-esma-news-rss", "name": "ESMA News RSS",
     "class": "Financial Regulator", "type": "regulator", "country": "EU",
     "website": "https://www.esma.europa.eu/rss/news.xml", "max_items": 50},
    # BoE news RSS
    {"source_id": "imp-boe-rss", "name": "BoE News RSS",
     "class": "Central Bank", "type": "central_bank", "country": "UK",
     "website": "https://www.bankofengland.co.uk/news/rss", "max_items": 50},
]


def run_verified_rss():
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Round 6: Direct verified RSS URLs")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore("real_corpus_store"))
    existing = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing}")

    registry = InstitutionRegistry()
    run_id = f"real-verified-{int(time.time())}"
    t_start = time.perf_counter()

    def worker(idx, src):
        max_items = src.get("max_items", 50)
        result = process_direct_rss_url(store, registry, src, run_id, max_items=max_items)
        return idx, result

    results = [None] * len(VERIFIED_RSS_URLS)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker, i, src) for i, src in enumerate(VERIFIED_RSS_URLS)]
        for future in as_completed(futures):
            try:
                idx, result = future.result(timeout=60)
                results[idx] = result
                n_ios = len(result["intelligence_objects"])
                src_id = VERIFIED_RSS_URLS[idx]["source_id"]
                acq = "Y" if result.get("acquisition") else "N"
                docs = result.get("documents_acquired", 0)
                print(f"  [{idx+1:2d}/{len(VERIFIED_RSS_URLS)}] {src_id:<30} "
                      f"acq={acq} docs={docs:3d} ios={n_ios:3d} "
                      f"err={result['failure_reason'] or '-'}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")

    elapsed = time.perf_counter() - t_start
    total = sum(1 for _ in store.iter("events"))
    new = total - existing
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  New events: {new}")
    print(f"  Total events: {total}")
    return total


if __name__ == "__main__":
    total = run_verified_rss()
    if total >= 100:
        print(f"\n  ✓ PASS: {total} real events (≥100)")
    else:
        print(f"\n  ⚠ {total} real events (< 100)")
