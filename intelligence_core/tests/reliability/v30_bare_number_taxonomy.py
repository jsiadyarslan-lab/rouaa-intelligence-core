"""V30 §2 — Bare-Number Taxonomy.

Classify all BARE_NUMBER FN facts into subcategories:
  metric-nearby, entity-nearby, unit-nearby, period-nearby,
  table/list context, multi-number ambiguity, unresolvable
"""
from __future__ import annotations
import json, re, sys
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


def classify_bare_number(gt_fact, doc_text, core_count_at_identity):
    doc_id = gt_fact.get("document_id", "")
    metric = canonical_metric(gt_fact.get("metric", ""))
    value = str(gt_fact.get("value", ""))
    canonical_val = canonical_value(value)

    if core_count_at_identity > 0:
        return "ALREADY_EXTRACTED_CARDINALITY"

    if not doc_text:
        return "UNRESOLVABLE"

    pos = doc_text.find(value)
    if pos == -1:
        pos = doc_text.find(canonical_val)
    if pos == -1:
        return "UNRESOLVABLE"

    # Context windows
    sent_start = max(0, pos - 150)
    sent_end = min(len(doc_text), pos + len(value) + 150)
    sentence = doc_text[sent_start:sent_end].lower()

    para_start = max(0, pos - 400)
    para_end = min(len(doc_text), pos + len(value) + 400)
    paragraph = doc_text[para_start:para_end].lower()

    # §3: Check for metric keywords nearby
    metric_keywords = [
        r"\b(gdp|gross\s+domestic\s+product|inflation|cpi|unemployment|employment|"
        r"trade|export|import|production|output|manufacturing|industrial|"
        r"rate|growth|change|increase|decrease|revenue|penalty|fine|"
        r"settlement|disgorgement|yield|spread|volume|barrels|tons|"
        r"index|indicator|survey|estimate|figure)\b"
    ]
    has_metric_nearby = any(re.search(p, sentence) for p in metric_keywords)

    # Check for entity nearby
    entity_patterns = [
        r"\b(sec|cftc|fca|esma|ecb|federal\s+reserve|bank\s+of\s+(?:canada|england|japan)|"
        r"bureau|census|eurostat|statistics|treasury|ministry)\b",
        r"\b(defendant|respondent|company|corporation|inc\.|ltd\.|corp\.|"
        r"bank|fund|institution)\b",
        r"\b(usa|united\s+states|eurozone|european\s+union|uk|japan|canada|"
        r"china|germany|france|italy|spain)\b",
    ]
    has_entity_nearby = any(re.search(p, paragraph) for p in entity_patterns)

    # Check for unit nearby
    unit_patterns = [
        r"\b(?:%|percent|percentage|bps|basis\s+points?|million|billion|trillion|"
        r"thousand|barrels|tons|tonnes|people|persons|employees|index\s+points?|"
        r"units?)\b",
        r"\$|€|£|¥",
    ]
    has_unit_nearby = any(re.search(p, sentence) for p in unit_patterns)

    # Check for period nearby
    period_patterns = [
        r"\b(?:q[1-4]|20\d{2}|january|february|march|april|may|june|july|"
        r"august|september|october|november|december|yoy|qoq|mom|"
        r"annual|quarterly|monthly|fiscal)\b",
    ]
    has_period_nearby = any(re.search(p, paragraph) for p in period_patterns)

    # Check for table/list context
    in_table = "[table:" in sentence.lower() or "|" in sentence
    in_list = "[list]" in sentence.lower()

    # Check for multiple same-value occurrences (ambiguity)
    occurrences = doc_text.lower().count(canonical_val.lower())
    has_multi_number = occurrences > 3

    # Classify
    if has_metric_nearby and has_unit_nearby:
        return "METRIC_AND_UNIT_NEARBY"
    elif has_metric_nearby:
        return "METRIC_NEARBY"
    elif has_entity_nearby and has_unit_nearby:
        return "ENTITY_AND_UNIT_NEARBY"
    elif has_entity_nearby:
        return "ENTITY_NEARBY"
    elif has_unit_nearby:
        return "UNIT_NEARBY"
    elif has_period_nearby:
        return "PERIOD_NEARBY"
    elif in_table or in_list:
        return "TABLE_LIST_CONTEXT"
    elif has_multi_number:
        return "MULTI_NUMBER_AMBIGUITY"
    else:
        return "UNRESOLVABLE"


