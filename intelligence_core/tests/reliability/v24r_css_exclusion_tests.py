"""V24R — CSS/UI/Boilerplate exclusion regression tests.

Tests that CSS, JavaScript, style blocks, script blocks, and template UI
content CANNOT participate in semantic extraction.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.tests.reliability.v15_recall_recovery import extract_html_structure
from intelligence_core.normalize import strip_html


class TestCSSJSExclusion(unittest.TestCase):
    """V24R — CSS/JS content must not participate in extraction."""

    def test_style_block_skipped(self):
        html = b"""<html><body>
        <style>
        .banner { background-color: #0379ca; opacity: 100%; }
        .scrollButton:hover { background-color: #0379ca; opacity: 100% !important; }
        </style>
        <p>The inflation rate was 3.4% in April 2026.</p>
        </body></html>"""
        segments = extract_html_structure(html)
        all_text = " ".join(s[0] for s in segments)
        self.assertNotIn("scrollButton", all_text)
        self.assertNotIn("opacity", all_text)
        self.assertNotIn("background-color", all_text)
        self.assertIn("inflation", all_text)

    def test_script_block_skipped(self):
        html = b"""<html><body>
        <script>
        var rate = 5.25;
        function updateRate() { document.getElementById('rate').innerText = rate + '%'; }
        </script>
        <p>The policy rate is 5.25%.</p>
        </body></html>"""
        segments = extract_html_structure(html)
        all_text = " ".join(s[0] for s in segments)
        self.assertNotIn("updateRate", all_text)
        self.assertNotIn("getElementById", all_text)
        self.assertIn("policy rate", all_text)

    def test_template_block_skipped(self):
        html = b"""<html><body>
        <template>
        <div>{{ rate }}%</div>
        <span>100%</span>
        </template>
        <p>GDP growth was 2.1%.</p>
        </body></html>"""
        segments = extract_html_structure(html)
        all_text = " ".join(s[0] for s in segments)
        self.assertIn("GDP growth", all_text)

    def test_noscript_block_skipped(self):
        html = b"""<html><body>
        <noscript>Please enable JavaScript to view 100% of content.</noscript>
        <p>Unemployment fell to 4.2%.</p>
        </body></html>"""
        segments = extract_html_structure(html)
        all_text = " ".join(s[0] for s in segments)
        self.assertNotIn("enable JavaScript", all_text)
        self.assertIn("Unemployment", all_text)

    def test_scrollButton_regression(self):
        """V23 negative regression: scrollButton:hover CSS must NOT appear."""
        html = b"""<html><head>
        <style>
        .scrollButton:hover{
            background-color: #0379ca;
            opacity: 100% !important;
        }
        </style>
        </head><body>
        <h1>TreasuryDirect STRIPS Program for May 2026</h1>
        <p>Total securities held: $1.2 billion.</p>
        </body></html>"""
        segments = extract_html_structure(html)
        all_text = " ".join(s[0] for s in segments)
        self.assertNotIn("scrollButton", all_text)
        self.assertNotIn("opacity", all_text)
        self.assertIn("TreasuryDirect", all_text)

    def test_ecl_banner_regression(self):
        html = b"""<html><head>
        <style>
        .ecl-banner:not(.ecl-banner--plain-background) {
            container-type: inline-size;
            background: #fff;
        }
        </style>
        </head><body>
        <p>GDP increased by 2.8% in Q3 2026.</p>
        </body></html>"""
        segments = extract_html_structure(html)
        all_text = " ".join(s[0] for s in segments)
        self.assertNotIn("ecl-banner", all_text)
        self.assertNotIn("container-type", all_text)
        self.assertIn("GDP", all_text)

    def test_strip_html_still_works(self):
        html = """<html><body>
        <style>.foo { opacity: 100%; }</style>
        <script>var x = 5.25;</script>
        <p>Rate: 5.25%.</p>
        </body></html>"""
        flat = strip_html(html)
        self.assertNotIn("opacity", flat)
        self.assertNotIn("var x", flat)
        self.assertIn("Rate", flat)

    def test_real_table_still_extracted(self):
        html = b"""<html><body>
        <style>.table { color: red; }</style>
        <table>
        <tr><th>Indicator</th><th>Value</th></tr>
        <tr><td>Inflation</td><td>3.4%</td></tr>
        <tr><td>GDP Growth</td><td>2.1%</td></tr>
        </table>
        </body></html>"""
        segments = extract_html_structure(html)
        table_rows = [s for s in segments if s[1] == "TABLE_ROW"]
        self.assertGreaterEqual(len(table_rows), 2)
        all_text = " ".join(s[0] for s in segments)
        self.assertNotIn("color: red", all_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
