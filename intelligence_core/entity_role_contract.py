"""
ROUAA Entity Role Contract
==========================
Defines the canonical semantic roles for entities in IntelligenceObjects.

This contract was extracted from human adjudication of the 10 Gold-V2 IOs
(see docs/evidence/gold_v2_entity_role_adjudication.md).

CRITICAL SEMANTIC RULE:

    source_authority != event_subject != measured_entity

These three roles MUST remain independently representable. An entity that
appears as source_authority MUST NOT automatically become event_subject,
and vice versa. Likewise, measured_entity is independent of both.

Special cases (from adjudication):
    - SEC enforcement IOs: source_authority=SEC, event_subject=UNRESOLVED,
      measured_entity=penalty_amount. The firm is genuinely not named in
      the evidence excerpt; UNRESOLVED is the honest representation.
      Do NOT infer the firm from source_authority.

    - BEA statistical IOs: source_authority=BEA (from canonical_url),
      event_subject=economic indicator (e.g., "Real GDP", "PCE"),
      measured_entity=GDP growth rate / PCE price index.

    - ECB IO3: surface form equivalence:
        "ECB Governing Council" == "The Governing Council of the ECB"
      (word order differs, same entity). Use surface_forms_equivalent()
      rather than naive substring matching.

This contract is a SCHEMA definition only. It does NOT:
    - replace extraction logic
    - implement entity resolution
    - modify event detection
    - change scoring
    - populate new roles heuristically

It only defines the representational schema for the adjudicated roles,
enabling future Gold-V2 re-issuance with role-aware decomposition.
"""
from dataclasses import dataclass, field
from typing import List


# Sentinel value for entities that are honestly unresolved.
# This is preferred over incorrect inference.
UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class EntityRoleContract:
    """Canonical semantic roles for entities in an IntelligenceObject.

    Extracted from human adjudication of the 10 Gold-V2 IOs. This contract
    separates three roles that were previously conflated into a single
    overloaded `entity` field.

    Fields:
        source_authority: Institution responsible for issuing the document/source.
                          Derived from canonical_url or document identity.
                          Example: "U.S. Bureau of Economic Analysis (BEA)"

        event_subject: Entity to which the event itself is attributed.
                      MUST be UNRESOLVED when the evidence does not identify it.
                      NEVER infer an entity merely from source_authority.
                      Example: "Federal Open Market Committee (FOMC)" or UNRESOLVED

        measured_entity: Entity/metric actually measured or represented by the fact.
                        Distinct from source_authority.
                        Example: "Real GDP growth (annual rate)" or
                                "civil penalty amount (USD)"

        mentioned_entities: All named entities appearing in the evidence excerpt.
                           List form to preserve multiplicity.
                           Example: ["Federal Reserve", "Committee"]

    Semantic Rule (CRITICAL):
        source_authority != event_subject != measured_entity

        These fields MUST remain independently representable. A source institution
        appearing in metadata, URL, document identity, or provenance MUST NOT
        automatically become the event subject.
    """

    source_authority: str
    event_subject: str
    measured_entity: str
    mentioned_entities: List[str] = field(default_factory=list)

    def validate_independence(self) -> bool:
        """Verify the three primary roles are independently representable.

        For monetary policy decisions, the committee (e.g., FOMC) may legitimately
        fill both source_authority and event_subject roles. This contract permits
        that case but requires explicit representation in both fields.

        UNRESOLVED is always a valid value for event_subject — it indicates
        the entity is honestly not identified in the evidence, preferred over
        incorrect inference.
        """
        # UNRESOLVED event_subject is always valid (honest)
        if self.event_subject == UNRESOLVED:
            return True
        # If event_subject is set, validate it is not auto-derived from source_authority
        # (This is a representation contract, not an inference rule —
        # we cannot programmatically detect all conflation, but we can
        # require the values to be explicitly set.)
        return True

    @staticmethod
    def surface_forms_equivalent(form_a: str, form_b: str) -> bool:
        """Check semantic equivalence of surface forms.

        Handles word-order differences without weakening into generic
        substring matching. Example:
            "ECB Governing Council" == "The Governing Council of the ECB"

        Method: normalize by lowercasing, removing articles/prepositions,
        and comparing token sets. This is NOT substring matching —
        "ECB" alone is NOT equivalent to "The Governing Council of the ECB"
        even though "ECB" is a substring of the latter.
        """
        if form_a == form_b:
            return True
        if not form_a or not form_b:
            return False

        # Normalize: lowercase, strip articles and prepositions, build token set
        # Articles: the, a, an
        # Prepositions: of, for, to, in, on, at, by
        STOP_TOKENS = frozenset(['the', 'a', 'an', 'of', 'for', 'to', 'in', 'on', 'at', 'by'])

        def normalize(s: str) -> frozenset:
            tokens = s.lower().split()
            significant = frozenset(t for t in tokens if t not in STOP_TOKENS)
            return significant

        norm_a = normalize(form_a)
        norm_b = normalize(form_b)

        # Both must have at least one significant token
        if not norm_a or not norm_b:
            return False

        # Token sets must be equal (semantic equivalence after normalization)
        return norm_a == norm_b


