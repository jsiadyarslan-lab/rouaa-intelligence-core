"""V37.2 — Structural Evidence Regression Suite.

Covers the 18 minimum coverage points from V37.2 IMPLEMENTATION DIRECTIVE
PHASE 7:

  1.  parent hierarchy
  2.  navigation exclusion
  3.  role exclusion
  4.  heading context
  5.  paragraph integrity
  6.  inline tags
  7.  malformed inline HTML
  8.  table row semantics
  9.  table column semantics
  10. multi-row headers
  11. colspan (existing-test-supported scope)
  12. table period/unit
  13. repeated table values
  14. occurrence ambiguity
  15. cross-metric collision
  16. insufficient evidence
  17. backward compatibility
  18. deterministic segment IDs

All tests are deterministic. No network. No I/O. Pure parser-state.

Run:
    python -m intelligence_core.tests.reliability.v37_2_structural_evidence_test
"""
from __future__ import annotations
import unittest
from intelligence_core.structural_parser import (
    EvidenceSegmentV1, StructuralHTMLParser, parse_html_to_segments,
    PRIMARY_EVIDENCE_TYPES, EXCLUDED_TYPES,
    detect_unit, detect_period,
)
from intelligence_core.evidence_selection import (
    select_evidence_segment, select_evidence_for_document,
    score_segment, EvidenceSelectionResult,
    DIRECT, INDIRECT, INSUFFICIENT_EVIDENCE, INVALID,
)
from intelligence_core.contracts import Evidence, Fact


def _fact(fact_id: str, value: str, metric: str, occurrence: int = 1) -> Fact:
    return Fact(
        fact_id=fact_id, fact_version=1,
        representation_id="rep-test", document_id="doc-test",
        metric=metric, value=value, occurrence=occurrence,
    )


class Test1ParentHierarchy(unittest.TestCase):
    """1. parent hierarchy — HEADING → PARAGRAPH, TABLE → TABLE_ROW, etc."""

    def test_heading_to_paragraph_parent(self):
        html = b"<h2>GDP Statistics</h2><p>GDP grew by 2.4% in Q1 2026.</p>"
        segs = parse_html_to_segments(html, document_id="doc1")
        # Expect: HEADING segment + PARAGRAPH segment, paragraph's parent is heading
        types = [s.segment_type for s in segs]
        self.assertIn("HEADING", types)
        self.assertIn("PARAGRAPH", types)
        h_idx = types.index("HEADING")
        p_idx = types.index("PARAGRAPH")
        # The paragraph's parent_segment_id should equal the heading's segment_id
        self.assertEqual(segs[p_idx].parent_segment_id, segs[h_idx].segment_id,
                         "PARAGRAPH parent must be the preceding HEADING")

    def test_heading_to_table_row_parent(self):
        html = (b"<h2>Economic Indicators</h2>"
                b"<table><thead><tr><th>Metric</th><th>Q1 2026</th></tr></thead>"
                b"<tbody><tr><td>GDP</td><td>2.4%</td></tr></tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc2")
        h_idx = next(i for i, s in enumerate(segs) if s.segment_type == "HEADING")
        tr_idx = next(i for i, s in enumerate(segs) if s.segment_type == "TABLE_ROW")
        # TABLE_ROW parent must be the heading (since we don't emit a TABLE segment)
        self.assertEqual(segs[tr_idx].parent_segment_id, segs[h_idx].segment_id,
                         "TABLE_ROW parent must be the heading")

    def test_heading_to_list_item_parent(self):
        html = b"<h2>Key Points</h2><ul><li>First point</li><li>Second point</li></ul>"
        segs = parse_html_to_segments(html, document_id="doc3")
        h_idx = next(i for i, s in enumerate(segs) if s.segment_type == "HEADING")
        li_indices = [i for i, s in enumerate(segs) if s.segment_type == "LIST_ITEM"]
        self.assertEqual(len(li_indices), 2)
        for li_idx in li_indices:
            self.assertEqual(segs[li_idx].parent_segment_id, segs[h_idx].segment_id,
                             "LIST_ITEM parent must be the heading")

    def test_no_parent_for_orphan_paragraph(self):
        html = b"<p>Orphan paragraph with no heading.</p>"
        segs = parse_html_to_segments(html, document_id="doc4")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].segment_type, "PARAGRAPH")
        self.assertIsNone(segs[0].parent_segment_id,
                          "Paragraph without heading must have parent=None")


