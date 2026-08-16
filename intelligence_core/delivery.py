"""D7/D8 — IntelligenceObject (canonical output) + Delivery (idempotent output act)."""
from __future__ import annotations
from .contracts import IntelligenceObject, Delivery
from .identity import io_id as make_io_id, delivery_id as make_delivery_id
from .detect import build_headline


def build_intelligence_object(store, event_row: dict, source_name: str = "",
                              created_at: str = "") -> IntelligenceObject:
    """IO-first abstraction with the FULL traceability chain embedded (D7):
    event -> facts(+versions) -> evidence -> representation(sha) -> document -> source."""
    chain = []
    for ref in event_row["fact_version_snapshot"]:
        fact = store.fact_row(ref["fact_id"], ref["fact_version"])
        if fact is None:
            raise ValueError(f"chain broken: {ref}")
        rep = store.latest_by_id("representations", "representation_id").get(fact["representation_id"])
        doc = store.latest_by_id("documents", "document_id").get(fact["document_id"])
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
    io = IntelligenceObject(
        io_id=make_io_id(event_row["event_id"], event_row["event_version"]),
        version=1, event_id=event_row["event_id"],
        event_version=event_row["event_version"],
        headline=build_headline_from_row(event_row, source_name),
        chain=chain, created_at=created_at)
    return io


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
