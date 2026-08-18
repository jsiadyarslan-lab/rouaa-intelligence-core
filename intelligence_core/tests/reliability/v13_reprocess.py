"""V13 §11 — Full Reprocessing with Recall Improvements.

Reprocess all 1,034 documents with:
  - V13 navigation classifier (MIXED content kept)
  - V13 expanded semantic gate (more inclusive context)
  - New recall patterns (basis points, seasonally adjusted, etc.)
  - Multilingual patterns (Japanese, Chinese, Arabic, Russian)
  - Structured document extraction (tables, lists, labeled values)
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Evidence
from intelligence_core.detect import detect_event, EVENT_TYPE_RULES
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v10_evidence_closure import classify_evidence_strict, expand_evidence_for_direct
from intelligence_core.tests.reliability.v13_recall_patterns import (
    classify_navigation_precise, is_navigation_content_v13,
    validate_event_context_v13, MULTILINGUAL_PATTERNS, MULTILINGUAL_EVENT_CONTEXT,
    NEW_RECALL_PATTERNS, STRUCTURED_PATTERNS,
)

from intelligence_core.extract import extract_facts, normalize_metric, PATTERN_TYPE_METADATA


def classify_language(text: str) -> str:
    if not text: return "unknown"
    total = len(text)
    if total == 0: return "unknown"
    hiragana = sum(1 for c in text if 0x3040 <= ord(c) <= 0x309F)
    katakana = sum(1 for c in text if 0x30A0 <= ord(c) <= 0x30FF)
    cjk = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
    arabic = sum(1 for c in text if 0x0600 <= ord(c) <= 0x06FF)
    cyrillic = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    if hiragana + katakana > 10: return "ja"
    elif cjk / total > 0.1: return "zh"
    elif arabic / total > 0.1: return "ar"
    elif cyrillic / total > 0.1: return "ru"
    else: return "en"


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


def get_all_patterns(language: str, event_type: str) -> list:
    """Get ALL applicable patterns for a document + event type."""
    # Base patterns (English)
    pattern_key = {
        "monetary_policy_decision": "monetary",
        "statistical_release": "statistical",
        "regulatory_enforcement": "regulatory",
    }.get(event_type, "statistical")
    base_patterns = REFINED_PATTERNS.get(pattern_key, [])

    # Add new recall patterns (for all languages)
    # Map new pattern types to trigger_metrics
    all_patterns = list(base_patterns)
    
    # Add new recall patterns that are relevant to the event type
    for regex, pattern_type in NEW_RECALL_PATTERNS:
        # Check if this pattern_type maps to a trigger_metric for this event type
        rules = EVENT_TYPE_RULES.get(event_type, {})
        trigger_metrics = rules.get("trigger_metrics", set())
        
        # Map pattern_type to metric
        metric, was_normalized = normalize_metric(pattern_type)
        if metric in trigger_metrics:
            all_patterns.append((regex, pattern_type))
        elif pattern_type in ("percentage_statistic",):
            # Generic percentage is always relevant for statistical
            if "percentage_statistic" in trigger_metrics:
                all_patterns.append((regex, pattern_type))

    # Add structured patterns
    for regex, pattern_type in STRUCTURED_PATTERNS:
        metric, _ = normalize_metric(pattern_type)
        rules = EVENT_TYPE_RULES.get(event_type, {})
        if metric in rules.get("trigger_metrics", set()) or pattern_type == "structured_rate":
            all_patterns.append((regex, pattern_type))

    # Add multilingual patterns
    if language in MULTILINGUAL_PATTERNS:
        ml_patterns = MULTILINGUAL_PATTERNS[language]
        for regex, pattern_type in ml_patterns:
            metric, _ = normalize_metric(pattern_type)
            rules = EVENT_TYPE_RULES.get(event_type, {})
            if metric in rules.get("trigger_metrics", set()):
                all_patterns.append((regex, pattern_type))

    return all_patterns


def run_v13_reprocessing(store_root: str = "v3_corpus_store"):
    """Reprocess all documents with V13 recall improvements."""
    print(f"\n{'='*70}")
    print(f"V13 §11 — Full Reprocessing with Recall Improvements")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    before_events = sum(1 for _ in store.iter("events"))
    before_facts = sum(1 for _ in store.iter("facts"))
    print(f"\n  Before: {before_events} events, {before_facts} facts")

    # Clear for reprocessing
    facts_path = Path(store_root) / "facts.jsonl"
    evidence_path = Path(store_root) / "evidence.jsonl"
    events_path = Path(store_root) / "events.jsonl"
    open(facts_path, "w").close()
    open(evidence_path, "w").close()
    open(events_path, "w").close()

    store = CachedStore(AppendOnlyStore(store_root))

    pipeline_stats = Counter()
    language_stats = defaultdict(lambda: Counter())
    nav_classifications = Counter()

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
        except Exception:
            continue

        if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
            pipeline_stats["PDF_BINARY"] += 1
            continue

        doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        language = classify_language(doc_text)
        language_stats[language]["documents"] += 1
        pipeline_stats["FORMAT_VALID"] += 1

        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            # Get ALL patterns (base + new recall + structured + multilingual)
            all_patterns = get_all_patterns(language, event_type)
            if not all_patterns:
                continue

            # Extract with sentence-aware evidence
            facts = improved_extract_facts(doc_text, all_patterns, rep_id, doc_id)
            if not facts:
                continue

            # V13 Navigation filtering (MIXED content kept)
            clean_facts = []
            for f in facts:
                nav_class = classify_navigation_precise(f.excerpt)
                nav_classifications[nav_class] += 1
                if nav_class == "NAVIGATION_ONLY":
                    pipeline_stats["NAV_REJECTED"] += 1
                    # Try expansion
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, doc_text)
                    if "DIRECT" in status:
                        f.excerpt = new_excerpt
                        clean_facts.append(f)
                        pipeline_stats["NAV_RECOVERED"] += 1
                else:
                    clean_facts.append(f)

            if not clean_facts:
                continue

            # Evidence selection
            direct_facts = []
            for f in clean_facts:
                cls, reason = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, doc_text)
                    if "DIRECT" in status:
                        f.excerpt = new_excerpt
                        direct_facts.append(f)
                    elif cls == "INVALID":
                        pipeline_stats["INVALID_EVIDENCE"] += 1
                    else:
                        direct_facts.append(f)
                else:
                    direct_facts.append(f)

            if not direct_facts:
                continue

            # V13 Semantic gate (expanded + multilingual)
            should_create, gate_reason = should_create_event_v13(event_type, direct_facts, doc_text, language)
            if not should_create:
                pipeline_stats["SEMANTIC_REJECTED"] += 1
                continue

            pipeline_stats["SEMANTIC_PASSED"] += 1

            # Append facts + evidence
            for f in direct_facts:
                store.append("facts", f.to_dict())
                store.append("evidence", Evidence(
                    evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                    event_or_fact_id=f.fact_id,
                    representation_id=f.representation_id,
                    location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                    excerpt=f.excerpt,
                    provenance_ref=f"representation:{f.representation_id}",
                ).to_dict())
                pipeline_stats["FACTS_APPENDED"] += 1

            # Event detection
            ev = detect_event(direct_facts, doc_id, event_type)
            if ev is None:
                continue

            existing_ev = store.current_event(ev.event_id)
            if existing_ev is None:
                store.append("events", ev.to_dict())
                existing_ev = store.current_event(ev.event_id)
                pipeline_stats["EVENTS_CREATED"] += 1

                try:
                    io = build_intelligence_object(store, existing_ev, source_name=src_id)
                    pipeline_stats["IOS_BUILT"] += 1
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
        pipeline_stats["BROKEN_REMOVED"] = removed

    store3 = CachedStore(AppendOnlyStore(store_root))
    final_events = sum(1 for _ in store3.iter("events"))
    final_facts = sum(1 for _ in store3.iter("facts"))

    print(f"\n--- Pipeline Statistics ---")
    for k, v in pipeline_stats.most_common():
        print(f"  {k:<30} {v:>6}")

    print(f"\n--- Navigation Classifications ---")
    for k, v in nav_classifications.most_common():
        print(f"  {k:<25} {v:>5}")

    print(f"\n--- Language Distribution ---")
    for lang, stats in sorted(language_stats.items(), key=lambda x: -x[1]["documents"]):
        print(f"  {lang}: {stats['documents']} docs")

    print(f"\n--- Final Results ---")
    print(f"  Events: {before_events} → {final_events} ({'+' if final_events > before_events else ''}{final_events - before_events})")
    print(f"  Facts: {before_facts} → {final_facts} ({'+' if final_facts > before_facts else ''}{final_facts - before_facts})")

    return final_events, final_facts


def should_create_event_v13(event_type, facts, doc_text, language="en"):
    """V13 combined fact + context decision with multilingual support."""
    if not facts:
        return False, "no facts"
    if not doc_text:
        return False, "no document text"
    
    is_valid, reason = validate_event_context_v13(event_type, doc_text, language)
    if not is_valid:
        return False, f"context: {reason}"
    
    return True, f"approved: {reason}"


if __name__ == "__main__":
    events, facts = run_v13_reprocessing()
    print(f"\n  Final: {events} events, {facts} facts")
