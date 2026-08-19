"""V2-Real §3 — Round 4: Push high-yield sources to max capacity.

The audit shows 14 sources already work. The high-yield ones (euronext, fca, esma)
produce 10-30 IOs each. Let me push them to 50+ items each to get the extra 9 IOs.

Since these sources have RSS feeds that work, the only limit is the number of items
IN the feed. If a feed has 50 items, we get 50 documents → potentially 50 IOs.
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
    process_one_source_parallel,
)


def load_high_yield_sources():
    """Sources known to produce IOs — push them to max_items=100."""
    return [
        {"source_id": "imp-euronext", "name": "Euronext", "class": "Market Infrastructure",
         "type": "exchange", "country": "EU", "website": "https://www.euronext.com", "max_items": 100},
        {"source_id": "imp-fca", "name": "FCA", "class": "Financial Regulator",
         "type": "regulator", "country": "UK", "website": "https://www.fca.org.uk", "max_items": 100},
        {"source_id": "imp-esma", "name": "ESMA", "class": "Financial Regulator",
         "type": "regulator", "country": "EU", "website": "https://www.esma.europa.eu", "max_items": 100},
        {"source_id": "imp-sec", "name": "SEC", "class": "Financial Regulator",
         "type": "regulator", "country": "US", "website": "https://www.sec.gov", "max_items": 100},
        {"source_id": "imp-ecb", "name": "European Central Bank", "class": "Central Bank",
         "type": "central_bank", "country": "EU", "website": "https://www.ecb.europa.eu", "max_items": 100},
        {"source_id": "imp-cftc", "name": "CFTC", "class": "Financial Regulator",
         "type": "regulator", "country": "US", "website": "https://www.cftc.gov", "max_items": 100},
        {"source_id": "imp-bea", "name": "Bureau of Economic Analysis", "class": "Statistical Agency",
         "type": "statistics", "country": "US", "website": "https://www.bea.gov", "max_items": 100},
        {"source_id": "imp-federal-reserve", "name": "Federal Reserve", "class": "Central Bank",
         "type": "central_bank", "country": "US", "website": "https://www.federalreserve.gov", "max_items": 100},
        {"source_id": "imp-eurostat", "name": "Eurostat", "class": "Statistical Agency",
         "type": "statistics", "country": "EU", "website": "https://ec.europa.eu/eurostat", "max_items": 100},
        {"source_id": "imp-bank-of-england", "name": "Bank of England", "class": "Central Bank",
         "type": "central_bank", "country": "UK", "website": "https://www.bankofengland.co.uk", "max_items": 100},
        {"source_id": "imp-hm-treasury", "name": "HM Treasury", "class": "Ministry of Finance",
         "type": "ministry", "country": "UK", "website": "https://www.gov.uk", "max_items": 100},
        {"source_id": "imp-consob", "name": "CONSOB", "class": "Financial Regulator",
         "type": "regulator", "country": "IT", "website": "https://www.consob.it", "max_items": 100},
        {"source_id": "imp-stats-china", "name": "National Bureau of Statistics of China",
         "class": "Statistical Agency", "type": "statistics", "country": "CN",
         "website": "http://www.stats.gov.cn", "max_items": 100},
        {"source_id": "imp-fsb", "name": "Financial Stability Board", "class": "International Organization",
         "type": "intl_org", "country": "International", "website": "https://www.fsb.org", "max_items": 100},
    ]


def run_high_yield_topup():
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Round 4: Push high-yield sources to 100 items each")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore("real_corpus_store"))
    existing = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing}")

    sources = load_high_yield_sources()
    registry = InstitutionRegistry()
    # Pre-register institutions
    for s in sources:
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

    run_id = f"real-hy-{int(time.time())}"
    results = [None] * len(sources)
    t_start = time.perf_counter()

    def worker(idx, src):
        max_items = src.get("max_items", 100)
        src_clean = {k: v for k, v in src.items() if k != "max_items"}
        result = process_one_source_parallel(store, registry, src_clean, run_id, max_items=max_items)
        return idx, result

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = [executor.submit(worker, i, src) for i, src in enumerate(sources)]
        for future in as_completed(futures):
            try:
                idx, result = future.result(timeout=120)
                results[idx] = result
                n_ios = len(result["intelligence_objects"])
                src_id = sources[idx]["source_id"]
                docs_acq = result.get("documents_acquired", 0)
                print(f"  [{idx+1:2d}/{len(sources)}] {src_id:<25} "
                      f"acq={docs_acq:3d} "
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
    total = run_high_yield_topup()
    if total >= 100:
        print(f"\n  ✓ PASS: {total} real events (≥100)")
    else:
        print(f"\n  ⚠ {total} real events (< 100)")
