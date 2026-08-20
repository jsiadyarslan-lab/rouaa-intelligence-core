# ROUAA CORE V47C — PUBLISHER INSTITUTION CONTEXT LAYER
**Phase:** V47C PUBLISHER INSTITUTION CONTEXT LAYER
**Executed (UTC):** 2026-08-20T20:56:35Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch HEAD before V47C:** `61ceeffa6cb17ea90d5987f6d803fe4b173e1e0e`
**NEW IOs:** 371
**Verdict:** `V47C PUBLISHER INSTITUTION LAYER PASSED`
## Executive Summary
V47C builds a deterministic canonical Publisher Institution layer that identifies the institution RESPONSIBLE FOR PUBLISHING a source/document — WITHOUT ever promoting publisher identity into subject_entity. The Subject Entity Firewall (§9) is mandatory: publisher_institution CONFIRMED does NOT promote subject_entity. The two fields are independent.
**Publisher CONFIRMED:** 272/371
**Subject_entity CONFIRMED (V47B event-local):** 49/371
**Firewall violations:** 0 (required: 0)
## §3 Conceptual Model
```
SOURCE
  ↓
PUBLISHER_INSTITUTION
  ↓
DOCUMENT
  ↓
EVENT
  ↓
SUBJECT_ENTITY
```
NEVER infer subject_entity from publisher_institution.
## §11 Publisher Distribution (371 NEW IOs)
| Status | Count | Rate |
|---|---|---|| `CONFIRMED` | 272 | 73.3% || `AMBIGUOUS` | 99 | 26.7% || `NOT_FOUND` | 0 | 0.0% |## §11 Subject_entity Distribution (V47B event-local binding)
| Status | Count | Rate |
|---|---|---|| `ENTITY_CONFIRMED` | 49 | 13.2% || `ENTITY_AMBIGUOUS` | 0 | 0.0% || `ENTITY_NOT_FOUND` | 322 | 86.8% |## §11 Publisher Institution Type Distribution
| Type | Count |
|---|---|| `CENTRAL_BANK` | 103 || `OTHER` | 99 || `STATISTICAL_AGENCY` | 98 || `EXCHANGE` | 31 || `SECURITIES_REGULATOR` | 19 || `GOVERNMENT_MINISTRY` | 12 || `REGULATOR` | 8 || `INTERNATIONAL_ORGANIZATION` | 1 |## §11 Publisher Confidence Distribution
| Confidence | Count |
|---|---|| `HIGH` | 209 || `MEDIUM` | 63 || `LOW` | 99 |## §11 Publisher Support Method Distribution
| Method | Count |
|---|---|| `SOURCE_REGISTRY` | 308 || `SOURCE_DOMAIN` | 63 |## §9 Subject Entity Firewall Verification
- Firewall violations: **0** (required: 0)
- Publisher CONFIRMED + Subject NOT_FOUND: ACCEPTED (per §9)
- Publisher CONFIRMED + Subject CONFIRMED (independent event-local evidence): ACCEPTED
- Publisher NEVER promotes subject_entity
## §14-15 Temporal + Event-State Preservation
V47C does NOT change temporal or event-state logic. Values are preserved exactly from V47B.

