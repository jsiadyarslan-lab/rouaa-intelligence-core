"""D7/D8 — IntelligenceObject (canonical output) + Delivery (idempotent output act).

K1/K2 Promotion (CORE_SEMANTIC_PROMOTION_K1_K2_V1):
  - K1 event_type: direct copy from Event.event_type into IntelligenceObject
  - K2 temporal_data: projected from Document.publication_tuples per D4

No inference. No fabrication. null = NOT_APPLICABLE / UNKNOWN per D4 semantics.
"""
from __future__ import annotations
from .contracts import IntelligenceObject, Delivery, TemporalDataProjection, TemporalTupleProjection
from .identity import io_id as make_io_id, delivery_id as make_delivery_id
from .detect import build_headline


def build_intelligence_object(store, event_row: dict, source_name: str = "",
                              created_at: str = "") -> IntelligenceObject:
    """IO-first abstraction with the FULL traceability chain embedded (D7):
    event -> facts(+versions) -> evidence -> representation(sha) -> document -> source.

    K1 (CORE_SEMANTIC_PROMOTION_K1_K2_V1 §3): event_type is copied DIRECTLY
    from event_row["event_type"]. No inference, no headline parsing.

    K2 (§4): temporal_data is projected from the FIRST fact's Document
    publication_tuples per D4 semantics. The publication tuple is the one
    with timestamp_semantics=="publication"; if none, the first tuple is
    used. The reference_period tuple is the one with
    timestamp_semantics=="reporting_period" (D4 distinction).
    """
    chain = []
    doc_for_k2 = None  # capture for K2 projection
    for ref in event_row["fact_version_snapshot"]:
        fact = store.fact_row(ref["fact_id"], ref["fact_version"])
        if fact is None:
            raise ValueError(f"chain broken: {ref}")
        rep = store.latest_by_id("representations", "representation_id").get(fact["representation_id"])
        doc = store.latest_by_id("documents", "document_id").get(fact["document_id"])
        if doc_for_k2 is None and doc is not None:
            doc_for_k2 = doc  # use first fact's document for K2
        ev_rows = [e for e in store.iter("evidence") if e["event_or_fact_id"] == fact["fact_id"]]
        src = None
        if doc:
            src = store.latest_by_id("sources", "source_id").get(doc.get("source_id", ""))
        chain.append({
            "fact": {"fact_id": fact["fact_id"], "fact_version": fact["fact_version"],
                     "metric": fact["metric"], "value": fact["value"]},
            "evidence": [{"evidence_id": e["evidence_id"], "excerpt": e["excerpt"][:120],
                          "representation_id": e["representation_id"]} for e in ev_rows],
            "representation": {"representation_id": fact["representation_id"],
                               "content_sha256": (rep or {}).get("content_sha256")},
            "document": {"document_id": fact["document_id"],
                         "canonical_url": (doc or {}).get("canonical_url")},
            "source": {"source_id": (doc or {}).get("source_id"),
                       "institution_id": (src or {}).get("institution_id")}})

    # K1: event_type — direct copy from Event.event_type
    event_type = event_row.get("event_type", "")

    # K2: temporal_data — projected from Document.publication_tuples per D4
    temporal_data = _project_temporal_data(doc_for_k2)

    io = IntelligenceObject(
        io_id=make_io_id(event_row["event_id"], event_row["event_version"]),
        version=1, event_id=event_row["event_id"],
        event_version=event_row["event_version"],
        headline=build_headline_from_row(event_row, source_name),
        chain=chain, created_at=created_at,
        event_type=event_type,
        temporal_data=temporal_data)
    return io


