"""Extraction semantics — carried over from scripts/pipeline/extractor.py @ 9298162.

PATTERN_TYPE_METADATA: rate family normalized; everything else identity fallback.
Gate-5-proven semantics (FED_ENF f16bc00, Eurostat 3454603, BaFin 282de0f).
"""
from __future__ import annotations
import re
from .contracts import Fact, ObjState
from .identity import fact_id as make_fact_id

# Verbatim metric mapping from extractor.py lines 389-433 (rate family only).
PATTERN_TYPE_METADATA = {
    "rate_value":             {"metric": "policy_rate"},
    "rate_range":             {"metric": "policy_rate_range"},
    "rate_maintain":          {"metric": "rate_decision"},
    "rate_action":            {"metric": "rate_decision"},
    "rate_action_with_value": {"metric": "rate_decision"},
}


def normalize_metric(pattern_type: str) -> tuple[str, bool]:
    """Returns (metric, was_normalized). Non-rate types: identity fallback (as coded)."""
    meta = PATTERN_TYPE_METADATA.get(pattern_type)
    if meta:
        return meta["metric"], True
    return pattern_type, False


def extract_facts(text: str, patterns: list, representation_id: str,
                  document_id: str, created_at: str = "") -> list[Fact]:
    """patterns: [(regex_source, pattern_type)]. Deterministic order; occurrence per (pattern, metric)."""
    facts: list[Fact] = []
    occurrences: dict[tuple, int] = {}
    for regex_src, pattern_type in patterns:
        metric, _ = normalize_metric(pattern_type)
        rx = re.compile(regex_src)
        for m in rx.finditer(text):
            key = (pattern_type, metric)
            occurrences[key] = occurrences.get(key, 0) + 1
            occ = occurrences[key]
            start = max(0, m.start() - 110)
            excerpt = text[start:m.end() + 40].strip()
            fid = make_fact_id(representation_id, metric, pattern_type, occ)
            facts.append(Fact(
                fact_id=fid, fact_version=1,
                representation_id=representation_id, document_id=document_id,
                metric=metric, value=m.group(1) if m.groups() else "",
                raw_value=m.group(0), pattern_ref=pattern_type, occurrence=occ,
                excerpt=excerpt, status=ObjState.ACTIVE, created_at=created_at))
    return facts
