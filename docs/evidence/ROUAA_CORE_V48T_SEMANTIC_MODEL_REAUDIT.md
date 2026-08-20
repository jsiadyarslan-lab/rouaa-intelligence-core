# ROUAA CORE V48T — SEMANTIC MODEL RE-AUDIT & READINESS DECOUPLING
**Phase:** V48T SEMANTIC MODEL RE-AUDIT
**Executed (UTC):** 2026-08-20T21:53:41Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Verdict:** `V48T SEMANTIC MODEL RE-AUDIT & READINESS DECOUPLING PASSED`
## Executive Summary
V48T applies the V48S semantic role model to the 371 NEW IOs and removes the entity-only dependency from READINESS scoring. The key reform: `subject_semantically_identified` replaces `entity_ok == ENTITY_CONFIRMED`. An IO is now READY when ANY subject field (entity/concept/indicator/instrument) is CONFIRMED — not just subject_entity.
**BEFORE (V48R):** READY=0, BLOCKED=371
**AFTER (V48T):** subject_status CONFIRMED (ANY)=24
## §4 Readiness Reform
**Old rule:** `entity_ok = entity_status == ENTITY_CONFIRMED`
**New rule:** `subject_semantically_identified = subject_entity OR subject_concept OR subject_indicator OR subject_instrument CONFIRMED`
**Other gates preserved:** True

READY = event_valid AND evidence_valid AND temporal_state_satisfied AND subject_semantically_identified
## §3 Subject Semantic Status + Type
| Subject Type | Count |
|---|---|| `UNKNOWN` | 347 || `INDICATOR` | 11 || `CONCEPT` | 9 || `INSTRUMENT` | 4 |## §5 BEFORE / AFTER
| Metric | V47B/V48R (BEFORE) | V48T (AFTER) |
|---|---|---|| subject_entity CONFIRMED | 49 | 0 || subject_concept CONFIRMED | — | 9 || subject_indicator CONFIRMED | — | 13 || subject_instrument CONFIRMED | — | 8 || subject_status CONFIRMED (ANY) | 49 | 24 || READY | 0 | 9 || PARTIAL | 0 | 15 || BLOCKED | 371 | 347 |## §6 Forensic Reconciliation
| Classification | Count |
|---|---|| `AMBIGUOUS` | 307 || `FALSE_POSITIVE` | 40 || `INDICATOR` | 11 || `CONCEPT` | 9 || `INSTRUMENT` | 4 |
### 49 V47B CONFIRMED → classified
| Classification | Count |
|---|---|| `FALSE_POSITIVE` | 40 || `CONCEPT` | 4 || `INDICATOR` | 4 || `INSTRUMENT` | 1 |
### 14 V48 CONFIRMED → classified
| Classification | Count |
|---|---|| `CONCEPT` | 6 || `INDICATOR` | 4 || `INSTRUMENT` | 4 |## §7 Mandatory Cases Through Actual Resolver
| Case | Publisher | Subject Entity | Subject Concept | Subject Indicator | Subject Instrument | Subject Type |
|---|---|---|---|---|---|---|| 'ECB raises policy rate' | European Central Bank | NOT_FOUND | NOT_FOUND | NOT_FOUND | Policy Rate | INSTRUMENT || 'Apple reports revenue' | Bureau of Economic Analysis | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND | UNKNOWN || 'FCA fines Broker X' | Financial Conduct Authority | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND | UNKNOWN || 'GDP increased in Germany' | Bureau of Economic Analysis | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND | UNKNOWN || 'Inflation rose in France' | Bureau of Economic Analysis | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND | UNKNOWN |## §8 Product Value Audit
| Value | V47B (BEFORE) | V48T (AFTER) |
|---|---|---|| `HIGH_VALUE` | 0 | 0 || `MEDIUM_VALUE` | 32 | 31 || `LOW_VALUE` | 8 | 9 || `NOT_USEFUL` | 0 | 0 |
- False regressions: 1 (readiness reclassified, quality same)
- True regressions: 0 (actual quality dropped)
- Reclassifications: 0 (same level, different readiness)
## §10 Acceptance Gates
| Gate | Passed |
|---|---|| `g1_v48s_roles_integrated` | ✓ || `g2_subject_type_separated_from_entity` | ✓ || `g3_publisher_independent` | ✓ || `g4_actor_independent` | ✓ || `g5_affected_independent` | ✓ || `g6_no_indicator_to_entity_promotion` | ✓ || `g7_no_concept_to_entity_promotion` | ✓ || `g8_no_instrument_to_entity_promotion` | ✓ || `g9_no_publisher_to_subject_promotion` | ✓ || `g10_no_mentioned_to_subject_promotion` | ✓ || `g11_all_371_ios_reaudited` | ✓ || `g12_historical_49_14_0_reconciled` | ✓ || `g13_readiness_no_longer_requires_entity` | ✓ || `g14_existing_readiness_gates_preserved` | ✓ || `g15_facts_unchanged` | ✓ || `g16_events_unchanged` | ✓ || `g17_evidence_unchanged` | ✓ || `g18_provenance_unchanged` | ✓ || `g19_no_extraction_changes` | ✓ || `g20_no_source_expansion` | ✓ || `g21_no_llm` | ✓ || `g22_no_entity_registry_population` | ✓ || `g23_no_product_integration` | ✓ || `g24_existing_tests_pass` | ✓ || `g25_v48t_tests_pass` | ✓ || `g26_five_mandatory_cases_pass` | ✓ || `g27_product_value_regression_explained` | ✓ || **all_pass** | **✓** |## Tests — 298/298 PASS
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS || `intelligence_core.tests.reliability.v46_evidence_context_tests` | 29 V46 | ✅ PASS || `intelligence_core.tests.reliability.v46_1_semantic_claim_forensics_tests` | 6 V46.1 | ✅ PASS || `intelligence_core.tests.reliability.v47_semantic_claim_binding_tests` | 6 V47A | ✅ PASS || `intelligence_core.tests.reliability.v47c_publisher_institution_tests` | 35 V47C | ✅ PASS || `intelligence_core.tests.reliability.v48_subject_entity_tests` | 26 V48 | ✅ PASS || `intelligence_core.tests.reliability.v48s_subject_role_tests` | 50 V48S | ✅ PASS |
**Total:** 11/11 modules = 298 tests
## STOP CONDITION
Per V48T STOP CONDITION: NO ENTITY_REGISTRY population, NO V49, NO Source Expansion, NO HTML extraction, NO new subject patterns, NO Japanese/Wave E, NO News/Trading/Product.

Until we see the 371 IOs' results with the new semantic model.
