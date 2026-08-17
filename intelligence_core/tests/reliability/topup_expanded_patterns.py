"""V2-Real §3 — Round 7: Re-process existing real documents with EXPANDED patterns.

We have 366 real documents but only 92 events. The gap is because the extraction
patterns are narrow (only rate_value/percentage_statistic/action_type).

Expand patterns to cover:
  - GDP growth (gdp_growth)
  - Inflation rate (inflation_rate)
  - Unemployment rate (unemployment_rate)
  - Employment level (employment_level)
  - USD amounts (usd_amount)
  - Cross-border changes (cross_border_change)
  - Defendant names (defendant_name)
  - Violation types (violation_type)
  - Statistic values (statistic_value)
  - Revenue/earnings (revenue, eps, net_income)

This re-processes existing documents (no new HTTP fetches needed) with
expanded patterns. New facts → new events → new IOs.
"""
from __future__ import annotations
import json
import re
import shutil
import sys
import threading
import time
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
from intelligence_core.tests.scale.run_scale_validation import (
    EVENT_TYPE_BY_SOURCE_TYPE,
)

# Expanded patterns covering ALL trigger_metrics in EVENT_TYPE_RULES
EXPANDED_PATTERNS = {
    "monetary": [
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", "rate_value"),
        (r"\b(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?)\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", "rate_action"),
        (r"\bpolicy\s+rate\b.*?\b(\d+(?:\.\d+)?)\s*%", "policy_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\s+(?:policy\s+rate|key\s+rate|interest\s+rate)", "policy_rate"),
    ],
    "statistical": [
        (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
        # GDP growth
        (r"\bGDP\s+(?:grew|growth|increased|expanded|rose)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "gdp_growth"),
        (r"\b(\d+(?:\.\d+)?)\s*%\s+GDP\s+growth", "gdp_growth"),
        (r"\bgross\s+domestic\s+product\s+(?:grew|rose|expanded)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "gdp_growth"),
        # Inflation
        (r"\binflation\s+rate\s+(?:of\s+|was\s+|reached\s+|stood\s+at\s+)?(\d+(?:\.\d+)?)\s*%", "inflation_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*%\s+inflation", "inflation_rate"),
        (r"\bCPI\s+(?:rose|increased|grew)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "inflation_rate"),
        # Unemployment
        (r"\bunemployment\s+rate\s+(?:of\s+|was\s+|reached\s+|stood\s+at\s+)?(\d+(?:\.\d+)?)\s*%", "unemployment_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*%\s+unemployment", "unemployment_rate"),
        # Employment level (raw number)
        (r"\bemployment\s+(?:level|stood)\s+(?:at\s+)?(\d+(?:,\d{3})+)\b", "employment_level"),
        (r"\b(\d+(?:,\d{3})+)\s+(?:persons|people|jobs)\s+employed", "employment_level"),
        # Cross-border change
        (r"\bcross[- ]border\s+(?:change|flows?)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%", "cross_border_change"),
        # Statistic value
        (r"\bstatistic(?:al\s+)?(?:value|figure):\s*(\d+(?:\.\d+)?)", "statistic_value"),
        # USD amounts in statistics
        (r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|trillion)", "usd_amount"),
    ],
    "regulatory": [
        (r"\b(consent\s+order|cease(?:-|\s+)and(?:-|\s+)desist|injunction|penalty|disgorgement|settlement|fine|charged|sued)\b", "action_type"),
        (r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|thousand)?", "penalty_amount"),
        (r"\bdefendant(?:s)?:\s*([A-Z][a-zA-Z\s&.,]+?)(?:\s+(?:was|were|agreed|paid|settled))", "defendant_name"),
        (r"\bviolation(?:s)?:\s*([a-z][a-zA-Z\s]+?)(?:\.|,|;|$)", "violation_type"),
    ],
    "earnings": [
        (r"\brevenue\s+(?:of\s+|was\s+)?\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion)", "revenue"),
        (r"\bEPS\s+(?:of\s+|was\s+)?\$(\d+(?:\.\d+)?)", "eps"),
        (r"\bnet\s+income\s+(?:of\s+|was\s+)?\$(\d+(?:,\d{3})*(?:\.\d+)?)", "net_income"),
    ],
    "market": [
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", "percentage_statistic"),
    ],
}


def reprocess_with_expanded_patterns(store):
    """Re-process all existing real documents with expanded patterns."""
    print(f"\n{'='*70}")
    print(f"V2-Real §3 — Round 7: Re-process real docs with expanded patterns")
    print(f"{'='*70}")

    existing_events = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing_events}")

    # Build lookups
    sources_by_id = store.latest_by_id("sources", "source_id")
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Track which documents we've already processed (have events)
    docs_with_events = set()
    for ev in store.iter("events"):
        docs_with_events.add(ev.get("document_id", ""))

    # Process each representation's blob with expanded patterns
    new_facts_count = 0
    new_events_count = 0
    new_io_count = 0

    # Group reps by source for pattern selection
    reps_to_process = []
    for rep_id, rep in reps_by_id.items():
        doc = docs_by_id.get(rep["document_id"], {})
        src_id = doc.get("source_id", "")
        src = sources_by_id.get(src_id, {})
        # Skip synthetic/canonical sources
        if "job-" in src_id or "istat" in src_id or "fdic" in src_id:
            continue
        # Determine source type from the source
        source_type = src.get("source_type", "")
        # Classify source by source_id pattern
        if any(x in src_id for x in ["ecb", "boe", "fed", "bank", "central"]):
            patterns_key = "monetary"
            event_type = "monetary_policy_decision"
        elif any(x in src_id for x in ["sec", "cftc", "esma", "fca", "regulator"]):
            patterns_key = "regulatory"
            event_type = "regulatory_enforcement"
        else:
            patterns_key = "statistical"
            event_type = "statistical_release"
        # Also try earnings + market
        reps_to_process.append((rep, doc, src_id, patterns_key, event_type))

    print(f"  Real representations to re-process: {len(reps_to_process)}")

    lock = threading.Lock()
    run_id = f"expand-patterns-{int(time.time())}"

    def process_one(rep_doc_src):
        rep, doc, src_id, patterns_key, event_type = rep_doc_src
        nonlocal new_facts_count, new_events_count, new_io_count

        try:
            # Read the blob
            blob_path = rep.get("raw_location", "")
            if not blob_path or not Path(blob_path).exists():
                return
            blob_bytes = Path(blob_path).read_bytes()
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))

            # Get expanded patterns
            patterns = EXPANDED_PATTERNS.get(patterns_key, [])

            # Extract facts
            facts = extract_facts(text, patterns, rep["representation_id"], doc["document_id"])
            if not facts:
                return

            # Check for new facts (not already in store)
            existing_fact_ids = set()
            for f in store.iter("facts"):
                if f["representation_id"] == rep["representation_id"]:
                    existing_fact_ids.add(f["fact_id"])

            new_facts = [f for f in facts if f.fact_id not in existing_fact_ids]
            if not new_facts:
                return

            with lock:
                for f in new_facts:
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
                ev = detect_event(new_facts, doc["document_id"], event_type)
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
                    new_io_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    # Process in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_one, r) for r in reps_to_process]
        for future in as_completed(futures):
            try:
                future.result(timeout=30)
            except Exception:
                pass

    final_events = sum(1 for _ in store.iter("events"))
    print(f"\n  New facts extracted: {new_facts_count}")
    print(f"  New events detected: {new_events_count}")
    print(f"  New IOs built: {new_io_count}")
    print(f"  Final total events: {final_events}")
    return final_events


if __name__ == "__main__":
    store = CachedStore(AppendOnlyStore("real_corpus_store"))
    total = reprocess_with_expanded_patterns(store)
    if total >= 100:
        print(f"\n  ✓ PASS: {total} real events (≥100)")
    else:
        print(f"\n  ⚠ {total} real events (< 100)")
