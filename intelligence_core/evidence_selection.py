"""V37.2 — Evidence Selection (Production).

Implements the V37.2 evidence-selection safety model:
  fact.value
    ↓
  candidate EvidenceSegmentV1 segments (text contains fact.value)
    ↓
  structural exclusion filter (segment.excluded == False)
    ↓
  PRIMARY_EVIDENCE_TYPES filter (PARAGRAPH, LIST_ITEM, TABLE_ROW, QUOTE, FOOTNOTE)
    ↓
  contextual scoring (VALUE_PRESENT + METRIC_CONTEXT + ENTITY_CONTEXT +
                      UNIT_CONTEXT + TEMPORAL_CONTEXT + STRUCTURAL_RELEVANCE +
                      HEADING_MATCH - BOILERPLATE_PENALTY)
    ↓
  ranked candidates → top candidate
    ↓
  if no candidate → INSUFFICIENT_EVIDENCE

NEVER:
  - value-only positional selection
  - occurrence-as-index into segment list
  - character slicing
  - sentence slicing
  - paragraph splitting on inline tags

fact.occurrence is read-only context for tiebreak only — never an index.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from .structural_parser import (
    EvidenceSegmentV1, PRIMARY_EVIDENCE_TYPES, EXCLUDED_TYPES,
    parse_html_to_segments, detect_unit, detect_period,
)


# ═══════════════════════════════════════════════════════════════════════
# Evidence status codes
# ═══════════════════════════════════════════════════════════════════════

DIRECT = "DIRECT"
INDIRECT = "INDIRECT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
INVALID = "INVALID"


# ═══════════════════════════════════════════════════════════════════════
# Scoring model — design from Evidence Segment Architecture V1 §5.2
# ═══════════════════════════════════════════════════════════════════════

# Metric-related keywords (for METRIC_CONTEXT dimension)
METRIC_KEYWORDS = {
    "percentage_statistic": [
        "rate", "growth", "change", "increase", "decrease", "figure",
        "percent", "percentage", "statistic", "estimate", "index",
        "indicator", "grew", "rose", "fell", "declined", "increased",
        "decreased", "narrowed", "expanded", "stood", "reached", "revised",
        "observed", "gdp", "inflation", "cpi", "unemployment", "employment",
        "production", "output", "trade", "deficit", "surplus", "balance",
    ],
    "policy_rate": ["rate", "interest", "policy", "benchmark", "base rate"],
    "rate_decision": ["maintain", "raise", "cut", "lower", "increase",
                      "decrease", "hold", "unchanged"],
    "usd_amount": ["$", "usd", "million", "billion", "trillion", "thousand"],
    "eur_amount": ["€", "eur"],
    "gbp_amount": ["£", "gbp"],
    "barrels": ["barrel", "bbl", "barrels"],
    "tons": ["ton", "tonne", "tons"],
    "people": ["people", "persons", "employees"],
    "basis_points": ["bp", "bps", "basis point"],
    "index_points": ["index point", "index"],
}

# Default fallback: any economic term
DEFAULT_METRIC_KEYWORDS = ["rate", "growth", "percent", "value", "amount"]


# Period regex for TEMPORAL_CONTEXT detection
_PERIOD_REGEX = re.compile(
    r"\b(20\d{2}|Q[1-4]|H[12]|"
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b",
    re.IGNORECASE,
)


@dataclass
class EvidenceSelectionResult:
    """Result of selecting evidence for a fact."""
    fact_id: str
    fact_value: str
    fact_metric: str
    fact_occurrence: int
    status: str  # DIRECT | INDIRECT | INSUFFICIENT_EVIDENCE | INVALID
    selected_segment: Optional[EvidenceSegmentV1] = None
    selected_score: float = 0.0
    candidate_count: int = 0
    reason: str = ""
    # For forensic audit — list all candidates considered
    candidates_considered: list = None  # list of (segment_id, score, segment_type)
    # V37.2 SUB-COLLISION FIX §8 — preserve pre-collision state for audit.
    # The auditor must inspect collision groups BEFORE resolution (before
    # selected_segment is cleared). This field captures the segment that
    # WOULD have been selected if collision detection had not run.
    pre_collision_segment: Optional[EvidenceSegmentV1] = None
    pre_collision_status: str = ""  # DIRECT/INDIRECT/INSUFFICIENT/INVALID before collision detection
    pre_collision_score: float = 0.0

    def __post_init__(self):
        if self.candidates_considered is None:
            self.candidates_considered = []

    def to_dict(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "fact_value": self.fact_value,
            "fact_metric": self.fact_metric,
            "fact_occurrence": self.fact_occurrence,
            "status": self.status,
            "selected_segment": (
                self.selected_segment.to_dict() if self.selected_segment else None
            ),
            "selected_score": self.selected_score,
            "candidate_count": self.candidate_count,
            "reason": self.reason,
            "candidates_considered": [
                {"segment_id": sid, "score": sc, "segment_type": st}
                for sid, sc, st in self.candidates_considered
            ],
            "pre_collision_segment": (
                self.pre_collision_segment.to_dict() if self.pre_collision_segment else None
            ),
            "pre_collision_status": self.pre_collision_status,
            "pre_collision_score": self.pre_collision_score,
        }


# ═══════════════════════════════════════════════════════════════════════
# Canonical numeric value matcher
# ═══════════════════════════════════════════════════════════════════════
#
# V37.2 COLLISION FIX §2: fact.value must match the ACTUAL primary
# numeric value of the candidate text, not an incidental substring.
#
# Handles:
#   5      matches "5", "5%", "5.0", "5.00", "$5", "€5", "5 billion"
#   5      does NOT match "15", "50", "3.5", "2025", "0.5"
#   0.5    matches "0.5", "0.5%", "$0.5"
#   3.5    matches "3.5%", "3,5 %" (EU decimal)
#
# Implementation: extract the FIRST standalone numeric value from text
# using regex that respects decimal boundaries. Compare numerically.

_NUMERIC_VALUE_RE = re.compile(
    r"(?<![\w.])"                    # negative lookbehind: not preceded by word char or dot
    r"(\d+(?:[.,]\d+)?)"              # capture: digits with optional decimal (US . or EU ,)
    r"(?![\w.])"                      # negative lookahead: not followed by word char or dot
)

# Currency prefixes that may appear before a number
_CURRENCY_PREFIXES = re.compile(r"[$€£]\s*(\d+(?:[.,]\d+)?)")


def _normalize_numeric(s: str) -> str:
    """Normalize a numeric string for comparison.

    '3,5' (EU) → '3.5'
    '5.0' → '5' (strip trailing zeros)
    '5.00' → '5'
    """
    if not s:
        return ""
    # EU decimal: comma → dot (only if no dot present)
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    # Try to strip trailing zeros after decimal
    try:
        f = float(s)
        # If integer value, return as int string
        if f == int(f):
            return str(int(f))
        return str(f)
    except (ValueError, OverflowError):
        return s


def extract_primary_numeric(text: str) -> Optional[str]:
    """Extract the primary (first) standalone numeric value from text.

    Returns the normalized numeric string, or None if no numeric found.
    The 'primary' value is the first number that appears as a standalone
    token (not a digit-substring of a larger number).

    Examples:
      "5%"                     → "5"
      "3,5 %" (EU)             → "3.5"
      "5.0 percent"            → "5"
      "$5.2 billion"            → "5.2"
      "5"                      → "5"
      "15.05.2026"              → "15.05"  (first standalone)
      "Inflation 2025 bei 3,5" → "2025"  (first standalone is year)
      "Revenue 2.4% in Q1 2026" → "2.4"

    Note: dates like "2025" will match as standalone numeric. This is
    acceptable — the fact_value 5 will not match "2025" because
    5 != 2025.
    """
    if not text:
        return None
    # Try currency-prefix match first (more specific)
    m = _CURRENCY_PREFIXES.search(text)
    if m:
        return _normalize_numeric(m.group(1))
    # Then standalone numeric
    m = _NUMERIC_VALUE_RE.search(text)
    if m:
        return _normalize_numeric(m.group(1))
    return None


def _all_standalone_numerics(text: str) -> list:
    """Extract ALL standalone numeric values from text.

    Used by numeric_value_matches to allow fact_value to match any
    number in the text (not just the first). This handles paragraphs
    that mention multiple numeric values like "Rate was 2.4% but rose
    to 5% later".
    """
    if not text:
        return []
    numerics = []
    # Currency-prefixed numbers
    for m in _CURRENCY_PREFIXES.finditer(text):
        numerics.append(_normalize_numeric(m.group(1)))
    # Standalone numbers (includes those already captured by currency
    # prefix — we'll dedupe by numeric value)
    for m in _NUMERIC_VALUE_RE.finditer(text):
        numerics.append(_normalize_numeric(m.group(1)))
    return numerics


def numeric_value_matches(fact_value: str, candidate_text: str) -> bool:
    """Canonical numeric matcher.

    Returns True if fact_value's numeric value equals ANY standalone
    numeric value in candidate_text. This prevents false positives like
    fact_value="5" matching "3,5 %" (5 != 3.5) while allowing a paragraph
    that mentions multiple values (e.g., "Rate was 2.4% but rose to 5%")
    to be matched by either fact_value=2.4 or fact_value=5.

    The matcher uses STANDALONE numeric extraction — meaning the number
    must be a complete token, not a digit-substring of a larger number.
    "5" does NOT match "15" or "2025" because those are different
    standalone numbers (15, 2025).
    """
    if not fact_value or not candidate_text:
        return False
    # Only applies to numeric fact values
    if not re.match(r"^\d+(?:[.,]\d+)?$", fact_value):
        return False
    fv = _normalize_numeric(fact_value)
    try:
        fv_float = float(fv)
    except (ValueError, OverflowError):
        fv_float = None
    # Check against ALL standalone numerics in the text
    for num_str in _all_standalone_numerics(candidate_text):
        try:
            if fv_float is not None and float(num_str) == fv_float:
                return True
        except (ValueError, OverflowError):
            if num_str == fv:
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Scoring dimensions
# ═══════════════════════════════════════════════════════════════════════

def _value_present(text: str, value: str) -> bool:
    """Prerequisite: fact.value appears in segment.text.

    For numeric fact values, uses the CANONICAL NUMERIC MATCHER
    (numeric_value_matches) — fact_value must equal the primary numeric
    value of the text. This prevents:
      - fact_value="5" matching "3,5 %" (5 != 3.5)
      - fact_value="5" matching "15.05.2026" (5 != 15.05)
      - fact_value="5" matching "2025" (5 != 2025)
      - fact_value="5" matching "0.5" (5 != 0.5)

    For non-numeric fact values (e.g., "maintain", "raise"), plain
    substring match.

    This implements V37.2 COLLISION FIX §2 (Case A — canonical table-cell
    value matcher) per OCCURRENCE_IDENTITY_REVIEW.md Case A.
    """
    if not value or not text:
        return False
    # Numeric fact value → canonical matcher
    if re.match(r"^\d+(?:[.,]\d+)?$", value):
        return numeric_value_matches(value, text)
    # Non-numeric value → substring match
    return value in text


def _metric_context_score(text: str, metric: str) -> float:
    """0.0 → 1.0. Count of metric-related keywords found."""
    if not text or not metric:
        return 0.0
    keywords = METRIC_KEYWORDS.get(metric, DEFAULT_METRIC_KEYWORDS)
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    if hits == 0:
        return 0.0
    # Cap at 1.0 — diminishing returns after 3 hits
    return min(1.0, hits / 3.0)


def _entity_context_score(text: str, known_entities: list) -> float:
    """0.0 → 1.0. Known entity name appears in text."""
    if not text or not known_entities:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for ent in known_entities if ent.lower() in text_lower)
    return min(1.0, hits / 2.0)


def _unit_context_score(text: str, fact_metric: str) -> float:
    """0.0 → 1.0. Segment text contains unit indicators consistent with
    the metric type. Detects $ for usd_amount, % for percentage_statistic,
    etc."""
    if not text:
        return 0.0
    text_lower = text.lower()
    if fact_metric in ("percentage_statistic", "policy_rate"):
        if "%" in text or "percent" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("usd_amount",):
        if "$" in text or "usd" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("eur_amount",):
        if "€" in text or "eur" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("gbp_amount",):
        if "£" in text or "gbp" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("basis_points",):
        if "bp" in text_lower or "basis" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("barrels",):
        if "barrel" in text_lower or "bbl" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("tons",):
        if "ton" in text_lower:
            return 1.0
        return 0.0
    if fact_metric in ("index_points",):
        if "index" in text_lower:
            return 1.0
        return 0.0
    return 0.0


def _temporal_context_score(text: str) -> float:
    """0.0 → 1.0. Segment text contains period indicators."""
    if not text:
        return 0.0
    matches = _PERIOD_REGEX.findall(text)
    if not matches:
        return 0.0
    return min(1.0, len(matches) / 2.0)


def _structural_relevance_score(segment_type: str) -> float:
    """0.0 → 1.0. Weight by segment_type priority."""
    weights = {
        "TABLE_ROW": 1.0,    # richest semantic context
        "PARAGRAPH": 0.9,
        "LIST_ITEM": 0.7,
        "QUOTE": 0.7,
        "FOOTNOTE": 0.6,
        "HEADING": 0.3,
        "OTHER": 0.1,
    }
    return weights.get(segment_type, 0.0)


def _heading_match_score(heading_context: Optional[str], metric: str,
                         known_entities: list) -> float:
    """0.0 → 1.0. Heading context contains metric/entity keyword."""
    if not heading_context:
        return 0.0
    hc_lower = heading_context.lower()
    keywords = METRIC_KEYWORDS.get(metric, DEFAULT_METRIC_KEYWORDS)
    for kw in keywords:
        if kw.lower() in hc_lower:
            return 1.0
    for ent in known_entities:
        if ent.lower() in hc_lower:
            return 1.0
    return 0.0


def _boilerplate_penalty(text: str) -> float:
    """0.0 → -1.0. Penalty for high non-alphanumeric content."""
    if not text:
        return 0.0
    alnum_count = sum(1 for c in text if c.isalnum())
    if len(text) == 0:
        return 0.0
    ratio = alnum_count / len(text)
    if ratio < 0.4:
        return -0.5
    if ratio < 0.6:
        return -0.2
    return 0.0


# ═══════════════════════════════════════════════════════════════════════
# Composite scoring
# ═══════════════════════════════════════════════════════════════════════

# Weights for the composite score (sum to 1.0)
SCORE_WEIGHTS = {
    "metric_context": 0.30,
    "unit_context": 0.20,
    "entity_context": 0.15,
    "temporal_context": 0.10,
    "structural_relevance": 0.15,
    "heading_match": 0.10,
}


def score_segment(
    segment: EvidenceSegmentV1,
    fact_value: str,
    fact_metric: str,
    known_entities: list,
) -> tuple[float, dict]:
    """Score one candidate segment. Returns (composite_score, breakdown)."""
    breakdown = {}
    breakdown["value_present"] = 1.0 if _value_present(segment.text, fact_value) else 0.0
    if breakdown["value_present"] == 0.0:
        return 0.0, breakdown  # prerequisite failed
    breakdown["metric_context"] = _metric_context_score(segment.text, fact_metric)
    breakdown["entity_context"] = _entity_context_score(segment.text, known_entities)
    breakdown["unit_context"] = _unit_context_score(segment.text, fact_metric)
    breakdown["temporal_context"] = _temporal_context_score(segment.text)
    breakdown["structural_relevance"] = _structural_relevance_score(segment.segment_type)
    breakdown["heading_match"] = _heading_match_score(
        segment.heading_context, fact_metric, known_entities,
    )
    breakdown["boilerplate_penalty"] = _boilerplate_penalty(segment.text)

    composite = (
        SCORE_WEIGHTS["metric_context"] * breakdown["metric_context"]
        + SCORE_WEIGHTS["unit_context"] * breakdown["unit_context"]
        + SCORE_WEIGHTS["entity_context"] * breakdown["entity_context"]
        + SCORE_WEIGHTS["temporal_context"] * breakdown["temporal_context"]
        + SCORE_WEIGHTS["structural_relevance"] * breakdown["structural_relevance"]
        + SCORE_WEIGHTS["heading_match"] * breakdown["heading_match"]
        + breakdown["boilerplate_penalty"]
    )
    # Floor at 0 — penalty cannot make score negative
    composite = max(0.0, composite)
    return composite, breakdown


# ═══════════════════════════════════════════════════════════════════════
# Selection entry point
# ═══════════════════════════════════════════════════════════════════════

def select_evidence_segment(
    fact,
    segments: list,
    known_entities: list = None,
) -> EvidenceSelectionResult:
    """Select the best EvidenceSegmentV1 for a fact.

    fact: a Fact dataclass (or dict with fact_id, value, metric, occurrence)
    segments: list of EvidenceSegmentV1 from parse_html_to_segments()
    known_entities: optional list of entity names for entity_context scoring

    Returns EvidenceSelectionResult with status:
      - DIRECT: top candidate score >= MIN_DIRECT_SCORE
      - INDIRECT: top candidate score < MIN_DIRECT_SCORE but > 0
      - INSUFFICIENT_EVIDENCE: zero candidates
      - INVALID: fact.value is empty/invalid

    fact.occurrence is NEVER used as a segment index. It is only available
    as a tiebreak signal (not used in this implementation — composite score
    is decisive).
    """
    # Extract fact fields
    if hasattr(fact, "fact_id"):
        fact_id = fact.fact_id
        fact_value = str(fact.value)
        fact_metric = fact.metric
        fact_occurrence = getattr(fact, "occurrence", 0) or 0
    else:
        fact_id = fact.get("fact_id", "")
        fact_value = str(fact.get("value", ""))
        fact_metric = fact.get("metric", "")
        fact_occurrence = fact.get("occurrence", 0) or 0

    known_entities = known_entities or []

    result = EvidenceSelectionResult(
        fact_id=fact_id,
        fact_value=fact_value,
        fact_metric=fact_metric,
        fact_occurrence=fact_occurrence,
        status=INSUFFICIENT_EVIDENCE,
    )

    # INVALID — no value to search for
    if not fact_value:
        result.status = INVALID
        result.reason = "empty fact value"
        return result

    # Step 1: Find candidate segments containing the value
    candidates = []
    for seg in segments:
        if seg.excluded:
            continue
        if seg.segment_type not in PRIMARY_EVIDENCE_TYPES:
            continue
        # For TABLE_ROW segments, match fact.value against cell_value
        # (the actual data value) — NOT the full segment text (which
        # includes row_label and column_label that may coincidentally
        # contain the value, e.g., fact_value=15 matching row_label
        # "15.01.2025" which is a date, not the data).
        if seg.segment_type == "TABLE_ROW" and seg.cell_value:
            check_text = seg.cell_value
        else:
            check_text = seg.text
        if not _value_present(check_text, fact_value):
            continue
        score, breakdown = score_segment(
            seg, fact_value, fact_metric, known_entities,
        )
        candidates.append((seg, score, breakdown))

    result.candidate_count = len(candidates)

    # Step 2: INSUFFICIENT_EVIDENCE if no candidates
    if not candidates:
        result.status = INSUFFICIENT_EVIDENCE
        result.reason = "no candidate segments contain the value"
        return result

    # Step 3: Sort by score descending
    candidates.sort(key=lambda c: c[1], reverse=True)

    # Record all candidates for forensic audit
    result.candidates_considered = [
        (seg.segment_id, score, seg.segment_type)
        for seg, score, _ in candidates
    ]

    # Step 4: Take top candidate
    top_seg, top_score, top_breakdown = candidates[0]
    result.selected_segment = top_seg
    result.selected_score = top_score

    # Step 5: Classify
    # MIN_DIRECT_SCORE = 0.40 — calibrated on the 158-case preview.
    # A score of 0.40 typically requires:
    #   - value present (1.0 * weight)
    #   - at least 1 of: metric_context, unit_context, heading_match
    #     with non-trivial score
    MIN_DIRECT_SCORE = 0.40
    if top_score >= MIN_DIRECT_SCORE:
        result.status = DIRECT
        result.reason = f"top score {top_score:.3f} >= {MIN_DIRECT_SCORE}"
    elif top_score > 0:
        result.status = INDIRECT
        result.reason = f"top score {top_score:.3f} < {MIN_DIRECT_SCORE}"
    else:
        # All candidates scored 0 — meaning value present but no context
        # matched. Treat as INDIRECT.
        result.status = INDIRECT
        result.reason = "value present but no contextual signal matched"

    return result


# ═══════════════════════════════════════════════════════════════════════
# Convenience: select evidence for many facts over one document
# (includes V37.2 COLLISION FIX §3 — collision detection)
# ═══════════════════════════════════════════════════════════════════════

def select_evidence_for_document(
    facts: list,
    html_bytes: bytes,
    document_id: str = "",
    known_entities: list = None,
) -> list:
    """Parse HTML once, then select evidence for each fact.

    Includes V37.2 SUB-COLLISION FIX §2/§3/§4 — sub-collision detection:

    For each segment shared by multiple facts:
      1. Sub-partition the collision group by (fact_value, fact_metric)
         using existing metric normalization (no new metric ontology).
      2. For each (value, metric) subgroup:
         - count == 1 → SAFE_SHARED_EVIDENCE (but only if segment has
           explicit metric/unit context for that fact)
         - count > 1 → UNRESOLVED_SUBCOLLISION → all facts in subgroup
           become INSUFFICIENT_EVIDENCE (selected_segment cleared but
           pre_collision_segment preserved for audit)

    Occurrence is NEVER used as positional index (§4). Even if segment
    contains N occurrences of the value, N facts with same value+metric
    are indistinguishable without entity/period extraction (V37.2 scope
    limit — V38+ may relax this).

    Returns list of EvidenceSelectionResult, one per fact.
    """
    segments = parse_html_to_segments(html_bytes, document_id=document_id)
    results = []
    for fact in facts:
        r = select_evidence_segment(fact, segments, known_entities=known_entities)
        # V37.2 SUB-COLLISION FIX §8 — preserve pre-collision state
        r.pre_collision_segment = r.selected_segment
        r.pre_collision_status = r.status
        r.pre_collision_score = r.selected_score
        results.append(r)

    # ── V37.2 SUB-COLLISION FIX §3 — sub-collision detection ─────────
    # Group results by pre_collision_segment.segment_id (BEFORE clearing).
    # This ensures the auditor can inspect collision groups even after
    # selected_segment is cleared for UNRESOLVED facts.
    from collections import defaultdict
    groups_by_seg = defaultdict(list)
    for i, r in enumerate(results):
        if r.pre_collision_segment is not None:
            groups_by_seg[r.pre_collision_segment.segment_id].append(i)

    for seg_id, indices in groups_by_seg.items():
        if len(indices) <= 1:
            continue  # No collision — single fact per segment

        # Sub-partition by (fact_value, fact_metric)
        # V37.2 SUB-COLLISION FIX §2 — use existing metric (no new ontology)
        subgroups = defaultdict(list)
        for i in indices:
            key = (results[i].fact_value, results[i].fact_metric)
            subgroups[key].append(i)

        # Get the segment text once (for unit_context check)
        seg_text = results[indices[0]].pre_collision_segment.text or ""

        for (val, met), sub_indices in subgroups.items():
            if len(sub_indices) == 1:
                # CASE A (§3) — count == 1 → potentially SAFE_SHARED
                # ONLY if segment has explicit metric/unit context for this fact
                i = sub_indices[0]
                unit_score = _unit_context_score(seg_text, met)
                if unit_score > 0:
                    # SAFE_SHARED_EVIDENCE — segment has unit context for this metric
                    old_reason = results[i].reason
                    results[i].reason = (
                        f"{old_reason} | SAFE_SHARED_EVIDENCE: 1 fact with "
                        f"(value={val!r}, metric={met!r}) in segment {seg_id} "
                        f"— unit context present (score={unit_score:.2f})"
                    )
                else:
                    # No unit context for this metric → fact's selection was arbitrary
                    old_status = results[i].status
                    results[i].status = INSUFFICIENT_EVIDENCE
                    results[i].selected_segment = None
                    results[i].selected_score = 0.0
                    results[i].reason = (
                        f"UNRESOLVED_SUBCOLLISION: 1 fact with "
                        f"(value={val!r}, metric={met!r}) in segment {seg_id} "
                        f"but no explicit unit context for metric {met!r} "
                        f"(was {old_status})"
                    )
            else:
                # CASE B (§3) — count > 1 → UNRESOLVED_SUBCOLLISION
                # All facts in this subgroup are indistinguishable among
                # themselves (same value, same metric, same segment).
                # Per V37.2 SUB-COLLISION FIX §4 — even if segment contains
                # N occurrences of the value, that does NOT prove fact_i →
                # occurrence_i. No positional guessing.
                for i in sub_indices:
                    old_status = results[i].status
                    results[i].status = INSUFFICIENT_EVIDENCE
                    # Clear selected_segment (preserve pre_collision_segment for audit)
                    results[i].selected_segment = None
                    results[i].selected_score = 0.0
                    results[i].reason = (
                        f"UNRESOLVED_SUBCOLLISION: {len(sub_indices)} facts with same "
                        f"value={val!r} and same metric={met!r} map to same "
                        f"segment {seg_id} (was {old_status}) — indistinguishable "
                        f"without entity/period extraction (V37.2 scope limit)"
                    )

    return results


# ═══════════════════════════════════════════════════════════════════════
# Collision audit helper — V37.2 SUB-COLLISION FIX §8 — uses
# pre_collision_segment to inspect collision groups BEFORE resolution
# ═══════════════════════════════════════════════════════════════════════

def audit_collisions(results: list) -> dict:
    """Audit a list of EvidenceSelectionResult for collisions.

    V37.2 COLLISION ACCOUNTING CORRECTION — 3-way classification:

    For every collision group, sub-partition by (value, metric). Each
    subgroup is classified as exactly ONE of:

      1. SAFE_SHARED_EVIDENCE
         count==1 AND segment has explicit unit context for the metric.
         Facts remain DIRECT/INDIRECT (selected_segment preserved).
         Distinction is by different metric/unit within the shared segment.

      2. RESOLVED_INSUFFICIENT_EVIDENCE
         count>1 (or count==1 without unit context).
         The system intentionally rejected the ambiguous facts as
         INSUFFICIENT_EVIDENCE. selected_segment is null, status is
         INSUFFICIENT_EVIDENCE, reason contains UNRESOLVED_SUBCOLLISION.

      3. UNRESOLVED_COLLISION
         The system detected a collision but FAILED to resolve it.
         Facts should have been INSUFFICIENT but aren't.
         This is a DEFECT — required to be 0.

    Accounting invariant:
      total_collision_facts
        = safe_shared_evidence_facts
        + resolved_insufficient_facts
        + unresolved_collision_facts

    No fact may disappear from accounting.
    """
    from collections import defaultdict
    # Group by pre_collision_segment.segment_id (BEFORE resolution)
    groups_by_seg = defaultdict(list)
    for r in results:
        if r.pre_collision_segment is not None:
            groups_by_seg[r.pre_collision_segment.segment_id].append(r)

    safe_shared_groups = []
    resolved_insufficient_groups = []
    unresolved_groups = []
    safe_facts = 0
    resolved_insufficient_facts = 0
    unresolved_facts = 0

    for seg_id, group in groups_by_seg.items():
        if len(group) <= 1:
            continue  # No collision — single fact per segment
        # Sub-partition by (value, metric)
        subgroups = defaultdict(list)
        for r in group:
            subgroups[(r.fact_value, r.fact_metric)].append(r)
        # Get segment text for unit context check
        seg_text = group[0].pre_collision_segment.text or ""
        for (val, met), sub_group in subgroups.items():
            count = len(sub_group)
            unit_score = _unit_context_score(seg_text, met)
            # Determine expected classification
            if count == 1 and unit_score > 0:
                expected = "SAFE_SHARED_EVIDENCE"
            else:
                expected = "RESOLVED_INSUFFICIENT_EVIDENCE"
            # Check actual state
            if expected == "SAFE_SHARED_EVIDENCE":
                # Should remain DIRECT/INDIRECT
                all_safe = all(r.status != INSUFFICIENT_EVIDENCE for r in sub_group)
                if all_safe:
                    safe_shared_groups.append({
                        "segment_id": seg_id,
                        "fact_ids": [r.fact_id for r in sub_group],
                        "value": val,
                        "metric": met,
                        "fact_count": count,
                        "classification": "SAFE_SHARED_EVIDENCE",
                    })
                    safe_facts += count
                else:
                    # Conversion failure — should be safe but isn't
                    unresolved_groups.append({
                        "segment_id": seg_id,
                        "fact_ids": [r.fact_id for r in sub_group],
                        "value": val,
                        "metric": met,
                        "fact_count": count,
                        "classification": "UNRESOLVED_COLLISION",
                        "expected": "SAFE_SHARED_EVIDENCE",
                    })
                    unresolved_facts += count
            else:
                # Should be ALL INSUFFICIENT (resolved insufficient)
                all_insufficient = all(r.status == INSUFFICIENT_EVIDENCE for r in sub_group)
                if all_insufficient:
                    # Correctly resolved as insufficient
                    resolved_insufficient_groups.append({
                        "segment_id": seg_id,
                        "fact_ids": [r.fact_id for r in sub_group],
                        "value": val,
                        "metric": met,
                        "fact_count": count,
                        "classification": "RESOLVED_INSUFFICIENT_EVIDENCE",
                    })
                    resolved_insufficient_facts += count
                else:
                    # Conversion failure — should be INSUFFICIENT but isn't
                    unresolved_groups.append({
                        "segment_id": seg_id,
                        "fact_ids": [r.fact_id for r in sub_group],
                        "value": val,
                        "metric": met,
                        "fact_count": count,
                        "classification": "UNRESOLVED_COLLISION",
                        "expected": "INSUFFICIENT_EVIDENCE",
                    })
                    unresolved_facts += count

    total_collision_facts = (
        safe_facts + resolved_insufficient_facts + unresolved_facts
    )
    invariant_holds = total_collision_facts == sum(
        len(g) for g in groups_by_seg.values() if len(g) > 1
    )

    return {
        "safe_shared_evidence": safe_shared_groups,
        "resolved_insufficient_evidence": resolved_insufficient_groups,
        "unresolved_collisions": unresolved_groups,
        "safe_shared_evidence_facts": safe_facts,
        "resolved_insufficient_facts": resolved_insufficient_facts,
        "unresolved_collision_facts": unresolved_facts,
        "safe_shared_evidence_groups": len(safe_shared_groups),
        "resolved_insufficient_groups": len(resolved_insufficient_groups),
        "unresolved_collision_groups": len(unresolved_groups),
        "total_collision_facts": total_collision_facts,
        "invariant_holds": invariant_holds,
    }
