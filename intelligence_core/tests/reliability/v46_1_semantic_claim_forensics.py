"""V46.1 -- forensic audit of V46 semantic-claim eligibility.

This is deliberately an audit, not an enrichment stage.  It identifies
whether a V46-derived entity, date, or state has an event-local proof.  A
signal found somewhere in a context window is not, by itself, such proof.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.tests.reliability.v45_intelligence_yield import (
    audit_entity, audit_event_state, audit_temporal,
)

IO_DUMP = CORE_REPO / "intelligence_core/tests/reliability/recovery_corpus_ios.jsonl"
OUTPUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v46_1_semantic_claim_forensics.json"
OUTPUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V46_1_SEMANTIC_CLAIM_FORENSICS.md"

ENTITY_CONFIRMED = "ENTITY_CONFIRMED"
UNKNOWN = "UNKNOWN"


def entity_disposition(entity_audit: dict) -> str:
    """Classify confirmation that depends on publisher/source identity."""
    if entity_audit["entity_status"] != ENTITY_CONFIRMED:
        return "NOT_CLAIMED"
    # V45's own explanation makes this dependency explicit.  That proves
    # publisher identity, not that the publisher is the subject of the fact.
    if "matches source_name" in entity_audit.get("why", ""):
        return "UNSUPPORTED_PUBLISHER_SUBJECT_CONFLATION"
    return "REQUIRES_HUMAN_REVIEW"


def temporal_disposition(temporal_audit: dict) -> str:
    """A regex date needs a local relationship to the represented event."""
    claimed = any(
        temporal_audit[f"{field}_status"] == "CONFIRMED"
        for field in ("event_date", "reference_period", "effective_date", "publication_date", "revision_date")
    )
    return "REQUIRES_HUMAN_REVIEW_UNSCOPED_TEMPORAL" if claimed else "NOT_CLAIMED"


def state_disposition(state: str) -> str:
    """The V45 state detector searches an aggregate string, not fact-local text."""
    return "REQUIRES_HUMAN_REVIEW_UNSCOPED_STATE" if state != UNKNOWN else "NOT_CLAIMED"


def event_type_disposition(io: dict) -> str:
    """V46 did not validate the pre-existing event type, so never endorse it."""
    return "NOT_AUDITED_BY_V46"


def run() -> dict:
    ios = [json.loads(line) for line in IO_DUMP.read_text(encoding="utf-8").splitlines()]
    ios = [io for io in ios if io.get("is_new")]
    ledger = []
    for io in ios:
        entity = audit_entity(io)
        temporal = audit_temporal(io)
        state = audit_event_state(io)
        ledger.append({
            "io_id": io["io_id"],
            "document_id": io.get("document_id", ""),
            "event_type": io.get("event_type", ""),
            "doc_url": io.get("doc_url", ""),
            "headline": io.get("headline", ""),
            "entity": {
                "claim": entity.get("primary_entity"),
                "status": entity.get("entity_status"),
                "disposition": entity_disposition(entity),
                "why": entity.get("why"),
            },
            "temporal": {
                "event_date": temporal.get("event_date"),
                "reference_period": temporal.get("reference_period"),
                "effective_date": temporal.get("effective_date"),
                "publication_date": temporal.get("publication_date"),
                "revision_date": temporal.get("revision_date"),
                "disposition": temporal_disposition(temporal),
            },
            "event_state": {"claim": state, "disposition": state_disposition(state)},
            "event_type_disposition": event_type_disposition(io),
            "fact_ids": [f.get("fact_id", "") for f in io.get("facts", [])],
            "evidence_ids": [e.get("evidence_id", e.get("fact_id", "")) for e in io.get("evidence", [])],
        })

    counts = {
        "entity": dict(Counter(x["entity"]["disposition"] for x in ledger)),
        "temporal": dict(Counter(x["temporal"]["disposition"] for x in ledger)),
        "event_state": dict(Counter(x["event_state"]["disposition"] for x in ledger)),
        "event_type": dict(Counter(x["event_type_disposition"] for x in ledger)),
    }
    result = {"phase": "V46.1 SEMANTIC CLAIM FORENSICS", "population": len(ledger), "counts": counts, "ledger": ledger}
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    entity_risk = counts["entity"].get("UNSUPPORTED_PUBLISHER_SUBJECT_CONFLATION", 0)
    temporal_risk = counts["temporal"].get("REQUIRES_HUMAN_REVIEW_UNSCOPED_TEMPORAL", 0)
    state_risk = counts["event_state"].get("REQUIRES_HUMAN_REVIEW_UNSCOPED_STATE", 0)
    lines = [
        "# ROUAA CORE V46.1 — SEMANTIC CLAIM FORENSICS",
        "",
        "## Verdict",
        "`V46.1 BLOCKED — SEMANTIC CLAIM ELIGIBILITY NOT PROVEN`",
        "",
        "V46 proved that structural context can be attached without changing evidence. It did **not** prove that an institution, date, or state found anywhere in that window belongs to the represented event.",
        "",
        "## Population",
        f"- NEW IOs examined: **{len(ledger)}**",
        f"- Entity confirmations dependent on source/publisher match: **{entity_risk}**",
        f"- Temporal claims requiring event-local review: **{temporal_risk}**",
        f"- Event-state claims requiring event-local review: **{state_risk}**",
        f"- Event types independently validated by V46: **0**",
        "",
        "## Root cause",
        "The entity auditor marks a candidate CONFIRMED when it appears in evidence *and matches `source_name`. This establishes publisher identity, not the subject entity of the fact or event. The temporal and state auditors search the complete aggregate evidence string, so they do not retain a fact-local/event-local relation for the matched signal.",
        "",
        "## Required next change",
        "Do not create a source-to-subject registry. First introduce a typed semantic contract that distinguishes `publisher_institution` from `subject_entity` and requires every event-level entity, date, and state claim to cite a segment that also contains (or structurally binds to) the represented fact/event.",
        "",
        "## Ledger",
        "The machine-readable ledger is `intelligence_core/tests/reliability/v46_1_semantic_claim_forensics.json`. It preserves IO, document, fact, evidence, and document URL identifiers for human adjudication.",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({"population": result["population"], "counts": result["counts"]}, indent=2))
