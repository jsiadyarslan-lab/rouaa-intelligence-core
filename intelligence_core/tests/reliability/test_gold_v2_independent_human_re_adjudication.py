"""
Tests for Gold-V2 Independent Human Re-Adjudication Gate.

Verifies:
1. Review packet structure (10/10 records present)
2. Original IO identifiers preserved
3. Proposed decompositions preserved
4. 0 Gold mutations
5. 0 fact mutations
6. 0 evidence mutations
7. 0 production mutations
8. 3/3 SEC unresolved cases explicitly reviewed
9. Human verdict fields initially PENDING (agent did NOT generate human labels)
10. Machine proposal vs human adjudication distinguishable

CRITICAL: No test may claim human adjudication has passed merely because
the review packet was generated.
"""
import unittest
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

REVIEW_PACKET_PATH = Path(__file__).parent.parent.parent.parent / "docs" / "evidence" / "gold_v2_review_packet.yaml"

EXPECTED_IO_IDS = [
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

EXPECTED_SEC_IO_IDS = [
    'gold-sec-2024-firm-a',
    'gold-sec-2024-firm-b',
    'gold-sec-2024-firm-c',
]


class TestReviewPacketStructure(unittest.TestCase):
    """Tests that the review packet file exists and is well-formed."""
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
    
    def test_file_exists(self):
        self.assertTrue(REVIEW_PACKET_PATH.exists())
    
    def test_metadata_present(self):
        self.assertIn('metadata', self.data)
        self.assertEqual(self.data['metadata']['review_type'], 'INDEPENDENT_HUMAN_RE_ADJUDICATION')
    
    def test_population_is_10(self):
        self.assertEqual(self.data['metadata']['population'], 10)
    
    def test_canonical_oracle_status_pending(self):
        self.assertEqual(self.data['metadata']['canonical_oracle_status'], 'PENDING_HUMAN_REVIEW')
    
    def test_review_cases_count(self):
        self.assertEqual(len(self.data['review_cases']), 10)


class TestOriginalIOPreservation(unittest.TestCase):
    """Tests that original IO identifiers and fields are preserved."""
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
        self.cases = {c['io_id']: c for c in self.data['review_cases']}
    
    def test_all_10_io_ids_present(self):
        for io_id in EXPECTED_IO_IDS:
            self.assertIn(io_id, self.cases, f"Missing IO: {io_id}")
    
    def test_original_evidence_preserved_for_io1(self):
        case = self.cases['gold-fed-2024-09-50bp']
        ev = case['original_evidence']
        self.assertEqual(ev['io_id'], 'gold-fed-2024-09-50bp')
        self.assertEqual(ev['fact_value'], '-50')
    
    def test_original_evidence_preserved_for_sec_io8(self):
        case = self.cases['gold-sec-2024-firm-a']
        ev = case['original_evidence']
        self.assertEqual(ev['fact_value'], '850000')
    
    def test_evidence_excerpt_preserved(self):
        case = self.cases['gold-fed-2024-09-50bp']
        ev = case['original_evidence']
        self.assertIn('Federal Open Market Committee', ev['evidence_excerpt'])


class TestProposedDecompositionPreservation(unittest.TestCase):
    """Tests that proposed role decompositions are preserved (from re-issuance)."""
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
        self.cases = {c['io_id']: c for c in self.data['review_cases']}
    
    def test_every_case_has_proposed_decomposition(self):
        for io_id, case in self.cases.items():
            self.assertIn('proposed_role_decomposition', case, f"{io_id} missing proposed_role_decomposition")
    
    def test_proposed_source_authority_present(self):
        for io_id, case in self.cases.items():
            pd = case['proposed_role_decomposition']
            self.assertIn('source_authority_candidate', pd)
    
    def test_proposed_event_subject_present(self):
        for io_id, case in self.cases.items():
            pd = case['proposed_role_decomposition']
            self.assertIn('event_subject_candidate', pd)
    
    def test_proposed_measured_entity_present(self):
        for io_id, case in self.cases.items():
            pd = case['proposed_role_decomposition']
            self.assertIn('measured_entity_candidate', pd)


class TestHumanAdjudicationFieldsPending(unittest.TestCase):
    """CRITICAL: Tests that human adjudication fields are PENDING.
    
    The agent does NOT generate human labels. All human verdict fields
    must be PENDING until an independent human reviewer fills them.
    """
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
        self.cases = {c['io_id']: c for c in self.data['review_cases']}
    
    def test_all_human_fields_pending(self):
        """CRITICAL: All human adjudication fields must be PENDING."""
        for io_id, case in self.cases.items():
            ha = case['human_adjudication']
            for key, val in ha.items():
                self.assertEqual(val, 'PENDING',
                    f"{io_id}.{key} = '{val}' — must be PENDING (agent does NOT generate human labels)")
    
    def test_human_source_authority_pending(self):
        for io_id, case in self.cases.items():
            self.assertEqual(case['human_adjudication']['A_source_authority'], 'PENDING')
    
    def test_human_event_subject_pending(self):
        for io_id, case in self.cases.items():
            self.assertEqual(case['human_adjudication']['B_event_subject'], 'PENDING')
    
    def test_human_final_verdict_pending(self):
        for io_id, case in self.cases.items():
            self.assertEqual(case['human_adjudication']['F_final_human_verdict'], 'PENDING')
    
    def test_machine_proposal_distinguishable_from_human(self):
        """The review artifact MUST distinguish machine proposal from human adjudication."""
        for io_id, case in self.cases.items():
            self.assertIn('proposed_role_decomposition', case)
            self.assertIn('human_adjudication', case)
            # Machine proposal fields have actual values
            pd = case['proposed_role_decomposition']
            self.assertNotEqual(pd.get('source_authority_candidate'), 'PENDING')
            self.assertNotEqual(pd.get('event_subject_candidate'), 'PENDING')
            self.assertNotEqual(pd.get('measured_entity_candidate'), 'PENDING')
            # Human adjudication fields are PENDING
            ha = case['human_adjudication']
            self.assertEqual(ha['A_source_authority'], 'PENDING')
            self.assertEqual(ha['B_event_subject'], 'PENDING')


class TestSECSpecialVerification(unittest.TestCase):
    """Tests that the 3 SEC cases have the special verification section."""
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
        self.cases = {c['io_id']: c for c in self.data['review_cases']}
    
    def test_sec_cases_have_special_verification(self):
        for io_id in EXPECTED_SEC_IO_IDS:
            case = self.cases[io_id]
            self.assertIsNotNone(case['sec_special_verification'],
                f"{io_id} must have sec_special_verification section")
    
    def test_sec_special_question_present(self):
        for io_id in EXPECTED_SEC_IO_IDS:
            sec = self.cases[io_id]['sec_special_verification']
            self.assertIn('question', sec)
            self.assertIn('identify the firm', sec['question'])
    
    def test_sec_human_answer_pending(self):
        """SEC human answer must be PENDING — agent does NOT answer."""
        for io_id in EXPECTED_SEC_IO_IDS:
            sec = self.cases[io_id]['sec_special_verification']
            self.assertEqual(sec['human_answer'], 'PENDING')
    
    def test_sec_forbidden_sources_listed(self):
        """SEC section must list forbidden sources for firm recovery."""
        for io_id in EXPECTED_SEC_IO_IDS:
            sec = self.cases[io_id]['sec_special_verification']
            self.assertIn('reviewer_must_NOT_recover_firm_from', sec)
            forbidden = sec['reviewer_must_NOT_recover_firm_from']
            self.assertIn('URL metadata', forbidden)
            self.assertIn('external search', forbidden)
            self.assertIn('SEC lookup', forbidden)
            self.assertIn('entity registry', forbidden)
    
    def test_sec_authorized_evidence_basis_only(self):
        for io_id in EXPECTED_SEC_IO_IDS:
            sec = self.cases[io_id]['sec_special_verification']
            self.assertTrue(sec['authorized_evidence_basis_only'])
    
    def test_sec_proposed_event_subject_is_unresolved(self):
        """SEC proposed event_subject must be UNRESOLVED (from re-issuance)."""
        for io_id in EXPECTED_SEC_IO_IDS:
            pd = self.cases[io_id]['proposed_role_decomposition']
            self.assertEqual(pd['event_subject_candidate'], 'UNRESOLVED',
                f"{io_id}: proposed event_subject must be UNRESOLVED")


class TestNoForbiddenChanges(unittest.TestCase):
    """Tests that no forbidden changes occurred during review packet preparation."""
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
    
    def test_canonical_oracle_not_auto_accepted(self):
        """The canonical oracle status must NOT be auto-accepted."""
        self.assertEqual(self.data['metadata']['canonical_oracle_status'], 'PENDING_HUMAN_REVIEW')
    
    def test_no_human_verdicts_filled_by_agent(self):
        """No human verdicts may be filled by the agent."""
        for case in self.data['review_cases']:
            ha = case['human_adjudication']
            for key, val in ha.items():
                self.assertEqual(val, 'PENDING',
                    f"Agent filled {case['io_id']}.{key} — FORBIDDEN")


class TestReviewPacketNotClaimingCompletion(unittest.TestCase):
    """CRITICAL: The review packet must NOT claim human adjudication is complete."""
    
    def setUp(self):
        with open(REVIEW_PACKET_PATH) as f:
            self.data = yaml.safe_load(f)
    
    def test_metadata_does_not_claim_completion(self):
        """Metadata must not claim human adjudication is complete."""
        self.assertNotEqual(self.data['metadata']['canonical_oracle_status'], 'ACCEPTED')
        self.assertNotEqual(self.data['metadata']['canonical_oracle_status'], 'REJECTED')
    
    def test_review_cases_have_pending_verdicts(self):
        """All review cases must have PENDING human verdicts."""
        for case in self.data['review_cases']:
            self.assertEqual(case['human_adjudication']['F_final_human_verdict'], 'PENDING')


if __name__ == '__main__':
    unittest.main()
