"""V27R — Percentage Evidence Semantic Equivalence.

Reconstructs V27 from V26R verified checkpoint.
  1. PERCENT_EQUIV in evidence classifier (already applied to v10_evidence_closure.py)
  2. Pattern Family 1 with (?!\w) fix (already applied to v5_re_extract_facts.py)
  3. Extended navigation rejection (already applied to classify_evidence_strict)
  4. Measure independently against V26R baseline

Independent measurement — NOT using previous V27 reported metrics.
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
from intelligence_core.normalize import strip_html
from intelligence_core.detect import detect_event
from intelligence_core.tests.reliability.v19_forensic import normalize_metric_v19
from intelligence_core.tests.reliability.v14_ground_truth import select_300_documents
from intelligence_core.tests.reliability.v13_reprocess import classify_language
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v15_recall_recovery import extract_html_structure
from intelligence_core.tests.reliability.v13_recall_patterns import (
    is_navigation_content_v13, validate_event_context_v13,
)
from intelligence_core.tests.reliability.v10_evidence_closure import (
    classify_evidence_strict, expand_evidence_for_direct,
)
from intelligence_core.tests.reliability.v21_frozen_benchmark import (
    get_patterns, get_source_class, SRC_TO_EVENT_TYPES,
)
from intelligence_core.tests.reliability.v23r_bipartite_matching import (
    canonical_value, canonical_metric, canonical_identity,
    match_bipartite, match_events_bipartite,
)
from intelligence_core.tests.reliability.v24r_css_hardened import is_css_js_contamination
from intelligence_core.tests.reliability.v25r_semantic_table_parser import (
    parse_semantic_tables, filter_negative_tables,
)


def run_v27r_extraction():
    selected_docs = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    facts_by_doc = defaultdict(list)
    events_by_doc = defaultdict(list)

    for doc_entry in selected_docs:
        doc_id = doc_entry["doc_id"]
        src_id = doc_entry.get("src_id", "")
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
            continue
        flat_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))

        tables = parse_semantic_tables(blob_bytes, document_id=doc_id)
        tables, _ = filter_negative_tables(tables)

        structured_segments = extract_html_structure(blob_bytes)
        has_tables = bool(tables)
        has_lists = sum(1 for _, ctx, _ in structured_segments if ctx == "LIST_ITEM") > 5
        has_headings = sum(1 for _, ctx, _ in structured_segments if ctx == "HEADING") > 3
        use_structured = has_tables or has_lists or has_headings
        language = classify_language(flat_text)
        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            patterns = get_patterns(language, event_type)  # V27R: includes Family 1 + Family 2
            if not patterns:
                continue
            flat_facts = improved_extract_facts(flat_text, patterns, rep["representation_id"], doc_id)
            structured_facts = []
            if use_structured:
                for seg_text, seg_ctx, seg_headers in structured_segments:
                    if is_navigation_content_v13(seg_text):
                        continue
                    if is_css_js_contamination(seg_text):
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
            seen = set()
            all_facts = []
            for f in flat_facts + structured_facts:
                if is_css_js_contamination(f.excerpt):
                    continue
                key = (f.document_id, normalize_metric_v19(f.pattern_ref), str(f.value))
                if key not in seen:
                    seen.add(key)
                    all_facts.append(f)
            if not all_facts:
                continue
            clean = []
            for f in all_facts:
                if is_navigation_content_v13(f.excerpt):
                    ne, st = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in st:
                        f.excerpt = ne
                        clean.append(f)
                else:
                    clean.append(f)
            if not clean:
                continue
            direct = []
            for f in clean:
                cls, _ = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    ne, st = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in st:
                        f.excerpt = ne
                        direct.append(f)
                    elif cls == "INVALID":
                        pass
                    else:
                        direct.append(f)
                else:
                    direct.append(f)
            if not direct:
                continue
            valid, reason = validate_event_context_v13(event_type, flat_text, language)
            if not valid:
                continue
            for f in direct:
                facts_by_doc[doc_id].append(f.to_dict())
            ev = detect_event(direct, doc_id, event_type)
            if ev is not None:
                events_by_doc[doc_id].append(ev.to_dict())

    facts_flat = [f for facts in facts_by_doc.values() for f in facts]
    events_flat = [ev for evs in events_by_doc.values() for ev in evs]
    return facts_flat, events_flat, benchmark_doc_ids


def main():
    print("=" * 70)
    print("V27R — Percentage Evidence Semantic Equivalence")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    gt_events = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/event_gt_v1.json"))

    v26r = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v26r_results.json"))
    v26r_m = v26r["v26r_measurement"]
    print(f"\n--- V26R Baseline ---")
    print(f"  Fact TP={v26r_m['fact_tp']}  FP={v26r_m['fact_fp']}  FN={v26r_m['fact_fn']}")
    print(f"  Fact Precision={v26r_m['fact_precision']}%  Recall={v26r_m['fact_recall']}%")
    print(f"  Event TP={v26r_m['event_tp']}  FP={v26r_m['event_fp']}  FN={v26r_m['event_fn']}")
    print(f"  Event Precision={v26r_m['event_precision']}%  Recall={v26r_m['event_recall']}%")

    print(f"\n--- V27R Extraction (PERCENT_EQUIV + Pattern Family 1) ---")
    t0 = time.perf_counter()
    v27r_facts, v27r_events, benchmark_doc_ids = run_v27r_extraction()
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s")
    print(f"  V27R raw facts: {len(v27r_facts)}")
    print(f"  V27R raw events: {len(v27r_events)}")

    # Save raw
    with open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_facts.json", "w") as f:
        json.dump(v27r_facts, f, indent=2, default=str)
    with open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_events.json", "w") as f:
        json.dump(v27r_events, f, indent=2, default=str)

    # Match
    v27r_fm = match_bipartite(v27r_facts, gt_facts, benchmark_doc_ids)
    v27r_em = match_events_bipartite(v27r_events, gt_events, benchmark_doc_ids)

    v27r_fact_tp = v27r_fm["tp"]
    v27r_fact_fp = v27r_fm["fp"]
    v27r_fact_fn = v27r_fm["fn"]
    v27r_fact_inv = v27r_fm["invariant_holds"]
    v27r_fact_prec = (v27r_fact_tp / (v27r_fact_tp + v27r_fact_fp) * 100) if (v27r_fact_tp + v27r_fact_fp) else 0
    v27r_fact_rec = (v27r_fact_tp / (v27r_fact_tp + v27r_fact_fn) * 100) if (v27r_fact_tp + v27r_fact_fn) else 0

    v27r_ev_tp = v27r_em["tp"]
    v27r_ev_fp = v27r_em["fp"]
    v27r_ev_fn = v27r_em["fn"]
    v27r_ev_inv = v27r_em["invariant_holds"]
    v27r_ev_prec = (v27r_ev_tp / (v27r_ev_tp + v27r_ev_fp) * 100) if (v27r_ev_tp + v27r_ev_fp) else 0
    v27r_ev_rec = (v27r_ev_tp / (v27r_ev_tp + v27r_ev_fn) * 100) if (v27r_ev_tp + v27r_ev_fn) else 0

    print(f"\n--- V27R Matching ---")
    print(f"  Fact: TP={v27r_fact_tp}  FP={v27r_fact_fp}  FN={v27r_fact_fn}  Inv={'✓' if v27r_fact_inv else '✗'}")
    print(f"  Fact Precision: {v27r_fact_prec:.2f}%")
    print(f"  Fact Recall:    {v27r_fact_rec:.2f}%")
    print(f"  Event: TP={v27r_ev_tp}  FP={v27r_ev_fp}  FN={v27r_ev_fn}  Inv={'✓' if v27r_ev_inv else '✗'}")
    print(f"  Event Precision: {v27r_ev_prec:.2f}%")
    print(f"  Event Recall:    {v27r_ev_rec:.2f}%")

    # V26R vs V27R
    print(f"\n--- V26R vs V27R Comparison ---")
    print(f"\n  {'Metric':<22} {'V26R':>10} {'V27R':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Fact TP':<22} {v26r_m['fact_tp']:>10} {v27r_fact_tp:>10} {v27r_fact_tp - v26r_m['fact_tp']:>+10}")
    print(f"  {'Fact FP':<22} {v26r_m['fact_fp']:>10} {v27r_fact_fp:>10} {v27r_fact_fp - v26r_m['fact_fp']:>+10}")
    print(f"  {'Fact FN':<22} {v26r_m['fact_fn']:>10} {v27r_fact_fn:>10} {v27r_fact_fn - v26r_m['fact_fn']:>+10}")
    print(f"  {'Fact Precision':<22} {v26r_m['fact_precision']:>9.2f}% {v27r_fact_prec:>9.2f}% {v27r_fact_prec - v26r_m['fact_precision']:>+8.2f}pp")
    print(f"  {'Fact Recall':<22} {v26r_m['fact_recall']:>9.2f}% {v27r_fact_rec:>9.2f}% {v27r_fact_rec - v26r_m['fact_recall']:>+8.2f}pp")
    print(f"  {'Event TP':<22} {v26r_m['event_tp']:>10} {v27r_ev_tp:>10} {v27r_ev_tp - v26r_m['event_tp']:>+10}")
    print(f"  {'Event FP':<22} {v26r_m['event_fp']:>10} {v27r_ev_fp:>10} {v27r_ev_fp - v26r_m['event_fp']:>+10}")
    print(f"  {'Event FN':<22} {v26r_m['event_fn']:>10} {v27r_ev_fn:>10} {v27r_ev_fn - v26r_m['event_fn']:>+10}")
    print(f"  {'Event Precision':<22} {v26r_m['event_precision']:>9.2f}% {v27r_ev_prec:>9.2f}% {v27r_ev_prec - v26r_m['event_precision']:>+8.2f}pp")
    print(f"  {'Event Recall':<22} {v26r_m['event_recall']:>9.2f}% {v27r_ev_rec:>9.2f}% {v27r_ev_rec - v26r_m['event_recall']:>+8.2f}pp")

    # FP forensics
    print(f"\n--- V27R FP Forensics ---")
    gt_mult = Counter()
    for g in gt_facts:
        if g.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (g["document_id"], canonical_metric(g["metric"]), canonical_value(g["value"]))
        gt_mult[ident] += 1

    v27r_facts_by_ident = defaultdict(list)
    for f in v27r_facts:
        if f.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (
            f.get("document_id", ""),
            canonical_metric(f.get("metric", ""), f.get("pattern_ref", "")),
            canonical_value(f.get("value", "")),
        )
        v27r_facts_by_ident[ident].append(f)

    fp_facts = []
    tp_count = 0
    for ident, facts in v27r_facts_by_ident.items():
        g = gt_mult.get(ident, 0)
        c = len(facts)
        tp_for_ident = min(g, c)
        tp_count += tp_for_ident
        fp_facts.extend(facts[tp_for_ident:])

    fp_classification = Counter()
    for fp in fp_facts:
        doc_id = fp.get("document_id", "")
        value = canonical_value(fp.get("value", ""))
        metric = canonical_metric(fp.get("metric", ""), fp.get("pattern_ref", ""))
        gt_for_doc = [g for g in gt_facts if g.get("document_id") == doc_id]
        gt_values = set(canonical_value(g.get("value", "")) for g in gt_for_doc)
        if value in gt_values:
            gt_metrics_for_value = set(
                canonical_metric(g.get("metric", "")) for g in gt_for_doc
                if canonical_value(g.get("value", "")) == value
            )
            if metric not in gt_metrics_for_value:
                fp_classification["WRONG_METRIC"] += 1
            else:
                fp_classification["DUPLICATE_SEMANTIC_FACT"] += 1
        else:
            if is_css_js_contamination(fp.get("excerpt", "")):
                fp_classification["CSS_JS_CONTAMINATION"] += 1
            else:
                fp_classification["TRUE_FP"] += 1

    print(f"  Total FPs: {len(fp_facts)}")
    for cls, count in fp_classification.most_common():
        print(f"    {cls:<30} {count}")

    # Mechanical vs forensic
    mechanical_prec = (tp_count / (tp_count + len(fp_facts)) * 100) if (tp_count + len(fp_facts)) else 0
    forensic_true_fp = fp_classification.get("TRUE_FP", 0) + fp_classification.get("CSS_JS_CONTAMINATION", 0)
    forensic_tp = tp_count + fp_classification.get("WRONG_METRIC", 0) + fp_classification.get("DUPLICATE_SEMANTIC_FACT", 0)
    forensic_prec = (forensic_tp / (forensic_tp + forensic_true_fp) * 100) if (forensic_tp + forensic_true_fp) else 0

    print(f"\n--- Mechanical vs Forensic Precision (reported SEPARATELY) ---")
    print(f"  Mechanical:  TP={tp_count}  FP={len(fp_facts)}  → {mechanical_prec:.2f}%")
    print(f"  Forensic:    TP={forensic_tp}  FP={forensic_true_fp}  → {forensic_prec:.2f}%")

    # Acceptance gate
    new_tps = v27r_fact_tp - v26r_m['fact_tp']
    recall_ok = v27r_fact_rec > v26r_m['fact_recall']
    precision_ok = v27r_fact_prec >= v26r_m['fact_precision'] - 1
    print(f"\n--- Acceptance Gate ---")
    print(f"  New TPs: {new_tps}")
    print(f"  Recall improved: {'✓' if recall_ok else '✗'} ({v26r_m['fact_recall']:.2f}% → {v27r_fact_rec:.2f}%)")
    print(f"  Precision maintained: {'✓' if precision_ok else '✗'} ({v26r_m['fact_precision']:.2f}% → {v27r_fact_prec:.2f}%)")
    print(f"  Verdict: {'ACCEPTED' if (recall_ok and precision_ok) else 'REJECTED'}")

    # Save
    results = {
        "v27r_measurement": {
            "fact_tp": v27r_fact_tp, "fact_fp": v27r_fact_fp, "fact_fn": v27r_fact_fn,
            "fact_precision": round(v27r_fact_prec, 2),
            "fact_recall": round(v27r_fact_rec, 2),
            "fact_invariant_holds": v27r_fact_inv,
            "event_tp": v27r_ev_tp, "event_fp": v27r_ev_fp, "event_fn": v27r_ev_fn,
            "event_precision": round(v27r_ev_prec, 2),
            "event_recall": round(v27r_ev_rec, 2),
            "event_invariant_holds": v27r_ev_inv,
        },
        "mechanical_precision": round(mechanical_prec, 2),
        "forensic_precision": round(forensic_prec, 2),
        "fp_classification": dict(fp_classification),
        "deltas_vs_v26r": {
            "fact_recall_delta_pp": round(v27r_fact_rec - v26r_m['fact_recall'], 2),
            "event_recall_delta_pp": round(v27r_ev_rec - v26r_m['event_recall'], 2),
            "new_tps": new_tps,
            "accepted": recall_ok and precision_ok,
        },
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v27r_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
