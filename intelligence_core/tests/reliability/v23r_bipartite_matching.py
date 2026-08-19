"""V23R — Controlled Reconstruction of V23 (Bipartite Matching Closure).

Starts strictly from V22 verified checkpoint (71e7805).
Reconstructs bipartite matching with multiplicity guarantees.
Does NOT use previous V23 reported metrics as expected results.

Measures against:
  - V22 immutable GT (1,612 facts, 208 events)
  - V22 frozen 300-doc benchmark
  - V17 raw facts (from V22 store)
  - V20 raw facts (re-extracted using V21 pipeline from V22 source)

Outputs:
  - V23R matching results (TP/FP/FN for V17 and V20, facts and events)
  - Invariant verification (TP + FN = GT_TOTAL)
  - Governance artifact: docs/evidence/ROUAA_CORE_BASELINE_MATCHING_CLOSURE_V23R.md
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]  # rouaa-intelligence-core root
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html
from intelligence_core.detect import detect_event, EVENT_TYPE_RULES
from intelligence_core.tests.reliability.v19_forensic import normalize_metric_v19
from intelligence_core.tests.reliability.v14_ground_truth import select_300_documents, build_ground_truth
from intelligence_core.tests.reliability.v13_reprocess import classify_language
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v15_recall_recovery import extract_html_structure
from intelligence_core.tests.reliability.v13_recall_patterns import (
    is_navigation_content_v13, validate_event_context_v13,
    NEW_RECALL_PATTERNS, STRUCTURED_PATTERNS, MULTILINGUAL_PATTERNS,
)
from intelligence_core.tests.reliability.v10_evidence_closure import (
    classify_evidence_strict, expand_evidence_for_direct,
)
from intelligence_core.tests.reliability.v21_frozen_benchmark import (
    get_patterns, get_source_class, SRC_TO_EVENT_TYPES,
)


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL IDENTITY (V23R — bipartite matching with multiplicity)
# ─────────────────────────────────────────────────────────────────────────────

def canonical_value(raw) -> str:
    """Canonical numeric/string normalization for fact values."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = re.sub(r"^(?:USD|EUR|GBP|JPY|CAD|AUD|CHF|CNY|INR)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^[$£€¥₹]\s*", "", s)
    if s.endswith("%"):
        s = s[:-1].strip()
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    try:
        f = float(s)
        if f == int(f) and abs(f) < 1e15:
            return str(int(f))
        s2 = repr(f)
        if "e" not in s2 and "E" not in s2:
            return s2
        return s
    except ValueError:
        return s.lower().strip()


def canonical_metric(raw_metric: str, pattern_ref: str = "") -> str:
    """V19 metric equivalence only — no new equivalences."""
    src = pattern_ref if pattern_ref else raw_metric
    return normalize_metric_v19(src)


def canonical_identity(fact: dict) -> tuple:
    """Canonical identity = (document_id, canonical_metric, canonical_value)."""
    return (
        fact.get("document_id", ""),
        canonical_metric(fact.get("metric", ""), fact.get("pattern_ref", "")),
        canonical_value(fact.get("value", "")),
    )


# ─────────────────────────────────────────────────────────────────────────────
# BIPARTITE MATCHING WITH MULTIPLICITIES
# ─────────────────────────────────────────────────────────────────────────────

def match_bipartite(core_facts, gt_facts, benchmark_doc_ids):
    """Bipartite matching with multiplicities.

    For each identity I = (doc, canonical_metric, canonical_value):
        GT_count   = multiplicity in GT
        Core_count = multiplicity in Core
        TP       += min(GT_count, Core_count)
        FN       += max(0, GT_count - Core_count)
        FP       += max(0, Core_count - GT_count)

    GUARANTEES: TP + FN = GT_TOTAL (by construction).
    """
    gt_mult = Counter()
    for gt in gt_facts:
        if gt.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (
            gt.get("document_id", ""),
            canonical_metric(gt.get("metric", "")),
            canonical_value(gt.get("value", "")),
        )
        gt_mult[ident] += 1

    core_mult = Counter()
    for cf in core_facts:
        if cf.get("document_id") not in benchmark_doc_ids:
            continue
        ident = canonical_identity(cf)
        core_mult[ident] += 1

    tp = fn = fp = duplicate = 0
    for ident in set(gt_mult.keys()) | set(core_mult.keys()):
        g = gt_mult.get(ident, 0)
        c = core_mult.get(ident, 0)
        tp += min(g, c)
        fn += max(0, g - c)
        fp += max(0, c - g)
        if c > g and g > 0:
            duplicate += (c - g)

    gt_total = sum(gt_mult.values())
    return {
        "tp": tp, "fn": fn, "fp": fp, "duplicate": duplicate,
        "gt_total": gt_total,
        "core_total": sum(core_mult.values()),
        "invariant_holds": (tp + fn == gt_total),
    }


