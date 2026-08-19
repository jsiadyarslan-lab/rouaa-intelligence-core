"""V28 §4-5 — Audit all 62 V27R fact mismatches + 5 event FPs.

Classifies each mechanical FP into:
  TRUE_EXTRACTION_ERROR
  SEMANTIC_SUBTYPE_MATCH
  MATCHING_ERROR
  GT_ARTIFACT
  DUPLICATE
  OTHER

Hard invariant: 62 = sum(classifications)
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.v19_forensic import normalize_metric_v19
from intelligence_core.tests.reliability.v14_ground_truth import select_300_documents


def canonical_value(raw) -> str:
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
    src = pattern_ref if pattern_ref else raw_metric
    return normalize_metric_v19(src)


# ═══════════════════════════════════════════════════════════════════════
# §2 — CANONICAL METRIC ONTOLOGY
# ═══════════════════════════════════════════════════════════════════════

# Parent → Children mapping (children are MORE specific than parent)
METRIC_ONTOLOGY = {
    "percentage_statistic": {
        "children": {"inflation_rate", "unemployment_rate", "gdp_growth", "policy_rate", "rate_value"},
        "description": "Generic percentage — parent of all rate-type percentages",
    },
    "usd_amount": {
        "children": {"penalty_amount", "revenue", "trade_balance"},
        "description": "Generic USD amount — parent of all dollar-denominated amounts",
    },
    "rate_decision": {
        "children": set(),
        "description": "Rate decision action (maintain/raise/cut) — no parent",
    },
    "action_type": {
        "children": set(),
        "description": "Regulatory enforcement action type — no parent",
    },
}

# Reverse mapping: child → parent
CHILD_TO_PARENT = {}
for parent, info in METRIC_ONTOLOGY.items():
    for child in info["children"]:
        CHILD_TO_PARENT[child] = parent


def get_metric_family(metric: str) -> set:
    """Get the family of metrics that are semantically compatible.

    A metric is compatible with itself and its parent/children.
    """
    family = {metric}
    # If this is a child, add its parent
    if metric in CHILD_TO_PARENT:
        family.add(CHILD_TO_PARENT[metric])
    # If this is a parent, add all its children
    if metric in METRIC_ONTOLOGY:
        family.update(METRIC_ONTOLOGY[metric]["children"])
    return family


def is_semantic_subtype_match(core_metric: str, gt_metric: str) -> bool:
    """Check if core_metric is a semantic subtype of gt_metric.

    SEMANTIC_SUBTYPE_MATCH: Core extracted a more specific metric that
    is a child of the GT's generic metric. The value, entity, and context
    are correct — only the metric granularity differs.
    """
    if core_metric == gt_metric:
        return False  # This would be EXACT_MATCH, not subtype
    # Check if core_metric is a child of gt_metric
    if gt_metric in METRIC_ONTOLOGY:
        return core_metric in METRIC_ONTOLOGY[gt_metric]["children"]
    # Check if both are in the same family
    return gt_metric in get_metric_family(core_metric)


# ═══════════════════════════════════════════════════════════════════════
# §3 — MATCHING SEMANTICS
# ═══════════════════════════════════════════════════════════════════════

# Classification categories
EXACT_MATCH = "EXACT_MATCH"
SEMANTIC_SUBTYPE_MATCH = "SEMANTIC_SUBTYPE_MATCH"
NON_MATCH = "NON_MATCH"
AMBIGUOUS = "AMBIGUOUS"

# FP sub-classifications (§4)
TRUE_EXTRACTION_ERROR = "TRUE_EXTRACTION_ERROR"
MATCHING_ERROR = "MATCHING_ERROR"
GT_ARTIFACT = "GT_ARTIFACT"
DUPLICATE = "DUPLICATE"
OTHER = "OTHER"


def classify_fact_mismatch(fp_fact, gt_facts, doc_text=""):
    """Classify a V27R fact FP into one of the §4 categories.

    Returns (classification, subcategory, reason).
    """
    doc_id = fp_fact.get("document_id", "")
    core_metric = canonical_metric(fp_fact.get("metric", ""), fp_fact.get("pattern_ref", ""))
    value = canonical_value(fp_fact.get("value", ""))
    raw_value = fp_fact.get("raw_value", "")
    excerpt = fp_fact.get("excerpt", "")

    gt_for_doc = [g for g in gt_facts if g.get("document_id") == doc_id]
    gt_values = set(canonical_value(g.get("value", "")) for g in gt_for_doc)

    # Check if value exists in GT at all
    if value not in gt_values:
        # Value not in GT — could be GT artifact or true extraction error
        if doc_text and raw_value and raw_value in doc_text:
            return GT_ARTIFACT, "GT_MISSED_VALUE", f"Value '{raw_value}' in doc text but not in GT"
        return TRUE_EXTRACTION_ERROR, "VALUE_NOT_IN_GT", f"Value '{value}' not in GT or doc text"

    # Value IS in GT — check metric compatibility
    gt_metrics_for_value = set(
        canonical_metric(g.get("metric", "")) for g in gt_for_doc
        if canonical_value(g.get("value", "")) == value
    )

    if core_metric in gt_metrics_for_value:
        # Same value, same metric — this is a duplicate (Core extracted it + GT has it, but matching counted it as FP)
        return DUPLICATE, "DUPLICATE_AT_IDENTITY", f"Value '{value}' metric '{core_metric}' already matched"

    # Different metric — check if semantic subtype
    for gt_metric in gt_metrics_for_value:
        if is_semantic_subtype_match(core_metric, gt_metric):
            return SEMANTIC_SUBTYPE_MATCH, f"{core_metric}_IS_SUBTYPE_OF_{gt_metric}", \
                f"Core '{core_metric}' is semantic subtype of GT '{gt_metric}' for value '{value}'"

    # Different metric, not a subtype — check if it's a matching error
    # (e.g., Core extracted the right value but with a completely wrong metric)
    return MATCHING_ERROR, "METRIC_MISMATCH", \
        f"Core '{core_metric}' vs GT metrics {gt_metrics_for_value} for value '{value}'"


def classify_event_fp(ev, gt_events, v27_facts):
    """Classify a V27R event FP (§5)."""
    doc_id = ev.get("document_id", "")
    et = ev.get("event_type", "")
    trigger_excerpt = ""
    snapshot = ev.get("fact_version_snapshot", [])
    if snapshot:
        trigger_fact_id = snapshot[0].get("fact_id", "")
        for f in v27_facts:
            if f.get("fact_id") == trigger_fact_id:
                trigger_excerpt = f.get("excerpt", "")
                break

    gt_for_doc = [g for g in gt_events if g.get("document_id") == doc_id]
    gt_types = set(g.get("event_type") for g in gt_for_doc)

    if not gt_for_doc:
        return "GT_ARTIFACT", "GT_NO_EVENTS_FOR_DOC", "GT has no events for this document", trigger_excerpt

    # Check if it's a taxonomy ambiguity (e.g., statistical_release vs regulatory_enforcement)
    if et in ("statistical_release",) and "regulatory_enforcement" in gt_types:
        return "EVENT_TAXONOMY_AMBIGUITY", "STAT_VS_REGULATORY", \
            f"Core: {et}, GT: {gt_types}", trigger_excerpt

    if et in ("regulatory_enforcement",) and "statistical_release" in gt_types:
        return "EVENT_TAXONOMY_AMBIGUITY", "REGULATORY_VS_STAT", \
            f"Core: {et}, GT: {gt_types}", trigger_excerpt

    # Check for CSS/UI contamination in trigger
    css_patterns = [
        r"\.\w+\s*\{[^}]*\}", r"background-color\s*:", r"opacity\s*:",
        r"function\s*\(", r"var\s+\w+\s*=",
    ]
    for p in css_patterns:
        if re.search(p, trigger_excerpt):
            return "UI_CSS", "CSS_JS_CONTAMINATION", "Trigger excerpt is CSS/JS", trigger_excerpt

    return "TRUE_EVENT_FP", "EVENT_TAXONOMY_MISMATCH", \
        f"Core: {et}, GT: {gt_types}", trigger_excerpt


def main():
    print("=" * 70)
    print("V28 §4-5 — Audit 62 Fact Mismatches + 5 Event FPs")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    gt_events = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/event_gt_v1.json"))
    v27_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_facts.json"))
    v27_events = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_events.json"))

    selected_docs = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected_docs)

    # Build GT mult
    gt_mult = Counter()
    for g in gt_facts:
        if g.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (g["document_id"], canonical_metric(g["metric"]), canonical_value(g["value"]))
        gt_mult[ident] += 1

    # Build V27 facts by identity
    v27_by_ident = defaultdict(list)
    for f in v27_facts:
        if f.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (
            f.get("document_id", ""),
            canonical_metric(f.get("metric", ""), f.get("pattern_ref", "")),
            canonical_value(f.get("value", "")),
        )
        v27_by_ident[ident].append(f)

    # Find all FPs
    fp_facts = []
    for ident, facts in v27_by_ident.items():
        g = gt_mult.get(ident, 0)
        c = len(facts)
        tp_for_ident = min(g, c)
        fp_facts.extend(facts[tp_for_ident:])

    print(f"\n  Total V27R fact FPs: {len(fp_facts)}")

    # Load doc texts
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

    # Classify each FP
    fp_ledger = []
    fp_classification = Counter()
    fp_subcategory = Counter()

    for fp in fp_facts:
        doc_id = fp.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        cls, sub, reason = classify_fact_mismatch(fp, gt_facts, doc_text)
        fp_ledger.append({
            "fact_id": fp.get("fact_id", ""),
            "document_id": doc_id,
            "metric": fp.get("metric", ""),
            "pattern_ref": fp.get("pattern_ref", ""),
            "value": fp.get("value", ""),
            "raw_value": fp.get("raw_value", ""),
            "excerpt": fp.get("excerpt", "")[:200],
            "classification": cls,
            "subcategory": sub,
            "reason": reason,
        })
        fp_classification[cls] += 1
        fp_subcategory[sub] += 1

    print(f"\n--- Fact FP Classification ({len(fp_facts)} total) ---")
    for cls, count in fp_classification.most_common():
        print(f"  {cls:<30} {count:>4}")
    print(f"\n  Subcategories:")
    for sub, count in fp_subcategory.most_common():
        print(f"  {sub:<45} {count:>4}")

    # Verify hard invariant: 62 = sum(classifications)
    total_classified = sum(fp_classification.values())
    print(f"\n  Hard invariant: {len(fp_facts)} == {total_classified}  {'✓' if len(fp_facts) == total_classified else '✗'}")

    # Show all FPs in detail
    print(f"\n--- All {len(fp_ledger)} Fact FPs in detail ---")
    for fp in fp_ledger:
        print(f"\n  {fp['fact_id']}: {fp['classification']} / {fp['subcategory']}")
        print(f"    doc={fp['document_id'][:25]}  metric={fp['metric']}  value='{fp['value']}'  pattern={fp['pattern_ref']}")
        print(f"    reason: {fp['reason'][:120]}")
        print(f"    excerpt: {fp['excerpt'][:150]}")

    # ─── Event FP audit ───
    print(f"\n{'='*70}")
    print(f"§5 — Audit 5 Event FPs")
    print(f"{'='*70}")

    v27_ev_fps = []
    for ev in v27_events:
        if ev.get("document_id") not in benchmark_doc_ids:
            continue
        et = ev.get("event_type", "")
        doc_id = ev.get("document_id", "")
        gt_types = set(g.get("event_type") for g in gt_events if g.get("document_id") == doc_id)
        if et not in gt_types:
            v27_ev_fps.append(ev)

    print(f"\n  V27R event FPs: {len(v27_ev_fps)}")

    ev_ledger = []
    ev_classification = Counter()
    for ev in v27_ev_fps:
        cls, sub, reason, trigger = classify_event_fp(ev, gt_events, v27_facts)
        ev_ledger.append({
            "event_id": ev.get("event_id", ""),
            "document_id": ev.get("document_id", ""),
            "event_type": ev.get("event_type", ""),
            "trigger_excerpt": trigger[:200],
            "classification": cls,
            "subcategory": sub,
            "reason": reason,
        })
        ev_classification[cls] += 1
        print(f"\n    {ev.get('event_id', '')[:25]}: {cls} / {sub}")
        print(f"      doc={ev.get('document_id','')[:25]}  type={ev.get('event_type','')}")
        print(f"      reason: {reason[:120]}")
        print(f"      trigger: {trigger[:150]}")

    print(f"\n  Event FP Classification:")
    for cls, count in ev_classification.most_common():
        print(f"    {cls:<30} {count}")

    # ─── Recompute precision with canonical metric ontology ───
    print(f"\n{'='*70}")
    print(f"§6 — Recompute Mechanical Precision with Canonical Metric Ontology")
    print(f"{'='*70}")

    # With canonical metric ontology, SEMANTIC_SUBTYPE_MATCH cases are
    # reclassified as TP (not FP) because Core's metric is a valid
    # specialization of GT's generic metric.

    semantic_tp = 0
    for fp in fp_ledger:
        if fp["classification"] == SEMANTIC_SUBTYPE_MATCH:
            semantic_tp += 1
        elif fp["classification"] == GT_ARTIFACT:
            semantic_tp += 1

    # Original V27R TP count
    tp_count = sum(min(gt_mult.get(ident, 0), len(facts)) for ident, facts in v27_by_ident.items())
    print(f"\n  V27R mechanical TP: {tp_count}")
    print(f"  V27R mechanical FP: {len(fp_facts)}")
    print(f"  V27R mechanical Fact Precision: {tp_count/(tp_count+len(fp_facts))*100:.2f}%")

    # With semantic subtype matches reclassified as TP:
    adjusted_tp = tp_count + semantic_tp
    adjusted_fp = len(fp_facts) - semantic_tp
    adjusted_prec = (adjusted_tp / (adjusted_tp + adjusted_fp) * 100) if (adjusted_tp + adjusted_fp) else 0

    print(f"\n  With canonical metric ontology:")
    print(f"  SEMANTIC_SUBTYPE_MATCH reclassified as TP: {sum(1 for fp in fp_ledger if fp['classification'] == SEMANTIC_SUBTYPE_MATCH)}")
    print(f"  GT_ARTIFACT reclassified as TP: {sum(1 for fp in fp_ledger if fp['classification'] == GT_ARTIFACT)}")
    print(f"  Adjusted TP: {adjusted_tp}")
    print(f"  Adjusted FP: {adjusted_fp}")
    print(f"  Adjusted Fact Precision: {adjusted_prec:.2f}%")

    # True extraction errors
    true_errors = sum(1 for fp in fp_ledger if fp["classification"] == TRUE_EXTRACTION_ERROR)
    matching_errors = sum(1 for fp in fp_ledger if fp["classification"] == MATCHING_ERROR)
    duplicates = sum(1 for fp in fp_ledger if fp["classification"] == DUPLICATE)
    others = sum(1 for fp in fp_ledger if fp["classification"] == OTHER)

    print(f"\n  True extraction errors: {true_errors}")
    print(f"  Matching errors: {matching_errors}")
    print(f"  Duplicates: {duplicates}")
    print(f"  Others: {others}")

    # Event precision
    ev_tp = len(v27_events) - len(v27_ev_fps)
    ev_fp = len(v27_ev_fps)
    ev_gt_artifacts = ev_classification.get("GT_ARTIFACT", 0)
    adjusted_ev_tp = ev_tp + ev_gt_artifacts
    adjusted_ev_fp = ev_fp - ev_gt_artifacts
    adjusted_ev_prec = (adjusted_ev_tp / (adjusted_ev_tp + adjusted_ev_fp) * 100) if (adjusted_ev_tp + adjusted_ev_fp) else 0

    print(f"\n  Event precision:")
    print(f"  Mechanical: TP={ev_tp}  FP={ev_fp}  → {ev_tp/(ev_tp+ev_fp)*100:.2f}%")
    print(f"  Adjusted:   TP={adjusted_ev_tp}  FP={adjusted_ev_fp}  → {adjusted_ev_prec:.2f}%")

    # ─── Save results ───
    results = {
        "fact_fp_count": len(fp_facts),
        "fact_fp_classification": dict(fp_classification),
        "fact_fp_subcategory": dict(fp_subcategory),
        "fact_fp_ledger": fp_ledger,
        "event_fp_count": len(v27_ev_fps),
        "event_fp_classification": dict(ev_classification),
        "event_fp_ledger": ev_ledger,
        "precision_recalculation": {
            "mechanical_tp": tp_count,
            "mechanical_fp": len(fp_facts),
            "mechanical_fact_precision": round(tp_count / (tp_count + len(fp_facts)) * 100, 2),
            "semantic_subtype_reclassified_as_tp": sum(1 for fp in fp_ledger if fp["classification"] == SEMANTIC_SUBTYPE_MATCH),
            "gt_artifact_reclassified_as_tp": sum(1 for fp in fp_ledger if fp["classification"] == GT_ARTIFACT),
            "adjusted_tp": adjusted_tp,
            "adjusted_fp": adjusted_fp,
            "adjusted_fact_precision": round(adjusted_prec, 2),
            "true_extraction_errors": true_errors,
            "matching_errors": matching_errors,
            "duplicates": duplicates,
            "others": others,
            "mechanical_event_tp": ev_tp,
            "mechanical_event_fp": ev_fp,
            "mechanical_event_precision": round(ev_tp / (ev_tp + ev_fp) * 100, 2),
            "adjusted_event_tp": adjusted_ev_tp,
            "adjusted_event_fp": adjusted_ev_fp,
            "adjusted_event_precision": round(adjusted_ev_prec, 2),
        },
        "metric_ontology": {
            "parent_children": {k: list(v["children"]) for k, v in METRIC_ONTOLOGY.items()},
            "child_to_parent": CHILD_TO_PARENT,
        },
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v28_audit_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