class Test2NavigationExclusion(unittest.TestCase):
    """2. navigation exclusion — <nav> children marked excluded."""

    def test_nav_paragraph_excluded(self):
        html = b"<nav><p>Home Menu About Contact</p></nav><p>Real content here.</p>"
        segs = parse_html_to_segments(html, document_id="doc5")
        # Both paragraphs should exist; the one in <nav> must be excluded=True
        excluded_paras = [s for s in segs if s.segment_type == "PARAGRAPH" and s.excluded]
        non_excluded_paras = [s for s in segs if s.segment_type == "PARAGRAPH" and not s.excluded]
        self.assertEqual(len(excluded_paras), 1, "nav paragraph must be excluded")
        self.assertEqual(len(non_excluded_paras), 1, "real paragraph must not be excluded")
        self.assertEqual(excluded_paras[0].exclusion_reason, "NAVIGATION")


class Test3RoleExclusion(unittest.TestCase):
    """3. role exclusion — role='navigation' / 'banner' / 'contentinfo'."""

    def test_role_navigation_excluded(self):
        html = (b"<div role='navigation'><p>Nav menu</p></div>"
                b"<p>Real paragraph with 5% rate.</p>")
        segs = parse_html_to_segments(html, document_id="doc6")
        nav_para = [s for s in segs if s.segment_type == "PARAGRAPH" and s.excluded]
        real_para = [s for s in segs if s.segment_type == "PARAGRAPH" and not s.excluded]
        self.assertEqual(len(nav_para), 1)
        self.assertEqual(len(real_para), 1)
        self.assertIn("ROLE_NAVIGATION", nav_para[0].exclusion_reason or "")


class Test4HeadingContext(unittest.TestCase):
    """4. heading context — heading_context attached to children."""

    def test_heading_context_propagates(self):
        html = (b"<h2>Inflation Report</h2>"
                b"<p>The inflation rate was 3.2% in June 2026.</p>"
                b"<p>This represents an increase from 3.0% in May.</p>")
        segs = parse_html_to_segments(html, document_id="doc7")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 2)
        for p in paras:
            self.assertEqual(p.heading_context, "Inflation Report",
                              "Both paragraphs must inherit heading_context")


class Test5ParagraphIntegrity(unittest.TestCase):
    """5. paragraph integrity — no splitting on structural boundaries."""

    def test_single_paragraph_emits_one_segment(self):
        html = b"<p>GDP grew by 2.4 percent in Q1 2026.</p>"
        segs = parse_html_to_segments(html, document_id="doc8")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertEqual(paras[0].text, "GDP grew by 2.4 percent in Q1 2026.")