def match_events_bipartite(core_events, gt_events, benchmark_doc_ids):
    """Bipartite event matching. Identity = (document_id, event_type)."""
    gt_mult = Counter()
    for ev in gt_events:
        if ev.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (ev.get("document_id", ""), ev.get("event_type", ""))
        gt_mult[ident] += 1

    core_mult = Counter()
    for ev in core_events:
        if ev.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (ev.get("document_id", ""), ev.get("event_type", ""))
        core_mult[ident] += 1

    tp = fn = fp = 0
    for ident in set(gt_mult.keys()) | set(core_mult.keys()):
        g = gt_mult.get(ident, 0)
        c = core_mult.get(ident, 0)
        tp += min(g, c)
        fn += max(0, g - c)
        fp += max(0, c - g)

    return {
        "tp": tp, "fn": fn, "fp": fp,
        "gt_total": sum(gt_mult.values()),
        "core_total": sum(core_mult.values()),
        "invariant_holds": (tp + fn == sum(gt_mult.values())),
    }


# ─────────────────────────────────────────────────────────────────────────────
# V20 EXTRACTION (re-extract using V21 pipeline from V22 source)
# ─────────────────────────────────────────────────────────────────────────────

def run_v20_extraction(store_root: str = "v3_corpus_store"):
    """Re-extract V20 facts using V21 pipeline (deterministic)."""
    selected_docs = select_300_documents(store_root)
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    v20_facts_by_doc = defaultdict(list)
    v20_events_by_doc = defaultdict(list)

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
                v20_facts_by_doc[doc_id].append(f.to_dict())
            ev = detect_event(direct, doc_id, event_type)
            if ev is not None:
                v20_events_by_doc[doc_id].append(ev.to_dict())

    v20_facts_flat = [f for facts in v20_facts_by_doc.values() for f in facts]
    v20_events_flat = [ev for evs in v20_events_by_doc.values() for ev in evs]
    return v20_facts_flat, v20_events_flat, benchmark_doc_ids


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("V23R — Bipartite Matching Closure (Controlled Reconstruction)")
    print("=" * 70)
    print(f"  Starting from V22 verified checkpoint: 71e7805")
    print(f"  V28R recovery report: 17eea7a")
    print()

    # Load immutable GT (V22 — frozen, never modified)
    gt_facts_path = CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"
    gt_events_path = CORE_REPO / "intelligence_core/tests/reliability/event_gt_v1.json"
    with open(gt_facts_path) as f:
        gt_facts = json.load(f)
    with open(gt_events_path) as f:
        gt_events = json.load(f)
    print(f"  Immutable GT facts: {len(gt_facts)}")
    print(f"  Immutable GT events: {len(gt_events)}")

    # GT multiplicity sanity check
    gt_keys = Counter((g["document_id"], g["value"]) for g in gt_facts)
    print(f"  GT unique (doc,value) keys: {len(gt_keys)}")
    print(f"  GT keys with mult > 1: {sum(1 for v in gt_keys.values() if v > 1)}")
    print(f"  GT extra duplicate facts: {sum(v - 1 for v in gt_keys.values() if v > 1)}")

    # Get benchmark docs
    selected_docs = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)
    print(f"  Benchmark docs: {len(selected_docs)}")

    # ─── V17 evaluation ───
    print(f"\n--- V17 Evaluation (bipartite matching) ---")
    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    v17_facts = [f for f in store.iter("facts") if f.get("document_id") in benchmark_doc_ids]
    v17_events = [ev for ev in store.iter("events") if ev.get("document_id") in benchmark_doc_ids]
    print(f"  V17 raw facts (in benchmark): {len(v17_facts)}")
    print(f"  V17 raw events (in benchmark): {len(v17_events)}")

    v17_fm = match_bipartite(v17_facts, gt_facts, benchmark_doc_ids)
    v17_em = match_events_bipartite(v17_events, gt_events, benchmark_doc_ids)

    v17_fact_tp = v17_fm["tp"]
    v17_fact_fp = v17_fm["fp"]
    v17_fact_fn = v17_fm["fn"]
    v17_fact_inv = v17_fm["invariant_holds"]
    v17_fact_prec = (v17_fact_tp / (v17_fact_tp + v17_fact_fp) * 100) if (v17_fact_tp + v17_fact_fp) else 0
    v17_fact_rec = (v17_fact_tp / (v17_fact_tp + v17_fact_fn) * 100) if (v17_fact_tp + v17_fact_fn) else 0

    v17_ev_tp = v17_em["tp"]
    v17_ev_fp = v17_em["fp"]
    v17_ev_fn = v17_em["fn"]
    v17_ev_inv = v17_em["invariant_holds"]
    v17_ev_prec = (v17_ev_tp / (v17_ev_tp + v17_ev_fp) * 100) if (v17_ev_tp + v17_ev_fp) else 0
    v17_ev_rec = (v17_ev_tp / (v17_ev_tp + v17_ev_fn) * 100) if (v17_ev_tp + v17_ev_fn) else 0

    print(f"\n  V17 Fact: TP={v17_fact_tp}  FP={v17_fact_fp}  FN={v17_fact_fn}  DUP={v17_fm['duplicate']}")
    print(f"  V17 Fact Invariant: TP({v17_fact_tp}) + FN({v17_fact_fn}) = {v17_fact_tp + v17_fact_fn} vs GT({v17_fm['gt_total']})  {'✓' if v17_fact_inv else '✗'}")
    print(f"  V17 Fact Precision: {v17_fact_prec:.2f}%")
    print(f"  V17 Fact Recall:    {v17_fact_rec:.2f}%")
    print(f"\n  V17 Event: TP={v17_ev_tp}  FP={v17_ev_fp}  FN={v17_ev_fn}")
    print(f"  V17 Event Invariant: TP({v17_ev_tp}) + FN({v17_ev_fn}) = {v17_ev_tp + v17_ev_fn} vs GT({v17_em['gt_total']})  {'✓' if v17_ev_inv else '✗'}")
    print(f"  V17 Event Precision: {v17_ev_prec:.2f}%")
    print(f"  V17 Event Recall:    {v17_ev_rec:.2f}%")

    # ─── V20 evaluation ───
    print(f"\n--- V20 Evaluation (bipartite matching) ---")
    print(f"  Re-extracting V20 using V21 pipeline (deterministic)...")
    t0 = time.perf_counter()
    v20_facts, v20_events, _ = run_v20_extraction()
    elapsed = time.perf_counter() - t0
    print(f"  Done in {elapsed:.1f}s")
    print(f"  V20 raw facts: {len(v20_facts)}")
    print(f"  V20 raw events: {len(v20_events)}")

    # Save V20 raw facts/events to disk for future audit
    with open(CORE_REPO / "intelligence_core/tests/reliability/v20_raw_facts.json", "w") as f:
        json.dump(v20_facts, f, indent=2, default=str)
    with open(CORE_REPO / "intelligence_core/tests/reliability/v20_raw_events.json", "w") as f:
        json.dump(v20_events, f, indent=2, default=str)

    v20_fm = match_bipartite(v20_facts, gt_facts, benchmark_doc_ids)
    v20_em = match_events_bipartite(v20_events, gt_events, benchmark_doc_ids)

    v20_fact_tp = v20_fm["tp"]
    v20_fact_fp = v20_fm["fp"]
    v20_fact_fn = v20_fm["fn"]
    v20_fact_inv = v20_fm["invariant_holds"]
    v20_fact_prec = (v20_fact_tp / (v20_fact_tp + v20_fact_fp) * 100) if (v20_fact_tp + v20_fact_fp) else 0
    v20_fact_rec = (v20_fact_tp / (v20_fact_tp + v20_fact_fn) * 100) if (v20_fact_tp + v20_fact_fn) else 0

    v20_ev_tp = v20_em["tp"]
    v20_ev_fp = v20_em["fp"]
    v20_ev_fn = v20_em["fn"]
    v20_ev_inv = v20_em["invariant_holds"]
    v20_ev_prec = (v20_ev_tp / (v20_ev_tp + v20_ev_fp) * 100) if (v20_ev_tp + v20_ev_fp) else 0
    v20_ev_rec = (v20_ev_tp / (v20_ev_tp + v20_ev_fn) * 100) if (v20_ev_tp + v20_ev_fn) else 0

    print(f"\n  V20 Fact: TP={v20_fact_tp}  FP={v20_fact_fp}  FN={v20_fact_fn}  DUP={v20_fm['duplicate']}")
    print(f"  V20 Fact Invariant: TP({v20_fact_tp}) + FN({v20_fact_fn}) = {v20_fact_tp + v20_fact_fn} vs GT({v20_fm['gt_total']})  {'✓' if v20_fact_inv else '✗'}")
    print(f"  V20 Fact Precision: {v20_fact_prec:.2f}%")
    print(f"  V20 Fact Recall:    {v20_fact_rec:.2f}%")
    print(f"\n  V20 Event: TP={v20_ev_tp}  FP={v20_ev_fp}  FN={v20_ev_fn}")
    print(f"  V20 Event Invariant: TP({v20_ev_tp}) + FN({v20_ev_fn}) = {v20_ev_tp + v20_ev_fn} vs GT({v20_em['gt_total']})  {'✓' if v20_ev_inv else '✗'}")
    print(f"  V20 Event Precision: {v20_ev_prec:.2f}%")
    print(f"  V20 Event Recall:    {v20_ev_rec:.2f}%")

    # ─── Comparison ───
    print(f"\n--- V17 vs V20 Comparison (V23R bipartite) ---")
    print(f"\n  {'Metric':<22} {'V17':>10} {'V20':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    print(f"  {'GT facts':<22} {v17_fm['gt_total']:>10} {v20_fm['gt_total']:>10} {'0':>10}")
    print(f"  {'Fact TP':<22} {v17_fact_tp:>10} {v20_fact_tp:>10} {v20_fact_tp - v17_fact_tp:>+10}")
    print(f"  {'Fact FP':<22} {v17_fact_fp:>10} {v20_fact_fp:>10} {v20_fact_fp - v17_fact_fp:>+10}")
    print(f"  {'Fact FN':<22} {v17_fact_fn:>10} {v20_fact_fn:>10} {v20_fact_fn - v17_fact_fn:>+10}")
    print(f"  {'Fact Precision':<22} {v17_fact_prec:>9.2f}% {v20_fact_prec:>9.2f}% {v20_fact_prec - v17_fact_prec:>+8.2f}pp")
    print(f"  {'Fact Recall':<22} {v17_fact_rec:>9.2f}% {v20_fact_rec:>9.2f}% {v20_fact_rec - v17_fact_rec:>+8.2f}pp")
    print(f"  {'GT events':<22} {v17_em['gt_total']:>10} {v20_em['gt_total']:>10} {'0':>10}")
    print(f"  {'Event TP':<22} {v17_ev_tp:>10} {v20_ev_tp:>10} {v20_ev_tp - v17_ev_tp:>+10}")
    print(f"  {'Event FP':<22} {v17_ev_fp:>10} {v20_ev_fp:>10} {v20_ev_fp - v17_ev_fp:>+10}")
    print(f"  {'Event FN':<22} {v17_ev_fn:>10} {v20_ev_fn:>10} {v20_ev_fn - v17_ev_fn:>+10}")
    print(f"  {'Event Precision':<22} {v17_ev_prec:>9.2f}% {v20_ev_prec:>9.2f}% {v20_ev_prec - v17_ev_prec:>+8.2f}pp")
    print(f"  {'Event Recall':<22} {v17_ev_rec:>9.2f}% {v20_ev_rec:>9.2f}% {v20_ev_rec - v17_ev_rec:>+8.2f}pp")

    # ─── Invariant verification ───
    print(f"\n--- Invariant Verification ---")
    all_inv = v17_fact_inv and v20_fact_inv and v17_ev_inv and v20_ev_inv
    print(f"  V17 Fact:  {'✓ PASS' if v17_fact_inv else '✗ FAIL'}  (TP+FN={v17_fact_tp + v17_fact_fn}, GT={v17_fm['gt_total']})")
    print(f"  V20 Fact:  {'✓ PASS' if v20_fact_inv else '✗ FAIL'}  (TP+FN={v20_fact_tp + v20_fact_fn}, GT={v20_fm['gt_total']})")
    print(f"  V17 Event: {'✓ PASS' if v17_ev_inv else '✗ FAIL'}  (TP+FN={v17_ev_tp + v17_ev_fn}, GT={v17_em['gt_total']})")
    print(f"  V20 Event: {'✓ PASS' if v20_ev_inv else '✗ FAIL'}  (TP+FN={v20_ev_tp + v20_ev_fn}, GT={v20_em['gt_total']})")
    print(f"\n  All invariants: {'✓ PASS' if all_inv else '✗ FAIL'}")

    # ─── Save results ───
    results = {
        "v23r_reconstruction": {
            "start_commit": "71e7805 (V22 verified)",
            "parent_commit": "17eea7a (V28R recovery report)",
            "gt_total_facts": len(gt_facts),
            "gt_total_events": len(gt_events),
            "v17": {
                "fact_tp": v17_fact_tp, "fact_fp": v17_fact_fp, "fact_fn": v17_fact_fn,
                "fact_duplicate": v17_fm["duplicate"],
                "fact_precision": round(v17_fact_prec, 2),
                "fact_recall": round(v17_fact_rec, 2),
                "fact_invariant_holds": v17_fact_inv,
                "fact_gt_total": v17_fm["gt_total"],
                "fact_core_total": v17_fm["core_total"],
                "event_tp": v17_ev_tp, "event_fp": v17_ev_fp, "event_fn": v17_ev_fn,
                "event_precision": round(v17_ev_prec, 2),
                "event_recall": round(v17_ev_rec, 2),
                "event_invariant_holds": v17_ev_inv,
                "event_gt_total": v17_em["gt_total"],
                "event_core_total": v17_em["core_total"],
            },
            "v20": {
                "fact_tp": v20_fact_tp, "fact_fp": v20_fact_fp, "fact_fn": v20_fact_fn,
                "fact_duplicate": v20_fm["duplicate"],
                "fact_precision": round(v20_fact_prec, 2),
                "fact_recall": round(v20_fact_rec, 2),
                "fact_invariant_holds": v20_fact_inv,
                "fact_gt_total": v20_fm["gt_total"],
                "fact_core_total": v20_fm["core_total"],
                "event_tp": v20_ev_tp, "event_fp": v20_ev_fp, "event_fn": v20_ev_fn,
                "event_precision": round(v20_ev_prec, 2),
                "event_recall": round(v20_ev_rec, 2),
                "event_invariant_holds": v20_ev_inv,
                "event_gt_total": v20_em["gt_total"],
                "event_core_total": v20_em["core_total"],
            },
            "deltas": {
                "fact_recall_delta_pp": round(v20_fact_rec - v17_fact_rec, 2),
                "event_recall_delta_pp": round(v20_ev_rec - v17_ev_rec, 2),
                "fact_precision_delta_pp": round(v20_fact_prec - v17_fact_prec, 2),
                "event_precision_delta_pp": round(v20_ev_prec - v17_ev_prec, 2),
            },
            "all_invariants_hold": all_inv,
        },
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v23r_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {out_path}")

    # Print final V23R summary
    print(f"\n{'='*70}")
    print(f"V23R Summary")
    print(f"{'='*70}")
    print(f"  V17 Fact Recall:  {v17_fact_rec:.2f}%  (TP={v17_fact_tp}, FN={v17_fact_fn})")
    print(f"  V20 Fact Recall:  {v20_fact_rec:.2f}%  (TP={v20_fact_tp}, FN={v20_fact_fn})")
    print(f"  Fact Recall Delta: {v20_fact_rec - v17_fact_rec:+.2f}pp")
    print(f"  V17 Event Recall: {v17_ev_rec:.2f}%  (TP={v17_ev_tp}, FN={v17_ev_fn})")
    print(f"  V20 Event Recall: {v20_ev_rec:.2f}%  (TP={v20_ev_tp}, FN={v20_ev_fn})")
    print(f"  Event Recall Delta: {v20_ev_rec - v17_ev_rec:+.2f}pp")
    print(f"  All invariants: {'✓ PASS' if all_inv else '✗ FAIL'}")

    return results


if __name__ == "__main__":
    main()