def _project_temporal_data(doc: dict | None) -> TemporalDataProjection | None:
    """Project D4 Document.publication_tuples into K2 TemporalDataProjection.

    Per CORE_K2_D4_FIDELITY_CLOSURE_V1 §3: ALL 6 D4 TemporalTuple fields
    are now preserved for both publication and reference_period tuples.
    No D4 field is dropped. No semantic transformation.

    Per CORE_SEMANTIC_PROMOTION_K1_K2_V1 §4-5 (original K2 promotion):
      - publication_time = normalized_utc of the tuple where
        timestamp_semantics == "publication" (or first tuple if none match).
      - reference_period = normalized_utc of the tuple where
        timestamp_semantics == "reporting_period" (D4 §9 distinction).

    Per §5: null = NOT_APPLICABLE / UNKNOWN. Never fabricate. Never infer
    timezone. Never convert a date-only reference period to UTC.
    """
    if not doc:
        return None
    tuples = doc.get("publication_tuples") or []
    if not tuples:
        return None

    # Find publication tuple: timestamp_semantics == "publication"
    pub_tuple = next((t for t in tuples
                      if t.get("timestamp_semantics") == "publication"), None)
    if pub_tuple is None:
        # Fall back to first tuple (D4: missing semantics = UNKNOWN, but
        # we surface the first tuple's values rather than fabricate None).
        pub_tuple = tuples[0]

    # Find reference_period tuple: timestamp_semantics == "reporting_period"
    ref_tuple = next((t for t in tuples
                      if t.get("timestamp_semantics") == "reporting_period"), None)

    # Per CORE_K2_D4_FIDELITY_CLOSURE_V1: surface ALL 6 D4 fields for both tuples.
    # Per CORE_K2_D4_MULTIPLICITY_CLOSURE_V1: surface ALL tuples in temporal_tuples[].
    # No field is dropped. No semantic transformation. No cardinality collapse.

    # Build temporal_tuples[] — ALL D4 tuples preserved in original order.
    temporal_tuples_list = [
        TemporalTupleProjection(
            original_value=t.get("original_value"),
            timezone_status=t.get("timezone_status"),
            normalized_utc=t.get("normalized_utc"),
            normalization_basis=t.get("normalization_basis"),
            timestamp_semantics=t.get("timestamp_semantics"),
            provenance_source=t.get("provenance_source"),
        )
        for t in tuples
    ]

    return TemporalDataProjection(
        # FULL D4 CARDINALITY — all tuples preserved (per MULTIPLICITY_CLOSURE):
        temporal_tuples=temporal_tuples_list,
        # Publication tuple — backward-compat fields (K1/K2 promotion):
        publication_time=pub_tuple.get("normalized_utc"),
        publication_time_raw=pub_tuple.get("original_value"),
        publication_timezone_status=pub_tuple.get("timezone_status"),
        # Publication tuple — D4-faithful fields ADDED per closure (was dropped):
        publication_normalization_basis=pub_tuple.get("normalization_basis"),
        publication_timestamp_semantics=pub_tuple.get("timestamp_semantics"),
        publication_provenance_source=pub_tuple.get("provenance_source"),

        # Reference period tuple — backward-compat fields (K1/K2 promotion):
        reference_period=ref_tuple.get("normalized_utc") if ref_tuple else None,
        reference_period_normalized_utc=ref_tuple.get("normalized_utc") if ref_tuple else None,
        # Reference period tuple — D4-faithful fields ADDED per closure (was dropped):
        reference_period_raw=ref_tuple.get("original_value") if ref_tuple else None,
        reference_period_timezone_status=ref_tuple.get("timezone_status") if ref_tuple else None,
        reference_period_normalization_basis=ref_tuple.get("normalization_basis") if ref_tuple else None,
        reference_period_timestamp_semantics=ref_tuple.get("timestamp_semantics") if ref_tuple else None,
        reference_period_provenance_source=ref_tuple.get("provenance_source") if ref_tuple else None,
    )


def build_headline_from_row(event_row: dict, source_name: str) -> str:
    from .detect import EVENT_TYPE_RULES
    tpl = EVENT_TYPE_RULES[event_row["event_type"]]["headline_template"]
    return tpl.format(source=source_name or "Source",
                      headline_verb=event_row["event_type"].replace("_", " ").title())


def deliver(store, io: IntelligenceObject, destination: str,
            created_at: str = "") -> tuple[Delivery, bool]:
    """D8 Contract C: idempotent per (io_id, version, destination).
    Re-delivery of the same version returns the existing record (no new row)."""
    key = f"{io.io_id}:v{io.version}:{destination}"
    for row in store.iter("deliveries"):
        if row["idempotency_key"] == key:
            return Delivery(**{k: row[k] for k in
                               ("delivery_id", "intelligence_object_id", "version",
                                "destination", "status", "idempotency_key", "created_at")}), False
    d = Delivery(delivery_id=make_delivery_id(io.io_id, io.version, destination),
                 intelligence_object_id=io.io_id, version=io.version,
                 destination=destination, status="DELIVERED",
                 idempotency_key=key, created_at=created_at)
    store.append("deliveries", d.to_dict())
    return d, True
