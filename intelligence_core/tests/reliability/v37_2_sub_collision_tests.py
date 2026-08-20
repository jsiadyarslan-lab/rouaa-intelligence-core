"""V37.2 — Sub-Collision Semantic Tests (PHASE 10).

Tests for the V37.2 SUB-COLLISION FIX directive §3:

  CASE A (count==1 in subgroup):
    → SAFE_SHARED_EVIDENCE only if segment has explicit unit context for metric
    → INSUFFICIENT_EVIDENCE if no unit context

  CASE B (count>1 in subgroup):
    → ALL facts in subgroup → UNRESOLVED_SUBCOLLISION → INSUFFICIENT_EVIDENCE

  Additional tests:
    - same value + same metric + 2 facts + 1 segment → both INSUFFICIENT
    - same value + same metric + 3 facts + 1 segment → all 3 INSUFFICIENT
    - different metric + one fact each (with unit context) → SAFE_SHARED
    - different metric + multiple facts in each subgroup → each subgroup INSUFFICIENT
    - same value + different metric + different segments → resolve independently
    - Case A (doc-a72c0918e27dd12b, 30 value=5 facts)
    - Case B (doc-8700a0859c829c44, 7 value=0.1 facts)
    - Case C (doc-7c5cd3967c2f9f10, exposes sub-collisions)

Required invariant (§9):
  safe_shared_evidence_facts + unresolved_collision_facts == total_collision_facts
  No fact may disappear from accounting.
"""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from collections import Counter

from intelligence_core.structural_parser import parse_html_to_segments
from intelligence_core.evidence_selection import (
    select_evidence_segment, select_evidence_for_document,
    audit_collisions, EvidenceSelectionResult,
    DIRECT, INDIRECT, INSUFFICIENT_EVIDENCE, INVALID,
)
from intelligence_core.contracts import Fact


def _fact(fid: str, value: str, metric: str, occurrence: int = 1) -> Fact:
    return Fact(
        fact_id=fid, fact_version=1,
        representation_id="rep-test", document_id="doc-test",
        metric=metric, value=value, occurrence=occurrence,
    )


class Test1SameValueMetric2Facts1Segment(unittest.TestCase):
    """1. same value + same metric + 2 facts + 1 segment → both INSUFFICIENT."""

    def test_two_facts_same_value_metric_segment_unresolved(self):
        html = b"<p>The rate was 2.4% in Q1 2026.</p>"
        facts = [_fact("F1", "2.4", "percentage_statistic"),
                 _fact("F2", "2.4", "percentage_statistic")]
        results = select_evidence_for_document(facts, html, document_id="doc1")
        for r in results:
            self.assertEqual(r.status, INSUFFICIENT_EVIDENCE,
                              f"Expected INSUFFICIENT, got {r.status} — {r.reason}")
            self.assertIn("UNRESOLVED_SUBCOLLISION", r.reason)


class Test2SameValueMetric3Facts1Segment(unittest.TestCase):
    """2. same value + same metric + 3 facts + 1 segment → all 3 INSUFFICIENT."""

    def test_three_facts_same_value_metric_segment_unresolved(self):
        html = b"<p>Rate was 5% in Q1.</p>"
        facts = [_fact(f"F{i+1}", "5", "percentage_statistic") for i in range(3)]
        results = select_evidence_for_document(facts, html, document_id="doc2")
        for i, r in enumerate(results):
            self.assertEqual(r.status, INSUFFICIENT_EVIDENCE,
                              f"F{i+1}: expected INSUFFICIENT, got {r.status}")
            self.assertIn("UNRESOLVED_SUBCOLLISION", r.reason)


class Test3DifferentMetricOneFactEach(unittest.TestCase):
    """3. different metric + one fact each → SAFE_SHARED only when metric/unit context is explicit."""

    def test_safe_shared_when_unit_context_present(self):
        # Paragraph contains BOTH "5%" and "$5 million" — explicit unit context for both metrics
        html = b"<p>The rate was 5% and revenue was $5 million in Q1.</p>"
        facts = [_fact("F1", "5", "percentage_statistic"),
                 _fact("F2", "5", "usd_amount")]
        results = select_evidence_for_document(facts, html, document_id="doc3")
        # Both facts have count==1 in their respective subgroups
        # AND segment has explicit unit context for each (% and $)
        # → SAFE_SHARED_EVIDENCE
        for r in results:
            self.assertNotEqual(r.status, INSUFFICIENT_EVIDENCE,
                                f"Should be SAFE_SHARED, got INSUFFICIENT — {r.reason}")
            self.assertIn("SAFE_SHARED_EVIDENCE", r.reason)

    def test_unresolved_when_unit_context_missing(self):
        # Paragraph contains "5" but NO "%" and NO "$"
        # → no explicit unit context for any metric → INSUFFICIENT for both
        html = b"<p>The number 5 appeared in the report.</p>"
        facts = [_fact("F1", "5", "percentage_statistic"),
                 _fact("F2", "5", "usd_amount")]
        results = select_evidence_for_document(facts, html, document_id="doc4")
        # No unit context → both facts should be INSUFFICIENT
        for r in results:
            self.assertEqual(r.status, INSUFFICIENT_EVIDENCE,
                              f"Expected INSUFFICIENT (no unit context), got {r.status}")


