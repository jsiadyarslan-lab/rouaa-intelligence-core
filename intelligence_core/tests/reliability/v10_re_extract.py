"""V10 §7 — Re-extract facts with navigation exclusion + evidence selector.

This re-processes all documents:
  1. Filters navigation/UI content (V9 is_navigation_content)
  2. Uses sentence-aware extraction (V5)
  3. Uses strict evidence classification (V10 classify_evidence_strict)
  4. Only keeps facts with DIRECT or INDIRECT evidence (not INVALID/INSUFFICIENT)
"""
from __future__ import annotations
import json
import shutil
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
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v9_navigation_exclusion import is_navigation_content
from intelligence_core.tests.reliability.v10_evidence_closure import classify_evidence_strict, expand_evidence_for_direct
from intelligence_core.tests.reliability.event_semantic_gate import should_create_event


def re_extract_with_nav_exclusion(store_root: str = "v3_corpus_store"):
    """Re-extract all facts with navigation exclusion + evidence selector."""
    print(f"\n{'='*70}")
    print(f"V10 §7 — Re-extract with Navigation Exclusion + Evidence Selector")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Count before
    before_facts = sum(1 for _ in store.iter("facts"))
    before_events = sum(1 for _ in store.iter("events"))
    print(f"\n  Before: {before_facts} facts, {before_events} events")

    # Clear facts + evidence + events
    import json
    facts_path = Path(store_root) / "facts.jsonl"
    evidence_path = Path(store_root) / "evidence.jsonl"
    events_path = Path(store_root) / "events.jsonl"

    open(facts_path, "w").close()
    open(evidence_path, "w").close()
    open(events_path, "w").close()

    store = CachedStore(AppendOnlyStore(store_root))

    # Re-extract from all representations
    new_facts_count = 0
    new_events_count = 0
    new_ios_count = 0
    nav_rejected_count = 0

    SRC_TO_EVENT_TYPES = {
        "central_bank": ["monetary_policy_decision", "statistical_release", "regulatory_enforcement"],
        "statistical_agency": ["statistical_release"],
        "financial_regulator": ["regulatory_enforcement", "statistical_release"],
        "securities_regulator": ["regulatory_enforcement", "statistical_release"],
        "banking_regulator": ["regulatory_enforcement", "statistical_release"],
        "finance_ministry": ["monetary_policy_decision", "statistical_release"],
    }

    def get_source_class(src_id):
        if any(x in src_id for x in ["fed-reserve", "ecb", "boe", "boj", "boc", "cbk", "nsi", "nbu",
                                      "cso", "sfc", "miti", "bb-", "nrb", "ecb-stat", "bnetza",
                                      "cma", "beis", "ustr", "sama", "cbj", "bank"]):
            return "central_bank"
        elif any(x in src_id for x in ["sec", "cftc", "esma", "fca", "consob", "naic", "dfsa"]):
            return "financial_regulator"
        else:
            return "statistical_agency"

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
            doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue

        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            pattern_key = {
                "monetary_policy_decision": "monetary",
                "statistical_release": "statistical",
                "regulatory_enforcement": "regulatory",
            }.get(event_type, "statistical")
            patterns = REFINED_PATTERNS.get(pattern_key, [])

            # Extract with sentence-aware evidence
            facts = improved_extract_facts(doc_text, patterns, rep_id, doc_id)
            if not facts:
                continue

            # Filter navigation/UI facts
            clean_facts = []
            for f in facts:
                if is_navigation_content(f.excerpt):
                    nav_rejected_count += 1
                    # Try to expand evidence
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, doc_text)
                    if "DIRECT" in status:
                        # Expand worked — keep fact with new excerpt
                        f.excerpt = new_excerpt
                        clean_facts.append(f)
                    # else: reject (navigation content)
                else:
                    clean_facts.append(f)

            if not clean_facts:
                continue

            # Apply semantic gate
            should_create, gate_reason = should_create_event(event_type, clean_facts, doc_text)
            if not should_create:
                continue

            # Append facts + evidence
            for f in clean_facts:
                # Expand evidence if needed
                cls, reason = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, doc_text)
                    if "DIRECT" in status:
                        f.excerpt = new_excerpt

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
            ev = detect_event(clean_facts, doc_id, event_type)
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

    # Clean broken chains
    store2 = CachedStore(AppendOnlyStore(store_root))
    all_events = list(store2.iter("events"))
    clean_events = []
    removed = 0
    for ev in all_events:
        try:
            io = build_intelligence_object(store2, ev, source_name="")
            clean_events.append(ev)
        except Exception:
            removed += 1

    if removed > 0:
        with open(events_path, "w", encoding="utf-8") as f:
            for ev in clean_events:
                f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")

    after_facts = sum(1 for _ in CachedStore(AppendOnlyStore(store_root)).iter("facts"))
    after_events = sum(1 for _ in CachedStore(AppendOnlyStore(store_root)).iter("events"))

    print(f"\n--- Results ---")
    print(f"  New facts: {new_facts_count}")
    print(f"  New events: {new_events_count}")
    print(f"  New IOs: {new_ios_count}")
    print(f"  Navigation rejected: {nav_rejected_count}")
    print(f"  Broken chains removed: {removed}")
    print(f"  Final facts: {after_facts}")
    print(f"  Final events: {after_events}")

    return after_events, after_facts


if __name__ == "__main__":
    events, facts = re_extract_with_nav_exclusion()
    print(f"\n  Final: {events} events, {facts} facts")
