"""V32 §2-4 — Deep Machine Adjudication of 788 AMBIGUOUS GT facts.

For each AMBIGUOUS fact, performs deeper structural and semantic analysis:
  A. DOM location (article/body vs nav/footer/sidebar)
  B. Link structure (anchor text, repeated patterns)
  C. Semantic context (sentence, paragraph, heading)
  D. Metric context (keyword, unit, entity, period)
  E. Document purpose (publication vs index/listing)
  F. Duplication check

Assigns one of:
  TRUE_MATERIAL_FACT
  NAVIGATION_OVER_CAPTURE
  LISTING_OVER_CAPTURE
  OUT_OF_SCOPE
  DUPLICATE_SEMANTIC_FACT
  REMAINS_AMBIGUOUS

With confidence: HIGH / MEDIUM / LOW
LOW-confidence cases MUST remain REMAINS_AMBIGUOUS.

This is NOT human review. This is DEEP_MACHINE_ADJUDICATION.
"""
from __future__ import annotations
import json, re, sys, csv
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


def deep_adjudicate(gt_fact, raw_html, stripped_text):
    """Deep machine adjudication of a single AMBIGUOUS GT fact.

    Returns (disposition, confidence, reasons[], evidence_excerpt).
    """
    doc_id = gt_fact.get("document_id", "")
    value = str(gt_fact.get("value", ""))
    canonical_val = canonical_value(value)
    metric = canonical_metric(gt_fact.get("metric", ""))
    language = gt_fact.get("language", "en")

    # Non-English → OUT_OF_SCOPE
    if language != "en":
        return "OUT_OF_SCOPE", "HIGH", [f"Non-English ({language})"], ""

    if not stripped_text:
        return "OUT_OF_SCOPE", "HIGH", ["No document text available"], ""

    # Find value in stripped text
    pos = stripped_text.find(value)
    if pos == -1:
        pos = stripped_text.find(canonical_val)
    if pos == -1:
        return "OUT_OF_SCOPE", "HIGH", [f"Value '{value}' not in stripped text"], ""

    # ── A. DOM location analysis ──
    # Check raw HTML for structural context around the value
    dom_location = "UNKNOWN"
    dom_signals = []

    if raw_html:
        raw_lower = raw_html.lower()
        # Find value in raw HTML
        raw_pos = raw_lower.find(value.lower())
        if raw_pos == -1:
            raw_pos = raw_lower.find(canonical_val.lower())

        if raw_pos >= 0:
            # Check what HTML tags surround the value
            before = raw_html[max(0, raw_pos - 500):raw_pos]
            after = raw_html[raw_pos:raw_pos + 500]

            # Check for navigation/footer/sidebar
            nav_tags = re.findall(r'<(?:nav|footer|aside|header)\b', before, re.IGNORECASE)
            if len(nav_tags) >= 2:
                dom_location = "NAVIGATION"
                dom_signals.append(f"{len(nav_tags)} nav/footer/aside/header tags before value")

            # Check for article/body/main
            content_tags = re.findall(r'<(?:article|main|section)\b', before, re.IGNORECASE)
            if len(content_tags) >= 1 and dom_location == "UNKNOWN":
                dom_location = "ARTICLE_BODY"
                dom_signals.append(f"{len(content_tags)} article/main/section tags before value")

            # Check for list/table structure
            if re.search(r'<(?:ul|ol|table|tbody|tr)\b', before, re.IGNORECASE):
                dom_location = "LIST_TABLE" if dom_location == "UNKNOWN" else dom_location
                dom_signals.append("list/table structure nearby")

            # Check for repeated link patterns (listing page signal)
            links_before = re.findall(r'<a\s+[^>]*href="([^"]*)"', before, re.IGNORECASE)
            if len(links_before) >= 3:
                dom_signals.append(f"{len(links_before)} links before value (listing pattern)")

    # ── B. Link structure analysis ──
    link_signals = []
    if raw_html:
        raw_lower = raw_html.lower()
        raw_pos = raw_lower.find(value.lower())
        if raw_pos == -1:
            raw_pos = raw_lower.find(canonical_val.lower())
        if raw_pos >= 0:
            # Check if value is inside an <a> tag
            before_200 = raw_html[max(0, raw_pos - 200):raw_pos]
            after_200 = raw_html[raw_pos:raw_pos + 200]
            if re.search(r'<a\s', before_200, re.IGNORECASE) and '</a>' in after_200:
                link_signals.append("Value inside <a> anchor tag")
            # Check for stock photo credits
            if re.search(r'shutterstock|adobe|stock\.photo|getty', before_200 + after_200, re.IGNORECASE):
                link_signals.append("Stock photo credit nearby")

    # ── C. Semantic context analysis ──
    sent_start = max(0, pos - 300)
    sent_end = min(len(stripped_text), pos + len(value) + 300)
    sentence = stripped_text[sent_start:sent_end]

    para_start = max(0, pos - 600)
    para_end = min(len(stripped_text), pos + len(value) + 600)
    paragraph = stripped_text[para_start:para_end]

    # ── D. Metric context ──
    has_metric = bool(re.search(
        r"\b(?:gdp|inflation|cpi|unemployment|employment|trade|production|"
        r"rate|growth|change|increase|decrease|revenue|penalty|fine|"
        r"settlement|yield|spread|volume|index|indicator|output)\b",
        sentence, re.IGNORECASE
    ))
    has_unit = bool(re.search(
        r"(?:%|percent|bps|basis\s+points?|million|billion|trillion|"
        r"\$|€|£|barrels|tons|people|index\s+points)",
        sentence, re.IGNORECASE
    ))
    has_entity = bool(re.search(
        r"\b(?:sec|cftc|fca|esma|ecb|federal\s+reserve|bank\s+of|"
        r"bureau|census|eurostat|treasury|ministry|corporation|inc\.|"
        r"usa|eurozone|european|uk|japan|canada|china)\b",
        paragraph, re.IGNORECASE
    ))
    has_period = bool(re.search(
        r"\b(?:q[1-4]|20\d{2}|january|february|march|april|may|june|july|"
        r"august|september|october|november|december|yoy|qoq|mom|"
        r"annual|quarterly|monthly)\b",
        paragraph, re.IGNORECASE
    ))

    # ── E. Document purpose ──
    text_lower = stripped_text[:2000].lower()
    is_listing_page = bool(re.search(
        r"(?:latest\s+news|view\s+all|asset\s+publisher|all\s+publications|"
        r"press\s+releases|news\s+articles|release\s+calendar|"
        r"browse\s+page|statistics\s+explained)",
        text_lower
    ))
    is_nav_heavy = bool(re.search(
        r"(?:skip\s+to\s+content|main\s+menu|site\s+menu|toggle\s+navigation|"
        r"search\s+the\s+site|change\s+theme|core\s+functions)",
        text_lower
    ))

    # ── F. Duplication check ──
    # Check if same value appears multiple times (cardinality context)
    occurrences = stripped_text.lower().count(canonical_val.lower())
    is_duplicated = occurrences > 5

    # ── Count navigation patterns in sentence ──
    nav_patterns = [
        r"\b(menu|navigation|breadcrumb|sidebar|navbar)\b",
        r"\b(skip\s+to\s+(?:main|content))\b",
        r"\b(contact\s+us|email|phone|tel:|mailto:)\b",
        r"\b(copyright|©)\b",
        r"\b(homepage|home\s+page)\b",
        r"\bpage\s+\d+\b",
        r"\b(click\s+here|read\s+more|share|print|download)\b",
        r"\b(cookie|privacy\s+notice|terms\s+of\s+use)\b",
        r"\b(subscribe|newsletter|sign\s+up)\b",
    ]
    nav_count = sum(1 for p in nav_patterns if re.search(p, sentence, re.IGNORECASE))

    # ── Count listing signals in sentence ──
    listing_patterns = [
        r"\b(?:latest\s+news|view\s+all|asset\s+publisher)\b",
        r"\b(?:published\s+\d|released?\s+\d|updated\s+\d)\b",
        r"\d{1,2}\s+(?:August|July|June|May|April|March|February|January)\s+20\d{2}",
        r"\b(?:shutterstock|adobe|stock)\b",
    ]
    listing_count = sum(1 for p in listing_patterns if re.search(p, sentence, re.IGNORECASE))

    # ── Decision logic ──
    reasons = []
    evidence_excerpt = sentence[:200]

    # Add DOM signals
    if dom_signals:
        reasons.extend(dom_signals)
    if link_signals:
        reasons.extend(link_signals)

    # Add context signals
    reasons.append(f"metric={has_metric}, unit={has_unit}, entity={has_entity}, period={has_period}")
    reasons.append(f"nav_count={nav_count}, listing_count={listing_count}")
    reasons.append(f"dom_location={dom_location}, is_listing_page={is_listing_page}, is_nav_heavy={is_nav_heavy}")
    reasons.append(f"occurrences={occurrences}")

    # HIGH confidence decisions

    # Navigation over-capture (HIGH confidence)
    if nav_count >= 4 and not (has_metric and has_unit):
        return "NAVIGATION_OVER_CAPTURE", "HIGH", reasons, evidence_excerpt

    if dom_location == "NAVIGATION" and nav_count >= 2:
        return "NAVIGATION_OVER_CAPTURE", "HIGH", reasons, evidence_excerpt

    # Listing over-capture (HIGH confidence)
    if is_listing_page and listing_count >= 2 and dom_location in ("NAVIGATION", "UNKNOWN", "LIST_TABLE"):
        return "LISTING_OVER_CAPTURE", "HIGH", reasons, evidence_excerpt

    if link_signals and listing_count >= 2:
        return "LISTING_OVER_CAPTURE", "HIGH", reasons, evidence_excerpt

    # Stock photo credit
    if any("stock photo" in s.lower() for s in link_signals):
        return "LISTING_OVER_CAPTURE", "HIGH", reasons, evidence_excerpt

    # Duplicate semantic fact
    if is_duplicated and not (has_metric and has_unit):
        return "DUPLICATE_SEMANTIC_FACT", "HIGH", reasons, evidence_excerpt

    # True material fact (HIGH confidence)
    if has_metric and has_unit and nav_count <= 1 and dom_location in ("ARTICLE_BODY", "UNKNOWN"):
        if not is_listing_page or (is_listing_page and listing_count == 0):
            return "TRUE_MATERIAL_FACT", "HIGH", reasons, evidence_excerpt

    # MEDIUM confidence decisions

    # Likely navigation (MEDIUM)
    if nav_count >= 3:
        return "NAVIGATION_OVER_CAPTURE", "MEDIUM", reasons, evidence_excerpt

    # Likely listing (MEDIUM)
    if is_listing_page and listing_count >= 1:
        return "LISTING_OVER_CAPTURE", "MEDIUM", reasons, evidence_excerpt

    # Likely material (MEDIUM)
    if has_metric and has_unit and nav_count <= 2:
        return "TRUE_MATERIAL_FACT", "MEDIUM", reasons, evidence_excerpt

    if has_metric and nav_count == 0 and not is_listing_page:
        return "TRUE_MATERIAL_FACT", "MEDIUM", reasons, evidence_excerpt

    # LOW confidence → REMAINS_AMBIGUOUS
    return "REMAINS_AMBIGUOUS", "LOW", reasons, evidence_excerpt


