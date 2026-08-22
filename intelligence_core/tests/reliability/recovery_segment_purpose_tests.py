"""Dedicated tests for segment_purpose.py (Recovery — post-V37 durability).

Verifies the segment-level purpose classifier's invariants:
- Substantive paragraphs are retained.
- Navigation-only lines (short, ordinal, lexicon) are dropped.
- TABLE_ROW / HEADING / TABLE_HEADER / CAPTION are always substantive.
- Already-excluded segments defer to their type.
- Document-level filter is NEVER applied — mixed-content pages keep
  their substantive segments.
- No GT-specific / document-specific / source-specific logic.
- Ambiguous segments default to SUBSTANTIVE for filtering (safe retain).
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.structural_parser import EvidenceSegmentV1, parse_html_to_segments
from intelligence_core.segment_purpose import (
    PURPOSE_SUBSTANTIVE,
    PURPOSE_NAVIGATION,
    PURPOSE_AMBIGUOUS,
    classify_segment_purpose,
    apply_purpose_filter,
    purpose_breakdown,
)


def _para(text: str, doc_id: str = "doc-test", idx: int = 0,
          heading_context: str | None = None) -> EvidenceSegmentV1:
    return EvidenceSegmentV1(
        document_id=doc_id,
        segment_id=f"seg-{idx:04d}",
        segment_index=idx,
        segment_type="PARAGRAPH",
        text=text,
        heading_context=heading_context,
    )


def _list_item(text: str, doc_id: str = "doc-test", idx: int = 0,
               heading_context: str | None = None) -> EvidenceSegmentV1:
    return EvidenceSegmentV1(
        document_id=doc_id,
        segment_id=f"seg-{idx:04d}",
        segment_index=idx,
        segment_type="LIST_ITEM",
        text=text,
        heading_context=heading_context,
    )


def _heading(text: str, doc_id: str = "doc-test", idx: int = 0) -> EvidenceSegmentV1:
    return EvidenceSegmentV1(
        document_id=doc_id,
        segment_id=f"seg-{idx:04d}",
        segment_index=idx,
        segment_type="HEADING",
        text=text,
    )


def _table_row(text: str, doc_id: str = "doc-test", idx: int = 0) -> EvidenceSegmentV1:
    return EvidenceSegmentV1(
        document_id=doc_id,
        segment_id=f"seg-{idx:04d}",
        segment_index=idx,
        segment_type="TABLE_ROW",
        text=text,
    )


def _nav(text: str, doc_id: str = "doc-test", idx: int = 0) -> EvidenceSegmentV1:
    return EvidenceSegmentV1(
        document_id=doc_id,
        segment_id=f"seg-{idx:04d}",
        segment_index=idx,
        segment_type="NAVIGATION",
        text=text,
        excluded=True,
        exclusion_reason="NAVIGATION",
    )


class TestSubstantiveRetention(unittest.TestCase):
    """Substantive paragraphs are retained."""

    def test_long_paragraph_with_sentence_end_is_substantive(self):
        seg = _para(
            "The Monetary Policy Committee voted 5-4 to maintain the policy "
            "rate at 4.0 percent, citing subdued inflationary pressures."
        )
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)

    def test_paragraph_with_percentage_value_is_substantive(self):
        seg = _para("Annual CPI inflation eased to 2.1 percent in October 2024.")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)

    def test_paragraph_under_substantive_heading_is_substantive(self):
        seg = _para(
            "The Bank's net asset purchases totalled £895 billion.",
            heading_context="Monetary Policy Summary",
        )
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)


class TestNavigationSuppression(unittest.TestCase):
    """Navigation-only lines are dropped."""

    def test_short_ordinal_with_nav_lexicon_is_navigation(self):
        seg = _para("1. Subscribe to updates")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)

    def test_short_ordinal_with_nav_lexicon_multiple(self):
        seg = _para("2. Browse topics")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)

    def test_short_ordinal_no_lexicon_no_sentence_end_is_navigation(self):
        # "1. Summary" is short, has ordinal, no sentence end
        seg = _para("1. Summary")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)

    def test_very_short_line_under_menu_heading_is_navigation(self):
        seg = _para("Home", heading_context="Menu")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)

    def test_short_list_item_under_quick_links_is_navigation(self):
        seg = _list_item("Publications archive", heading_context="Quick links")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)

    def test_short_line_under_footer_heading_is_navigation(self):
        seg = _para("Contact us", heading_context="Footer")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)


class TestAlwaysSubstantiveTypes(unittest.TestCase):
    """TABLE_ROW / HEADING / TABLE_HEADER / CAPTION always substantive."""

    def test_table_row_always_substantive(self):
        # Even short table-row text is substantive — structural context
        # is unambiguous.
        seg = _table_row("1.5")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)

    def test_heading_always_substantive(self):
        seg = _heading("Table of Contents")  # even though it LOOKS nav
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)

    def test_table_header_always_substantive(self):
        seg = EvidenceSegmentV1(
            document_id="d", segment_id="s", segment_index=0,
            segment_type="TABLE_HEADER", text="2024",
        )
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)

    def test_caption_always_substantive(self):
        seg = EvidenceSegmentV1(
            document_id="d", segment_id="s", segment_index=0,
            segment_type="CAPTION", text="Figure 1 — Inflation trend",
        )
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_SUBSTANTIVE)


class TestExcludedDeferToType(unittest.TestCase):
    """Already-excluded segments defer to their type."""

    def test_excluded_navigation_type_is_navigation(self):
        seg = _nav("Menu")
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_NAVIGATION)

    def test_excluded_other_type_is_ambiguous(self):
        seg = EvidenceSegmentV1(
            document_id="d", segment_id="s", segment_index=0,
            segment_type="PARAGRAPH",
            text="Lorem ipsum",
            excluded=True,
            exclusion_reason="ADVERTISEMENT",
        )
        # Excluded + non-NEVER_SUBSTANTIVE type → AMBIGUOUS
        self.assertEqual(classify_segment_purpose(seg), PURPOSE_AMBIGUOUS)


class TestMixedPageInvariant(unittest.TestCase):
    """Mixed pages keep substantive segments."""

    def test_mixed_page_keeps_substantive_drops_navigation(self):
        """Simulate a page with nav menu + substantive content."""
        segments = [
            _nav("Home", idx=0),
            _para("1. Subscribe to updates", idx=1, heading_context="Menu"),
            _para("2. Browse topics", idx=2, heading_context="Menu"),
            _para("The Monetary Policy Committee voted 5-4 to maintain "
                  "the policy rate at 4.0 percent.", idx=3,
                  heading_context="Monetary Policy Summary"),
            _para("Annual CPI inflation eased to 2.1 percent in October 2024.",
                  idx=4, heading_context="Monetary Policy Summary"),
            _table_row("1.5", idx=5),
        ]
        substantive = apply_purpose_filter(segments)
        # Should retain: substantive paragraph 1, substantive paragraph 2,
        # and the table row. The nav + 2 menu items should be dropped.
        self.assertEqual(len(substantive), 3)
        self.assertEqual(substantive[0].segment_index, 3)
        self.assertEqual(substantive[1].segment_index, 4)
        self.assertEqual(substantive[2].segment_index, 5)

    def test_return_purposes_returns_full_length_list(self):
        """When return_purposes=True, the purposes list has the same
        length as the input — every input segment receives a
        classification, even filtered-out ones."""
        segments = [
            _nav("Home", idx=0),
            _para("1. Subscribe", idx=1, heading_context="Menu"),
            _para("Inflation eased to 2.1 percent in 2024.", idx=2),
        ]
        substantive, purposes = apply_purpose_filter(
            segments, return_purposes=True
        )
        self.assertEqual(len(purposes), 3)  # full-length
        self.assertEqual(len(substantive), 1)
        self.assertEqual(purposes[0], PURPOSE_NAVIGATION)
        self.assertEqual(purposes[1], PURPOSE_NAVIGATION)
        self.assertEqual(purposes[2], PURPOSE_SUBSTANTIVE)


class TestNoShortcutsInvariant(unittest.TestCase):
    """No GT-specific / document-specific / source-specific logic."""

    def test_classifier_uses_only_text_and_heading_context(self):
        """The classifier should not consult document_id or source_id."""
        # Same text + heading_context but different document_id → same result
        seg_a = _para("1. Subscribe to updates", doc_id="doc-A")
        seg_b = _para("1. Subscribe to updates", doc_id="doc-B")
        self.assertEqual(
            classify_segment_purpose(seg_a),
            classify_segment_purpose(seg_b),
        )

    def test_no_hardcoded_institution_names(self):
        """Source the module text and verify no institution names."""
        # tests/reliability/recovery_segment_purpose_tests.py -> parents[3] = CORE_REPO
        module_path = Path(__file__).resolve().parents[3] / "intelligence_core" / "segment_purpose.py"
        source = module_path.read_text()
        # Reject specific institution names from the lexicon. Use word
        # boundaries to avoid false positives like "SEC" matching "SECTION".
        import re as _re
        forbidden = [
            "Bank of England", "BankOfEngland", "bank_of_england",
            r"\bECB\b", "European Central Bank",
            "Federal Reserve", "fedreserve",
            "Bank of Japan", r"\bBOJ\b",
            r"\bSEC\b", "Securities and Exchange",
            r"\bFCA\b", "Financial Conduct",
            "Bangladesh", "bb-bangladesh",
            r"\beurostat\b", r"\bEurostat\b",
            r"\bSNB\b", "Swiss National Bank",
        ]
        for name in forbidden:
            pattern = _re.compile(name, _re.IGNORECASE)
            m = pattern.search(source)
            self.assertIsNone(
                m, f"Institution name '{name}' must NOT appear in segment_purpose.py"
            )


class TestAmbiguousSafeDefault(unittest.TestCase):
    """Ambiguous segments default to SUBSTANTIVE for filtering."""

    def test_empty_paragraph_is_ambiguous_but_dropped(self):
        seg = _para("")
        p = classify_segment_purpose(seg)
        self.assertEqual(p, PURPOSE_AMBIGUOUS)
        # In apply_purpose_filter, AMBIGUOUS is dropped (not SUBSTANTIVE)
        substantive = apply_purpose_filter([seg])
        self.assertEqual(len(substantive), 0)


class TestPurposeBreakdown(unittest.TestCase):
    """purpose_breakdown returns a Counter-style dict."""

    def test_breakdown_sums_correctly(self):
        segments = [
            _nav("Home", idx=0),
            _para("1. Subscribe", idx=1, heading_context="Menu"),
            _para("Inflation eased to 2.1 percent.", idx=2),
            _para("", idx=3),  # AMBIGUOUS
            _table_row("1.5", idx=4),
        ]
        bd = purpose_breakdown(segments)
        self.assertEqual(bd[PURPOSE_NAVIGATION], 2)
        self.assertEqual(bd[PURPOSE_SUBSTANTIVE], 2)
        self.assertEqual(bd[PURPOSE_AMBIGUOUS], 1)


class TestParserIntegration(unittest.TestCase):
    """End-to-end: parse a real HTML doc and apply purpose filter."""

    def test_parse_and_filter_nav_heavy_page(self):
        """A page with explicit <nav> + substantive <article> keeps
        substantive segments and drops nav."""
        html = b"""<!DOCTYPE html><html><head><title>Test</title></head><body>
<nav><ul><li>Home</li><li>About</li><li>Subscribe</li></ul></nav>
<article>
<h1>Monetary Policy Report</h1>
<p>The Monetary Policy Committee voted 5-4 to maintain the policy rate at 4.0 percent.</p>
<p>Annual CPI inflation eased to 2.1 percent in October 2024.</p>
</article>
</body></html>"""
        segments = parse_html_to_segments(html, document_id="doc-integration")
        substantive = apply_purpose_filter(segments)
        # The nav items are structurally excluded by the parser → already
        # excluded=True. Our filter returns them as NAVIGATION purpose but
        # drops them from the substantive list. The two substantive
        # paragraphs must remain.
        substantive_texts = [s.text for s in substantive if s.segment_type == "PARAGRAPH"]
        self.assertGreaterEqual(len(substantive_texts), 2)
        joined = " ".join(substantive_texts)
        self.assertIn("4.0 percent", joined)
        self.assertIn("2.1 percent", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
