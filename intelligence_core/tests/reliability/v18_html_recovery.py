"""V18 §2-11 — HTML-Aware Intelligence Recovery.

Integrate HTMLStructureParser into Core pipeline, re-run frozen 300-doc benchmark,
measure TRUE delta from V17 to V18.

§2: Capture V17 baseline
§3-4: Integrate parser (additive: text + structured segments)
§5-8: Table/list/headline extraction with evidence
§9: Metric normalization
§10-11: Re-run SAME frozen benchmark
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from html.parser import HTMLParser

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Evidence, Fact, ObjState
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts, normalize_metric
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v9_navigation_exclusion import is_navigation_content
from intelligence_core.tests.reliability.v10_evidence_closure import classify_evidence_strict, expand_evidence_for_direct
from intelligence_core.tests.reliability.v13_recall_patterns import (
    is_navigation_content_v13, validate_event_context_v13,
    NEW_RECALL_PATTERNS, STRUCTURED_PATTERNS,
    MULTILINGUAL_PATTERNS, MULTILINGUAL_EVENT_CONTEXT,
)
from intelligence_core.tests.reliability.v15_recall_recovery import HTMLStructureParser, extract_html_structure


# §9 — Metric normalization mapping
METRIC_EQUIVALENCE = {
    # Core uses these metric names; GT regex uses different names
    # Map: GT_metric → canonical_core_metric
    "percentage": "percentage_statistic",
    "rate_value": "rate_value",
    "policy_rate": "policy_rate",
    "rate_decision": "rate_decision",
    "action_type": "action_type",
    "penalty_amount": "penalty_amount",
    "usd_amount": "usd_amount",
    "gdp_growth": "gdp_growth",
    "inflation_rate": "inflation_rate",
    "unemployment_rate": "unemployment_rate",
    "employment_level": "employment_level",
    # Structured extraction may produce these
    "structured_rate": "percentage_statistic",  # Table row with rate → percentage
    "labeled_rate": "percentage_statistic",
    "list_percentage": "percentage_statistic",
    # New recall patterns
    "basis_points": "percentage_statistic",  # 25 bps = 0.25%
    "seasonally_adjusted": "percentage_statistic",
    "yield_rate": "percentage_statistic",
    "spread": "percentage_statistic",
    "volume": "usd_amount",
    "trade_value": "usd_amount",
    "production_change": "percentage_statistic",
    "employment_change": "employment_level",
    "index_change": "percentage_statistic",
    "qoq_change": "percentage_statistic",
    "yoy_change": "percentage_statistic",
    "mom_change": "percentage_statistic",
}


def normalize_metric_v18(pattern_type: str) -> str:
    """§9 — Normalize metric to canonical name."""
    # First try Core's built-in normalization
    from intelligence_core.extract import normalize_metric as core_normalize
    metric, was_normalized = core_normalize(pattern_type)
    # Then apply our equivalence map
    canonical = METRIC_EQUIVALENCE.get(metric, metric)
    return canonical


def run_v18_html_aware_recovery(store_root: str = "v3_corpus_store"):
    """V18 — Integrate HTMLStructureParser + re-run frozen benchmark."""
    print(f"\n{'='*70}")
    print(f"V18 — HTML-Aware Intelligence Recovery")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # ═══ §2: Capture V17 baseline ═══
    print(f"\n--- §2: V17 Baseline ---")
    v17_events = sum(1 for _ in store.iter("events"))
    v17_facts = sum(1 for _ in store.iter("facts"))
    print(f"  V17 events: {v17_events}")
    print(f"  V17 facts: {v17_facts}")

    # ═══ §3-4: Integrate HTMLStructureParser ═══
    # Clear for reprocessing
    facts_path = Path(store_root) / "facts.jsonl"
    evidence_path = Path(store_root) / "evidence.jsonl"
    events_path = Path(store_root) / "events.jsonl"
    open(facts_path, "w").close()
    open(evidence_path, "w").close()
    open(events_path, "w").close()

    store = CachedStore(AppendOnlyStore(store_root))

    pipeline_stats = Counter()
    structural_recovery = Counter()  # TABLE, LIST, HEADING, PARAGRAPH

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

    def get_all_patterns_v18(language, event_type):
        """Get ALL patterns including new recall + structured + multilingual."""
        pattern_key = {
            "monetary_policy_decision": "monetary",
            "statistical_release": "statistical",
            "regulatory_enforcement": "regulatory",
        }.get(event_type, "statistical")
        base_patterns = REFINED_PATTERNS.get(pattern_key, [])

        all_patterns = list(base_patterns)

        # Add new recall patterns
        for regex, pattern_type in NEW_RECALL_PATTERNS:
            metric = normalize_metric_v18(pattern_type)
            from intelligence_core.detect import EVENT_TYPE_RULES
            rules = EVENT_TYPE_RULES.get(event_type, {})
            if metric in rules.get("trigger_metrics", set()):
                all_patterns.append((regex, pattern_type))

        # Add structured patterns
        for regex, pattern_type in STRUCTURED_PATTERNS:
            all_patterns.append((regex, pattern_type))

        # Add multilingual patterns
        if language in MULTILINGUAL_PATTERNS:
            for regex, pattern_type in MULTILINGUAL_PATTERNS[language]:
                metric = normalize_metric_v18(pattern_type)
                from intelligence_core.detect import EVENT_TYPE_RULES
                rules = EVENT_TYPE_RULES.get(event_type, {})
                if metric in rules.get("trigger_metrics", set()):
                    all_patterns.append((regex, pattern_type))

        return all_patterns

    # Process each document with HTML-aware extraction
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

        pipeline_stats["FORMAT_VALID"] += 1

        # §3-4: Get BOTH flat text AND structured segments
        flat_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        structured_segments = extract_html_structure(blob_bytes)

        # Language classification
        from intelligence_core.tests.reliability.v13_reprocess import classify_language
        language = classify_language(flat_text)

        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            all_patterns = get_all_patterns_v18(language, event_type)
            if not all_patterns:
                continue

            # §3: Extract from FLAT text (existing path)
            flat_facts = improved_extract_facts(flat_text, all_patterns, rep_id, doc_id)

            # §4: Extract from STRUCTURED segments (new path)
            structured_facts = []
            for seg_text, seg_context, seg_headers in structured_segments:
                # Skip navigation-like segments
                if is_navigation_content_v13(seg_text):
                    continue

                # Extract facts from this structural segment
                seg_facts = improved_extract_facts(seg_text, all_patterns, rep_id, doc_id)
                for f in seg_facts:
                    # Enrich evidence with structural context
                    if seg_context == "TABLE_ROW" and seg_headers:
                        # Add column headers to evidence
                        header_context = " | ".join(seg_headers[:5])
                        f.excerpt = f"[TABLE: {header_context}] {f.excerpt}"
                    elif seg_context == "LIST_ITEM":
                        f.excerpt = f"[LIST] {f.excerpt}"
                    elif seg_context == "HEADING":
                        f.excerpt = f"[HEADING] {f.excerpt}"
                structured_facts.extend(seg_facts)

            # Combine: flat + structured (deduplicate by fact_id)
            all_facts = flat_facts + structured_facts
            seen_ids = set()
            unique_facts = []
            for f in all_facts:
                if f.fact_id not in seen_ids:
                    seen_ids.add(f.fact_id)
                    unique_facts.append(f)
                    # Track which structural context produced this fact
                    if "[TABLE:" in f.excerpt:
                        structural_recovery["TABLE"] += 1
                    elif "[LIST]" in f.excerpt:
                        structural_recovery["LIST"] += 1
                    elif "[HEADING]" in f.excerpt:
                        structural_recovery["HEADING"] += 1
                    else:
                        structural_recovery["PARAGRAPH"] += 1

            if not unique_facts:
                continue

            # Navigation filtering (V13 MIXED classifier)
            clean_facts = []
            for f in unique_facts:
                if is_navigation_content_v13(f.excerpt):
                    pipeline_stats["NAV_REJECTED"] += 1
                    # Try expansion
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in status:
                        f.excerpt = new_excerpt
                        clean_facts.append(f)
                        pipeline_stats["NAV_RECOVERED"] += 1
                else:
                    clean_facts.append(f)

            if not clean_facts:
                continue

            # Evidence selection (expand INDIRECT to DIRECT)
            direct_facts = []
            for f in clean_facts:
                cls, reason = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, flat_text)
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

            # Semantic gate (V13 expanded + multilingual)
            should_create, gate_reason = should_create_event_v13(event_type, direct_facts, flat_text, language)
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

    store3 = CachedStore(AppendOnlyStore(store_root))
    v18_events = sum(1 for _ in store3.iter("events"))
    v18_facts = sum(1 for _ in store3.iter("facts"))

    # Print results
    print(f"\n--- Pipeline Statistics ---")
    for k, v in pipeline_stats.most_common():
        print(f"  {k:<30} {v:>6}")

    print(f"\n--- Structural Recovery ---")
    for k, v in structural_recovery.most_common():
        print(f"  {k:<15} {v:>5}")

    print(f"\n--- V17 vs V18 ---")
    print(f"  Events: {v17_events} → {v18_events} ({'+' if v18_events > v17_events else ''}{v18_events - v17_events})")
    print(f"  Facts:  {v17_facts} → {v18_facts} ({'+' if v18_facts > v17_facts else ''}{v18_facts - v17_facts})")

    return v18_events, v18_facts


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
    events, facts = run_v18_html_aware_recovery()
    print(f"\n  Final: {events} events, {facts} facts")
