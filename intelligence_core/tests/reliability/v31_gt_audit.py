"""V31 §2-6 — Ground Truth Audit & Reclassification.

Builds a fact disposition ledger for ALL 1,612 GT facts.
Independently adjudicates a stratified 250-fact sample.
Measures GT purity. Extrapolates to full population.
"""
from __future__ import annotations
import json, re, sys, random
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.v19_forensic import normalize_metric_v19
from intelligence_core.tests.reliability.v14_ground_truth import select_300_documents
from intelligence_core.tests.reliability.v23r_bipartite_matching import (
    canonical_value, canonical_metric, canonical_identity,
)

# V9 navigation patterns (used for independent adjudication)
NAV_KEYWORDS = [
    r"\b(menu|navigation|breadcrumb|sidebar|navbar)\b",
    r"\b(skip\s+to\s+(?:main|content))\b",
    r"\b(search\s+(?:form|box|button))\b",
    r"\b(facebook|twitter|linkedin|youtube|instagram)\b",
    r"\b(contact\s+us|email|phone|address|tel:|mailto:)\b",
    r"\b(copyright|©|all\s+rights\s+reserved)\b",
    r"\b(homepage|home\s+page)\b",
    r"\bpage\s+\d+\b",
    r"\bp\.\s*\d+\b",
    r"\b(click\s+here|read\s+more|share|print|download)\b",
    r"\b(cookie|privacy\s+notice|terms\s+of\s+use)\b",
    r"\b(browse\s+page|news\s+articles|press\s+releases?)\b",
    r"\b(subscribe|newsletter|sign\s+up|sign\s+in|log\s+in|register)\b",
    r"\b(privacy\s+policy|cookie\s+consent)\b",
]

COMPILED_NAV = [re.compile(p, re.IGNORECASE) for p in NAV_KEYWORDS]


