"""V6 §3-4 — Event Context Requirements + Document-Level Semantic Gate.

Per directive §3-4:
  - Define explicit minimum contextual requirements for each Event Type
  - Implement document-level semantic gate: fact match → context validation → event semantic gate → event

This module provides:
  - EVENT_CONTEXT_REQUIREMENTS: per-event-type context rules
  - validate_event_context(): document-level semantic gate
  - should_create_event(): combined fact + context decision
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


# ── Event Context Requirements (V6 §3) ──

# For each event type, define what the DOCUMENT must contain for the event
# to be semantically valid. This is stronger than just pattern matching.

EVENT_CONTEXT_REQUIREMENTS = {
    "monetary_policy_decision": {
        "description": "Document must announce a monetary policy decision by a central bank",
        "required_patterns": [
            # Must contain monetary policy / interest rate decision language
            {
                "pattern": r"\b(monetary\s+policy|policy\s+rate|interest\s+rate|key\s+rate|"
                          r"base\s+rate|benchmark\s+rate|central\s+bank\s+rate)\b",
                "description": "monetary policy / interest rate context",
            },
            # Must contain decision/announcement language
            {
                "pattern": r"\b(decid(?:e|ed|ion)|announc(?:e|ed|ement)|statement\s+on|"
                          r"press\s+release|press\s+conference|policy\s+(?:meeting|committee))\b",
                "description": "decision/announcement language",
            },
        ],
        "all_required": True,  # ALL patterns must match
        "exclusion_patterns": [
            # Exclude if this is clearly a statistical release
            {
                "pattern": r"\b(gdp\s+(?:growth|estimate|advance|release)|"
                          r"economic\s+indicators?\s+(?:report|release)|"
                          r"statistical\s+release|cpi\s+(?:report|release)|"
                          r"employment\s+situation\s+report)\b",
                "description": "statistical release exclusion",
            },
        ],
    },

    "statistical_release": {
        "description": "Document must be a statistical publication by an official agency",
        "required_patterns": [
            # Must contain statistical publication language
            {
                "pattern": r"\b(statistic(?:s|al)?|data\s+(?:release|report)|index|indicator|"
                          r"survey|estimate|figure|table|chart)\b",
                "description": "statistical publication context",
            },
            # Must contain period/time reference
            {
                "pattern": r"\b(quarter|monthly|annual|year(?:\s+over\s+year)?|"
                          r"period|seasonally\s+adjusted|period[- ]over[- ]period)\b",
                "description": "time period reference",
            },
        ],
        "all_required": True,
        "exclusion_patterns": [],
    },

    "regulatory_enforcement": {
        "description": "Document must describe an actual regulatory enforcement action",
        "required_patterns": [
            # Must contain actual enforcement action language (not just "enforcement")
            {
                "pattern": r"\b(consent\s+order|cease\s+(?:-|\s+)and\s+(?:-|\s+)desist|"
                          r"injunction|penalty\s+(?:of|imposed|assessed)|"
                          r"disgorgement|settlement\s+(?:agreement|order)|"
                          r"fine\s+(?:of|imposed|assessed)|"
                          r"charged\s+with|sued\s+for|"
                          r"enforcement\s+(?:action|proceeding|order)|"
                          r"order\s+(?:to\s+cease|to\s+desist|of\s+prohibition))\b",
                "description": "actual enforcement action language",
            },
            # Must contain regulatory authority context
            {
                "pattern": r"\b(sec|cftc|fca|esma|consob|bafin|finra|"
                          r"regulator|regulatory|commission|authority|"
                          r"supervisory|enforcement\s+division|"
                          r"defendant|respondent|respondents)\b",
                "description": "regulatory authority context",
            },
        ],
        "all_required": True,
        "exclusion_patterns": [
            # Exclude if this is clearly a speech/op-ed (not an enforcement action)
            {
                "pattern": r"\b(op[- ]?ed|speech|testimony|remarks|keynote|"
                          r"commentary|opinion\s+piece|blog\s+post)\b",
                "description": "speech/op-ed exclusion",
            },
        ],
    },
}


def validate_event_context(event_type: str, document_text: str) -> tuple[bool, str]:
    """V6 §4 — Document-level semantic gate.

    Validates that the document has sufficient context for the event type.

    Returns:
      (is_valid, reason)
    """
    requirements = EVENT_CONTEXT_REQUIREMENTS.get(event_type)
    if not requirements:
        # No requirements defined — allow (backward compat)
        return True, "no requirements defined for this event type"

    text_lower = document_text.lower()

    # Check required patterns
    required_matches = 0
    for req in requirements["required_patterns"]:
        if re.search(req["pattern"], text_lower):
            required_matches += 1

    if requirements.get("all_required", True):
        if required_matches < len(requirements["required_patterns"]):
            matched = required_matches
            total = len(requirements["required_patterns"])
            return False, f"missing required context patterns ({matched}/{total} matched)"

    # Check exclusion patterns
    for excl in requirements.get("exclusion_patterns", []):
        if re.search(excl["pattern"], text_lower):
            return False, f"document matches exclusion pattern: {excl['description']}"

    return True, f"document has sufficient context ({required_matches}/{len(requirements['required_patterns'])} patterns matched)"


def should_create_event(event_type: str, facts: list, document_text: str) -> tuple[bool, str]:
    """Combined fact + context decision.

    The full pipeline:
      1. Fact extraction (patterns match → facts created)
      2. Context validation (document-level semantic check)
      3. Event semantic gate (should this fact become an event?)

    Returns:
      (should_create, reason)
    """
    if not facts:
        return False, "no facts to create event from"

    if not document_text:
        return False, "no document text to validate context"

    # Step 2: Context validation
    is_valid, reason = validate_event_context(event_type, document_text)
    if not is_valid:
        return False, f"context validation failed: {reason}"

    return True, f"event creation approved: {reason}"


def test_semantic_gate():
    """Test the semantic gate with known cases."""
    print(f"\n--- Testing Semantic Gate ---")

    # Test 1: BEA document (should NOT create monetary_policy_decision)
    bea_text = """
    U.S. Economy at a Glance. GDP (Advance Estimate), 2nd Quarter 2026.
    Real GDP increased 2.1 percent in the first quarter.
    Bureau of Economic Analysis (BEA). Statistical release.
    """
    valid, reason = validate_event_context("monetary_policy_decision", bea_text)
    print(f"  Test 1: BEA → monetary_policy_decision: {'VALID' if valid else 'REJECTED'}")
    print(f"    Reason: {reason}")
    assert not valid, "BEA document should not create monetary_policy_decision"
    print(f"    ✓ PASS (correctly rejected)")

    # Test 2: ECB press release (SHOULD create monetary_policy_decision)
    ecb_text = """
    ECB Monetary Policy Decision. The Governing Council today decided to
    raise the key ECB interest rates by 25 basis points. This decision
    follows the monetary policy meeting. Press release.
    """
    valid, reason = validate_event_context("monetary_policy_decision", ecb_text)
    print(f"\n  Test 2: ECB → monetary_policy_decision: {'VALID' if valid else 'REJECTED'}")
    print(f"    Reason: {reason}")
    assert valid, "ECB document should create monetary_policy_decision"
    print(f"    ✓ PASS (correctly accepted)")

    # Test 3: CFTC op-ed (should NOT create regulatory_enforcement)
    cftc_text = """
    The Economist Op-Ed. The New Era of Finance Needs Innovation More Than Consensus.
    Speech by Chairman. CFTC. Derivatives innovation.
    """
    valid, reason = validate_event_context("regulatory_enforcement", cftc_text)
    print(f"\n  Test 3: CFTC op-ed → regulatory_enforcement: {'VALID' if valid else 'REJECTED'}")
    print(f"    Reason: {reason}")
    assert not valid, "CFTC op-ed should not create regulatory_enforcement"
    print(f"    ✓ PASS (correctly rejected)")

    # Test 4: SEC enforcement action (SHOULD create regulatory_enforcement)
    sec_text = """
    SEC Charges XYZ Corporation with Fraud. The Securities and Exchange Commission
    today announced that XYZ Corporation has agreed to a consent order and will pay
    a penalty of $5 million to settle charges. The defendant agreed to cease and desist.
    """
    valid, reason = validate_event_context("regulatory_enforcement", sec_text)
    print(f"\n  Test 4: SEC enforcement → regulatory_enforcement: {'VALID' if valid else 'REJECTED'}")
    print(f"    Reason: {reason}")
    assert valid, "SEC enforcement document should create regulatory_enforcement"
    print(f"    ✓ PASS (correctly accepted)")

    # Test 5: BEA statistical release (SHOULD create statistical_release)
    bea_stat_text = """
    GDP and Personal Income. Bureau of Economic Analysis. Statistical release.
    Quarterly data. Real GDP increased at an annual rate of 2.1 percent in the
    first quarter of 2026. Seasonally adjusted annual rates.
    """
    valid, reason = validate_event_context("statistical_release", bea_stat_text)
    print(f"\n  Test 5: BEA → statistical_release: {'VALID' if valid else 'REJECTED'}")
    print(f"    Reason: {reason}")
    assert valid, "BEA document should create statistical_release"
    print(f"    ✓ PASS (correctly accepted)")

    print(f"\n  All semantic gate tests passed!")


if __name__ == "__main__":
    test_semantic_gate()
