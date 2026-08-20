"""ROUAA Core V46 — Evidence Context Recovery.

Builds a deterministic context package (EvidenceContextV1) around each
existing fact's evidence excerpt, using V37.2 structural segments
(`parse_html_to_segments` + `apply_purpose_filter`).

The context package adds BROADER textual context around the short
fact excerpts (which were truncated to 300 chars in Phase B). This
broader context enables honest downstream semantic enrichment to
detect:
  - primary entity (institution names in nearby text)
  - reference period (date patterns in nearby text)
  - event date / publication date / effective date / revision date
  - event state (NEW / REVISED / INCREASED / DECREASED / etc.)

INVARIANTS:
  - Original fact values are NEVER changed.
  - Original evidence excerpts are NEVER changed.
  - Original evidence IDs are NEVER changed.
  - Original fact IDs are NEVER changed.
  - Source / document identity is NEVER changed.
  - Navigation evidence is NEVER introduced (purpose filter applied).
  - All signals carry provenance (segment_ids that contributed).

Context window model (priority order per §4):
  1. Same structural segment as the fact's excerpt
  2. Parent structural segment
  3. Adjacent sibling segments (immediate prev/next)
  4. Same table row / table context
  5. Same heading section (segments sharing the same heading_context)
  6. Bounded structural neighborhood (next-N segments, capped at 5)

STOP expansion when at least 200 chars of context_before + context_after
are gathered, OR when priority 6 is exhausted.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .contracts import EvidenceContextV1
from .structural_parser import EvidenceSegmentV1, parse_html_to_segments
from .segment_purpose import apply_purpose_filter, PURPOSE_SUBSTANTIVE


# ═══════════════════════════════════════════════════════════════════════
# Signal detectors — entity / temporal / state
# ═══════════════════════════════════════════════════════════════════════

# Institution long-form names (generic, not document-specific)
_INSTITUTION_LONG_NAMES = [
    (re.compile(r"\bEuropean\s+Central\s+Bank\b", re.I), "ECB"),
    (re.compile(r"\bBank\s+of\s+England\b", re.I), "BOE"),
    (re.compile(r"\bBank\s+of\s+Japan\b", re.I), "BOJ"),
    (re.compile(r"\bFederal\s+Reserve\b", re.I), "FED"),
    (re.compile(r"\bBureau\s+of\s+Economic\s+Analysis\b", re.I), "BEA"),
    (re.compile(r"\bBureau\s+of\s+Labor\s+Statistics\b", re.I), "BLS"),
    (re.compile(r"\bInternational\s+Monetary\s+Fund\b", re.I), "IMF"),
    (re.compile(r"\bSwiss\s+National\s+Bank\b", re.I), "SNB"),
    (re.compile(r"\bBank\s+of\s+Canada\b", re.I), "BOC"),
    (re.compile(r"\bReserve\s+Bank\s+of\s+Australia\b", re.I), "RBA"),
    (re.compile(r"\bReserve\s+Bank\s+of\s+New\s+Zealand\b", re.I), "RBNZ"),
    (re.compile(r"\bEuropean\s+Securities\s+and\s+Markets\s+Authority\b", re.I), "ESMA"),
    (re.compile(r"\bEuropean\s+Banking\s+Authority\b", re.I), "EBA"),
    (re.compile(r"\bFinancial\s+Conduct\s+Authority\b", re.I), "FCA"),
    (re.compile(r"\bSecurities\s+and\s+Exchange\s+Commission\b", re.I), "SEC"),
    (re.compile(r"\bCommodity\s+Futures\s+Trading\s+Commission\b", re.I), "CFTC"),
    (re.compile(r"\bEuropean\s+Statistical\s+Office\b", re.I), "EUROSTAT"),
    (re.compile(r"\bEurostat\b", re.I), "EUROSTAT"),
    (re.compile(r"\bBank\s+for\s+International\s+Settlements\b", re.I), "BIS"),
    (re.compile(r"\bOrganisation\s+for\s+Economic\s+Co-operation\s+and\s+Development\b", re.I), "OECD"),
]

# Institution acronyms (uppercase 2-6 letter tokens, with word boundary)
_INSTITUTION_ACRONYM_RE = re.compile(
    r"\b((?:ECB|BOE|BOJ|FED|BEA|BLS|IMF|OECD|BIS|ESMA|EBA|EIOPA|FCA|SEC|CFTC|OCC|FDIC|SNB|BOC|RBA|RBNZ|EUROSTAT|ESRB))"
)

# Temporal patterns (date + period forms)
_TEMPORAL_PATTERNS = [
    # Full dates "January 2024", "January 15, 2024", "15 January 2024"
    (re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b", re.I), "month_day_year"),
    (re.compile(r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b", re.I), "day_month_year"),
    (re.compile(r"\b(?:in|for|of)\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b", re.I), "month_year"),
    # Q1 2024 / 2024 Q1 / Q1-2024
    (re.compile(r"\bQ([1-4])\s*(?:of\s+|-)?(\d{4})\b", re.I), "quarter_year"),
    (re.compile(r"\b(\d{4})\s*Q([1-4])\b", re.I), "year_quarter"),
    # Year alone with context word
    (re.compile(r"\b(?:in|for|of|fiscal\s+year|FY)\s+(20\d{2})\b", re.I), "year_context"),
    # ISO dates YYYY-MM-DD
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso_date"),
    # Quarter "first quarter of 2024"
    (re.compile(r"\b(first|second|third|fourth)\s+quarter\s+of\s+(\d{4})\b", re.I), "quarter_word_year"),
]

# Event-state signal words (deterministic, evidence-backed)
_STATE_SIGNALS = [
    (re.compile(r"\bcorrected\b|\bcorrection\b", re.I), "REVISED"),
    (re.compile(r"\bsuperseded\b|\bsupersedes\b|\breplaces\b", re.I), "REVISED"),
    (re.compile(r"\brevise[ds]?\b|\brevision\b|\bamend[eds]?\b|\bamendment\b|\bupdated?\b", re.I), "REVISED"),
    (re.compile(r"\bincrease[ds]?\b|\braise[ds]?\b|\bup\s+by\b|\bgrew\s+by\b|\brose\s+by\b", re.I), "INCREASED"),
    (re.compile(r"\bdecrease[ds]?\b|\breduce[ds]?\b|\bdown\s+by\b|\bcut\b|\bfell\s+by\b|\bdeclined?\b", re.I), "DECREASED"),
    (re.compile(r"\beffective\b", re.I), "EFFECTIVE"),
    (re.compile(r"\benforce[ds]?\b|\benforcement\b", re.I), "ENFORCED"),
    (re.compile(r"\bpending\b|\bawaiting\b", re.I), "PENDING"),
    (re.compile(r"\bunchanged\b|\bheld\s+(?:steady|at)\b|\bmaintained\b|\bkept\s+at\b", re.I), "UNCHANGED"),
    (re.compile(r"\bannounces\b|\bannounced\b|\bpublished\b|\breleased\b|\bissues\b", re.I), "ANNOUNCED"),
    (re.compile(r"\bnew\b|\bfirst\b|\binitial\b", re.I), "NEW"),
]


def _detect_entity_signals(text: str) -> list[tuple[str, str]]:
    """Return list of (institution_name, source_match) found in text."""
    if not text:
        return []
    found = []
    seen = set()
    # Long-form names first (more specific)
    for pat, acronym in _INSTITUTION_LONG_NAMES:
        m = pat.search(text)
        if m and acronym not in seen:
            found.append((acronym, m.group(0)))
            seen.add(acronym)
    # Then standalone acronyms (avoid double-counting long-form)
    for m in _INSTITUTION_ACRONYM_RE.finditer(text):
        if m.group(1) not in seen:
            found.append((m.group(1), m.group(0)))
            seen.add(m.group(1))
    return found


def _detect_temporal_signals(text: str) -> list[tuple[str, str]]:
    """Return list of (signal_type, matched_text) found in text."""
    if not text:
        return []
    found = []
    seen = set()
    for pat, sig_type in _TEMPORAL_PATTERNS:
        for m in pat.finditer(text):
            matched = m.group(0)
            if matched not in seen:
                found.append((sig_type, matched))
                seen.add(matched)
    return found


def _detect_state_signals(text: str) -> list[tuple[str, str]]:
    """Return list of (state, matched_text) found in text."""
    if not text:
        return []
    found = []
    seen = set()
    for pat, state in _STATE_SIGNALS:
        for m in pat.finditer(text):
            matched = m.group(0)
            key = (state, matched)
            if key not in seen:
                found.append((state, matched))
                seen.add(key)
    return found


# ═══════════════════════════════════════════════════════════════════════
# Context window builder
# ═══════════════════════════════════════════════════════════════════════

# Minimum context chars (before + after) for SUFFICIENT classification
_MIN_SUFFICIENT_CONTEXT_CHARS = 200
# Maximum segments to include in the bounded neighborhood
_MAX_NEIGHBORHOOD_SEGMENTS = 5
# Maximum chars of context_before / context_after to retain
_MAX_CONTEXT_CHARS_PER_SIDE = 1000


def find_primary_segment(segments: list[EvidenceSegmentV1], excerpt: str) -> Optional[EvidenceSegmentV1]:
    """Find the structural segment whose text contains the excerpt (or the
    longest overlap if no exact match)."""
    if not excerpt or not segments:
        return None
    # Exact substring match first
    for seg in segments:
        if excerpt in (seg.text or ""):
            return seg
    # Fall back to first 50 chars of excerpt (handles truncation)
    excerpt_prefix = excerpt[:50]
    for seg in segments:
        if excerpt_prefix and excerpt_prefix in (seg.text or ""):
            return seg
    # Last resort: first 30 chars
    excerpt_short = excerpt[:30]
    for seg in segments:
        if excerpt_short and excerpt_short in (seg.text or ""):
            return seg
    return None


def build_context_window(
    segments: list[EvidenceSegmentV1],
    primary: EvidenceSegmentV1,
    *,
    max_segments: int = _MAX_NEIGHBORHOOD_SEGMENTS,
    max_chars_per_side: int = _MAX_CONTEXT_CHARS_PER_SIDE,
) -> tuple[list[str], str, str, list[EvidenceSegmentV1], list[EvidenceSegmentV1]]:
    """Build the context window around the primary segment.

    Returns:
        context_segment_ids: list of segment IDs in the context window
        context_before: concatenated text from preceding segments (capped)
        context_after: concatenated text from following segments (capped)
        before_segs: list of segment objects that contributed to context_before
        after_segs: list of segment objects that contributed to context_after
    """
    if not segments or not primary:
        return [], "", "", [], []

    # Find primary's index in the segment list
    primary_idx = None
    for i, seg in enumerate(segments):
        if seg.segment_id == primary.segment_id:
            primary_idx = i
            break
    if primary_idx is None:
        return [], "", "", [], []

    # Same heading section: segments sharing primary's heading_context
    primary_heading = primary.heading_context
    same_section_indices = []
    if primary_heading:
        for i, seg in enumerate(segments):
            if seg.heading_context == primary_heading and not seg.excluded:
                same_section_indices.append(i)

    # Build context_before: prefer (1) immediate prev sibling, (2) prev same-section
    before_segs = []
    before_text_parts = []
    before_chars = 0

    # Walk backwards from primary_idx
    for i in range(primary_idx - 1, -1, -1):
        if len(before_segs) >= max_segments:
            break
        if before_chars >= max_chars_per_side:
            break
        seg = segments[i]
        if seg.excluded or not seg.text:
            continue
        # Stop if we cross a different heading section (boundary)
        if (primary_heading and seg.heading_context
                and seg.heading_context != primary_heading):
            # Different section — only include if it's the immediate prev sibling
            if i != primary_idx - 1:
                break
        before_segs.insert(0, seg)
        before_text_parts.insert(0, seg.text)
        before_chars += len(seg.text)

    # Build context_after: walk forwards from primary_idx
    after_segs = []
    after_text_parts = []
    after_chars = 0
    for i in range(primary_idx + 1, len(segments)):
        if len(after_segs) >= max_segments:
            break
        if after_chars >= max_chars_per_side:
            break
        seg = segments[i]
        if seg.excluded or not seg.text:
            continue
        if (primary_heading and seg.heading_context
                and seg.heading_context != primary_heading):
            if i != primary_idx + 1:
                break
        after_segs.append(seg)
        after_text_parts.append(seg.text)
        after_chars += len(seg.text)

    context_before = " ".join(before_text_parts)[:max_chars_per_side]
    context_after = " ".join(after_text_parts)[:max_chars_per_side]
    context_segment_ids = [s.segment_id for s in before_segs] + [primary.segment_id] + [s.segment_id for s in after_segs]
    return context_segment_ids, context_before, context_after, before_segs, after_segs


# ═══════════════════════════════════════════════════════════════════════
# Context quality classification
# ═══════════════════════════════════════════════════════════════════════

CONTEXT_SUFFICIENT = "CONTEXT_SUFFICIENT"
CONTEXT_PARTIAL = "CONTEXT_PARTIAL"
CONTEXT_INSUFFICIENT = "CONTEXT_INSUFFICIENT"


def classify_context_quality(
    context_before: str,
    context_after: str,
    primary: Optional[EvidenceSegmentV1],
    entity_signals: list,
    temporal_signals: list,
    state_signals: list,
) -> str:
    """Classify the context package quality.

    SUFFICIENT: ≥200 chars of context (before+after) AND at least one
    signal found (entity OR temporal OR state).

    PARTIAL: ≥50 chars of context OR at least one signal found but not
    enough to meet SUFFICIENT threshold.

    INSUFFICIENT: <50 chars context AND no signals found.
    """
    total_context_chars = len(context_before) + len(context_after)
    has_signals = bool(entity_signals or temporal_signals or state_signals)
    has_primary = primary is not None

    if not has_primary:
        return CONTEXT_INSUFFICIENT
    if total_context_chars >= _MIN_SUFFICIENT_CONTEXT_CHARS and has_signals:
        return CONTEXT_SUFFICIENT
    if total_context_chars >= 50 or has_signals:
        return CONTEXT_PARTIAL
    return CONTEXT_INSUFFICIENT


# ═══════════════════════════════════════════════════════════════════════
# EvidenceContextV1 builder
# ═══════════════════════════════════════════════════════════════════════

def build_evidence_context(
    fact_id: str,
    document_id: str,
    excerpt: str,
    segments: list[EvidenceSegmentV1],
    *,
    evidence_id: str = "",
) -> EvidenceContextV1:
    """Build an EvidenceContextV1 package for a single fact.

    The excerpt is preserved EXACTLY (no truncation, no extension) — it
    is the evidence_excerpt field. Context is added SEPARATELY as
    context_before / context_after.

    Args:
        fact_id: the fact's ID (preserved)
        document_id: the document's ID (preserved)
        excerpt: the original evidence excerpt (PRESERVED EXACTLY)
        segments: V37.2 structural segments (post purpose-filter)
        evidence_id: optional link to existing Evidence.evidence_id

    Returns:
        EvidenceContextV1 with all fields populated.
    """
    # Find the primary segment containing the excerpt
    primary = find_primary_segment(segments, excerpt)

    # Build context window
    if primary is not None:
        ctx_ids, ctx_before, ctx_after, before_segs, after_segs = build_context_window(
            segments, primary
        )
        heading_context = primary.heading_context
        table_context = primary.table_id
        row_label = primary.row_label
        column_label = primary.column_label
        list_context = primary.list_depth if primary.list_depth > 0 else None
    else:
        ctx_ids = []
        ctx_before = ""
        ctx_after = ""
        before_segs = []
        after_segs = []
        heading_context = None
        table_context = None
        row_label = None
        column_label = None
        list_context = None

    # Scan for signals across the FULL context (before + excerpt + after)
    full_context_text = " ".join([
        ctx_before,
        excerpt,  # include the excerpt itself
        ctx_after,
    ])

    entity_signals = _detect_entity_signals(full_context_text)
    temporal_signals = _detect_temporal_signals(full_context_text)
    state_signals = _detect_state_signals(full_context_text)

    # Provenance: which segments contributed which signals
    entity_prov = []
    temp_prov = []
    state_prov = []
    all_ctx_segs = before_segs + ([primary] if primary else []) + after_segs
    for seg in all_ctx_segs:
        seg_text = seg.text or ""
        if not seg_text:
            continue
        e_sigs = _detect_entity_signals(seg_text)
        t_sigs = _detect_temporal_signals(seg_text)
        s_sigs = _detect_state_signals(seg_text)
        if e_sigs:
            entity_prov.append({"segment_id": seg.segment_id, "signals": [s[0] for s in e_sigs]})
        if t_sigs:
            temp_prov.append({"segment_id": seg.segment_id, "signals": [s[0] for s in t_sigs]})
        if s_sigs:
            state_prov.append({"segment_id": seg.segment_id, "signals": [s[0] for s in s_sigs]})

    # Classify context quality
    quality = classify_context_quality(
        ctx_before, ctx_after, primary,
        entity_signals, temporal_signals, state_signals,
    )

    return EvidenceContextV1(
        fact_id=fact_id,
        document_id=document_id,
        evidence_id=evidence_id,
        primary_segment_id=primary.segment_id if primary else None,
        context_segment_ids=ctx_ids,
        context_before=ctx_before,
        evidence_excerpt=excerpt,  # PRESERVED EXACTLY
        context_after=ctx_after,
        heading_context=heading_context,
        table_context=table_context,
        row_label=row_label,
        column_label=column_label,
        list_context=list_context,
        entity_signals=[{"entity": e, "match": m} for e, m in entity_signals],
        temporal_signals=[{"type": t, "match": m} for t, m in temporal_signals],
        state_signals=[{"state": s, "match": m} for s, m in state_signals],
        context_quality=quality,
        entity_signal_provenance=entity_prov,
        temporal_signal_provenance=temp_prov,
        state_signal_provenance=state_prov,
    )


def build_contexts_for_io(io: dict, segments: list[EvidenceSegmentV1]) -> list[EvidenceContextV1]:
    """Build context packages for all facts in an IO.

    The IO is expected to have keys: io_id, document_id, facts, evidence.
    Each fact in facts[] should have: fact_id, excerpt (or fall back to
    evidence[].excerpt).
    """
    contexts = []
    facts = io.get("facts", [])
    evidence = io.get("evidence", [])
    # Build fact_id → evidence_id map
    fact_to_ev = {}
    for ev in evidence:
        fid = ev.get("fact_id", "")
        if fid:
            fact_to_ev[fid] = ev.get("evidence_id", ev.get("excerpt", "")[:64])  # fallback if no evidence_id

    for f in facts:
        fact_id = f.get("fact_id", "")
        excerpt = f.get("excerpt", "")
        if not excerpt and evidence:
            # Fall back to evidence excerpt
            for ev in evidence:
                if ev.get("fact_id") == fact_id:
                    excerpt = ev.get("excerpt", "")
                    break
        ev_id = fact_to_ev.get(fact_id, "")
        ctx = build_evidence_context(
            fact_id=fact_id,
            document_id=io.get("document_id", ""),
            excerpt=excerpt,
            segments=segments,
            evidence_id=ev_id,
        )
        contexts.append(ctx)
    return contexts


__all__ = [
    "EvidenceContextV1",
    "CONTEXT_SUFFICIENT",
    "CONTEXT_PARTIAL",
    "CONTEXT_INSUFFICIENT",
    "find_primary_segment",
    "build_context_window",
    "classify_context_quality",
    "build_evidence_context",
    "build_contexts_for_io",
]
