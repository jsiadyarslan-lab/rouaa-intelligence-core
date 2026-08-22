from __future__ import annotations

import sys
import unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.contracts import EvidenceContextV1
from intelligence_core.semantic_claim_binding import (
    CONFIRMED, NOT_FOUND, bind_event_state_claims, bind_subject_entities, bind_temporal_claims,
)


def context(**changes):
    values = dict(fact_id="fact-1", document_id="doc-1", evidence_id="ev-1", primary_segment_id="seg-1")
    values.update(changes)
    return EvidenceContextV1(**values)


class TestV47SemanticClaimBinding(unittest.TestCase):
    def test_publisher_in_adjacent_context_cannot_confirm_subject(self):
        ctx = context(entity_signals=[{"entity": "SEC", "match": "Securities and Exchange Commission"}])
        claim = bind_subject_entities(ctx, "Apple reported revenue of $5 billion.")[0]
        self.assertEqual(claim.status, NOT_FOUND)
        self.assertEqual(claim.value, "UNKNOWN")

    def test_entity_in_fact_segment_is_bound(self):
        ctx = context(entity_signals=[{"entity": "ECB", "match": "European Central Bank"}])
        claim = bind_subject_entities(ctx, "The European Central Bank held its policy rate.")[0]
        self.assertEqual(claim.status, CONFIRMED)
        self.assertEqual(claim.segment_id, "seg-1")

    def test_date_in_adjacent_context_cannot_be_event_date_claim(self):
        ctx = context(temporal_signals=[{"type": "iso_date", "match": "2026-08-20"}])
        claim = bind_temporal_claims(ctx, "The policy rate is 4.0 percent.")[0]
        self.assertEqual(claim.status, NOT_FOUND)

    def test_date_in_fact_segment_is_bound(self):
        ctx = context(temporal_signals=[{"type": "iso_date", "match": "2026-08-20"}])
        claim = bind_temporal_claims(ctx, "On 2026-08-20, the policy rate was held at 4.0 percent.")[0]
        self.assertEqual(claim.status, CONFIRMED)

    def test_state_in_adjacent_context_cannot_be_bound(self):
        ctx = context(state_signals=[{"state": "INCREASED"}])
        claim = bind_event_state_claims(ctx, "The policy rate is 4.0 percent.")[0]
        self.assertEqual(claim.status, NOT_FOUND)

    def test_state_in_fact_segment_is_bound(self):
        ctx = context(state_signals=[{"state": "INCREASED"}])
        claim = bind_event_state_claims(ctx, "The policy rate increased to 4.0 percent.")[0]
        self.assertEqual(claim.status, CONFIRMED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