def main():
    print("=" * 70)
    print("V30 §2 — Bare-Number Taxonomy")
    print("=" * 70)

    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    v27_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_facts.json"))

    selected = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected)

    # Build GT and Core mult
    gt_mult = Counter()
    for g in gt_facts:
        if g.get("document_id") not in benchmark_doc_ids:
            continue
        ident = (g["document_id"], canonical_metric(g["metric"]), canonical_value(g["value"]))
        gt_mult[ident] += 1

    core_mult = Counter()
    for f in v27_facts:
        if f.get("document_id") not in benchmark_doc_ids:
            continue
        ident = canonical_identity(f)
        core_mult[ident] += 1

    # Find all FN
    fn_facts = []
    for ident, g_count in gt_mult.items():
        c_count = core_mult.get(ident, 0)
        if g_count > c_count:
            doc_id, metric, value = ident
            matching_gt = [g for g in gt_facts
                           if g.get("document_id") == doc_id
                           and canonical_metric(g.get("metric", "")) == metric
                           and canonical_value(g.get("value", "")) == value]
            fn_facts.extend([(g, c_count) for g in matching_gt[:g_count - c_count]])

    print(f"\n  Total FN: {len(fn_facts)}")

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

    # Classify ALL FN (not just BARE_NUMBER) to get full picture
    taxonomy = Counter()
    fn_classified = []

    for fn, core_count in fn_facts:
        doc_id = fn.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        category = classify_bare_number(fn, doc_text, core_count)
        fn_classified.append({
            "gt_fact_id": fn.get("gt_fact_id", ""),
            "document_id": doc_id,
            "metric": fn.get("metric", ""),
            "value": fn.get("value", ""),
            "language": fn.get("language", "en"),
            "category": category,
        })
        taxonomy[category] += 1

    print(f"\n--- Full FN Taxonomy ---")
    print(f"\n  {'Category':<30} {'Count':>8} {'%':>8}")
    print(f"  {'-'*48}")
    for cat, count in taxonomy.most_common():
        pct = count / len(fn_facts) * 100
        print(f"  {cat:<30} {count:>8} {pct:>7.1f}%")

    # Focus on BARE_NUMBER candidates (those NOT already extracted)
    bare_candidates = [fn for fn in fn_classified if fn["category"] != "ALREADY_EXTRACTED_CARDINALITY"]
    print(f"\n--- Bare-Number Candidates (excluding already-extracted) ---")
    print(f"  Total: {len(bare_candidates)}")

    bare_taxonomy = Counter()
    for fn in bare_candidates:
        bare_taxonomy[fn["category"]] += 1

    print(f"\n  {'Subcategory':<30} {'Count':>8}")
    print(f"  {'-'*40}")
    for cat, count in bare_taxonomy.most_common():
        print(f"  {cat:<30} {count:>8}")

    # Sample examples per category
    print(f"\n--- Sample examples (top 3 per category) ---")
    by_cat = defaultdict(list)
    for fn in bare_candidates:
        by_cat[fn["category"]].append(fn)

    for cat, fns in sorted(by_cat.items(), key=lambda x: -len(x[1]))[:5]:
        print(f"\n  {cat} ({len(fns)} facts):")
        for fn in fns[:3]:
            print(f"    gtf={fn['gt_fact_id']} doc={fn['document_id'][:20]} metric={fn['metric']} value='{fn['value']}' lang={fn['language']}")

    # Save
    results = {
        "total_fn": len(fn_facts),
        "full_taxonomy": dict(taxonomy),
        "bare_candidates": len(bare_candidates),
        "bare_taxonomy": dict(bare_taxonomy),
        "fn_classified": fn_classified,
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v30_bare_number_taxonomy.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
