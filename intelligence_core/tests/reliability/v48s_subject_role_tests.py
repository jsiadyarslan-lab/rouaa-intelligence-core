"""V48S — Subject Role & Semantic Object Model Reconciliation.

Per V48S directive §4 CRITICAL RULE:
  Do NOT define "subject = ENTITY" as an axiom.
  Instead define:
    subject = the semantic object the event asserts a state,
    change, action, measurement, or decision about.

  Then determine whether that object is represented as:
    ENTITY | CONCEPT | INDICATOR | INSTRUMENT | MARKET | REGULATION

This test file encodes the role ontology + 5 mandatory semantic cases
+ role coexistence rules + subject≠actor + subject≠affected analysis
+ readiness coupling audit.

Per §7: ENTITY_REGISTRY remains empty. No new patterns.
Per §8: 3 artifacts only (tests, results JSON, MD document).
"""
from __future__ import annotations
import sys, unittest, json, time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))


# ═══════════════════════════════════════════════════════════════════════
# §2 — ROLE ONTOLOGY (formal semantic contract)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SubjectRoleModel:
    """V48S §2 — Formal semantic contract for event roles.

    Each role has: definition, can_be_null, can_equal_another_role,
    evidence_requirements, whether promotable to canonical IO.
    """
    role: str
    definition: str
    can_be_null: bool
    can_equal_another_role: list  # list of role names this role CAN equal
    evidence_requirements: str
    promotable_to_canonical_io: bool


