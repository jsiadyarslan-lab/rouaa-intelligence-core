# ROUAA CORE V48S — SUBJECT ROLE & SEMANTIC OBJECT MODEL
**Phase:** V48S SUBJECT ROLE & SEMANTIC OBJECT MODEL RECONCILIATION
**Executed (UTC):** 2026-08-20T21:43:07Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch HEAD before V48S:** `bbae37c46463a5cf73240a6933911e038803e03a`
**Verdict:** `V48S SUBJECT ROLE SEMANTIC MODEL PASSED`
## A. Subject Definition
**V48S §4 CRITICAL RULE:**
> subject = the semantic object the event asserts a state, change, action, measurement, or decision about.

**Subject representation:**
> The subject object can be represented as: ENTITY | CONCEPT | INDICATOR | INSTRUMENT | MARKET | REGULATION. It is NOT required to be an ENTITY.

**V48R's rejected axiom:**
> `subject = REAL ENTITY`

V48R incorrectly defined subject as REAL ENTITY. V48S corrects this: subject is the **semantic object** of the event — which can be an entity, concept, indicator, instrument, market, or regulation. The subject object's TYPE is determined by the event's content, not by an a priori axiom.
## B. Role Ontology
| Role | Definition | Can Be Null | Can Equal | Evidence | Promotable |
|---|---|---|---|---|---|| `PUBLISHER` | The institution responsible for publishing the source/document. Identified from source metadata (source_id, source_path,... | False | ACTOR | source_id + source_path + (optional) institution_id | True || `ACTOR` | The agent that PERFORMS the action described in the event. Often the publisher, but can differ (e.g., a news outlet repo... | True | PUBLISHER, SUBJECT_ENTITY | event-local action verb (announces, publishes, releases, issues, decides, raises | True || `SUBJECT_ENTITY` | The REAL ENTITY (institution, company, jurisdiction) that the event is ABOUT — when the event's semantic object is an en... | True | ACTOR, AFFECTED_ENTITY | entity name in primary segment OR event-local context that structurally binds th | True || `SUBJECT_CONCEPT` | The POLICY CONCEPT the event is about (e.g., Monetary Policy, Fiscal Policy, Enforcement Action). Can coexist with SUBJE... | True | — | concept alias match in primary segment or event-local heading | True || `SUBJECT_INDICATOR` | The MACROECONOMIC INDICATOR the event is about (e.g., GDP, CPI, Inflation, Unemployment). Can be the ONLY subject (GDP i... | True | — | indicator alias match in primary segment | True || `SUBJECT_INSTRUMENT` | The FINANCIAL INSTRUMENT the event is about (e.g., Policy Rate, Bonds, Equities). Can coexist with SUBJECT_CONCEPT (ECB ... | True | — | instrument alias match in primary segment | True || `JURISDICTION` | The geographic or political scope of the event (e.g., Germany, France, Euro Area, United States, United Kingdom). Can co... | True | — | jurisdiction name in primary segment or event-local context | True || `AFFECTED_ENTITY` | The entity ACTED UPON by the event. CAN equal SUBJECT_ENTITY (FCA fines Broker X: affected=Broker X, subject=Broker X — ... | True | SUBJECT_ENTITY | passive verb context (was fined, was penalized, was charged) + entity name | True || `MENTIONED_ENTITY` | An entity that merely APPEARS in the event text but is neither the actor, subject, affected, nor publisher. CANNOT be pr... | True | — | entity name in text without event-local binding | False |## C. Role Coexistence Rules
| Rule | Allowed |
|---|---|| subject_entity + subject_concept CAN coexist | ✓ || subject_entity + subject_indicator CAN coexist | ✓ || subject_entity + subject_instrument CAN coexist | ✓ || subject_concept + subject_indicator CAN coexist | ✓ || subject_concept + subject_instrument CAN coexist | ✓ || actor + subject_entity CAN be same | ✓ || actor + subject_entity CAN differ | ✓ || affected_entity + subject_entity CAN be same | ✓ || affected_entity + subject_entity CAN differ | ✓ || publisher + actor CAN be same | ✓ || publisher + actor CAN differ | ✓ || mentioned_entity + subject_entity CANNOT auto-promote | ✓ |## D. Five Mandatory Semantic Cases
### "ECB raises policy rate"
| Role | Value |
|---|---|| Publisher | European Central Bank || Actor | European Central Bank || Subject Entity | NOT_FOUND || Subject Concept | Monetary Policy || Subject Indicator | NOT_FOUND || Subject Instrument | Policy Rate || Jurisdiction | Euro Area || Affected Entity | NOT_FOUND |
**Rationale:** The event is about ECB's decision to raise the policy rate. ECB is the ACTOR (it performs the 'raise' action). The SUBJECT is the policy rate — which is an INSTRUMENT, not an entity. subject_concept=Monetary Policy captures the broader policy area. subject_entity=NOT_FOUND because the event is not about an entity (e.g., a company or institution being acted upon); it's about a financial instrument. Actor ≠ Subject here because ECB is the actor, not the semantic object of the event.
### "Apple reports revenue"
| Role | Value |
|---|---|| Publisher | NOT_FOUND || Actor | Apple || Subject Entity | Apple || Subject Concept | Revenue || Subject Indicator | NOT_FOUND || Subject Instrument | NOT_FOUND || Jurisdiction | NOT_FOUND || Affected Entity | NOT_FOUND |
**Rationale:** The event is about Apple's revenue report. Apple is BOTH the ACTOR (it reports) AND the SUBJECT_ENTITY (the event is about Apple). subject_concept=Revenue captures what kind of report. Actor = Subject here — this is a legal coexistence per §5. subject_entity is NOT_FOUND only if we refuse to treat Apple as an entity — but Apple IS a real company entity. The ENTITY_REGISTRY is empty (per §7), so in practice this IO would have subject_entity=NOT_FOUND until the registry is populated. But the SEMANTIC MODEL says: if Apple were in the registry, subject_entity=Apple would be correct.
### "FCA fines Broker X"
| Role | Value |
|---|---|| Publisher | Financial Conduct Authority || Actor | Financial Conduct Authority || Subject Entity | Broker X || Subject Concept | Enforcement Action || Subject Indicator | NOT_FOUND || Subject Instrument | NOT_FOUND || Jurisdiction | United Kingdom || Affected Entity | Broker X |
**Rationale:** The event is about Broker X being fined by FCA. Broker X is BOTH the AFFECTED_ENTITY (it is acted upon) AND the SUBJECT_ENTITY (the event is about Broker X). FCA is the ACTOR and PUBLISHER. subject_concept=Enforcement Action captures the event type. Affected = Subject here — this is a legal coexistence per §5. V48R incorrectly said 'affected → never subject' — V48S corrects this: affected CAN equal subject when the event is about the affected entity.
### "GDP increased in Germany"
| Role | Value |
|---|---|| Publisher | NOT_FOUND || Actor | NOT_FOUND || Subject Entity | NOT_FOUND || Subject Concept | NOT_FOUND || Subject Indicator | GDP || Subject Instrument | NOT_FOUND || Jurisdiction | Germany || Affected Entity | NOT_FOUND |
**Rationale:** The event is about GDP increasing. GDP is an INDICATOR, not an entity. subject_indicator=GDP. jurisdiction=Germany. There is NO actor (no one 'performed' the increase — it's a statistical observation). subject_entity=NOT_FOUND is CORRECT and EXPECTED — the event doesn't need an entity subject. The IO is institutionally useful even without subject_entity. This is the key V48S insight: subject can be an INDICATOR without any entity.
### "Inflation rose in France"
| Role | Value |
|---|---|| Publisher | NOT_FOUND || Actor | NOT_FOUND || Subject Entity | NOT_FOUND || Subject Concept | NOT_FOUND || Subject Indicator | Inflation || Subject Instrument | NOT_FOUND || Jurisdiction | France || Affected Entity | NOT_FOUND |
**Rationale:** The event is about inflation rising. Inflation is an INDICATOR. subject_indicator=Inflation. jurisdiction=France. No actor, no entity subject. The IO is institutionally useful (inflation is a key macro indicator for monetary policy decisions). subject_entity=NOT_FOUND is correct.
## E. Subject vs Actor Analysis
- **Actor** = who PERFORMS the action
- **Subject** = what the event is ABOUT
- Actor CAN equal Subject (e.g., "Apple reports revenue" — Apple is both actor and subject)
- Actor CAN differ from Subject (e.g., "ECB raises policy rate" — ECB is actor, policy rate is subject)
- Actor CAN be NULL (e.g., "GDP increased in Germany" — statistical observation, no actor)
- V48R incorrectly treated Actor as automatically NOT Subject — V48S corrects this.
## F. Subject vs Affected Analysis
- **Affected Entity** = who is ACTED UPON
- **Subject** = what the event is ABOUT
- Affected CAN equal Subject (e.g., "FCA fines Broker X" — Broker X is both affected and subject)
- Affected CAN differ from Subject (e.g., "ECB raises policy rate" — no affected entity)
- V48R incorrectly set 'affected → never subject' rule — V48S corrects this: affected CAN equal subject when the event is about the affected entity.
## G. Entity vs Concept/Indicator Analysis
- **Entity** = institution, company, jurisdiction (ECB, Apple, Germany)
- **Concept** = policy concept (Monetary Policy, Enforcement Action)
- **Indicator** = macroeconomic indicator (GDP, CPI, Inflation)
- **Instrument** = financial instrument (Policy Rate, Bonds, Equities)
- V48R separated these correctly into 6 registries
- V48R's ERROR was making subject_entity the ONLY path to subject confirmation
- V48S corrects: subject can be ANY of these types — subject_entity is ONE representation, not the only one
## H. Readiness Coupling Analysis
**Current rule:** `entity_ok = entity_status == ENTITY_CONFIRMED`
**Problem:** The current readiness model makes entity confirmation a HARD requirement for READY. This means IOs about macro indicators (GDP, CPI, Inflation) can NEVER be READY — even though they are institutionally useful. This is a P0 semantic governance issue.

### Impact by scenario
| Scenario | Impact |
|---|---|| `central_bank_policy_decision` | READY requires entity_ok. ECB policy decision has subject_concept=Monetary Policy + subject_instrument=Policy Rate but subject_entity=NOT_FOUND. Under current rule: BLOCKED. Under V48S model: should b... || `gdp_release` | GDP release has subject_indicator=GDP + jurisdiction=Germany but subject_entity=NOT_FOUND. Under current rule: BLOCKED. Under V48S model: should be READY (has confirmed indicator + jurisdiction).... || `inflation_release` | Inflation release has subject_indicator=Inflation + jurisdiction=France. Under current rule: BLOCKED. Under V48S model: should be READY.... || `regulatory_enforcement` | FCA fines Broker X has subject_entity=Broker X + affected_entity=Broker X + subject_concept=Enforcement Action. Under current rule: READY (if Broker X in registry). Under V48S model: READY.... || `market_level_event` | Market events (e.g., FX moves) may have subject_instrument=Foreign Exchange but no entity. Under current rule: BLOCKED. Under V48S model: should be PARTIAL or READY.... || `company_earnings` | Apple reports revenue has subject_entity=Apple + subject_concept=Revenue. Under current rule: READY (if Apple in registry). Under V48S model: READY.... |
**Proposed fix:** READY should require: at least ONE of {subject_entity, subject_concept, subject_indicator, subject_instrument} is CONFIRMED — NOT specifically subject_entity. This decouples readiness from entity-only confirmation.

**V48S decision:** V48S does NOT change the readiness implementation (per §6 'Do not change the readiness implementation yet'). V48S only produces the semantic decision and impact analysis. The fix belongs to a later phase.
## I. Decision
V48S **formally defines** the Subject Role & Semantic Object Model:
1. **Subject** = the semantic object the event asserts about (NOT necessarily an entity)
2. **9 roles** formally defined: PUBLISHER, ACTOR, SUBJECT_ENTITY, SUBJECT_CONCEPT, SUBJECT_INDICATOR, SUBJECT_INSTRUMENT, JURISDICTION, AFFECTED_ENTITY, MENTIONED_ENTITY
3. **Role coexistence rules** explicitly allow actor=subject, affected=subject, entity+concept coexistence
4. **5 mandatory cases** resolved with correct role assignments
5. **Readiness coupling** identified as P0 governance issue — decoupling proposed but NOT implemented in V48S
6. **ENTITY_REGISTRY remains empty** — no new patterns added per §7
## J. Next Permitted Phase
Per V48S STOP CONDITION:
- NO V49
- NO ENTITY_REGISTRY population
- NO source expansion
- NO HTML
- NO new extraction patterns
- NO Japanese / Wave E
- NO News / Trading / Product integration

Until the user decides to:
1. **Decouple readiness** from entity-only confirmation (implement the proposed fix from §H)
2. **Populate ENTITY_REGISTRY** with real institutions/companies/jurisdictions
3. **Re-audit the 371 IOs** with the V48S semantic model (subject can be entity, concept, indicator, or instrument)
4. **Only then** consider Controlled Source Expansion
## Acceptance Gates
| Gate | Passed |
|---|---|| `g1_subject_formally_defined` | ✓ || `g2_actor_formally_separated` | ✓ || `g3_publisher_formally_separated` | ✓ || `g4_affected_formally_separated` | ✓ || `g5_entity_concept_indicator_instrument_separated` | ✓ || `g6_subject_without_forcing_entity` | ✓ || `g7_role_coexistence_explicit` | ✓ || `g8_five_mandatory_cases_resolved` | ✓ || `g9_no_publisher_to_subject_promotion` | ✓ || `g10_no_actor_to_subject_automatic_promotion` | ✓ || `g11_no_indicator_to_entity_promotion` | ✓ || `g12_no_affected_to_subject_automatic_prohibition` | ✓ || `g13_facts_unchanged` | ✓ || `g14_events_unchanged` | ✓ || `g15_evidence_unchanged` | ✓ || `g16_no_extraction_changes` | ✓ || `g17_no_source_expansion` | ✓ || `g18_no_llm` | ✓ || `g19_existing_tests_pass` | ✓ || `g20_v48s_tests_pass` | ✓ || `g21_readiness_coupling_documented` | ✓ || `g22_no_product_integration` | ✓ || **all_pass** | **✓** |## Tests — 298/298 PASS
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS || `intelligence_core.tests.reliability.v46_evidence_context_tests` | 29 V46 | ✅ PASS || `intelligence_core.tests.reliability.v46_1_semantic_claim_forensics_tests` | 6 V46.1 | ✅ PASS || `intelligence_core.tests.reliability.v47_semantic_claim_binding_tests` | 6 V47A | ✅ PASS || `intelligence_core.tests.reliability.v47c_publisher_institution_tests` | 35 V47C | ✅ PASS || `intelligence_core.tests.reliability.v48_subject_entity_tests` | 26 V48 | ✅ PASS || `intelligence_core.tests.reliability.v48s_subject_role_tests` | 50 V48S | ✅ PASS |
**Total:** 11/11 modules = 298/298 tests
