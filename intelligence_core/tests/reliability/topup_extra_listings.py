"""V2-Real §3 — Round 5: Use real URLs from existing store as additional document sources.

Each event in the store has a document.canonical_url. If we fetch NEW URLs
(from additional pages/listings on the same source), we get NEW documents
and potentially NEW IOs.

Strategy:
  - For each high-yield source, fetch a DIFFERENT listing page or sitemap
  - Try URLs like:
    - https://www.sec.gov/cgi-bin/browse-edgar (list of filings)
    - https://www.fca.org.uk/news/news-stories (different from /news/rss.xml)
    - https://www.esma.europa.eu/news-events/news (different listing)
  - Each new listing provides NEW document URLs
"""
from __future__ import annotations
import json
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.acquisition import DirectHttpAdapter, Transport, parse_rss_items
from intelligence_core.contracts import Source, Document
from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.expand_real_corpus_parallel import (
    process_one_source_parallel,
)

# Additional listing URLs for already-working sources
EXTRA_LISTING_URLS = [
    # SEC has multiple RSS feeds
    {"source_id": "imp-sec-litigation", "name": "SEC Litigation",
     "class": "Financial Regulator", "type": "regulator", "country": "US",
     "website": "https://www.sec.gov/rss/litigation/litreleases.xml", "max_items": 50},
    {"source_id": "imp-sec-news", "name": "SEC News",
     "class": "Financial Regulator", "type": "regulator", "country": "US",
     "website": "https://www.sec.gov/rss/news/pressreleases.xml", "max_items": 50},
    # ECB monetary policy decisions
    {"source_id": "imp-ecb-mp", "name": "ECB Monetary Policy",
     "class": "Central Bank", "type": "central_bank", "country": "EU",
     "website": "https://www.ecb.europa.eu/rss/pressreferences.html", "max_items": 50},
    # FCA news stories (different feed)
    {"source_id": "imp-fca-stories", "name": "FCA News Stories",
     "class": "Financial Regulator", "type": "regulator", "country": "UK",
     "website": "https://www.fca.org.uk/news/news-stories", "max_items": 50},
    # ESMA news listing
    {"source_id": "imp-esma-news", "name": "ESMA News",
     "class": "Financial Regulator", "type": "regulator", "country": "EU",
     "website": "https://www.esma.europa.eu/rss/news.xml", "max_items": 50},
    # Federal Reserve enforcement
    {"source_id": "imp-fed-enf", "name": "Fed Reserve Enforcement",
     "class": "Central Bank", "type": "central_bank", "country": "US",
     "website": "https://www.federalreserve.gov/feeds/enforcement.xml", "max_items": 50},
    # CFTC enforcement
    {"source_id": "imp-cftc-enf", "name": "CFTC Enforcement",
     "class": "Financial Regulator", "type": "regulator", "country": "US",
     "website": "https://www.cftc.gov/PressRoom/PressReleases/rss", "max_items": 50},
    # BEA newsroom
    {"source_id": "imp-bea-news", "name": "BEA Newsroom",
     "class": "Statistical Agency", "type": "statistics", "country": "US",
     "website": "https://www.bea.gov/news?format=feed&type=news", "max_items": 50},
    # HM Treasury speeches
    {"source_id": "imp-hm-speeches", "name": "HM Treasury Speeches",
     "class": "Ministry of Finance", "type": "ministry", "country": "UK",
     "website": "https://www.gov.uk/government/organisations/hm-treasury.atom",
     "max_items": 50},
    # Eurostat news
    {"source_id": "imp-eurostat-news", "name": "Eurostat News",
     "class": "Statistical Agency", "type": "statistics", "country": "EU",
     "website": "https://ec.europa.eu/eurostat/api/dissemination/catalogue/news/rss",
     "max_items": 50},
    # Bank of England news
    {"source_id": "imp-boe-news", "name": "BoE News",
     "class": "Central Bank", "type": "central_bank", "country": "UK",
     "website": "https://www.bankofengland.co.uk/news/rss",
     "max_items": 50},
]


def run_extra_listings():
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Round 5: Extra listing URLs for high-yield sources")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore("real_corpus_store"))
    existing = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing}")

    registry = InstitutionRegistry()
    for s in EXTRA_LISTING_URLS:
        from urllib.parse import urlsplit
        from intelligence_core.contracts import Institution
        website = s["website"]
        parts = urlsplit(website)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            inst_id = s["source_id"].upper()
            inst = Institution(
                institution_id=inst_id, legal_entity=s["name"],
                jurisdiction=s["country"], institutional_class=s["class"],
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                registry.add_institution(inst)
            except Exception:
                pass

    run_id = f"real-list-{int(time.time())}"
    t_start = time.perf_counter()

    def worker(idx, src):
        max_items = src.get("max_items", 50)
        src_clean = {k: v for k, v in src.items() if k != "max_items"}
        result = process_one_source_parallel(store, registry, src_clean, run_id, max_items=max_items)
        return idx, result

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(worker, i, src) for i, src in enumerate(EXTRA_LISTING_URLS)]
        for future in as_completed(futures):
            try:
                idx, result = future.result(timeout=80)
                n_ios = len(result["intelligence_objects"])
                src_id = EXTRA_LISTING_URLS[idx]["source_id"]
                acq = "Y" if result.get("acquisition") else "N"
                docs = result.get("documents_acquired", 0)
                print(f"  [{idx+1:2d}/{len(EXTRA_LISTING_URLS)}] {src_id:<25} "
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
    total = run_extra_listings()
    if total >= 100:
        print(f"\n  ✓ PASS: {total} real events (≥100)")
    else:
        print(f"\n  ⚠ {total} real events (< 100)")
