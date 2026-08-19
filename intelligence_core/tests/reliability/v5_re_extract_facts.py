"""V5 §4-5 — Re-extract all facts with sentence-aware evidence + entity/unit context.

Re-process all existing documents with:
  1. Sentence-aware evidence extraction (§4)
  2. Entity/unit/context preservation (§5)
  3. Refined patterns (§6)

This REPLACES the old facts with new, higher-quality facts.
"""
from __future__ import annotations
import json
import re
import shutil
import sys
import time
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Evidence, Fact, ObjState
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.topup_expanded_patterns import EXPANDED_PATTERNS


# Refined patterns (V5 §6) — fix the 3 zero-productivity patterns
# rate_action: was too narrow, broaden to include "rate" + action verb
# trade_balance: was looking for "trade balance" specifically, broaden
# revenue: was too specific, broaden to include "revenue" + amount

REFINED_PATTERNS = {
    "monetary": [
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "rate_value"),
        (r"\b(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?)\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", "rate_action"),
        (r"\bpolicy\s+rate\b.*?\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "policy_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)\s+(?:policy\s+rate|key\s+rate|interest\s+rate)", "policy_rate"),
    ],
    "statistical": [
        # V27R Pattern Family 1: match "percent" word with (?!\w) fix
        # (trailing \b after % fails because % is not a word character)
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "percentage_statistic"),
        (r"\bGDP\s+(?:grew|growth|increased|expanded|rose)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "gdp_growth"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)\s+GDP\s+growth", "gdp_growth"),
        (r"\bgross\s+domestic\s+product\s+(?:grew|rose|expanded)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "gdp_growth"),
        (r"\binflation\s+rate\s+(?:of\s+|was\s+|reached\s+|stood\s+at\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "inflation_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)\s+inflation", "inflation_rate"),
        (r"\bCPI\s+(?:rose|increased|grew)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "inflation_rate"),
        (r"\bunemployment\s+rate\s+(?:of\s+|was\s+|reached\s+|stood\s+at\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)", "unemployment_rate"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)\s+unemployment", "unemployment_rate"),
        (r"\bemployment\s+(?:level|stood)\s+(?:at\s+)?(\d+(?:,\d{3})+)\b", "employment_level"),
        (r"\b(\d+(?:,\d{3})+)\s+(?:persons|people|jobs)\s+employed", "employment_level"),
        # Refined trade_balance (V5 §6) — broaden
        (r"\btrade\s+(?:balance|deficit|surplus)\s+(?:of\s+|was\s+)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "trade_balance"),
        (r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:billion|million)\s+(?:trade|export|import)", "trade_balance"),
        # Refined revenue (V5 §6) — broaden
        (r"\brevenue\s+(?:of\s+|was\s+)?\$?(\d+(?:,\d{3})*(?:\.\d+)?)", "revenue"),
        (r"\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:billion|million)\s+(?:in\s+)?(?:revenue|sales|income)", "revenue"),
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


def re_extract_all_facts(store_root: str = "v3_corpus_store"):
    """Re-extract all facts with sentence-aware evidence + refined patterns."""
    print(f"\n{'='*70}")
    print(f"V5 §4-6 — Re-extract Facts with Sentence-Aware Evidence")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")
    sources_by_id = store.latest_by_id("sources", "source_id")

    # Count existing
    old_facts_count = sum(1 for _ in store.iter("facts"))
    old_events_count = sum(1 for _ in store.iter("events"))
    print(f"\n  Old facts: {old_facts_count}")
    print(f"  Old events: {old_events_count}")

    # Clear old facts + evidence + events (we'll re-extract)
    # But keep documents + representations + sources
    import json
    facts_path = Path(store_root) / "facts.jsonl"
    evidence_path = Path(store_root) / "evidence.jsonl"
    events_path = Path(store_root) / "events.jsonl"

    # Clear
    open(facts_path, "w").close()
    open(evidence_path, "w").close()
    open(events_path, "w").close()

    # Re-open store (to clear cache)
    store = CachedStore(AppendOnlyStore(store_root))

    # Re-extract from all representations
    new_facts_count = 0
    new_events_count = 0
    new_ios_count = 0

    # Group reps by source for pattern selection
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

    # Process each representation
    for rep_id, rep in reps_by_id.items():
        doc_id = rep.get("document_id", "")
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")

        # Skip synthetic sources
        if "job-" in src_id or "istat" in src_id.lower() or "fdic" in src_id.lower():
            continue
        if "evt-broken-injection-test" in src_id:
            continue

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue

        try:
            blob_bytes = Path(blob_path).read_bytes()
            # Skip PDF/binary
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                continue
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue

        # Determine source class + patterns
        source_class = "statistical_agency"
        if any(x in src_id for x in ["fed-reserve", "ecb", "boe", "boj", "boc", "cbk", "nsi", "nbu",
                                      "cso", "sfc", "miti", "bb-", "nrb", "ecb-stat", "bnetza",
                                      "cma", "beis", "ustr", "sama", "cbj", "bank"]):
            source_class = "central_bank"
        elif any(x in src_id for x in ["sec", "cftc", "esma", "fca", "consob", "naic", "dfsa"]):
            source_class = "financial_regulator"
        elif any(x in src_id for x in ["bea", "eurostat", "stats", "stat", "ine"]):
            source_class = "statistical_agency"

        event_type = SRC_TO_EVENT_TYPE.get(source_class, "statistical_release")
        pattern_key = {
            "central_bank": "monetary",
            "financial_regulator": "regulatory",
            "securities_regulator": "regulatory",
            "banking_regulator": "regulatory",
            "insurance_regulator": "regulatory",
            "statistical_agency": "statistical",
            "stock_exchange": "statistical",
        }.get(source_class, "statistical")

        patterns = REFINED_PATTERNS.get(pattern_key, REFINED_PATTERNS["statistical"])

        # Extract with sentence-aware evidence
        facts = improved_extract_facts(text, patterns, rep_id, doc_id)
        if not facts:
            continue

        # Append facts + evidence
        for f in facts:
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
            continue
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

    # Also try multi-event detection
    print(f"\n  Running multi-event detection...")
    for rep_id, rep in reps_by_id.items():
        doc_id = rep.get("document_id", "")
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")
        if "job-" in src_id:
            continue

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue
        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                continue
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue

        # Try ALL event types for multi-event detection
        for event_type, pattern_key in [
            ("monetary_policy_decision", "monetary"),
            ("statistical_release", "statistical"),
            ("regulatory_enforcement", "regulatory"),
        ]:
            patterns = REFINED_PATTERNS.get(pattern_key, [])
            facts = improved_extract_facts(text, patterns, rep_id, doc_id)
            if not facts:
                continue

            # Check if any new facts
            new_facts = []
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
                    new_facts.append(f)
                    new_facts_count += 1
                else:
                    new_facts.append(f)

            if not new_facts:
                continue

            ev = detect_event(new_facts, doc_id, event_type)
            if ev is None:
                continue
            existing_ev = store.current_event(ev.event_id)
            if existing_ev is None:
                store.append("events", ev.to_dict())
                existing_ev = store.current_event(ev.event_id)
                new_events_count += 1
                try:
                    io = build_intelligence_object(store, existing_ev, source_name=src_id)
                    new_ios_count += 1
                except Exception:
                    pass

    print(f"\n--- Results ---")
    print(f"  New facts: {new_facts_count}")
    print(f"  New events: {new_events_count}")
    print(f"  New IOs: {new_ios_count}")

    # Final counts
    store2 = CachedStore(AppendOnlyStore(store_root))
    final_facts = sum(1 for _ in store2.iter("facts"))
    final_events = sum(1 for _ in store2.iter("events"))
    print(f"\n  Final facts: {final_facts}")
    print(f"  Final events: {final_events}")

    return final_events, final_facts


if __name__ == "__main__":
    final_events, final_facts = re_extract_all_facts()
    print(f"\n  Final: {final_events} events, {final_facts} facts")
