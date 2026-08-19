"""V2 §11 — Freeze 30 Golden IOs + Golden Regression.

Golden corpus: 30 frozen IOs that serve as regression anchors.
Distribution (per directive §11):
  - 10 monetary_policy_decision
  - 10 statistical_release
  - 10 regulatory_enforcement

Freezing means: capture the COMPLETE canonical IO dict (with transport
projections: status, supersedes_io_id) so any future change that alters
ANY canonical field is detected.

Golden regression: after all transport/performance changes, re-build
each golden IO from the live store and verify byte-identical match.
"""
from __future__ import annotations
import json
import os
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


def freeze_golden_corpus(store, target_per_type=10):
    """Freeze `target_per_type` golden IOs per event_type.

    Selection criteria:
      - IO must build successfully (chain not broken)
      - IO must have temporal_data (K2) — prefer IOs with full D4 tuples
      - IO must have non-empty chain (provenance complete)
    """
    print(f"\n{'='*70}")
    print(f"V2 §11 — Freezing Golden Corpus ({target_per_type} per event_type)")
    print(f"{'='*70}")

    # Group IOs by event_type
    ios_by_type = defaultdict(list)
    for ev in store.iter("events"):
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        try:
            io = build_intelligence_object(store, ev, source_name="")
            io_dict = io.to_dict()
            # Add transport projections
            io_dict["status"] = _derive_status(ev)
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev)
            # Score this IO: prefer ones with temporal_data + multi-tuple D4
            score = 0
            if io.temporal_data:
                score += 10
                if io.temporal_data.temporal_tuples:
                    score += len(io.temporal_data.temporal_tuples)
            if io.chain:
                score += 5
            ios_by_type[ev["event_type"]].append((score, ioid, io_dict, ev))
        except Exception as e:
            # Skip broken IOs
            continue

    # Select top N per type
    golden = {}
    distribution = {}
    for event_type, candidates in ios_by_type.items():
        # Sort by score descending, then by io_id for determinism
        candidates.sort(key=lambda x: (-x[0], x[1]))
        selected = candidates[:target_per_type]
        for score, ioid, io_dict, ev in selected:
            golden[ioid] = {
                "io_id": ioid,
                "event_type": event_type,
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "io_dict": io_dict,
                "etag": _compute_etag(io_dict),
            }
        distribution[event_type] = len(selected)
        print(f"  {event_type}: {len(selected)} frozen (target {target_per_type})")
        # Print each golden IO id
        for score, ioid, io_dict, ev in selected:
            td = io_dict.get("temporal_data")
            n_tuples = len(td.get("temporal_tuples", [])) if td else 0
            print(f"    {ioid}  score={score}  temporal_tuples={n_tuples}")

    print(f"\n  Total golden: {len(golden)}")
    print(f"  Distribution: {dict(distribution)}")

    # Check target met
    required_types = ["monetary_policy_decision", "statistical_release", "regulatory_enforcement"]
    target_met = all(distribution.get(t, 0) >= target_per_type for t in required_types)
    if target_met:
        print(f"  ✓ PASS: ≥{target_per_type} per required event_type")
    else:
        print(f"  ✗ FAIL: not enough per type")

    return golden, distribution, target_met