def main():
    print("=" * 70)
    print("V32 — Deep Machine GT Adjudication")
    print("=" * 70)
    print("  This is NOT human review. This is DEEP_MACHINE_ADJUDICATION.")
    print()

    # Load V31 results
    v31 = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v31_gt_audit_results.json"))
    gt_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v1.json"))
    v27_facts = json.load(open(CORE_REPO / "intelligence_core/tests/reliability/v27r_raw_facts.json"))

    # Get the 788 AMBIGUOUS facts from V31
    ambiguous_facts = [d for d in v31["full_disposition_ledger"] if d["disposition"] == "AMBIGUOUS"]
    print(f"  V31 AMBIGUOUS facts: {len(ambiguous_facts)}")

    # Also include the other V31 dispositions for complete GT_V3
    # V31 already removed: NAVIGATION_OVER_CAPTURE (147), LISTING_OVER_CAPTURE (89), OUT_OF_SCOPE (189)
    # V31 kept: TRUE_MATERIAL_FACT (399), AMBIGUOUS (788)
    # V32 re-adjudicates the 788 AMBIGUOUS

    selected = select_300_documents("v3_corpus_store")
    benchmark_doc_ids = set(d["doc_id"] for d in selected)

    # Build Core mult
    core_mult = Counter()
    for f in v27_facts:
        if f.get("document_id") in benchmark_doc_ids:
            ident = canonical_identity(f)
            core_mult[ident] += 1

    # Load document texts and raw HTML
    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    doc_cache = {}

    def get_doc_data(doc_id):
        if doc_id in doc_cache:
            return doc_cache[doc_id]
        rep = None
        for rid, r in reps_by_id.items():
            if r.get("document_id") == doc_id:
                rep = r
                break
        if not rep:
            doc_cache[doc_id] = ("", "")
            return "", ""
        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            doc_cache[doc_id] = ("", "")
            return "", ""
        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                doc_cache[doc_id] = ("", "")
                return "", ""
            raw_html = blob_bytes.decode("utf-8", errors="replace")
            stripped = strip_html(raw_html)
            doc_cache[doc_id] = (raw_html, stripped)
            return raw_html, stripped
        except Exception:
            doc_cache[doc_id] = ("", "")
            return "", ""

    # ── Adjudicate all 788 AMBIGUOUS facts ──
    print(f"\n--- Deep Adjudicating {len(ambiguous_facts)} AMBIGUOUS facts ---")

    adjudicated = []
    for amb in ambiguous_facts:
        gt_fact_id = amb["gt_fact_id"]
        # Find the original GT fact
        gt_fact = next((g for g in gt_facts if g.get("gt_fact_id") == gt_fact_id), None)
        if not gt_fact:
            adjudicated.append({
                "gt_fact_id": gt_fact_id,
                "document_id": amb["document_id"],
                "v31_disposition": "AMBIGUOUS",
                "v32_disposition": "OUT_OF_SCOPE",
                "confidence": "HIGH",
                "reasons": ["GT fact not found in original GT"],
                "evidence_excerpt": "",
            })
            continue

        doc_id = gt_fact.get("document_id", "")
        raw_html, stripped_text = get_doc_data(doc_id)
        disposition, confidence, reasons, evidence = deep_adjudicate(gt_fact, raw_html, stripped_text)

        adjudicated.append({
            "gt_fact_id": gt_fact_id,
            "document_id": doc_id,
            "source_id": docs_by_id.get(doc_id, {}).get("source_id", ""),
            "metric": gt_fact.get("metric", ""),
            "value": gt_fact.get("value", ""),
            "language": gt_fact.get("language", "en"),
            "v31_disposition": "AMBIGUOUS",
            "v32_disposition": disposition,
            "confidence": confidence,
            "reasons": reasons,
            "evidence_excerpt": evidence,
        })

    # ── §3: Classification summary ──
    disposition_counter = Counter()
    confidence_counter = Counter()
    for a in adjudicated:
        disposition_counter[a["v32_disposition"]] += 1
        confidence_counter[a["confidence"]] += 1

    print(f"\n--- V32 Disposition of 788 AMBIGUOUS facts ---")
    print(f"\n  {'Disposition':<30} {'Count':>6} {'%':>8}")
    print(f"  {'-'*46}")
    for disp, count in disposition_counter.most_common():
        pct = count / len(adjudicated) * 100
        print(f"  {disp:<30} {count:>6} {pct:>7.1f}%")

    print(f"\n  Confidence breakdown:")
    for conf, count in confidence_counter.most_common():
        print(f"    {conf:<10} {count:>6}")

    print(f"\n  Hard invariant: {sum(disposition_counter.values())} == 788  {'✓' if sum(disposition_counter.values()) == 788 else '✗'}")

    # ── §6: Build GT_V3 ──
    print(f"\n--- §6: Building GT_V3_MACHINE_ADJUDICATED ---")

    # GT_V3 = V31 TRUE_MATERIAL_FACT (399) + V32 TRUE_MATERIAL_FACT + V32 REMAINS_AMBIGUOUS + V32 MEDIUM TRUE_MATERIAL
    # Remove only HIGH-confidence: NAV/LISTING/OUT_OF_SCOPE/DUPLICATE

    gt_v3 = []
    removed_v32 = []

    # Start with V31 TRUE_MATERIAL_FACT (399) — these stay
    v31_true_material = [d for d in v31["full_disposition_ledger"] if d["disposition"] == "TRUE_MATERIAL_FACT"]
    for d in v31_true_material:
        gt = next((g for g in gt_facts if g.get("gt_fact_id") == d["gt_fact_id"]), None)
        if gt:
            gt_v3.append(gt)

    # Process V32 adjudicated AMBIGUOUS facts
    for a in adjudicated:
        gt = next((g for g in gt_facts if g.get("gt_fact_id") == a["gt_fact_id"]), None)
        if not gt:
            continue

        if a["v32_disposition"] == "REMAINS_AMBIGUOUS":
            # Keep in GT_V3 (conservative)
            gt_v3.append(gt)
        elif a["confidence"] == "HIGH" and a["v32_disposition"] in (
            "NAVIGATION_OVER_CAPTURE", "LISTING_OVER_CAPTURE", "OUT_OF_SCOPE", "DUPLICATE_SEMANTIC_FACT"
        ):
            # Remove with HIGH confidence
            removed_v32.append(a)
        else:
            # MEDIUM confidence TRUE_MATERIAL or other → keep
            gt_v3.append(gt)

    print(f"  V31 TRUE_MATERIAL: {len(v31_true_material)}")
    print(f"  V32 removed (HIGH confidence): {len(removed_v32)}")
    print(f"  V32 kept (TRUE_MATERIAL + MEDIUM + REMAINS_AMBIGUOUS): {len(gt_v3) - len(v31_true_material)}")
    print(f"  GT_V3 total: {len(gt_v3)}")

    # Save GT_V3
    gt_v3_path = CORE_REPO / "intelligence_core/tests/reliability/fact_gt_v3.json"
    with open(gt_v3_path, "w") as f:
        json.dump(gt_v3, f, indent=2, default=str)

    # ── §7: Recompute Recall ──
    print(f"\n--- §7: Recompute Recall ---")

    # Build GT_V3 mult
    gt_v3_mult = Counter()
    for g in gt_v3:
        ident = (g["document_id"], canonical_metric(g["metric"]), canonical_value(g["value"]))
        gt_v3_mult[ident] += 1

    # Bipartite match Core against GT_V3
    tp_v3 = fn_v3 = fp_v3 = 0
    all_idents = set(gt_v3_mult.keys()) | set(core_mult.keys())
    for ident in all_idents:
        g = gt_v3_mult.get(ident, 0)
        c = core_mult.get(ident, 0)
        tp_v3 += min(g, c)
        fn_v3 += max(0, g - c)
        fp_v3 += max(0, c - g)

    gt_v3_total = sum(gt_v3_mult.values())
    recall_v3 = (tp_v3 / gt_v3_total * 100) if gt_v3_total else 0
    precision_v3 = (tp_v3 / (tp_v3 + fp_v3) * 100) if (tp_v3 + fp_v3) else 0

    print(f"\n  Original GT (1,612):  TP=338  FN=1,274  Recall=20.97%")
    print(f"  GT_V2 (1,187):         TP=321  FN=866    Recall=27.04%")
    print(f"  GT_V3 ({gt_v3_total}):   TP={tp_v3}  FN={fn_v3}    Recall={recall_v3:.2f}%  Precision={precision_v3:.2f}%")
    print(f"  Invariant: TP({tp_v3}) + FN({fn_v3}) = {tp_v3 + fn_v3} vs GT_V3({gt_v3_total})  {'✓' if tp_v3 + fn_v3 == gt_v3_total else '✗'}")

    # ── §8: Uncertainty bounds ──
    print(f"\n--- §8: Uncertainty Bounds ---")

    remains_ambiguous_count = disposition_counter.get("REMAINS_AMBIGUOUS", 0)

    # Lower bound: assume ALL remaining ambiguous are valid GT
    gt_lower = gt_v3_total  # GT_V3 already includes REMAINS_AMBIGUOUS
    recall_lower = (tp_v3 / gt_lower * 100) if gt_lower else 0

    # Upper bound: assume ALL remaining ambiguous are artifacts (remove them)
    gt_upper = gt_v3_total - remains_ambiguous_count
    # Recalculate TP if ambiguous facts removed
    # TP can only stay same or decrease (some TPs matched ambiguous GT facts)
    # For upper bound, keep TP same (optimistic) — actual TP might be lower
    recall_upper = (tp_v3 / gt_upper * 100) if gt_upper else 0

    print(f"  Remaining AMBIGUOUS: {remains_ambiguous_count}")
    print(f"  Lower bound (all ambiguous valid):    GT={gt_lower}, Recall={recall_lower:.2f}%")
    print(f"  Upper bound (all ambiguous artifacts): GT={gt_upper}, Recall={recall_upper:.2f}%")
    print(f"  Machine-adjudicated estimate:         Recall={recall_v3:.2f}%")

    # ── §9: True engineering target ──
    print(f"\n--- §9: True Extraction Gap (HIGH-confidence TRUE_MATERIAL missed) ---")

    # Find HIGH-confidence TRUE_MATERIAL facts that Core missed (FN)
    high_true_material = [a for a in adjudicated
                          if a["v32_disposition"] == "TRUE_MATERIAL_FACT"
                          and a["confidence"] == "HIGH"]

    missed_high = []
    for a in high_true_material:
        gt = next((g for g in gt_facts if g.get("gt_fact_id") == a["gt_fact_id"]), None)
        if not gt:
            continue
        ident = (gt["document_id"], canonical_metric(gt["metric"]), canonical_value(gt["value"]))
        c = core_mult.get(ident, 0)
        if c == 0:
            missed_high.append(a)

    # Also include V31 TRUE_MATERIAL facts that Core missed
    v31_true_missed = []
    for d in v31_true_material:
        gt = next((g for g in gt_facts if g.get("gt_fact_id") == d["gt_fact_id"]), None)
        if not gt:
            continue
        ident = (gt["document_id"], canonical_metric(gt["metric"]), canonical_value(gt["value"]))
        c = core_mult.get(ident, 0)
        if c == 0:
            v31_true_missed.append(d)

    total_missed_true = len(missed_high) + len(v31_true_missed)
    print(f"  V31 TRUE_MATERIAL missed by Core: {len(v31_true_missed)}")
    print(f"  V32 HIGH TRUE_MATERIAL missed by Core: {len(missed_high)}")
    print(f"  Total HIGH-confidence true FN: {total_missed_true}")

    # Classify the gap
    gap_taxonomy = Counter()
    for a in missed_high + v31_true_missed:
        doc_id = a.get("document_id", "")
        raw_html, stripped_text = get_doc_data(doc_id)
        if not stripped_text:
            gap_taxonomy["VALUE_NOT_IN_TEXT"] += 1
            continue
        value = a.get("value", "")
        pos = stripped_text.find(value)
        if pos == -1:
            gap_taxonomy["VALUE_NOT_IN_TEXT"] += 1
            continue
        ctx = stripped_text[max(0, pos-100):min(len(stripped_text), pos+100)].lower()
        if re.search(r"%|percent", ctx):
            gap_taxonomy["EVIDENCE_SELECTION_GAP"] += 1
        elif re.search(r"\b(?:gdp|inflation|cpi|unemployment|rate|growth)\b", ctx):
            gap_taxonomy["METRIC_CONTEXT_GAP"] += 1
        elif re.search(r"\$\d|million|billion", ctx):
            gap_taxonomy["ENTITY_CONTEXT_GAP"] += 1
        else:
            gap_taxonomy["OTHER"] += 1

    print(f"\n  Gap taxonomy:")
    for gap, count in gap_taxonomy.most_common():
        print(f"    {gap:<30} {count}")

    # ── §10: Human review packet ──
    print(f"\n--- §10: Human Review Packet ---")

    # Prioritize: all LOW + all MEDIUM + representative HIGH
    review_packet = []
    for a in adjudicated:
        if a["confidence"] in ("LOW", "MEDIUM"):
            review_packet.append(a)
        elif a["confidence"] == "HIGH" and a["v32_disposition"] in ("TRUE_MATERIAL_FACT", "REMAINS_AMBIGUOUS"):
            # Include some HIGH-confidence TRUE_MATERIAL and REMAINS_AMBIGUOUS
            review_packet.append(a)

    # Also include V31 TRUE_MATERIAL that Core missed
    for d in v31_true_missed:
        review_packet.append({
            "gt_fact_id": d["gt_fact_id"],
            "document_id": d["document_id"],
            "source_id": d.get("source_id", ""),
            "metric": d.get("metric", ""),
            "value": d.get("value", ""),
            "language": d.get("language", "en"),
            "v31_disposition": "TRUE_MATERIAL_FACT",
            "v32_disposition": "TRUE_MATERIAL_FACT (V31)",
            "confidence": "HIGH (V31)",
            "reasons": ["V31 confirmed TRUE_MATERIAL_FACT, Core missed"],
            "evidence_excerpt": "",
        })

    print(f"  Review packet size: {len(review_packet)}")

    # Save as CSV
    csv_path = CORE_REPO / "docs/evidence/ROUAA_CORE_HUMAN_REVIEW_PACKET_V32.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "gt_fact_id", "document_id", "source_id", "metric", "value", "language",
            "v31_disposition", "v32_disposition", "confidence", "reasons", "evidence_excerpt"
        ])
        writer.writeheader()
        for r in review_packet:
            writer.writerow({
                "gt_fact_id": r.get("gt_fact_id", ""),
                "document_id": r.get("document_id", ""),
                "source_id": r.get("source_id", ""),
                "metric": r.get("metric", ""),
                "value": r.get("value", ""),
                "language": r.get("language", "en"),
                "v31_disposition": r.get("v31_disposition", ""),
                "v32_disposition": r.get("v32_disposition", ""),
                "confidence": r.get("confidence", ""),
                "reasons": "; ".join(r.get("reasons", [])),
                "evidence_excerpt": r.get("evidence_excerpt", "")[:200],
            })

    # Save as JSON for full data
    json_path = CORE_REPO / "intelligence_core/tests/reliability/v32_review_packet.json"
    with open(json_path, "w") as f:
        json.dump(review_packet, f, indent=2, default=str)

    print(f"  CSV saved: {csv_path}")
    print(f"  JSON saved: {json_path}")

    # ── Save full results ──
    results = {
        "v32_adjudication": {
            "total_ambiguous": len(ambiguous_facts),
            "dispositions": dict(disposition_counter),
            "confidence": dict(confidence_counter),
        },
        "gt_v3": {
            "size": len(gt_v3),
            "removed_v32": len(removed_v32),
            "remains_ambiguous": remains_ambiguous_count,
        },
        "recall": {
            "original_gt": {"gt": 1612, "tp": 338, "fn": 1274, "recall": 20.97},
            "gt_v2": {"gt": 1187, "tp": 321, "fn": 866, "recall": 27.04},
            "gt_v3": {"gt": gt_v3_total, "tp": tp_v3, "fn": fn_v3, "recall": round(recall_v3, 2), "precision": round(precision_v3, 2)},
            "lower_bound": round(recall_lower, 2),
            "upper_bound": round(recall_upper, 2),
            "machine_adjudicated": round(recall_v3, 2),
        },
        "true_fn": {
            "v31_true_material_missed": len(v31_true_missed),
            "v32_high_true_material_missed": len(missed_high),
            "total_high_confidence_fn": total_missed_true,
            "gap_taxonomy": dict(gap_taxonomy),
        },
        "review_packet_size": len(review_packet),
    }
    out_path = CORE_REPO / "intelligence_core/tests/reliability/v32_deep_adjudication_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Save full adjudication ledger
    ledger_path = CORE_REPO / "intelligence_core/tests/reliability/v32_adjudication_ledger.json"
    with open(ledger_path, "w") as f:
        json.dump(adjudicated, f, indent=2, default=str)

    print(f"\n  Results saved: {out_path}")
    print(f"  Ledger saved: {ledger_path}")
    print(f"  GT_V3 saved: {gt_v3_path}")

    # ── Final scorecard ──
    print(f"\n{'='*70}")
    print(f"V32 Final Scorecard")
    print(f"{'='*70}")
    print(f"\n  Original GT facts:           1,612")
    print(f"  GT_V2:                       1,187")
    print(f"  V31 ambiguous:                 788")
    print(f"\n  V32 dispositions:")
    for disp, count in disposition_counter.most_common():
        print(f"    {disp:<30} {count}")
    print(f"\n  GT_V3_MACHINE_ADJUDICATED:   {len(gt_v3)}")
    print(f"  Core TP:                     {tp_v3}")
    print(f"  Core FN:                     {fn_v3}")
    print(f"\n  Original GT Recall:          20.97%")
    print(f"  GT_V2 Recall:                27.04%")
    print(f"  Machine-adjudicated Recall:  {recall_v3:.2f}%")
    print(f"\n  Recall lower bound:          {recall_lower:.2f}%")
    print(f"  Recall upper bound:          {recall_upper:.2f}%")
    print(f"\n  HIGH-confidence true FN:     {total_missed_true}")
    print(f"  Review packet size:           {len(review_packet)}")


if __name__ == "__main__":
    main()
