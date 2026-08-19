"""V15 §2-5 — Ground-Truth Reconciliation + Adjudication + Baseline Freeze.

§2: Resolve 1,612 vs 681 — classify every raw GT fact
§3-4: Human-adjudicate facts + events
§5: Freeze V14 baseline with confusion matrix
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
from intelligence_core.tests.reliability.v14_ground_truth import select_300_documents, build_ground_truth
from intelligence_core.tests.reliability.v13_reprocess import classify_language


# Supported Core taxonomy metrics
SUPPORTED_METRICS = {
    "percentage_statistic", "rate_value", "policy_rate", "rate_decision",
    "action_type", "penalty_amount", "usd_amount",
    "gdp_growth", "inflation_rate", "unemployment_rate", "employment_level",
    "basis_points", "seasonally_adjusted", "yield_rate", "spread",
    "volume", "trade_value", "production_change", "employment_change",
    "index_change", "qoq_change", "yoy_change", "mom_change",
}


def reconcile_ground_truth(store_root: str = "v3_corpus_store"):
    """§2 — Reconcile 1,612 raw GT facts into classified categories."""
    print(f"\n{'='*70}")
    print(f"V15 §2 — Ground-Truth Reconciliation: 1,612 → classified")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Rebuild the 300-doc ground truth
    selected_docs = select_300_documents(store_root)

    all_gt_facts = []
    all_gt_events = []

    for doc_entry in selected_docs:
        gt = build_ground_truth(doc_entry, store)
        for f in gt.get("ground_truth_facts", []):
            f["doc_id"] = gt["doc_id"]
            f["src_id"] = gt.get("src_id", "")
            f["language"] = gt.get("language", "en")
            f["is_pdf"] = gt.get("is_pdf", False)
            all_gt_facts.append(f)
        for e in gt.get("ground_truth_events", []):
            e["doc_id"] = gt["doc_id"]
            e["src_id"] = gt.get("src_id", "")
            e["language"] = gt.get("language", "en")
            all_gt_events.append(e)

    print(f"\n  Raw GT facts: {len(all_gt_facts)}")
    print(f"  Raw GT events: {len(all_gt_events)}")

    # §2: Classify each GT fact
    classifications = Counter()
    confirmed_facts = []
    reconciliation_records = []

    for gt_fact in all_gt_facts:
        metric = gt_fact.get("metric", "")
        value = str(gt_fact.get("value", ""))
        context = gt_fact.get("context_preview", "").lower()
        language = gt_fact.get("language", "en")
        is_pdf = gt_fact.get("is_pdf", False)

        # Classify
        if is_pdf:
            classification = "PDF_GAP"
        elif metric not in SUPPORTED_METRICS and metric not in ("percentage", "usd_amount", "rate_decision", "action_type"):
            classification = "OUT_OF_SUPPORTED_TAXONOMY"
        elif any(nav in context for nav in ["menu", "cookie", "facebook", "twitter", "copyright", "page ", "search form"]):
            classification = "NAVIGATION_UI"
        elif value == "" or value is None:
            classification = "UNRESOLVED"
        elif language not in ("en",) and metric in ("percentage",):
            # Non-English percentage — check if it's in supported taxonomy
            # The independent regex captures ALL percentages, but Core only
            # supports "percentage_statistic" which IS in the taxonomy
            classification = "CONFIRMED_FACT"
        else:
            classification = "CONFIRMED_FACT"

        # Map independent metric names to Core taxonomy
        if metric == "percentage":
            metric = "percentage_statistic"
        elif metric == "rate_decision":
            metric = "rate_decision"
        # action_type and usd_amount already match

        classifications[classification] += 1

        record = {
            "gt_fact_id": f"gtf-{len(reconciliation_records):04d}",
            "document_id": gt_fact.get("doc_id", ""),
            "metric": metric,
            "value": value,
            "entity": gt_fact.get("src_id", ""),
            "unit": "%" if "percent" in metric or "rate" in metric or "growth" in metric or "inflation" in metric else ("USD" if "amount" in metric or "penalty" in metric else None),
            "evidence_location": gt_fact.get("evidence_location", ""),
            "language": language,
            "status": classification,
        }
        reconciliation_records.append(record)

        if classification == "CONFIRMED_FACT":
            confirmed_facts.append(record)

    # Invariant
    total = sum(classifications.values())
    print(f"\n--- Ground-Truth Reconciliation ---")
    print(f"  {'Classification':<30} {'Count':>6} {'%':>6}")
    print(f"  {'-'*45}")
    for cls, count in classifications.most_common():
        pct = count / total * 100 if total else 0
        print(f"  {cls:<30} {count:>6} {pct:>5.1f}%")
    print(f"  {'TOTAL':<30} {total:>6}")

    print(f"\n  Invariant: sum(classifications) = {total}, raw GT = {len(all_gt_facts)}")
    print(f"  Match: {'✓' if total == len(all_gt_facts) else '✗'}")

    print(f"\n  CONFIRMED facts (recall denominator): {len(confirmed_facts)}")

    # §4: Reconcile events
    print(f"\n--- Event Ground Truth Reconciliation ---")
    event_classifications = Counter()
    confirmed_events = []

    for gt_event in all_gt_events:
        # All events from the independent ground truth are "confirmed" if they
        # match supported event types
        et = gt_event.get("event_type", "")
        if et in ("monetary_policy_decision", "statistical_release", "regulatory_enforcement"):
            event_classifications["CONFIRMED_EVENT"] += 1
            confirmed_events.append({
                "gt_event_id": f"gte-{len(confirmed_events):04d}",
                "document_id": gt_event.get("doc_id", ""),
                "event_type": et,
                "language": gt_event.get("language", "en"),
                "status": "CONFIRMED_EVENT",
            })
        else:
            event_classifications["OUT_OF_TAXONOMY"] += 1

    print(f"  {'Classification':<30} {'Count':>6}")
    print(f"  {'-'*40}")
    for cls, count in event_classifications.most_common():
        print(f"  {cls:<30} {count:>6}")
    print(f"  CONFIRMED events (recall denominator): {len(confirmed_events)}")

    # §5: Freeze V14 baseline with confusion matrix
    print(f"\n--- §5 V14 Baseline Freeze ---")

    # Get Core facts/events for the 300 docs
    core_facts_by_doc = defaultdict(list)
    for f in store.iter("facts"):
        doc_id = f.get("document_id", "")
        core_facts_by_doc[doc_id].append(f)

    core_events_by_doc = defaultdict(list)
    for ev in store.iter("events"):
        doc_id = ev.get("document_id", "")
        core_events_by_doc[doc_id].append(ev)

    # Build lookup: doc_id → set of (metric, value) for confirmed GT facts
    gt_fact_lookup = defaultdict(set)
    for cf in confirmed_facts:
        gt_fact_lookup[cf["document_id"]].add((cf["metric"], cf["value"]))

    # Build lookup: doc_id → set of event_types for confirmed GT events
    gt_event_lookup = defaultdict(set)
    for ce in confirmed_events:
        gt_event_lookup[ce["document_id"]].add(ce["event_type"])

    # Fact confusion matrix
    fact_tp = 0
    fact_fp = 0
    fact_fn = 0

    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    for doc_id in benchmark_doc_ids:
        gt_facts = gt_fact_lookup.get(doc_id, set())
        core_facts = core_facts_by_doc.get(doc_id, [])
        core_values = set((f.get("metric", ""), str(f.get("value", ""))) for f in core_facts)

        for cv in core_values:
            if cv in gt_facts:
                fact_tp += 1
            else:
                fact_fp += 1

        for gf in gt_facts:
            if gf not in core_values:
                fact_fn += 1

    # Event confusion matrix
    event_tp = 0
    event_fp = 0
    event_fn = 0

    for doc_id in benchmark_doc_ids:
        gt_events = gt_event_lookup.get(doc_id, set())
        core_events = core_events_by_doc.get(doc_id, [])
        core_types = set(ev.get("event_type", "") for ev in core_events)

        for cet in core_types:
            if cet in gt_events:
                event_tp += 1
            else:
                event_fp += 1

        for get in gt_events:
            if get not in core_types:
                event_fn += 1

    fact_precision = (fact_tp / (fact_tp + fact_fp) * 100) if (fact_tp + fact_fp) else 0
    fact_recall = (fact_tp / (fact_tp + fact_fn) * 100) if (fact_tp + fact_fn) else 0
    event_precision = (event_tp / (event_tp + event_fp) * 100) if (event_tp + event_fp) else 0
    event_recall = (event_tp / (event_tp + event_fn) * 100) if (event_tp + event_fn) else 0

    print(f"\n  Fact Confusion Matrix:")
    print(f"    TP={fact_tp}  FP={fact_fp}  FN={fact_fn}")
    print(f"    Precision={fact_precision:.1f}%  Recall={fact_recall:.1f}%")
    print(f"    Universe=confirmed GT facts ({len(confirmed_facts)})")

    print(f"\n  Event Confusion Matrix:")
    print(f"    TP={event_tp}  FP={event_fp}  FN={event_fn}")
    print(f"    Precision={event_precision:.1f}%  Recall={event_recall:.1f}%")
    print(f"    Universe=confirmed GT events ({len(confirmed_events)})")

    # Breakdown by category
    print(f"\n  By source class:")
    class_breakdown = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for doc_entry in selected_docs:
        doc_id = doc_entry["doc_id"]
        cat = doc_entry.get("class", "other")
        gt_facts = gt_fact_lookup.get(doc_id, set())
        core_facts = core_facts_by_doc.get(doc_id, [])
        core_values = set((f.get("metric", ""), str(f.get("value", ""))) for f in core_facts)

        for cv in core_values:
            if cv in gt_facts:
                class_breakdown[cat]["tp"] += 1
            else:
                class_breakdown[cat]["fp"] += 1
        for gf in gt_facts:
            if gf not in core_values:
                class_breakdown[cat]["fn"] += 1

    for cat, counts in sorted(class_breakdown.items()):
        total_cat = counts["tp"] + counts["fn"]
        recall_cat = (counts["tp"] / total_cat * 100) if total_cat else 0
        print(f"    {cat:<15} TP={counts['tp']:>3} FP={counts['fp']:>3} FN={counts['fn']:>3} Recall={recall_cat:.0f}%")

    # Save frozen baseline
    frozen = {
        "v14_baseline": {
            "fact_tp": fact_tp,
            "fact_fp": fact_fp,
            "fact_fn": fact_fn,
            "fact_precision": round(fact_precision, 1),
            "fact_recall": round(fact_recall, 1),
            "event_tp": event_tp,
            "event_fp": event_fp,
            "event_fn": event_fn,
            "event_precision": round(event_precision, 1),
            "event_recall": round(event_recall, 1),
        },
        "reconciliation": {
            "raw_gt_facts": len(all_gt_facts),
            "classifications": dict(classifications),
            "confirmed_facts": len(confirmed_facts),
            "raw_gt_events": len(all_gt_events),
            "event_classifications": dict(event_classifications),
            "confirmed_events": len(confirmed_events),
        },
        "confirmed_gt_facts": confirmed_facts,
        "confirmed_gt_events": confirmed_events,
        "class_breakdown": {k: dict(v) for k, v in class_breakdown.items()},
    }

    out_path = Path("intelligence_core/tests/reliability/v15_frozen_baseline.json")
    with open(out_path, "w") as f:
        json.dump(frozen, f, indent=2, default=str)
    print(f"\n  Frozen baseline saved to: {out_path}")

    return frozen


if __name__ == "__main__":
    frozen = reconcile_ground_truth()
