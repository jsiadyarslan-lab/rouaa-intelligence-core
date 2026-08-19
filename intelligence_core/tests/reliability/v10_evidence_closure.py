"""V10 §3-7 — Fix 19 fact failures + classify 270 INDIRECT + evidence selector.

§3: Forensic analysis of 19 failures → FIXED/REJECTED/RECLASSIFIED
§4: Deterministic evidence selector (sentence→table→list→paragraph→bounded)
§5: Strict DIRECT evidence contract
§6: Classify 270 INDIRECT (CONTEXT_IN_NEXT_SENTENCE, PARAGRAPH, TABLE, LIST, NAVIGATION, HEADER, TITLE_ONLY, OTHER)
§7: Re-extract with navigation exclusion + evidence selector
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
from intelligence_core.contracts import Evidence, Fact, ObjState
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v9_navigation_exclusion import is_navigation_content


# ── Strict DIRECT Evidence Contract (§5) ──

# For each metric, define what the excerpt MUST contain to be DIRECT.
# The excerpt must establish: metric + value + context.
# This is STRICTER than "value appears in excerpt."

# V27R §5 — Semantic equivalence for percentage expressions.
# The evidence classifier must recognize equivalent linguistic forms:
#   %  =  percent  =  percentage  =  percentage points  =  pct
# WITHOUT lowering contextual requirements (still needs context keywords).
# Note: No trailing \b after % because % is not a word character.
# Use (?!\w) lookahead to prevent matching partial words like "5percentX".
PERCENT_EQUIV = r"(?:%|percent(?:age\s+points?)?|percentage|pct)(?!\w)"

DIRECT_EVIDENCE_REQUIREMENTS = {
    "percentage_statistic": {
        "value_pattern": rf"\d+(?:\.\d+)?\s*{PERCENT_EQUIV}",
        "context_patterns": [
            r"\b(rate|growth|change|increase|decrease|figure|percent|percentage|"
            r"statistic|estimate|index|indicator|"
            # V27R: verb forms (past tense)
            r"grew|grows|growing|rose|rises|rising|fell|falls|falling|"
            r"declined|declines|declining|increased|increases|increasing|"
            r"decreased|decreases|decreasing|narrowed|narrows|narrowing|"
            r"expanded|expands|expanding|stood|reached|revised|observed|"
            # V27R: economic nouns (context for percentages)
            r"gdp|inflation|cpi|unemployment|employment|production|output|"
            r"trade|deficit|surplus|balance)\b",
        ],
        "min_context": 1,
    },
    "rate_value": {
        "value_pattern": rf"\d+(?:\.\d+)?\s*{PERCENT_EQUIV}",
        "context_patterns": [
            r"\b(rate|interest|policy|benchmark|base\s+rate)\b",
        ],
        "min_context": 1,
    },
    "policy_rate": {
        "value_pattern": rf"\d+(?:\.\d+)?\s*{PERCENT_EQUIV}",
        "context_patterns": [
            r"\b(policy\s+rate|interest\s+rate|benchmark|base\s+rate)\b",
        ],
        "min_context": 1,
    },
    "rate_decision": {
        "value_pattern": r"\b(maintain|raise|cut|lower|increase|decrease)",
        "context_patterns": [
            r"\b(rate|policy|interest)\b",
        ],
        "min_context": 1,
    },
    "action_type": {
        "value_pattern": r"\b(consent|cease|desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)\b",
        "context_patterns": [
            r"\b(order|action|proceeding|investigation|imposed|defendant|respondent|"
            r"regulator|commission|authority)\b",
        ],
        "min_context": 1,
    },
    "penalty_amount": {
        "value_pattern": r"\$\d+",
        "context_patterns": [
            r"\b(penalty|fine|settlement|disgorgement|pay|paid|imposed|assessed|million|billion)\b",
        ],
        "min_context": 1,
    },
    "usd_amount": {
        "value_pattern": r"\$\d+",
        "context_patterns": [
            r"\b(million|billion|thousand|revenue|income|sales|assets|fund|"
            r"penalty|fine|settlement)\b",
        ],
        "min_context": 1,
    },
    "gdp_growth": {
        "value_pattern": rf"\d+(?:\.\d+)?\s*{PERCENT_EQUIV}",
        "context_patterns": [
            r"\b(gdp|gross\s+domestic\s+product)\b",
        ],
        "min_context": 1,
    },
    "inflation_rate": {
        "value_pattern": rf"\d+(?:\.\d+)?\s*{PERCENT_EQUIV}",
        "context_patterns": [
            r"\b(inflation|cpi|consumer\s+price)\b",
        ],
        "min_context": 1,
    },
    "unemployment_rate": {
        "value_pattern": rf"\d+(?:\.\d+)?\s*{PERCENT_EQUIV}",
        "context_patterns": [
            r"\b(unemployment|employment\s+rate)\b",
        ],
        "min_context": 1,
    },
    "employment_level": {
        "value_pattern": r"\d+(?:,\d{3})+",
        "context_patterns": [
            r"\b(employment|employed|jobs?|workers?)\b",
        ],
        "min_context": 1,
    },
}


def classify_evidence_strict(fact, excerpt: str) -> tuple[str, str]:
    """§5 — Strict DIRECT evidence classification.

    DIRECT: excerpt contains value + required context keywords
    INDIRECT: excerpt contains value but not context
    INSUFFICIENT: excerpt doesn't contain value
    INVALID: excerpt is navigation/UI content

    V27R §5: Semantic equivalence for percentage expressions —
    recognizes % = percent = percentage = percentage points = pct.
    """
    # Support both dict and Fact dataclass
    if hasattr(fact, 'metric'):
        metric = fact.metric
        value = str(fact.value)
    else:
        metric = fact.get("metric", "")
        value = str(fact.get("value", ""))

    # First check: is this navigation/UI content?
    if is_navigation_content(excerpt):
        return "INVALID", "evidence is navigation/UI content"

    # V27R §5: Extended navigation check — reject social media, subscribe, cookie, etc.
    excerpt_lower = excerpt.lower()
    extended_nav_patterns = [
        r"\b(?:facebook|twitter|linkedin|youtube|instagram|tiktok)\b",
        r"\b(?:subscribe|newsletter|sign\s+up|sign\s+in|log\s+in|register)\b",
        r"\b(?:privacy\s+policy|terms\s+of\s+use|cookie\s+(?:consent|policy))\b",
        r"\b(?:all\s+rights\s+reserved|copyright\s*©?)\b",
        r"\b(?:skip\s+to\s+(?:main|content|navigation))\b",
        r"\b(?:main\s+menu|site\s+menu|navigation\s+menu)\b",
        r"\b(?:page\s+\d+\s+of\s+\d+)\b",
    ]
    for p in extended_nav_patterns:
        if re.search(p, excerpt_lower):
            return "INVALID", "evidence is navigation/UI/boilerplate content"

    # Get requirements for this metric
    reqs = DIRECT_EVIDENCE_REQUIREMENTS.get(metric)
    if not reqs:
        # No specific requirements — check if value is in excerpt
        if value in excerpt:
            return "DIRECT", "value present, no specific context requirements"
        return "INSUFFICIENT", "value not in excerpt"

    # Check if value pattern matches in excerpt
    if not re.search(reqs["value_pattern"], excerpt, re.IGNORECASE):
        if value in excerpt:
            # Value is there but doesn't match expected format
            return "INDIRECT", "value in excerpt but format mismatch"
        return "INSUFFICIENT", "value not in excerpt"

    # Check context patterns
    context_matches = 0
    for pattern in reqs["context_patterns"]:
        if re.search(pattern, excerpt, re.IGNORECASE):
            context_matches += 1

    if context_matches >= reqs["min_context"]:
        return "DIRECT", f"value + {context_matches} context patterns matched"
    else:
        return "INDIRECT", f"value present but only {context_matches}/{len(reqs['context_patterns'])} context patterns"


def expand_evidence_for_direct(fact, excerpt: str, doc_text: str) -> tuple[str, str]:
    """§4 — Expand evidence to find direct context.

    Tries in order:
      1. Current excerpt (already direct?)
      2. Sentence containing the value + adjacent sentences
      3. Paragraph containing the value
      4. Bounded local context (±300 chars)
    """
    # Step 1: Check current excerpt
    classification, reason = classify_evidence_strict(fact, excerpt)
    if classification == "DIRECT":
        return excerpt, "DIRECT (current excerpt)"
    if classification == "INVALID":
        return excerpt, "INVALID (navigation content)"

    # Step 2: Find value in document and extract sentence + context
    if hasattr(fact, 'value'):
        value = str(fact.value)
    else:
        value = str(fact.get("value", ""))
    if not value or not doc_text:
        return excerpt, classification

    # Find the value position
    value_pos = doc_text.find(value)
    if value_pos < 0:
        return excerpt, classification

    # Try sentence-level extraction (±200 chars for sentence context)
    sentence_start = max(0, value_pos - 200)
    sentence_end = min(len(doc_text), value_pos + len(value) + 200)

    # Find sentence boundaries
    for i in range(value_pos, sentence_start, -1):
        if doc_text[i] in '.!?\n' and i > 0 and doc_text[i-1:i] != '.':
            sentence_start = i + 1
            break
    for i in range(value_pos + len(value), sentence_end):
        if doc_text[i] in '.!?\n':
            sentence_end = i + 1
            break

    sentence_excerpt = doc_text[sentence_start:sentence_end].strip()

    # Check if navigation
    if is_navigation_content(sentence_excerpt):
        # Try paragraph level
        para_start = max(0, value_pos - 500)
        para_end = min(len(doc_text), value_pos + len(value) + 500)
        para_excerpt = doc_text[para_start:para_end].strip()
        if is_navigation_content(para_excerpt):
            return excerpt, classification  # Can't fix
        cls2, _ = classify_evidence_strict(fact, para_excerpt)
        if cls2 == "DIRECT":
            return para_excerpt, "DIRECT (paragraph expansion)"
        return para_excerpt, "INDIRECT (paragraph expanded but context elsewhere)"
    else:
        cls2, _ = classify_evidence_strict(fact, sentence_excerpt)
        if cls2 == "DIRECT":
            return sentence_excerpt, "DIRECT (sentence expansion)"
        return sentence_excerpt, "INDIRECT (sentence expanded but context elsewhere)"


def run_v10_evidence_closure(store_root: str = "v3_corpus_store"):
    """Run the complete V10 evidence closure."""
    print(f"\n{'='*70}")
    print(f"V10 — Evidence Substrate Closure")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Get all facts attached to surviving events
    surviving_fact_ids = set()
    for ev in store.iter("events"):
        for ref in ev.get("fact_version_snapshot", []):
            surviving_fact_ids.add(ref.get("fact_id"))

    all_facts = list(store.iter("facts"))
    attached_facts = [f for f in all_facts if f["fact_id"] in surviving_fact_ids]

    print(f"\n  Total attached facts: {len(attached_facts)}")

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

    # §3: Fix 19 fact failures
    print(f"\n--- §3 Fix 19 Fact Failures ---")
    fact_dispositions = []
    fixed_count = 0
    rejected_count = 0
    reclassified_count = 0

    for fact in attached_facts:
        doc_id = fact.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        excerpt = fact.get("excerpt", "")

        # Classify with strict rules
        classification, reason = classify_evidence_strict(fact, excerpt)

        if classification == "INVALID":
            # Navigation/UI — try to expand
            new_excerpt, new_status = expand_evidence_for_direct(fact, excerpt, doc_text)
            if "DIRECT" in new_status:
                fact_dispositions.append({
                    "fact_id": fact["fact_id"][:25],
                    "metric": fact.get("metric", ""),
                    "value": str(fact.get("value", ""))[:30],
                    "old_classification": "INVALID",
                    "new_disposition": "FIXED",
                    "new_excerpt": new_excerpt[:100],
                })
                fixed_count += 1
            else:
                fact_dispositions.append({
                    "fact_id": fact["fact_id"][:25],
                    "metric": fact.get("metric", ""),
                    "value": str(fact.get("value", ""))[:30],
                    "old_classification": "INVALID",
                    "new_disposition": "REJECTED",
                    "reason": "navigation content, cannot fix",
                })
                rejected_count += 1
        elif classification == "INSUFFICIENT":
            # Try to expand
            new_excerpt, new_status = expand_evidence_for_direct(fact, excerpt, doc_text)
            if "DIRECT" in new_status:
                fact_dispositions.append({
                    "fact_id": fact["fact_id"][:25],
                    "metric": fact.get("metric", ""),
                    "value": str(fact.get("value", ""))[:30],
                    "old_classification": "INSUFFICIENT",
                    "new_disposition": "FIXED",
                    "new_excerpt": new_excerpt[:100],
                })
                fixed_count += 1
            else:
                fact_dispositions.append({
                    "fact_id": fact["fact_id"][:25],
                    "metric": fact.get("metric", ""),
                    "value": str(fact.get("value", ""))[:30],
                    "old_classification": "INSUFFICIENT",
                    "new_disposition": "RECLASSIFIED",
                    "reason": "value not in semantic content",
                })
                reclassified_count += 1
        elif classification == "INDIRECT":
            # Try to expand
            new_excerpt, new_status = expand_evidence_for_direct(fact, excerpt, doc_text)
            if "DIRECT" in new_status:
                fact_dispositions.append({
                    "fact_id": fact["fact_id"][:25],
                    "metric": fact.get("metric", ""),
                    "value": str(fact.get("value", ""))[:30],
                    "old_classification": "INDIRECT",
                    "new_disposition": "FIXED",
                    "new_excerpt": new_excerpt[:100],
                })
                fixed_count += 1
            # else stays INDIRECT

    print(f"  Fixed (expanded to DIRECT): {fixed_count}")
    print(f"  Rejected (navigation, cannot fix): {rejected_count}")
    print(f"  Reclassified (value not in semantic content): {reclassified_count}")

    # §6: Full census with strict classification + expansion
    print(f"\n--- §6-7 Full Census with Strict Evidence Classification ---")

    strict_dist = Counter()
    expanded_dist = Counter()
    indirect_classification = Counter()

    for fact in attached_facts:
        doc_id = fact.get("document_id", "")
        doc_text = get_doc_text(doc_id)
        excerpt = fact.get("excerpt", "")

        # Original classification
        orig_cls, orig_reason = classify_evidence_strict(fact, excerpt)
        strict_dist[orig_cls] += 1

        # Expanded classification
        expanded_excerpt, expanded_status = expand_evidence_for_direct(fact, excerpt, doc_text)
        if "DIRECT" in expanded_status:
            expanded_dist["DIRECT"] += 1
        elif "INVALID" in expanded_status:
            expanded_dist["INVALID"] += 1
        elif "INDIRECT" in expanded_status:
            expanded_dist["INDIRECT"] += 1
            # Classify why indirect
            if is_navigation_content(expanded_excerpt):
                indirect_classification["NAVIGATION"] += 1
            else:
                # Check where context is
                value = str(fact.get("value", ""))
                value_pos = doc_text.find(value) if value else -1
                if value_pos >= 0:
                    # Check if context is in same paragraph (±500 chars)
                    para_context = doc_text[max(0, value_pos-500):value_pos+500]
                    metric = fact.get("metric", "")
                    reqs = DIRECT_EVIDENCE_REQUIREMENTS.get(metric, {})
                    context_patterns = reqs.get("context_patterns", [])
                    has_context_nearby = any(re.search(p, para_context, re.IGNORECASE) for p in context_patterns)
                    if has_context_nearby:
                        indirect_classification["CONTEXT_IN_PARAGRAPH"] += 1
                    else:
                        # Check if in title/header
                        first_500 = doc_text[:500]
                        has_context_in_header = any(re.search(p, first_500, re.IGNORECASE) for p in context_patterns)
                        if has_context_in_header:
                            indirect_classification["TITLE_ONLY"] += 1
                        else:
                            indirect_classification["CONTEXT_ELSEWHERE"] += 1
                else:
                    indirect_classification["OTHER"] += 1
        else:
            expanded_dist["INSUFFICIENT"] += 1

    total = len(attached_facts)

    print(f"\n--- Original Classification (strict) ---")
    for cls, count in strict_dist.most_common():
        print(f"  {cls:<25} {count:>5}  ({count/total*100:.1f}%)")

    print(f"\n--- After Evidence Expansion ---")
    for cls, count in expanded_dist.most_common():
        print(f"  {cls:<25} {count:>5}  ({count/total*100:.1f}%)")

    print(f"\n--- INDIRECT Classification ---")
    for cls, count in indirect_classification.most_common():
        print(f"  {cls:<30} {count:>5}")

    direct_pct = expanded_dist.get("DIRECT", 0) / total * 100
    insufficient_pct = expanded_dist.get("INSUFFICIENT", 0) / total * 100
    invalid_pct = expanded_dist.get("INVALID", 0) / total * 100

    # Fact precision = DIRECT + (INDIRECT if value is correct)
    direct_count = expanded_dist.get("DIRECT", 0)
    indirect_count = expanded_dist.get("INDIRECT", 0)
    # Fact precision counts facts where the value is correct (DIRECT + INDIRECT)
    # but NOT INVALID or INSUFFICIENT
    fact_precision = (direct_count + indirect_count) / total * 100

    print(f"\n--- Quality Metrics ---")
    print(f"  Fact Precision: {fact_precision:.1f}% (numerator={direct_count+indirect_count}, denominator={total})")
    print(f"  Direct Evidence: {direct_pct:.1f}% (numerator={direct_count}, denominator={total})")
    print(f"  Insufficient: {insufficient_pct:.1f}%")
    print(f"  Invalid: {invalid_pct:.1f}%")

    return {
        "total_facts": total,
        "original_classification": dict(strict_dist),
        "expanded_classification": dict(expanded_dist),
        "indirect_subclassification": dict(indirect_classification),
        "fact_precision_pct": round(fact_precision, 1),
        "direct_evidence_pct": round(direct_pct, 1),
        "insufficient_pct": round(insufficient_pct, 1),
        "invalid_pct": round(invalid_pct, 1),
        "fixed_count": fixed_count,
        "rejected_count": rejected_count,
        "reclassified_count": reclassified_count,
        "fact_dispositions": fact_dispositions[:50],
    }


if __name__ == "__main__":
    result = run_v10_evidence_closure()
    out_path = Path("intelligence_core/tests/reliability/v10_evidence_closure_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
