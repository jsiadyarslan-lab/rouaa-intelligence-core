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
    # V37.2 — Hybrid Structural Evidence (Option B). Both fields nullable
    # for backward compatibility with V37.1 evidence records. New evidence
    # records produced via evidence_selection.select_evidence_segment()
    # populate these; old evidence records (Phase 0) carry None — both
    # remain valid. See docs/architecture/ROUAA_CORE_EVIDENCE_SEGMENT_ARCHITECTURE_V1.md §8.
    segment_id: Optional[str] = None           # links to EvidenceSegmentV1.segment_id
    segment_type: Optional[str] = None         # for audit without segment lookup

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class TemporalTupleProjection:
    """A single D4 TemporalTuple projected to IO emission — ALL 6 D4 fields preserved.

    Per CORE_K2_D4_MULTIPLICITY_CLOSURE_V1: D4 permits multiple tuples with
    different timestamp_semantics, provenance_source, timezone_status, etc.
    The IO must not silently collapse distinct D4 tuples. This dataclass
    represents ONE tuple in the temporal_tuples[] array.
    """
    original_value: Optional[str] = None
    timezone_status: Optional[str] = None
    normalized_utc: Optional[str] = None
    normalization_basis: Optional[str] = None
    timestamp_semantics: Optional[str] = None
    provenance_source: Optional[str] = None

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class TemporalDataProjection:  # K2 — D4 publication_tuples projected to IO emission (D4-faithful + multiplicity-preserving)
    """K2 projection of D4 Document.publication_tuples into the IO.

    Per CORE_K2_D4_MULTIPLICITY_CLOSURE_V1: D4 permits multiple TemporalTuples
    per Document (e.g. conflicting publication dates from RSS vs HTML, multiple
    reporting periods, or tuples with different semantics like document_date,
    update, effective, event_occurrence). The previous projection collapsed
    this multiplicity into 2 fixed slots (publication_* + reference_period_*),
    silently discarding additional tuples. This closure adds a
    `temporal_tuples` array that preserves ALL D4 tuples in their original order.

    D4 TemporalTuple fields (contracts.py):
      1. original_value       — the raw timestamp string from the source
      2. timezone_status      — D4 TZStatus enum (EXPLICIT_ZONE, EXPLICIT_OFFSET,
                                 NAIVE_LOCAL, DATE_ONLY, UNKNOWN)
      3. normalized_utc       — ISO 8601 UTC, or null when zone unknown
      4. normalization_basis  — D4 NormBasis enum (EXPLICIT_SOURCE_TIMEZONE,
                                 SOURCE_DOCUMENT_METADATA, JURISDICTION_RULE,
                                 INFERRED, NONE) — determines ordering participation
      5. timestamp_semantics   — D4 Semantics enum (publication, reporting_period,
                                 update, effective, document_date, event_occurrence, unknown)
      6. provenance_source     — D4 ProvenanceSource enum (rss_pubdate, html_time_attr,
                                 meta_date, url_date, rendered_text, js_title,
                                 filename, file_metadata)

    STRUCTURE:
      - temporal_tuples: list[TemporalTupleProjection] — ALL D4 tuples preserved
        in their original order. Cardinality == Document.publication_tuples.length.
        No tuple is silently discarded.
      - publication_*: convenience accessor for the FIRST tuple with
        timestamp_semantics == "publication" (backward-compat with K1/K2 promotion).
      - reference_period_*: convenience accessor for the FIRST tuple with
        timestamp_semantics == "reporting_period" (backward-compat).

    Backward compat: the 13 convenience fields from K2_D4_FIDELITY_CLOSURE_V1
    are preserved. The temporal_tuples array is ADDITIVE — no consumer breaks.
    Consumers that only read publication_* / reference_period_* continue to work;
    consumers that need full D4 multiplicity read temporal_tuples[].

    D4 semantics for missing values (§5):
      - null = NOT_APPLICABLE / UNKNOWN (never fabricated).
      - A date-only reference period is preserved as-is, NOT converted to UTC.
      - A missing timezone is preserved as None, NOT inferred.
      - normalization_basis = NONE when D4 says the timezone is not safely
        normalizable (normalized_utc = null in that case).
    """
    # === FULL D4 CARDINALITY (added per CORE_K2_D4_MULTIPLICITY_CLOSURE_V1) ===
    # ALL D4 TemporalTuples preserved in original order. No collapse.
    temporal_tuples: list = field(default_factory=list)  # list[TemporalTupleProjection]

    # === Publication tuple — convenience accessor (backward-compat from K1/K2) ===
    # Points to the FIRST tuple with timestamp_semantics == "publication".
    # If multiple publication tuples exist, temporal_tuples[] preserves them all.
    publication_time: Optional[str] = None              # D4 normalized_utc
    publication_time_raw: Optional[str] = None          # D4 original_value
    publication_timezone_status: Optional[str] = None  # D4 timezone_status
    publication_normalization_basis: Optional[str] = None   # D4 normalization_basis
    publication_timestamp_semantics: Optional[str] = None   # D4 timestamp_semantics
    publication_provenance_source: Optional[str] = None     # D4 provenance_source

    # === Reference period tuple — convenience accessor (backward-compat from K1/K2) ===
    # Points to the FIRST tuple with timestamp_semantics == "reporting_period".
    # If multiple reporting_period tuples exist, temporal_tuples[] preserves them all.
    reference_period: Optional[str] = None                    # D4 normalized_utc
    reference_period_normalized_utc: Optional[str] = None     # D4 normalized_utc (alias)
    reference_period_raw: Optional[str] = None                # D4 original_value
    reference_period_timezone_status: Optional[str] = None    # D4 timezone_status
    reference_period_normalization_basis: Optional[str] = None # D4 normalization_basis
    reference_period_timestamp_semantics: Optional[str] = None # D4 timestamp_semantics
    reference_period_provenance_source: Optional[str] = None   # D4 provenance_source

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