class Test6InlineTags(unittest.TestCase):
    """6. inline tags — <b>, <strong>, <i>, <em>, <a>, <span> don't split paragraphs."""

    def test_bold_inline_tag(self):
        html = b"<p>The <b>rate</b> was 3.5%.</p>"
        segs = parse_html_to_segments(html, document_id="doc9")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("rate", paras[0].text)
        self.assertIn("3.5%", paras[0].text)

    def test_strong_inline_tag(self):
        html = b"<p>Revenue increased <strong>significantly</strong> by 5%.</p>"
        segs = parse_html_to_segments(html, document_id="doc10")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("significantly", paras[0].text)
        self.assertIn("5%", paras[0].text)

    def test_emphasis_inline_tag(self):
        html = b"<p>The figure <em>exceeded</em> expectations at 4.2%.</p>"
        segs = parse_html_to_segments(html, document_id="doc11")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("exceeded", paras[0].text)

    def test_anchor_inline_tag(self):
        html = b"<p>See <a href='report.html'>the full report</a> for 3.1%.</p>"
        segs = parse_html_to_segments(html, document_id="doc12")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("the full report", paras[0].text)
        self.assertIn("3.1%", paras[0].text)

    def test_span_inline_tag(self):
        html = b"<p>The <span class='highlight'>GDP</span> grew 2.1%.</p>"
        segs = parse_html_to_segments(html, document_id="doc13")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("GDP", paras[0].text)
        self.assertIn("2.1%", paras[0].text)

    def test_italic_inline_tag(self):
        html = b"<p>The <i>current</i> rate is 5.25%.</p>"
        segs = parse_html_to_segments(html, document_id="doc14")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("current", paras[0].text)


class Test7MalformedInlineHTML(unittest.TestCase):
    """7. malformed inline HTML — unclosed <b>, <strong>, <i>, <em>, <a>, <span>."""

    def test_unclosed_bold(self):
        # <p>Unclosed <b>paragraph — the <b> is never closed before </p>
        # The text "Unclosed paragraph" should remain one logical paragraph
        html = b"<p>Unclosed <b>paragraph"
        segs = parse_html_to_segments(html, document_id="doc15")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        # Even without </p>, on close() the buffer should flush
        self.assertEqual(len(paras), 1, "Unclosed <b> must not split the paragraph")
        self.assertIn("Unclosed", paras[0].text)
        self.assertIn("paragraph", paras[0].text)

    def test_unclosed_strong(self):
        html = b"<p>Real <strong>content here"
        segs = parse_html_to_segments(html, document_id="doc16")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("Real", paras[0].text)
        self.assertIn("content", paras[0].text)

    def test_unclosed_em(self):
        html = b"<p>Some <em>important fact at 4% rate"
        segs = parse_html_to_segments(html, document_id="doc17")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("4%", paras[0].text)

    def test_unclosed_anchor(self):
        html = b"<p>Click <a href='x'>here for the 5% increase"
        segs = parse_html_to_segments(html, document_id="doc18")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("here", paras[0].text)
        self.assertIn("5%", paras[0].text)

    def test_unclosed_span(self):
        html = b"<p>Real <span>content with 3.2% rate"
        segs = parse_html_to_segments(html, document_id="doc19")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1)
        self.assertIn("content", paras[0].text)
        self.assertIn("3.2%", paras[0].text)

    def test_multiple_unclosed_inline(self):
        html = b"<p>Text <b>with <em>nested <span>unclosed at 2.5%"
        segs = parse_html_to_segments(html, document_id="doc20")
        paras = [s for s in segs if s.segment_type == "PARAGRAPH"]
        self.assertEqual(len(paras), 1, "Nested unclosed inline tags must not split")
        self.assertIn("2.5%", paras[0].text)


class Test8TableRowSemantics(unittest.TestCase):
    """8. table row semantics — row_label + cell_value preserved."""

    def test_simple_table_row(self):
        html = (b"<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
                b"<tbody><tr><td>GDP</td><td>2.4%</td></tr></tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc21")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].row_label, "GDP")
        self.assertEqual(rows[0].cell_value, "2.4%")
        self.assertEqual(rows[0].column_label, "Value")


class Test9TableColumnSemantics(unittest.TestCase):
    """9. table column semantics — column_label from headers."""

    def test_column_label_from_header(self):
        html = (b"<table><thead><tr><th>Indicator</th><th>Q1</th><th>Q2</th></tr></thead>"
                b"<tbody><tr><td>GDP</td><td>2.4%</td><td>2.6%</td></tr></tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc22")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        self.assertEqual(len(rows), 2)
        # First cell value 2.4% should have column_label="Q1"
        # Second cell value 2.6% should have column_label="Q2"
        by_value = {r.cell_value: r for r in rows}
        self.assertEqual(by_value["2.4%"].column_label, "Q1")
        self.assertEqual(by_value["2.6%"].column_label, "Q2")
        # row_label must be "GDP" for both (since both come from same row)
        self.assertEqual(by_value["2.4%"].row_label, "GDP")
        self.assertEqual(by_value["2.6%"].row_label, "GDP")


