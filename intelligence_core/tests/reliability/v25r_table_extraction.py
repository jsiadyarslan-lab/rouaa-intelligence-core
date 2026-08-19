"""V25R — Semantic Table Extraction + Independent Measurement.

Re-runs V24R pipeline WITH V25R semantic table extraction enabled.
Tables are parsed into SemanticTable objects and their cells are
matched against existing REFINED_PATTERNS.

Measures V25R against V24R baseline. The key question:
  Does table extraction recover NEW TPs, or are table values
  already captured by flat extraction?
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


def extract_table_facts(tables, patterns, rep_id, doc_id, flat_text):
    """Extract facts from semantic tables using existing patterns."""
    table_facts = []
    for tbl in tables:
        for row in tbl.body_rows:
            for cell in row.cells:
                if not cell.value:
                    continue
                if is_css_js_contamination(cell.value):
                    continue
                composite = f"{row.row_label} {cell.column_label} {cell.value}"
                facts = improved_extract_facts(composite, patterns, rep_id, doc_id)
                for f in facts:
                    unit_suffix = ""
                    if cell.unit == "percent":
                        unit_suffix = "%"
                    elif cell.unit == "basis_points":
                        unit_suffix = " bps"
                    elif cell.unit:
                        unit_suffix = f" {cell.unit}"
                    f.excerpt = f"[TABLE: {row.row_label} | {cell.column_label}] {cell.numeric_value}{unit_suffix}"
                    f.pattern_ref = f"TABLE:{tbl.table_id}"
                    table_facts.append(f)
    return table_facts


def run_v25r_extraction():
    selected_docs = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    facts_by_doc = defaultdict(list)
    events_by_doc = defaultdict(list)
    table_stats = Counter()

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

        # V25R: Parse semantic tables
        tables = parse_semantic_tables(blob_bytes, document_id=doc_id)
        tables, tbl_filter_stats = filter_negative_tables(tables)
        table_stats["tables_parsed"] += len(tables)
        for tbl in tables:
            table_stats["table_rows"] += len(tbl.body_rows)
            for r in tbl.body_rows:
                table_stats["table_cells"] += len(r.cells)
        for k, v in tbl_filter_stats.items():
            table_stats[f"filter_{k}"] += v

        structured_segments = extract_html_structure(blob_bytes)
        has_tables = bool(tables)
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

            # V25R: Semantic table extraction
            table_facts = extract_table_facts(tables, patterns, rep["representation_id"], doc_id, flat_text)
            table_stats["table_facts_emitted"] += len(table_facts)

            seen = set()
            all_facts = []
            for f in flat_facts + structured_facts + table_facts:
                if is_css_js_contamination(f.excerpt):
                    table_stats["css_filtered"] += 1
                    continue
                key = (f.document_id, normalize_metric_v19(f.pattern_ref), str(f.value))
                if key not in seen:
                    seen.add(key)
                    all_facts.append(f)
                    if "[TABLE:" in f.excerpt and " | " in f.excerpt:
                        table_stats["TABLE"] += 1
                    elif "[LIST]" in f.excerpt:
                        table_stats["LIST"] += 1
                    elif "[HEADING]" in f.excerpt:
                        table_stats["HEADING"] += 1
                    else:
                        table_stats["PARAGRAPH"] += 1
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
    return facts_flat, events_flat, benchmark_doc_ids, table_stats


def main():
    print("=" * 70)
    print("V25R — Semantic Table Intelligence Recovery")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    gt_events = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/event_gt_v1.json"))

    v24r = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v24r_results.json"))
    v24r_m = v24r["v24r_measurement"]
    print(f"\n--- V24R Baseline ---")
    print(f"  Fact TP={v24r_m['fact_tp']}  FP={v24r_m['fact_fp']}  FN={v24r_m['fact_fn']}")
    print(f"  Fact Precision={v24r_m['fact_precision']}%  Recall={v24r_m['fact_recall']}%")
    print(f"  Event TP={v24r_m['event_tp']}  FP={v24r_m['event_fp']}  FN={v24r_m['event_fn']}")
    print(f"  Event Precision={v24r_m['event_precision']}%  Recall={v24r_m['event_recall']}%")

    print(f"\n--- V25R Extraction (semantic tables) ---")
    t0 = time.perf_counter()
    v25r_facts, v25r_events, benchmark_doc_ids, table_stats = run_v25r_extraction()
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s")
    print(f"  V25R raw facts: {len(v25r_facts)}")
    print(f"  V25R raw events: {len(v25r_events)}")

    print(f"\n--- Table Statistics ---")
    for k, v in table_stats.most_common():
        print(f"  {k:<30} {v}")

    # Save raw
    with open(CORE_REPO / "intelligence_core/tests/reliability/v25r_raw_facts.json", "w") as f:
        json.dump(v25r_facts, f, indent=2, default=str)
    with open(CORE_REPO / "intelligence_core/tests/reliability/v25r_raw_events.json", "w") as f:
        json.dump(v25r_events, f, indent=2, default=str)

    # Match
    v25r_fm = match_bipartite(v25r_facts, gt_facts, benchmark_doc_ids)
    v25r_em = match_events_bipartite(v25r_events, gt_events, benchmark_doc_ids)

    v25r_fact_tp = v25r_fm["tp"]
    v25r_fact_fp = v25r_fm["fp"]
    v25r_fact_fn = v25r_fm["fn"]
    v25r_fact_inv = v25r_fm["invariant_holds"]
    v25r_fact_prec = (v25r_fact_tp / (v25r_fact_tp + v25r_fact_fp) * 100) if (v25r_fact_tp + v25r_fact_fp) else 0
    v25r_fact_rec = (v25r_fact_tp / (v25r_fact_tp + v25r_fact_fn) * 100) if (v25r_fact_tp + v25r_fact_fn) else 0

    v25r_ev_tp = v25r_em["tp"]
    v25r_ev_fp = v25r_em["fp"]
    v25r_ev_fn = v25r_em["fn"]
    v25r_ev_inv = v25r_em["invariant_holds"]
    v25r_ev_prec = (v25r_ev_tp / (v25r_ev_tp + v25r_ev_fp) * 100) if (v25r_ev_tp + v25r_ev_fp) else 0
    v25r_ev_rec = (v25r_ev_tp / (v25r_ev_tp + v25r_ev_fn) * 100) if (v25r_ev_tp + v25r_ev_fn) else 0

    print(f"\n--- V25R Matching ---")
    print(f"  Fact: TP={v25r_fact_tp}  FP={v25r_fact_fp}  FN={v25r_fact_fn}  Inv={'✓' if v25r_fact_inv else '✗'}")
    print(f"  Fact Precision: {v25r_fact_prec:.2f}%")
    print(f"  Fact Recall:    {v25r_fact_rec:.2f}%")
    print(f"  Event: TP={v25r_ev_tp}  FP={v25r_ev_fp}  FN={v25r_ev_fn}  Inv={'✓' if v25r_ev_inv else '✗'}")
    print(f"  Event Precision: {v25r_ev_prec:.2f}%")
    print(f"  Event Recall:    {v25r_ev_rec:.2f}%")

    # V24R vs V25R
    print(f"\n--- V24R vs V25R Comparison ---")
    print(f"\n  {'Metric':<22} {'V24R':>10} {'V25R':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Fact TP':<22} {v24r_m['fact_tp']:>10} {v25r_fact_tp:>10} {v25r_fact_tp - v24r_m['fact_tp']:>+10}")
    print(f"  {'Fact FP':<22} {v24r_m['fact_fp']:>10} {v25r_fact_fp:>10} {v25r_fact_fp - v24r_m['fact_fp']:>+10}")
    print(f"  {'Fact FN':<22} {v24r_m['fact_fn']:>10} {v25r_fact_fn:>10} {v25r_fact_fn - v24r_m['fact_fn']:>+10}")
    print(f"  {'Fact Precision':<22} {v24r_m['fact_precision']:>9.2f}% {v25r_fact_prec:>9.2f}% {v25r_fact_prec - v24r_m['fact_precision']:>+8.2f}pp")
    print(f"  {'Fact Recall':<22} {v24r_m['fact_recall']:>9.2f}% {v25r_fact_rec:>9.2f}% {v25r_fact_rec - v24r_m['fact_recall']:>+8.2f}pp")
    print(f"  {'Event TP':<22} {v24r_m['event_tp']:>10} {v25r_ev_tp:>10} {v25r_ev_tp - v24r_m['event_tp']:>+10}")
    print(f"  {'Event FP':<22} {v24r_m['event_fp']:>10} {v25r_ev_fp:>10} {v25r_ev_fp - v24r_m['event_fp']:>+10}")
    print(f"  {'Event FN':<22} {v24r_m['event_fn']:>10} {v25r_ev_fn:>10} {v25r_ev_fn - v24r_m['event_fn']:>+10}")
    print(f"  {'Event Precision':<22} {v24r_m['event_precision']:>9.2f}% {v25r_ev_prec:>9.2f}% {v25r_ev_prec - v24r_m['event_precision']:>+8.2f}pp")
    print(f"  {'Event Recall':<22} {v24r_m['event_recall']:>9.2f}% {v25r_ev_rec:>9.2f}% {v25r_ev_rec - v24r_m['event_recall']:>+8.2f}pp")

    # Table attribution
    table_emitted_facts = sum(1 for f in v25r_facts if "TABLE:" in f.get("pattern_ref", ""))
    print(f"\n--- Table Recovery Attribution ---")
    print(f"  Table-emitted facts (in V25R raw): {table_emitted_facts}")
    print(f"  Tables parsed: {table_stats['tables_parsed']}")
    print(f"  Table facts emitted (before dedup): {table_stats['table_facts_emitted']}")
    new_tps = v25r_fact_tp - v24r_m['fact_tp']
    print(f"  New TPs from table extraction: {new_tps}")
    print(f"\n  Hypothesis: 'TABLE is the major remaining structural recall opportunity'")
    print(f"  Result: {'CONFIRMED' if new_tps > 0 else 'REFUTED — table facts are duplicates of flat-extracted facts'}")

    # Save
    results = {
        "v25r_measurement": {
            "fact_tp": v25r_fact_tp, "fact_fp": v25r_fact_fp, "fact_fn": v25r_fact_fn,
            "fact_precision": round(v25r_fact_prec, 2),
            "fact_recall": round(v25r_fact_rec, 2),
            "fact_invariant_holds": v25r_fact_inv,
            "event_tp": v25r_ev_tp, "event_fp": v25r_ev_fp, "event_fn": v25r_ev_fn,
            "event_precision": round(v25r_ev_prec, 2),
            "event_recall": round(v25r_ev_rec, 2),
            "event_invariant_holds": v25r_ev_inv,
        },
        "table_statistics": dict(table_stats),
        "deltas_vs_v24r": {
            "fact_recall_delta_pp": round(v25r_fact_rec - v24r_m['fact_recall'], 2),
            "event_recall_delta_pp": round(v25r_ev_rec - v24r_m['event_recall'], 2),
            "new_tps_from_tables": new_tps,
        },
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v25r_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
