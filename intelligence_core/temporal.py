"""D4 — temporal semantics engine. No silent inference; NULL when unknown."""
from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from .contracts import (TemporalTuple, TZStatus, NormBasis, Semantics,
                        ProvenanceSource, ORDERING_BASES)

_ISO_NAIVE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?))?$")
_RFC822 = re.compile(r"^\w{3},\s+.+\s+\d{4}\s+")


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_rfc822_pubdate(value: str,
                         semantics: Semantics = Semantics.PUBLICATION) -> TemporalTuple:
    """RSS pubDate e.g. 'Mon, 10 Aug 2026 13:10:04 -0500' -> explicit offset/zone."""
    dt = parsedate_to_datetime(value.strip())
    if dt.tzinfo is None:  # malformed RFC-822 without zone
        return TemporalTuple(value, TZStatus.UNKNOWN, None, NormBasis.NONE,
                             semantics, ProvenanceSource.RSS_PUBDATE)
    offset = dt.utcoffset() or timedelta(0)
    status = TZStatus.EXPLICIT_ZONE if offset == timedelta(0) else TZStatus.EXPLICIT_OFFSET
    return TemporalTuple(value, status, _utc_iso(dt), NormBasis.EXPLICIT_SOURCE_TIMEZONE,
                         semantics, ProvenanceSource.RSS_PUBDATE)


def parse_iso_or_date(value: str,
                      semantics: Semantics = Semantics.PUBLICATION,
                      provenance: ProvenanceSource = ProvenanceSource.HTML_TIME_ATTR) -> TemporalTuple:
    """ISO-like values. Aware (Z / +HH:MM) -> explicit; naive -> NAIVE_LOCAL/DATE_ONLY, utc NULL."""
    v = value.strip()
    m = _ISO_NAIVE.match(v)
    if not m:
        return TemporalTuple(value, TZStatus.UNKNOWN, None, NormBasis.NONE,
                             Semantics.UNKNOWN, provenance)
    date_part, time_part = m.group(1), m.group(2)
    if time_part is None:  # date-only
        return TemporalTuple(value, TZStatus.DATE_ONLY, None, NormBasis.NONE,
                             semantics, provenance)
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        status = TZStatus.EXPLICIT_ZONE if dt.utcoffset() == timedelta(0) else TZStatus.EXPLICIT_OFFSET
        return TemporalTuple(value, status, _utc_iso(dt),
                             NormBasis.SOURCE_DOCUMENT_METADATA, semantics, provenance)
    # D4 rules 1-2: naive -> no normalized_utc, no inference.
    return TemporalTuple(value, TZStatus.NAIVE_LOCAL, None, NormBasis.NONE,
                         semantics, provenance)


class JurisdictionRule:
    """D4 rule 4: recorded, reviewable rule with fixed offset (no tz database needed)."""
    def __init__(self, name: str, utc_offset_hours: float, approved: bool, evidence: str):
        self.name, self.offset = name, timedelta(hours=utc_offset_hours)
        self.approved, self.evidence = approved, evidence


def apply_jurisdiction_rule(t: TemporalTuple, rule: JurisdictionRule) -> TemporalTuple:
    """Only NAIVE_LOCAL tuples eligible. Unapproved rule => INFERRED, still excluded from ordering."""
    if t.timezone_status != TZStatus.NAIVE_LOCAL:
        return t
    m = _ISO_NAIVE.match(t.original_value.strip())
    if not m or m.group(2) is None:
        return t
    if not rule.approved:
        return TemporalTuple(t.original_value, TZStatus.NAIVE_LOCAL, None,
                             NormBasis.INFERRED, t.timestamp_semantics, t.provenance_source)
    dt = datetime.fromisoformat(t.original_value.strip()).replace(tzinfo=timezone(rule.offset))
    return TemporalTuple(t.original_value, t.timezone_status, _utc_iso(dt),
                         NormBasis.JURISDICTION_RULE, t.timestamp_semantics, t.provenance_source)


def ordering_filter(tuples: list[TemporalTuple]) -> list[TemporalTuple]:
    """D4 rule 3: only non-NULL utc with qualifying basis participates in cross-JURISDICTION ordering."""
    return [t for t in tuples
            if t.normalized_utc is not None and t.normalization_basis in ORDERING_BASES]
