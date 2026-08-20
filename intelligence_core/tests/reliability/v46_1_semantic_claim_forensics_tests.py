from __future__ import annotations

import sys
import unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.tests.reliability.v46_1_semantic_claim_forensics import (
    entity_disposition, temporal_disposition, state_disposition, event_type_disposition,
)


class TestV461ForensicRules(unittest.TestCase):
    def test_source_match_is_not_subject_proof(self):
        audit = {"entity_status": "ENTITY_CONFIRMED", "why": "Single institution 'SEC' found in evidence matches source_name 'sec'"}
        self.assertEqual(entity_disposition(audit), "UNSUPPORTED_PUBLISHER_SUBJECT_CONFLATION")

    def test_unclaimed_entity_is_not_escalated(self):
        self.assertEqual(entity_disposition({"entity_status": "ENTITY_NOT_FOUND"}), "NOT_CLAIMED")

    def test_any_regex_temporal_claim_requires_event_local_review(self):
        audit = {f"{field}_status": "NOT_FOUND" for field in ("event_date", "reference_period", "effective_date", "publication_date", "revision_date")}
        audit["event_date_status"] = "CONFIRMED"
        self.assertEqual(temporal_disposition(audit), "REQUIRES_HUMAN_REVIEW_UNSCOPED_TEMPORAL")

    def test_unknown_state_is_not_claimed(self):
        self.assertEqual(state_disposition("UNKNOWN"), "NOT_CLAIMED")

    def test_known_state_requires_event_local_review(self):
        self.assertEqual(state_disposition("INCREASED"), "REQUIRES_HUMAN_REVIEW_UNSCOPED_STATE")

    def test_v46_did_not_validate_event_type(self):
        self.assertEqual(event_type_disposition({"event_type": "regulatory_enforcement"}), "NOT_AUDITED_BY_V46")


if __name__ == "__main__":
    unittest.main(verbosity=2)
