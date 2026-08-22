"""
Tests for ROUAA Entity Role Contract.

Tests the canonical semantic roles defined in
intelligence_core/entity_role_contract.py.

Covers:
    - source_authority != event_subject (no conflation)
    - event_subject = UNRESOLVED (honest representation)
    - measured_entity distinct from source_authority
    - BEA GDP/PCE representation
    - SEC penalty representation (UNRESOLVED event_subject)
    - ECB equivalent surface-form identity (word-order invariance)
"""
import unittest
import sys
from pathlib import Path

# Add intelligence_core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from intelligence_core.entity_role_contract import (
    EntityRoleContract,
    UNRESOLVED,
    SEC_PENALTY_CONTRACT,
    SEC_DISGORGEMENT_CONTRACT,
    BEA_GDP_CONTRACT,
    BEA_PCE_CONTRACT,
    FED_POLICY_RATE_CONTRACT,
    ECB_POLICY_RATE_CONTRACT,
    ECB_SURFACE_FORM_EQUIVALENCE_PAIRS,
)


class TestRoleContractIndependence(unittest.TestCase):
    """Tests for the semantic rule: source_authority != event_subject != measured_entity."""

    def test_sec_contract_event_subject_is_unresolved(self):
        """SEC IOs: event_subject MUST be UNRESOLVED (firm not named in evidence)."""
        self.assertEqual(SEC_PENALTY_CONTRACT.event_subject, UNRESOLVED)
        self.assertEqual(SEC_DISGORGEMENT_CONTRACT.event_subject, UNRESOLVED)

    def test_sec_contract_source_authority_is_sec(self):
        """SEC IOs: source_authority is SEC (from URL/document identity)."""
        self.assertIn("SEC", SEC_PENALTY_CONTRACT.source_authority)
        self.assertIn("SEC", SEC_DISGORGEMENT_CONTRACT.source_authority)

    def test_sec_contract_measured_entity_is_penalty(self):
        """SEC IOs: measured_entity is the penalty amount, not SEC."""
        self.assertIn("penalty", SEC_PENALTY_CONTRACT.measured_entity.lower())
        self.assertIn("disgorgement", SEC_DISGORGEMENT_CONTRACT.measured_entity.lower())

    def test_sec_contract_source_not_event_subject(self):
        """CRITICAL: source_authority != event_subject (no conflation)."""
        self.assertNotEqual(
            SEC_PENALTY_CONTRACT.source_authority,
            SEC_PENALTY_CONTRACT.event_subject,
            "source_authority (SEC) must not equal event_subject (UNRESOLVED)"
        )

    def test_sec_contract_source_not_measured_entity(self):
        """CRITICAL: source_authority != measured_entity."""
        self.assertNotEqual(
            SEC_PENALTY_CONTRACT.source_authority,
            SEC_PENALTY_CONTRACT.measured_entity
        )

    def test_bea_gdp_contract_measured_entity_is_gdp(self):
        """BEA GDP IOs: measured_entity is GDP growth, NOT BEA."""
        self.assertIn("GDP", BEA_GDP_CONTRACT.measured_entity)
        self.assertNotIn("BEA", BEA_GDP_CONTRACT.measured_entity)

    def test_bea_gdp_contract_source_authority_is_bea(self):
        """BEA IOs: source_authority is BEA (from URL)."""
        self.assertIn("BEA", BEA_GDP_CONTRACT.source_authority)

    def test_bea_gdp_contract_event_subject_is_gdp(self):
        """BEA GDP IOs: event_subject is the economic indicator (GDP), not BEA."""
        self.assertIn("GDP", BEA_GDP_CONTRACT.event_subject)

    def test_bea_contract_source_not_measured(self):
        """CRITICAL: source_authority != measured_entity (no conflation)."""
        self.assertNotEqual(
            BEA_GDP_CONTRACT.source_authority,
            BEA_GDP_CONTRACT.measured_entity
        )

    def test_bea_contract_source_not_event_subject(self):
        """CRITICAL: source_authority != event_subject."""
        self.assertNotEqual(
            BEA_GDP_CONTRACT.source_authority,
            BEA_GDP_CONTRACT.event_subject
        )

    def test_bea_pce_contract_measured_entity_is_pce(self):
        """BEA PCE IOs: measured_entity is PCE price index, not BEA."""
        self.assertIn("PCE", BEA_PCE_CONTRACT.measured_entity)
        self.assertNotIn("BEA", BEA_PCE_CONTRACT.measured_entity)

    def test_fed_contract_committee_as_event_subject(self):
        """Fed IOs: FOMC is event_subject (committee = authority for monetary)."""
        self.assertIn("FOMC", FED_POLICY_RATE_CONTRACT.event_subject)

    def test_fed_contract_measured_entity_is_policy_rate(self):
        """Fed IOs: measured_entity is federal funds rate."""
        self.assertIn("federal funds rate", FED_POLICY_RATE_CONTRACT.measured_entity.lower())

    def test_ecb_contract_governing_council_as_event_subject(self):
        """ECB IOs: Governing Council is event_subject."""
        self.assertIn("Governing Council", ECB_POLICY_RATE_CONTRACT.event_subject)


