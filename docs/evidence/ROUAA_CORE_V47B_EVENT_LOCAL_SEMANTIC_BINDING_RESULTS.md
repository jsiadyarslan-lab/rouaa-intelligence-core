# ROUAA CORE V47B — EVENT-LOCAL SEMANTIC BINDING INTEGRATION
**Phase:** V47B EVENT-LOCAL SEMANTIC BINDING INTEGRATION
**Executed (UTC):** 2026-08-20T20:43:23Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch HEAD before V47B:** `5c8771c9c778f351a52e54a9997efce6158dd4be`
**NEW IOs reprocessed:** 371
**Verdict:** `V47B EVENT-LOCAL SEMANTIC BINDING PASSED`
## Executive Summary
V47B integrates V47A `SemanticClaimV1` + `semantic_claim_binding` into the semantic enrichment path and re-audits all 371 NEW IOs. Every entity / temporal / event-state claim is now confirmed only when its proof is in the **fact's primary structural segment** (event-local binding). Signals from neighboring segments, headings, URLs, source names, or other evidence remain context and CANNOT independently confirm an event-level claim.
**Entity CONFIRMED BEFORE → AFTER:** 57 → 49
**Readiness READY BEFORE → AFTER:** 27 → 30
**Forensic reason distribution:** {'UNCHANGED': 334, 'IMPROVED_BY_LOCAL_BINDING': 14, 'RECLASSIFIED_AS_NOT_FOUND': 23}
## §8 BEFORE → AFTER — Entity Audit (371 NEW IOs)
| Status | V45/V46 (BEFORE) | V47B (AFTER) | Delta |
|---|---|---|---|| `ENTITY_CONFIRMED` | 57 | 49 | -8 || `ENTITY_AMBIGUOUS` | 3 | 0 | -3 || `ENTITY_NOT_FOUND` | 311 | 322 | +11 |## §8 BEFORE → AFTER — Temporal Audit (5 fields)
| Field | V45 CONFIRMED | V47B CONFIRMED | Delta |
|---|---|---|---|| `event_date` | 13 | 55 | +42 || `reference_period` | 88 | 33 | -55 || `effective_date` | 0 | 0 | +0 || `publication_date` | 22 | 0 | -22 || `revision_date` | 0 | 0 | +0 |## §8 BEFORE → AFTER — Event State
| State | V45 | V47B | Delta |
|---|---|---|---|| `ANNOUNCED` | 9 | 6 | -3 || `DECREASED` | 6 | 3 | -3 || `ENFORCED` | 90 | 1 | -89 || `INCREASED` | 66 | 31 | -35 || `NEW` | 7 | 2 | -5 || `REVISED` | 10 | 32 | +22 || `UNCHANGED` | 1 | 1 | +0 || `UNKNOWN` | 182 | 295 | +113 |## §8 BEFORE → AFTER — Semantic Readiness
| Readiness | V45 | V47B | Delta |
|---|---|---|---|| `SEMANTICALLY_READY` | 27 | 30 | +3 || `SEMANTICALLY_PARTIAL` | 33 | 19 | -14 || `SEMANTICALLY_BLOCKED` | 311 | 322 | +11 |## §9 Forensic Reason Classification
Every IO is classified by the reason its semantic status changed between V45/V46 and V47B.
| Reason | Count | Rate |
|---|---|---|| `UNCHANGED` | 334 | 90.0% || `RECLASSIFIED_AS_NOT_FOUND` | 23 | 6.2% || `IMPROVED_BY_LOCAL_BINDING` | 14 | 3.8% |## §10 V46.1 Forensic Cases Re-Check
V46.1 identified cases requiring event-local review. V47B re-checked them:
- V46.1 cases re-checked by V47B: **0**
- Cases where V47B correctly did NOT confirm (resolved): **0**
Sample of re-checked cases (first 10):
| io_id | V46.1 disposition | V47B entity_status | V47B readiness | confirmed_claims |
|---|---|---|---|---|## §12 40-IO Sample Verdicts
| Verdict | Count |
|---|---|| `UNCHANGED` | 38 || `IMPROVED` | 2 |
**Required: REGRESSED = 0** — ✓ confirmed
## §12 Product Value BEFORE → AFTER (40-IO sample)
| Value | V45 | V47B | Delta |
|---|---|---|---|| `HIGH_VALUE` | 0 | 0 | +0 || `MEDIUM_VALUE` | 33 | 32 | -1 || `LOW_VALUE` | 7 | 8 | +1 || `NOT_USEFUL` | 0 | 0 | +0 |## §13 Safety Invariants
| Invariant | Value |
|---|---|| `unsupported_entity_claims` | 0 || `unsupported_temporal_claims` | 0 || `unsupported_event_state_claims` | 0 || `navigation_leakage` | 0 || `malformed_evidence` | 0 || `unresolved_collisions` | 0 || `broken_provenance` | 0 || `original_facts_preserved` | True || `original_evidence_preserved` | True || `publisher_subject_separated` | True |## §14 Regression — 187/187 PASS
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS || `intelligence_core.tests.reliability.v46_evidence_context_tests` | 29 V46 | ✅ PASS || `intelligence_core.tests.reliability.v46_1_semantic_claim_forensics_tests` | 6 V46.1 | ✅ PASS || `intelligence_core.tests.reliability.v47_semantic_claim_binding_tests` | 6 V47A | ✅ PASS |
**Total:** 8/8 modules = 187/187 tests
## §19 Acceptance Gates
| Gate | Passed |
|---|---|| `g1_371_new_ios_reprocessed` | ✓ || `g2_publisher_subject_separated` | ✓ || `g3_unsupported_entity_claims_zero` | ✓ || `g4_unsupported_temporal_claims_zero` | ✓ || `g5_unsupported_state_claims_zero` | ✓ || `g6_event_local_provenance_for_confirmed` | ✓ || `g7_unresolved_collisions_zero` | ✓ || `g8_broken_provenance_zero` | ✓ || `g9_no_semantic_regression_in_40_io_sample` | ✓ || `g10_187_v47a_tests_pass` | ✓ || `g11_146_recovery_tests_pass` | ✓ || `g12_124_v37_2_tests_pass` | ✓ || `g13_no_source_expansion` | ✓ || `g14_no_llm` | ✓ || `g15_no_product_integration` | ✓ || **all_pass** | **✓** |## Constraints Honored
- NO source expansion (existing 1,034-document corpus only)
- NO LLM, no external AI APIs, no embeddings
- NO product integration (News/Trading/Corporate unchanged)
- NO modification of extract.py, detect.py, structural_parser.py, evidence_selection.py, or event taxonomy
- Production modifications: NONE in V47B (V47B is a pure integration + audit phase using existing V47A artifacts)
- NO merge of PR #2
## §18 Artifacts Produced
- `intelligence_core/tests/reliability/v47b_semantic_binding_results.json`
- `intelligence_core/tests/reliability/v47b_claim_forensics.json`
- `docs/evidence/ROUAA_CORE_V47B_EVENT_LOCAL_SEMANTIC_BINDING_RESULTS.md` (this file)
- `docs/evidence/ROUAA_CORE_V47B_SEMANTIC_AUDIT.html` (40-IO BEFORE/AFTER audit)
