# ROUAA CORE V48 — SUBJECT ENTITY RESOLUTION LAYER
**Phase:** V48 SUBJECT ENTITY RESOLUTION LAYER
**Executed (UTC):** 2026-08-20T21:10:34Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch HEAD before V48:** `deb9fbc97c708356eda8de04a237b2589a605d87`
**NEW IOs:** 371
**Verdict:** `V48 SUBJECT ENTITY RESOLUTION BLOCKED`
## Executive Summary
V48 builds a deterministic Subject Entity Resolution layer that answers "What is the event actually about?" — distinct from publisher_institution. Subject candidates come ONLY from structurally relevant context (priority order per §4). The Publisher Firewall (§11) is mandatory: publisher CONFIRMED does NOT promote subject_entity. affected_entity is stored SEPARATELY from subject_entity (§12).
**Subject_entity CONFIRMED BEFORE → AFTER:** 49 → 14
**Publisher CONFIRMED:** 272
**Firewall violations:** 0 (required: 0)
**Affected entities:** 3 across 2 IOs
## §3 SubjectEntityV1 Contract
Additive dataclass in `intelligence_core/contracts.py`:
- subject_entity_id, canonical_name, entity_type, status, confidence
- supporting_segment_ids, supporting_fact_ids, supporting_evidence_ids
- resolution_method, relationship, aliases
- affected_entities (separate field per §12)
## §15 Subject_entity BEFORE → AFTER (371 NEW IOs)
| Status | V47B (BEFORE) | V48 (AFTER) | Delta |
|---|---|---|---|| `CONFIRMED` | 49 | 14 | -35 || `AMBIGUOUS` | 0 | 10 | +10 || `NOT_FOUND` | 322 | 347 | +25 |## §11 Publisher Firewall Verification
- Firewall violations: **0** (required: 0)
- Publisher CONFIRMED + Subject NOT_FOUND: ACCEPTED (per §11)
- Publisher CONFIRMED + Subject CONFIRMED (independent event-local evidence): ACCEPTED
- Publisher NEVER promotes subject_entity
## §12 Affected Entity Separation
- IOs with affected_entities: **2**
- Total affected entities stored separately: **3**
- affected_entity stored SEPARATELY from subject_entity (per §12)
## §16 Forensic Reason Classification
| Reason | Count |
|---|---|| `UNCHANGED` | 312 || `RECLASSIFIED_AS_NOT_FOUND` | 40 || `IMPROVED_BY_EVENT_LOCAL_RESOLUTION` | 15 || `RECLASSIFIED_AS_AMBIGUOUS` | 4 |## §18 40-IO Sample Subject Classification
| Class | Count |
|---|---|| `SUBJECT_CORRECT` | 1 || `SUBJECT_AMBIGUOUS` | 39 || `SUBJECT_INCORRECT` | 0 (required: 0) |## §19-20 Product Value BEFORE → AFTER (40-IO sample)
| Value | V47B (BEFORE) | V48 (AFTER) | Delta |
|---|---|---|---|| `HIGH_VALUE` | 0 | 0 | +0 || `MEDIUM_VALUE` | 32 | 31 | -1 || `LOW_VALUE` | 8 | 9 | +1 || `NOT_USEFUL` | 0 | 0 | +0 |
**Sample REGRESSED:** 1 (required: 0)
## §19 Semantic Readiness
| Readiness | Count | Rate |
|---|---|---|| `SEMANTICALLY_READY` | 5 | 1.3% || `SEMANTICALLY_PARTIAL` | 19 | 5.1% || `SEMANTICALLY_BLOCKED` | 347 | 93.5% |## §21-22 Safety Invariants
| Invariant | Value |
|---|---|| `unsupported_subject_claims` | 0 || `navigation_leakage` | 0 || `malformed_evidence` | 0 || `unresolved_collisions` | 0 || `broken_provenance` | 0 || `publisher_subject_conflicts` | 0 || `subject_entity_role_conflicts` | 0 || `new_facts` | 0 || `new_events` | 0 || `evidence_rewritten` | 0 || `firewall_violations` | 0 || `original_facts_preserved` | True || `original_evidence_preserved` | True || `publisher_subject_separated` | True |## §23 Regression Tests — 248/248 PASS
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS || `intelligence_core.tests.reliability.v46_evidence_context_tests` | 29 V46 | ✅ PASS || `intelligence_core.tests.reliability.v46_1_semantic_claim_forensics_tests` | 6 V46.1 | ✅ PASS || `intelligence_core.tests.reliability.v47_semantic_claim_binding_tests` | 6 V47A | ✅ PASS || `intelligence_core.tests.reliability.v47c_publisher_institution_tests` | 35 V47C | ✅ PASS || `intelligence_core.tests.reliability.v48_subject_entity_tests` | 26 V48 | ✅ PASS |
**Total:** 10/10 modules = 248/248 tests
## §30 Acceptance Gates
| Gate | Passed |
|---|---|| `g1_SubjectEntityV1_implemented` | ✓ || `g2_publisher_subject_affected_roles_separate` | ✓ || `g3_publisher_firewall_passes` | ✓ || `g4_unsupported_subject_claims_zero` | ✓ || `g5_subject_incorrect_in_40_sample_zero` | ✓ || `g6_original_facts_preserved` | ✓ || `g7_original_evidence_preserved` | ✓ || `g8_new_facts_zero` | ✓ || `g9_new_events_zero` | ✓ || `g10_evidence_rewritten_zero` | ✓ || `g11_unresolved_collisions_zero` | ✓ || `g12_broken_provenance_zero` | ✓ || `g13_semantic_readiness_improves_or_safe` | ✗ || `g14_product_value_no_regression` | ✗ || `g15_222_existing_tests_pass` | ✓ || `g16_all_v48_tests_pass` | ✓ || `g17_no_source_expansion` | ✓ || `g18_no_llm` | ✓ || `g19_no_product_integration` | ✓ || `g20_v48_committed_and_pushed` | ✗ || `g21_pr2_updated_unmerged` | ✗ || **all_pass** | **✗** |## Constraints Honored
- NO source expansion (existing 1,034-document corpus only)
- NO LLM, no external AI APIs, no embeddings
- NO product integration (News/Trading/Corporate unchanged)
- NO modification of extract.py / detect.py / structural_parser.py / evidence_selection.py / collision semantics / event taxonomy / publisher institution IDs
- Production modifications limited to: `contracts.py` (additive SubjectEntityV1) + `subject_entity.py` (NEW module)
- NO merge of PR #2
## §27 Artifacts Produced
- `intelligence_core/contracts.py` (additive SubjectEntityV1)
- `intelligence_core/subject_entity.py` (NEW module)
- `intelligence_core/tests/reliability/v48_subject_entity_tests.py` (26 dedicated tests)
- `intelligence_core/tests/reliability/v48_subject_entity_results.json`
- `intelligence_core/tests/reliability/v48_subject_forensics.json`
- `docs/evidence/ROUAA_CORE_V48_SUBJECT_ENTITY_RESOLUTION.md` (this file)
- `docs/evidence/ROUAA_CORE_V48_SUBJECT_ENTITY_AUDIT.html` (40-IO audit)
