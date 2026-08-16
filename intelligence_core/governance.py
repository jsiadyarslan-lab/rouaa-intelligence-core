"""D2 — corrections/versioning operations. Immutable rows; supersession via new versions."""
from __future__ import annotations
from .contracts import ObjState, SupersessionReason
from .store import AppendOnlyStore


def supersede_fact(store: AppendOnlyStore, fact_id: str, new_value: str,
                   reason: SupersessionReason, evidence_ref: str,
                   actor: str, run_id: str, created_at: str = "") -> dict:
    """Same-fact correction (e.g. re-extraction of SAME representation found an error):
    appends version+1; prior row remains intact (readable as history)."""
    current = store.current_fact(fact_id)
    if current is None:
        raise ValueError(f"unknown fact {fact_id}")
    if current["status"] != ObjState.ACTIVE.value:
        raise ValueError(f"fact {fact_id} not ACTIVE (={current['status']})")
    # close old row (new version row carrying SUPERSEDED status + link)
    closed = dict(current)
    closed.update({"fact_version": current["fact_version"] + 1,
                   "status": ObjState.SUPERSEDED.value,
                   "superseded_by": f"{fact_id}:v{current['fact_version'] + 2}",
                   "supersession_reason": reason.value, "supersession_evidence": evidence_ref})
    store.append("facts", closed)
    # new active row
    nxt = dict(current)
    nxt.update({"fact_version": current["fact_version"] + 2, "value": new_value,
                "status": ObjState.ACTIVE.value,
                "supersedes": f"{fact_id}:v{current['fact_version']}",
                "superseded_by": None, "supersession_reason": reason.value,
                "supersession_evidence": evidence_ref})
    store.append("facts", nxt)
    store.audit("FACT_SUPERSEDED", {"fact_id": fact_id, "reason": reason.value,
                                    "evidence": evidence_ref, "actor": actor, "run_id": run_id})
    return nxt


def supersede_fact_by_source(store: AppendOnlyStore, old_fact_id: str,
                             new_fact_row: dict, reason: SupersessionReason,
                             evidence_ref: str, actor: str, run_id: str) -> dict:
    """Source-driven change (SOURCE_REVISION / RETRACTED_BY_SOURCE): the successor is a
    DIFFERENT fact (new representation). Old fact gets a closing SUPERSEDED row pointing at it."""
    current = store.current_fact(old_fact_id)
    if current is None:
        raise ValueError(f"unknown fact {old_fact_id}")
    closed = dict(current)
    closed.update({"fact_version": current["fact_version"] + 1,
                   "status": ObjState.SUPERSEDED.value,
                   "superseded_by": new_fact_row["fact_id"],
                   "supersession_reason": reason.value, "supersession_evidence": evidence_ref})
    store.append("facts", closed)
    store.audit("FACT_SUPERSEDED_BY_SOURCE", {"fact_id": old_fact_id,
                                              "successor": new_fact_row["fact_id"],
                                              "reason": reason.value, "evidence": evidence_ref,
                                              "actor": actor, "run_id": run_id})
    return closed


def _resolve_active_fact(store: AppendOnlyStore, fact_id: str,
                         _seen: set | None = None) -> dict | None:
    """L-EVT-PROP fix: follow the supersession chain (same-id version bumps AND
    cross-representation superseded_by links) to the terminal ACTIVE fact.
    Returns None only for INVALIDATED chains (withdrawn without successor)."""
    seen = _seen or set()
    if fact_id in seen:
        return None                      # cycle guard (defensive; links are append-only)
    seen.add(fact_id)
    cur = store.current_fact(fact_id)
    if cur is None:
        return None
    if cur["status"] == ObjState.ACTIVE.value:
        return cur
    if cur["status"] == ObjState.SUPERSEDED.value and cur.get("superseded_by"):
        # same-id version path: "fact-x:vN" -> same fact_id; cross-id path: raw fact_id
        nxt = cur["superseded_by"].split(":v")[0]
        return _resolve_active_fact(store, nxt, seen)
    return None                          # INVALIDATED (no successor)


def recompute_event(store: AppendOnlyStore, event_id: str,
                    derived_at: str = "") -> dict | None:
    """D2 propagation (L-EVT-PROP fixed): rebuild the derivation by resolving every
    snapshot fact through its supersession chain to the current ACTIVE successors.
    Appends event_version+1; the prior version remains exactly reproducible.
    An event never silently disappears: if every chain is INVALIDATED (withdrawn
    without successor), an INVALIDATED event version is appended instead."""
    versions = store.event_versions(event_id)
    if not versions:
        raise ValueError(f"unknown event {event_id}")
    latest = versions[-1]
    resolved, invalidated = [], 0
    for ref in latest["fact_version_snapshot"]:
        cur = _resolve_active_fact(store, ref["fact_id"])
        if cur is not None:
            resolved.append(cur)
        else:
            invalidated += 1
    snapshot = [{"fact_id": r["fact_id"], "fact_version": r["fact_version"]}
                for r in resolved]
    if snapshot == latest["fact_version_snapshot"] and invalidated == 0:
        return latest  # no change — no new version (idempotent, Case F)
    new_version = latest["event_version"] + 1
    # close old version FIRST (append-only: last row per id = current view)
    closing = dict(latest)
    closing.update({"status": ObjState.SUPERSEDED.value,
                    "superseded_by_version": new_version})
    store.append("events", closing)
    row = dict(latest)
    row.update({"event_version": new_version, "fact_version_snapshot": snapshot,
                "status": ObjState.ACTIVE.value if snapshot else ObjState.INVALIDATED.value,
                "derived_at": derived_at})
    store.append("events", row)
    store.audit("EVENT_RECOMPUTED", {"event_id": event_id, "new_version": new_version,
                                     "resolved_facts": len(snapshot),
                                     "invalidated_chains": invalidated})
    return store.current_event(event_id)


def reproduce_event(store: AppendOnlyStore, event_id: str, event_version: int) -> dict | None:
    """Historical reproducibility: the old version's snapshot resolves against RETAINED rows."""
    for r in store.event_versions(event_id):
        if r["event_version"] == event_version:
            facts = [store.fact_row(ref["fact_id"], ref["fact_version"])
                     for ref in r["fact_version_snapshot"]]
            if any(f is None for f in facts):
                return None
            return {"event": r, "facts": facts}
    return None
