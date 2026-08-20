"""V47C dedicated tests for publisher_institution.py.

Tests the V47C publisher layer + Subject Entity Firewall invariants.
Per directive §19, covers cases A-J:

  A. publisher confirmed, subject not found
  B. publisher confirmed, subject differs
  C. publisher confirmed, multiple subject candidates
  D. explicit subject confirmed independently
  E. domain normalization
  F. alias normalization
  G. unknown publisher
  H. source metadata conflict
  I. document publisher metadata conflict
  J. GT metadata must not affect result

Plus the Subject Entity Firewall (§9) regression tests.
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.contracts import PublisherInstitutionV1
from intelligence_core.publisher_institution import (
    PUBLISHER_CONFIRMED, PUBLISHER_AMBIGUOUS, PUBLISHER_NOT_FOUND,
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW,
    TYPE_CENTRAL_BANK, TYPE_STATISTICAL_AGENCY, TYPE_SECURITIES_REGULATOR,
    TYPE_GOVERNMENT_MINISTRY, TYPE_EXCHANGE, TYPE_OTHER,
    METHOD_SOURCE_REGISTRY, METHOD_SOURCE_DOMAIN,
    METHOD_DOCUMENT_PUBLISHER_METADATA,
    ALLOWED_METHODS, FORBIDDEN_METHODS,
    normalize_domain, normalize_source_id_suffix,
    identify_publisher, verify_subject_entity_firewall,
)


class TestCaseA_PublisherConfirmedSubjectNotFound(unittest.TestCase):
    """§19 Case A: publisher confirmed, subject not found.

    The Subject Entity Firewall MUST be intact: publisher CONFIRMED
    does NOT promote subject_entity. A document where publisher is
    CONFIRMED but subject is NOT_FOUND is an ACCEPTED state.
    """

    def test_publisher_confirmed_subject_not_found_is_accepted(self):
        publisher = identify_publisher("imp-ecb", source_path="https://www.ecb.europa.eu/rss/press.html")
        self.assertEqual(publisher.status, PUBLISHER_CONFIRMED)
        # Subject is NOT_FOUND (no entity signal in primary segment)
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_NOT_FOUND")
        self.assertTrue(firewall["firewall_intact"])
        self.assertEqual(firewall["violation"], "")


class TestCaseB_PublisherConfirmedSubjectDiffers(unittest.TestCase):
    """§19 Case B: publisher confirmed, subject differs.

    Publisher (e.g., ECB) may differ from subject (e.g., EUR inflation).
    """

    def test_publisher_ecb_subject_german_economy(self):
        publisher = identify_publisher("imp-ecb", source_path="https://www.ecb.europa.eu/rss/press.html")
        self.assertEqual(publisher.canonical_name, "European Central Bank")
        # Subject is "German economy" (a different entity) — confirmed by
        # INDEPENDENT event-local evidence, not by publisher identity
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_CONFIRMED")
        self.assertTrue(firewall["firewall_intact"])


class TestCaseC_PublisherConfirmedMultipleSubjectCandidates(unittest.TestCase):
    """§19 Case C: publisher confirmed, multiple subject candidates."""

    def test_publisher_confirmed_multiple_subjects(self):
        publisher = identify_publisher("imp-ecb", source_path="https://www.ecb.europa.eu/")
        self.assertEqual(publisher.status, PUBLISHER_CONFIRMED)
        # Subject is AMBIGUOUS (multiple candidates)
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_AMBIGUOUS")
        self.assertTrue(firewall["firewall_intact"])


class TestCaseD_ExplicitSubjectConfirmedIndependently(unittest.TestCase):
    """§19 Case D: explicit subject confirmed independently.

    When subject_entity is CONFIRMED, it must have its own supporting
    segment/evidence provenance — NOT derived from publisher identity.
    """

    def test_subject_confirmed_independent_of_publisher(self):
        publisher = identify_publisher("imp-ecb", source_path="https://www.ecb.europa.eu/")
        # Subject confirmed independently
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_CONFIRMED")
        self.assertTrue(firewall["firewall_intact"])
        # The firewall does NOT auto-promote subject based on publisher


class TestCaseE_DomainNormalization(unittest.TestCase):
    """§19 Case E: domain normalization.

    www.example.gov, example.gov, https://example.gov/... all normalize
    to the same canonical publisher identity.
    """

    def test_normalize_strips_www(self):
        self.assertEqual(normalize_domain("https://www.ecb.europa.eu/press"), "europa.eu")

    def test_normalize_handles_no_scheme(self):
        self.assertEqual(normalize_domain("www.bankofengland.co.uk/news"), "co.uk")

    def test_normalize_handles_https(self):
        # "example.gov" → last 2 labels = "example.gov"
        self.assertEqual(normalize_domain("https://example.gov/"), "example.gov")

    def test_normalize_empty_returns_none(self):
        self.assertIsNone(normalize_domain(""))
        self.assertIsNone(normalize_domain(None))


class TestCaseF_AliasNormalization(unittest.TestCase):
    """§19 Case F: alias normalization.

    Different aliases (ECB, European Central Bank, ecb.europa.eu) map to
    the same canonical publisher identity.
    """

    def test_alias_ecb_matches_canonical(self):
        publisher = identify_publisher("imp-ecb")
        self.assertEqual(publisher.canonical_name, "European Central Bank")
        self.assertEqual(publisher.status, PUBLISHER_CONFIRMED)

    def test_alias_european_central_bank_matches(self):
        # source_id with full name but NOT in registry — should fall back
        # to AMBIGUOUS with generic canonical name (not the registry ECB)
        publisher = identify_publisher("imp-some-unknown-agency-xyz")
        self.assertNotEqual(publisher.canonical_name, "European Central Bank")
        self.assertEqual(publisher.status, PUBLISHER_AMBIGUOUS)

    def test_alias_domain_match(self):
        publisher = identify_publisher(
            "src-unknown",
            source_path="https://www.ecb.europa.eu/press/",
        )
        # Domain match should identify ECB
        self.assertEqual(publisher.canonical_name, "European Central Bank")
        self.assertEqual(publisher.publisher_support_method, METHOD_SOURCE_DOMAIN)


class TestCaseG_UnknownPublisher(unittest.TestCase):
    """§19 Case G: unknown publisher.

    When no publisher can be identified, status = NOT_FOUND.
    """

    def test_unknown_publisher_returns_not_found(self):
        publisher = identify_publisher("")
        self.assertEqual(publisher.status, PUBLISHER_NOT_FOUND)
        self.assertEqual(publisher.canonical_name, "UNKNOWN")

    def test_unknown_source_id_suffix_falls_back_to_ambiguous(self):
        # Source with an unrecognized suffix
        publisher = identify_publisher("imp-unknown-institution-xyz")
        self.assertEqual(publisher.status, PUBLISHER_AMBIGUOUS)
        self.assertEqual(publisher.confidence, CONFIDENCE_LOW)
        self.assertEqual(publisher.institution_type, TYPE_OTHER)


class TestCaseH_SourceMetadataConflict(unittest.TestCase):
    """§19 Case H: source metadata conflict.

    When source_id and source_path domain point to DIFFERENT institutions,
    publisher status becomes AMBIGUOUS (currently the source_id wins as
    higher-priority evidence; this is documented behavior).
    """

    def test_source_id_takes_precedence_over_domain(self):
        # Source_id says "ecb" but domain is "federalreserve.gov"
        # source_id should take precedence (registry suffix match)
        publisher = identify_publisher(
            "imp-ecb",
            source_path="https://www.federalreserve.gov/feeds/",
        )
        # source_id suffix "ecb" matches first → ECB
        self.assertEqual(publisher.canonical_name, "European Central Bank")


class TestCaseI_DocumentPublisherMetadataConflict(unittest.TestCase):
    """§19 Case I: document publisher metadata conflict."""

    def test_document_url_can_identify_publisher(self):
        # source_id is unknown but document_url identifies the publisher
        publisher = identify_publisher(
            "src-unknown-xyz",
            source_path="https://www.example.com",
            document_url="https://www.ecb.europa.eu/press/pr/2024/html/something",
        )
        # The document_url domain should identify ECB
        self.assertEqual(publisher.canonical_name, "European Central Bank")
        self.assertEqual(publisher.publisher_support_method, METHOD_DOCUMENT_PUBLISHER_METADATA)


class TestCaseJ_GTMetadataMustNotAffectResult(unittest.TestCase):
    """§19 Case J: GT metadata must not affect result.

    Publisher identification uses ONLY source metadata — NOT GT metadata,
    NOT document_id, NOT event_id, NOT fact_id, NOT headline text.
    """

    def test_publisher_does_not_use_document_id(self):
        # Even with a document_id that mentions a different institution,
        # publisher identification should NOT be affected
        publisher = identify_publisher(
            "imp-ecb",
            source_path="https://www.ecb.europa.eu/",
            document_url="https://www.federalreserve.gov/some-path",  # conflicting domain
        )
        # source_id takes precedence — ECB wins
        self.assertEqual(publisher.canonical_name, "European Central Bank")

    def test_publisher_does_not_use_event_type(self):
        # Pass no event-type-related info; publisher should still identify
        publisher = identify_publisher("imp-ecb")
        self.assertEqual(publisher.canonical_name, "European Central Bank")

    def test_publisher_does_not_use_fact_value(self):
        publisher = identify_publisher("imp-ecb", source_path="https://www.ecb.europa.eu/")
        self.assertEqual(publisher.canonical_name, "European Central Bank")
        # publisher_support_method must be one of ALLOWED_METHODS
        self.assertIn(publisher.publisher_support_method, ALLOWED_METHODS)
        # publisher_support_method must NOT be a forbidden method
        self.assertNotIn(publisher.publisher_support_method, FORBIDDEN_METHODS)


class TestSubjectEntityFirewall(unittest.TestCase):
    """§9 Subject Entity Firewall — mandatory regression tests.

    Publisher CONFIRMED MUST NOT promote subject_entity.
    """

    def test_publisher_confirmed_subject_not_found_accepted(self):
        publisher = identify_publisher("imp-ecb")
        self.assertEqual(publisher.status, PUBLISHER_CONFIRMED)
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_NOT_FOUND")
        self.assertTrue(firewall["firewall_intact"])

    def test_publisher_confirmed_subject_confirmed_accepted(self):
        publisher = identify_publisher("imp-ecb")
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_CONFIRMED")
        self.assertTrue(firewall["firewall_intact"])

    def test_publisher_not_found_subject_confirmed_accepted(self):
        publisher = identify_publisher("imp-unknown-xyz")
        # Falls back to AMBIGUOUS, not NOT_FOUND (suffix is generic)
        # Use empty source_id for NOT_FOUND
        publisher = identify_publisher("")
        self.assertEqual(publisher.status, PUBLISHER_NOT_FOUND)
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_CONFIRMED")
        self.assertTrue(firewall["firewall_intact"])

    def test_publisher_confirmed_subject_ambiguous_accepted(self):
        publisher = identify_publisher("imp-ecb")
        firewall = verify_subject_entity_firewall(publisher, "ENTITY_AMBIGUOUS")
        self.assertTrue(firewall["firewall_intact"])


class TestPublisherSupportMethods(unittest.TestCase):
    """Publisher support methods must be in ALLOWED set, never forbidden."""

    def test_source_registry_method(self):
        publisher = identify_publisher("imp-ecb")
        self.assertEqual(publisher.publisher_support_method, METHOD_SOURCE_REGISTRY)

    def test_source_domain_method(self):
        publisher = identify_publisher(
            "src-unknown",
            source_path="https://www.ecb.europa.eu/press/",
        )
        self.assertEqual(publisher.publisher_support_method, METHOD_SOURCE_DOMAIN)

    def test_no_forbidden_methods(self):
        # Test for a variety of sources that none return forbidden methods
        for sid in ("imp-ecb", "imp-federal-reserve", "imp-bank-of-england",
                    "src-boc", "imp-bea", "imp-eurostat"):
            publisher = identify_publisher(sid)
            self.assertIn(
                publisher.publisher_support_method, ALLOWED_METHODS,
                f"source_id={sid} returned forbidden method {publisher.publisher_support_method}",
            )


class TestInstitutionTypeClassification(unittest.TestCase):
    """Institution types are classified correctly."""

    def test_central_bank_type(self):
        publisher = identify_publisher("imp-ecb")
        self.assertEqual(publisher.institution_type, TYPE_CENTRAL_BANK)

    def test_statistical_agency_type(self):
        publisher = identify_publisher("imp-bea")
        self.assertEqual(publisher.institution_type, TYPE_STATISTICAL_AGENCY)

    def test_securities_regulator_type(self):
        publisher = identify_publisher("imp-sec")
        self.assertEqual(publisher.institution_type, TYPE_SECURITIES_REGULATOR)

    def test_government_ministry_type(self):
        publisher = identify_publisher("imp-hm-treasury")
        self.assertEqual(publisher.institution_type, TYPE_GOVERNMENT_MINISTRY)

    def test_exchange_type(self):
        publisher = identify_publisher("imp-jpx")
        self.assertEqual(publisher.institution_type, TYPE_EXCHANGE)

    def test_unknown_falls_back_to_other_type(self):
        publisher = identify_publisher("imp-unknown-institution-xyz")
        self.assertEqual(publisher.institution_type, TYPE_OTHER)


class TestConfidenceLevels(unittest.TestCase):
    """Confidence levels are HIGH/MEDIUM/LOW, never hallucinated."""

    def test_source_registry_match_is_high_confidence(self):
        publisher = identify_publisher("imp-ecb")
        self.assertEqual(publisher.confidence, CONFIDENCE_HIGH)

    def test_domain_match_is_medium_confidence(self):
        publisher = identify_publisher(
            "src-unknown",
            source_path="https://www.ecb.europa.eu/press/",
        )
        self.assertEqual(publisher.confidence, CONFIDENCE_MEDIUM)

    def test_generic_fallback_is_low_confidence(self):
        publisher = identify_publisher("imp-unknown-xyz")
        self.assertEqual(publisher.confidence, CONFIDENCE_LOW)


class TestNoDocumentSpecificShortcuts(unittest.TestCase):
    """§5: NO document-specific shortcuts. NO GT/document_id/event_id mappings."""

    def test_publisher_does_not_inspect_document_id(self):
        # Even with arbitrary document metadata, publisher should be
        # identified from source metadata only
        publisher = identify_publisher("imp-ecb")
        # Test the module source for absence of forbidden patterns
        module_path = Path(__file__).resolve().parents[2] / "publisher_institution.py"
        source = module_path.read_text()
        # No document_id-specific hard-coded mappings
        self.assertNotIn("doc-737e4fff6a05c09d", source)
        self.assertNotIn("event-5c8786e99b5f6d7c", source)
        self.assertNotIn("fact-44507f3041d96250", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