class Test4DifferentMetricMultipleFactsEachSubgroup(unittest.TestCase):
    """4. different metric + multiple facts in each subgroup → each subgroup independently INSUFFICIENT."""

    def test_each_subgroup_independently_unresolved(self):
        # Segment contains BOTH "%" and "$" (so unit context exists)
        # But each metric subgroup has >1 fact → both subgroups INSUFFICIENT
        html = b"<p>Rate 0.1% and revenue $0.1 million - both 0.1 values.</p>"
        facts = [
            _fact("P1", "0.1", "percentage_statistic"),
            _fact("P2", "0.1", "percentage_statistic"),  # subgroup count=2 → INSUFFICIENT
            _fact("U1", "0.1", "usd_amount"),
            _fact("U2", "0.1", "usd_amount"),  # subgroup count=2 → INSUFFICIENT
        ]
        results = select_evidence_for_document(facts, html, document_id="doc5")
        for r in results:
            self.assertEqual(r.status, INSUFFICIENT_EVIDENCE,
                              f"Expected INSUFFICIENT (subgroup count>1), got {r.status} — {r.reason}")
            self.assertIn("UNRESOLVED_SUBCOLLISION", r.reason)


class Test5SameValueDifferentMetricDifferentSegments(unittest.TestCase):
    """5. same value + different metric + different segments → resolve independently."""

    def test_different_segments_resolve_independently(self):
        # Each fact selects a DIFFERENT segment (one paragraph per metric)
        html = b"<p>Rate was 5% in Q1.</p><p>Revenue was $5 million in Q1.</p>"
        facts = [_fact("F1", "5", "percentage_statistic"),
                 _fact("F2", "5", "usd_amount")]
        results = select_evidence_for_document(facts, html, document_id="doc6")
        # Each fact selects a different segment → no collision → both resolve
        self.assertIsNotNone(results[0].selected_segment)
        self.assertIsNotNone(results[1].selected_segment)
        self.assertNotEqual(results[0].selected_segment.segment_id,
                            results[1].selected_segment.segment_id)
        # Verify correct segment per metric
        self.assertIn("%", results[0].selected_segment.text)
        self.assertIn("$", results[1].selected_segment.text)


class Test6CaseARegression(unittest.TestCase):
    """6. Case A regression — 30 value=5 facts → all INSUFFICIENT."""

    def test_case_a_listing_page_30_value_5_facts_all_insufficient(self):
        # Load real preflight data for doc-a72c0918e27dd12b
        preflight = Path("intelligence_core/tests/reliability/v37_2_raw_blob_availability.json")
        if not preflight.exists():
            self.skipTest("preflight JSON not found")
        with preflight.open() as f:
            cases = json.load(f)
        doc_id = "doc-a72c0918e27dd12b"
        doc_cases = [c for c in cases if c["document_id"] == doc_id and c["value"] == "5"]
        if not doc_cases:
            self.skipTest(f"no value=5 cases for {doc_id}")
        blob_bytes = Path(doc_cases[0]["raw_location"]).read_bytes()
        facts = [Fact(fact_id=c["gt_fact_id"], fact_version=1,
                      representation_id=c["representation_id"],
                      document_id=c["document_id"],
                      metric=c["metric"], value=c["value"], occurrence=1)
                 for c in doc_cases]
        results = select_evidence_for_document(facts, blob_bytes, document_id=doc_id)
        insufficient_count = sum(1 for r in results if r.status == INSUFFICIENT_EVIDENCE)
        self.assertEqual(insufficient_count, len(doc_cases),
                         f"Expected all {len(doc_cases)} value=5 facts to be INSUFFICIENT, "
                         f"got {insufficient_count}")
        # Verify no fact has a selected_segment
        for r in results:
            self.assertIsNone(r.selected_segment,
                              f"Fact {r.fact_id} should not have selected_segment")