class Test10MultiRowHeaders(unittest.TestCase):
    """10. multi-row headers — column_label composed from header rows."""

    def test_multi_row_header(self):
        html = (b"<table><thead>"
                b"<tr><th>Metric</th><th colspan='2'>2026</th></tr>"
                b"<tr><th></th><th>Q1</th><th>Q2</th></tr>"
                b"</thead><tbody>"
                b"<tr><td>GDP</td><td>2.4%</td><td>2.6%</td></tr>"
                b"</tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc23")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        # colspan not yet merged across rows — but Q1/Q2 must still be picked
        # from the second header row.
        by_value = {r.cell_value: r for r in rows}
        self.assertEqual(by_value["2.4%"].column_label, "Q1")
        self.assertEqual(by_value["2.6%"].column_label, "Q2")


class Test11Colspan(unittest.TestCase):
    """11. colspan — existing-test-supported scope (we don't merge colspan
    across multiple header rows, but we preserve column_label from each
    header row independently). This is documented as the V37.2 minimum
    coverage — full colspan merge is V37.3+ scope."""

    def test_colspan_does_not_crash(self):
        html = (b"<table><thead>"
                b"<tr><th>A</th><th colspan='2'>B</th></tr>"
                b"</thead><tbody>"
                b"<tr><td>X</td><td>1</td><td>2</td></tr>"
                b"</tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc24")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        # Must not crash and must produce 2 segments
        self.assertEqual(len(rows), 2)


class Test12TablePeriodUnit(unittest.TestCase):
    """12. table period/unit — detected from cell or header."""

    def test_period_from_cell(self):
        html = (b"<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
                b"<tbody><tr><td>GDP</td><td>2.4% in Q1 2026</td></tr></tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc25")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].unit, "percent")
        # Period should be detected from "Q1 2026" in cell
        self.assertIsNotNone(rows[0].period)
        self.assertIn("2026", rows[0].period)

    def test_period_from_header(self):
        html = (b"<table><thead><tr><th>Metric</th><th>Q1 2026</th></tr></thead>"
                b"<tbody><tr><td>GDP</td><td>2.4%</td></tr></tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc26")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].unit, "percent")
        self.assertIsNotNone(rows[0].period)
        self.assertIn("2026", rows[0].period)

    def test_unit_dollar(self):
        html = (b"<table><thead><tr><th>Item</th><th>Amount</th></tr></thead>"
                b"<tbody><tr><td>Revenue</td><td>$5.2 billion</td></tr></tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc27")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].unit, "usd")


class Test13RepeatedTableValues(unittest.TestCase):
    """13. repeated table values — multiple TABLE_ROW segments with same cell_value."""

    def test_repeated_value_produces_distinct_segments(self):
        html = (b"<table><thead><tr><th>Metric</th><th>Q1</th><th>Q2</th></tr></thead>"
                b"<tbody>"
                b"<tr><td>GDP</td><td>2.4%</td><td>2.4%</td></tr>"
                b"</tbody></table>")
        segs = parse_html_to_segments(html, document_id="doc28")
        rows = [s for s in segs if s.segment_type == "TABLE_ROW"]
        self.assertEqual(len(rows), 2)
        # Both rows have cell_value="2.4%" but different column_label
        self.assertEqual(rows[0].cell_value, "2.4%")
        self.assertEqual(rows[1].cell_value, "2.4%")
        self.assertEqual(rows[0].column_label, "Q1")
        self.assertEqual(rows[1].column_label, "Q2")
        self.assertNotEqual(rows[0].segment_id, rows[1].segment_id,
                            "Distinct segments must have distinct segment_ids")


