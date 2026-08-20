# ROUAA CORE RECOVERY — CANONICAL SEMANTIC ENRICHMENT
**Phase:** ROUAA CORE RECOVERY — CANONICAL SEMANTIC ENRICHMENT
**Executed (UTC):** 2026-08-20T18:57:04Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Enrichment time:** 0.1s
**NEW IOs enriched:** 371
## Executive Summary
All NEW IOs from Phase B are enriched with deterministic, evidence-backed semantic fields. UNKNOWN is a first-class value — when a field cannot be derived from evidence, it is explicitly set to UNKNOWN rather than invented.
**Entity found rate:** 100.0%
**Temporal complete rate:** 0.5%
**Headline supported rate:** 100.0%
## Entity Coverage
| Status | Count | Rate |
|---|---|---|| `ENTITY_FOUND` | 371 | 100.0% || `ENTITY_AMBIGUOUS` | 0 | 0.0% || `ENTITY_MISSING` | 0 | 0.0% |## Temporal Coverage
| Field | Count | Rate |
|---|---|---|| Publication date found | 20 | 5.4% || Reference period found | 67 | 18.1% || Both (complete) | 2 | 0.5% || Either (partial) | 83 | 22.4% || Neither (none — explicitly reported as UNKNOWN) | 286 | 77.1% |## Event State Distribution
| State | Count | Rate |
|---|---|---|| `UNKNOWN` | 355 | 95.7% || `NEW` | 11 | 3.0% || `REVISED` | 5 | 1.3% |## Specific Headline Coverage
| Field | Count | Rate |
|---|---|---|| Specific (supported by evidence) | 371 | 100.0% || UNKNOWN (not derivable) | 0 | 0.0% |## Safety (§10 directive)
| Field | Value |
|---|---|| `unsupported_semantic_claims` | 0 (required: 0) || `broken_provenance` | 0 (required: 0) || `entity_ambiguity_reported` | True || `temporal_absence_reported` | True || `event_state_uncertainty_reported` | True |## Safety Gates
| Gate | Passed |
|---|---|| `unsupported_semantic_claims_zero` | ✓ || `broken_provenance_zero` | ✓ || `entity_ambiguity_reported_not_hidden` | ✓ || `temporal_absence_reported_not_invented` | ✓ || `event_state_uncertainty_reported_not_invented` | ✓ || `all_tests_pass` | ✓ || **all_pass** | **✓** |## Regression
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS |
**Total:** 5/5 modules = 146/146 tests
## Enrichment Strategy
Every semantic field is derived DETERMINISTICALLY from the IO's existing evidence — its `source_name`, `doc_url`, `facts[].excerpt`, `evidence[].excerpt`. No external web data. No LLM. No embeddings.
**UNKNOWN is a first-class value.** When a field cannot be derived from evidence (e.g., `effective_date` is not mentioned in any excerpt), the field is set to `UNKNOWN` and explicitly reported. Nothing is invented.
**Provenance is preserved.** Every derived field retains the `fact_ids` and `evidence_ids` it was derived from in the `provenance` sub-object.
