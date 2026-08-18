"""V21 §3-7 — Run ONLY the 300 frozen benchmark documents with V20 architecture.

Processes ONLY the 300 benchmark documents (not all 1,034).
Uses V13 gate consistently for event evaluation.
Produces V17 → V20 comparison on the SAME documents.
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
from intelligence_core.tests.reliability.v9_navigation_exclusion import is_navigation_content
from intelligence_core.tests.reliability.v10_evidence_closure import classify_evidence_strict, expand_evidence_for_direct
from intelligence_core.tests.reliability.v13_recall_patterns import (
    is_navigation_content_v13, validate_event_context_v13,
    NEW_RECALL_PATTERNS, STRUCTURED_PATTERNS, MULTILINGUAL_PATTERNS,
)
from intelligence_core.tests.reliability.v15_recall_recovery import extract_html_structure
from intelligence_core.tests.reliability.v19_forensic import normalize_metric_v19
from intelligence_core.tests.reliability.v13_reprocess import classify_language
from intelligence_core.tests.reliability.v14_ground_truth import select_300_documents, build_ground_truth

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

def get_patterns(language, event_type):
    pk = {"monetary_policy_decision": "monetary", "statistical_release": "statistical",
          "regulatory_enforcement": "regulatory"}.get(event_type, "statistical")
    patterns = list(REFINED_PATTERNS.get(pk, []))
    for regex, pt in NEW_RECALL_PATTERNS:
        m = normalize_metric_v19(pt)
        if m in EVENT_TYPE_RULES.get(event_type, {}).get("trigger_metrics", set()):
            patterns.append((regex, pt))
    for regex, pt in STRUCTURED_PATTERNS:
        patterns.append((regex, pt))
    if language in MULTILINGUAL_PATTERNS:
        for regex, pt in MULTILINGUAL_PATTERNS[language]:
            m = normalize_metric_v19(pt)
            if m in EVENT_TYPE_RULES.get(event_type, {}).get("trigger_metrics", set()):
                patterns.append((regex, pt))
    return patterns


def run_v21_frozen_benchmark(store_root: str = "v3_corpus_store"):
    """Run ONLY the 300 frozen benchmark documents."""
    print(f"\n{'='*70}")
    print(f"V21 — Frozen 300-Document Benchmark Completion")
    print(f"{'='*70}")

    # Get the 300 frozen documents
    selected_docs = select_300_documents(store_root)
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)
    print(f"\n  Frozen benchmark documents: {len(selected_docs)}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # §2: Capture V17 baseline on these 300 docs
    print(f"\n--- §2: V17 Baseline on 300 Docs ---")
    v17_events = [ev for ev in store.iter("events") if ev.get("document_id") in benchmark_doc_ids]
    v17_facts = [f for f in store.iter("facts") if f.get("document_id") in benchmark_doc_ids]
    print(f"  V17 events (in benchmark): {len(v17_events)}")
    print(f"  V17 facts (in benchmark): {len(v17_facts)}")

    # Build V17 ground truth
    print(f"\n--- Building V17 Ground Truth ---")
    gt_facts = []
    gt_events = []
    for doc_entry in selected_docs:
        gt = build_ground_truth(doc_entry, store)
        for f in gt.get("ground_truth_facts", []):
            f["doc_id"] = gt["doc_id"]
            f["language"] = gt.get("language", "en")
            # Normalize metric
            if f.get("metric") == "percentage":
                f["metric"] = "percentage_statistic"
            gt_facts.append(f)
        for e in gt.get("ground_truth_events", []):
            e["doc_id"] = gt["doc_id"]
            gt_events.append(e)

    # Ground truth lookups
    gt_fact_lookup = defaultdict(set)  # (doc_id, metric, value)
    for f in gt_facts:
        gt_fact_lookup[f["doc_id"]].add((f.get("metric", ""), str(f.get("value", ""))))

    gt_event_lookup = defaultdict(set)
    for e in gt_events:
        gt_event_lookup[e["doc_id"]].add(e.get("event_type", ""))

    total_gt_facts = len(gt_facts)
    total_gt_events = len(gt_events)
    print(f"  GT facts: {total_gt_facts}")
    print(f"  GT events: {total_gt_events}")

    # V17 matching
    v17_tp = 0
    v17_fp = 0
    v17_fn = 0
    for f in v17_facts:
        key = (f.get("document_id", ""), f.get("metric", ""), str(f.get("value", "")))
        if key[2] in [v for k, v_list in gt_fact_lookup.items() if k == key[0] for v in v_list if isinstance(v, tuple) and v[1] == key[2]]:
            v17_tp += 1
        else:
            # Try value-only match
            matched = False
            for gt_key in gt_fact_lookup.get(key[0], set()):
                if gt_key[1] == key[2]:
                    v17_tp += 1
                    matched = True
                    break
            if not matched:
                v17_fp += 1
    # FN = GT facts not matched
    matched_gt = 0
    for doc_id, gt_facts_set in gt_fact_lookup.items():
        core_values = set(str(f.get("value", "")) for f in v17_facts if f.get("document_id") == doc_id)
        for gt_metric, gt_value in gt_facts_set:
            if gt_value in core_values:
                matched_gt += 1
    v17_fn = total_gt_facts - matched_gt

    v17_fact_precision = (v17_tp / (v17_tp + v17_fp) * 100) if (v17_tp + v17_fp) else 0
    v17_fact_recall = (matched_gt / total_gt_facts * 100) if total_gt_facts else 0

    # V17 event matching
    v17_ev_tp = 0
    v17_ev_fp = 0
    for ev in v17_events:
        doc_id = ev.get("document_id", "")
        et = ev.get("event_type", "")
        if et in gt_event_lookup.get(doc_id, set()):
            v17_ev_tp += 1
        else:
            v17_ev_fp += 1
    v17_ev_fn = total_gt_events - v17_ev_tp
    v17_ev_precision = (v17_ev_tp / (v17_ev_tp + v17_ev_fp) * 100) if (v17_ev_tp + v17_ev_fp) else 0
    v17_ev_recall = (v17_ev_tp / total_gt_events * 100) if total_gt_events else 0

    print(f"\n  V17 Fact Precision: {v17_fact_precision:.1f}% ({v17_tp}/{v17_tp + v17_fp})")
    print(f"  V17 Fact Recall:    {v17_fact_recall:.1f}% ({matched_gt}/{total_gt_facts})")
    print(f"  V17 Event Precision: {v17_ev_precision:.1f}% ({v17_ev_tp}/{v17_ev_tp + v17_ev_fp})")
    print(f"  V17 Event Recall:    {v17_ev_recall:.1f}% ({v17_ev_tp}/{total_gt_events})")

    # ═══ §3: Run V20 architecture on SAME 300 docs ═══
    print(f"\n--- §3: Running V20 Architecture on 300 Docs ---")

    # Clear ONLY benchmark-related facts/events
    # (We need a clean store for the 300 docs)
    # Actually, we'll build a separate comparison — process the 300 docs fresh

    pipeline_stats = Counter()
    structural_stats = Counter()
    v20_facts_by_doc = defaultdict(list)
    v20_events_by_doc = defaultdict(list)
    total_docs_processed = 0

    for doc_entry in selected_docs:
        doc_id = doc_entry["doc_id"]
        src_id = doc_entry.get("src_id", doc_entry.get("src_id", ""))

        # Find representation
        rep = None
        for rid, r in reps_by_id.items():
            if r.get("document_id") == doc_id:
                rep = r
                break
        if not rep:
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

        flat_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        structured_segments = extract_html_structure(blob_bytes)

        has_tables = any(ctx == "TABLE_ROW" for _, ctx, _ in structured_segments)
        has_lists = sum(1 for _, ctx, _ in structured_segments if ctx == "LIST_ITEM") > 5
        has_headings = sum(1 for _, ctx, _ in structured_segments if ctx == "HEADING") > 3
        use_structured = has_tables or has_lists or has_headings

        if use_structured:
            pipeline_stats["STRUCTURED_TRIGGERED"] += 1
        else:
            pipeline_stats["FLAT_ONLY"] += 1

        language = classify_language(flat_text)
        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            patterns = get_patterns(language, event_type)
            if not patterns:
                continue

            flat_facts = improved_extract_facts(flat_text, patterns, rep["representation_id"], doc_id)

            structured_facts = []
            if use_structured:
                for seg_text, seg_ctx, seg_headers in structured_segments:
                    if is_navigation_content_v13(seg_text):
                        continue
                    seg_facts = improved_extract_facts(seg_text, patterns, rep["representation_id"], doc_id)
                    for f in seg_facts:
                        if seg_ctx == "TABLE_ROW" and seg_headers:
                            f.excerpt = f"[TABLE: {' | '.join(seg_headers[:5])}] {f.excerpt}"
                        elif seg_ctx == "LIST_ITEM":
                            f.excerpt = f"[LIST] {f.excerpt}"
                        elif seg_ctx == "HEADING":
                            f.excerpt = f"[HEADING] {f.excerpt}"
                    structured_facts.extend(seg_facts)

            # Semantic dedup
            seen = set()
            all_facts = []
            for f in flat_facts + structured_facts:
                key = (f.document_id, normalize_metric_v19(f.pattern_ref), str(f.value))
                if key not in seen:
                    seen.add(key)
                    all_facts.append(f)
                    if "[TABLE:" in f.excerpt:
                        structural_stats["TABLE"] += 1
                    elif "[LIST]" in f.excerpt:
                        structural_stats["LIST"] += 1
                    elif "[HEADING]" in f.excerpt:
                        structural_stats["HEADING"] += 1
                    else:
                        structural_stats["PARAGRAPH"] += 1

            if not all_facts:
                continue

            # Nav filter
            clean = []
            for f in all_facts:
                if is_navigation_content_v13(f.excerpt):
                    pipeline_stats["NAV_REJECTED"] += 1
                    ne, st = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in st:
                        f.excerpt = ne
                        clean.append(f)
                        pipeline_stats["NAV_RECOVERED"] += 1
                else:
                    clean.append(f)
            if not clean:
                continue

            # Evidence selection
            direct = []
            for f in clean:
                cls, _ = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    ne, st = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in st:
                        f.excerpt = ne
                        direct.append(f)
                    elif cls == "INVALID":
                        pipeline_stats["INVALID_EVIDENCE"] += 1
                    else:
                        direct.append(f)
                else:
                    direct.append(f)
            if not direct:
                continue

            # §6: V13 semantic gate ONLY
            valid, reason = validate_event_context_v13(event_type, flat_text, language)
            if not valid:
                pipeline_stats["SEMANTIC_REJECTED"] += 1
                continue
            pipeline_stats["SEMANTIC_PASSED"] += 1

            # Record facts + events (in-memory only, not appending to store)
            for f in direct:
                v20_facts_by_doc[doc_id].append(f.to_dict())
                pipeline_stats["FACTS_EXTRACTED"] += 1

            ev = detect_event(direct, doc_id, event_type)
            if ev is not None:
                v20_events_by_doc[doc_id].append(ev.to_dict())
                pipeline_stats["EVENTS_DETECTED"] += 1

        total_docs_processed += 1
        if total_docs_processed % 50 == 0:
            print(f"  Processed {total_docs_processed}/{len(selected_docs)}...")

    print(f"\n  Total docs processed: {total_docs_processed}")
    print(f"  Facts extracted: {pipeline_stats['FACTS_EXTRACTED']}")
    print(f"  Events detected: {pipeline_stats['EVENTS_DETECTED']}")

    print(f"\n--- Pipeline Stats ---")
    for k, v in pipeline_stats.most_common():
        print(f"  {k:<25} {v:>5}")

    print(f"\n--- Structural Recovery ---")
    for k, v in structural_stats.most_common():
        print(f"  {k:<15} {v:>5}")

    # ═══ §7: V17 → V20 comparison ═══
    print(f"\n--- §7: V17 → V20 Comparison ---")

    # V20 matching
    v20_tp = 0
    v20_fp = 0
    v20_total_facts = 0
    for doc_id, facts in v20_facts_by_doc.items():
        for f in facts:
            v20_total_facts += 1
            value = str(f.get("value", ""))
            # Check against GT
            gt_set = gt_fact_lookup.get(doc_id, set())
            matched = any(gt_value == value for gt_metric, gt_value in gt_set)
            if matched:
                v20_tp += 1
            else:
                v20_fp += 1

    # V20 FN
    v20_matched_gt = 0
    for doc_id, gt_set in gt_fact_lookup.items():
        core_values = set(str(f.get("value", "")) for f in v20_facts_by_doc.get(doc_id, []))
        for gt_metric, gt_value in gt_set:
            if gt_value in core_values:
                v20_matched_gt += 1
    v20_fn = total_gt_facts - v20_matched_gt

    v20_fact_precision = (v20_tp / v20_total_facts * 100) if v20_total_facts else 0
    v20_fact_recall = (v20_matched_gt / total_gt_facts * 100) if total_gt_facts else 0

    # V20 event matching
    v20_ev_tp = 0
    v20_ev_fp = 0
    v20_total_events = 0
    for doc_id, events in v20_events_by_doc.items():
        for ev in events:
            v20_total_events += 1
            et = ev.get("event_type", "")
            if et in gt_event_lookup.get(doc_id, set()):
                v20_ev_tp += 1
            else:
                v20_ev_fp += 1
    v20_ev_fn = total_gt_events - v20_ev_tp
    v20_ev_precision = (v20_ev_tp / v20_total_events * 100) if v20_total_events else 0
    v20_ev_recall = (v20_ev_tp / total_gt_events * 100) if total_gt_events else 0

    print(f"\n  {'Metric':<25} {'V17':>10} {'V20':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Facts extracted':<25} {len(v17_facts):>10} {v20_total_facts:>10} {v20_total_facts - len(v17_facts):>+10}")
    print(f"  {'Events detected':<25} {len(v17_events):>10} {v20_total_events:>10} {v20_total_events - len(v17_events):>+10}")
    print(f"  {'Fact TP':<25} {v17_tp:>10} {v20_tp:>10} {v20_tp - v17_tp:>+10}")
    print(f"  {'Fact FP':<25} {v17_fp:>10} {v20_fp:>10} {v20_fp - v17_fp:>+10}")
    print(f"  {'Fact FN':<25} {v17_fn:>10} {v20_fn:>10} {v20_fn - v17_fn:>+10}")
    print(f"  {'Fact Precision':<25} {v17_fact_precision:>9.1f}% {v20_fact_precision:>9.1f}% {v20_fact_precision - v17_fact_precision:>+8.1f}pp")
    print(f"  {'Fact Recall':<25} {v17_fact_recall:>9.1f}% {v20_fact_recall:>9.1f}% {v20_fact_recall - v17_fact_recall:>+8.1f}pp")
    print(f"  {'Event TP':<25} {v17_ev_tp:>10} {v20_ev_tp:>10} {v20_ev_tp - v17_ev_tp:>+10}")
    print(f"  {'Event FP':<25} {v17_ev_fp:>10} {v20_ev_fp:>10} {v20_ev_fp - v17_ev_fp:>+10}")
    print(f"  {'Event FN':<25} {v17_ev_fn:>10} {v20_ev_fn:>10} {v20_ev_fn - v17_ev_fn:>+10}")
    print(f"  {'Event Precision':<25} {v17_ev_precision:>9.1f}% {v20_ev_precision:>9.1f}% {v20_ev_precision - v17_ev_precision:>+8.1f}pp")
    print(f"  {'Event Recall':<25} {v17_ev_recall:>9.1f}% {v20_ev_recall:>9.1f}% {v20_ev_recall - v17_ev_recall:>+8.1f}pp")

    # Save results
    results = {
        "benchmark_docs": len(selected_docs),
        "docs_processed": total_docs_processed,
        "v17_baseline": {
            "facts": len(v17_facts), "events": len(v17_events),
            "fact_tp": v17_tp, "fact_fp": v17_fp, "fact_fn": v17_fn,
            "fact_precision": round(v17_fact_precision, 1),
            "fact_recall": round(v17_fact_recall, 1),
            "event_tp": v17_ev_tp, "event_fp": v17_ev_fp, "event_fn": v17_ev_fn,
            "event_precision": round(v17_ev_precision, 1),
            "event_recall": round(v17_ev_recall, 1),
        },
        "v20_final": {
            "facts": v20_total_facts, "events": v20_total_events,
            "fact_tp": v20_tp, "fact_fp": v20_fp, "fact_fn": v20_fn,
            "fact_precision": round(v20_fact_precision, 1),
            "fact_recall": round(v20_fact_recall, 1),
            "event_tp": v20_ev_tp, "event_fp": v20_ev_fp, "event_fn": v20_ev_fn,
            "event_precision": round(v20_ev_precision, 1),
            "event_recall": round(v20_ev_recall, 1),
        },
        "structural_stats": dict(structural_stats),
        "pipeline_stats": dict(pipeline_stats),
        "gt_facts": total_gt_facts,
        "gt_events": total_gt_events,
    }

    out_path = Path("intelligence_core/tests/reliability/v21_frozen_benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return results


if __name__ == "__main__":
    results = run_v21_frozen_benchmark()
