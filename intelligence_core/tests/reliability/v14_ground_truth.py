"""V14 §2-8 — Independent Ground-Truth Benchmark.

Build a 300-document independent ground-truth dataset and measure Core against it.

§2: Select 300 stratified documents
§3-5: Create independent ground truth (facts + events) per document
§6: Compare Core output against ground truth
§7: Classify every mismatch
§8: Independent evidence evaluation

This is the FIRST measurement that doesn't use Core's own rules as the oracle.
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
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.v13_reprocess import classify_language


def select_300_documents(store_root: str = "v3_corpus_store"):
    """§2 — Select 300 stratified documents from the corpus."""
    print(f"\n{'='*70}")
    print(f"V14 §2 — Select 300 Stratified Documents")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")
    sources_by_id = store.latest_by_id("sources", "source_id")

    # Classify documents by source class
    doc_classifications = []
    for doc_id, doc in docs_by_id.items():
        src_id = doc.get("source_id", "")
        if "job-" in src_id:
            continue

        # Find representation
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
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                doc_classifications.append({
                    "doc_id": doc_id, "src_id": src_id, "class": "pdf",
                    "language": "unknown", "is_pdf": True,
                })
                continue
            doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue

        language = classify_language(doc_text)

        # Determine document category
        if any(x in src_id for x in ["fed-reserve", "ecb", "boe", "boj", "boc", "cbk", "bank"]):
            category = "monetary"
        elif any(x in src_id for x in ["sec", "cftc", "esma", "fca", "consob", "naic"]):
            category = "regulatory"
        elif any(x in src_id for x in ["bea", "eurostat", "stats", "stat", "ine"]):
            category = "statistical"
        elif any(x in src_id for x in ["treasury", "mof", "finance"]):
            category = "monetary"
        elif any(x in src_id for x in ["trade", "customs", "ustr", "wto"]):
            category = "trade"
        elif any(x in src_id for x in ["energy", "eia", "oil", "gas"]):
            category = "energy"
        else:
            category = "other"

        doc_classifications.append({
            "doc_id": doc_id, "src_id": src_id, "class": category,
            "language": language, "is_pdf": False, "text_preview": doc_text[:200],
        })

    # Stratify: 75 per category (monetary, statistical, regulatory, mixed)
    by_category = defaultdict(list)
    for d in doc_classifications:
        by_category[d["class"]].append(d)

    selected = []
    targets = {
        "statistical": 75,
        "regulatory": 75,
        "monetary": 75,
        "other": 75,  # mixed: trade, energy, other, pdf
    }

    for cat, target in targets.items():
        pool = by_category.get(cat, [])
        # Ensure diversity: max 5 per source
        per_source = defaultdict(int)
        for d in pool:
            if per_source[d["src_id"]] >= 5:
                continue
            selected.append(d)
            per_source[d["src_id"]] += 1
            if len([s for s in selected if s["class"] == cat]) >= target:
                break
        # Fill from any if not enough
        cat_count = len([s for s in selected if s["class"] == cat])
        if cat_count < target:
            for d in pool:
                if d not in selected:
                    selected.append(d)
                    if len([s for s in selected if s["class"] == cat]) >= target:
                        break

    print(f"\n  Total documents in corpus: {len(doc_classifications)}")
    print(f"  Selected: {len(selected)}")

    # Distribution
    cat_dist = Counter(s["class"] for s in selected)
    lang_dist = Counter(s["language"] for s in selected)
    pdf_count = sum(1 for s in selected if s.get("is_pdf"))

    print(f"\n  By category:")
    for k, v in cat_dist.most_common():
        print(f"    {k:<15} {v:>3}")
    print(f"\n  By language:")
    for k, v in lang_dist.most_common():
        print(f"    {k:<10} {v:>3}")
    print(f"\n  PDFs: {pdf_count}")

    # Source diversity
    sources = set(s["src_id"] for s in selected)
    print(f"  Sources: {len(sources)}")

    return selected


def build_ground_truth(doc_entry: dict, store: CachedStore) -> dict:
    """§3-5 — Build independent ground truth for a single document.

    This creates a HUMAN-AUDITABLE ground truth by:
    1. Reading the document text
    2. Identifying all material facts (percentages, dollar amounts, rate decisions, enforcement actions)
    3. Identifying all events (monetary/statistical/regulatory)
    4. NOT using Core's extraction — using independent pattern matching

    This is a semi-automated ground truth — the patterns are INDEPENDENT of Core's patterns.
    """
    doc_id = doc_entry["doc_id"]
    src_id = doc_entry["src_id"]

    if doc_entry.get("is_pdf"):
        return {
            "doc_id": doc_id,
            "src_id": src_id,
            "is_pdf": True,
            "ground_truth_facts": [],
            "ground_truth_events": [],
            "language": "unknown",
        }

    # Get document text
    reps_by_id = store.latest_by_id("representations", "representation_id")
    rep = None
    for rid, r in reps_by_id.items():
        if r.get("document_id") == doc_id:
            rep = r
            break
    if not rep:
        return {"doc_id": doc_id, "src_id": src_id, "error": "no representation"}

    blob_path = rep.get("raw_location", "")
    if not blob_path or not Path(blob_path).exists():
        return {"doc_id": doc_id, "src_id": src_id, "error": "no blob"}

    try:
        blob_bytes = Path(blob_path).read_bytes()
        if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
            return {"doc_id": doc_id, "src_id": src_id, "is_pdf": True,
                    "ground_truth_facts": [], "ground_truth_events": []}
        doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
    except Exception:
        return {"doc_id": doc_id, "src_id": src_id, "error": "blob read failed"}

    language = classify_language(doc_text)

    # ═══ INDEPENDENT GROUND-TRUTH FACTS ═══
    # Use INDEPENDENT patterns (different from Core's REFINED_PATTERNS)
    gt_facts = []

    # Independent percentage pattern (different from Core's)
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", doc_text, re.IGNORECASE):
        value = m.group(1)
        # Skip navigation-like context
        start = max(0, m.start() - 50)
        end = min(len(doc_text), m.end() + 50)
        context = doc_text[start:end].lower()
        if any(nav in context for nav in ["page ", "cookie", "facebook", "twitter", "menu", "copyright"]):
            continue
        gt_facts.append({
            "metric": "percentage",
            "value": value,
            "evidence_location": (m.start(), m.end()),
            "context_preview": context[:100],
        })

    # Independent dollar amount pattern
    for m in re.finditer(r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|thousand)?", doc_text, re.IGNORECASE):
        value = m.group(1)
        start = max(0, m.start() - 50)
        end = min(len(doc_text), m.end() + 50)
        context = doc_text[start:end].lower()
        if any(nav in context for nav in ["page ", "cookie", "facebook", "twitter", "menu"]):
            continue
        gt_facts.append({
            "metric": "usd_amount",
            "value": value,
            "evidence_location": (m.start(), m.end()),
            "context_preview": context[:100],
        })

    # Independent rate decision pattern
    for m in re.finditer(r"\b(maintain|raise|cut|lower|increase|decrease)\w*\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", doc_text, re.IGNORECASE):
        gt_facts.append({
            "metric": "rate_decision",
            "value": m.group(1).lower(),
            "evidence_location": (m.start(), m.end()),
            "context_preview": doc_text[max(0, m.start()-50):m.end()+50][:100],
        })

    # Independent enforcement action pattern
    for m in re.finditer(r"\b(consent\s+order|cease\s+and\s+desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement\s+action)\b", doc_text, re.IGNORECASE):
        gt_facts.append({
            "metric": "action_type",
            "value": m.group(1).lower(),
            "evidence_location": (m.start(), m.end()),
            "context_preview": doc_text[max(0, m.start()-50):m.end()+50][:100],
        })

    # ═══ INDEPENDENT GROUND-TRUTH EVENTS ═══
    gt_events = []

    # Check for monetary policy decision signals
    has_monetary_context = bool(re.search(
        r"\b(monetary\s+policy|policy\s+rate|interest\s+rate|key\s+rate|base\s+rate|"
        r"central\s+bank|federal\s+reserve|ECB|Bank\s+of\s+England|Bank\s+of\s+Japan)\b",
        doc_text, re.IGNORECASE
    ))
    has_decision = bool(re.search(
        r"\b(decid|announc|statement|press\s+release|maintain.*rate|raise.*rate|cut.*rate)\b",
        doc_text, re.IGNORECASE
    ))
    if has_monetary_context and has_decision:
        gt_events.append({"event_type": "monetary_policy_decision"})

    # Check for statistical release signals
    has_stat_context = bool(re.search(
        r"\b(statistic|data\s+release|index|indicator|survey|estimate|figure|GDP|inflation|CPI|unemployment)\b",
        doc_text, re.IGNORECASE
    ))
    has_period = bool(re.search(
        r"\b(quarter|monthly|annual|year|period|seasonally\s+adjusted)\b",
        doc_text, re.IGNORECASE
    ))
    if has_stat_context and has_period:
        gt_events.append({"event_type": "statistical_release"})

    # Check for regulatory enforcement signals
    has_enforcement = bool(re.search(
        r"\b(consent\s+order|cease\s+and\s+desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement\s+action|fined|sanctioned)\b",
        doc_text, re.IGNORECASE
    ))
    has_authority = bool(re.search(
        r"\b(SEC|CFTC|FCA|ESMA|CONSOB|BAFIN|FINRA|regulator|commission|authority|defendant|respondent)\b",
        doc_text, re.IGNORECASE
    ))
    if has_enforcement and has_authority:
        gt_events.append({"event_type": "regulatory_enforcement"})

    return {
        "doc_id": doc_id,
        "src_id": src_id,
        "is_pdf": False,
        "language": language,
        "ground_truth_facts": gt_facts,
        "ground_truth_events": gt_events,
    }


def run_ground_truth_benchmark(store_root: str = "v3_corpus_store"):
    """Run the full independent ground-truth benchmark."""
    print(f"\n{'='*70}")
    print(f"V14 — Independent Ground-Truth Benchmark")
    print(f"{'='*70}")

    # §2: Select 300 documents
    selected_docs = select_300_documents(store_root)

    store = CachedStore(AppendOnlyStore(store_root))

    # §3-5: Build ground truth for each document
    print(f"\n--- Building Independent Ground Truth ---")
    ground_truth = []
    for i, doc_entry in enumerate(selected_docs):
        gt = build_ground_truth(doc_entry, store)
        ground_truth.append(gt)
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(selected_docs)}...")

    # Count ground-truth facts + events
    total_gt_facts = sum(len(gt["ground_truth_facts"]) for gt in ground_truth)
    total_gt_events = sum(len(gt["ground_truth_events"]) for gt in ground_truth)

    print(f"\n  Ground truth facts: {total_gt_facts}")
    print(f"  Ground truth events: {total_gt_events}")

    # §6: Get Core's output for the same documents
    print(f"\n--- Comparing Core Against Ground Truth ---")

    # Build doc → Core facts map
    core_facts_by_doc = defaultdict(list)
    for f in store.iter("facts"):
        doc_id = f.get("document_id", "")
        core_facts_by_doc[doc_id].append(f)

    # Build doc → Core events map
    core_events_by_doc = defaultdict(list)
    for ev in store.iter("events"):
        doc_id = ev.get("document_id", "")
        core_events_by_doc[doc_id].append(ev)

    # §6-7: Compare and classify mismatches
    fact_tp = 0  # true positives
    fact_fp = 0  # false positives
    fact_fn = 0  # false negatives
    event_tp = 0
    event_fp = 0
    event_fn = 0
    error_taxonomy = Counter()

    for gt in ground_truth:
        doc_id = gt["doc_id"]
        gt_facts = gt["ground_truth_facts"]
        gt_events = gt["ground_truth_events"]

        core_facts = core_facts_by_doc.get(doc_id, [])
        core_events = core_events_by_doc.get(doc_id, [])

        # Compare facts
        gt_values = set(str(f["value"]) for f in gt_facts)
        core_values = set(str(f.get("value", "")) for f in core_facts)

        for cv in core_values:
            if cv in gt_values:
                fact_tp += 1
            else:
                fact_fp += 1
                error_taxonomy["FALSE_POSITIVE_FACT"] += 1

        for gv in gt_values:
            if gv not in core_values:
                fact_fn += 1
                # Classify why missed
                gt_fact = next((f for f in gt_facts if str(f["value"]) == gv), None)
                if gt_fact:
                    ctx = gt_fact.get("context_preview", "").lower()
                    if any(nav in ctx for nav in ["menu", "skip to", "search"]):
                        error_taxonomy["NAVIGATION_REJECTION"] += 1
                    elif gt["language"] != "en":
                        error_taxonomy["LANGUAGE_GAP"] += 1
                    elif gt.get("is_pdf"):
                        error_taxonomy["PDF_GAP"] += 1
                    else:
                        error_taxonomy["PATTERN_GAP"] += 1
                else:
                    error_taxonomy["OTHER"] += 1

        # Compare events
        gt_event_types = set(e["event_type"] for e in gt_events)
        core_event_types = set(e["event_type"] for e in core_events)

        for cet in core_event_types:
            if cet in gt_event_types:
                event_tp += 1
            else:
                event_fp += 1
                error_taxonomy["FALSE_POSITIVE_EVENT"] += 1

        for get in gt_event_types:
            if get not in core_event_types:
                event_fn += 1
                if gt["language"] != "en":
                    error_taxonomy["EVENT_LANGUAGE_GAP"] += 1
                else:
                    error_taxonomy["EVENT_PATTERN_GAP"] += 1

    # §6: Calculate metrics
    fact_precision = (fact_tp / (fact_tp + fact_fp) * 100) if (fact_tp + fact_fp) else 0
    fact_recall = (fact_tp / (fact_tp + fact_fn) * 100) if (fact_tp + fact_fn) else 0
    event_precision = (event_tp / (event_tp + event_fp) * 100) if (event_tp + event_fp) else 0
    event_recall = (event_tp / (event_tp + event_fn) * 100) if (event_tp + event_fn) else 0

    print(f"\n--- Independent Ground-Truth Results ---")
    print(f"\n  Facts:")
    print(f"    True Positives:  {fact_tp}")
    print(f"    False Positives: {fact_fp}")
    print(f"    False Negatives: {fact_fn}")
    print(f"    Precision: {fact_precision:.1f}% (numerator={fact_tp}, denominator={fact_tp + fact_fp})")
    print(f"    Recall:    {fact_recall:.1f}% (numerator={fact_tp}, denominator={fact_tp + fact_fn})")
    print(f"    Universe: ground-truth facts from 300-doc independent benchmark")
    print(f"    Sample: census (100%)")

    print(f"\n  Events:")
    print(f"    True Positives:  {event_tp}")
    print(f"    False Positives: {event_fp}")
    print(f"    False Negatives: {event_fn}")
    print(f"    Precision: {event_precision:.1f}% (numerator={event_tp}, denominator={event_tp + event_fp})")
    print(f"    Recall:    {event_recall:.1f}% (numerator={event_tp}, denominator={event_tp + event_fn})")
    print(f"    Universe: ground-truth events from 300-doc independent benchmark")
    print(f"    Sample: census (100%)")

    print(f"\n--- Error Taxonomy ---")
    for error, count in error_taxonomy.most_common():
        print(f"  {error:<30} {count:>5}")

    # §9: Adjudicate the 9 V13 disputed events
    print(f"\n--- §9 V13 Disputed Events Adjudication ---")
    v6_event_types = set()
    v13_event_types = set()
    # The 9 events that V13 accepts but V6 rejects are the ones in the current
    # corpus that wouldn't be in the V6-only corpus
    # We can identify them by checking which current events V6 would reject
    from intelligence_core.tests.reliability.event_semantic_gate import validate_event_context as v6_gate
    from intelligence_core.tests.reliability.v13_recall_patterns import validate_event_context_v13

    reps_by_id = store.latest_by_id("representations", "representation_id")
    disputed = []
    for ev in store.iter("events"):
        doc_id = ev.get("document_id", "")
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
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                continue
            doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue

        lang = classify_language(doc_text)
        v6_valid, v6_reason = v6_gate(ev["event_type"], doc_text)
        v13_valid, v13_reason = validate_event_context_v13(ev["event_type"], doc_text, lang)

        if v13_valid and not v6_valid:
            # This is a disputed event — check against ground truth
            gt_for_doc = next((g for g in ground_truth if g["doc_id"] == doc_id), None)
            if gt_for_doc:
                gt_events = set(e["event_type"] for e in gt_for_doc.get("ground_truth_events", []))
                if ev["event_type"] in gt_events:
                    adjudication = "TRUE_RECOVERY"
                else:
                    adjudication = "FALSE_POSITIVE"
            else:
                adjudication = "NOT_IN_BENCHMARK"

            disputed.append({
                "event_id": ev["event_id"][:25],
                "event_type": ev["event_type"],
                "v6_reason": v6_reason[:50],
                "v13_reason": v13_reason[:50],
                "adjudication": adjudication,
            })

    print(f"  Disputed events: {len(disputed)}")
    true_recovery = sum(1 for d in disputed if d["adjudication"] == "TRUE_RECOVERY")
    false_positive = sum(1 for d in disputed if d["adjudication"] == "FALSE_POSITIVE")
    print(f"  TRUE_RECOVERY: {true_recovery}")
    print(f"  FALSE_POSITIVE: {false_positive}")
    for d in disputed:
        print(f"    {d['adjudication']:<20} type={d['event_type']:<30} v6={d['v6_reason']}")

    # Save results
    results = {
        "total_documents": len(selected_docs),
        "total_gt_facts": total_gt_facts,
        "total_gt_events": total_gt_events,
        "fact_tp": fact_tp,
        "fact_fp": fact_fp,
        "fact_fn": fact_fn,
        "event_tp": event_tp,
        "event_fp": event_fp,
        "event_fn": event_fn,
        "fact_precision": round(fact_precision, 1),
        "fact_recall": round(fact_recall, 1),
        "event_precision": round(event_precision, 1),
        "event_recall": round(event_recall, 1),
        "error_taxonomy": dict(error_taxonomy),
        "disputed_events": disputed,
        "ground_truth": [{
            "doc_id": gt["doc_id"],
            "src_id": gt.get("src_id", ""),
            "language": gt.get("language", "unknown"),
            "is_pdf": gt.get("is_pdf", False),
            "gt_facts_count": len(gt.get("ground_truth_facts", [])),
            "gt_events": [e["event_type"] for e in gt.get("ground_truth_events", [])],
        } for gt in ground_truth],
    }

    out_path = Path("intelligence_core/tests/reliability/v14_ground_truth_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return results


if __name__ == "__main__":
    results = run_ground_truth_benchmark()