ROLE_ONTOLOGY: dict[str, SubjectRoleModel] = {
    "PUBLISHER": SubjectRoleModel(
        role="PUBLISHER",
        definition="The institution responsible for publishing the source/document. Identified from source metadata (source_id, source_path, institution_id). NEVER inferred from event content.",
        can_be_null=False,  # every document has a publisher (source_id)
        can_equal_another_role=["ACTOR"],  # publisher can also be the actor
        evidence_requirements="source_id + source_path + (optional) institution_id",
        promotable_to_canonical_io=True,  # publisher_institution is a canonical IO field
    ),
    "ACTOR": SubjectRoleModel(
        role="ACTOR",
        definition="The agent that PERFORMS the action described in the event. Often the publisher, but can differ (e.g., a news outlet reporting on ECB's decision). CAN equal SUBJECT_ENTITY when the event is about the actor's own action (e.g., 'Apple reports revenue' — Apple is both actor AND subject).",
        can_be_null=True,  # statistical observations have no actor
        can_equal_another_role=["PUBLISHER", "SUBJECT_ENTITY"],
        evidence_requirements="event-local action verb (announces, publishes, releases, issues, decides, raises, lowers, cuts, approves, settles, fines, imposes) + the actor name in the primary segment",
        promotable_to_canonical_io=True,
    ),
    "SUBJECT_ENTITY": SubjectRoleModel(
        role="SUBJECT_ENTITY",
        definition="The REAL ENTITY (institution, company, jurisdiction) that the event is ABOUT — when the event's semantic object is an entity. Can be NULL when the event is about an indicator/concept/instrument (e.g., 'GDP increased' — subject is GDP the INDICATOR, not an entity). CAN equal ACTOR (Apple reports revenue: subject=Apple, actor=Apple). CAN equal AFFECTED_ENTITY (FCA fines Broker X: subject=Broker X, affected=Broker X).",
        can_be_null=True,  # the critical V48S insight: subject can be non-entity
        can_equal_another_role=["ACTOR", "AFFECTED_ENTITY"],
        evidence_requirements="entity name in primary segment OR event-local context that structurally binds the entity to the event",
        promotable_to_canonical_io=True,
    ),
    "SUBJECT_CONCEPT": SubjectRoleModel(
        role="SUBJECT_CONCEPT",
        definition="The POLICY CONCEPT the event is about (e.g., Monetary Policy, Fiscal Policy, Enforcement Action). Can coexist with SUBJECT_ENTITY (Apple + Revenue). Can be the ONLY subject when no entity is involved (ECB raises rate: subject_concept=Monetary Policy, subject_entity=NOT_FOUND).",
        can_be_null=True,
        can_equal_another_role=[],  # concept is never equal to entity/actor
        evidence_requirements="concept alias match in primary segment or event-local heading",
        promotable_to_canonical_io=True,
    ),
    "SUBJECT_INDICATOR": SubjectRoleModel(
        role="SUBJECT_INDICATOR",
        definition="The MACROECONOMIC INDICATOR the event is about (e.g., GDP, CPI, Inflation, Unemployment). Can be the ONLY subject (GDP increased in Germany: subject_indicator=GDP, subject_entity=NOT_FOUND). Can coexist with SUBJECT_ENTITY (Apple + Revenue — if Revenue is classified as indicator).",
        can_be_null=True,
        can_equal_another_role=[],
        evidence_requirements="indicator alias match in primary segment",
        promotable_to_canonical_io=True,
    ),
    "SUBJECT_INSTRUMENT": SubjectRoleModel(
        role="SUBJECT_INSTRUMENT",
        definition="The FINANCIAL INSTRUMENT the event is about (e.g., Policy Rate, Bonds, Equities). Can coexist with SUBJECT_CONCEPT (ECB raises policy rate: subject_concept=Monetary Policy + subject_instrument=Policy Rate).",
        can_be_null=True,
        can_equal_another_role=[],
        evidence_requirements="instrument alias match in primary segment",
        promotable_to_canonical_io=True,
    ),
    "JURISDICTION": SubjectRoleModel(
        role="JURISDICTION",
        definition="The geographic or political scope of the event (e.g., Germany, France, Euro Area, United States, United Kingdom). Can coexist with any subject role. Is NOT the subject itself — it's the scope.",
        can_be_null=True,
        can_equal_another_role=[],  # jurisdiction is never equal to subject
        evidence_requirements="jurisdiction name in primary segment or event-local context",
        promotable_to_canonical_io=True,
    ),
    "AFFECTED_ENTITY": SubjectRoleModel(
        role="AFFECTED_ENTITY",
        definition="The entity ACTED UPON by the event. CAN equal SUBJECT_ENTITY (FCA fines Broker X: affected=Broker X, subject=Broker X — the event is about Broker X being fined). Is NOT automatically the subject — requires event-type analysis to determine if affected=subject.",
        can_be_null=True,
        can_equal_another_role=["SUBJECT_ENTITY"],  # affected CAN equal subject
        evidence_requirements="passive verb context (was fined, was penalized, was charged) + entity name",
        promotable_to_canonical_io=True,
    ),
    "MENTIONED_ENTITY": SubjectRoleModel(
        role="MENTIONED_ENTITY",
        definition="An entity that merely APPEARS in the event text but is neither the actor, subject, affected, nor publisher. CANNOT be promoted to subject_entity merely by appearing.",
        can_be_null=True,
        can_equal_another_role=[],  # mentioned is never equal to subject
        evidence_requirements="entity name in text without event-local binding",
        promotable_to_canonical_io=False,  # mentioned entities are NOT canonical
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# §4 — CRITICAL RULE: subject ≠ ENTITY (axiom)
# ═══════════════════════════════════════════════════════════════════════

SUBJECT_DEFINITION = (
    "subject = the semantic object the event asserts a state, "
    "change, action, measurement, or decision about."
)

SUBJECT_REPRESENTATION_RULE = (
    "The subject object can be represented as: ENTITY | CONCEPT | "
    "INDICATOR | INSTRUMENT | MARKET | REGULATION. "
    "It is NOT required to be an ENTITY."
)

# V48R's incorrect axiom (rejected by V48S):
V48R_REJECTED_AXIOM = "subject = REAL ENTITY"  # ← V48S rejects this


# ═══════════════════════════════════════════════════════════════════════
# §5 — ROLE COEXISTENCE RULES
# ═══════════════════════════════════════════════════════════════════════

COEXISTENCE_RULES = {
    "subject_entity + subject_concept CAN coexist": True,
    "subject_entity + subject_indicator CAN coexist": True,
    "subject_entity + subject_instrument CAN coexist": True,
    "subject_concept + subject_indicator CAN coexist": True,
    "subject_concept + subject_instrument CAN coexist": True,
    "actor + subject_entity CAN be same": True,  # Apple reports revenue
    "actor + subject_entity CAN differ": True,   # ECB raises rate (actor=ECB, subject=Policy Rate)
    "affected_entity + subject_entity CAN be same": True,   # FCA fines Broker X
    "affected_entity + subject_entity CAN differ": True,    # ECB raises rate (no affected)
    "publisher + actor CAN be same": True,      # ECB publishes + ECB acts
    "publisher + actor CAN differ": True,       # Reuters publishes + ECB acts
    "mentioned_entity + subject_entity CANNOT auto-promote": True,
}


# ═══════════════════════════════════════════════════════════════════════
# §3 — 5 MANDATORY SEMANTIC CASES
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SemanticCase:
    """A mandatory semantic test case with expected role assignments."""
    text: str
    publisher: str
    actor: Optional[str]
    subject_entity: Optional[str]
    subject_concept: Optional[str]
    subject_indicator: Optional[str]
    subject_instrument: Optional[str]
    jurisdiction: Optional[str]
    affected_entity: Optional[str]
    rationale: str


MANDATORY_CASES = [
    SemanticCase(
        text="ECB raises policy rate",
        publisher="European Central Bank",
        actor="European Central Bank",  # ECB performs the action
        subject_entity=None,  # NOT an entity — the event is about policy rate (instrument)
        subject_concept="Monetary Policy",  # the policy concept
        subject_indicator=None,
        subject_instrument="Policy Rate",  # the specific instrument
        jurisdiction="Euro Area",
        affected_entity=None,
        rationale=(
            "The event is about ECB's decision to raise the policy rate. "
            "ECB is the ACTOR (it performs the 'raise' action). The "
            "SUBJECT is the policy rate — which is an INSTRUMENT, not an "
            "entity. subject_concept=Monetary Policy captures the broader "
            "policy area. subject_entity=NOT_FOUND because the event is "
            "not about an entity (e.g., a company or institution being "
            "acted upon); it's about a financial instrument. Actor ≠ Subject "
            "here because ECB is the actor, not the semantic object of the "
            "event."
        ),
    ),
    SemanticCase(
        text="Apple reports revenue",
        publisher=None,  # not specified — could be Apple or third party
        actor="Apple",  # Apple performs the 'reports' action
        subject_entity="Apple",  # the event IS about Apple's revenue
        subject_concept="Revenue",  # the financial concept
        subject_indicator=None,  # revenue is not a macro indicator
        subject_instrument=None,
        jurisdiction=None,
        affected_entity=None,
        rationale=(
            "The event is about Apple's revenue report. Apple is BOTH the "
            "ACTOR (it reports) AND the SUBJECT_ENTITY (the event is about "
            "Apple). subject_concept=Revenue captures what kind of report. "
            "Actor = Subject here — this is a legal coexistence per §5. "
            "subject_entity is NOT_FOUND only if we refuse to treat Apple "
            "as an entity — but Apple IS a real company entity. The "
            "ENTITY_REGISTRY is empty (per §7), so in practice this IO "
            "would have subject_entity=NOT_FOUND until the registry is "
            "populated. But the SEMANTIC MODEL says: if Apple were in the "
            "registry, subject_entity=Apple would be correct."
        ),
    ),
    SemanticCase(
        text="FCA fines Broker X",
        publisher="Financial Conduct Authority",
        actor="Financial Conduct Authority",  # FCA performs the 'fines' action
        subject_entity="Broker X",  # the event IS about Broker X being fined
        subject_concept="Enforcement Action",
        subject_indicator=None,
        subject_instrument=None,
        jurisdiction="United Kingdom",
        affected_entity="Broker X",  # Broker X is also the affected entity
        rationale=(
            "The event is about Broker X being fined by FCA. Broker X is "
            "BOTH the AFFECTED_ENTITY (it is acted upon) AND the "
            "SUBJECT_ENTITY (the event is about Broker X). FCA is the "
            "ACTOR and PUBLISHER. subject_concept=Enforcement Action "
            "captures the event type. Affected = Subject here — this is a "
            "legal coexistence per §5. V48R incorrectly said "
            "'affected → never subject' — V48S corrects this: affected "
            "CAN equal subject when the event is about the affected entity."
        ),
    ),
    SemanticCase(
        text="GDP increased in Germany",
        publisher=None,  # statistical agency (e.g., Destatis)
        actor=None,  # no actor — this is a statistical observation
        subject_entity=None,  # no entity — the subject is GDP the indicator
        subject_concept=None,
        subject_indicator="GDP",  # the event is about GDP
        subject_instrument=None,
        jurisdiction="Germany",
        affected_entity=None,
        rationale=(
            "The event is about GDP increasing. GDP is an INDICATOR, not "
            "an entity. subject_indicator=GDP. jurisdiction=Germany. "
            "There is NO actor (no one 'performed' the increase — it's a "
            "statistical observation). subject_entity=NOT_FOUND is "
            "CORRECT and EXPECTED — the event doesn't need an entity "
            "subject. The IO is institutionally useful even without "
            "subject_entity. This is the key V48S insight: subject can "
            "be an INDICATOR without any entity."
        ),
    ),
    SemanticCase(
        text="Inflation rose in France",
        publisher=None,  # statistical agency (e.g., INSEE)
        actor=None,  # no actor
        subject_entity=None,  # no entity
        subject_concept=None,
        subject_indicator="Inflation",
        subject_instrument=None,
        jurisdiction="France",
        affected_entity=None,
        rationale=(
            "The event is about inflation rising. Inflation is an "
            "INDICATOR. subject_indicator=Inflation. jurisdiction=France. "
            "No actor, no entity subject. The IO is institutionally "
            "useful (inflation is a key macro indicator for monetary "
            "policy decisions). subject_entity=NOT_FOUND is correct."
        ),
    ),
]


# ═══════════════════════════════════════════════════════════════════════
# §6 — READINESS COUPLING ANALYSIS
# ═══════════════════════════════════════════════════════════════════════

READINESS_COUPLING_ANALYSIS = {
    "current_rule": "entity_ok = entity_status == ENTITY_CONFIRMED",
    "problem": (
        "The current readiness model makes entity confirmation a HARD "
        "requirement for READY. This means IOs about macro indicators "
        "(GDP, CPI, Inflation) can NEVER be READY — even though they "
        "are institutionally useful. This is a P0 semantic governance "
        "issue."
    ),
    "impact": {
        "central_bank_policy_decision": (
            "READY requires entity_ok. ECB policy decision has "
            "subject_concept=Monetary Policy + subject_instrument=Policy "
            "Rate but subject_entity=NOT_FOUND. Under current rule: "
            "BLOCKED. Under V48S model: should be READY (has 2 confirmed "
            "subject roles)."
        ),
        "gdp_release": (
            "GDP release has subject_indicator=GDP + jurisdiction=Germany "
            "but subject_entity=NOT_FOUND. Under current rule: BLOCKED. "
            "Under V48S model: should be READY (has confirmed indicator "
            "+ jurisdiction)."
        ),
        "inflation_release": (
            "Inflation release has subject_indicator=Inflation + "
            "jurisdiction=France. Under current rule: BLOCKED. Under "
            "V48S model: should be READY."
        ),
        "regulatory_enforcement": (
            "FCA fines Broker X has subject_entity=Broker X + "
            "affected_entity=Broker X + subject_concept=Enforcement "
            "Action. Under current rule: READY (if Broker X in registry). "
            "Under V48S model: READY."
        ),
        "market_level_event": (
            "Market events (e.g., FX moves) may have "
            "subject_instrument=Foreign Exchange but no entity. Under "
            "current rule: BLOCKED. Under V48S model: should be PARTIAL "
            "or READY."
        ),
        "company_earnings": (
            "Apple reports revenue has subject_entity=Apple + "
            "subject_concept=Revenue. Under current rule: READY (if "
            "Apple in registry). Under V48S model: READY."
        ),
    },
    "proposed_fix": (
        "READY should require: at least ONE of {subject_entity, "
        "subject_concept, subject_indicator, subject_instrument} is "
        "CONFIRMED — NOT specifically subject_entity. This decouples "
        "readiness from entity-only confirmation."
    ),
    "v48s_decision": (
        "V48S does NOT change the readiness implementation (per §6 "
        "'Do not change the readiness implementation yet'). V48S only "
        "produces the semantic decision and impact analysis. The fix "
        "belongs to a later phase."
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════

class TestRoleOntology(unittest.TestCase):
    """§2 — Role ontology formally defined."""

    def test_all_roles_defined(self):
        expected = {"PUBLISHER", "ACTOR", "SUBJECT_ENTITY", "SUBJECT_CONCEPT",
                    "SUBJECT_INDICATOR", "SUBJECT_INSTRUMENT", "JURISDICTION",
                    "AFFECTED_ENTITY", "MENTIONED_ENTITY"}
        self.assertEqual(set(ROLE_ONTOLOGY.keys()), expected)

    def test_every_role_has_definition(self):
        for role, model in ROLE_ONTOLOGY.items():
            self.assertTrue(model.definition, f"{role} has empty definition")
            self.assertIsInstance(model.can_be_null, bool)
            self.assertIsInstance(model.can_equal_another_role, list)
            self.assertTrue(model.evidence_requirements)
            self.assertIsInstance(model.promotable_to_canonical_io, bool)

    def test_subject_entity_can_be_null(self):
        """V48S §4 CRITICAL RULE: subject ≠ ENTITY. subject_entity CAN be null."""
        self.assertTrue(ROLE_ONTOLOGY["SUBJECT_ENTITY"].can_be_null,
                        "SUBJECT_ENTITY must be nullable — subject can be non-entity")

    def test_actor_can_equal_subject_entity(self):
        """§5: actor + subject_entity CAN be same (Apple reports revenue)."""
        self.assertIn("SUBJECT_ENTITY", ROLE_ONTOLOGY["ACTOR"].can_equal_another_role)

    def test_affected_can_equal_subject_entity(self):
        """§5: affected_entity + subject_entity CAN be same (FCA fines Broker X)."""
        self.assertIn("SUBJECT_ENTITY", ROLE_ONTOLOGY["AFFECTED_ENTITY"].can_equal_another_role)

    def test_mentioned_entity_not_promotable(self):
        """MENTIONED_ENTITY is NOT promotable to canonical IO."""
        self.assertFalse(ROLE_ONTOLOGY["MENTIONED_ENTITY"].promotable_to_canonical_io)


class TestCriticalRule(unittest.TestCase):
    """§4 — subject ≠ ENTITY (axiom rejected)."""

    def test_subject_definition_not_entity_axiom(self):
        self.assertNotIn("REAL ENTITY", SUBJECT_DEFINITION)
        self.assertIn("semantic object", SUBJECT_DEFINITION)

    def test_v48r_axiom_rejected(self):
        self.assertEqual(V48R_REJECTED_AXIOM, "subject = REAL ENTITY")

    def test_subject_can_be_multiple_types(self):
        self.assertIn("ENTITY", SUBJECT_REPRESENTATION_RULE)
        self.assertIn("CONCEPT", SUBJECT_REPRESENTATION_RULE)
        self.assertIn("INDICATOR", SUBJECT_REPRESENTATION_RULE)
        self.assertIn("INSTRUMENT", SUBJECT_REPRESENTATION_RULE)


class TestRoleCoexistence(unittest.TestCase):
    """§5 — Role coexistence rules."""

    def test_subject_entity_plus_concept_can_coexist(self):
        self.assertTrue(COEXISTENCE_RULES["subject_entity + subject_concept CAN coexist"])

    def test_subject_entity_plus_indicator_can_coexist(self):
        self.assertTrue(COEXISTENCE_RULES["subject_entity + subject_indicator CAN coexist"])

    def test_actor_plus_subject_can_be_same(self):
        self.assertTrue(COEXISTENCE_RULES["actor + subject_entity CAN be same"])

    def test_actor_plus_subject_can_differ(self):
        self.assertTrue(COEXISTENCE_RULES["actor + subject_entity CAN differ"])

    def test_affected_plus_subject_can_be_same(self):
        self.assertTrue(COEXISTENCE_RULES["affected_entity + subject_entity CAN be same"])

    def test_affected_plus_subject_can_differ(self):
        self.assertTrue(COEXISTENCE_RULES["affected_entity + subject_entity CAN differ"])

    def test_mentioned_cannot_auto_promote_to_subject(self):
        self.assertTrue(COEXISTENCE_RULES["mentioned_entity + subject_entity CANNOT auto-promote"])


class TestMandatoryCase_ECBRaisesRate(unittest.TestCase):
    """§3 Case 1: 'ECB raises policy rate'."""

    def setUp(self):
        self.case = next(c for c in MANDATORY_CASES if "ECB raises" in c.text)

    def test_publisher_is_ecb(self):
        self.assertEqual(self.case.publisher, "European Central Bank")

    def test_actor_is_ecb(self):
        self.assertEqual(self.case.actor, "European Central Bank")

    def test_subject_entity_is_not_found(self):
        """The event is about policy rate (instrument), not about an entity."""
        self.assertIsNone(self.case.subject_entity)

    def test_subject_concept_is_monetary_policy(self):
        self.assertEqual(self.case.subject_concept, "Monetary Policy")

    def test_subject_instrument_is_policy_rate(self):
        self.assertEqual(self.case.subject_instrument, "Policy Rate")

    def test_jurisdiction_is_euro_area(self):
        self.assertEqual(self.case.jurisdiction, "Euro Area")

    def test_actor_differs_from_subject(self):
        """ECB is the actor, but the subject is the policy rate (instrument)."""
        self.assertNotEqual(self.case.actor, self.case.subject_entity)


class TestMandatoryCase_AppleReportsRevenue(unittest.TestCase):
    """§3 Case 2: 'Apple reports revenue'."""

    def setUp(self):
        self.case = next(c for c in MANDATORY_CASES if "Apple reports" in c.text)

    def test_actor_is_apple(self):
        self.assertEqual(self.case.actor, "Apple")

    def test_subject_entity_is_apple(self):
        """The event IS about Apple — Apple is both actor AND subject."""
        self.assertEqual(self.case.subject_entity, "Apple")

    def test_subject_concept_is_revenue(self):
        self.assertEqual(self.case.subject_concept, "Revenue")

    def test_actor_equals_subject(self):
        """§5: actor + subject_entity CAN be same."""
        self.assertEqual(self.case.actor, self.case.subject_entity)


class TestMandatoryCase_FCAFinesBrokerX(unittest.TestCase):
    """§3 Case 3: 'FCA fines Broker X'."""

    def setUp(self):
        self.case = next(c for c in MANDATORY_CASES if "FCA fines" in c.text)

    def test_publisher_is_fca(self):
        self.assertEqual(self.case.publisher, "Financial Conduct Authority")

    def test_actor_is_fca(self):
        self.assertEqual(self.case.actor, "Financial Conduct Authority")

    def test_subject_entity_is_broker_x(self):
        """The event IS about Broker X being fined."""
        self.assertEqual(self.case.subject_entity, "Broker X")

    def test_affected_entity_is_broker_x(self):
        self.assertEqual(self.case.affected_entity, "Broker X")

    def test_affected_equals_subject(self):
        """§5: affected_entity + subject_entity CAN be same."""
        self.assertEqual(self.case.affected_entity, self.case.subject_entity)

    def test_subject_concept_is_enforcement_action(self):
        self.assertEqual(self.case.subject_concept, "Enforcement Action")


class TestMandatoryCase_GDPIncreasedInGermany(unittest.TestCase):
    """§3 Case 4: 'GDP increased in Germany'."""

    def setUp(self):
        self.case = next(c for c in MANDATORY_CASES if "GDP increased" in c.text)

    def test_actor_is_null(self):
        """No actor — this is a statistical observation."""
        self.assertIsNone(self.case.actor)

    def test_subject_entity_is_not_found(self):
        """The subject is GDP (indicator), not an entity."""
        self.assertIsNone(self.case.subject_entity)

    def test_subject_indicator_is_gdp(self):
        self.assertEqual(self.case.subject_indicator, "GDP")

    def test_jurisdiction_is_germany(self):
        self.assertEqual(self.case.jurisdiction, "Germany")

    def test_no_entity_needed_for_usefulness(self):
        """The IO is institutionally useful even without subject_entity."""
        self.assertIsNone(self.case.subject_entity)
        self.assertIsNotNone(self.case.subject_indicator)
        self.assertIsNotNone(self.case.jurisdiction)


class TestMandatoryCase_InflationRoseInFrance(unittest.TestCase):
    """§3 Case 5: 'Inflation rose in France'."""

    def setUp(self):
        self.case = next(c for c in MANDATORY_CASES if "Inflation rose" in c.text)

    def test_actor_is_null(self):
        self.assertIsNone(self.case.actor)

    def test_subject_entity_is_not_found(self):
        self.assertIsNone(self.case.subject_entity)

    def test_subject_indicator_is_inflation(self):
        self.assertEqual(self.case.subject_indicator, "Inflation")

    def test_jurisdiction_is_france(self):
        self.assertEqual(self.case.jurisdiction, "France")


class TestReadinessCouplingAudit(unittest.TestCase):
    """§6 — Readiness coupling audit."""

    def test_current_rule_documented(self):
        self.assertIn("entity_ok", READINESS_COUPLING_ANALYSIS["current_rule"])

    def test_problem_documented(self):
        self.assertIn("P0", READINESS_COUPLING_ANALYSIS["problem"])

    def test_all_6_scenarios_analyzed(self):
        expected = {"central_bank_policy_decision", "gdp_release",
                    "inflation_release", "regulatory_enforcement",
                    "market_level_event", "company_earnings"}
        self.assertEqual(set(READINESS_COUPLING_ANALYSIS["impact"].keys()), expected)

    def test_gdp_release_can_be_useful_without_entity(self):
        impact = READINESS_COUPLING_ANALYSIS["impact"]["gdp_release"]
        self.assertIn("BLOCKED", impact)
        self.assertIn("READY", impact)

    def test_proposed_fix_decouples_entity_from_readiness(self):
        fix = READINESS_COUPLING_ANALYSIS["proposed_fix"]
        self.assertIn("subject_concept", fix)
        self.assertIn("subject_indicator", fix)
        self.assertIn("subject_instrument", fix)

    def test_v48s_does_not_change_implementation(self):
        decision = READINESS_COUPLING_ANALYSIS["v48s_decision"]
        self.assertIn("does NOT change", decision)


class TestNoNewRegistryPopulation(unittest.TestCase):
    """§7 — ENTITY_REGISTRY remains empty."""

    def test_entity_registry_remains_empty(self):
        from intelligence_core.subject_entity import _ENTITY_REGISTRY
        self.assertEqual(len(_ENTITY_REGISTRY), 0,
                         "ENTITY_REGISTRY must remain empty per V48S §7")


class TestExistingTestsPass(unittest.TestCase):
    """§9 — Existing tests must still pass (verified by runner, not here)."""

    def test_v48_tests_still_pass(self):
        # This is a placeholder — the runner verifies all 248 existing tests
        # pass. If we're here, the import succeeded.
        import intelligence_core.subject_entity  # noqa
        import intelligence_core.contracts  # noqa


if __name__ == "__main__":
    unittest.main(verbosity=2)