class Test14OccurrenceAmbiguity(unittest.TestCase):
    """14. occurrence ambiguity — occurrence NOT used as segment index."""

    def test_occurrence_not_used_as_index(self):
        # Two paragraphs both contain "2.4%" — occurrence=1 vs occurrence=2
        # must NOT select a specific one by index. Scoring decides.
        html = (b"<p>GDP grew by 2.4% in the first quarter.</p>"
                b"<p>The inflation rate was 2.4% in June.</p>")
        segs = parse_html_to_segments(html, document_id="doc29")
        # Build two facts with same value, different occurrence
        f1 = _fact("f1", "2.4%", "percentage_statistic", occurrence=1)
        f2 = _fact("f2", "2.4%", "percentage_statistic", occurrence=2)
        r1 = select_evidence_segment(f1, segs)
        r2 = select_evidence_segment(f2, segs)
        # Both facts see both candidates. Selection is by score, not by
        # occurrence index. Both facts may select the same segment (correct
        # conservative behavior — the V37.2 directive says occurrence is a
        # tiebreak only, not an index).
        self.assertIsNotNone(r1.selected_segment)
        self.assertIsNotNone(r2.selected_segment)
        # Both should be either DIRECT or INDIRECT (not INSUFFICIENT)
        self.assertIn(r1.status, (DIRECT, INDIRECT))
        self.assertIn(r2.status, (DIRECT, INDIRECT))


class Test15CrossMetricCollision(unittest.TestCase):
    """15. cross-metric collision — same value, different metrics."""

    def test_percentage_vs_usd_amount(self):
        # "$5" is a dollar amount, "5%" is a percentage
        # Both contain "5" as a substring of "5%" or "$5"
        html = b"<p>The rate was 5% in Q1.</p><p>Revenue: $5 million.</p>"
        segs = parse_html_to_segments(html, document_id="doc30")
        pct_fact = _fact("p1", "5", "percentage_statistic")
        usd_fact = _fact("u1", "5", "usd_amount")
        # Note: "5" is a substring of both "5%" and "$5" — both paragraphs
        # are candidates. The UNIT_CONTEXT scoring dimension distinguishes:
        #   - percentage_statistic prefers the paragraph with "%"
        #   - usd_amount prefers the paragraph with "$"
        r_pct = select_evidence_segment(pct_fact, segs)
        r_usd = select_evidence_segment(usd_fact, segs)
        # Both should select different segments
        self.assertIsNotNone(r_pct.selected_segment)
        self.assertIsNotNone(r_usd.selected_segment)
        # Percentage fact should pick the paragraph with "%"
        self.assertIn("%", r_pct.selected_segment.text)
        # USD fact should pick the paragraph with "$"
        self.assertIn("$", r_usd.selected_segment.text)


class Test16InsufficientEvidence(unittest.TestCase):
    """16. insufficient evidence — value not in any non-excluded segment."""

    def test_value_not_present(self):
        html = b"<p>GDP grew by 2.4% in Q1 2026.</p>"
        segs = parse_html_to_segments(html, document_id="doc31")
        f = _fact("f1", "99.9", "percentage_statistic")
        r = select_evidence_segment(f, segs)
        self.assertEqual(r.status, INSUFFICIENT_EVIDENCE)
        self.assertEqual(r.candidate_count, 0)

    def test_value_only_in_excluded_segment(self):
        html = (b"<nav><p>Menu 5 items</p></nav>"
                b"<p>Real content here.</p>")
        segs = parse_html_to_segments(html, document_id="doc32")
        # The value "5" only appears in the excluded nav segment
        f = _fact("f1", "5", "percentage_statistic")
        r = select_evidence_segment(f, segs)
        self.assertEqual(r.status, INSUFFICIENT_EVIDENCE,
                         "Value only in excluded segment → INSUFFICIENT")


