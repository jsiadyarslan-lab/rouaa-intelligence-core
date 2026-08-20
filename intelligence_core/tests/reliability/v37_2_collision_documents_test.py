"""V37.2 — Critical Test: 3 Known Collision Documents.

Tests the three architectural test cases from OCCURRENCE_IDENTITY_REVIEW.md:

  A. doc-a72c0918e27dd12b (Listing Page, value=5)
  B. doc-8700a0859c829c44 (Cross-Metric Collision, value=0.1)
  C. doc-7c5cd3967c2f9f10 (Simple Value Collision, value=0.2)

These are architectural test cases, not benchmark results. The correct
V37.2 outcome per the design decision OCCURRENCE_REQUIRES_CONTEXT:
  - Listing pages → INSUFFICIENT_EVIDENCE for ambiguous rows
  - Cross-metric → resolved by UNIT_CONTEXT scoring
  - Simple collision → resolved by structural context scoring

Reports per-document:
  GT fact count (from preflight JSON)
  candidate segments (per fact)
  selected segments (per fact)
  ambiguous cases (top-2 within 0.05)
  insufficient cases
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.structural_parser import parse_html_to_segments
from intelligence_core.evidence_selection import (
    select_evidence_segment,
    select_evidence_for_document,
    audit_collisions,
    DIRECT, INDIRECT, INSUFFICIENT_EVIDENCE, INVALID,
)


PREFLIGHT_JSON = (CORE_REPO /
                   "intelligence_core/tests/reliability/"
                   "v37_2_raw_blob_availability.json")

TARGET_DOCS = {
    "doc-a72c0918e27dd12b": "Case A — Listing Page (value=5)",
    "doc-8700a0859c829c44": "Case B — Cross-Metric Collision (value=0.1)",
    "doc-7c5cd3967c2f9f10": "Case C — Simple Value Collision (value=0.2)",
}


def make_fact(record):
    class _F:
        fact_id = record["gt_fact_id"]
        value = record["value"]
        metric = record["metric"]
        occurrence = 1
    return _F()


def main():
    print(f"\n{'=' * 70}")
    print(f"V37.2 — Critical Test: 3 Known Collision Documents")
    print(f"{'=' * 70}\n")

    with PREFLIGHT_JSON.open() as f:
        cases = json.load(f)

    # Group cases by target doc
    cases_by_doc = {}
    for c in cases:
        if c["document_id"] in TARGET_DOCS:
            cases_by_doc.setdefault(c["document_id"], []).append(c)

    for doc_id, label in TARGET_DOCS.items():
        doc_cases = cases_by_doc.get(doc_id, [])
        print(f"\n{'─' * 70}")
        print(f"{label}")
        print(f"  document_id: {doc_id}")
        print(f"  GT fact count: {len(doc_cases)}")

        if not doc_cases:
            print(f"  ⚠ NO GT FACTS FOUND for this doc in preflight JSON")
            continue

        # Parse the document once
        first_case = doc_cases[0]
        blob_path = Path(first_case["raw_location"])
        if not blob_path.exists():
            print(f"  ✗ Blob not accessible: {blob_path}")
            continue
        blob_bytes = blob_path.read_bytes()
        segs = parse_html_to_segments(blob_bytes, document_id=doc_id)
        print(f"  Total segments parsed: {len(segs)}")
        type_counts = Counter(s.segment_type for s in segs)
        print(f"  Segment types: {dict(type_counts)}")
        excluded_count = sum(1 for s in segs if s.excluded)
        print(f"  Excluded segments: {excluded_count}")

        # Run evidence selection for ALL facts in this doc at once —
        # this enables collision detection (V37.2 COLLISION FIX §3).
        facts = [make_fact(c) for c in doc_cases]
        doc_results = select_evidence_for_document(
            facts, blob_bytes, document_id=doc_id,
        )

        # Run collision audit
        collision_audit = audit_collisions(doc_results)

        # Aggregate stats
        status_counts = Counter()
        candidate_counts = []
        selected_segments = []
        ambiguous_count = 0

        for c, r in zip(doc_cases, doc_results):
            status_counts[r.status] += 1
            candidate_counts.append(r.candidate_count)
            if r.selected_segment:
                selected_segments.append({
                    "gt_fact_id": c["gt_fact_id"],
                    "fact_value": c["value"],
                    "fact_metric": c["metric"],
                    "selected_segment_id": r.selected_segment.segment_id,
                    "selected_segment_type": r.selected_segment.segment_type,
                    "selected_score": r.selected_score,
                    "cell_value": r.selected_segment.cell_value,
                    "row_label": r.selected_segment.row_label,
                    "column_label": r.selected_segment.column_label,
                    "heading_context": r.selected_segment.heading_context,
                    "reason": r.reason,
                })
                if len(r.candidates_considered) >= 2:
                    top = r.candidates_considered[0][1]
                    second = r.candidates_considered[1][1]
                    if abs(top - second) < 0.05 and top > 0:
                        ambiguous_count += 1

        # Report per-document stats
        print(f"\n  Per-fact selection stats:")
        print(f"    DIRECT:               {status_counts[DIRECT]}")
        print(f"    INDIRECT:             {status_counts[INDIRECT]}")
        print(f"    INSUFFICIENT_EVIDENCE: {status_counts[INSUFFICIENT_EVIDENCE]}")
        print(f"    INVALID:              {status_counts[INVALID]}")
        print(f"    Sum:                  {sum(status_counts.values())} (should match GT fact count)")
        print(f"    Total candidates across all facts: {sum(candidate_counts)}")
        if candidate_counts:
            print(f"    Avg candidates per fact: {sum(candidate_counts) / len(candidate_counts):.2f}")
        print(f"    Facts with selected segment: {len(selected_segments)}")
        print(f"    Ambiguous (top-2 within 0.05): {ambiguous_count}")
        # V37.2 COLLISION FIX §3+§4 — collision audit KPIs
        print(f"    ── Collision Audit (V37.2 COLLISION ACCOUNTING — 3-way) ──")
        print(f"    safe_shared_evidence_facts:    {collision_audit['safe_shared_evidence_facts']}")
        print(f"    resolved_insufficient_facts:   {collision_audit['resolved_insufficient_facts']}")
        print(f"    unresolved_collision_facts:    {collision_audit['unresolved_collision_facts']}  (required: 0)")
        print(f"    safe_shared_evidence_groups:    {collision_audit['safe_shared_evidence_groups']}")
        print(f"    resolved_insufficient_groups:   {collision_audit['resolved_insufficient_groups']}")
        print(f"    unresolved_collision_groups:    {collision_audit['unresolved_collision_groups']}  (required: 0)")
        print(f"    total_collision_facts:           {collision_audit['total_collision_facts']}")
        print(f"    invariant_holds:                 {collision_audit['invariant_holds']}")

        # Show all selected segments
        if selected_segments:
            print(f"\n  Selected segments detail:")
            for s in selected_segments:
                print(f"    {s['gt_fact_id']}: value={s['fact_value']!r} metric={s['fact_metric']}")
                print(f"      → segment_type={s['selected_segment_type']} score={s['selected_score']:.3f}")
                print(f"      → cell_value={s['cell_value']!r} row={s['row_label']!r} col={s['column_label']!r}")
                print(f"      → heading_context={s['heading_context']!r}")

    print(f"\n{'─' * 70}")
    print(f"Critical test complete.")


if __name__ == "__main__":
    main()
