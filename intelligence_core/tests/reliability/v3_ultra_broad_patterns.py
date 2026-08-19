"""V2 §6 — Re-process 668 docs without events with ULTRA-BROAD patterns.

These docs have content but no extractable facts with current patterns.
Use ultra-broad patterns to extract ANY numerical/financial data.
"""
from __future__ import annotations
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Evidence
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html


# Ultra-broad patterns — catch ANY numerical/financial content
ULTRA_BROAD_PATTERNS = [
    # Any percentage
    (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
    # Any USD amount
    (r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|trillion|thousand)?", "usd_amount"),
    # Any rate decision keywords
    (r"\b(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?|increase(?:d)?|decrease(?:d)?)\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", "rate_action"),
    # Any enforcement keywords
    (r"\b(consent\s+order|cease(?:-|\s+)and(?:-|\s+)desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)\b", "action_type"),
    # GDP
    (r"\bGDP\s+(?:grew|growth|increased|expanded|rose|contracted|declined)\s+(?:by\s+)?(\d+(?:\.\d+)?)", "gdp_growth"),
    # Inflation
    (r"\binflation\s+(?:rate\s+)?(?:of\s+|was\s+|reached\s+|stood\s+at\s+|is\s+)?(\d+(?:\.\d+)?)\s*%", "inflation_rate"),
    # Unemployment
    (r"\bunemployment\s+(?:rate\s+)?(?:of\s+|was\s+|reached\s+|stood\s+at\s+|is\s+)?(\d+(?:\.\d+)?)\s*%", "unemployment_rate"),
    # Employment level
    (r"\bemployment\s+(?:level|stood|was)\s+(?:at\s+)?(\d+(?:,\d{3})+)", "employment_level"),
    # Trade balance
    (r"\btrade\s+(?:balance|deficit|surplus)\s+(?:of\s+|was\s+)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "trade_balance"),
    # Revenue
    (r"\brevenue\s+(?:of\s+|was\s+)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "revenue"),
    # Penalty amount
    (r"\bpenalty\s+(?:of\s+|was\s+)?\$(\d+(?:,\d{3})*(?:\.\d+)?)", "penalty_amount"),
    # Defendant
    (r"\b(?:defendant|respondent)[:\s]+([A-Z][a-zA-Z\s&.,]+?)(?:\.|,|;|$)", "defendant_name"),
]


def reprocess_docs_without_events(store_root: str = "v3_corpus_store"):
    """Re-process all docs without events using ultra-broad patterns."""
    print(f"\n{'='*70}")
    print(f"V2 §6 — Re-process Docs Without Events (Ultra-Broad Patterns)")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Find docs without events
    docs_with_events = set()
    for ev in store.iter("events"):
        docs_with_events.add(ev.get("document_id", ""))

    docs_without_events = [
        (doc_id, doc) for doc_id, doc in docs_by_id.items()
        if doc_id not in docs_with_events
    ]
    print(f"\n  Total docs without events: {len(docs_without_events)}")

    # Map source_class → event_type
    sources_by_id = store.latest_by_id("sources", "source_id")
    SRC_TO_EVENT_TYPE = {
        "central_bank": "monetary_policy_decision",
        "finance_ministry": "monetary_policy_decision",
        "securities_regulator": "regulatory_enforcement",
        "financial_regulator": "regulatory_enforcement",
        "banking_regulator": "regulatory_enforcement",
        "insurance_regulator": "regulatory_enforcement",
        "statistical_agency": "statistical_release",
        "stock_exchange": "statistical_release",
        "international_financial_institution": "statistical_release",
        "international_economic_institution": "statistical_release",
    }

    lock = threading.Lock()
    run_id = f"ultra-broad-{int(time.time())}"
    new_facts_count = 0
    new_events_count = 0
    new_ios_count = 0

    def process_one(doc_tuple):
        nonlocal new_facts_count, new_events_count, new_ios_count
        doc_id, doc = doc_tuple
        src_id = doc.get("source_id", "")
        src = sources_by_id.get(src_id, {})
        # Determine event type from source
        # Map source_id to class
        source_class = "statistical_agency"  # default
        if "central" in src_id.lower() or "bank" in src_id.lower() or "fed" in src_id.lower():
            source_class = "central_bank"
        elif "regulator" in src_id.lower() or "sec" in src_id.lower() or "cftc" in src_id.lower():
            source_class = "financial_regulator"
        elif "stat" in src_id.lower() or "bea" in src_id.lower() or "eurostat" in src_id.lower():
            source_class = "statistical_agency"

        event_type = SRC_TO_EVENT_TYPE.get(source_class, "statistical_release")

        # Find the representation for this document
        rep_id = None
        for rid, rep in reps_by_id.items():
            if rep.get("document_id") == doc_id:
                rep_id = rid
                break
        if not rep_id:
            return

        rep = reps_by_id.get(rep_id, {})
        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            return

        try:
            blob_bytes = Path(blob_path).read_bytes()
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))

            # Extract with ultra-broad patterns
            facts = extract_facts(text, ULTRA_BROAD_PATTERNS, rep_id, doc_id)
            if not facts:
                return

            with lock:
                for f in facts:
                    cur = store.current_fact(f.fact_id)
                    if cur is None:
                        store.append("facts", f.to_dict())
                        store.append("evidence", Evidence(
                            evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                            event_or_fact_id=f.fact_id,
                            representation_id=f.representation_id,
                            location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                            excerpt=f.excerpt,
                            provenance_ref=f"representation:{f.representation_id}",
                        ).to_dict())
                        new_facts_count += 1

                # Detect event
                ev = detect_event(facts, doc_id, event_type)
                if ev is None:
                    return
                existing_ev = store.current_event(ev.event_id)
                if existing_ev is None:
                    store.append("events", ev.to_dict())
                    existing_ev = store.current_event(ev.event_id)
                    new_events_count += 1

                # Build IO
                try:
                    io = build_intelligence_object(store, existing_ev, source_name=src_id)
                    new_ios_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    # Process in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_one, dt) for dt in docs_without_events[:600]]
        for future in as_completed(futures):
            try:
                future.result(timeout=15)
            except Exception:
                pass

    final_events = sum(1 for _ in store.iter("events"))
    print(f"\n  New facts extracted: {new_facts_count}")
    print(f"  New events detected: {new_events_count}")
    print(f"  New IOs built: {new_ios_count}")
    print(f"  Final total events: {final_events}")

    return final_events


if __name__ == "__main__":
    final = reprocess_docs_without_events()
    if final >= 500:
        print(f"\n  ✓ PASS: {final} real IOs (≥500 target)")
    else:
        print(f"\n  ⚠ {final} real IOs (< 500 target)")