# ═══════════════════════════════════════════════════════════════════════
# V46 — Evidence Context Recovery (additive, optional, non-breaking)
# ═══════════════════════════════════════════════════════════════════════
# Per V46 directive §9: a deterministic context package around existing
# evidence. Does NOT replace Evidence; creates a contextual layer that
# downstream semantic enrichment can read. All fields nullable so older
# evidence without context packages remain valid.

@dataclass
class EvidenceContextV1:
    """V46 — Context package around an existing Evidence record.

    Per V46 §9: minimum fields are fact_id, document_id,
    primary_segment_id, context_segment_ids, context_before,
    evidence_excerpt, context_after, heading_context, table_context,
    entity_signals, temporal_signals, state_signals, context_quality.
    """
    fact_id: str
    document_id: str
    evidence_id: str = ""                       # links to existing Evidence.evidence_id (preserved)
    primary_segment_id: Optional[str] = None   # the segment containing the excerpt
    context_segment_ids: list = field(default_factory=list)  # structural segment IDs in context window
    context_before: str = ""                    # text from preceding structural segments
    evidence_excerpt: str = ""                  # the original excerpt (UNCHANGED from Evidence.excerpt)
    context_after: str = ""                     # text from following structural segments
    heading_context: Optional[str] = None       # nearest ancestor heading text
    table_context: Optional[str] = None         # table_id if excerpt is in a table, else None
    row_label: Optional[str] = None             # table row label if applicable
    column_label: Optional[str] = None          # table column label if applicable
    list_context: Optional[int] = None          # list depth if excerpt is in a list, else None
    entity_signals: list = field(default_factory=list)     # institution names found in context
    temporal_signals: list = field(default_factory=list)   # date/period patterns found in context
    state_signals: list = field(default_factory=list)      # event-state signal words found in context
    context_quality: str = "CONTEXT_INSUFFICIENT"  # SUFFICIENT | PARTIAL | INSUFFICIENT
    # Provenance — which segments contributed to each signal
    entity_signal_provenance: list = field(default_factory=list)
    temporal_signal_provenance: list = field(default_factory=list)
    state_signal_provenance: list = field(default_factory=list)

    def to_dict(self) -> dict: return asdict(self)


@dataclass
class SemanticClaimV1:
    """A semantic assertion with a fact-local structural proof.

    `publisher_institution` and `subject_entity` are intentionally separate.
    Neither source identity nor a neighbouring segment can confirm the subject
    of a fact.  Consumers must use only CONFIRMED claims for event semantics.
    """
    claim_type: str
    value: str
    status: str
    fact_id: str
    evidence_id: str
    segment_id: Optional[str] = None
    provenance: str = ""

    def to_dict(self) -> dict: return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# V47C — Publisher Institution Context Layer (additive, optional, non-breaking)
# ═══════════════════════════════════════════════════════════════════════
# Per V47C directive §4: a deterministic canonical Publisher Institution
# layer that identifies the institution responsible for the source/document
# WITHOUT ever promoting publisher identity into subject_entity.
#
# The SUBJECT ENTITY FIREWALL (§9) is mandatory: publisher_institution
# CONFIRMED does NOT promote subject_entity. publisher_institution and
# subject_entity are independent fields.

@dataclass
class PublisherInstitutionV1:
    """V47C — Canonical Publisher Institution for a source/document.

    Per V47C §4: identifies the institution RESPONSIBLE FOR PUBLISHING
    the source/document. This is NOT the subject entity of any event.

    Per V47C §9 (Subject Entity Firewall):
      publisher_institution.status == CONFIRMED does NOT promote
      subject_entity status. The two fields are independent.

    Confidence (§4): HIGH / MEDIUM / LOW — explicitly documented
    deterministic scale, NOT a hallucinated probability.
    """
    publisher_institution_id: str
    canonical_name: str
    institution_type: str = "OTHER"   # CENTRAL_BANK | STATISTICAL_AGENCY | REGULATOR | GOVERNMENT_MINISTRY | MARKET_OPERATOR | EXCHANGE | SECURITIES_REGULATOR | CORPORATE | INTERNATIONAL_ORGANIZATION | OTHER
    jurisdiction: Optional[str] = None
    source_ids: list = field(default_factory=list)
    confidence: str = "MEDIUM"  # HIGH | MEDIUM | LOW
    status: str = "NOT_FOUND"   # CONFIRMED | AMBIGUOUS | NOT_FOUND
    # Per §10: publisher support provenance
    publisher_support_source_id: Optional[str] = None
    publisher_support_document_id: Optional[str] = None
    publisher_support_segment_id: Optional[str] = None
    publisher_support_method: Optional[str] = None
    # Allowed methods (§10): SOURCE_REGISTRY | SOURCE_DOMAIN |
    # DOCUMENT_PUBLISHER_METADATA | DOCUMENT_EXPLICIT_PUBLISHER |
    # DETERMINISTIC_ALIAS
    # Forbidden methods: HEADLINE_TEMPLATE | EVENT_TYPE | FACT_VALUE | GT_METADATA
    aliases: list = field(default_factory=list)
    canonical_url: Optional[str] = None  # source domain / canonical URL

    def to_dict(self) -> dict: return asdict(self)