class Test17BackwardCompatibility(unittest.TestCase):
    """17. backward compatibility — old Evidence records still valid."""

    def test_old_evidence_without_segment_id(self):
        # Construct an Evidence without segment_id/segment_type (V37.1 style)
        ev = Evidence(
            evidence_id="evi-test",
            event_or_fact_id="fact-test:v1",
            representation_id="rep-test",
            location="doc-test#p0",
            excerpt="GDP grew by 2.4% in Q1 2026.",
            provenance_ref="representation:rep-test",
        )
        # segment_id and segment_type must default to None
        self.assertIsNone(ev.segment_id)
        self.assertIsNone(ev.segment_type)
        # to_dict must include the new fields
        d = ev.to_dict()
        self.assertIn("segment_id", d)
        self.assertIn("segment_type", d)
        self.assertIsNone(d["segment_id"])
        self.assertIsNone(d["segment_type"])

    def test_new_evidence_with_segment_id(self):
        ev = Evidence(
            evidence_id="evi-test2",
            event_or_fact_id="fact-test:v1",
            representation_id="rep-test",
            location="doc-test#p0",
            excerpt="GDP grew by 2.4% in Q1 2026.",
            provenance_ref="representation:rep-test",
            segment_id="seg-abc123",
            segment_type="PARAGRAPH",
        )
        d = ev.to_dict()
        self.assertEqual(d["segment_id"], "seg-abc123")
        self.assertEqual(d["segment_type"], "PARAGRAPH")


class Test18DeterministicSegmentIDs(unittest.TestCase):
    """18. deterministic segment IDs — same HTML produces same segment_ids."""

    def test_same_html_same_ids(self):
        html = b"<h2>Report</h2><p>GDP grew 2.4%.</p>"
        segs1 = parse_html_to_segments(html, document_id="docA")
        segs2 = parse_html_to_segments(html, document_id="docA")
        # Same document_id + same HTML → same segment_ids
        self.assertEqual(
            [s.segment_id for s in segs1],
            [s.segment_id for s in segs2],
        )

    def test_different_doc_id_different_ids(self):
        html = b"<h2>Report</h2><p>GDP grew 2.4%.</p>"
        segs1 = parse_html_to_segments(html, document_id="docA")
        segs2 = parse_html_to_segments(html, document_id="docB")
        # Different document_id → different segment_ids
        self.assertNotEqual(
            [s.segment_id for s in segs1],
            [s.segment_id for s in segs2],
        )

    def test_segment_id_format(self):
        html = b"<p>Test paragraph.</p>"
        segs = parse_html_to_segments(html, document_id="docX")
        self.assertEqual(len(segs), 1)
        # segment_id must start with "seg-" prefix and be 20 chars
        self.assertTrue(segs[0].segment_id.startswith("seg-"))
        self.assertEqual(len(segs[0].segment_id), 20)  # "seg-" (4) + 16 hex chars


# ═══════════════════════════════════════════════════════════════════════
# Test runner — prints exact counts per V37.2 PHASE 7
# ═══════════════════════════════════════════════════════════════════════

def run_all_v37_2_tests():
    """Run all V37.2 tests with verbose output. Returns True if all pass."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_classes = [
        Test1ParentHierarchy, Test2NavigationExclusion, Test3RoleExclusion,
        Test4HeadingContext, Test5ParagraphIntegrity, Test6InlineTags,
        Test7MalformedInlineHTML, Test8TableRowSemantics, Test9TableColumnSemantics,
        Test10MultiRowHeaders, Test11Colspan, Test12TablePeriodUnit,
        Test13RepeatedTableValues, Test14OccurrenceAmbiguity,
        Test15CrossMetricCollision, Test16InsufficientEvidence,
        Test17BackwardCompatibility, Test18DeterministicSegmentIDs,
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_all_v37_2_tests()
    sys.exit(0 if success else 1)
