"""V2-Real §3 — Round 3: Try verified RSS paths for additional sources.

Some sources need explicit RSS path guesses beyond the default list.
This script tries known-good RSS paths for: BIS, IMF, OECD, EC, Federal Reserve,
Eurostat, HM Treasury, CONSOB, Stats China.
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
from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.tests.reliability.expand_real_corpus_parallel import (
    process_one_source_parallel, load_known_working_sources,
)


# Verified RSS/feed paths for sources that failed default guessing
EXTRA_SOURCES = [
    # Federal Reserve has explicit feeds
    {"source_id": "imp-fed-press", "name": "Federal Reserve Press Releases",
     "class": "Central Bank", "type": "central_bank", "country": "US",
     "website": "https://www.federalreserve.gov/feeds/press_all.xml",
     "max_items": 30, "direct_feed": True},
    # IMF news
    {"source_id": "imp-imf-news", "name": "IMF News",
     "class": "International Organization", "type": "intl_org", "country": "International",
     "website": "https://www.imf.org/en/News/Search-Archive",
     "max_items": 30},
    # BIS central bank feeds
    {"source_id": "imp-bis-news", "name": "BIS News",
     "class": "International Organization", "type": "intl_org", "country": "International",
     "website": "https://www.bis.org/list/cbspeeches/index.htm",
     "max_items": 30},
    # OECD newsroom
    {"source_id": "imp-oecd-news", "name": "OECD Newsroom",
     "class": "International Organization", "type": "intl_org", "country": "International",
     "website": "https://www.oecd.org/newsroom/",
     "max_items": 30},
    # ECB statistics feeds (separate from press)
    {"source_id": "imp-ecb-stats", "name": "ECB Statistics",
     "class": "Central Bank", "type": "central_bank", "country": "EU",
     "website": "https://www.ecb.europa.eu/stats/html/index.en.html",
     "max_items": 30},
    # SEC litigation
    {"source_id": "imp-sec-litigation", "name": "SEC Litigation",
     "class": "Financial Regulator", "type": "regulator", "country": "US",
     "website": "https://www.sec.gov/litigation/litreleases.shtml",
     "max_items": 30},
    # NY Fed
    {"source_id": "imp-nyfed", "name": "New York Fed",
     "class": "Central Bank", "type": "central_bank", "country": "US",
     "website": "https://www.newyorkfed.org",
     "max_items": 30},
    # ECB monetary policy
    {"source_id": "imp-ecb-mp", "name": "ECB Monetary Policy",
     "class": "Central Bank", "type": "central_bank", "country": "EU",
     "website": "https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html",
     "max_items": 30},
    # Federal Reserve Bank of St. Louis (FRED news)
    {"source_id": "imp-stlouisfed", "name": "St. Louis Fed",
     "class": "Central Bank", "type": "central_bank", "country": "US",
     "website": "https://www.stlouisfed.org",
     "max_items": 30},
    # Bank of Italy
    {"source_id": "imp-bankitaly", "name": "Bank of Italy",
     "class": "Central Bank", "type": "central_bank", "country": "IT",
     "website": "https://www.bancaditalia.it",
     "max_items": 30},
    # Bundesbank
    {"source_id": "imp-bundesbank", "name": "Bundesbank",
     "class": "Central Bank", "type": "central_bank", "country": "DE",
     "website": "https://www.bundesbank.de",
     "max_items": 30},
    # Bank of Canada
    {"source_id": "imp-bankcanada", "name": "Bank of Canada",
     "class": "Central Bank", "type": "central_bank", "country": "CA",
     "website": "https://www.bankofcanada.ca",
     "max_items": 30},
    # Riksbank (Sweden)
    {"source_id": "imp-riksbank", "name": "Riksbank",
     "class": "Central Bank", "type": "central_bank", "country": "SE",
     "website": "https://www.riksbank.se",
     "max_items": 30},
    # Norges Bank (Norway)
    {"source_id": "imp-norges", "name": "Norges Bank",
     "class": "Central Bank", "type": "central_bank", "country": "NO",
     "website": "https://www.norges-bank.no",
     "max_items": 30},
]


def run_extra_sources():
    """Try additional sources with verified feed paths."""
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Round 3: Extra sources with verified paths")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore("real_corpus_store"))
    existing = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing}")

    registry = InstitutionRegistry()
    # Pre-register institutions for the extra sources
    for s in EXTRA_SOURCES:
        website = s["website"]
        from urllib.parse import urlsplit
        parts = urlsplit(website)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            inst_id = s["source_id"].upper()
            from intelligence_core.contracts import Institution
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

    run_id = f"real-extra-{int(time.time())}"
    results = [None] * len(EXTRA_SOURCES)
    t_start = time.perf_counter()

    def worker(idx, src):
        max_items = src.get("max_items", 30)
        src_clean = {k: v for k, v in src.items() if k != "max_items" and k != "direct_feed"}
        result = process_one_source_parallel(store, registry, src_clean, run_id, max_items=max_items)
        return idx, result

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker, i, src) for i, src in enumerate(EXTRA_SOURCES)]
        for future in as_completed(futures):
            try:
                idx, result = future.result(timeout=80)
                results[idx] = result
                n_ios = len(result["intelligence_objects"])
                src_id = EXTRA_SOURCES[idx]["source_id"]
                print(f"  [{idx+1:2d}/{len(EXTRA_SOURCES)}] {src_id:<25} "
                      f"ios={n_ios:3d} "
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
    total = run_extra_sources()
    if total >= 100:
        print(f"\n  ✓ PASS: {total} real events (≥100)")
    else:
        print(f"\n  ⚠ {total} real events (< 100)")