### Temporal confirmed counts (must match V47B)
| Field | Count |
|---|---|| `reference_period` | 33 || `event_date` | 55 || `effective_date` | 0 || `publication_date` | 0 || `revision_date` | 0 |
### Event state distribution
| State | Count |
|---|---|| `UNKNOWN` | 295 || `ANNOUNCED` | 6 || `INCREASED` | 31 || `REVISED` | 32 || `UNCHANGED` | 1 || `DECREASED` | 3 || `NEW` | 2 || `ENFORCED` | 1 |## §16 No Re-Extraction
- new_facts = 0
- new_events = 0
- evidence_rewritten = 0
## §20 40-IO Publisher Classification
| Class | Count |
|---|---|| `PUBLISHER_CORRECT` | 28 || `PUBLISHER_AMBIGUOUS` | 12 || `PUBLISHER_INCORRECT` | 0 (required: 0) |## §21 Institution Productivity View (Top 15)
| Publisher | NEW IOs | Sources | Event Types |
|---|---|---|---|| `Bank Of England` | 57 | 1 | statistical_release || `Bureau of Economic Analysis` | 41 | 1 | statistical_release || `Euronext` | 30 | 1 | monetary_policy_decision, regulatory_enforcement || `National Bank of Ukraine` | 25 | 1 | monetary_policy_decision || `European Central Bank Statistics` | 24 | 1 | regulatory_enforcement, statistical_release || `Bank of Canada` | 20 | 1 | statistical_release || `Central Bank of Bosnia and Herzegovina` | 19 | 1 | market_statistic_release, monetary_policy_decision, regulatory_enforcement || `National Statistical Institute of Bulgaria` | 15 | 1 | monetary_policy_decision || `European Central Bank` | 13 | 2 | regulatory_enforcement, statistical_release || `European Securities and Markets Authority` | 10 | 1 | regulatory_enforcement || `Central Bank of Kenya` | 10 | 1 | monetary_policy_decision || `Financial Conduct Authority` | 8 | 1 | monetary_policy_decision, regulatory_enforcement || `Central Statistics Office of Ireland` | 8 | 1 | monetary_policy_decision || `U.S. Department of the Treasury` | 6 | 1 | monetary_policy_decision, regulatory_enforcement || `Central Bank of Jordan` | 6 | 1 | monetary_policy_decision |
*Informational only. Publisher count is NOT intelligence yield.*
## §22 Acceptance Gates
| Gate | Passed |
|---|---|| `g1_PublisherInstitutionV1_implemented` | ✓ || `g2_publisher_registry_deterministic` | ✓ || `g3_publisher_coverage_measurable` | ✓ || `g4_publisher_neq_subject_firewall_passes` | ✓ || `g5_unsupported_subject_claims_zero` | ✓ || `g6_unsupported_temporal_claims_zero` | ✓ || `g7_unsupported_event_state_claims_zero` | ✓ || `g8_original_facts_preserved` | ✓ || `g9_original_evidence_preserved` | ✓ || `g10_new_facts_zero` | ✓ || `g11_new_events_zero` | ✓ || `g12_evidence_rewritten_zero` | ✓ || `g13_publisher_incorrect_in_40_sample_zero` | ✓ || `g14_187_existing_tests_pass` | ✓ || `g15_all_v47c_tests_pass` | ✓ || `g16_no_source_expansion` | ✓ || `g17_no_llm` | ✓ || `g18_no_product_integration` | ✓ || **all_pass** | **✓** |## §19 Regression Tests — 222/222 PASS
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS || `intelligence_core.tests.reliability.v46_evidence_context_tests` | 29 V46 | ✅ PASS || `intelligence_core.tests.reliability.v46_1_semantic_claim_forensics_tests` | 6 V46.1 | ✅ PASS || `intelligence_core.tests.reliability.v47_semantic_claim_binding_tests` | 6 V47A | ✅ PASS || `intelligence_core.tests.reliability.v47c_publisher_institution_tests` | 35 V47C | ✅ PASS |
**Total:** 9/9 modules = 187+35=222 tests
## Constraints Honored
- NO source expansion (existing 1,034-document corpus only)
- NO LLM, no external AI APIs, no embeddings
- NO product integration (News/Trading/Corporate unchanged)
- NO modification of extract.py / detect.py / structural_parser.py / evidence_selection.py / collision semantics / event taxonomy / source registry core
- Production modifications limited to: `intelligence_core/contracts.py` (additive PublisherInstitutionV1) + `intelligence_core/publisher_institution.py` (NEW module)
- NO merge of PR #2
## §23 Artifacts Produced
- `intelligence_core/contracts.py` (additive PublisherInstitutionV1)
- `intelligence_core/publisher_institution.py` (NEW module)
- `intelligence_core/tests/reliability/v47c_publisher_institution_tests.py` (35 dedicated tests)
- `intelligence_core/tests/reliability/v47c_publisher_audit_results.json`
- `intelligence_core/tests/reliability/v47c_semantic_results.json`
- `docs/evidence/ROUAA_CORE_V47C_PUBLISHER_INSTITUTION_LAYER.md` (this file)
- `docs/evidence/ROUAA_CORE_V47C_PUBLISHER_SUBJECT_AUDIT.html` (40-IO audit)
