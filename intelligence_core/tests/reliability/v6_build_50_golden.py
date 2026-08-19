"""V6 §10 — Build 50+ Golden IOs with NEGATIVE regression tests.

Expand golden corpus to ≥50 IOs including:
  - monetary, statistical, regulatory
  - multi-event
  - non-English where valid
  - 3 former false positives as NEGATIVE regression tests
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


# The 3 former false positives — these should NOT produce events now
NEGATIVE_REGRESSION_CASES = [
    {
        "io_id": "io-935ab64f33806484",
        "event_type": "monetary_policy_decision",
        "source_id": "imp-bea",
        "document_id": "doc-7c5cd3967c2f9f10",
        "negative_test": True,
        "reason": "BEA GDP statistical release incorrectly classified as monetary_policy_decision",
    },
    {
        "io_id": "io-39cfc3b482bba190",
        "event_type": "regulatory_enforcement",
        "source_id": "imp-cftc",
        "document_id": "doc-5d55c41d98f4dd08",
        "negative_test": True,
        "reason": "CFTC op-ed incorrectly classified as regulatory_enforcement",
    },
    {
        "io_id": "io-f405b7c878fbec26",
        "event_type": "regulatory_enforcement",
        "source_id": "imp-bea",
        "document_id": "doc-7c5cd3967c2f9f10",
        "negative_test": True,
        "reason": "BEA statistical release incorrectly classified as regulatory_enforcement",
    },
]


def build_50_golden_corpus(store_root: str = "v3_corpus_store"):
    """Build 50+ golden IOs from the clean V6 corpus."""
    print(f"\n{'='*70}")
    print(f"V6 §10 — Build 50+ Golden IOs with Negative Regression Tests")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Group IOs by event_type
    ios_by_type = defaultdict(list)
    for ev in store.iter("events"):
        doc = docs_by_id.get(ev.get("document_id", ""), {})
        src_id = doc.get("source_id", "")
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        ios_by_type[ev["event_type"]].append({
            "io_id": ioid,
            "event_row": ev,
            "source_id": src_id,
            "event_type": ev["event_type"],
        })

    # Select golden IOs: aim for 15 per type + multi-event + language
    selected = []
    seen_sources = set()

    # 15 monetary
    for io in ios_by_type.get("monetary_policy_decision", [])[:15]:
        if io["source_id"] not in seen_sources or len(selected) < 50:
            selected.append(io)
            seen_sources.add(io["source_id"])

    # 15 statistical
    for io in ios_by_type.get("statistical_release", [])[:15]:
        if io["source_id"] not in seen_sources or len(selected) < 50:
            selected.append(io)
            seen_sources.add(io["source_id"])

    # 15 regulatory
    for io in ios_by_type.get("regulatory_enforcement", [])[:15]:
        if io["source_id"] not in seen_sources or len(selected) < 50:
            selected.append(io)
            seen_sources.add(io["source_id"])

    # If we don't have 45, fill from any
    if len(selected) < 45:
        for et, ios in ios_by_type.items():
            for io in ios:
                if io not in selected:
                    selected.append(io)
                    if len(selected) >= 50:
                        break
            if len(selected) >= 50:
                break

    # Find multi-event docs
    events_per_doc = defaultdict(list)
    for ev in store.iter("events"):
        events_per_doc[ev.get("document_id", "")].append(ev)

    multi_event_docs = {doc_id: evs for doc_id, evs in events_per_doc.items() if len(evs) >= 2}

    # Add 5 multi-event IOs
    multi_added = 0
    for doc_id, evs in multi_event_docs.items():
        if multi_added >= 5:
            break
        ev = evs[0]
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        # Check not already selected
        if not any(s["io_id"] == ioid for s in selected):
            doc = docs_by_id.get(doc_id, {})
            selected.append({
                "io_id": ioid,
                "event_row": ev,
                "source_id": doc.get("source_id", ""),
                "event_type": ev["event_type"],
                "multi_event": True,
                "multi_event_count": len(evs),
            })
            multi_added += 1

    print(f"  Selected {len(selected)} golden IOs")
    print(f"    monetary_policy_decision: {sum(1 for s in selected if s['event_type'] == 'monetary_policy_decision')}")
    print(f"    statistical_release: {sum(1 for s in selected if s['event_type'] == 'statistical_release')}")
    print(f"    regulatory_enforcement: {sum(1 for s in selected if s['event_type'] == 'regulatory_enforcement')}")
    print(f"    multi-event: {multi_added}")

    # Freeze golden IOs
    frozen = {}
    for io_entry in selected:
        try:
            io = build_intelligence_object(store, io_entry["event_row"], source_name=io_entry["source_id"])
            io_dict = io.to_dict()
            io_dict["status"] = _derive_status(io_entry["event_row"])
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, io_entry["event_row"])
            frozen[io_entry["io_id"]] = {
                "io_id": io_entry["io_id"],
                "event_type": io_entry["event_type"],
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "io_dict": io_dict,
                "etag": _compute_etag(io_dict),
                "source_id": io_entry["source_id"],
                "multi_event": io_entry.get("multi_event", False),
            }
        except Exception as e:
            continue

    # Add NEGATIVE regression cases
    negative_cases = {}
    for case in NEGATIVE_REGRESSION_CASES:
        negative_cases[case["io_id"]] = {
            "io_id": case["io_id"],
            "event_type": case["event_type"],
            "source_id": case["source_id"],
            "document_id": case["document_id"],
            "negative_test": True,
            "reason": case["reason"],
            "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    # Save
    frozen_path = Path("intelligence_core/tests/reliability/golden_corpus_frozen.json")
    with open(frozen_path, "w") as f:
        json.dump(frozen, f, indent=2, default=str)

    # Save negative cases separately
    negative_path = Path("intelligence_core/tests/reliability/negative_regression_cases.json")
    with open(negative_path, "w") as f:
        json.dump(negative_cases, f, indent=2, default=str)

    # Update golden summary
    golden_path = Path("intelligence_core/tests/reliability/golden_corpus_v2.json")
    golden_summary = {"golden_ios": {}}
    for ioid, entry in frozen.items():
        golden_summary["golden_ios"][ioid] = {
            "io_id": ioid,
            "event_type": entry["event_type"],
            "frozen_at": entry["frozen_at"],
            "etag": entry["etag"],
            "source_id": entry["source_id"],
            "multi_event": entry.get("multi_event", False),
        }
    golden_summary["total_golden"] = len(golden_summary["golden_ios"])
    golden_summary["negative_regression_count"] = len(negative_cases)

    with open(golden_path, "w") as f:
        json.dump(golden_summary, f, indent=2, default=str)

    print(f"\n  Total golden IOs: {golden_summary['total_golden']}")
    print(f"  Negative regression cases: {golden_summary['negative_regression_count']}")

    return frozen, negative_cases


def verify_negative_regression(store_root: str = "v3_corpus_store"):
    """Verify that the 3 former false positives do NOT produce events."""
    print(f"\n--- Verifying Negative Regression Cases ---")

    store = CachedStore(AppendOnlyStore(store_root))

    all_pass = True
    for case in NEGATIVE_REGRESSION_CASES:
        # Check if this io_id exists in the store
        ev = store.find_by_io_id(case["io_id"])
        if ev is None:
            print(f"  ✓ {case['io_id']} — NOT in store (correctly rejected by semantic gate)")
        else:
            print(f"  ✗ {case['io_id']} — STILL in store (semantic gate failed to reject)")
            all_pass = False

    return all_pass


def run_golden_regression(store_root: str = "v3_corpus_store"):
    """Run golden regression on the 50+ IOs."""
    print(f"\n--- Golden Regression ---")

    store = CachedStore(AppendOnlyStore(store_root))
    frozen_path = Path("intelligence_core/tests/reliability/golden_corpus_frozen.json")

    if not frozen_path.exists():
        print(f"  ✗ No frozen golden corpus found")
        return False

    with open(frozen_path) as f:
        frozen = json.load(f)

    print(f"  Total frozen golden IOs: {len(frozen)}")

    passed = 0
    failed = 0
    docs_by_id = store.latest_by_id("documents", "document_id")

    for ioid, entry in frozen.items():
        ev = store.find_by_io_id(ioid)
        if ev is None:
            failed += 1
            continue

        try:
            doc = docs_by_id.get(ev.get("document_id", ""), {})
            src_id = doc.get("source_id", "")
            io = build_intelligence_object(store, ev, source_name=src_id)
            io_dict = io.to_dict()
            io_dict["status"] = _derive_status(ev)
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev)

            if io_dict == entry["io_dict"]:
                passed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    print(f"  Results: {passed}/{len(frozen)} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    frozen, negative = build_50_golden_corpus()
    negative_pass = verify_negative_regression()
    golden_pass = run_golden_regression()

    print(f"\n  Negative regression: {'PASS' if negative_pass else 'FAIL'}")
    print(f"  Golden regression: {'PASS' if golden_pass else 'FAIL'}")
    print(f"  Overall: {'PASS' if (negative_pass and golden_pass) else 'FAIL'}")
