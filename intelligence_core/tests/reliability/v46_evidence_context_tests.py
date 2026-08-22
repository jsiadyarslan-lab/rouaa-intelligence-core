"""Dedicated V46 tests for evidence_context.py.

Tests the context recovery invariants:
- Original fact values preserved exactly (no truncation, no extension)
- Context window builds correctly using structural segments
- Signal detection is deterministic
- Provenance is preserved per segment
- Context quality classification rules
- No navigation evidence introduced (purpose filter applied)
- Bounded neighborhood (capped at 5 segments per side)
- Empty/None inputs handled safely
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.structural_parser import EvidenceSegmentV1, parse_html_to_segments
from intelligence_core.segment_purpose import apply_purpose_filter
from intelligence_core.evidence_context import (
    EvidenceContextV1,
    CONTEXT_SUFFICIENT,
    CONTEXT_PARTIAL,
    CONTEXT_INSUFFICIENT,
    find_primary_segment,
    build_context_window,
    classify_context_quality,
    build_evidence_context,
    build_contexts_for_io,
    _detect_entity_signals,
    _detect_temporal_signals,
    _detect_state_signals,
)


def _seg(text: str, idx: int = 0, sid: str = None, stype: str = "PARAGRAPH",
         heading: str = None, parent: str = None) -> EvidenceSegmentV1:
    return EvidenceSegmentV1(
        document_id="doc-test",
        segment_id=sid or f"seg-{idx:04d}",
        segment_index=idx,
        segment_type=stype,
        parent_segment_id=parent,
        text=text,
        heading_context=heading,
    )


class TestExcerptPreservation(unittest.TestCase):
    """Original fact excerpts MUST be preserved exactly."""

    def test_excerpt_unchanged_in_context(self):
        excerpt = "The MPC voted 5-4 to maintain the policy rate at 4.0 percent."
        segs = [_seg("The MPC voted 5-4 to maintain the policy rate at 4.0 percent.")]
        ctx = build_evidence_context("fact-1", "doc-1", excerpt, segs)
        self.assertEqual(ctx.evidence_excerpt, excerpt)

    def test_excerpt_not_truncated_in_context(self):
        long_excerpt = "A" * 500  # longer than typical 300-char truncation
        segs = [_seg("A" * 500)]
        ctx = build_evidence_context("fact-1", "doc-1", long_excerpt, segs)
        self.assertEqual(ctx.evidence_excerpt, long_excerpt)
        self.assertEqual(len(ctx.evidence_excerpt), 500)

    def test_excerpt_not_extended_in_context(self):
        # Short excerpt inside longer segment — context_after should not
        # bleed into evidence_excerpt
        excerpt = "policy rate"
        seg_text = "The MPC voted to maintain the policy rate at 4.0 percent."
        segs = [_seg(seg_text)]
        ctx = build_evidence_context("fact-1", "doc-1", excerpt, segs)
        self.assertEqual(ctx.evidence_excerpt, "policy rate")
        self.assertNotIn("4.0", ctx.evidence_excerpt)


class TestContextWindow(unittest.TestCase):
    """Context window builds correctly using structural segments."""

    def test_primary_segment_found_by_substring(self):
        segs = [_seg("The MPC voted to maintain the policy rate.")]
        primary = find_primary_segment(segs, "policy rate")
        self.assertIsNotNone(primary)
        self.assertEqual(primary.segment_id, segs[0].segment_id)

    def test_primary_segment_not_found_returns_none(self):
        segs = [_seg("Some unrelated text.")]
        primary = find_primary_segment(segs, "policy rate")
        self.assertIsNone(primary)

    def test_context_before_includes_preceding_segment(self):
        segs = [
            _seg("Bank of England press release.", idx=0),
            _seg("The policy rate is 4.0 percent.", idx=1),
        ]
        primary = segs[1]
        ctx_ids, ctx_before, ctx_after, _, _ = build_context_window(segs, primary)
        self.assertIn("Bank of England", ctx_before)
        self.assertIn(segs[0].segment_id, ctx_ids)
        self.assertEqual(primary.segment_id, ctx_ids[len(ctx_ids) // 2 if ctx_ids else 0] if ctx_ids else None,
                         primary.segment_id)  # primary is in the middle

    def test_context_after_includes_following_segment(self):
        segs = [
            _seg("The policy rate is 4.0 percent.", idx=0),
            _seg("Annual CPI inflation eased to 2.1 percent.", idx=1),
        ]
        primary = segs[0]
        ctx_ids, ctx_before, ctx_after, _, _ = build_context_window(segs, primary)
        self.assertIn("2.1 percent", ctx_after)

    def test_neighborhood_capped_at_5_segments(self):
        # 10 preceding + primary + 10 following — only 5+1+5 should be in context
        segs = [_seg(f"Segment {i} text.", idx=i) for i in range(21)]
        primary = segs[10]
        ctx_ids, _, _, before_segs, after_segs = build_context_window(segs, primary)
        self.assertLessEqual(len(before_segs), 5)
        self.assertLessEqual(len(after_segs), 5)

    def test_excluded_segments_skipped(self):
        # An excluded segment should not contribute to context
        segs = [
            _seg("Navigation menu.", idx=0),  # we'll mark as excluded manually
            _seg("The policy rate is 4.0 percent.", idx=1),
            _seg("Annual CPI inflation eased to 2.1 percent.", idx=2),
        ]
        segs[0].excluded = True
        segs[0].exclusion_reason = "NAVIGATION"
        primary = segs[1]
        ctx_ids, ctx_before, _, _, _ = build_context_window(segs, primary)
        self.assertNotIn("Navigation menu", ctx_before)


class TestSignalDetection(unittest.TestCase):
    """Signal detection is deterministic."""

    def test_entity_signals_long_form(self):
        text = "The European Central Bank announced a policy decision."
        sigs = _detect_entity_signals(text)
        self.assertIn(("ECB", "European Central Bank"), sigs)

    def test_entity_signals_acronym(self):
        text = "ECB announced a policy decision."
        sigs = _detect_entity_signals(text)
        self.assertTrue(any(s[0] == "ECB" for s in sigs))

    def test_entity_signals_none(self):
        text = "Some random text without institutions."
        sigs = _detect_entity_signals(text)
        self.assertEqual(sigs, [])

    def test_temporal_signals_month_year(self):
        text = "In October 2024, the rate was 4.0%."
        sigs = _detect_temporal_signals(text)
        self.assertTrue(any("October" in s[1] for s in sigs))

    def test_temporal_signals_iso_date(self):
        text = "Published: 2024-10-15"
        sigs = _detect_temporal_signals(text)
        self.assertTrue(any(s[0] == "iso_date" for s in sigs))

    def test_state_signals_revised(self):
        text = "The figure was revised upward."
        sigs = _detect_state_signals(text)
        self.assertTrue(any(s[0] == "REVISED" for s in sigs))

    def test_state_signals_increased(self):
        text = "The rate increased to 4.5%."
        sigs = _detect_state_signals(text)
        self.assertTrue(any(s[0] == "INCREASED" for s in sigs))


class TestContextQualityClassification(unittest.TestCase):
    """Context quality classification rules."""

    def test_sufficient_when_200_chars_and_signals(self):
        primary = _seg("policy rate.")
        quality = classify_context_quality(
            "A" * 150, "B" * 150, primary,
            entity_signals=[("ECB", "ECB")],
            temporal_signals=[], state_signals=[],
        )
        self.assertEqual(quality, CONTEXT_SUFFICIENT)

    def test_partial_when_50_chars_no_signals(self):
        primary = _seg("policy rate.")
        quality = classify_context_quality(
            "A" * 50, "", primary, [], [], []
        )
        self.assertEqual(quality, CONTEXT_PARTIAL)

    def test_partial_when_signals_but_short_context(self):
        primary = _seg("policy rate.")
        quality = classify_context_quality(
            "A" * 10, "", primary,
            entity_signals=[("ECB", "ECB")], temporal_signals=[], state_signals=[],
        )
        self.assertEqual(quality, CONTEXT_PARTIAL)

    def test_insufficient_when_no_primary(self):
        quality = classify_context_quality("A" * 500, "B" * 500, None, [], [], [])
        self.assertEqual(quality, CONTEXT_INSUFFICIENT)

    def test_insufficient_when_no_context_no_signals(self):
        primary = _seg("policy rate.")
        quality = classify_context_quality("", "", primary, [], [], [])
        self.assertEqual(quality, CONTEXT_INSUFFICIENT)


class TestProvenance(unittest.TestCase):
    """Signal provenance is preserved per segment."""

    def test_entity_signal_provenance_lists_contributing_segment(self):
        segs = [
            _seg("Bank of England announcement.", idx=0),
            _seg("The policy rate is 4.0%.", idx=1),
        ]
        ctx = build_evidence_context("fact-1", "doc-1", "policy rate", segs)
        # The entity signal "BOE" should be in provenance from seg-0000
        all_prov_entities = []
        for prov in ctx.entity_signal_provenance:
            all_prov_entities.extend(prov["signals"])
        self.assertIn("BOE", all_prov_entities)

    def test_temporal_signal_provenance_lists_contributing_segment(self):
        segs = [
            _seg("In October 2024, the bank announced.", idx=0),
            _seg("The policy rate is 4.0%.", idx=1),
        ]
        ctx = build_evidence_context("fact-1", "doc-1", "policy rate", segs)
        all_prov_temporal = []
        for prov in ctx.temporal_signal_provenance:
            all_prov_temporal.extend(prov["signals"])
        # Should contain a temporal signal type
        self.assertTrue(len(all_prov_temporal) > 0)


class TestSafetyInvariants(unittest.TestCase):
    """V46 §11 safety invariants."""

    def test_no_navigation_in_context_when_purpose_filter_applied(self):
        """When apply_purpose_filter is called before context building,
        navigation segments should not contribute to context."""
        html = b"""<!DOCTYPE html><html><head><title>Test</title></head><body>
