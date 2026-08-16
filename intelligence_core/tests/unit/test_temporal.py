"""§11 Temporal — D4 rules (explicit/unknown tz, conflicts, ordering guard)."""
import unittest
from intelligence_core.temporal import (parse_rfc822_pubdate, parse_iso_or_date,
                                        apply_jurisdiction_rule, JurisdictionRule,
                                        ordering_filter)
from intelligence_core.contracts import TZStatus, NormBasis, Semantics, ProvenanceSource


class TestTemporal(unittest.TestCase):
    def test_explicit_offset(self):  # FDIC evidence
        t = parse_rfc822_pubdate("Mon, 10 Aug 2026 13:10:04 -0500")
        self.assertEqual(t.timezone_status, TZStatus.EXPLICIT_OFFSET)
        self.assertEqual(t.normalized_utc, "2026-08-10T18:10:04Z")
        self.assertTrue(t.ordering_participating())

    def test_explicit_utc(self):  # ISTAT/DFSA evidence
        t = parse_rfc822_pubdate("Wed, 12 Aug 2026 08:00:58 +0000")
        self.assertEqual(t.timezone_status, TZStatus.EXPLICIT_ZONE)
        self.assertEqual(t.normalized_utc, "2026-08-12T08:00:58Z")

    def test_naive_iso_null_utc(self):  # DG Tresor evidence
        t = parse_iso_or_date("2026-07-29T00:00:00.0000000")
        self.assertEqual(t.timezone_status, TZStatus.NAIVE_LOCAL)
        self.assertIsNone(t.normalized_utc)
        self.assertEqual(t.normalization_basis, NormBasis.NONE)
        self.assertFalse(t.ordering_participating())

    def test_date_only(self):
        t = parse_iso_or_date("2026-06-05", provenance=ProvenanceSource.HTML_TIME_ATTR)
        self.assertEqual(t.timezone_status, TZStatus.DATE_ONLY)
        self.assertIsNone(t.normalized_utc)

    def test_conflicting_dates_coexist(self):  # DGT A1: URL vs <time>
        url_t = parse_iso_or_date("2026-06-25", semantics=Semantics.DOCUMENT_DATE,
                                  provenance=ProvenanceSource.URL_DATE)
        time_t = parse_iso_or_date("2026-07-17", semantics=Semantics.PUBLICATION,
                                   provenance=ProvenanceSource.HTML_TIME_ATTR)
        both = [url_t, time_t]
        self.assertEqual(len(both), 2)  # neither destroyed
        self.assertNotEqual(both[0].original_value, both[1].original_value)
        self.assertNotEqual(both[0].timestamp_semantics, both[1].timestamp_semantics)

    def test_update_vs_publication_distinct(self):
        pub = parse_rfc822_pubdate("Mon, 10 Aug 2026 13:10:04 -0500", Semantics.PUBLICATION)
        upd = parse_rfc822_pubdate("Tue, 11 Aug 2026 09:00:00 -0500", Semantics.UPDATE)
        self.assertNotEqual(pub.timestamp_semantics, upd.timestamp_semantics)

    def test_unapproved_jurisdiction_rule_not_inferred(self):
        naive = parse_iso_or_date("2026-08-14T07:00:02")  # LSE evidence
        unapproved = JurisdictionRule("UK", 1.0, approved=False, evidence="none")
        t = apply_jurisdiction_rule(naive, unapproved)
        self.assertEqual(t.normalization_basis, NormBasis.INFERRED)
        self.assertIsNone(t.normalized_utc)      # no silent inference
        self.assertFalse(t.ordering_participating())

    def test_approved_rule_participates(self):
        naive = parse_iso_or_date("2026-08-14T07:00:02")
        approved = JurisdictionRule("UK-BST", 1.0, approved=True,
                                    evidence="gov-uk BST 2026-03-29..2026-10-25; review-board#7")
        t = apply_jurisdiction_rule(naive, approved)
        self.assertEqual(t.normalization_basis, NormBasis.JURISDICTION_RULE)
        self.assertEqual(t.normalized_utc, "2026-08-14T06:00:02Z")
        self.assertTrue(t.ordering_participating())

    def test_ordering_guard_filters_naive(self):
        fdic = parse_rfc822_pubdate("Mon, 10 Aug 2026 13:10:04 -0500")
        lse = parse_iso_or_date("2026-08-14T07:00:02")
        participating = ordering_filter([fdic, lse])
        self.assertEqual(participating, [fdic])   # cross-J ordering only on safe tuples


if __name__ == "__main__":
    unittest.main()
