"""V6 §5 — Reprocess real corpus with semantic event gates.

Re-extract events with the document-level semantic gate:
  - For each document, try all event types
  - Apply semantic gate before creating events
  - Measure events removed/corrected
"""
from __future__ import annotations
import json
import sys
import time
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
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.event_semantic_gate import should_create_event


def reprocess_with_semantic_gate(store_root: str = "v3_corpus_store"):
    """Reprocess corpus with document-level semantic gate."""
    print(f"\n{'='*70}")
    print(f"V6 §5 — Reprocess Corpus with Semantic Event Gate")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Count before
    before_events = sum(1 for _ in store.iter("events"))
    before_facts = sum(1 for _ in store.iter("facts"))
    print(f"\n  Before reprocessing:")
    print(f"    Events: {before_events}")
    print(f"    Facts: {before_facts}")

    # Clear events (keep facts)
    events_path = Path(store_root) / "events.jsonl"
    open(events_path, "w").close()

    # Re-open store
    store = CachedStore(AppendOnlyStore(store_root))

    # Reprocess: for each document, try all event types with semantic gate
    events_created = 0
    events_rejected = 0
    events_by_type = {}
    rejection_reasons = {}

    SRC_TO_EVENT_TYPES = {
        "central_bank": ["monetary_policy_decision", "statistical_release", "regulatory_enforcement"],
        "finance_ministry": ["monetary_policy_decision", "statistical_release"],
        "securities_regulator": ["regulatory_enforcement", "statistical_release"],
        "financial_regulator": ["regulatory_enforcement", "statistical_release"],
        "banking_regulator": ["regulatory_enforcement", "statistical_release"],
        "insurance_regulator": ["regulatory_enforcement", "statistical_release"],
        "statistical_agency": ["statistical_release"],
        "stock_exchange": ["statistical_release", "regulatory_enforcement"],
        "international_financial_institution": ["statistical_release"],
        "international_economic_institution": ["statistical_release"],
    }

    def get_source_class(src_id):
        if any(x in src_id for x in ["fed-reserve", "ecb", "boe", "boj", "boc", "cbk", "nsi", "nbu",
                                      "cso", "sfc", "miti", "bb-", "nrb", "ecb-stat", "bnetza",
                                      "cma", "beis", "ustr", "sama", "cbj", "bank"]):
            return "central_bank"
        elif any(x in src_id for x in ["sec", "cftc", "esma", "fca", "consob", "naic", "dfsa"]):
            return "financial_regulator"
        elif any(x in src_id for x in ["bea", "eurostat", "stats", "stat", "ine"]):
            return "statistical_agency"
        else:
            return "statistical_agency"

    def get_patterns(event_type, source_class):
        if event_type == "monetary_policy_decision":
            return REFINED_PATTERNS.get("monetary", [])
        elif event_type == "regulatory_enforcement":
            return REFINED_PATTERNS.get("regulatory", [])
        else:
            return REFINED_PATTERNS.get("statistical", [])

    for rep_id, rep in reps_by_id.items():
        doc_id = rep.get("document_id", "")
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")

        if "job-" in src_id or "evt-broken-injection-test" in src_id:
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

        # Get event types to try for this source
        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            patterns = get_patterns(event_type, source_class)
            if not patterns:
                continue

            # Extract facts with sentence-aware evidence
            facts = improved_extract_facts(text, patterns, rep_id, doc_id)
            if not facts:
                continue

            # Apply semantic gate
            should_create, reason = should_create_event(event_type, facts, text)
            if not should_create:
                events_rejected += 1
                rejection_reasons[event_type] = rejection_reasons.get(event_type, 0) + 1
                continue

            # Detect event
            ev = detect_event(facts, doc_id, event_type)
            if ev is None:
                continue

            existing_ev = store.current_event(ev.event_id)
            if existing_ev is None:
                store.append("events", ev.to_dict())
                existing_ev = store.current_event(ev.event_id)
                events_created += 1
                events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

                # Build IO
                try:
                    io = build_intelligence_object(store, existing_ev, source_name=src_id)
                except Exception:
                    pass

    after_events = sum(1 for _ in store.iter("events"))
    after_facts = sum(1 for _ in store.iter("facts"))

    print(f"\n  After reprocessing:")
    print(f"    Events: {after_events}")
    print(f"    Facts: {after_facts}")
    print(f"    Events created: {events_created}")
    print(f"    Events rejected by semantic gate: {events_rejected}")
    print(f"    Events removed (vs before): {before_events - after_events}")

    print(f"\n  Events by type:")
    for et, count in sorted(events_by_type.items()):
        print(f"    {et:<30} {count:>4}")

    print(f"\n  Rejections by type:")
    for et, count in sorted(rejection_reasons.items()):
        print(f"    {et:<30} {count:>4}")

    return after_events, after_facts


if __name__ == "__main__":
    events, facts = reprocess_with_semantic_gate()
    print(f"\n  Final: {events} events, {facts} facts")