<nav><ul><li>Home</li><li>About</li></ul></nav>
<article>
<h1>Bank of England Monetary Policy</h1>
<p>The MPC voted to maintain the policy rate at 4.0 percent in October 2024.</p>
<p>Annual CPI inflation eased to 2.1 percent.</p>
</article>
</body></html>"""
        segs = parse_html_to_segments(html, document_id="doc-1")
        segs = apply_purpose_filter(segs)
        # Find a substantive segment containing "policy rate"
        primary = None
        for s in segs:
            if "policy rate" in (s.text or ""):
                primary = s
                break
        self.assertIsNotNone(primary)
        ctx = build_evidence_context("fact-1", "doc-1", "policy rate", segs)
        # Context should NOT contain "Home" or "About" (nav)
        self.assertNotIn("Home", ctx.context_before)
        self.assertNotIn("Home", ctx.context_after)
        self.assertNotIn("About", ctx.context_before)
        self.assertNotIn("About", ctx.context_after)

    def test_fact_id_preserved_in_context(self):
        segs = [_seg("The policy rate is 4.0%.")]
        ctx = build_evidence_context("fact-abc-123", "doc-xyz", "policy rate", segs)
        self.assertEqual(ctx.fact_id, "fact-abc-123")
        self.assertEqual(ctx.document_id, "doc-xyz")

    def test_evidence_id_links_to_existing_evidence(self):
        segs = [_seg("The policy rate is 4.0%.")]
        ctx = build_evidence_context("fact-1", "doc-1", "policy rate", segs, evidence_id="ev-orig-001")
        self.assertEqual(ctx.evidence_id, "ev-orig-001")

    def test_empty_segments_returns_insufficient(self):
        ctx = build_evidence_context("fact-1", "doc-1", "anything", [])
        self.assertEqual(ctx.context_quality, CONTEXT_INSUFFICIENT)
        self.assertIsNone(ctx.primary_segment_id)

    def test_no_overshare_in_excerpt(self):
        """The excerpt must NOT include surrounding context — context
        is added separately as context_before / context_after."""
        seg_text = "Bank of England. The MPC voted to maintain the policy rate at 4.0%."
        segs = [_seg(seg_text)]
        ctx = build_evidence_context("fact-1", "doc-1", "policy rate", segs)
        self.assertEqual(ctx.evidence_excerpt, "policy rate")
        self.assertNotIn("Bank of England", ctx.evidence_excerpt)


class TestBuildContextsForIO(unittest.TestCase):
    """build_contexts_for_io builds context for all facts in an IO."""

    def test_build_contexts_for_io_handles_multiple_facts(self):
        io = {
            "io_id": "io-test",
            "document_id": "doc-test",
            "facts": [
                {"fact_id": "fact-1", "metric": "policy_rate", "value": "4.0%",
                 "excerpt": "The MPC voted to maintain the policy rate at 4.0 percent."},
                {"fact_id": "fact-2", "metric": "inflation_rate", "value": "2.1%",
                 "excerpt": "Annual CPI inflation eased to 2.1 percent in October 2024."},
            ],
            "evidence": [
                {"fact_id": "fact-1", "excerpt": "The MPC voted to maintain the policy rate at 4.0 percent.", "evidence_id": "ev-1"},
                {"fact_id": "fact-2", "excerpt": "Annual CPI inflation eased to 2.1 percent in October 2024.", "evidence_id": "ev-2"},
            ],
        }
        segs = [
            _seg("Bank of England press release for October 2024.", idx=0),
            _seg("The MPC voted to maintain the policy rate at 4.0 percent.", idx=1),
            _seg("Annual CPI inflation eased to 2.1 percent in October 2024.", idx=2),
        ]
        contexts = build_contexts_for_io(io, segs)
        self.assertEqual(len(contexts), 2)
        self.assertEqual(contexts[0].fact_id, "fact-1")
        self.assertEqual(contexts[1].fact_id, "fact-2")
        # Both should link to their original evidence IDs
        self.assertEqual(contexts[0].evidence_id, "ev-1")
        self.assertEqual(contexts[1].evidence_id, "ev-2")
        # Excerpts preserved exactly
        self.assertIn("policy rate", contexts[0].evidence_excerpt)
        self.assertIn("CPI inflation", contexts[1].evidence_excerpt)
        # Context should pick up "Bank of England" from preceding segment
        all_entity_sigs = []
        for c in contexts:
            for s in c.entity_signals:
                all_entity_sigs.append(s["entity"])
        self.assertIn("BOE", all_entity_sigs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