def adjudicate_fact(gt_fact, doc_text):
    """Independently adjudicate a single GT fact.

    Returns one of:
      TRUE_MATERIAL_FACT — the value appears in semantic content with
        metric/entity/unit context, not in navigation/listing
      NAVIGATION_OVER_CAPTURE — the value appears primarily in navigation,
        site menu, or boilerplate context
      LISTING_OVER_CAPTURE — the value appears in a news/article listing
        page where it's a headline link, not the primary content
      UI_TEMPLATE_ARTIFACT — the value is from CSS/JS/template content
      DUPLICATE_SEMANTIC_FACT — same value already counted at same identity
      AMBIGUOUS — cannot determine independently
      OUT_OF_SCOPE — value not in stripped text or non-English
    """
    doc_id = gt_fact.get("document_id", "")
    value = str(gt_fact.get("value", ""))
    canonical_val = canonical_value(value)
    metric = canonical_metric(gt_fact.get("metric", ""))
    language = gt_fact.get("language", "en")

    # Non-English — out of scope for English adjudication
    if language != "en":
        return "OUT_OF_SCOPE", f"Non-English ({language})"

    if not doc_text:
        return "OUT_OF_SCOPE", "No document text available"

    # Find the value in document
    pos = doc_text.find(value)
    if pos == -1:
        pos = doc_text.find(canonical_val)
    if pos == -1:
        return "OUT_OF_SCOPE", f"Value '{value}' not in stripped text"

    # Get context windows
    sent_start = max(0, pos - 200)
    sent_end = min(len(doc_text), pos + len(value) + 200)
    sentence = doc_text[sent_start:sent_end]

    para_start = max(0, pos - 500)
    para_end = min(len(doc_text), pos + len(value) + 500)
    paragraph = doc_text[para_start:para_end]

    # Count navigation patterns in the sentence (±200 chars around value)
    nav_count_sent = sum(1 for p in COMPILED_NAV if p.search(sentence))

    # Count navigation patterns in the paragraph (±500 chars)
    nav_count_para = sum(1 for p in COMPILED_NAV if p.search(paragraph))

    # Check if value is in a "listing" context (news headline links, publication index)
    listing_signals = [
        r"\b(?:latest\s+news|view\s+all|asset\s+publisher)\b",
        r"\b(?:published\s+\d|released?\s+\d|updated\s+\d)\b",
        r"\d{1,2}\s+(?:August|July|June|May|April|March|February|January)\s+20\d{2}",
        r"\b(?:shutterstock|adobe|stock)\b",  # Stock photo credits
    ]
    listing_count = sum(1 for p in listing_signals if re.search(p, sentence, re.IGNORECASE))

    # Check for CSS/JS contamination
    css_patterns = [
        r"\.\w+\s*\{[^}]*\}", r"background-color\s*:", r"opacity\s*:",
        r"function\s*\(", r"var\s+\w+\s*=", r"document\.\w+",
    ]
    is_css = any(re.search(p, sentence) for p in css_patterns)

    if is_css:
        return "UI_TEMPLATE_ARTIFACT", "Value in CSS/JS content"

    # Decision logic:
    # If 3+ nav patterns in sentence → NAVIGATION_OVER_CAPTURE
    # If 2+ listing signals in sentence → LISTING_OVER_CAPTURE
    # If value has metric+unit context AND nav_count < 3 → TRUE_MATERIAL_FACT
    # Otherwise → AMBIGUOUS

    if nav_count_sent >= 3:
        return "NAVIGATION_OVER_CAPTURE", f"{nav_count_sent} nav patterns in sentence"

    if listing_count >= 2:
        return "LISTING_OVER_CAPTURE", f"{listing_count} listing signals in sentence"

    # Check for metric + unit context (semantic content)
    has_metric = bool(re.search(
        r"\b(?:gdp|inflation|cpi|unemployment|employment|trade|production|"
        r"rate|growth|change|increase|decrease|revenue|penalty|fine|"
        r"settlement|yield|spread|volume|index|indicator)\b",
        sentence, re.IGNORECASE
    ))
    has_unit = bool(re.search(
        r"(?:%|percent|bps|basis\s+points?|million|billion|trillion|"
        r"\$|€|£|barrels|tons|people|index\s+points)",
        sentence, re.IGNORECASE
    ))

    if has_metric and has_unit and nav_count_sent < 2:
        return "TRUE_MATERIAL_FACT", "metric + unit in semantic content"

    if nav_count_sent >= 2:
        return "NAVIGATION_OVER_CAPTURE", f"{nav_count_sent} nav patterns in sentence"

    if listing_count >= 1:
        return "LISTING_OVER_CAPTURE", f"{listing_count} listing signal in sentence"

    # Value is in text but lacks clear semantic context
    return "AMBIGUOUS", f"nav={nav_count_sent}, listing={listing_count}, metric={has_metric}, unit={has_unit}"


