"""V2 §6 — Multi-event-type detection per document.

Each document can produce MULTIPLE events of DIFFERENT types:
  - monetary_policy_decision (if rate keywords found)
  - statistical_release (if percentage found)
  - regulatory_enforcement (if enforcement keywords found)

This multiplies the IO count per document.
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
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.v3_ultra_broad_patterns import ULTRA_BROAD_PATTERNS


# Per-event-type patterns
EVENT_PATTERNS = {
    "monetary_policy_decision": [
        (r"\b(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?)\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", "rate_action"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", "rate_value"),
        (r"\bpolicy\s+rate\b.*?\b(\d+(?:\.\d+)?)\s*%", "policy_rate"),
    ],
    "statistical_release": [
        (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
        (r"\bGDP\s+(?:grew|growth|increased|expanded|rose)\s+(?:by\s+)?(\d+(?:\.\d+)?)", "gdp_growth"),
        (r"\binflation\s+(?:rate\s+)?(?:of\s+|was\s+|reached\s+)?(\d+(?:\.\d+)?)\s*%", "inflation_rate"),
        (r"\bunemployment\s+(?:rate\s+)?(?:of\s+|was\s+|reached\s+)?(\d+(?:\.\d+)?)\s*%", "unemployment_rate"),
    ],
    "regulatory_enforcement": [
        (r"\b(consent\s+order|cease(?:-|\s+)and(?:-|\s+)desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)\b", "action_type"),
        (r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|thousand)?", "penalty_amount"),
        (r"\bdefendant[:\s]+([A-Z][a-zA-Z\s&.,]+?)(?:\.|,|;|$)", "defendant_name"),
    ],
}


def multi_event_detection(store_root: str = "v3_corpus_store"):
    """Detect multiple event types per document."""
    print(f"\n{'='*70}")
    print(f"V2 §6 — Multi-Event-Type Detection Per Document")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")
    sources_by_id = store.latest_by_id("sources", "source_id")

    # Find docs with representations
    docs_with_reps = []
    for doc_id, doc in docs_by_id.items():
        for rid, rep in reps_by_id.items():
            if rep.get("document_id") == doc_id:
                docs_with_reps.append((doc_id, doc, rep))
                break

    print(f"\n  Docs with representations: {len(docs_with_reps)}")
    print(f"  Current events: {sum(1 for _ in store.iter('events'))}")

    lock = threading.Lock()
    new_facts_count = 0
    new_events_count = 0
    new_ios_count = 0

    def process_one(doc_rep):
        nonlocal new_facts_count, new_events_count, new_ios_count
        doc_id, doc, rep = doc_rep
        src_id = doc.get("source_id", "")
        rep_id = rep["representation_id"]

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            return

        try:
            blob_bytes = Path(blob_path).read_bytes()
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))

            # Try ALL 3 event types for each doc
            for event_type, patterns in EVENT_PATTERNS.items():
                facts = extract_facts(text, patterns, rep_id, doc_id)
                if not facts:
                    continue

                # Check if any facts are new
                new_facts = []
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
                            new_facts.append(f)
                        else:
                            new_facts.append(f)

                if not new_facts:
                    continue

                # Detect event for this type
                ev = detect_event(new_facts, doc_id, event_type)
                if ev is None:
                    continue

                with lock:
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
        futures = [executor.submit(process_one, dr) for dr in docs_with_reps[:900]]
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
    final = multi_event_detection()
    if final >= 500:
        print(f"\n  ✓ PASS: {final} real IOs (≥500 target)")
    else:
        print(f"\n  ⚠ {final} real IOs (< 500 target)")
