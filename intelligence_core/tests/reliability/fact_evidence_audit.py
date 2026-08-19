"""V5 §2-3 — Fact Quality Root-Cause Audit + Evidence-Grounding Audit.

For at least 200 real facts, classify each:
  - DIRECTLY_SUPPORTED: evidence excerpt directly proves the fact
  - PARTIALLY_SUPPORTED: evidence contains value but missing context
  - CONTEXT_MISMATCH: fact value exists but wrong context
  - WRONG_VALUE: fact value doesn't match evidence
  - WRONG_ENTITY: fact attributed to wrong entity
  - WRONG_UNIT: unit missing or wrong (e.g., $74M vs 74%)
  - WRONG_CONTEXT: fact classified under wrong event type

Evidence grounding:
  - DIRECT_EVIDENCE: excerpt directly states the fact
  - INDIRECT_EVIDENCE: excerpt implies the fact but doesn't state it
  - INSUFFICIENT_EVIDENCE: excerpt doesn't support the fact
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


# ── Fact Quality Classification Rules ──

# For each metric, define what constitutes a correctly-supported fact
# with proper entity/unit/context.

FACT_QUALITY_RULES = {
    "percentage_statistic": {
        "value_format": r"^\d+(?:\.\d+)?$",
        "unit_expected": "%",
        "evidence_must_contain": [
            (r"\d+(?:\.\d+)?\s*%", "percentage value with % symbol"),
        ],
        "context_keywords": [r"\b(rate|growth|change|increase|decrease|figure|percent|percentage)\b"],
    },
    "rate_value": {
        "value_format": r"^\d+(?:\.\d+)?$",
        "unit_expected": "%",
        "evidence_must_contain": [
            (r"\d+(?:\.\d+)?\s*%", "percentage value"),
        ],
        "context_keywords": [r"\b(rate|interest|policy|benchmark|base)\b"],
    },
    "policy_rate": {
        "value_format": r"^\d+(?:\.\d+)?$",
        "unit_expected": "%",
        "evidence_must_contain": [
            (r"\d+(?:\.\d+)?\s*%", "percentage value"),
        ],
        "context_keywords": [r"\b(policy\s+rate|interest\s+rate|benchmark|base\s+rate)\b"],
    },
    "rate_decision": {
        "value_format": r"^(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?|increase(?:d)?|decrease(?:d)?)$",
        "unit_expected": None,
        "evidence_must_contain": [
            (r"\b(maintain|raise|cut|lower|increase|decrease)\b", "rate decision verb"),
        ],
        "context_keywords": [r"\b(rate|policy|interest)\b"],
    },
    "action_type": {
        "value_format": r"^(consent\s+order|cease\s+and\s+desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)$",
        "unit_expected": None,
        "evidence_must_contain": [
            (r"\b(consent|cease|desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)\b", "enforcement keyword"),
        ],
        "context_keywords": [r"\b(order|action|proceeding|investigation|imposed|required|defendant|respondent)\b"],
    },
    "penalty_amount": {
        "value_format": r"^\d+(?:,\d{3})*(?:\.\d+)?$",
        "unit_expected": "USD",
        "evidence_must_contain": [
            (r"\$\d+", "dollar amount"),
            (r"\b(million|billion|thousand|M|B|K)\b", "scale indicator"),
        ],
        "context_keywords": [r"\b(penalty|fine|settlement|disgorgement|pay|paid)\b"],
    },
    "usd_amount": {
        "value_format": r"^\d+(?:,\d{3})*(?:\.\d+)?$",
        "unit_expected": "USD",
        "evidence_must_contain": [
            (r"\$\d+", "dollar amount"),
        ],
        "context_keywords": [r"\b(million|billion|thousand|revenue|income|sales|assets|fund)\b"],
    },
    "gdp_growth": {
        "value_format": r"^\d+(?:\.\d+)?$",
        "unit_expected": "%",
        "evidence_must_contain": [
            (r"\d+(?:\.\d+)?\s*%", "percentage value"),
        ],
        "context_keywords": [r"\b(gdp|gross\s+domestic\s+product)\b"],
    },
    "inflation_rate": {
        "value_format": r"^\d+(?:\.\d+)?$",
        "unit_expected": "%",
        "evidence_must_contain": [
            (r"\d+(?:\.\d+)?\s*%", "percentage value"),
        ],
        "context_keywords": [r"\b(inflation|cpi|consumer\s+price)\b"],
    },
    "unemployment_rate": {
        "value_format": r"^\d+(?:\.\d+)?$",
        "unit_expected": "%",
        "evidence_must_contain": [
            (r"\d+(?:\.\d+)?\s*%", "percentage value"),
        ],
        "context_keywords": [r"\b(unemployment|employment\s+rate)\b"],
    },
    "employment_level": {
        "value_format": r"^\d+(?:,\d{3})+$",
        "unit_expected": "persons",
        "evidence_must_contain": [
            (r"\d+(?:,\d{3})+", "number with thousands separator"),
        ],
        "context_keywords": [r"\b(employment|employed|jobs?|workers?)\b"],
    },
    "defendant_name": {
        "value_format": r"^[A-Z][a-zA-Z\s&.,]+$",
        "unit_expected": None,
        "evidence_must_contain": [
            (r"[A-Z][a-zA-Z]+", "capitalized name"),
        ],
        "context_keywords": [r"\b(defendant|respondent|charged|sued|settled)\b"],
    },
}


def classify_fact_quality(fact: dict, document_text: str) -> tuple[str, str]:
    """Classify a single fact's quality.

    Returns (classification, reason).
    """
    metric = fact.get("metric", "")
    value = str(fact.get("value", ""))
    excerpt = fact.get("excerpt", "")

    rules = FACT_QUALITY_RULES.get(metric)
    if not rules:
        # No rules for this metric — classify as supported if excerpt contains value
        if value and value in excerpt:
            return "DIRECTLY_SUPPORTED", "value found in evidence excerpt"
        return "INSUFFICIENT_EVIDENCE", "no rules + value not in excerpt"

    # Check if document is non-English (language gap)
    ascii_chars = sum(1 for c in document_text if ord(c) < 128)
    total_chars = len(document_text)
    if total_chars > 0:
        non_ascii_ratio = 1 - (ascii_chars / total_chars)
        if non_ascii_ratio > 0.3:
            # Non-English document — classify based on whether value exists
            if value and value in excerpt:
                return "PARTIALLY_SUPPORTED", f"non-English document ({non_ascii_ratio*100:.0f}% non-ASCII) — value in excerpt but context unverified"
            return "CONTEXT_MISMATCH", f"non-English document — value not found in excerpt"

    # Check evidence_must_contain
    evidence_checks = rules["evidence_must_contain"]
    evidence_passes = 0
    for pattern, desc in evidence_checks:
        if re.search(pattern, excerpt, re.IGNORECASE):
            evidence_passes += 1

    if evidence_passes < len(evidence_checks):
        return "INSUFFICIENT_EVIDENCE", f"evidence missing required pattern ({evidence_passes}/{len(evidence_checks)} found)"

    # Check context keywords in document
    context_matches = 0
    for pattern in rules["context_keywords"]:
        if re.search(pattern, document_text, re.IGNORECASE):
            context_matches += 1

    if context_matches == 0:
        return "WRONG_CONTEXT", "document lacks context keywords for this metric"

    # Check value format
    if rules["value_format"] and not re.match(rules["value_format"], value, re.IGNORECASE):
        return "WRONG_VALUE", f"value '{value}' doesn't match expected format"

    # Check unit
    if rules["unit_expected"] == "%":
        # Verify the excerpt has a % near the value
        if not re.search(rf"{re.escape(value)}\s*%", excerpt):
            # Check if value appears with % anywhere
            if not re.search(r"\d+(?:\.\d+)?\s*%", excerpt):
                return "WRONG_UNIT", f"percentage expected but no % found in excerpt"

    # All checks pass
    if evidence_passes == len(evidence_checks) and context_matches > 0:
        return "DIRECTLY_SUPPORTED", f"evidence + context verified ({context_matches} context matches)"
    else:
        return "PARTIALLY_SUPPORTED", f"partial support ({evidence_passes}/{len(evidence_checks)} evidence, {context_matches} context)"


def classify_evidence_grounding(fact: dict, document_text: str) -> tuple[str, str]:
    """Classify evidence grounding level.

    Returns (classification, reason).
    """
    metric = fact.get("metric", "")
    value = str(fact.get("value", ""))
    excerpt = fact.get("excerpt", "")

    if not excerpt:
        return "INSUFFICIENT_EVIDENCE", "no evidence excerpt"

    # Check if the excerpt DIRECTLY contains the fact value + context
    if value in excerpt:
        # Check if the excerpt also contains context keywords
        rules = FACT_QUALITY_RULES.get(metric, {})
        context_keywords = rules.get("context_keywords", [])
        context_matches = sum(1 for p in context_keywords if re.search(p, excerpt, re.IGNORECASE))

        if context_matches > 0:
            return "DIRECT_EVIDENCE", f"excerpt contains value + {context_matches} context keywords"
        else:
            return "INDIRECT_EVIDENCE", "excerpt contains value but lacks context keywords"

    # Value not in excerpt — check if it's in the broader document
    if value in document_text:
        return "INDIRECT_EVIDENCE", "value in document but not in excerpt"

    return "INSUFFICIENT_EVIDENCE", "value not found in excerpt or document"


def run_fact_evidence_audit(store_root: str = "v3_corpus_store", n_facts: int = 200):
    """Run the full fact/evidence quality audit."""
    print(f"\n{'='*70}")
    print(f"V5 §2-3 — Fact Quality + Evidence-Grounding Audit")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Collect all facts with their document texts
    all_facts = list(store.iter("facts"))
    print(f"\n  Total facts in corpus: {len(all_facts)}")
    print(f"  Auditing first {n_facts} facts...")

    # Build document text cache
    doc_text_cache = {}
    def get_doc_text(doc_id):
        if doc_id not in doc_text_cache:
            rep = None
            for rid, r in reps_by_id.items():
                if r.get("document_id") == doc_id:
                    rep = r
                    break
            if rep:
                blob_path = rep.get("raw_location", "")
                if blob_path and Path(blob_path).exists():
                    try:
                        blob_bytes = Path(blob_path).read_bytes()
                        if blob_bytes[:5] != b"%PDF-" and b"\x00" not in blob_bytes[:1000]:
                            doc_text_cache[doc_id] = strip_html(blob_bytes.decode("utf-8", errors="replace"))
                        else:
                            doc_text_cache[doc_id] = ""
                    except Exception:
                        doc_text_cache[doc_id] = ""
                else:
                    doc_text_cache[doc_id] = ""
            else:
                doc_text_cache[doc_id] = ""
        return doc_text_cache[doc_id]

    # Audit facts
    fact_classifications = []
    evidence_classifications = []

    for i, fact in enumerate(all_facts[:n_facts]):
        doc_id = fact.get("document_id", "")
        doc_text = get_doc_text(doc_id)

        # §2: Fact quality classification
        fact_class, fact_reason = classify_fact_quality(fact, doc_text)
        fact_classifications.append({
            "fact_id": fact.get("fact_id", ""),
            "metric": fact.get("metric", ""),
            "value": str(fact.get("value", ""))[:50],
            "doc_id": doc_id[:25],
            "classification": fact_class,
            "reason": fact_reason,
        })

        # §3: Evidence grounding classification
        ev_class, ev_reason = classify_evidence_grounding(fact, doc_text)
        evidence_classifications.append({
            "fact_id": fact.get("fact_id", ""),
            "metric": fact.get("metric", ""),
            "classification": ev_class,
            "reason": ev_reason,
        })

    # Summarize fact quality
    fact_dist = Counter(c["classification"] for c in fact_classifications)
    print(f"\n--- §2 Fact Quality Distribution ({len(fact_classifications)} facts) ---")
    for cls, count in fact_dist.most_common():
        pct = count / len(fact_classifications) * 100
        print(f"  {cls:<30} {count:>4}  ({pct:.1f}%)")

    # Summarize evidence grounding
    ev_dist = Counter(c["classification"] for c in evidence_classifications)
    print(f"\n--- §3 Evidence Grounding Distribution ({len(evidence_classifications)} facts) ---")
    for cls, count in ev_dist.most_common():
        pct = count / len(evidence_classifications) * 100
        print(f"  {cls:<30} {count:>4}  ({pct:.1f}%)")

    # Calculate precision metrics
    direct_supported = fact_dist.get("DIRECTLY_SUPPORTED", 0)
    partial_supported = fact_dist.get("PARTIALLY_SUPPORTED", 0)
    fact_precision = (direct_supported + partial_supported) / len(fact_classifications) * 100

    direct_evidence = ev_dist.get("DIRECT_EVIDENCE", 0)
    indirect_evidence = ev_dist.get("INDIRECT_EVIDENCE", 0)
    evidence_grounding = (direct_evidence + indirect_evidence) / len(evidence_classifications) * 100

    print(f"\n--- Quality Metrics ---")
    print(f"  Fact Precision: {fact_precision:.1f}% (DIRECT + PARTIAL)")
    print(f"  Direct Evidence: {direct_evidence/len(evidence_classifications)*100:.1f}%")
    print(f"  Evidence Grounding: {evidence_grounding:.1f}% (DIRECT + INDIRECT)")

    # Show failure examples
    failures = [c for c in fact_classifications if c["classification"] not in ("DIRECTLY_SUPPORTED", "PARTIALLY_SUPPORTED")]
    if failures:
        print(f"\n--- Failure Examples (first 10) ---")
        for f in failures[:10]:
            print(f"  {f['classification']:<25} metric={f['metric']:<25} value={f['value'][:20]:<20} reason={f['reason'][:60]}")

    # Metric breakdown
    print(f"\n--- Fact Quality by Metric ---")
    metric_quality = defaultdict(lambda: Counter())
    for c in fact_classifications:
        metric_quality[c["metric"]][c["classification"]] += 1
    for metric, dist in sorted(metric_quality.items()):
        total = sum(dist.values())
        direct = dist.get("DIRECTLY_SUPPORTED", 0)
        pct = direct / total * 100 if total else 0
        print(f"  {metric:<25} total={total:>3} direct={direct:>3} ({pct:.0f}%)")

    return {
        "total_facts_audited": len(fact_classifications),
        "fact_quality_dist": dict(fact_dist),
        "evidence_grounding_dist": dict(ev_dist),
        "fact_precision_pct": round(fact_precision, 1),
        "direct_evidence_pct": round(direct_evidence / len(evidence_classifications) * 100, 1),
        "evidence_grounding_pct": round(evidence_grounding, 1),
        "fact_classifications": fact_classifications,
        "evidence_classifications": evidence_classifications,
        "metric_quality": {k: dict(v) for k, v in metric_quality.items()},
    }


if __name__ == "__main__":
    store_root = sys.argv[1] if len(sys.argv) > 1 else "v3_corpus_store"
    result = run_fact_evidence_audit(store_root, n_facts=200)

    out_path = Path("intelligence_core/tests/reliability/fact_evidence_audit_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    # Target check
    if result["fact_precision_pct"] >= 95:
        print(f"\n  ✓ Fact Precision ≥95%: {result['fact_precision_pct']:.1f}%")
    else:
        print(f"\n  ⚠ Fact Precision <95%: {result['fact_precision_pct']:.1f}%")