class TestECBSurfaceFormEquivalence(unittest.TestCase):
    """Tests for ECB IO3 surface form equivalence (literal matcher false negative fix)."""

    def test_ecb_governing_council_equivalence(self):
        """ECB IO3: "ECB Governing Council" == "The Governing Council of the ECB"."""
        form_a = "ECB Governing Council"
        form_b = "The Governing Council of the ECB"
        self.assertTrue(
            EntityRoleContract.surface_forms_equivalent(form_a, form_b),
            f"Surface forms should be semantically equivalent: '{form_a}' vs '{form_b}'"
        )

    def test_ecb_equivalence_is_not_substring_match(self):
        """Equivalence is token-set based, NOT substring match."""
        # "ECB" is a substring of "The Governing Council of the ECB"
        # but they are NOT equivalent
        self.assertFalse(
            EntityRoleContract.surface_forms_equivalent("ECB", "The Governing Council of the ECB"),
            "'ECB' alone must not be equivalent to the full phrase"
        )

    def test_ecb_equivalence_pairs_from_adjudication(self):
        """All adjudicated ECB equivalence pairs must pass."""
        for form_a, form_b in ECB_SURFACE_FORM_EQUIVALENCE_PAIRS:
            self.assertTrue(
                EntityRoleContract.surface_forms_equivalent(form_a, form_b),
                f"Adjudicated pair must be equivalent: '{form_a}' == '{form_b}'"
            )

    def test_ecb_governing_council_not_equivalent_to_separate_concept(self):
        """ECB Governing Council is NOT equivalent to unrelated entities."""
        self.assertFalse(
            EntityRoleContract.surface_forms_equivalent(
                "ECB Governing Council",
                "Securities and Exchange Commission"
            )
        )


    def test_bare_governing_council_not_equivalent_to_ecb_qualified(self):
        """Bare "Governing Council" is NOT equivalent to "ECB Governing Council" — bare phrase is ambiguous."""
        self.assertFalse(
            EntityRoleContract.surface_forms_equivalent("Governing Council", "ECB Governing Council"),
            "Bare 'Governing Council' is ambiguous — must not be equivalent to ECB-qualified form"
        )

    def test_empty_strings_not_equivalent(self):
        """Empty strings are not equivalent to non-empty strings."""
        self.assertFalse(EntityRoleContract.surface_forms_equivalent("", "ECB"))
        self.assertFalse(EntityRoleContract.surface_forms_equivalent("ECB", ""))


class TestContractValidation(unittest.TestCase):
    """Tests for contract-level validation methods."""

    def test_unresolved_event_subject_is_valid(self):
        """UNRESOLVED event_subject is a valid honest state."""
        contract = EntityRoleContract(
            source_authority="SEC",
            event_subject=UNRESOLVED,
            measured_entity="penalty",
        )
        self.assertTrue(contract.validate_independence())

    def test_explicit_event_subject_is_valid(self):
        """Explicit event_subject (when named in evidence) is valid."""
        contract = EntityRoleContract(
            source_authority="Federal Reserve",
            event_subject="Federal Open Market Committee",
            measured_entity="policy rate",
        )
        self.assertTrue(contract.validate_independence())

    def test_contract_is_immutable(self):
        """Contract is frozen (dataclass(frozen=True)) — cannot be modified after creation."""
        contract = EntityRoleContract(
            source_authority="A",
            event_subject="B",
            measured_entity="C",
        )
        with self.assertRaises((AttributeError, Exception)):
            contract.source_authority = "X"

    def test_mentioned_entities_default_empty(self):
        """mentioned_entities defaults to empty list."""
        contract = EntityRoleContract(
            source_authority="A",
            event_subject="B",
            measured_entity="C",
        )
        self.assertEqual(contract.mentioned_entities, [])


class TestForbiddenConflation(unittest.TestCase):
    """Tests that the contract does NOT perform forbidden conflation."""

    def test_sec_source_authority_not_promoted_to_event_subject(self):
        """SEC source_authority MUST NOT be auto-promoted to event_subject."""
        # The contract explicitly sets event_subject=UNRESOLVED for SEC
        # This is the opposite of conflation
        self.assertEqual(SEC_PENALTY_CONTRACT.event_subject, UNRESOLVED)
        self.assertNotEqual(
            SEC_PENALTY_CONTRACT.event_subject,
            SEC_PENALTY_CONTRACT.source_authority
        )

    def test_bea_source_authority_not_promoted_to_measured_entity(self):
        """BEA source_authority MUST NOT be auto-promoted to measured_entity."""
        self.assertNotEqual(
            BEA_GDP_CONTRACT.source_authority,
            BEA_GDP_CONTRACT.measured_entity
        )


if __name__ == '__main__':
    unittest.main()