class Test7CaseB(unittest.TestCase):
    """7. Case B — doc-8700a0859c829c44, 7 value=0.1 facts.

    Expected structure: 3 facts (percentage_statistic) subgroup + 4 facts (usd_amount) subgroup.
    Both subgroups have count>1 → all 7 INSUFFICIENT.
    """

    def test_case_b_7_value_01_facts_all_insufficient(self):
        preflight = Path("intelligence_core/tests/reliability/v37_2_raw_blob_availability.json")
        if not preflight.exists():
            self.skipTest("preflight JSON not found")
        with preflight.open() as f:
            cases = json.load(f)
        doc_id = "doc-8700a0859c829c44"
        doc_cases = [c for c in cases if c["document_id"] == doc_id and c["value"] == "0.1"]
        self.assertEqual(len(doc_cases), 7,
                         f"Expected 7 value=0.1 facts in Case B, got {len(doc_cases)}")
        # Subgroup structure check
        pct_count = sum(1 for c in doc_cases if c["metric"] == "percentage_statistic")
        usd_count = sum(1 for c in doc_cases if c["metric"] == "usd_amount")
        self.assertEqual(pct_count, 3, f"Expected 3 percentage facts, got {pct_count}")
        self.assertEqual(usd_count, 4, f"Expected 4 usd_amount facts, got {usd_count}")
        blob_bytes = Path(doc_cases[0]["raw_location"]).read_bytes()
        facts = [Fact(fact_id=c["gt_fact_id"], fact_version=1,
                      representation_id=c["representation_id"],
                      document_id=c["document_id"],
                      metric=c["metric"], value=c["value"], occurrence=1)
                 for c in doc_cases]
        results = select_evidence_for_document(facts, blob_bytes, document_id=doc_id)
        # Per directive §5: each subgroup with count>1 → all facts in subgroup → INSUFFICIENT
        insufficient_count = sum(1 for r in results if r.status == INSUFFICIENT_EVIDENCE)
        self.assertEqual(insufficient_count, 7,
                         f"Expected all 7 facts INSUFFICIENT (both subgroups have count>1), "
                         f"got {insufficient_count} INSUFFICIENT")


class Test8CaseC(unittest.TestCase):
    """8. Case C — doc-7c5cd3967c2f9f10.

    Expected: expose previously hidden sub-collisions.
    Per directive §6: every subgroup with same value+metric+segment+count>1
    must become INSUFFICIENT_EVIDENCE.
    """

    def test_case_c_exposes_sub_collisions(self):
        preflight = Path("intelligence_core/tests/reliability/v37_2_raw_blob_availability.json")
        if not preflight.exists():
            self.skipTest("preflight JSON not found")
        with preflight.open() as f:
            cases = json.load(f)
        doc_id = "doc-7c5cd3967c2f9f10"
        doc_cases = [c for c in cases if c["document_id"] == doc_id]
        self.assertEqual(len(doc_cases), 27,
                         f"Expected 27 facts in Case C, got {len(doc_cases)}")
        blob_bytes = Path(doc_cases[0]["raw_location"]).read_bytes()
        facts = [Fact(fact_id=c["gt_fact_id"], fact_version=1,
                      representation_id=c["representation_id"],
                      document_id=c["document_id"],
                      metric=c["metric"], value=c["value"], occurrence=1)
                 for c in doc_cases]
        results = select_evidence_for_document(facts, blob_bytes, document_id=doc_id)
        # Run collision audit — should expose unresolved sub-collisions
        audit = audit_collisions(results)
        # Verify invariant (§9): safe + unresolved == total_collision_facts
        self.assertTrue(audit["invariant_holds"],
                        "Invariant violation: facts disappeared from accounting")
        # Report structure
        print(f"\n  Case C audit:")
        print(f"    total_collision_facts:        {audit['total_collision_facts']}")
        print(f"    unresolved_collision_facts:    {audit['unresolved_collision_facts']}")
        print(f"    safe_shared_evidence_facts:    {audit['safe_shared_evidence_facts']}")
        print(f"    unresolved_collision_groups:   {audit['unresolved_collision_groups']}")
        print(f"    safe_shared_evidence_groups:   {audit['safe_shared_evidence_groups']}")
        # Verify: any subgroup with count>1 → all facts in subgroup INSUFFICIENT
        for sg in audit["unresolved_collisions"]:
            self.assertGreater(sg["fact_count"], 0)
            # Each fact in subgroup should be INSUFFICIENT
            for r in results:
                if r.fact_id in sg["fact_ids"]:
                    self.assertEqual(r.status, INSUFFICIENT_EVIDENCE,
                                      f"Fact {r.fact_id} in unresolved subgroup should be INSUFFICIENT")


# ═══════════════════════════════════════════════════════════════════════
# Test runner
# ═══════════════════════════════════════════════════════════════════════

def run_all_sub_collision_tests():
    """Run all V37.2 sub-collision tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_classes = [
        Test1SameValueMetric2Facts1Segment,
        Test2SameValueMetric3Facts1Segment,
        Test3DifferentMetricOneFactEach,
        Test4DifferentMetricMultipleFactsEachSubgroup,
        Test5SameValueDifferentMetricDifferentSegments,
        Test6CaseARegression,
        Test7CaseB,
        Test8CaseC,
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_all_sub_collision_tests()
    sys.exit(0 if success else 1)
