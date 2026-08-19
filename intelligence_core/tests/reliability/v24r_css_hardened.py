"""V24R — CSS-hardened extraction + measurement.

Re-runs V20 extraction WITH V24R CSS hardening applied (HTMLStructureParser
now skips <style>, <script>, <template>, <noscript>).

Measures V24R against V23R baseline using same GT and same bipartite matching.
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


def is_css_js_contamination(text: str) -> bool:
    if not text:
        return False
    patterns = [
        r"\.\w+\s*\{[^}]*\}", r"\.\w+:hover\s*\{",
        r"background-color\s*:", r"opacity\s*:\s*\d+%",
        r"border\s*:\s*\d+px", r"padding\s*:\s*\d+px",
        r"margin\s*:\s*\d+px", r"font-size\s*:",
        r"color\s*:\s*#", r"function\s*\(",
        r"var\s+\w+\s*=", r"=>\s*\{",
        r"document\.\w+", r"window\.\w+",
        r"console\.\w+", r"#\w+\s*\{[^}]*\}",
        r"@media\s+", r"@import\s+",
        r"linear-gradient", r"container-type\s*:",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def run_v24r_extraction():
    """Run V24R extraction (V20 + CSS hardening)."""
    selected_docs = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    facts_by_doc = defaultdict(list)
    events_by_doc = defaultdict(list)
    css_filtered = 0

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
        structured_segments = extract_html_structure(blob_bytes)
        has_tables = any(ctx == "TABLE_ROW" for _, ctx, _ in structured_segments)
        has_lists = sum(1 for _, ctx, _ in structured_segments if ctx == "LIST_ITEM") > 5
        has_headings = sum(1 for _, ctx, _ in structured_segments if ctx == "HEADING") > 3
        use_structured = has_tables or has_lists or has_headings
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
                    if is_css_js_contamination(seg_text):
                        css_filtered += 1
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
                    css_filtered += 1
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
    return facts_flat, events_flat, benchmark_doc_ids, css_filtered


def main():
    print("=" * 70)
    print("V24R — CSS/JS/Template Contamination Elimination")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    gt_events = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/event_gt_v1.json"))

    # V23R baseline
    v23r = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v23r_results.json"))
    v23r_v20 = v23r["v23r_reconstruction"]["v20"]
    print(f"\n--- V23R Baseline (V20) ---")
    print(f"  Fact TP={v23r_v20['fact_tp']}  FP={v23r_v20['fact_fp']}  FN={v23r_v20['fact_fn']}")
    print(f"  Fact Precision={v23r_v20['fact_precision']}%  Recall={v23r_v20['fact_recall']}%")
    print(f"  Event TP={v23r_v20['event_tp']}  FP={v23r_v20['event_fp']}  FN={v23r_v20['event_fn']}")
    print(f"  Event Precision={v23r_v20['event_precision']}%  Recall={v23r_v20['event_recall']}%")

    print(f"\n--- V24R Extraction (CSS hardening) ---")
    t0 = time.perf_counter()
    v24r_facts, v24r_events, benchmark_doc_ids, css_filtered = run_v24r_extraction()
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s")
    print(f"  V24R raw facts: {len(v24r_facts)}")
    print(f"  V24R raw events: {len(v24r_events)}")
    print(f"  CSS/JS contaminated segments/facts filtered: {css_filtered}")

    # Save raw
    with open(CORE_REPO / "intelligence_core/tests/reliability/v24r_raw_facts.json", "w") as f:
        json.dump(v24r_facts, f, indent=2, default=str)
    with open(CORE_REPO / "intelligence_core/tests/reliability/v24r_raw_events.json", "w") as f:
        json.dump(v24r_events, f, indent=2, default=str)

    # Match
    v24r_fm = match_bipartite(v24r_facts, gt_facts, benchmark_doc_ids)
    v24r_em = match_events_bipartite(v24r_events, gt_events, benchmark_doc_ids)

    v24r_fact_tp = v24r_fm["tp"]
    v24r_fact_fp = v24r_fm["fp"]
    v24r_fact_fn = v24r_fm["fn"]
    v24r_fact_inv = v24r_fm["invariant_holds"]
    v24r_fact_prec = (v24r_fact_tp / (v24r_fact_tp + v24r_fact_fp) * 100) if (v24r_fact_tp + v24r_fact_fp) else 0
    v24r_fact_rec = (v24r_fact_tp / (v24r_fact_tp + v24r_fact_fn) * 100) if (v24r_fact_tp + v24r_fact_fn) else 0

    v24r_ev_tp = v24r_em["tp"]
    v24r_ev_fp = v24r_em["fp"]
    v24r_ev_fn = v24r_em["fn"]
    v24r_ev_inv = v24r_em["invariant_holds"]
    v24r_ev_prec = (v24r_ev_tp / (v24r_ev_tp + v24r_ev_fp) * 100) if (v24r_ev_tp + v24r_ev_fp) else 0
    v24r_ev_rec = (v24r_ev_tp / (v24r_ev_tp + v24r_ev_fn) * 100) if (v24r_ev_tp + v24r_ev_fn) else 0

    print(f"\n--- V24R Matching ---")
    print(f"  Fact: TP={v24r_fact_tp}  FP={v24r_fact_fp}  FN={v24r_fact_fn}  Inv={'✓' if v24r_fact_inv else '✗'}")
    print(f"  Fact Precision: {v24r_fact_prec:.2f}%")
    print(f"  Fact Recall:    {v24r_fact_rec:.2f}%")
    print(f"  Event: TP={v24r_ev_tp}  FP={v24r_ev_fp}  FN={v24r_ev_fn}  Inv={'✓' if v24r_ev_inv else '✗'}")
    print(f"  Event Precision: {v24r_ev_prec:.2f}%")
    print(f"  Event Recall:    {v24r_ev_rec:.2f}%")

    # V23R vs V24R
    print(f"\n--- V23R vs V24R Comparison ---")
    print(f"\n  {'Metric':<22} {'V23R':>10} {'V24R':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Fact TP':<22} {v23r_v20['fact_tp']:>10} {v24r_fact_tp:>10} {v24r_fact_tp - v23r_v20['fact_tp']:>+10}")
    print(f"  {'Fact FP':<22} {v23r_v20['fact_fp']:>10} {v24r_fact_fp:>10} {v24r_fact_fp - v23r_v20['fact_fp']:>+10}")
    print(f"  {'Fact FN':<22} {v23r_v20['fact_fn']:>10} {v24r_fact_fn:>10} {v24r_fact_fn - v23r_v20['fact_fn']:>+10}")
    print(f"  {'Fact Precision':<22} {v23r_v20['fact_precision']:>9.2f}% {v24r_fact_prec:>9.2f}% {v24r_fact_prec - v23r_v20['fact_precision']:>+8.2f}pp")
    print(f"  {'Fact Recall':<22} {v23r_v20['fact_recall']:>9.2f}% {v24r_fact_rec:>9.2f}% {v24r_fact_rec - v23r_v20['fact_recall']:>+8.2f}pp")
    print(f"  {'Event TP':<22} {v23r_v20['event_tp']:>10} {v24r_ev_tp:>10} {v24r_ev_tp - v23r_v20['event_tp']:>+10}")
    print(f"  {'Event FP':<22} {v23r_v20['event_fp']:>10} {v24r_ev_fp:>10} {v24r_ev_fp - v23r_v20['event_fp']:>+10}")
    print(f"  {'Event FN':<22} {v23r_v20['event_fn']:>10} {v24r_ev_fn:>10} {v24r_ev_fn - v23r_v20['event_fn']:>+10}")
    print(f"  {'Event Precision':<22} {v23r_v20['event_precision']:>9.2f}% {v24r_ev_prec:>9.2f}% {v24r_ev_prec - v23r_v20['event_precision']:>+8.2f}pp")
    print(f"  {'Event Recall':<22} {v23r_v20['event_recall']:>9.2f}% {v24r_ev_rec:>9.2f}% {v24r_ev_rec - v23r_v20['event_recall']:>+8.2f}pp")

    # Save
    results = {
        "v24r_measurement": {
            "fact_tp": v24r_fact_tp, "fact_fp": v24r_fact_fp, "fact_fn": v24r_fact_fn,
            "fact_precision": round(v24r_fact_prec, 2),
            "fact_recall": round(v24r_fact_rec, 2),
            "fact_invariant_holds": v24r_fact_inv,
            "event_tp": v24r_ev_tp, "event_fp": v24r_ev_fp, "event_fn": v24r_ev_fn,
            "event_precision": round(v24r_ev_prec, 2),
            "event_recall": round(v24r_ev_rec, 2),
            "event_invariant_holds": v24r_ev_inv,
            "css_filtered": css_filtered,
        },
        "deltas_vs_v23r": {
            "fact_recall_delta_pp": round(v24r_fact_rec - v23r_v20['fact_recall'], 2),
            "event_recall_delta_pp": round(v24r_ev_rec - v23r_v20['event_recall'], 2),
            "fact_precision_delta_pp": round(v24r_fact_prec - v23r_v20['fact_precision'], 2),
            "fp_eliminated": v23r_v20['fact_fp'] - v24r_fact_fp,
        },
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v24r_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
