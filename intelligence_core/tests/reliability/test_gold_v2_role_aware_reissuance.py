"""
Tests for Gold-V2 Role-Aware Re-Issuance.

Verifies:
1. Original Gold IO immutability (fact/evidence/source unchanged)
2. Role decomposition correctness for all 10 IOs
3. UNRESOLVED handling for SEC IOs (firm not named)
4. BEA role separation (source_authority=BEA, measured_entity=GDP/PCE)
5. ECB surface form equivalence
6. Authority ≠ Subject ≠ Measured Entity
"""
import unittest
import sys
import json
import hashlib
import yaml
from pathlib import Path

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
)

REISSUANCE_PATH = Path(__file__).parent.parent.parent.parent / "docs" / "evidence" / "gold_v2_role_aware_reissuance.yaml"


class TestReissuanceFile(unittest.TestCase):
    """Tests that the re-issuance file exists and is well-formed."""
    
    def setUp(self):
        with open(REISSUANCE_PATH) as f:
            self.data = yaml.safe_load(f)
    
    def test_file_exists(self):
        self.assertTrue(REISSUANCE_PATH.exists())
    
    def test_metadata_present(self):
        self.assertIn('metadata', self.data)
        self.assertEqual(self.data['metadata']['purpose'], 'Gold-V2 Role-Aware Re-Issuance')
    
    def test_gold_ios_count(self):
        self.assertEqual(len(self.data['gold_ios']), 10)
    
    def test_immutability_anchor_present(self):
        self.assertIn('immutability_anchor_sha256', self.data['metadata'])


class TestGoldIOImmutability(unittest.TestCase):
    """Tests that original Gold IO fields are preserved (immutability)."""
    
    def setUp(self):
        with open(REISSUANCE_PATH) as f:
            self.data = yaml.safe_load(f)
        self.ios = {io['io_id']: io for io in self.data['gold_ios']}
    
    def test_all_10_io_ids_present(self):
        expected = [
            'gold-fed-2024-09-50bp',
            'gold-fed-2024-07-25bp',
            'gold-ecb-2024-09-25bp',
            'gold-ecb-2024-06-25bp',
            'gold-bea-2024-q3-gdp',
            'gold-bea-2024-q2-gdp',
            'gold-bea-2024-09-pce',
            'gold-sec-2024-firm-a',
            'gold-sec-2024-firm-b',
            'gold-sec-2024-firm-c',
        ]
        for io_id in expected:
            self.assertIn(io_id, self.ios, f"Missing IO: {io_id}")
    
    def test_fed_io1_fact_value_unchanged(self):
        self.assertEqual(self.ios['gold-fed-2024-09-50bp']['fact_value'], '-50')
    
    def test_fed_io2_fact_value_unchanged(self):
        self.assertEqual(self.ios['gold-fed-2024-07-25bp']['fact_value'], '-25')
    
    def test_bea_io5_fact_value_unchanged(self):
        self.assertEqual(self.ios['gold-bea-2024-q3-gdp']['fact_value'], '+2.8')
    
    def test_sec_io8_fact_value_unchanged(self):
        self.assertEqual(self.ios['gold-sec-2024-firm-a']['fact_value'], '850000')
    
    def test_evidence_excerpt_unchanged_for_io1(self):
        excerpt = self.ios['gold-fed-2024-09-50bp']['evidence_excerpt']
        self.assertIn('Federal Open Market Committee', excerpt)
    
    def test_canonical_url_unchanged_for_io1(self):
        url = self.ios['gold-fed-2024-09-50bp']['canonical_url']
        self.assertIn('federalreserve.gov', url)
    
    def test_entity_legacy_field_preserved(self):
        """Original entity field preserved as entity_legacy (not deleted)."""
        for io_id, io in self.ios.items():
            self.assertIn('entity_legacy', io, f"{io_id} missing entity_legacy")


