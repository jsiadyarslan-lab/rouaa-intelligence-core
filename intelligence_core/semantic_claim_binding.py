"""V47 -- minimum event-local binding for semantic claims.

This module is additive.  It does not alter extraction, event detection, or
existing evidence.  It turns V46 context signals into claims only when the
matched wording occurs in the primary segment that contains the fact excerpt.
"""
from __future__ import annotations

from .contracts import EvidenceContextV1, SemanticClaimV1

CONFIRMED = "CONFIRMED"
NOT_FOUND = "NOT_FOUND"


def _present_in_primary(match: str, primary_segment_text: str) -> bool:
    return bool(match and primary_segment_text and match.casefold() in primary_segment_text.casefold())


def _claim(claim_type: str, value: str, context: EvidenceContextV1, primary_text: str, match: str,
           bound: bool | None = None) -> SemanticClaimV1:
    bound = _present_in_primary(match, primary_text) if bound is None else bound
    return SemanticClaimV1(
        claim_type=claim_type,
        value=value if bound else "UNKNOWN",
        status=CONFIRMED if bound else NOT_FOUND,
        fact_id=context.fact_id,
        evidence_id=context.evidence_id,
        segment_id=context.primary_segment_id if bound else None,
        provenance=f"primary_segment:{context.primary_segment_id}" if bound else "",
    )


def bind_subject_entities(context: EvidenceContextV1, primary_segment_text: str) -> list[SemanticClaimV1]:
    """Confirm entity candidates only in the fact's primary segment.

    A neighbouring heading or a source/publisher name remains context, not a
    subject-entity claim.
    """
    return [_claim("subject_entity", signal["entity"], context, primary_segment_text, signal.get("match", ""))
            for signal in context.entity_signals]


def bind_temporal_claims(context: EvidenceContextV1, primary_segment_text: str) -> list[SemanticClaimV1]:
    return [_claim("temporal", signal["match"], context, primary_segment_text, signal["match"])
            for signal in context.temporal_signals]


def bind_event_state_claims(context: EvidenceContextV1, primary_segment_text: str) -> list[SemanticClaimV1]:
    # V46's signal record contains the state, not its exact match.  A state is
    # thus only eligible when the primary segment has an explicit state signal.
    explicit = ("increased", "raised", "decreased", "reduced", "revised", "amended",
                "effective", "enforced", "pending", "maintained", "announced", "published")
    primary_lower = (primary_segment_text or "").casefold()
    claims = []
    for signal in context.state_signals:
        has_local_signal = any(word in primary_lower for word in explicit)
        claims.append(_claim("event_state", signal["state"], context, primary_segment_text,
                             "", bound=has_local_signal))
    return claims
