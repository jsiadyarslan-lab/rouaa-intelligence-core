"""V7 §6-8 — Direct Evidence Gap Closure.

Implement improved evidence extraction that produces DIRECT evidence by:
1. Sentence-aware extraction (already done in V5)
2. Paragraph-aware extraction (new)
3. Context-aware excerpt expansion (new)

The goal: the evidence excerpt itself must contain enough info to prove:
  - What is the value?
  - What metric does it represent?
  - Which entity does it belong to?
  - What unit applies?
  - What context applies?
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html


# Context keywords that should be in the evidence excerpt for DIRECT classification
METRIC_CONTEXT_KEYWORDS = {
    "percentage_statistic": [
        r"\b(rate|growth|change|increase|decrease|figure|percent|percentage|"
        r"statistic|estimate|index|indicator)\b"
    ],
    "rate_value": [
        r"\b(rate|interest|policy|benchmark|base\s+rate)\b"
    ],
    "policy_rate": [
        r"\b(policy\s+rate|interest\s+rate|benchmark|base\s+rate)\b"
    ],
    "rate_decision": [
        r"\b(maintain|raise|cut|lower|increase|decrease)\b.*\b(rate|policy|interest)\b"
    ],
    "action_type": [
        r"\b(consent|cease|desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|"
        r"enforcement|order|defendant|respondent)\b"
    ],
    "penalty_amount": [
        r"\b(penalty|fine|settlement|disgorgement|pay|paid|imposed|assessed)\b"
    ],
    "usd_amount": [
        r"\b(million|billion|thousand|revenue|income|sales|assets|fund|"
        r"penalty|fine|settlement)\b"
    ],
    "gdp_growth": [
        r"\b(gdp|gross\s+domestic\s+product|economic\s+growth)\b"
    ],
    "inflation_rate": [
        r"\b(inflation|cpi|consumer\s+price)\b"
    ],
    "unemployment_rate": [
        r"\b(unemployment|employment\s+rate|labor\s+force)\b"
    ],
    "employment_level": [
        r"\b(employment|employed|jobs?|workers?|labor)\b"
    ],
    "defendant_name": [
        r"\b(defendant|respondent|charged|sued|settled|agreed)\b"
    ],
    "trade_balance": [
        r"\b(trade|export|import|balance|deficit|surplus)\b"
    ],
    "revenue": [
        r"\b(revenue|sales|income|earnings)\b"
    ],
}


def expand_evidence_to_direct(value: str, metric: str, current_excerpt: str,
                               full_document_text: str, match_start: int = 0,
                               match_end: int = 0) -> tuple[str, bool]:
    """Expand evidence excerpt until it contains direct context.

    Returns (expanded_excerpt, is_direct).
    """
    if not current_excerpt:
        return current_excerpt, False

    # Check if current excerpt is already direct
    context_patterns = METRIC_CONTEXT_KEYWORDS.get(metric, [])
    if not context_patterns:
        return current_excerpt, True  # No context requirements

    # Check current excerpt
    for pattern in context_patterns:
        if re.search(pattern, current_excerpt, re.IGNORECASE):
            return current_excerpt, True  # Already has context

    # Need to expand — find the value position in the full document
    if not full_document_text:
        return current_excerpt, False

    # Find the value in the document
    value_pos = full_document_text.find(value)
    if value_pos < 0:
        return current_excerpt, False

    # Try expanding: sentence → paragraph → larger window
    # Step 1: Try the full paragraph containing the value
    # Find paragraph boundaries (double newlines or sentence boundaries)
    para_start = value_pos
    para_end = value_pos + len(value)

    # Expand backward to find paragraph start
    while para_start > 0:
        if full_document_text[para_start - 1:para_start + 1] == "\n\n":
            break
        if full_document_text[para_start - 1] == "." and para_start > 2:
            # Check if this is a sentence boundary
            if full_document_text[para_start:para_start + 1].isspace():
                break
        para_start -= 1
        if value_pos - para_start > 500:  # cap at 500 chars
            break

    # Expand forward to find paragraph end
    while para_end < len(full_document_text):
        if full_document_text[para_end:para_end + 2] == "\n\n":
            break
        if full_document_text[para_end] == "." and para_end + 1 < len(full_document_text):
            if full_document_text[para_end + 1:para_end + 2].isspace():
                para_end += 1
                break
        para_end += 1
        if para_end - value_pos > 500:
            break

    expanded = full_document_text[para_start:para_end].strip()

    # Check if expanded excerpt has context
    for pattern in context_patterns:
        if re.search(pattern, expanded, re.IGNORECASE):
            return expanded, True

    # Step 2: Try even larger window (±500 chars)
    large_start = max(0, value_pos - 500)
    large_end = min(len(full_document_text), value_pos + len(value) + 500)
    large_excerpt = full_document_text[large_start:large_end].strip()

    for pattern in context_patterns:
        if re.search(pattern, large_excerpt, re.IGNORECASE):
            return large_excerpt, True

    # Could not find context — return the best we have
    return expanded, False


def re_classify_evidence_with_expansion(fact: dict, document_text: str) -> tuple[str, str, str]:
    """Re-classify evidence with expansion support.

    Returns (classification, expanded_excerpt, reason).
    """
    metric = fact.get("metric", "")
    value = str(fact.get("value", ""))
    excerpt = fact.get("excerpt", "")

    if not excerpt:
        return "INSUFFICIENT_EVIDENCE", excerpt, "no evidence excerpt"

    if not value:
        return "INSUFFICIENT_EVIDENCE", excerpt, "no fact value"

    # Check if value is in excerpt
    if value not in excerpt:
        # Value not in excerpt — check if in document
        if value in document_text:
            # Try to expand
            expanded, is_direct = expand_evidence_to_direct(
                value, metric, excerpt, document_text
            )
            if is_direct:
                return "DIRECT_EVIDENCE", expanded, "expanded to find direct context"
            return "INDIRECT_EVIDENCE", expanded, "value in document, expanded but still indirect"
        return "INSUFFICIENT_EVIDENCE", excerpt, "value not found in excerpt or document"

    # Value IS in excerpt — check if context keywords are present
    context_patterns = METRIC_CONTEXT_KEYWORDS.get(metric, [])
    if not context_patterns:
        return "DIRECT_EVIDENCE", excerpt, "no context requirements for metric"

    for pattern in context_patterns:
        if re.search(pattern, excerpt, re.IGNORECASE):
            return "DIRECT_EVIDENCE", excerpt, "excerpt contains value + context"

    # Value in excerpt but no context — try expanding
    expanded, is_direct = expand_evidence_to_direct(
        value, metric, excerpt, document_text
    )
    if is_direct:
        return "DIRECT_EVIDENCE", expanded, "expanded excerpt now contains context"
    return "INDIRECT_EVIDENCE", expanded, "value in excerpt but context only in broader document"


def audit_direct_evidence_with_expansion(store_root: str = "v3_corpus_store", n_facts=300):
    """Audit direct evidence with the expansion capability."""
    print(f"\n{'='*70}")
    print(f"V7 §6-8 — Direct Evidence Gap Closure")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    all_facts = list(store.iter("facts"))
    print(f"\n  Total facts: {len(all_facts)}")
    print(f"  Auditing first {min(n_facts, len(all_facts))} facts with evidence expansion...")

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
        return doc_text_cache[doc_id]

    # Audit with expansion
    from collections import Counter
    old_dist = Counter()
    new_dist = Counter()
    expanded_count = 0
    improved_count = 0

    for fact in all_facts[:n_facts]:
        doc_id = fact.get("document_id", "")
        doc_text = get_doc_text(doc_id)

        # Old classification (without expansion)
        value = str(fact.get("value", ""))
        excerpt = fact.get("excerpt", "")
        context_patterns = METRIC_CONTEXT_KEYWORDS.get(fact.get("metric", ""), [])
        if value in excerpt:
            has_context = any(re.search(p, excerpt, re.IGNORECASE) for p in context_patterns)
            if has_context or not context_patterns:
                old_dist["DIRECT_EVIDENCE"] += 1
            else:
                old_dist["INDIRECT_EVIDENCE"] += 1
        elif value in doc_text:
            old_dist["INDIRECT_EVIDENCE"] += 1
        else:
            old_dist["INSUFFICIENT_EVIDENCE"] += 1

        # New classification (with expansion)
        new_class, expanded_excerpt, reason = re_classify_evidence_with_expansion(fact, doc_text)
        new_dist[new_class] += 1

        if expanded_excerpt != excerpt:
            expanded_count += 1
        if new_class == "DIRECT_EVIDENCE" and old_dist.get("DIRECT_EVIDENCE", 0) < new_dist.get("DIRECT_EVIDENCE", 0):
            improved_count += 1

    total = min(n_facts, len(all_facts))
    old_direct = old_dist.get("DIRECT_EVIDENCE", 0)
    new_direct = new_dist.get("DIRECT_EVIDENCE", 0)
    old_direct_pct = old_direct / total * 100
    new_direct_pct = new_direct / total * 100

    print(f"\n--- Evidence Classification Comparison ({total} facts) ---")
    print(f"  {'Classification':<25} {'Before Expansion':>15} {'After Expansion':>15}")
    print(f"  {'-'*55}")
    for cls in ["DIRECT_EVIDENCE", "INDIRECT_EVIDENCE", "INSUFFICIENT_EVIDENCE"]:
        old_count = old_dist.get(cls, 0)
        new_count = new_dist.get(cls, 0)
        print(f"  {cls:<25} {old_count:>7} ({old_count/total*100:.1f}%)  {new_count:>7} ({new_count/total*100:.1f}%)")

    print(f"\n  Direct Evidence: {old_direct_pct:.1f}% → {new_direct_pct:.1f}% (improvement: +{new_direct_pct - old_direct_pct:.1f}%)")
    print(f"  Expanded excerpts: {expanded_count}")
    print(f"  Target: Direct Evidence ≥90%")

    return {
        "total_audited": total,
        "old_direct_pct": round(old_direct_pct, 1),
        "new_direct_pct": round(new_direct_pct, 1),
        "improvement_pp": round(new_direct_pct - old_direct_pct, 1),
        "old_dist": dict(old_dist),
        "new_dist": dict(new_dist),
    }


if __name__ == "__main__":
    result = audit_direct_evidence_with_expansion(n_facts=300)
    out_path = Path("intelligence_core/tests/reliability/direct_evidence_expansion_results.json")
    with open(out_path, "w") as f:
        import json
        json.dump(result, f, indent=2)
    print(f"\n  Results saved to: {out_path}")