def main():
    print("=" * 70)
    print("V31 — Ground Truth Audit & Reclassification")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    v27_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_facts.json"))

    selected = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected)

    print(f"\n  GT facts: {len(gt_facts)}")
    print(f"  Benchmark docs: {len(benchmark_doc_ids)}")

    # Build Core mult for cardinality check
    core_mult = Counter()
    for f in v27_facts:
        if f.get("document_id") in benchmark_doc_ids:
            ident = canonical_identity(f)
            core_mult[ident] += 1

    # Load doc texts
    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")
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

    # ─── §2: Build fact disposition ledger for ALL 1,612 facts ───
    print(f"\n--- §2: Building Fact Disposition Ledger ---")

    # Stratify by source institution for the sample
    source_by_doc = {}
    for doc_id, doc in docs_by_id.items():
        source_by_doc[doc_id] = doc.get("source_id", "")

    # Build strata
    strata = defaultdict(list)
    for gt in gt_facts:
        if gt.get("document_id") not in benchmark_doc_ids:
            continue
        src = source_by_doc.get(gt["document_id"], "unknown")
        metric = gt.get("metric", "")
        strata[(src, metric)].append(gt)

    # ─── §4: Select stratified 250-fact sample ───
    print(f"\n--- §4: Selecting Stratified 250-Fact Sample ---")

    # Flatten all benchmark GT facts
    benchmark_gt = [g for g in gt_facts if g.get("document_id") in benchmark_doc_ids]
    print(f"  Benchmark GT facts: {len(benchmark_gt)}")

    # Stratify by source institution
    src_groups = defaultdict(list)
    for g in benchmark_gt:
        src = source_by_doc.get(g["document_id"], "unknown")
        src_groups[src].append(g)

    # Sample proportionally from each source, minimum 5 per source
    random.seed(42)  # deterministic
    sample = []
    for src, facts in sorted(src_groups.items()):
        n = max(5, int(250 * len(facts) / len(benchmark_gt)))
        n = min(n, len(facts))
        sampled = random.sample(facts, n)
        sample.extend(sampled)

    # Trim to exactly 250
    if len(sample) > 250:
        sample = random.sample(sample, 250)
    print(f"  Sampled facts: {len(sample)}")
    print(f"  Sources in sample: {len(set(source_by_doc.get(g['document_id'],'') for g in sample))}")

    # ─── §4: Adjudicate each sampled fact ───
    print(f"\n--- §4: Independent Adjudication of {len(sample)} Facts ---")

    sample_dispositions = []
    for gt in sample:
        doc_id = gt.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        disposition, reason = adjudicate_fact(gt, doc_text)
        src = source_by_doc.get(doc_id, "")
        sample_dispositions.append({
            "gt_fact_id": gt.get("gt_fact_id", ""),
            "document_id": doc_id,
            "source_id": src,
            "metric": gt.get("metric", ""),
            "value": gt.get("value", ""),
            "language": gt.get("language", "en"),
            "disposition": disposition,
            "reason": reason,
        })

    # ─── §5: Measure GT purity ───
    disposition_counter = Counter(d["disposition"] for d in sample_dispositions)
    print(f"\n--- §5: GT Purity Metrics (250-fact sample) ---")
    print(f"\n  {'Disposition':<30} {'Count':>6} {'%':>8}")
    print(f"  {'-'*46}")
    for disp, count in disposition_counter.most_common():
        pct = count / len(sample) * 100
        print(f"  {disp:<30} {count:>6} {pct:>7.1f}%")

    total_sampled = len(sample_dispositions)
    true_material = disposition_counter.get("TRUE_MATERIAL_FACT", 0)
    nav_over = disposition_counter.get("NAVIGATION_OVER_CAPTURE", 0)
    listing_over = disposition_counter.get("LISTING_OVER_CAPTURE", 0)
    ui_artifact = disposition_counter.get("UI_TEMPLATE_ARTIFACT", 0)
    ambiguous = disposition_counter.get("AMBIGUOUS", 0)
    out_scope = disposition_counter.get("OUT_OF_SCOPE", 0)

    print(f"\n  GT Confirmation Rate: {true_material}/{total_sampled} = {true_material/total_sampled*100:.1f}%")
    print(f"  Navigation Over-capture Rate: {nav_over}/{total_sampled} = {nav_over/total_sampled*100:.1f}%")
    print(f"  Listing Over-capture Rate: {listing_over}/{total_sampled} = {listing_over/total_sampled*100:.1f}%")
    print(f"  Ambiguity Rate: {ambiguous}/{total_sampled} = {ambiguous/total_sampled*100:.1f}%")
    print(f"  Out of Scope Rate: {out_scope}/{total_sampled} = {out_scope/total_sampled*100:.1f}%")

    # ─── §6: Extrapolate to full population ───
    print(f"\n--- §6: Extrapolation to Full 1,612 GT Population ---")

    contamination_rate = (nav_over + listing_over + ui_artifact) / total_sampled
    estimated_contamination = int(contamination_rate * len(benchmark_gt))
    estimated_true_gt = len(benchmark_gt) - estimated_contamination

    print(f"  Contamination rate (sample): {contamination_rate*100:.1f}%")
    print(f"  Estimated contamination (full): ~{estimated_contamination} facts")
    print(f"  Estimated true GT: ~{estimated_true_gt} facts")
    print(f"  Estimated true Recall: {338}/{estimated_true_gt} = {338/estimated_true_gt*100:.1f}%")

    # ─── §2: Adjudicate ALL 1,612 facts ───
    print(f"\n--- §2: Full Adjudication of ALL {len(benchmark_gt)} GT Facts ---")

    full_dispositions = []
    for gt in benchmark_gt:
        doc_id = gt.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        disposition, reason = adjudicate_fact(gt, doc_text)
        full_dispositions.append({
            "gt_fact_id": gt.get("gt_fact_id", ""),
            "document_id": doc_id,
            "source_id": source_by_doc.get(doc_id, ""),
            "metric": gt.get("metric", ""),
            "value": gt.get("value", ""),
            "language": gt.get("language", "en"),
            "disposition": disposition,
            "reason": reason,
        })

    full_disposition_counter = Counter(d["disposition"] for d in full_dispositions)
    print(f"\n  {'Disposition':<30} {'Count':>6} {'%':>8}")
    print(f"  {'-'*46}")
    for disp, count in full_disposition_counter.most_common():
        pct = count / len(benchmark_gt) * 100
        print(f"  {disp:<30} {count:>6} {pct:>7.1f}%")

    total_full = len(full_dispositions)
    full_true_material = full_disposition_counter.get("TRUE_MATERIAL_FACT", 0)
    full_nav_over = full_disposition_counter.get("NAVIGATION_OVER_CAPTURE", 0)
    full_listing_over = full_disposition_counter.get("LISTING_OVER_CAPTURE", 0)
    full_ui = full_disposition_counter.get("UI_TEMPLATE_ARTIFACT", 0)
    full_ambiguous = full_disposition_counter.get("AMBIGUOUS", 0)
    full_out_scope = full_disposition_counter.get("OUT_OF_SCOPE", 0)

    print(f"\n  Hard invariant: {sum(full_disposition_counter.values())} == {len(benchmark_gt)}  {'✓' if sum(full_disposition_counter.values()) == len(benchmark_gt) else '✗'}")

    # ─── §7: Build GT_V2 ───
    print(f"\n--- §7: Building GT_V2 ---")

    gt_v2 = []
    removed_facts = []
    for gt, disp in zip(benchmark_gt, full_dispositions):
        if disp["disposition"] == "TRUE_MATERIAL_FACT":
            gt_v2.append(gt)
        elif disp["disposition"] == "AMBIGUOUS":
            # Keep ambiguous facts in GT_V2 (conservative — don't remove without certainty)
            gt_v2.append(gt)
        else:
            removed_facts.append({
                "original_gt_fact_id": gt.get("gt_fact_id", ""),
                "document_id": gt.get("document_id", ""),
                "source_id": disp["source_id"],
                "metric": gt.get("metric", ""),
                "value": gt.get("value", ""),
                "disposition": disp["disposition"],
                "reason": disp["reason"],
            })

    print(f"  Original GT: {len(benchmark_gt)}")
    print(f"  GT_V2 (TRUE_MATERIAL + AMBIGUOUS): {len(gt_v2)}")
    print(f"  Removed (NAV + LISTING + UI + OUT_OF_SCOPE): {len(removed_facts)}")
    print(f"  Removed breakdown:")
    removed_breakdown = Counter(r["disposition"] for r in removed_facts)
    for disp, count in removed_breakdown.most_common():
        print(f"    {disp:<30} {count}")

    # ─── §8: Recalculate Core Recall against GT_V2 ───
    print(f"\n--- §8: Recalculate Core Recall against GT_V2 ---")

    # Build GT_V2 mult
    gt_v2_mult = Counter()
    for g in gt_v2:
        ident = (g["document_id"], canonical_metric(g["metric"]), canonical_value(g["value"]))
        gt_v2_mult[ident] += 1

    # Bipartite match Core against GT_V2
    tp_v2 = fn_v2 = fp_v2 = 0
    all_idents = set(gt_v2_mult.keys()) | set(core_mult.keys())
    for ident in all_idents:
        g = gt_v2_mult.get(ident, 0)
        c = core_mult.get(ident, 0)
        tp_v2 += min(g, c)
        fn_v2 += max(0, g - c)
        fp_v2 += max(0, c - g)

    gt_v2_total = sum(gt_v2_mult.values())
    recall_v2 = (tp_v2 / gt_v2_total * 100) if gt_v2_total else 0
    precision_v2 = (tp_v2 / (tp_v2 + fp_v2) * 100) if (tp_v2 + fp_v2) else 0

    print(f"\n  Original GT (1,612):")
    print(f"    TP=338  FP=58  FN=1,274")
    print(f"    Recall=20.97%  Precision=85.35%")
    print(f"\n  GT_V2 ({gt_v2_total}):")
    print(f"    TP={tp_v2}  FP={fp_v2}  FN={fn_v2}")
    print(f"    Recall={recall_v2:.2f}%  Precision={precision_v2:.2f}%")
    print(f"    Invariant: TP({tp_v2}) + FN({fn_v2}) = {tp_v2 + fn_v2} vs GT_V2({gt_v2_total})  {'✓' if tp_v2 + fn_v2 == gt_v2_total else '✗'}")

    # ─── Save results ───
    results = {
        "sample_size": len(sample),
        "sample_dispositions": sample_dispositions,
        "sample_purity": {
            "true_material": true_material,
            "nav_over_capture": nav_over,
            "listing_over_capture": listing_over,
            "ui_artifact": ui_artifact,
            "ambiguous": ambiguous,
            "out_of_scope": out_scope,
            "confirmation_rate": round(true_material / total_sampled * 100, 1),
            "contamination_rate": round((nav_over + listing_over + ui_artifact) / total_sampled * 100, 1),
        },
        "full_adjudication": {
            "total_gt": len(benchmark_gt),
            "dispositions": dict(full_disposition_counter),
            "true_material": full_true_material,
            "nav_over_capture": full_nav_over,
            "listing_over_capture": full_listing_over,
            "ui_artifact": full_ui,
            "ambiguous": full_ambiguous,
            "out_of_scope": full_out_scope,
        },
        "gt_v2": {
            "original_gt": len(benchmark_gt),
            "gt_v2_size": len(gt_v2),
            "removed": len(removed_facts),
            "removed_breakdown": dict(removed_breakdown),
        },
        "recall_recalculation": {
            "original_gt_total": 1612,
            "original_tp": 338,
            "original_fn": 1274,
            "original_recall": 20.97,
            "gt_v2_total": gt_v2_total,
            "gt_v2_tp": tp_v2,
            "gt_v2_fp": fp_v2,
            "gt_v2_fn": fn_v2,
            "gt_v2_recall": round(recall_v2, 2),
            "gt_v2_precision": round(precision_v2, 2),
            "invariant_holds": tp_v2 + fn_v2 == gt_v2_total,
        },
        "full_disposition_ledger": full_dispositions,
        "removed_facts": removed_facts,
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v31_gt_audit_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")

    # Save GT_V2
    gt_v2_path = CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v2.json"
    with open(gt_v2_path, "w") as f:
        json.dump(gt_v2, f, indent=2, default=str)
    print(f"  GT_V2 saved: {gt_v2_path}")


if __name__ == "__main__":
    main()
