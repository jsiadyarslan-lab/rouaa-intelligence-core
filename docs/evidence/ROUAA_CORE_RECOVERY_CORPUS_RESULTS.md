# ROUAA CORE RECOVERY — FULL EXISTING-CORPUS MEASUREMENT
**Phase:** ROUAA CORE RECOVERY — FULL EXISTING-CORPUS MEASUREMENT
**Executed (UTC):** 2026-08-20T18:54:29Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Extraction time:** 27.31s
## Executive Summary
Full existing-corpus measurement on the current `v3_corpus_store`. All 1,034 documents processed end-to-end through the recovered segment-purpose filter, V37.2 structural parser, refined + expanded fact patterns, and event detection.
Numbers below are the **current reproducible canonical state** — NOT extrapolated, NOT claimed from historical V38–V44 runs.
**Total IOs emitted:** 406
**Pre-existing IOs:** 35
**NEW IOs:** 371
**Unique NEW io_ids:** 371
## Terminal Accounting
Required invariant: `sum(terminal_accounting) == total_documents`.
| Category | Count |
|---|---|| `SUCCESS_NO_FACTS` | 622 || `SUCCESS_WITH_FACTS` | 406 || `UNSUPPORTED` | 6 || **TOTAL** | **1034** || Total documents in store | 1034 || Invariant holds | True |## Segment Purpose Statistics
Aggregate counts across all parsed segments of all documents.
| Purpose | Count |
|---|---|| `SUBSTANTIVE` | 103832 || `NAVIGATION` | 30 || `AMBIGUOUS` | 16185 |## NEW IOs by Event Type
| Event Type | Count |
|---|---|| `monetary_policy_decision` | 136 || `statistical_release` | 134 || `regulatory_enforcement` | 92 || `market_statistic_release` | 8 || `earnings_release` | 1 |## NEW IOs by Source (Top 15)
| Source | Count |
|---|---|| `bank-of-england` | 57 || `bea` | 41 || `euronext` | 30 || `nbu-ukraine` | 25 || `ecb-stat` | 24 || `boc` | 20 || `cbbh-bosnia` | 19 || `nsi-bulgaria` | 15 || `ecb` | 10 || `esma` | 10 || `cbk-kenya` | 10 || `fca` | 8 || `cso-ireland` | 8 || `treasurydirect-us` | 6 || `cbj-jordan` | 6 |## Core Invariants
| Field | Value |
|---|---|| `total_documents_in_store` | 1034 || `total_ios_emitted` | 406 || `pre_existing_io_count` | 35 || `new_io_count` | 371 || `new_io_unique_id_count` | 371 || `new_io_duplicate_id_count` | 0 || `new_io_orphan_count` | 0 || `new_ios_have_all_fields` | True |## Regression: V37.2 + Recovery Tests
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS |
**Total:** 5/5 modules = 146/146 tests (124 V37.2 + 22 recovery-purpose)
## Quality Gates
| Gate | Passed |
|---|---|| `invariant_terminal_sum_matches_total` | ✓ || `new_ios_have_all_fields` | ✓ || `no_orphan_ioss` | ✓ || `no_duplicate_io_ids` | ✓ || `all_tests_pass` | ✓ || `navigation_leakage_zero` | ✓ || `unresolved_collisions_zero` | ✓ || `broken_provenance_zero` | ✓ || **all_pass** | **✓** |## Failure Samples
No failures recorded.
## Artifacts Produced
- `docs/evidence/ROUAA_CORE_RECOVERY_CORPUS_RESULTS.md`- `intelligence_core/tests/reliability/recovery_corpus_results.json`- `intelligence_core/tests/reliability/recovery_corpus_ios.jsonl`## Constraints Honored
- No sources added (existing 1,034-document corpus only)
- No LLM, no external inference APIs
- No extraction / collision / event taxonomy modifications
- No `main` branch modifications (recovery branch only)
- 124/124 V37.2 + 22/22 recovery-purpose tests pass