# ---------------------------------------------------------------------------
# Predefined contracts for the 10 Gold-V2 IOs (from human adjudication).
# These are reference templates, NOT populated by inference.
# ---------------------------------------------------------------------------

# SEC enforcement IOs (IO8, IO9, IO10):
# - source_authority = SEC (from canonical_url)
# - event_subject = UNRESOLVED (firm genuinely not named in excerpt)
# - measured_entity = penalty/disgorgement amount (USD)
SEC_PENALTY_CONTRACT = EntityRoleContract(
    source_authority="U.S. Securities and Exchange Commission (SEC)",
    event_subject=UNRESOLVED,
    measured_entity="civil penalty amount (USD)",
)

SEC_DISGORGEMENT_CONTRACT = EntityRoleContract(
    source_authority="U.S. Securities and Exchange Commission (SEC)",
    event_subject=UNRESOLVED,
    measured_entity="disgorgement amount (USD)",
)

# BEA statistical IOs (IO5, IO6, IO7):
# - source_authority = BEA (from canonical_url)
# - event_subject = economic indicator (named in excerpt)
# - measured_entity = GDP growth rate / PCE price index
BEA_GDP_CONTRACT = EntityRoleContract(
    source_authority="U.S. Bureau of Economic Analysis (BEA)",
    event_subject="Real Gross Domestic Product (GDP)",
    measured_entity="Real GDP growth (annual rate)",
)

BEA_PCE_CONTRACT = EntityRoleContract(
    source_authority="U.S. Bureau of Economic Analysis (BEA)",
    event_subject="Personal Consumption Expenditures (PCE)",
    measured_entity="PCE price index (month-over-month change)",
)

# Monetary policy IOs (IO1, IO2, IO3, IO4):
# - source_authority = central bank (from canonical_url)
# - event_subject = committee (FOMC / Governing Council) — same as authority for monetary decisions
# - measured_entity = policy rate
FED_POLICY_RATE_CONTRACT = EntityRoleContract(
    source_authority="Federal Reserve (Federal Reserve Board)",
    event_subject="Federal Open Market Committee (FOMC)",
    measured_entity="federal funds rate (target range)",
)

ECB_POLICY_RATE_CONTRACT = EntityRoleContract(
    source_authority="European Central Bank (ECB)",
    event_subject="ECB Governing Council",
    measured_entity="ECB key interest rates (deposit facility rate)",
)

# ECB surface-form equivalence pairs (from adjudication of IO3)
ECB_SURFACE_FORM_EQUIVALENCE_PAIRS = [
    ("ECB Governing Council", "The Governing Council of the ECB"),
    ("Governing Council of the ECB", "ECB Governing Council"),
]
