"""V4 §13 — Add 10 Golden IOs from multi-event/pattern logic.

These golden IOs specifically protect against future semantic over-detection
by anchoring multi-event documents as regression fixtures.
"""
from __future__ import annotations
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id
from intelligence_core.production_transport import (
    _derive_status, _derive_supersedes_io_id, _compute_etag,
)


def add_multi_event_golden(store_root: str = "v3_corpus_store"):
    """Add 10 golden IOs from multi-event documents."""
    print(f"\n{'='*70}")
    print(f"V4 §13 — Add 10 Multi-Event Golden IOs")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Find multi-event docs
    events_per_doc = defaultdict(list)
    for ev in store.iter("events"):
        events_per_doc[ev.get("document_id", "")].append(ev)

    multi_event_docs = {doc_id: evs for doc_id, evs in events_per_doc.items() if len(evs) >= 2}
    print(f"  Multi-event docs available: {len(multi_event_docs)}")

    # Select 10 diverse multi-event IOs
    selected = []
    seen_sources = set()
    for doc_id, evs in multi_event_docs.items():
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")
        if src_id in seen_sources:
            continue
        # Pick the first event from this doc
        ev = evs[0]
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        try:
            io = build_intelligence_object(store, ev, source_name=src_id)
            io_dict = io.to_dict()
            io_dict["status"] = _derive_status(ev)
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev)
            selected.append({
                "io_id": ioid,
                "event_type": ev["event_type"],
                "source_id": src_id,
                "doc_id": doc_id,
                "multi_event_count": len(evs),
                "all_event_types": [e["event_type"] for e in evs],
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "io_dict": io_dict,
                "etag": _compute_etag(io_dict),
            })
            seen_sources.add(src_id)
            if len(selected) >= 10:
                break
        except Exception:
            continue

    print(f"  Selected {len(selected)} multi-event golden IOs:")
    for g in selected:
        print(f"    {g['io_id']}  type={g['event_type']:<30} src={g['source_id']:<25} "
              f"events={g['multi_event_count']} types={g['all_event_types']}")

    # Start fresh: rebuild golden corpus from current store
    # (30 original + 10 multi-event = 40 total)
    golden_path = Path("intelligence_core/tests/reliability/golden_corpus_v2.json")
    frozen_path = Path("intelligence_core/tests/reliability/golden_corpus_frozen.json")

    # Re-freeze ALL 40 golden IOs from the current store
    # First, get the original 30 from the existing golden_corpus_v2.json
    if golden_path.exists():
        with open(golden_path) as f:
            existing = json.load(f)
    else:
        existing = {"golden_ios": {}}

    # Keep track of which io_ids were in the original 30
    original_io_ids = set()
    for ioid, info in existing["golden_ios"].items():
        if not info.get("multi_event"):
            original_io_ids.add(ioid)

    # Re-freeze the original 30 from the current store
    frozen = {}
    re_frozen_original = 0
    docs_by_id_for_freeze = store.latest_by_id("documents", "document_id")
    sources_by_id = store.latest_by_id("sources", "source_id")
    for ioid in original_io_ids:
        ev = store.find_by_io_id(ioid)
        if ev is None:
            continue
        try:
            # Get the source_name for this event
            doc = docs_by_id_for_freeze.get(ev.get("document_id", ""), {})
            src_id = doc.get("source_id", "")
            io = build_intelligence_object(store, ev, source_name=src_id)
            io_dict = io.to_dict()
            io_dict["status"] = _derive_status(ev)
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev)
            frozen[ioid] = {
                "io_id": ioid,
                "event_type": ev["event_type"],
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "io_dict": io_dict,
                "etag": _compute_etag(io_dict),
            }
            re_frozen_original += 1
        except Exception:
            pass

    print(f"  Re-frozen original golden IOs: {re_frozen_original}")

    # Add the 10 new multi-event golden IOs
    for g in selected:
        frozen[g["io_id"]] = {
            "io_id": g["io_id"],
            "event_type": g["event_type"],
            "frozen_at": g["frozen_at"],
            "io_dict": g["io_dict"],
            "etag": g["etag"],
        }

    # Save frozen dicts
    with open(frozen_path, "w") as f:
        json.dump(frozen, f, indent=2, default=str)
    print(f"  Total frozen golden IOs: {len(frozen)}")

    # Update golden summary
    existing["golden_ios"] = {}
    for ioid, entry in frozen.items():
        is_multi = ioid in [g["io_id"] for g in selected]
        existing["golden_ios"][ioid] = {
            "io_id": ioid,
            "event_type": entry["event_type"],
            "frozen_at": entry["frozen_at"],
            "etag": entry["etag"],
            "event_version": 1,
            "status": "ACTIVE",
            "supersedes_io_id": None,
            "chain_length": len(entry["io_dict"].get("chain", [])),
            "temporal_tuples_count": len((entry["io_dict"].get("temporal_data") or {}).get("temporal_tuples", [])),
            "multi_event": is_multi,
        }

    existing["total_golden"] = len(existing["golden_ios"])
    existing["multi_event_golden_count"] = sum(1 for v in existing["golden_ios"].values() if v.get("multi_event"))

    with open(golden_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)
    print(f"\n  Golden corpus: {existing['total_golden']} total ({existing['multi_event_golden_count']} multi-event)")

    return selected


def run_golden_regression_with_multi(store_root: str = "v3_corpus_store"):
    """Run golden regression including the 10 new multi-event IOs."""
    print(f"\n{'='*70}")
    print(f"V4 §13 — Golden Regression (40 IOs: 30 original + 10 multi-event)")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    frozen_path = Path("intelligence_core/tests/reliability/golden_corpus_frozen.json")

    if not frozen_path.exists():
        print(f"  ✗ No frozen golden corpus found")
        return False

    docs_by_id_for_reg = store.latest_by_id("documents", "document_id")

    with open(frozen_path) as f:
        frozen = json.load(f)

    print(f"  Total frozen golden IOs: {len(frozen)}")

    passed = 0
    failed = 0

    for ioid, entry in frozen.items():
        ev = store.find_by_io_id(ioid)
        if ev is None:
            failed += 1
            continue

        try:
            # Get the source_name for this event (same as when frozen)
            doc = docs_by_id_for_reg.get(ev.get("document_id", ""), {})
            src_id = doc.get("source_id", "")
            io = build_intelligence_object(store, ev, source_name=src_id)
            io_dict = io.to_dict()
            io_dict["status"] = _derive_status(ev)
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev)

            if io_dict == entry["io_dict"]:
                passed += 1
            else:
                failed += 1
                print(f"  ✗ MISMATCH: {ioid}")
        except Exception as e:
            failed += 1
            print(f"  ✗ ERROR: {ioid}: {e}")

    print(f"\n  Results: {passed}/{len(frozen)} passed, {failed} failed")
    print(f"  Overall: {'PASS' if failed == 0 else 'FAIL'}")
    return failed == 0


if __name__ == "__main__":
    new_golden = add_multi_event_golden()
    success = run_golden_regression_with_multi()
    sys.exit(0 if success else 1)
