# ROUAA CORE RECOVERY — INTELLIGENCE OUTPUT WORKBENCH
**Phase:** ROUAA CORE RECOVERY — OUTPUT WORKBENCH
**Executed (UTC):** 2026-08-20T18:59:22Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**IO population:** 371
**Sample size:** 40
## Executive Summary
Standalone HTML workbench demonstrating that ONE canonical IO produces FOUR institutional outputs (NEWS / RESEARCH / RISK / EXECUTIVE) without re-extracting the source document. All 371 enriched NEW IOs from Phase C are present in the workbench.
**Reuse rate:** 100.0%
**Unsupported claims:** 0 (required: 0)
**Provenance complete:** 100.0%
**Differentiation:** 100.0%
## Reuse Test
| Field | Value |
|---|---|| `ios_tested` | 371 || `outputs_per_io` | 4 || `total_outputs` | 1484 || `reuse_without_extraction` | 371 || `re_extraction_required` | 0 || `reuse_success_rate` | 1.0 |## Output Quality
| Field | Value |
|---|---|| `unsupported_claims` | 0 || `provenance_complete` | 371 || `provenance_rate` | 1.0 || `differentiation` | 371 || `differentiation_rate` | 1.0 |## Output Diversity
| Field | Value |
|---|---|| `unique_headlines` | 193 || `unique_news` | 235 || `unique_research` | 201 || `unique_risk` | 197 || `unique_executive` | 193 |## Sample by Event Type
| Event Type | Count |
|---|---|| `monetary_policy_decision` | 10 || `statistical_release` | 10 || `regulatory_enforcement` | 11 || `market_statistic_release` | 8 || `earnings_release` | 1 |## Acceptance Gates
| Gate | Passed |
|---|---|| `population_verified` | ✓ || `four_outputs` | ✓ || `reuse_100` | ✓ || `re_extraction_zero` | ✓ || `unsupported_zero` | ✓ || `provenance_100` | ✓ || `differentiation` | ✓ || `nav_leakage_zero` | ✓ || `collisions_zero` | ✓ || `broken_provenance_zero` | ✓ || `tests_146` | ✓ || `html_real` | ✓ || **all_pass** | **✓** |## Regression
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS |
**Total:** 5/5 modules = 146/146 tests
## Constraints Honored
- No integration with rouatradingnews or roua-trading (workbench is Core-only)
- No LLM, no external inference APIs
- No sources added (existing corpus only)
- No `main` modification (recovery branch only)
- 124/124 V37.2 + 22/22 recovery-purpose tests pass
