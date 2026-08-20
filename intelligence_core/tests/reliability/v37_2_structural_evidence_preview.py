"""V37.2 — 158-Case Structural Evidence Preview.

PHASE 10 of the V37.2 IMPLEMENTATION DIRECTIVE.

Runs a structural evidence preview against the 158-case ledger in
v37_2_raw_blob_availability.json. Does NOT run the full frozen benchmark,
event safety, live IO validation, or performance benchmark.

For each case, reports:
  - gt_fact_id
  - segment candidates (count + IDs)
  - selected segment (segment_id, segment_type)
  - structural context (heading_context, parent_segment_id, table_id,
                       row_label, column_label, period, unit)
  - selection score
  - evidence status (DIRECT | INDIRECT | INSUFFICIENT_EVIDENCE | INVALID)

Aggregates:
  - DIRECT / INDIRECT / INSUFFICIENT / INVALID counts
  - ambiguous_cases (where top-2 candidates were within 0.05 of each other)
  - navigation_filtered_cases (excluded segments existed but were filtered)
  - table_selected_cases (selected segment was TABLE_ROW)
  - paragraph_selected_cases (selected segment was PARAGRAPH)
  - list_selected_cases (selected segment was LIST_ITEM)

Output:
  - Console summary
  - JSON results: intelligence_core/tests/reliability/v37_2_structural_evidence_results.json
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.structural_parser import parse_html_to_segments, EvidenceSegmentV1, PRIMARY_EVIDENCE_TYPES
from intelligence_core.evidence_selection import (
    select_evidence_segment,
    select_evidence_for_document,
    audit_collisions,
    DIRECT, INDIRECT, INSUFFICIENT_EVIDENCE, INVALID,
)


PREFLIGHT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v37_2_raw_blob_availability.json"
RESULTS_JSON = CORE_REPO / "intelligence_core/tests/reliability/v37_2_structural_evidence_results.json"


# ── Cache parsed segments per document_id (16 unique docs) ────────────

_doc_cache: dict[str, list[EvidenceSegmentV1]] = {}


def get_segments_for_doc(record: dict) -> list[EvidenceSegmentV1]:
    """Parse the document HTML once and cache by representation_id."""
    rep_id = record["representation_id"]
    if rep_id in _doc_cache:
        return _doc_cache[rep_id]
    blob_path = record["raw_location"]
    try:
        blob_bytes = Path(blob_path).read_bytes()
    except Exception:
        _doc_cache[rep_id] = []
        return []
    segs = parse_html_to_segments(blob_bytes, document_id=record["document_id"])
    _doc_cache[rep_id] = segs
    return segs


def make_fact(record: dict):
    """Build a fact-like object for select_evidence_segment."""
    class _F:
        fact_id = record["gt_fact_id"]
        value = record["value"]
        metric = record["metric"]
        occurrence = 1  # preflight JSON doesn't carry occurrence
    return _F()


def run_preview():
    """Run the 158-case structural preview."""
    print(f"\n{'=' * 70}")
    print(f"V37.2 PHASE 10 — 158-Case Structural Evidence Preview")
    print(f"{'=' * 70}\n")

    if not PREFLIGHT_JSON.exists():
        print(f"  ✗ Preflight JSON not found at {PREFLIGHT_JSON}")
        return None
    with PREFLIGHT_JSON.open() as f:
        cases = json.load(f)

    print(f"  Total cases: {len(cases)}")
    print(f"  Unique documents: {len(set(c['document_id'] for c in cases))}")
    print(f"  Unique metrics: {sorted(set(c['metric'] for c in cases))}")
    print()

    # ── V37.2 COLLISION FIX §3 + §4 — group cases by document_id so we
    # can run select_evidence_for_document (which performs collision
    # detection) per document, instead of per-fact select_evidence_segment.
    cases_by_doc = {}
    for c in cases:
        cases_by_doc.setdefault(c["document_id"], []).append(c)

    # Per-case results
    case_results = []
    status_counts = Counter()
    selected_type_counts = Counter()
    ambiguous_cases = []
    navigation_filtered_cases = []
    table_selected_cases = []
    paragraph_selected_cases = []
    list_selected_cases = []
    no_candidates_cases = []
    all_results_for_audit = []  # for audit_collisions()

    # Process per-document — this gives us collision detection
    for doc_id, doc_cases in cases_by_doc.items():
        # Parse the document HTML once
        first_case = doc_cases[0]
        blob_path = Path(first_case["raw_location"])
        try:
            blob_bytes = blob_path.read_bytes()
        except Exception:
            blob_bytes = b""
        segs = parse_html_to_segments(blob_bytes, document_id=doc_id)

        # Build fact objects for all cases in this doc
        facts = [make_fact(c) for c in doc_cases]
        # Use select_evidence_for_document — applies collision detection
        doc_results = select_evidence_for_document(
            facts, blob_bytes, document_id=doc_id,
        )
        all_results_for_audit.extend(doc_results)

        # Build per-case result entries
        for c, r in zip(doc_cases, doc_results):
            gt_fact_id = c["gt_fact_id"]
            metric = c["metric"]
            value = c["value"]
            total_segments = len(segs)
            excluded_segments = sum(1 for s in segs if s.excluded)

            status_counts[r.status] += 1

            if r.selected_segment:
                selected_type_counts[r.selected_segment.segment_type] += 1
                if r.selected_segment.segment_type == "TABLE_ROW":
                    table_selected_cases.append(gt_fact_id)
                elif r.selected_segment.segment_type == "PARAGRAPH":
                    paragraph_selected_cases.append(gt_fact_id)
                elif r.selected_segment.segment_type == "LIST_ITEM":
                    list_selected_cases.append(gt_fact_id)

            if len(r.candidates_considered) >= 2:
                top_score = r.candidates_considered[0][1]
                second_score = r.candidates_considered[1][1]
                if abs(top_score - second_score) < 0.05 and top_score > 0:
                    ambiguous_cases.append(gt_fact_id)

            if excluded_segments > 0:
                navigation_filtered_cases.append(gt_fact_id)
            if r.candidate_count == 0:
                no_candidates_cases.append(gt_fact_id)

            case_results.append({
                "gt_fact_id": gt_fact_id,
                "document_id": doc_id,
                "metric": metric,
                "value": value,
                "total_segments": total_segments,
                "excluded_segments": excluded_segments,
                "candidate_count": r.candidate_count,
                "selected_segment_id": (r.selected_segment.segment_id
                                         if r.selected_segment else None),
                "selected_segment_type": (r.selected_segment.segment_type
                                           if r.selected_segment else None),
                "selected_score": r.selected_score,
                "evidence_status": r.status,
                "reason": r.reason,
                "structural_context": {
                    "heading_context": (r.selected_segment.heading_context
                                          if r.selected_segment else None),
                    "parent_segment_id": (r.selected_segment.parent_segment_id
                                           if r.selected_segment else None),
                    "table_id": (r.selected_segment.table_id
                                  if r.selected_segment else None),
                    "row_label": (r.selected_segment.row_label
                                    if r.selected_segment else None),
                    "column_label": (r.selected_segment.column_label
                                      if r.selected_segment else None),
                    "cell_value": (r.selected_segment.cell_value
                                    if r.selected_segment else None),
                    "period": (r.selected_segment.period
                                 if r.selected_segment else None),
                    "unit": (r.selected_segment.unit
                              if r.selected_segment else None),
                },
                "candidates_preview": [
                    {"segment_id": sid, "score": sc, "segment_type": st}
                    for sid, sc, st in r.candidates_considered[:5]
                ],
            })

    # ── Run collision audit ─────────────────────────────────────────
    collision_audit = audit_collisions(all_results_for_audit)

    # ── Summary ──────────────────────────────────────────────────────
    print(f"  ── Evidence Status Counts ──")
    print(f"  DIRECT:                {status_counts[DIRECT]:>4}")
    print(f"  INDIRECT:              {status_counts[INDIRECT]:>4}")
    print(f"  INSUFFICIENT_EVIDENCE: {status_counts[INSUFFICIENT_EVIDENCE]:>4}")
    print(f"  INVALID:               {status_counts[INVALID]:>4}")
    print()
    print(f"  ── Selected Segment Type Counts ──")
    for st, cnt in sorted(selected_type_counts.items()):
        print(f"  {st:24s}: {cnt:>4}")
    print()
    print(f"  ── Aggregate Case Counts ──")
    print(f"  ambiguous_cases (top-2 within 0.05):    {len(ambiguous_cases):>4}")
    print(f"  navigation_filtered_cases:              {len(navigation_filtered_cases):>4}")
    print(f"  table_selected_cases:                   {len(table_selected_cases):>4}")
    print(f"  paragraph_selected_cases:               {len(paragraph_selected_cases):>4}")
    print(f"  list_selected_cases:                    {len(list_selected_cases):>4}")
    print(f"  no_candidates_cases:                     {len(no_candidates_cases):>4}")
    print()
    print(f"  ── V37.2 COLLISION ACCOUNTING — 3-way classification ──")
    print(f"  safe_shared_evidence_facts:              {collision_audit['safe_shared_evidence_facts']:>4}")
    print(f"  resolved_insufficient_facts:             {collision_audit['resolved_insufficient_facts']:>4}")
    print(f"  unresolved_collision_facts:              {collision_audit['unresolved_collision_facts']:>4}  (required: 0)")
    print(f"  safe_shared_evidence_groups:             {collision_audit['safe_shared_evidence_groups']:>4}")
    print(f"  resolved_insufficient_groups:            {collision_audit['resolved_insufficient_groups']:>4}")
    print(f"  unresolved_collision_groups:             {collision_audit['unresolved_collision_groups']:>4}  (required: 0)")
    print(f"  total_collision_facts:                   {collision_audit['total_collision_facts']:>4}")
    print(f"  invariant (safe+resolved+unresolved==total): {collision_audit['invariant_holds']}")
    print()

    # ── Persist JSON results ────────────────────────────────────────
    output = {
        "phase": "V37.2 PHASE 10 — 158-Case Structural Evidence Preview (with Collision Fix)",
        "baseline_commit": "0dedc99ad96aba65923f8dfd610e65fb2e8797c9",
        "total_cases": len(cases),
        "unique_documents": len(set(c["document_id"] for c in cases)),
        "unique_metrics": sorted(set(c["metric"] for c in cases)),
        "status_counts": {
            "DIRECT": status_counts[DIRECT],
            "INDIRECT": status_counts[INDIRECT],
            "INSUFFICIENT_EVIDENCE": status_counts[INSUFFICIENT_EVIDENCE],
            "INVALID": status_counts[INVALID],
        },
        "selected_segment_type_counts": dict(selected_type_counts),
        "aggregate_counts": {
            "ambiguous_cases": len(ambiguous_cases),
            "navigation_filtered_cases": len(navigation_filtered_cases),
            "table_selected_cases": len(table_selected_cases),
            "paragraph_selected_cases": len(paragraph_selected_cases),
            "list_selected_cases": len(list_selected_cases),
            "no_candidates_cases": len(no_candidates_cases),
        },
        "collision_audit": {
            "safe_shared_evidence_facts": collision_audit["safe_shared_evidence_facts"],
            "resolved_insufficient_facts": collision_audit["resolved_insufficient_facts"],
            "unresolved_collision_facts": collision_audit["unresolved_collision_facts"],
            "safe_shared_evidence_groups": collision_audit["safe_shared_evidence_groups"],
            "resolved_insufficient_groups": collision_audit["resolved_insufficient_groups"],
            "unresolved_collision_groups": collision_audit["unresolved_collision_groups"],
            "total_collision_facts": collision_audit["total_collision_facts"],
            "invariant_holds": collision_audit["invariant_holds"],
            "safe_shared_evidence": collision_audit["safe_shared_evidence"],
            "resolved_insufficient_evidence": collision_audit["resolved_insufficient_evidence"],
            "unresolved_collisions": collision_audit["unresolved_collisions"],
        },
        "ambiguous_case_ids": ambiguous_cases,
        "navigation_filtered_case_ids": navigation_filtered_cases,
        "table_selected_case_ids": table_selected_cases,
        "paragraph_selected_case_ids": paragraph_selected_cases,
        "list_selected_case_ids": list_selected_cases,
        "no_candidates_case_ids": no_candidates_cases,
        "case_results": case_results,
    }

    RESULTS_JSON.write_text(json.dumps(output, indent=2))
    print(f"  ✓ Results written to {RESULTS_JSON}")

    return output


if __name__ == "__main__":
    result = run_preview()
    sys.exit(0 if result else 1)
