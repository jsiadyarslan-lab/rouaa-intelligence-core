"""V26R — FN Classification + Action-Type Recovery.

Reconstructs V26 from V25R verified checkpoint.
  1. Classify all FN facts into taxonomy (TRUE_EXTRACTION_GAP vs CARDINALITY_GAP)
  2. Implement Pattern Family 2 (action_type always)
  3. Measure independently against V25R baseline

Independent measurement — NOT using previous V26 reported metrics.
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


# ─────────────────────────────────────────────────────────────────────────────
# FN CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_fn(gt_fact, doc_text, core_count_at_identity, extracted_values):
    """Classify a GT false negative."""
    doc_id = gt_fact.get("document_id", "")
    metric = canonical_metric(gt_fact.get("metric", ""))
    value = str(gt_fact.get("value", ""))
    canonical_val = canonical_value(value)
    language = gt_fact.get("language", "en")

    if core_count_at_identity > 0:
        gap_type = "CARDINALITY_GAP"
    else:
        gap_type = "TRUE_EXTRACTION_GAP"

    if gap_type == "CARDINALITY_GAP":
        if metric == "percentage_statistic":
            return gap_type, "STATISTICAL_EXPRESSION", "PERCENTAGE_CARDINALITY"
        if metric in ("usd_amount", "penalty_amount"):
            return gap_type, "FINANCIAL_EXPRESSION", "AMOUNT_CARDINALITY"
        if metric == "rate_decision":
            return gap_type, "MONETARY_EXPRESSION", "RATE_CARDINALITY"
        return gap_type, "PATTERN_LEXICON", "OTHER_CARDINALITY"

    if language != "en":
        return gap_type, "LANGUAGE", language.upper()

    if not doc_text:
        return gap_type, "OTHER", "NO_DOC_TEXT"

    value_in_doc = value in doc_text or canonical_val in doc_text
    if not value_in_doc:
        if re.fullmatch(r"20\d{2}", value):
            return gap_type, "DATE_PERIOD", "YEAR_VALUE"
        return gap_type, "VALUE_FORMAT", "VALUE_NOT_IN_DOC_TEXT"

    pos = doc_text.find(value)
    if pos == -1:
        pos = doc_text.find(canonical_val)
    if pos == -1:
        return gap_type, "OTHER", "VALUE_NOT_LOCATABLE"

    ctx_start = max(0, pos - 150)
    ctx_end = min(len(doc_text), pos + 150)
    context = doc_text[ctx_start:ctx_end].lower()

    if re.search(rf"\b{re.escape(canonical_val)}\s*(?:-|–|to)\s*\d", context):
        return gap_type, "VALUE_FORMAT", "RANGE"
    if re.search(rf"(?:<|>|≤|≥|less\s+than|greater\s+than)\s*{re.escape(canonical_val)}", context):
        return gap_type, "VALUE_FORMAT", "INEQUALITY"
    if re.search(rf"(?:approximately|approx\.?|~|about|around|nearly)\s*{re.escape(canonical_val)}", context):
        return gap_type, "VALUE_FORMAT", "APPROXIMATE"
    if re.search(rf"\({re.escape(canonical_val)}\)", context):
        return gap_type, "VALUE_FORMAT", "PARENTHETICAL"
    if re.search(rf"(?:-|−|negative)\s*{re.escape(canonical_val)}", context):
        return gap_type, "VALUE_FORMAT", "NEGATIVE_VALUE"

    has_percent = bool(re.search(r"%|percent", context))
    has_econ_keyword = bool(re.search(r"\b(?:gdp|inflation|cpi|unemployment|employment|trade|production|output|manufacturing|industrial)\b", context))
    has_magnitude = bool(re.search(r"\b(?:million|billion|thousand|trillion|m|bn|b)\b", context))
    has_dollar = bool(re.search(r"\$\s*\d", context))
    has_penalty_keyword = bool(re.search(r"\b(?:penalty|fine|settlement|disgorgement|charged|sued|consent\s+order|cease\s+and\s+desist|injunction|enforcement)\b", context))
    has_rate_decision = bool(re.search(r"\b(?:maintain|raise|cut|lower|hold)\w*\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate\b", context))

    if metric == "percentage_statistic":
        if has_percent:
            if has_econ_keyword:
                if re.search(r"\bgdp\b", context):
                    return gap_type, "STATISTICAL_EXPRESSION", "GDP_PERCENTAGE"
                if re.search(r"\b(?:inflation|cpi)\b", context):
                    return gap_type, "STATISTICAL_EXPRESSION", "INFLATION_PERCENTAGE"
                if re.search(r"\b(?:unemployment|employment)\b", context):
                    return gap_type, "STATISTICAL_EXPRESSION", "EMPLOYMENT_PERCENTAGE"
                if re.search(r"\b(?:production|output|manufacturing|industrial)\b", context):
                    return gap_type, "STATISTICAL_EXPRESSION", "PRODUCTION_PERCENTAGE"
                if re.search(r"\b(?:trade|export|import)\b", context):
                    return gap_type, "STATISTICAL_EXPRESSION", "TRADE_PERCENTAGE"
            return gap_type, "STATISTICAL_EXPRESSION", "OTHER_PERCENTAGE"
        return gap_type, "PATTERN_LEXICON", "BARE_NUMBER_NO_PERCENT"

    if metric in ("usd_amount", "penalty_amount"):
        if has_dollar:
            return gap_type, "FINANCIAL_EXPRESSION", "DOLLAR_AMOUNT"
        if has_magnitude:
            return gap_type, "FINANCIAL_EXPRESSION", "MAGNITUDE_AMOUNT"
        if has_penalty_keyword:
            return gap_type, "REGULATORY_EXPRESSION", "PENALTY_AMOUNT"
        return gap_type, "FINANCIAL_EXPRESSION", "OTHER_AMOUNT"

    if metric == "action_type":
        if has_penalty_keyword:
            return gap_type, "REGULATORY_EXPRESSION", "ENFORCEMENT_ACTION"
        return gap_type, "REGULATORY_EXPRESSION", "ACTION_TYPE_NO_KEYWORD"

    if metric == "rate_decision":
        if has_rate_decision:
            return gap_type, "MONETARY_EXPRESSION", "RATE_DECISION"
        return gap_type, "MONETARY_EXPRESSION", "RATE_DECISION_NO_KEYWORD"

    return gap_type, "OTHER", "UNCLASSIFIED"


# ─────────────────────────────────────────────────────────────────────────────
# V26R EXTRACTION (V25R + Family 2: action_type always)
# ─────────────────────────────────────────────────────────────────────────────

def run_v26r_extraction():
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
            patterns = get_patterns(language, event_type)  # V26R: includes Family 2
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
    print("V26R — FN Classification + Action-Type Recovery")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    gt_events = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/event_gt_v1.json"))

    v25r = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v25r_results.json"))
    v25r_m = v25r["v25r_measurement"]
    print(f"\n--- V25R Baseline ---")
    print(f"  Fact TP={v25r_m['fact_tp']}  FP={v25r_m['fact_fp']}  FN={v25r_m['fact_fn']}")
    print(f"  Fact Precision={v25r_m['fact_precision']}%  Recall={v25r_m['fact_recall']}%")

    # ─── FN Taxonomy ───
    print(f"\n--- FN Taxonomy ---")
    v25r_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v25r_raw_facts.json"))

    selected_docs = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    doc_text_cache = {}

    def get_doc_text(doc_id):
        if doc_id in doc_text_cache:
            return doc_text_cache[doc_id]
        rep = None
        for rid, r in reps_by_id.items():
            if r.get("document_id") == doc_id:
                rep = r
                break
        if not rep:
            doc_text_cache[doc_id] = ""
            return ""
        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            doc_text_cache[doc_id] = ""
            return ""
        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                doc_text_cache[doc_id] = ""
                return ""
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
            doc_text_cache[doc_id] = text
            return text
        except Exception:
            doc_text_cache[doc_id] = ""
            return ""

    # Build GT mult and V25R mult
    gt_mult = Counter()
    for g in gt_facts:
        if g.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (g["document_id"], canonical_metric(g["metric"]), canonical_value(g["value"]))
        gt_mult[ident] += 1

    v25r_mult = Counter()
    for f in v25r_facts:
        if f.get("document_id") not in benchmark_doc_ids:
            continue
        ident = canonical_identity(f)
        v25r_mult[ident] += 1

    # Find FN
    fn_facts = []
    for ident, g_count in gt_mult.items():
        c_count = v25r_mult.get(ident, 0)
        if g_count > c_count:
            doc_id, metric, value = ident
            matching_gt = [g for g in gt_facts
                           if g.get("document_id") == doc_id
                           and canonical_metric(g.get("metric", "")) == metric
                           and canonical_value(g.get("value", "")) == value]
            fn_facts.extend([(g, c_count) for g in matching_gt[:g_count - c_count]])

    print(f"  Total FN: {len(fn_facts)}")

    # Classify
    gap_type_counter = Counter()
    category_by_gap = defaultdict(Counter)
    subcategory_counter = Counter()

    for fn, core_count in fn_facts:
        doc_id = fn.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        gap_type, category, subcategory = classify_fn(fn, doc_text, core_count, set())
        gap_type_counter[gap_type] += 1
        category_by_gap[gap_type][category] += 1
        subcategory_counter[subcategory] += 1

    print(f"\n  Gap Type Split:")
    for gap, count in gap_type_counter.most_common():
        print(f"    {gap:<25} {count:>6} ({count/len(fn_facts)*100:.1f}%)")

    print(f"\n  TRUE_EXTRACTION_GAP categories:")
    for cat, count in category_by_gap["TRUE_EXTRACTION_GAP"].most_common():
        print(f"    {cat:<30} {count:>6}")

    print(f"\n  Top subcategories:")
    for sub, count in subcategory_counter.most_common(10):
        print(f"    {sub:<35} {count:>6}")

    # ─── V26R Extraction ───
    print(f"\n--- V26R Extraction (Family 2: action_type always) ---")
    t0 = time.perf_counter()
    v26r_facts, v26r_events, _ = run_v26r_extraction()
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s")
    print(f"  V26R raw facts: {len(v26r_facts)}")
    print(f"  V26R raw events: {len(v26r_events)}")

    # Save raw
    with open(CORE_REPO / "intelligence_core/tests/reliability/v26r_raw_facts.json", "w") as f:
        json.dump(v26r_facts, f, indent=2, default=str)
    with open(CORE_REPO / "intelligence_core/tests/reliability/v26r_raw_events.json", "w") as f:
        json.dump(v26r_events, f, indent=2, default=str)

    # Match
    v26r_fm = match_bipartite(v26r_facts, gt_facts, benchmark_doc_ids)
    v26r_em = match_events_bipartite(v26r_events, gt_events, benchmark_doc_ids)

    v26r_fact_tp = v26r_fm["tp"]
    v26r_fact_fp = v26r_fm["fp"]
    v26r_fact_fn = v26r_fm["fn"]
    v26r_fact_inv = v26r_fm["invariant_holds"]
    v26r_fact_prec = (v26r_fact_tp / (v26r_fact_tp + v26r_fact_fp) * 100) if (v26r_fact_tp + v26r_fact_fp) else 0
    v26r_fact_rec = (v26r_fact_tp / (v26r_fact_tp + v26r_fact_fn) * 100) if (v26r_fact_tp + v26r_fact_fn) else 0

    v26r_ev_tp = v26r_em["tp"]
    v26r_ev_fp = v26r_em["fp"]
    v26r_ev_fn = v26r_em["fn"]
    v26r_ev_inv = v26r_em["invariant_holds"]
    v26r_ev_prec = (v26r_ev_tp / (v26r_ev_tp + v26r_ev_fp) * 100) if (v26r_ev_tp + v26r_ev_fp) else 0
    v26r_ev_rec = (v26r_ev_tp / (v26r_ev_tp + v26r_ev_fn) * 100) if (v26r_ev_tp + v26r_ev_fn) else 0

    print(f"\n--- V26R Matching ---")
    print(f"  Fact: TP={v26r_fact_tp}  FP={v26r_fact_fp}  FN={v26r_fact_fn}  Inv={'✓' if v26r_fact_inv else '✗'}")
    print(f"  Fact Precision: {v26r_fact_prec:.2f}%")
    print(f"  Fact Recall:    {v26r_fact_rec:.2f}%")
    print(f"  Event: TP={v26r_ev_tp}  FP={v26r_ev_fp}  FN={v26r_ev_fn}  Inv={'✓' if v26r_ev_inv else '✗'}")
    print(f"  Event Precision: {v26r_ev_prec:.2f}%")
    print(f"  Event Recall:    {v26r_ev_rec:.2f}%")

    # V25R vs V26R
    print(f"\n--- V25R vs V26R Comparison ---")
    print(f"\n  {'Metric':<22} {'V25R':>10} {'V26R':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Fact TP':<22} {v25r_m['fact_tp']:>10} {v26r_fact_tp:>10} {v26r_fact_tp - v25r_m['fact_tp']:>+10}")
    print(f"  {'Fact FP':<22} {v25r_m['fact_fp']:>10} {v26r_fact_fp:>10} {v26r_fact_fp - v25r_m['fact_fp']:>+10}")
    print(f"  {'Fact FN':<22} {v25r_m['fact_fn']:>10} {v26r_fact_fn:>10} {v26r_fact_fn - v25r_m['fact_fn']:>+10}")
    print(f"  {'Fact Precision':<22} {v25r_m['fact_precision']:>9.2f}% {v26r_fact_prec:>9.2f}% {v26r_fact_prec - v25r_m['fact_precision']:>+8.2f}pp")
    print(f"  {'Fact Recall':<22} {v25r_m['fact_recall']:>9.2f}% {v26r_fact_rec:>9.2f}% {v26r_fact_rec - v25r_m['fact_recall']:>+8.2f}pp")
    print(f"  {'Event TP':<22} {v25r_m['event_tp']:>10} {v26r_ev_tp:>10} {v26r_ev_tp - v25r_m['event_tp']:>+10}")
    print(f"  {'Event FP':<22} {v25r_m['event_fp']:>10} {v26r_ev_fp:>10} {v26r_ev_fp - v25r_m['event_fp']:>+10}")
    print(f"  {'Event FN':<22} {v25r_m['event_fn']:>10} {v26r_ev_fn:>10} {v26r_ev_fn - v25r_m['event_fn']:>+10}")
    print(f"  {'Event Precision':<22} {v25r_m['event_precision']:>9.2f}% {v26r_ev_prec:>9.2f}% {v26r_ev_prec - v25r_m['event_precision']:>+8.2f}pp")
    print(f"  {'Event Recall':<22} {v25r_m['event_recall']:>9.2f}% {v26r_ev_rec:>9.2f}% {v26r_ev_rec - v25r_m['event_recall']:>+8.2f}pp")

    # Acceptance gate
    new_tps = v26r_fact_tp - v25r_m['fact_tp']
    recall_ok = v26r_fact_rec > v25r_m['fact_recall']
    precision_ok = v26r_fact_prec >= v25r_m['fact_precision'] - 1
    print(f"\n--- Acceptance Gate ---")
    print(f"  New TPs: {new_tps}")
    print(f"  Recall improved: {'✓' if recall_ok else '✗'} ({v25r_m['fact_recall']:.2f}% → {v26r_fact_rec:.2f}%)")
    print(f"  Precision maintained: {'✓' if precision_ok else '✗'} ({v25r_m['fact_precision']:.2f}% → {v26r_fact_prec:.2f}%)")
    print(f"  Verdict: {'ACCEPTED' if (recall_ok and precision_ok) else 'REJECTED'}")

    # Save
    results = {
        "v26r_measurement": {
            "fact_tp": v26r_fact_tp, "fact_fp": v26r_fact_fp, "fact_fn": v26r_fact_fn,
            "fact_precision": round(v26r_fact_prec, 2),
            "fact_recall": round(v26r_fact_rec, 2),
            "fact_invariant_holds": v26r_fact_inv,
            "event_tp": v26r_ev_tp, "event_fp": v26r_ev_fp, "event_fn": v26r_ev_fn,
            "event_precision": round(v26r_ev_prec, 2),
            "event_recall": round(v26r_ev_rec, 2),
            "event_invariant_holds": v26r_ev_inv,
        },
        "fn_taxonomy": {
            "total_fn": len(fn_facts),
            "gap_type_split": dict(gap_type_counter),
            "true_extraction_gap_categories": dict(category_by_gap["TRUE_EXTRACTION_GAP"]),
            "cardinality_gap_categories": dict(category_by_gap["CARDINALITY_GAP"]),
            "top_subcategories": dict(subcategory_counter.most_common(15)),
        },
        "deltas_vs_v25r": {
            "fact_recall_delta_pp": round(v26r_fact_rec - v25r_m['fact_recall'], 2),
            "new_tps": new_tps,
            "accepted": recall_ok and precision_ok,
        },
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v26r_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
