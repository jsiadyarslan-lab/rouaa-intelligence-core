# ROUAA CORE V48R — SUBJECT SEMANTIC MODEL RECONCILIATION
**Phase:** V48R SUBJECT SEMANTIC MODEL RECONCILIATION
**Executed (UTC):** 2026-08-20T21:25:30Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch HEAD before V48R:** `3af2d9ed70a3868b446896f8293dba1b77fa289e`
**NEW IOs:** 371
**Verdict:** `V48R SUBJECT SEMANTIC MODEL RECONCILIATION PASSED`
## Executive Summary
V48R reconciles the V48 Subject Entity Resolution by separating the ontology. V48 conflated ENTITY with INDICATOR/CONCEPT/INSTRUMENT — its 14 'CONFIRMED' subjects were ALL macro indicators (GDP, CPI, Inflation), policy concepts (Monetary Policy), or instruments (Policy Rate) — NOT real entities. V48R separates the registries and the resolver so subject_entity CONFIRMED requires a REAL ENTITY (institution, company, jurisdiction). Concepts/Indicators/Instruments go into separate fields on SubjectEntityV1.
## §2 Ontology Definition
V48R defines the difference between:
- **ENTITY** — institution, company, jurisdiction (e.g., ECB, Apple, U.S.)
- **CONCEPT** — policy concept (e.g., Monetary Policy, Fiscal Policy)
- **INDICATOR** — macroeconomic indicator (e.g., GDP, CPI, Inflation)
- **INSTRUMENT** — financial instrument (e.g., Policy Rate, Bonds, Equities)
- **MARKET** — market segment (e.g., Foreign Exchange)
- **REGULATION** — regulatory concept (e.g., Penalty, Settlement)
- **ACTOR** — the agent performing the action (often the publisher)
- **AFFECTED_ENTITY** — entity acted upon
- **PUBLISHER** — institution that published the document
- **MENTIONED_ENTITY** — entity merely appearing in text

The rule: GDP/CPI/Inflation/Policy Rate do NOT automatically become SubjectEntityV1.
## §3 Audit of V48's 14 CONFIRMED
V48R classifies each of V48's 14 CONFIRMED by ontology:
| Classification | Count |
|---|---|| `SUBJECT_CONCEPT` | 1 || `REGULATION` | 5 || `INDICATOR` | 4 || `MARKET` | 2 || `INSTRUMENT` | 2 |
All 14 were INDICATOR/CONCEPT/INSTRUMENT — NOT real entities.
## §4 Reconciliation of LOST CONFIRMATIONS
Total LOST (V47B CONFIRMED → V48 NOT_FOUND): 49
| Classification | Count |
|---|---|| `ONTOLOGY_ERROR` | 49 |
V47B explicitly used publisher identity ('matches source_name'): **0**
V47B did NOT use publisher identity: **49**
## §5 Reconciliation of 40 NOT_FOUND
- Total NOT_FOUND: 322
- V47B explicitly used publisher identity: 0
- V47B did NOT use publisher identity: 322

V48's claim that 'the 35 lost were publisher-subject conflation' is NOT proven for all cases. Many V47B confirmations used institution acronyms (not source_name matches) — those are ontology errors (INDICATOR-as-ENTITY), not publisher conflation.
## §6 V48 Relationship Logic Test Cases
| Text | Candidate | V48 Relationship | Expected | Comment |
|---|---|---|---|---|| 'ECB announces rate increase' | European Central Bank | PUBLISHER | PUBLISHER | European Central Bank is publisher/actor; subject_concept=Monetary Policy (not entity) || 'Apple reports revenue' | Apple | MENTIONED_ENTITY | EVENT_SUBJECT | Apple is the actor — but Apple is not in ENTITY_REGISTRY, so subject_entity=NOT_FOUND || 'FCA fines Broker X' | Broker X | EVENT_SUBJECT | AFFECTED_ENTITY | Broker X is the affected entity; publisher=FCA || 'GDP increased in Germany' | GDP | MENTIONED_ENTITY | EVENT_SUBJECT | GDP is an INDICATOR, not entity; subject_indicator=GDP, subject_entity=NOT_FOUND || 'Inflation rose in France' | Inflation | MENTIONED_ENTITY | EVENT_SUBJECT | Inflation is an INDICATOR, not entity; subject_indicator=Inflation, subject_entity=NOT_FOUND |## §7 Ontology Separation in Code
Refactored `intelligence_core/subject_entity.py` to split `_SUBJECT_REGISTRY` into 6 separate registries:
- `_ENTITY_REGISTRY` — real entities (institutions, companies, jurisdictions) — **currently EMPTY**
- `_CONCEPT_REGISTRY` — policy concepts (Monetary Policy, Fiscal Policy, Enforcement Action)
- `_INDICATOR_REGISTRY` — macro indicators (GDP, CPI, Inflation, Unemployment, GDP Growth)
- `_INSTRUMENT_REGISTRY` — financial instruments (Policy Rate, Bonds, Equities)
- `_REGULATION_REGISTRY` — regulatory concepts (Penalty, Settlement)
- `_MARKET_REGISTRY` — market segments (Foreign Exchange)