class TestRoleDecomposition(unittest.TestCase):
    """Tests for role decomposition correctness."""
    
    def setUp(self):
        with open(REISSUANCE_PATH) as f:
            self.data = yaml.safe_load(f)
        self.ios = {io['io_id']: io for io in self.data['gold_ios']}
    
    def test_every_io_has_role_contract(self):
        for io_id, io in self.ios.items():
            self.assertIn('entity_role_contract', io, f"{io_id} missing entity_role_contract")
    
    def test_every_io_has_source_authority(self):
        for io_id, io in self.ios.items():
            rc = io['entity_role_contract']
            self.assertIn('source_authority', rc)
            self.assertNotEqual(rc['source_authority'], UNRESOLVED, 
                               f"{io_id} source_authority must not be UNRESOLVED (always derivable from URL)")
    
    def test_every_io_has_measured_entity(self):
        for io_id, io in self.ios.items():
            rc = io['entity_role_contract']
            self.assertIn('measured_entity', rc)
            self.assertNotEqual(rc['measured_entity'], UNRESOLVED,
                               f"{io_id} measured_entity must not be UNRESOLVED (derivable from fact_metric)")
    
    def test_sec_event_subjects_unresolved(self):
        """SEC IOs MUST have UNRESOLVED event_subject (firm not named)."""
        for io_id in ['gold-sec-2024-firm-a', 'gold-sec-2024-firm-b', 'gold-sec-2024-firm-c']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertEqual(rc['event_subject'], UNRESOLVED,
                            f"{io_id} event_subject must be UNRESOLVED (firm not named in excerpt)")
    
    def test_sec_source_authority_not_promoted_to_event_subject(self):
        """CRITICAL: SEC source_authority MUST NOT be promoted to event_subject."""
        for io_id in ['gold-sec-2024-firm-a', 'gold-sec-2024-firm-b', 'gold-sec-2024-firm-c']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertNotEqual(rc['source_authority'], rc['event_subject'],
                            f"{io_id}: source_authority must not equal event_subject")
    
    def test_bea_source_authority_is_bea(self):
        for io_id in ['gold-bea-2024-q3-gdp', 'gold-bea-2024-q2-gdp', 'gold-bea-2024-09-pce']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertIn('BEA', rc['source_authority'])
    
    def test_bea_measured_entity_not_bea(self):
        """CRITICAL: BEA measured_entity MUST NOT be BEA."""
        for io_id in ['gold-bea-2024-q3-gdp', 'gold-bea-2024-q2-gdp']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertNotIn('BEA', rc['measured_entity'],
                            f"{io_id}: measured_entity must not contain BEA")
    
    def test_fed_event_subject_is_fomc(self):
        rc = self.ios['gold-fed-2024-09-50bp']['entity_role_contract']
        self.assertIn('FOMC', rc['event_subject'])
    
    def test_ecb_event_subject_is_governing_council(self):
        for io_id in ['gold-ecb-2024-09-25bp', 'gold-ecb-2024-06-25bp']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertIn('Governing Council', rc['event_subject'])
    
    def test_subject_resolution_status_present(self):
        for io_id, io in self.ios.items():
            rc = io['entity_role_contract']
            self.assertIn('subject_resolution_status', rc)
    
    def test_evidence_basis_present(self):
        for io_id, io in self.ios.items():
            rc = io['entity_role_contract']
            self.assertIn('evidence_basis', rc)
            self.assertIn('source_authority', rc['evidence_basis'])
            self.assertIn('event_subject', rc['evidence_basis'])
            self.assertIn('measured_entity', rc['evidence_basis'])


class TestCriticalInvariant(unittest.TestCase):
    """Tests for the CRITICAL INVARIANT: source_authority != event_subject != measured_entity."""
    
    def setUp(self):
        with open(REISSUANCE_PATH) as f:
            self.data = yaml.safe_load(f)
        self.ios = {io['io_id']: io for io in self.data['gold_ios']}
    
    def test_sec_invariant_holds(self):
        """SEC: source=SEC, subject=UNRESOLVED, measured=penalty — all distinct."""
        for io_id in ['gold-sec-2024-firm-a', 'gold-sec-2024-firm-b', 'gold-sec-2024-firm-c']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertNotEqual(rc['source_authority'], rc['event_subject'])
            self.assertNotEqual(rc['source_authority'], rc['measured_entity'])
            self.assertNotEqual(rc['event_subject'], rc['measured_entity'])
    
    def test_bea_invariant_holds(self):
        """BEA: source=BEA, subject=GDP/PCE, measured=GDP growth/PCE price — distinct."""
        for io_id in ['gold-bea-2024-q3-gdp', 'gold-bea-2024-q2-gdp', 'gold-bea-2024-09-pce']:
            rc = self.ios[io_id]['entity_role_contract']
            self.assertNotEqual(rc['source_authority'], rc['event_subject'])
            self.assertNotEqual(rc['source_authority'], rc['measured_entity'])
    
    def test_fed_invariant_exception_documented(self):
        """Fed: committee fills both authority and subject roles (legitimate for monetary policy)."""
        rc = self.ios['gold-fed-2024-09-50bp']['entity_role_contract']
        # For monetary policy, FOMC is both authority (Federal Reserve) and subject
        # This is the documented exception in the contract
        self.assertIn('Federal Reserve', rc['source_authority'])
        self.assertIn('FOMC', rc['event_subject'])


class TestECBSurfaceFormEquivalence(unittest.TestCase):
    """Tests that ECB IO3 correctly handles surface form equivalence."""
    
    def setUp(self):
        with open(REISSUANCE_PATH) as f:
            self.data = yaml.safe_load(f)
        self.ios = {io['io_id']: io for io in self.data['gold_ios']}
    
    def test_ecb_io3_subject_resolution_status_documents_equivalence(self):
        """ECB IO3: status must document the surface form equivalence."""
        rc = self.ios['gold-ecb-2024-09-25bp']['entity_role_contract']
        status = rc['subject_resolution_status']
        self.assertIn('RESOLVED', status)
        # Must reference surface form equivalence or the actual excerpt phrase
        self.assertTrue(
            'Governing Council of the ECB' in status or 'surface_forms_equivalent' in status,
            f"ECB IO3 status must document surface form equivalence: {status}"
        )


if __name__ == '__main__':
    unittest.main()
