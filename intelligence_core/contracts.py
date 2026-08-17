"""Canonical domain contracts — Architecture V1.1 (D1-D10).

Every field here maps to an approved decision:
  D1 document 3-level identity / D2 immutable versioned facts+events /
  D3 Insight deferred (absent by design) / D4 6-field temporal tuple /
  D5 SourcePublication vs Delivery / D6 institution identity /
  D7 IO-first / D8 simulation contracts / D9 append-only / D10 boundary.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class ObjState(str, Enum):
    # D2: exactly three states; RETRACTED is a supersession reason, not a state.
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class SupersessionReason(str, Enum):
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    SOURCE_REVISION = "SOURCE_REVISION"
    RETRACTED_BY_SOURCE = "RETRACTED_BY_SOURCE"
    ENTITY_CORRECTION = "ENTITY_CORRECTION"
    RE_EXTRACTION = "RE_EXTRACTION"


class TZStatus(str, Enum):
    EXPLICIT_ZONE = "EXPLICIT_ZONE"        # e.g. +0000 / GMT
    EXPLICIT_OFFSET = "EXPLICIT_OFFSET"    # e.g. -0500
    NAIVE_LOCAL = "NAIVE_LOCAL"            # datetime without zone
    UNKNOWN = "UNKNOWN"
    DATE_ONLY = "DATE_ONLY"


class NormBasis(str, Enum):
    EXPLICIT_SOURCE_TIMEZONE = "EXPLICIT_SOURCE_TIMEZONE"
    SOURCE_DOCUMENT_METADATA = "SOURCE_DOCUMENT_METADATA"
    JURISDICTION_RULE = "JURISDICTION_RULE"
    INFERRED = "INFERRED"
    NONE = "NONE"


# D4 rule 3: ordering participation requires non-NULL utc AND qualifying basis.
ORDERING_BASES = {NormBasis.EXPLICIT_SOURCE_TIMEZONE,
                  NormBasis.SOURCE_DOCUMENT_METADATA,
                  NormBasis.JURISDICTION_RULE}


class Semantics(str, Enum):
    PUBLICATION = "publication"
    UPDATE = "update"
    EFFECTIVE = "effective"
    REPORTING_PERIOD = "reporting_period"
    DOCUMENT_DATE = "document_date"
    EVENT_OCCURRENCE = "event_occurrence"
    UNKNOWN = "unknown"


class ProvenanceSource(str, Enum):
    RSS_PUBDATE = "rss_pubdate"
    HTML_TIME_ATTR = "html_time_attr"
    META_DATE = "meta_date"
    URL_DATE = "url_date"
    RENDERED_TEXT = "rendered_text"
    JS_TITLE = "js_title"
    FILENAME = "filename"
    FILE_METADATA = "file_metadata"


@dataclass
class TemporalTuple:  # D4
    original_value: str
    timezone_status: TZStatus
    normalized_utc: Optional[str] = None            # NULL when zone unknown
    normalization_basis: NormBasis = NormBasis.NONE
    timestamp_semantics: Semantics = Semantics.UNKNOWN
    provenance_source: ProvenanceSource = ProvenanceSource.RENDERED_TEXT

    def ordering_participating(self) -> bool:
        return (self.normalized_utc is not None
                and self.normalization_basis in ORDERING_BASES)

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class Institution:  # D6
    institution_id: str                       # INST-<slug>-<n>, Core-issued
    legal_entity: str
    jurisdiction: str
    institutional_class: str
    verified_domains: list = field(default_factory=list)   # [{domain, verification_evidence}]
    brands: list = field(default_factory=list)             # recorded, NEVER identity
    status: str = "ACTIVE"
    history: list = field(default_factory=list)            # append-only metadata history

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class Source:  # D6/D10
    source_id: str
    institution_id: str
    source_path: str
    source_type: str
    acquisition_method: str = "direct_http"   # minimum core: only this
    configuration_version: str = "1"
    status: str = "PENDING"

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class Document:  # D1 logical level
    document_id: str
    canonical_url: str
    aliases: list = field(default_factory=list)
    source_id: str = ""
    publication_tuples: list = field(default_factory=list)  # [TemporalTuple dicts]
    created_at: str = ""
    status: str = "ACTIVE"

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class Representation:  # D1 content level
    representation_id: str
    document_id: str
    content_sha256: str
    retrieved_at: str = ""
    retrieval_event_id: str = ""
    content_type: str = ""
    raw_location: str = ""                    # blob path

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class RetrievalEvent:  # D1 acquisition act
    retrieval_event_id: str
    method: str
    adapter_class: str = "direct_http"
    requested_url: str = ""
    final_url: str = ""
    http_status: int = 0
    retrieved_at: str = ""
    run_id: str = ""

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class Fact:  # D2 immutable row; corrections append new versions
    fact_id: str
    fact_version: int
    representation_id: str
    document_id: str
    metric: str
    value: str
    raw_value: str = ""
    pattern_ref: str = ""
    occurrence: int = 0
    excerpt: str = ""
    status: ObjState = ObjState.ACTIVE
    supersedes: Optional[str] = None           # "fact_id:vN"
    superseded_by: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self); d["status"] = self.status.value; return d


@dataclass
class Event:  # D2 derivation-versioned
    event_id: str
    event_version: int
    document_id: str
    event_type: str
    fact_version_snapshot: list = field(default_factory=list)  # [{fact_id, fact_version}]
    occurrence: int = 0
    status: ObjState = ObjState.ACTIVE
    derived_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self); d["status"] = self.status.value; return d


@dataclass
class Evidence:  # binds to the EXACT representation (D1 rule 5)
    evidence_id: str
    event_or_fact_id: str
    representation_id: str
    location: str = ""
    excerpt: str = ""
    provenance_ref: str = ""                   # temporal tuple / source publication ref
    created_at: str = ""

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class TemporalDataProjection:  # K2 — D4 publication_tuples projected to IO emission
    """K2 projection of D4 Document.publication_tuples into the IO.

    Per directive CORE_SEMANTIC_PROMOTION_K1_K2_V1 §4-5:
      - publication_time: normalized_utc of the tuple where
        timestamp_semantics == "publication" (or first tuple if none match).
      - publication_time_raw: original_value of the same tuple.
      - publication_timezone_status: timezone_status of the same tuple.
      - reference_period: normalized_utc of the tuple where
        timestamp_semantics == "reporting_period" (D4 distinction).
      - reference_period_normalized_utc: same as reference_period
        (kept as a separate field for explicit D4-compliance clarity).

    D4 semantics for missing values (§5):
      - null = NOT_APPLICABLE / UNKNOWN (never fabricated).
      - A date-only reference period is preserved as-is, NOT converted to UTC.
      - A missing timezone is preserved as None, NOT inferred.
    """
    publication_time: Optional[str] = None
    publication_time_raw: Optional[str] = None
    publication_timezone_status: Optional[str] = None
    reference_period: Optional[str] = None
    reference_period_normalized_utc: Optional[str] = None

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class IntelligenceObject:  # D7 IO-first canonical output
    io_id: str
    version: int
    event_id: str
    event_version: int
    headline: str
    chain: list = field(default_factory=list)  # traceability: facts->evidence->rep->doc->source
    created_at: str = ""
    # K1 (CORE_SEMANTIC_PROMOTION_K1_K2_V1 §3): direct copy from Event.event_type.
    # No inference, no headline parsing, no source-specific logic.
    event_type: str = ""
    # K2 (CORE_SEMANTIC_PROMOTION_K1_K2_V1 §4): projected from
    # Document.publication_tuples per D4 semantics. null = NOT_APPLICABLE / UNKNOWN.
    temporal_data: Optional[TemporalDataProjection] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Delivery:  # D5 output act / D8 Contract C
    delivery_id: str
    intelligence_object_id: str
    version: int
    destination: str
    status: str = "PENDING"                    # PENDING | DELIVERED | FAILED
    idempotency_key: str = ""
    created_at: str = ""

    def to_dict(self) -> dict: return asdict(self)
