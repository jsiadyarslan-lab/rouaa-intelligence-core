"""V48U — Subject Binding & Ontology Fidelity Tests.

Tests:
  §2 Semantic binding: registry match ≠ subject proof
  §3 "GDP increased" binds; "because unemployment increased" does NOT
  §4 MARKET is first-class (NOT mapped to instrument)
  §5 REGULATION is first-class (NOT collapsed to concept)
  §8 Adversarial cases
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.contracts import SubjectEntityV1
from intelligence_core.subject_entity import (
    resolve_subject, _check_semantic_binding,
    _ALL_REGISTRIES, _ENTITY_REGISTRY, _CONCEPT_REGISTRY,
    _INDICATOR_REGISTRY, _INSTRUMENT_REGISTRY, _REGULATION_REGISTRY,
    _MARKET_REGISTRY,
    SUBJECT_CONFIRMED, SUBJECT_NOT_FOUND,
    METHOD_PRIMARY_EVIDENCE,
)
from intelligence_core.structural_parser import EvidenceSegmentV1
from intelligence_core.evidence_context import EvidenceContextV1
from intelligence_core.publisher_institution import identify_publisher


def _seg(text, sid="seg-0", stype="PARAGRAPH", heading=None):
    return EvidenceSegmentV1(document_id="d", segment_id=sid, segment_index=0, segment_type=stype, text=text, heading_context=heading)

def _ctx(fid="fact-1", sid="seg-0"):
    return EvidenceContextV1(fact_id=fid, document_id="d", evidence_id="ev-1", primary_segment_id=sid, evidence_excerpt="")


class TestSemanticBinding(unittest.TestCase):
    """§2 — registry match ≠ subject proof."""

    def test_gdp_increased_binds(self):
        seg = _seg("GDP increased in Germany.")
        io = {"facts": [{"fact_id": "f1", "metric": "test", "value": "1", "excerpt": "GDP increased"}], "evidence": [{"fact_id": "f1", "excerpt": "GDP increased"}]}
        ctx = _ctx()
        subject = resolve_subject(io, [ctx], {"f1": seg}, [seg], None)
        self.assertEqual(subject.subject_indicator_status, "CONFIRMED")

    def test_unemployment_in_subordinate_clause_does_not_bind(self):
        # "Monetary policy was tightened because unemployment increased"
        # unemployment is AFTER "because" → subordinate clause → NOT bound
        seg = _seg("Monetary policy was tightened because unemployment increased.")
        io = {"facts": [{"fact_id": "f1", "metric": "test", "value": "1", "excerpt": "Monetary policy tightened"}], "evidence": [{"fact_id": "f1", "excerpt": "..."}]}
        ctx = _ctx()
        subject = resolve_subject(io, [ctx], {"f1": seg}, [seg], None)
        # Unemployment should NOT be bound (it's after "because")
        # Monetary Policy should be bound (it's in the main clause)
        self.assertEqual(subject.subject_concept_status, "CONFIRMED")  # Monetary Policy IS the subject
        self.assertEqual(subject.subject_indicator_status, "NOT_FOUND")  # unemployment is NOT


class TestMarketFirstClass(unittest.TestCase):
    """§4 — MARKET is first-class, NOT mapped to instrument."""

    def test_market_field_exists_on_contract(self):
        s = SubjectEntityV1(subject_entity_id="x", canonical_name="y")
        self.assertTrue(hasattr(s, "subject_market"))
        self.assertTrue(hasattr(s, "subject_market_status"))
        self.assertEqual(s.subject_market_status, "NOT_FOUND")

    def test_market_not_mapped_to_instrument(self):
        # Check that MARKET_REGISTRY is separate from INSTRUMENT_REGISTRY
        self.assertNotEqual(id(_MARKET_REGISTRY), id(_INSTRUMENT_REGISTRY))
        # Foreign Exchange is in MARKET_REGISTRY, NOT INSTRUMENT_REGISTRY
        self.assertIn("fx", _MARKET_REGISTRY)
        self.assertNotIn("fx", _INSTRUMENT_REGISTRY)


class TestRegulationFirstClass(unittest.TestCase):
    """§5 — REGULATION is first-class, NOT collapsed to concept."""

    def test_regulation_field_exists_on_contract(self):
        s = SubjectEntityV1(subject_entity_id="x", canonical_name="y")
        self.assertTrue(hasattr(s, "subject_regulation"))
        self.assertTrue(hasattr(s, "subject_regulation_status"))
        self.assertEqual(s.subject_regulation_status, "NOT_FOUND")

    def test_regulation_not_collapsed_to_concept(self):
        self.assertNotEqual(id(_REGULATION_REGISTRY), id(_CONCEPT_REGISTRY))
        self.assertIn("penalty", _REGULATION_REGISTRY)
        self.assertNotIn("penalty", _CONCEPT_REGISTRY)


class TestAdversarialCases(unittest.TestCase):
    """§8 — adversarial cases through actual resolver."""

    def test_ecb_raised_rates_as_unemployment_increased(self):
        # unemployment is after "as" → subordinate → NOT bound
        seg = _seg("ECB raised rates as unemployment increased.")
        io = {"facts": [{"fact_id": "f1", "metric": "test", "value": "1", "excerpt": "ECB raised rates"}], "evidence": [{"fact_id": "f1", "excerpt": "..."}]}
        ctx = _ctx()
        subject = resolve_subject(io, [ctx], {"f1": seg}, [seg], None)
        # unemployment should NOT be the subject (it's after "as")
        self.assertEqual(subject.subject_indicator_status, "NOT_FOUND")

    def test_gdp_increased_binds_correctly(self):
        seg = _seg("GDP increased in Germany by 0.4%.")
        io = {"facts": [{"fact_id": "f1", "metric": "test", "value": "0.4", "excerpt": "GDP increased"}], "evidence": [{"fact_id": "f1", "excerpt": "..."}]}
        ctx = _ctx()
        subject = resolve_subject(io, [ctx], {"f1": seg}, [seg], None)
        self.assertEqual(subject.subject_indicator, "Gross Domestic Product")
        self.assertEqual(subject.subject_indicator_status, "CONFIRMED")

    def test_inflation_rose_binds_correctly(self):
        seg = _seg("Inflation rose in France to 2.1%.")
        io = {"facts": [{"fact_id": "f1", "metric": "test", "value": "2.1", "excerpt": "Inflation rose"}], "evidence": [{"fact_id": "f1", "excerpt": "..."}]}
        ctx = _ctx()
        subject = resolve_subject(io, [ctx], {"f1": seg}, [seg], None)
        self.assertEqual(subject.subject_indicator, "Inflation")
        self.assertEqual(subject.subject_indicator_status, "CONFIRMED")


class TestEntityRegistryEmpty(unittest.TestCase):
    """§3 — ENTITY_REGISTRY remains empty."""

    def test_entity_registry_empty(self):
        self.assertEqual(len(_ENTITY_REGISTRY), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
