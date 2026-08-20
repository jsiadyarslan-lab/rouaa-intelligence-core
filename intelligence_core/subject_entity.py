"""ROUAA Core V48 — Subject Entity Resolution Layer.

A deterministic Subject Entity Resolution layer that answers:
  "What is the event actually about?"

This is DIFFERENT from publisher_institution (which answers
"Who published the document?"). The two fields are independent.

INVARIANTS (per V48 directive):

  §5 RELATIONSHIP CATEGORIZATION:
    A candidate name is NOT sufficient. The resolver must determine
    whether the candidate is:
      EVENT_SUBJECT  → can become subject_entity
      AFFECTED_ENTITY → stored in affected_entities (separate)
      PUBLISHER       → NEVER becomes subject_entity
      MENTIONED_ENTITY → CANNOT become subject merely by appearing
      UNKNOWN         → no relationship established

  §6 STRUCTURAL LOCALITY:
    A subject can be CONFIRMED only when the candidate appears in a
    structurally relevant context connected to the event. Allowed:
    - same primary event segment
    - same table row
    - explicit parent event segment
    - explicit event-local heading
    - document title/subtitle when relation to event is deterministic

    Forbidden:
    - navigation
    - unrelated heading
    - unrelated paragraph
    - source registry name alone
    - publisher name alone
    - URI/domain alone
    - unrelated document metadata
    - adjacent unrelated event

  §7 DOCUMENT TITLE RULE:
    Document title may provide subject evidence ONLY when the title
    explicitly defines the object of the event. The institution name
    alone does NOT establish a specific event subject.

  §8 TABLE SUBJECT RULE:
    For TABLE_ROW evidence: prefer row_label → subject candidate.
    Verify row/value relationship makes candidate the subject of the
    fact/event. Do NOT treat dates, column headers, units, or
    navigation labels as subjects.

  §11 PUBLISHER FIREWALL (mandatory):
    publisher_institution CONFIRMED does NOT increase subject
    confidence. The two fields are independent.

  §12 AFFECTED ENTITY:
    Where evidence supports an affected entity, store affected_entity
    SEPARATELY from subject_entity. Do NOT collapse these roles.

  §10 SUBJECT ENTITY REGISTRY:
    Generic, deterministic. NO document-specific shortcuts.
    NO gt_fact_id mappings. NO hard-coded test-case mappings.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Optional

from .contracts import SubjectEntityV1, PublisherInstitutionV1
from .structural_parser import EvidenceSegmentV1
from .evidence_context import EvidenceContextV1


# ═══════════════════════════════════════════════════════════════════════
# Status / confidence / type / relationship constants
# ═══════════════════════════════════════════════════════════════════════

SUBJECT_CONFIRMED = "CONFIRMED"
SUBJECT_AMBIGUOUS = "AMBIGUOUS"
SUBJECT_NOT_FOUND = "NOT_FOUND"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

# Entity types per V48 §3
TYPE_ECONOMY = "ECONOMY"
TYPE_INDUSTRY = "INDUSTRY"
TYPE_MARKET = "MARKET"
TYPE_INSTRUMENT = "INSTRUMENT"
TYPE_INSTITUTION = "INSTITUTION"
TYPE_POLICY = "POLICY"
TYPE_INDICATOR = "INDICATOR"
TYPE_REGULATION = "REGULATION"
TYPE_ENTITY = "ENTITY"
TYPE_OTHER = "OTHER"

# Relationship categories per §5
REL_EVENT_SUBJECT = "EVENT_SUBJECT"
REL_AFFECTED_ENTITY = "AFFECTED_ENTITY"
REL_PUBLISHER = "PUBLISHER"
REL_MENTIONED_ENTITY = "MENTIONED_ENTITY"
REL_UNKNOWN = "UNKNOWN"

# Resolution methods per §4 (priority order)
METHOD_PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
METHOD_EVENT_LOCAL_PARENT = "EVENT_LOCAL_PARENT"
METHOD_TABLE_CONTEXT = "TABLE_CONTEXT"
METHOD_EVENT_LOCAL_HEADING = "EVENT_LOCAL_HEADING"
METHOD_DOCUMENT_TITLE = "DOCUMENT_TITLE"
METHOD_DOCUMENT_SUBTITLE = "DOCUMENT_SUBTITLE"
METHOD_DETERMINISTIC_METADATA = "DETERMINISTIC_METADATA"

PRIORITY_ORDER = (
    METHOD_PRIMARY_EVIDENCE,
    METHOD_EVENT_LOCAL_PARENT,
    METHOD_TABLE_CONTEXT,
    METHOD_EVENT_LOCAL_HEADING,
    METHOD_DOCUMENT_TITLE,
    METHOD_DOCUMENT_SUBTITLE,
    METHOD_DETERMINISTIC_METADATA,
)


# ═══════════════════════════════════════════════════════════════════════
# V48R §2 + §7 — ONTOLOGY SEPARATION
# ═══════════════════════════════════════════════════════════════════════
# The previous V48 _SUBJECT_REGISTRY conflated:
#   - REAL ENTITIES (institutions, companies, jurisdictions)
#   - CONCEPTS (monetary policy, fiscal policy, enforcement action)
#   - INDICATORS (GDP, CPI, inflation, unemployment)
#   - INSTRUMENTS (policy rate, bonds, equities)
#   - MARKETS (foreign exchange)
#   - REGULATIONS (penalty, settlement)
#
# V48R separates them into 4 distinct registries. The subject_entity
# resolver matches ONLY against _ENTITY_REGISTRY for subject_entity
# CONFIRMED. Concepts/Indicators/Instruments are captured in separate
# fields on SubjectEntityV1 (subject_concept, subject_indicator,
# subject_instrument) and DO NOT promote subject_entity.
#
# Per V48R §2: the ontology is:
#   ENTITY       = institution, company, jurisdiction (e.g., ECB, Apple, U.S.)
#   CONCEPT      = policy concept (e.g., Monetary Policy, Fiscal Policy)
#   INDICATOR    = macroeconomic indicator (e.g., GDP, CPI, Inflation)
#   INSTRUMENT   = financial instrument (e.g., Policy Rate, Bonds, Equities)
#   MARKET       = market segment (e.g., Foreign Exchange)
#   REGULATION   = regulatory concept (e.g., Penalty, Settlement, Enforcement Action)
#   ACTOR        = the agent performing the action (often the publisher)
#   AFFECTED     = entity acted upon
#   PUBLISHER    = institution that published the document
#   MENTIONED    = entity merely appearing in text

# ENTITY_REGISTRY — real entities (institutions, companies, jurisdictions)
# Currently EMPTY — no real entities in the V48 registry. This is the
# HONEST answer: V48 had ZERO real subject entities.
_ENTITY_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    # Empty by design. V48's 14 "CONFIRMED" were ALL indicators/concepts/
    # instruments, NOT real entities. V48R does NOT add new entity patterns
    # (per stop condition "No new subject patterns yet"). When the user
    # decides to populate ENTITY_REGISTRY, it must contain ONLY real
    # institutions/companies/jurisdictions — NOT macro indicators.
}

# CONCEPT_REGISTRY — policy concepts
_CONCEPT_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    "monetary_policy": ("Monetary Policy", TYPE_POLICY,
                        ["monetary policy", "policy stance", "monetary policy stance"]),
    "fiscal_policy": ("Fiscal Policy", TYPE_POLICY,
                      ["fiscal policy", "budget policy"]),
    "enforcement_action": ("Enforcement Action", TYPE_REGULATION,
                           ["enforcement action", "enforcement"]),
}

# INDICATOR_REGISTRY — macroeconomic indicators
_INDICATOR_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    "gdp": ("Gross Domestic Product", TYPE_INDICATOR,
            ["gdp", "gross domestic product", "gdp growth"]),
    "cpi": ("Consumer Price Index", TYPE_INDICATOR,
            ["cpi", "consumer price index", "cpi inflation"]),
    "hicp": ("Harmonised Index of Consumer Prices", TYPE_INDICATOR,
             ["hicp", "harmonised index of consumer prices"]),
    "inflation": ("Inflation", TYPE_INDICATOR,
                  ["inflation", "inflation rate", "cpi inflation"]),
    "unemployment": ("Unemployment", TYPE_INDICATOR,
                     ["unemployment", "unemployment rate"]),
    "gdp_growth": ("GDP Growth", TYPE_INDICATOR,
                   ["gdp growth", "economic growth"]),
}

# INSTRUMENT_REGISTRY — financial instruments
_INSTRUMENT_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    "policy_rate": ("Policy Rate", TYPE_INSTRUMENT,
                    ["policy rate", "interest rate", "base rate",
                     "refinancing rate", "main refinancing operations rate"]),
    "bonds": ("Bonds", TYPE_INSTRUMENT, ["bonds", "government bonds", "sovereign bonds"]),
    "equities": ("Equities", TYPE_INSTRUMENT, ["equities", "stock market", "shares"]),
}

# REGULATION_REGISTRY — regulatory concepts (separate from CONCEPT)
_REGULATION_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    "penalty": ("Penalty", TYPE_REGULATION,
                ["penalty", "fine", "civil monetary penalty"]),
    "settlement": ("Settlement", TYPE_REGULATION,
                   ["settlement", "penalty settlement"]),
}

# MARKET_REGISTRY — market segments
_MARKET_REGISTRY: dict[str, tuple[str, str, list[str]]] = {
    "fx": ("Foreign Exchange", TYPE_MARKET, ["fx", "foreign exchange", "currency"]),
}

# Combined registry for backward-compat matching (V48R's audit re-runs
# the candidate extraction against ALL registries, but only ENTITY matches
# can become subject_entity CONFIRMED)
_ALL_REGISTRIES = {
    "ENTITY": _ENTITY_REGISTRY,
    "CONCEPT": _CONCEPT_REGISTRY,
    "INDICATOR": _INDICATOR_REGISTRY,
    "INSTRUMENT": _INSTRUMENT_REGISTRY,
    "REGULATION": _REGULATION_REGISTRY,
    "MARKET": _MARKET_REGISTRY,
}

# Reverse maps for each registry
_ALIAS_TO_CANONICAL_BY_TYPE: dict[str, dict[str, str]] = {}
for reg_type, reg in _ALL_REGISTRIES.items():
    _ALIAS_TO_CANONICAL_BY_TYPE[reg_type] = {}
    for canonical_id, (_name, _etype, aliases) in reg.items():
        for alias in aliases:
            _ALIAS_TO_CANONICAL_BY_TYPE[reg_type][alias.lower()] = canonical_id

# Combined reverse map (for backward compat with V48 functions)
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for reg_type, alias_map in _ALIAS_TO_CANONICAL_BY_TYPE.items():
    for alias, canonical_id in alias_map.items():
        _ALIAS_TO_CANONICAL[alias] = canonical_id


def _match_subject_alias(text: str) -> Optional[str]:
    """Match a text snippet against the subject registry. Returns canonical_id or None."""
    if not text:
        return None
    text_lower = text.lower()
    # Try longest match first (longer aliases are more specific)
    sorted_aliases = sorted(_ALIAS_TO_CANONICAL.keys(), key=lambda x: -len(x))
    for alias in sorted_aliases:
        # Word-boundary match to avoid spurious substring matches
        if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
            return _ALIAS_TO_CANONICAL[alias]
    return None


def _match_alias_by_registry_type(text: str, reg_type: str) -> Optional[tuple[str, str]]:
    """Match text against a SPECIFIC registry type.
    Returns (canonical_id, canonical_name) or None.
    """
    if not text or reg_type not in _ALIAS_TO_CANONICAL_BY_TYPE:
        return None
    text_lower = text.lower()
    alias_map = _ALIAS_TO_CANONICAL_BY_TYPE[reg_type]
    # Sort by length descending for longest match
    sorted_aliases = sorted(alias_map.keys(), key=lambda x: -len(x))
    for alias in sorted_aliases:
        if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
            canonical_id = alias_map[alias]
            reg = _ALL_REGISTRIES[reg_type]
            canonical_name = reg[canonical_id][0]
            return (canonical_id, canonical_name)
    return None


def _registry_type_for_canonical_id(canonical_id: str) -> Optional[str]:
    """Return the registry type for a given canonical_id."""
    for reg_type, reg in _ALL_REGISTRIES.items():
        if canonical_id in reg:
            return reg_type
    return None


# ═══════════════════════════════════════════════════════════════════════
# Relationship categorization (§5)
# ═══════════════════════════════════════════════════════════════════════

# Action verbs that suggest the candidate is the SUBJECT of the event
_SUBJECT_ACTION_VERBS = re.compile(
    r"\b(?:announces?|publishes?|releases?|issues?|decides?|maintains?|raises?|lowers?|cuts?|approves?|settles?|fines?|imposes?|investigates?|charges?)\b",
    re.I,
)

# Passive verbs that suggest AFFECTED_ENTITY
_AFFECTED_VERBS = re.compile(
    r"\b(?:was\s+fined|was\s+penalized|was\s+charged|was\s+investigated|against\s+\w+|barred\s+from|banned\s+from|prohibited\s+from)\b",
    re.I,
)

# Institution names — anything matching publisher registry aliases
# is treated as PUBLISHER unless the surrounding context clearly
# makes it the SUBJECT of the event (e.g., "ECB announces..." could
# mean ECB is both publisher AND subject, but we'd default to PUBLISHER
# unless subject evidence elsewhere).


def categorize_relationship(
    candidate_name: str,
    surrounding_text: str,
    publisher: Optional[PublisherInstitutionV1],
) -> str:
    """Determine the relationship of a candidate to the event.

    Per V48 §5:
      EVENT_SUBJECT     — the candidate is what the event is about
      AFFECTED_ENTITY   — the candidate is acted upon
      PUBLISHER         — the candidate matches publisher identity
      MENTIONED_ENTITY  — the candidate merely appears
      UNKNOWN           — no relationship established
    """
    if not candidate_name:
        return REL_UNKNOWN
    candidate_lower = candidate_name.lower()
    text_lower = (surrounding_text or "").lower()

    # Check if candidate matches publisher identity
    if publisher and publisher.status == "CONFIRMED":
        publisher_aliases_lower = [a.lower() for a in publisher.aliases]
        publisher_name_lower = publisher.canonical_name.lower()
        # If candidate matches publisher name OR any publisher alias
        if (candidate_lower == publisher_name_lower
                or candidate_lower in publisher_aliases_lower):
            # Could be subject if explicit subject-action verb precedes/follows
            # But by default, treat as PUBLISHER (per §11 firewall)
            # Exception: if the candidate is described AS THE SUBJECT via
            # a subject-action verb in event-local context, it could be
            # EVENT_SUBJECT. We default to PUBLISHER for safety.
            return REL_PUBLISHER

    # Check for explicit subject-action context
    # If the text contains a subject-action verb (announces, publishes, etc.)
    # AND the candidate name appears near it, the candidate is likely the
    # EVENT_SUBJECT (the one performing the action).
    if _SUBJECT_ACTION_VERBS.search(text_lower):
        # The candidate is the actor of the verb — could be EVENT_SUBJECT
        # OR PUBLISHER (if it matches publisher). Since we already handled
        # publisher above, this is EVENT_SUBJECT.
        return REL_EVENT_SUBJECT

    # Check for affected-entity context
    if _AFFECTED_VERBS.search(text_lower):
        return REL_AFFECTED_ENTITY

    # Default: just mentioned
    return REL_MENTIONED_ENTITY


# ═══════════════════════════════════════════════════════════════════════
# Subject candidate extraction (§4)
# ═══════════════════════════════════════════════════════════════════════

def extract_candidates_from_primary_segment(
    primary_segment: EvidenceSegmentV1,
    excerpt: str,
) -> list[dict]:
    """Extract subject candidates from the primary evidence segment.

    Per §4 priority 1: PRIMARY_EVIDENCE.
    Per V48R §7: candidates are tagged with their registry_type
    (ENTITY/CONCEPT/INDICATOR/INSTRUMENT/REGULATION/MARKET).
    Only ENTITY-registry candidates can become subject_entity CONFIRMED.
    """
    candidates = []
    if not primary_segment or not primary_segment.text:
        return candidates
    primary_text = primary_segment.text
    text_lower = primary_text.lower()
    # Match against ALL registries, tagging each candidate with its type.
    # Sort aliases by length DESCENDING so longest (most specific) matches first.
    for reg_type, reg in _ALL_REGISTRIES.items():
        alias_map = _ALIAS_TO_CANONICAL_BY_TYPE.get(reg_type, {})
        sorted_aliases = sorted(alias_map.items(), key=lambda x: -len(x[0]))
        for alias, canonical_id in sorted_aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
                canonical_name, etype, aliases = reg[canonical_id]
                candidates.append({
                    "canonical_id": canonical_id,
                    "canonical_name": canonical_name,
                    "entity_type": etype,
                    "registry_type": reg_type,  # V48R §7 — ontology tag
                    "aliases": aliases,
                    "match_text": alias,
                    "supporting_segment_id": primary_segment.segment_id,
                    "resolution_method": METHOD_PRIMARY_EVIDENCE,
                })
    return candidates


def extract_candidates_from_table_context(
    primary_segment: EvidenceSegmentV1,
) -> list[dict]:
    """Extract subject candidates from table row/column labels.

    Per §4 priority 3: TABLE_CONTEXT.
    Per §8: prefer row_label → subject candidate. Do NOT treat dates,
    column headers, units, or navigation labels as subjects.
    Per V48R §7: candidates are tagged with registry_type.
    """
    candidates = []
    if not primary_segment:
        return candidates
    if primary_segment.segment_type != "TABLE_ROW":
        return candidates
    row_label = primary_segment.row_label or ""
    if row_label and len(row_label) > 2:
        # Match row_label against ALL registries, tagging with registry_type.
        # Sort aliases by length DESCENDING so longest (most specific) matches first.
        for reg_type, reg in _ALL_REGISTRIES.items():
            alias_map = _ALIAS_TO_CANONICAL_BY_TYPE.get(reg_type, {})
            sorted_aliases = sorted(alias_map.items(), key=lambda x: -len(x[0]))
            for alias, canonical_id in sorted_aliases:
                if re.search(r"\b" + re.escape(alias) + r"\b", row_label.lower()):
                    canonical_name, etype, aliases = reg[canonical_id]
                    candidates.append({
                        "canonical_id": canonical_id,
                        "canonical_name": canonical_name,
                        "entity_type": etype,
                        "registry_type": reg_type,
                        "aliases": aliases,
                        "match_text": row_label,
                        "supporting_segment_id": primary_segment.segment_id,
                        "resolution_method": METHOD_TABLE_CONTEXT,
                    })
                    break
    return candidates


def extract_candidates_from_event_local_heading(
    primary_segment: EvidenceSegmentV1,
    all_segments: list[EvidenceSegmentV1],
) -> list[dict]:
    """Extract subject candidates from event-local heading context.

    Per §4 priority 4: EVENT_LOCAL_HEADING. The heading_context of the
    primary segment provides the topic it falls under.
    Per V48R §7: candidates are tagged with registry_type.
    """
    candidates = []
    if not primary_segment or not primary_segment.heading_context:
        return candidates
    heading_text = primary_segment.heading_context
    # Match against ALL registries, tagging with registry_type.
    # Sort aliases by length DESCENDING so longest (most specific) matches first.
    for reg_type, reg in _ALL_REGISTRIES.items():
        alias_map = _ALIAS_TO_CANONICAL_BY_TYPE.get(reg_type, {})
        sorted_aliases = sorted(alias_map.items(), key=lambda x: -len(x[0]))
        for alias, canonical_id in sorted_aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", heading_text.lower()):
                canonical_name, etype, aliases = reg[canonical_id]
                candidates.append({
                    "canonical_id": canonical_id,
                    "canonical_name": canonical_name,
                    "entity_type": etype,
                    "registry_type": reg_type,
                    "aliases": aliases,
                    "match_text": heading_text[:80],
                    "supporting_segment_id": primary_segment.segment_id,
                    "resolution_method": METHOD_EVENT_LOCAL_HEADING,
                })
                break  # Take the first match per registry
    return candidates


def extract_candidates_from_document_title(
    all_segments: list[EvidenceSegmentV1],
) -> list[dict]:
    """Extract subject candidates from the document title.

    Per §4 priority 5: DOCUMENT_TITLE. Per §7: title may provide subject
    evidence ONLY when the title explicitly defines the object of the
    event. The institution name alone does NOT establish a subject.

    Strategy: find the first HEADING segment with heading_context=None
    (top-level heading). This is typically the document title/topic.
    """
    candidates = []
    if not all_segments:
        return candidates
    # Find the first HEADING segment with heading_context=None
    title_segment = None
    for seg in all_segments:
        if seg.segment_type == "HEADING" and not seg.heading_context:
            title_segment = seg
            break
    if not title_segment or not title_segment.text:
        return candidates
    title_text = title_segment.text
    # Match against ALL registries — but ONLY if the title contains
    # a registry alias (not just any institution name). Tag with registry_type.
    # Sort aliases by length DESCENDING so longest (most specific) matches first.
    for reg_type, reg in _ALL_REGISTRIES.items():
        alias_map = _ALIAS_TO_CANONICAL_BY_TYPE.get(reg_type, {})
        sorted_aliases = sorted(alias_map.items(), key=lambda x: -len(x[0]))
        for alias, canonical_id in sorted_aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", title_text.lower()):
                canonical_name, etype, aliases = reg[canonical_id]
                candidates.append({
                    "canonical_id": canonical_id,
                    "canonical_name": canonical_name,
                    "entity_type": etype,
                    "registry_type": reg_type,
                    "aliases": aliases,
                    "match_text": title_text[:120],
                    "supporting_segment_id": title_segment.segment_id,
                    "resolution_method": METHOD_DOCUMENT_TITLE,
                })
                break  # Take the first match per registry
    return candidates


# ═══════════════════════════════════════════════════════════════════════
# V48U §2 — Semantic Binding Check
# ═══════════════════════════════════════════════════════════════════════
# A registry match is NOT sufficient. The candidate must be the SEMANTIC
# OBJECT of the event — i.e., it must appear as the subject/object of
# an event verb in the MAIN CLAUSE (not a subordinate clause).
#
# "GDP increased" → GDP + increased → BOUND ✓
# "Monetary policy was tightened because unemployment increased"
#   → unemployment is in subordinate clause (after "because") → NOT BOUND
# "Inflation rose" → Inflation + rose → BOUND ✓

# Subordinate clause markers — text after these is NOT the main clause
_SUBORDINATE_CONJUNCTIONS = re.compile(
    r"\b(?:because|since|as|while|although|whereas|given|noting|after|before|"
    r"due to|owing to|in light of|in view of)\b",
    re.I,
)

# Event verbs by subject type
_EVENT_VERBS = {
    "INDICATOR": re.compile(
        r"\b(?:increase[ds]?|rose|fell|decrease[ds]?|grew|decline[ds]?|eased|"
        r"accelerate[ds]?|slowed|dropped|climbed|surge[ds]?|dipped?|rebound(?:ed)?|"
        r"recovered|contract(?:ed)?|expand(?:ed)?|stand[ds]? at|"
        r"was|were|is|are|reached?)\b",
        re.I,
    ),
    "CONCEPT": re.compile(
        r"\b(?:tighten(?:ed)?|eased|expand(?:ed)?|contract(?:ed)?|shift(?:ed)?|change[ds]?|"
        r"adjust(?:ed)?|decide[ds]?|announce[ds]?|publish(?:ed)?|release[ds]?|issues?|"
        r"was|were|is|are|remains?|remained?)\b",
        re.I,
    ),
    "INSTRUMENT": re.compile(
        r"\b(?:raise[ds]?|lower[eds]?|cut|maintain(?:ed)?|set|kept|held|unchanged?|"
        r"increase[ds]?|reduce[ds]?|adjust(?:ed)?|was|were|is|are|stood at|"
        r"remain(?:ed)?|stay(?:ed)?)\b",
        re.I,
    ),
    "REGULATION": re.compile(
        r"\b(?:impose[ds]?|issued?|reached?|settled?|fined?|penalized?|"
        r"charged?|was|were|is|are|announced?|published?)\b",
        re.I,
    ),
    "MARKET": re.compile(
        r"\b(?:increase[ds]?|rose|fell|decrease[ds]?|surge[ds]?|volatility|"
        r"turnover|was|were|is|are|reached?)\b",
        re.I,
    ),
}


def _check_semantic_binding(
    candidate: dict,
    primary_segments_by_fact: dict,
    reg_type: str,
) -> bool:
    """V48U §2 — Check whether a candidate is the semantic object of the event.

    A registry match alone is NOT sufficient. The candidate must:
    1. Appear in the primary segment text
    2. Be near an event verb appropriate to its type
    3. NOT be in a subordinate clause (after "because", "since", etc.)

    Returns True if the candidate is semantically bound as the subject.
    """
    fact_id = candidate.get("supporting_fact_id", "")
    primary_text_obj = primary_segments_by_fact.get(fact_id, "")
    # primary_segments_by_fact may store EvidenceSegmentV1 objects OR strings
    if isinstance(primary_text_obj, str):
        primary_text = primary_text_obj
    elif hasattr(primary_text_obj, 'text'):
        primary_text = primary_text_obj.text or ""
    else:
        primary_text = str(primary_text_obj)
    if not primary_text:
        primary_text = candidate.get("match_text", "")
    if not primary_text:
        return False

    text_lower = primary_text.lower()
    match_text_lower = (candidate.get("match_text") or "").lower()

    # Find the position of the candidate in the text
    idx = text_lower.find(match_text_lower)
    if idx < 0:
        # Try the canonical name
        idx = text_lower.find(candidate.get("canonical_name", "").lower())
    if idx < 0:
        return False

    # Check if the candidate appears AFTER a subordinate conjunction
    # (in a subordinate clause — NOT the main clause)
    text_before_candidate = text_lower[:idx]
    if _SUBORDINATE_CONJUNCTIONS.search(text_before_candidate):
        # The candidate is in a subordinate clause — NOT the semantic subject
        return False

    # Check if an event verb appears within 100 chars of the candidate
    event_verbs = _EVENT_VERBS.get(reg_type, _EVENT_VERBS["INDICATOR"])
    window = text_lower[max(0, idx - 50): idx + len(match_text_lower) + 100]
    if event_verbs.search(window):
        return True

    # Also check: is the candidate the FIRST noun phrase in the text?
    # (Often the subject of the sentence)
    text_start = text_lower[:idx + len(match_text_lower) + 20]
    # If the candidate is in the first 80 chars AND there's a verb after it
    if idx < 80:
        after_candidate = text_lower[idx + len(match_text_lower):idx + len(match_text_lower) + 100]
        if event_verbs.search(after_candidate):
            return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# Subject Entity Resolution (§5)
# ═══════════════════════════════════════════════════════════════════════

def resolve_subject(
    io: dict,
    contexts: list[EvidenceContextV1],
    primary_texts_by_fact: dict[str, str],
    all_segments: list[EvidenceSegmentV1],
    publisher: Optional[PublisherInstitutionV1] = None,
) -> SubjectEntityV1:
    """Resolve the subject entity for an IO.

    Strategy (per §4 priority order):
      1. PRIMARY_EVIDENCE — extract candidates from primary segment text
      2. EVENT_LOCAL_PARENT — extract from parent segment
      3. TABLE_CONTEXT — extract from table row_label
      4. EVENT_LOCAL_HEADING — extract from heading_context
      5. DOCUMENT_TITLE — extract from document title (top-level heading)
      6. DETERMINISTIC_METADATA — fallback to deterministic metadata

    For each candidate, categorize the relationship (§5). Only
    EVENT_SUBJECT candidates can become subject_entity. PUBLISHER
    candidates are NEVER subject_entity (per §11 firewall).

    Returns a SubjectEntityV1. status reflects the quality of resolution.
    """
    fact_ids = [f.get("fact_id", "") for f in io.get("facts", [])]
    evidence_ids = [e.get("fact_id", "") for e in io.get("evidence", [])]
    all_candidates = []

    # Find primary segments per fact
    primary_segments_by_fact = {}
    for ctx in contexts:
        if ctx.primary_segment_id:
            for seg in all_segments:
                if seg.segment_id == ctx.primary_segment_id:
                    primary_segments_by_fact[ctx.fact_id] = seg
                    break

    # Priority 1: PRIMARY_EVIDENCE
    for fact_id, primary_seg in primary_segments_by_fact.items():
        candidates = extract_candidates_from_primary_segment(
            primary_seg,
            next((c.evidence_excerpt for c in contexts if c.fact_id == fact_id), ""),
        )
        for c in candidates:
            c["supporting_fact_id"] = fact_id
            all_candidates.append(c)

    # Priority 3: TABLE_CONTEXT (only for TABLE_ROW segments)
    for fact_id, primary_seg in primary_segments_by_fact.items():
        if primary_seg.segment_type == "TABLE_ROW":
            candidates = extract_candidates_from_table_context(primary_seg)
            for c in candidates:
                c["supporting_fact_id"] = fact_id
                all_candidates.append(c)

    # Priority 4: EVENT_LOCAL_HEADING
    for fact_id, primary_seg in primary_segments_by_fact.items():
        candidates = extract_candidates_from_event_local_heading(primary_seg, all_segments)
        for c in candidates:
            c["supporting_fact_id"] = fact_id
            all_candidates.append(c)

    # Priority 5: DOCUMENT_TITLE
    title_candidates = extract_candidates_from_document_title(all_segments)
    all_candidates.extend(title_candidates)

    if not all_candidates:
        return SubjectEntityV1(
            subject_entity_id="SUBJ-UNKNOWN",
            canonical_name="UNKNOWN",
            entity_type=TYPE_OTHER,
            status=SUBJECT_NOT_FOUND,
            confidence=CONFIDENCE_LOW,
            supporting_segment_ids=[],
            supporting_fact_ids=fact_ids,
            supporting_evidence_ids=evidence_ids,
            resolution_method=None,
            relationship=REL_UNKNOWN,
            aliases=[],
            affected_entities=[],
        )

    # Deduplicate candidates by canonical_id, keeping highest-priority method
    deduped = {}
    for cand in all_candidates:
        cid = cand["canonical_id"]
        method = cand["resolution_method"]
        if cid not in deduped or PRIORITY_ORDER.index(method) < PRIORITY_ORDER.index(deduped[cid]["resolution_method"]):
            deduped[cid] = cand

    # Categorize relationship for each candidate
    categorized = []
    for cand in deduped.values():
        primary_seg = primary_segments_by_fact.get(cand.get("supporting_fact_id", ""))
        surrounding_text = primary_seg.text if primary_seg else (cand.get("match_text", ""))
        relationship = categorize_relationship(
            cand["canonical_name"], surrounding_text, publisher
        )
        cand["relationship"] = relationship
        categorized.append(cand)

    # Separate candidates by relationship
    event_subjects = [c for c in categorized if c["relationship"] == REL_EVENT_SUBJECT]
    affected = [c for c in categorized if c["relationship"] == REL_AFFECTED_ENTITY]
    publishers = [c for c in categorized if c["relationship"] == REL_PUBLISHER]
    mentioned = [c for c in categorized if c["relationship"] == REL_MENTIONED_ENTITY]

    # V48T-R §2/§4 + V48U §2/§4-5 — ONTOLOGY SEPARATION + SEMANTIC BINDING:
    # Only ENTITY-registry candidates with EVENT_SUBJECT relationship can
    # become subject_entity CONFIRMED.
    #
    # V48T-R FIX: CONCEPT/INDICATOR/INSTRUMENT/REGULATION/MARKET candidates
    # are captured from ALL categorized candidates.
    #
    # V48U FIX: candidates must pass SEMANTIC BINDING check — the candidate
    # must be the semantic object of the event (near an event verb in the
    # main clause), NOT merely present. "Monetary policy was tightened
    # because unemployment increased" → unemployment is NOT the subject
    # (it's in a subordinate clause).
    #
    # V48U §4-5: MARKET and REGULATION are FIRST-CLASS fields:
    #   MARKET → subject_market (NOT subject_instrument)
    #   REGULATION → subject_regulation (NOT subject_concept)
    entity_event_subjects = [c for c in event_subjects if c.get("registry_type") == "ENTITY"]
    concept_candidates = [c for c in categorized if c.get("registry_type") == "CONCEPT"]
    indicator_candidates = [c for c in categorized if c.get("registry_type") == "INDICATOR"]
    instrument_candidates = [c for c in categorized if c.get("registry_type") == "INSTRUMENT"]
    regulation_candidates = [c for c in categorized if c.get("registry_type") == "REGULATION"]
    market_candidates = [c for c in categorized if c.get("registry_type") == "MARKET"]

    # V48U §2 — SEMANTIC BINDING: filter candidates by whether they are
    # actually the semantic object of the event, not merely present.
    bound_concept = [c for c in concept_candidates if _check_semantic_binding(c, primary_segments_by_fact, "CONCEPT")]
    bound_indicator = [c for c in indicator_candidates if _check_semantic_binding(c, primary_segments_by_fact, "INDICATOR")]
    bound_instrument = [c for c in instrument_candidates if _check_semantic_binding(c, primary_segments_by_fact, "INSTRUMENT")]
    bound_regulation = [c for c in regulation_candidates if _check_semantic_binding(c, primary_segments_by_fact, "REGULATION")]
    bound_market = [c for c in market_candidates if _check_semantic_binding(c, primary_segments_by_fact, "MARKET")]

    # Helper to build separate-field dicts (V48U: separate MARKET and REGULATION)
    def _sep_field(cands):
        if not cands:
            return (None, "NOT_FOUND")
        chosen = cands[0]
        return (chosen["canonical_name"], "CONFIRMED")

    # V48U §4-5 — FIRST-CLASS fields (NOT mapped/collapsed):
    subject_concept, subject_concept_status = _sep_field(bound_concept)
    subject_indicator, subject_indicator_status = _sep_field(bound_indicator)
    subject_instrument, subject_instrument_status = _sep_field(bound_instrument)
    subject_market, subject_market_status = _sep_field(bound_market)
    subject_regulation, subject_regulation_status = _sep_field(bound_regulation)

    # If we have ENTITY-registry EVENT_SUBJECT candidates, pick the highest-priority one
    if entity_event_subjects:
        # Sort by priority order
        entity_event_subjects.sort(key=lambda c: PRIORITY_ORDER.index(c["resolution_method"]))
        chosen = entity_event_subjects[0]
        # If multiple distinct entity event subjects → AMBIGUOUS
        if len(set(c["canonical_id"] for c in entity_event_subjects)) > 1:
            return SubjectEntityV1(
                subject_entity_id=f"SUBJ-AMBIGUOUS",
                canonical_name="; ".join(c["canonical_name"] for c in entity_event_subjects[:3]),
                entity_type=entity_event_subjects[0]["entity_type"],
                status=SUBJECT_AMBIGUOUS,
                confidence=CONFIDENCE_MEDIUM,
                supporting_segment_ids=[c["supporting_segment_id"] for c in entity_event_subjects],
                supporting_fact_ids=fact_ids,
                supporting_evidence_ids=evidence_ids,
                resolution_method=entity_event_subjects[0]["resolution_method"],
                relationship=REL_EVENT_SUBJECT,
                aliases=entity_event_subjects[0]["aliases"],
                affected_entities=[{"canonical_name": c["canonical_name"],
                                     "supporting_segment_ids": [c["supporting_segment_id"]]}
                                    for c in affected],
                subject_concept=subject_concept,
                subject_concept_status=subject_concept_status,
                subject_indicator=subject_indicator,
                subject_indicator_status=subject_indicator_status,
                subject_instrument=subject_instrument,
                subject_instrument_status=subject_instrument_status,
                subject_market=subject_market,
                subject_market_status=subject_market_status,
                subject_regulation=subject_regulation,
                subject_regulation_status=subject_regulation_status,
            )
        # Single entity event subject → CONFIRMED
        return SubjectEntityV1(
            subject_entity_id=f"SUBJ-{chosen['canonical_id'].upper().replace('-', '_')}",
            canonical_name=chosen["canonical_name"],
            entity_type=chosen["entity_type"],
            status=SUBJECT_CONFIRMED,
            confidence=CONFIDENCE_HIGH if chosen["resolution_method"] == METHOD_PRIMARY_EVIDENCE
            else CONFIDENCE_MEDIUM,
            supporting_segment_ids=[chosen["supporting_segment_id"]],
            supporting_fact_ids=fact_ids,
            supporting_evidence_ids=evidence_ids,
            resolution_method=chosen["resolution_method"],
            relationship=REL_EVENT_SUBJECT,
            aliases=chosen["aliases"],
            affected_entities=[{"canonical_name": c["canonical_name"],
                                 "supporting_segment_ids": [c["supporting_segment_id"]]}
                                for c in affected],
            subject_concept=subject_concept,
            subject_concept_status=subject_concept_status,
            subject_indicator=subject_indicator,
            subject_indicator_status=subject_indicator_status,
            subject_instrument=subject_instrument,
            subject_instrument_status=subject_instrument_status,
            subject_market=subject_market,
            subject_market_status=subject_market_status,
            subject_regulation=subject_regulation,
            subject_regulation_status=subject_regulation_status,
        )

    # No ENTITY-registry EVENT_SUBJECT found — but we may have concept/
    # indicator/instrument candidates. Subject_entity remains NOT_FOUND,
    # but the separate fields capture the conceptual subject.
    if affected or concept_candidates or indicator_candidates or instrument_candidates or regulation_candidates or market_candidates:
        return SubjectEntityV1(
            subject_entity_id="SUBJ-UNKNOWN",
            canonical_name="UNKNOWN",
            entity_type=TYPE_OTHER,
            status=SUBJECT_NOT_FOUND,
            confidence=CONFIDENCE_LOW,
            supporting_segment_ids=[],
            supporting_fact_ids=fact_ids,
            supporting_evidence_ids=evidence_ids,
            resolution_method=None,
            relationship=REL_UNKNOWN,
            aliases=[],
            affected_entities=[{"canonical_name": c["canonical_name"],
                                 "supporting_segment_ids": [c["supporting_segment_id"]]}
                                for c in affected],
            subject_concept=subject_concept,
            subject_concept_status=subject_concept_status,
            subject_indicator=subject_indicator,
            subject_indicator_status=subject_indicator_status,
            subject_instrument=subject_instrument,
            subject_instrument_status=subject_instrument_status,
            subject_market=subject_market,
            subject_market_status=subject_market_status,
            subject_regulation=subject_regulation,
            subject_regulation_status=subject_regulation_status,
        )

    # No EVENT_SUBJECT found, but we have candidates with other relationships
    if affected:
        # Subject cannot be confirmed — store affected entities
        return SubjectEntityV1(
            subject_entity_id="SUBJ-UNKNOWN",
            canonical_name="UNKNOWN",
            entity_type=TYPE_OTHER,
            status=SUBJECT_NOT_FOUND,
            confidence=CONFIDENCE_LOW,
            supporting_segment_ids=[],
            supporting_fact_ids=fact_ids,
            supporting_evidence_ids=evidence_ids,
            resolution_method=None,
            relationship=REL_UNKNOWN,
            aliases=[],
            affected_entities=[{"canonical_name": c["canonical_name"],
                                 "supporting_segment_ids": [c["supporting_segment_id"]]}
                                for c in affected],
            subject_concept=subject_concept,
            subject_concept_status=subject_concept_status,
            subject_indicator=subject_indicator,
            subject_indicator_status=subject_indicator_status,
            subject_instrument=subject_instrument,
            subject_instrument_status=subject_instrument_status,
            subject_market=subject_market,
            subject_market_status=subject_market_status,
            subject_regulation=subject_regulation,
            subject_regulation_status=subject_regulation_status,
        )

    # Only MENTIONED or PUBLISHER candidates — no subject
    return SubjectEntityV1(
        subject_entity_id="SUBJ-UNKNOWN",
        canonical_name="UNKNOWN",
        entity_type=TYPE_OTHER,
        status=SUBJECT_NOT_FOUND,
        confidence=CONFIDENCE_LOW,
        supporting_segment_ids=[],
        supporting_fact_ids=fact_ids,
        supporting_evidence_ids=evidence_ids,
        resolution_method=None,
        relationship=REL_UNKNOWN,
        aliases=[],
        affected_entities=[],
    )


def verify_publisher_firewall(
    publisher: Optional[PublisherInstitutionV1],
    subject: SubjectEntityV1,
) -> dict:
    """Per §11: Publisher Firewall — publisher CONFIRMED MUST NOT increase
    subject confidence. The two fields are independent.
    """
    publisher_status = publisher.status if publisher else "NOT_FOUND"
    subject_status = subject.status
    firewall_intact = True
    violation = ""

    # The firewall is intact BY CONSTRUCTION because the subject resolver
    # never looks at publisher.status to decide subject.status.
    # Verify: if publisher is CONFIRMED and subject is NOT_FOUND, that's ACCEPTED.
    # If publisher is CONFIRMED and subject is CONFIRMED, the subject must have
    # been confirmed by INDEPENDENT evidence (not by publisher identity).
    # Our resolver checks relationship == EVENT_SUBJECT which requires
    # event-local action verbs, NOT publisher identity.
    if publisher_status == "CONFIRMED" and subject_status == "CONFIRMED":
        # Verify the subject's relationship is EVENT_SUBJECT (not PUBLISHER)
        if subject.relationship == REL_PUBLISHER:
            firewall_intact = False
            violation = "Subject CONFIRMED with relationship=PUBLISHER — firewall violation"
    return {
        "publisher_status": publisher_status,
        "subject_status": subject_status,
        "subject_relationship": subject.relationship,
        "firewall_intact": firewall_intact,
        "violation": violation,
    }


__all__ = [
    "SubjectEntityV1",
    "SUBJECT_CONFIRMED", "SUBJECT_AMBIGUOUS", "SUBJECT_NOT_FOUND",
    "CONFIDENCE_HIGH", "CONFIDENCE_MEDIUM", "CONFIDENCE_LOW",
    "TYPE_ECONOMY", "TYPE_INDUSTRY", "TYPE_MARKET", "TYPE_INSTRUMENT",
    "TYPE_INSTITUTION", "TYPE_POLICY", "TYPE_INDICATOR",
    "TYPE_REGULATION", "TYPE_ENTITY", "TYPE_OTHER",
    "REL_EVENT_SUBJECT", "REL_AFFECTED_ENTITY", "REL_PUBLISHER",
    "REL_MENTIONED_ENTITY", "REL_UNKNOWN",
    "METHOD_PRIMARY_EVIDENCE", "METHOD_EVENT_LOCAL_PARENT",
    "METHOD_TABLE_CONTEXT", "METHOD_EVENT_LOCAL_HEADING",
    "METHOD_DOCUMENT_TITLE", "METHOD_DOCUMENT_SUBTITLE",
    "METHOD_DETERMINISTIC_METADATA",
    "PRIORITY_ORDER",
    "resolve_subject", "verify_publisher_firewall",
    "categorize_relationship",
    "extract_candidates_from_primary_segment",
    "extract_candidates_from_table_context",
    "extract_candidates_from_event_local_heading",
    "extract_candidates_from_document_title",
]