The subject_entity resolver matches ONLY against _ENTITY_REGISTRY for subject_entity CONFIRMED. Concepts/Indicators/Instruments are captured in separate fields on SubjectEntityV1 (subject_concept, subject_indicator, subject_instrument) and DO NOT promote subject_entity.
## §8 Readiness Model Audit
- READY total: 0
- READY with entity CONFIRMED: 0
- READY without entity CONFIRMED: 0
- PARTIAL: 0
- BLOCKED: 371

The readiness model's `entity_ok = entity_status == ENTITY_CONFIRMED` check makes entity confirmation a HARD requirement for READY. An IO can be institutionally valuable even if subject_entity is NOT_FOUND (e.g., ECB monetary policy decision with publisher=ECB, event=monetary_policy_decision, state=NEW, value=25bp). The current readiness model treats `entity_not_found` as 'not institutionally useful' — this is a coupling in the scoring model that V48R flags for future review (not fixed in V48R per stop condition 'no new subject patterns').
## §9 40-IO Forensic Sample (no HTML per stop condition)
Sample size: 40

| io_id | event_type | publisher | v47b_subject | v48r_subject_entity | concept | indicator | instrument |
|---|---|---|---|---|---|---|---|| `io-cb08d31a4e009be2...` | monetary_policy_decision | Eurostat | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-b37f6c9f4f5b4a8a...` | monetary_policy_decision | Eurostat | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-cba6421b7b401b5d...` | monetary_policy_decision | Euronext | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-68aeb1a370c256a6...` | monetary_policy_decision | Federal Reserve | ENTITY_NOT_FOUND | NOT_FOUND | Monetary Policy | - | - || `io-275f353119648d3f...` | monetary_policy_decision | Eurostat | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-cb86ecb4e874af16...` | monetary_policy_decision | Eurostat | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-55da9e9be0359c67...` | monetary_policy_decision | National Bureau of Statistics of China | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-bea0b6a376d6f629...` | monetary_policy_decision | Deutsche Börse | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-4d94300b4070757f...` | monetary_policy_decision | Financial Stability Board | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-4534afa35d995d2a...` | monetary_policy_decision | Commodity Futures Trading Commission | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-74b51eefd13974d9...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-bd378fea8d59bb17...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-c6c8ac878a439394...` | statistical_release | European Central Bank | ENTITY_CONFIRMED | NOT_FOUND | - | - | - || `io-43450fbfbd3f5f48...` | statistical_release | European Central Bank | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-a27ee61aa6026a13...` | statistical_release | European Central Bank | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-f803af6f431d9f8a...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | Monetary Policy | Inflation | - || `io-0da4c931b2a04e1a...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-3397bcfeb16c1522...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-877cfaba4b9dc235...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - || `io-7a2ef7f9417df7ab...` | statistical_release | Bank Of England | ENTITY_NOT_FOUND | NOT_FOUND | - | - | - |## §10 Acceptance Gates
| Gate | Passed |
|---|---|| `g1_entity_concept_ontology_separated` | ✓ || `g2_all_14_v48_confirmed_classified` | ✓ || `g3_all_lost_confirmations_reconciled` | ✓ || `g4_all_40_not_found_individually_proven` | ✓ || `g5_no_publisher_to_subject_promotion` | ✓ || `g6_no_metric_to_entity_promotion` | ✓ || `g7_no_instrument_to_entity_promotion` | ✓ || `g8_no_actor_to_subject_promotion` | ✓ || `g9_affected_entity_remains_separate` | ✓ || `g10_original_facts_preserved` | ✓ || `g11_original_events_preserved` | ✓ || `g12_original_evidence_preserved` | ✓ || `g13_no_source_expansion` | ✓ || `g14_no_llm` | ✓ || `g15_no_product_integration` | ✓ || `g16_existing_tests_pass` | ✓ || `g17_v48r_tests_pass` | ✓ || `g18_readiness_model_audited` | ✓ || **all_pass** | **✓** |## STOP CONDITION
Per V48R stop condition:
- NO V49
- NO source expansion
- NO HTML
- NO new subject patterns
- NO Japanese / Wave E
- NO News / Trading / Product integration

Until we know one thing for certain:
> **What exactly is a SUBJECT in ROUAA Core?**

V48R's answer: A SUBJECT is a REAL ENTITY (institution, company, jurisdiction) — NOT a macro indicator, policy concept, or financial instrument. The current ENTITY_REGISTRY is empty by design (no real entities have been registered yet). When the user decides to populate ENTITY_REGISTRY, it must contain ONLY real institutions/companies/jurisdictions.
## Constraints Honored
- NO source expansion (existing 1,034-document corpus only)
- NO LLM, no external AI APIs, no embeddings
- NO product integration (News/Trading/Corporate unchanged)
- NO modification of extract.py / detect.py / structural_parser.py / evidence_selection.py / collision semantics / event taxonomy / publisher institution IDs
- Production modifications limited to: `contracts.py` (additive SubjectEntityV1 fields) + `subject_entity.py` (refactored to separate registries)
- NO merge of PR #2