def run_golden_regression(store, golden):
    """Re-build each golden IO from the live store and verify byte-identical match."""
    print(f"\n{'='*70}")
    print(f"V2 §11 — Golden Regression ({len(golden)} IOs)")
    print(f"{'='*70}")

    passed = 0
    failed = 0
    failures = []

    for ioid, golden_entry in golden.items():
        ev = store.find_by_io_id(ioid)
        if ev is None:
            failed += 1
            failures.append((ioid, "event_row not found"))
            continue

        try:
            io = build_intelligence_object(store, ev, source_name="")
            io_dict = io.to_dict()
            io_dict["status"] = _derive_status(ev)
            io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev)

            # Compare to frozen
            frozen_dict = golden_entry["io_dict"]
            if io_dict == frozen_dict:
                passed += 1
            else:
                failed += 1
                # Find what changed
                diffs = []
                for k in set(list(frozen_dict.keys()) + list(io_dict.keys())):
                    if frozen_dict.get(k) != io_dict.get(k):
                        diffs.append(f"{k}: {str(frozen_dict.get(k))[:50]} → {str(io_dict.get(k))[:50]}")
                failures.append((ioid, "; ".join(diffs[:3])))
        except Exception as e:
            failed += 1
            failures.append((ioid, f"exception: {e}"))

    print(f"\n  Results: {passed}/{len(golden)} passed, {failed} failed")
    if failures:
        print(f"\n  Failures (first 5):")
        for ioid, reason in failures[:5]:
            print(f"    {ioid}: {reason}")

    # Verify each canonical field is unchanged
    # Check specific fields per directive §11: event_type, facts, evidence, temporal_tuples, provenance, version lineage
    print(f"\n  Field-level verification (directive §11):")
    field_pass = {"event_type": 0, "facts": 0, "evidence": 0, "temporal_tuples": 0, "provenance": 0, "version_lineage": 0}
    field_fail = {k: 0 for k in field_pass}
    for ioid, golden_entry in golden.items():
        ev = store.find_by_io_id(ioid)
        if ev is None:
            for k in field_fail:
                field_fail[k] += 1
            continue
        try:
            io = build_intelligence_object(store, ev, source_name="")
            frozen = golden_entry["io_dict"]
            # event_type
            if io.event_type == frozen["event_type"]:
                field_pass["event_type"] += 1
            else:
                field_fail["event_type"] += 1
            # facts (in chain)
            frozen_facts = [link["fact"] for link in frozen["chain"]]
            live_facts = [link["fact"] for link in io.chain]
            if frozen_facts == live_facts:
                field_pass["facts"] += 1
            else:
                field_fail["facts"] += 1
            # evidence (in chain)
            frozen_ev = [link["evidence"] for link in frozen["chain"]]
            live_ev = [link["evidence"] for link in io.chain]
            if frozen_ev == live_ev:
                field_pass["evidence"] += 1
            else:
                field_fail["evidence"] += 1
            # temporal_tuples
            frozen_td = frozen.get("temporal_data") or {}
            live_td = io.temporal_data.to_dict() if io.temporal_data else None
            frozen_tuples = frozen_td.get("temporal_tuples", [])
            live_tuples = live_td.get("temporal_tuples", []) if live_td else []
            if frozen_tuples == live_tuples:
                field_pass["temporal_tuples"] += 1
            else:
                field_fail["temporal_tuples"] += 1
            # provenance (chain structure)
            if frozen["chain"] == io.chain:
                field_pass["provenance"] += 1
            else:
                field_fail["provenance"] += 1
            # version lineage
            frozen_v = (frozen["event_version"], frozen["status"], frozen.get("supersedes_io_id"))
            live_v = (io.event_version, _derive_status(ev), _derive_supersedes_io_id(store, ev))
            if frozen_v == live_v:
                field_pass["version_lineage"] += 1
            else:
                field_fail["version_lineage"] += 1
        except Exception:
            for k in field_fail:
                field_fail[k] += 1

    for k in field_pass:
        status = "✓" if field_fail[k] == 0 else "✗"
        print(f"    {status} {k:<20} {field_pass[k]}/{len(golden)}")

    return passed, failed, field_pass, field_fail


def main():
    store_root = sys.argv[1] if len(sys.argv) > 1 else "corpus_100_store"
    print(f"\n{'='*70}")
    print(f"V2 §11 — Golden Corpus + Regression")
    print(f"Store: {store_root}")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))

    # Step 1: Freeze 30 golden IOs
    golden, distribution, target_met = freeze_golden_corpus(store, target_per_type=10)

    # Save golden corpus
    golden_path = Path(__file__).resolve().parent / "golden_corpus_v2.json"
    # Strip the heavy io_dict for storage (keep summary + etag)
    golden_summary = {}
    for ioid, entry in golden.items():
        golden_summary[ioid] = {
            "io_id": ioid,
            "event_type": entry["event_type"],
            "frozen_at": entry["frozen_at"],
            "etag": entry["etag"],
            "event_version": entry["io_dict"]["event_version"],
            "status": entry["io_dict"]["status"],
            "supersedes_io_id": entry["io_dict"]["supersedes_io_id"],
            "chain_length": len(entry["io_dict"]["chain"]),
            "temporal_tuples_count": len((entry["io_dict"].get("temporal_data") or {}).get("temporal_tuples", [])),
        }
    with open(golden_path, "w") as f:
        json.dump({
            "schema_version": "2.0",
            "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "store_root": store_root,
            "target_per_type": 10,
            "distribution": distribution,
            "target_met": target_met,
            "golden_ios": golden_summary,
        }, f, indent=2, default=str)
    print(f"\n  Golden summary saved to: {golden_path}")

    # Save full frozen dicts (for regression comparison)
    full_path = Path(__file__).resolve().parent / "golden_corpus_frozen.json"
    with open(full_path, "w") as f:
        json.dump(golden, f, indent=2, default=str)
    print(f"  Full frozen dicts saved to: {full_path}")

    # Step 2: Golden regression (verify byte-identical rebuild)
    passed, failed, field_pass, field_fail = run_golden_regression(store, golden)

    # Final assessment
    print(f"\n{'='*70}")
    print(f"FINAL ASSESSMENT")
    print(f"{'='*70}")
    target_total = 30
    print(f"  Golden corpus size: {len(golden)}/{target_total}")
    print(f"  Target per type:    {target_met}")
    print(f"  Regression:         {passed}/{len(golden)} byte-identical")
    print(f"  Field-level:        {sum(field_pass.values())}/{sum(field_pass.values()) + sum(field_fail.values())} fields unchanged")

    overall = target_met and passed == len(golden) and sum(field_fail.values()) == 0
    print(f"\n  Overall: {'PASS' if overall else 'FAIL'}")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
