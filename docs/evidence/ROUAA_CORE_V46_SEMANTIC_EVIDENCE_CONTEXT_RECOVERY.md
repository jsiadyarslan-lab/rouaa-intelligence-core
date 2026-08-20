# ROUAA CORE V46 — SEMANTIC EVIDENCE CONTEXT RECOVERY
**Phase:** V46 SEMANTIC EVIDENCE CONTEXT RECOVERY
**Executed (UTC):** 2026-08-20T20:02:55Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch HEAD before V46:** `a2079c7c691367e86ab8ac89bba48f7d54672eb1`
**NEW IOs:** 371
**Context packages built:** 5023
**Verdict (pending push):** `V46 SEMANTIC EVIDENCE CONTEXT RECOVERY PASSED (pending push)`
## Executive Summary
V46 is **Evidence Context Recovery** — a deterministic context package (EvidenceContextV1) is built around every existing fact's evidence excerpt using V37.2 structural segments. The original excerpt is preserved EXACTLY; broader context is added SEPARATELY as `context_before` / `context_after`. Downstream semantic enrichment (entity / temporal / state) re-audits the broader context and produces honest BEFORE → AFTER deltas.
**Entity CONFIRMED delta:** 57 → 86 (Δ +29)
**Readiness READY delta:** 27 → 58 (Δ +31)
**Sample 40-IO verdicts:** {'UNCHANGED': 25, 'IMPROVED': 15}
## Context Quality Distribution
| Quality | Count | Rate |
|---|---|---|| `CONTEXT_SUFFICIENT` | 2082 | 41.4% || `CONTEXT_PARTIAL` | 984 | 19.6% || `CONTEXT_INSUFFICIENT` | 1957 | 39.0% |## BEFORE / AFTER — Entity Audit (371 NEW IOs)
| Status | V45 (BEFORE) | V46 (AFTER) | Delta |
|---|---|---|---|| `ENTITY_CONFIRMED` | 57 | 86 | +29 || `ENTITY_AMBIGUOUS` | 3 | 14 | +11 || `ENTITY_NOT_FOUND` | 311 | 271 | -40 |## BEFORE / AFTER — Temporal Audit (5 fields)
| Field | V45 CONFIRMED | V46 CONFIRMED | Delta |
|---|---|---|---|| `event_date` | 13 | 44 | +31 || `reference_period` | 88 | 120 | +32 || `effective_date` | 0 | 1 | +1 || `publication_date` | 22 | 22 | +0 || `revision_date` | 0 | 0 | +0 |## BEFORE / AFTER — Semantic Readiness
| Readiness | V45 (BEFORE) | V46 (AFTER) | Delta |
|---|---|---|---|| `SEMANTICALLY_READY` | 27 | 58 | +31 || `SEMANTICALLY_PARTIAL` | 33 | 42 | +9 || `SEMANTICALLY_BLOCKED` | 311 | 271 | -40 |## BEFORE / AFTER — Product Value (40-IO sample)
| Value | V45 (BEFORE) | V46 (AFTER) | Delta |
|---|---|---|---|| `HIGH_VALUE` | 0 | 4 | +4 || `MEDIUM_VALUE` | 33 | 30 | -3 || `LOW_VALUE` | 7 | 6 | -1 || `NOT_USEFUL` | 0 | 0 | +0 |## 40-IO Sample Verdicts
| Verdict | Count |
|---|---|| `UNCHANGED` | 25 || `IMPROVED` | 15 |**Required: REGRESSED = 0** — confirmed.
## Safety Invariants (§11-12)
| Invariant | Value |
|---|---|| `original_facts_preserved` | True || `original_evidence_preserved` | True || `unsupported_entity_claims` | 0 || `unsupported_temporal_claims` | 0 || `unsupported_state_claims` | 0 || `navigation_leakage` | 0 || `malformed_evidence` | 0 || `unresolved_collisions` | 0 || `broken_provenance` | 0 |- **Original facts preserved:** YES (V46 only reads from recovery_corpus_ios.jsonl; never writes to it)
- **Original evidence preserved:** YES (evidence_excerpt is set to the original excerpt exactly; context is added separately)
- **No navigation leakage:** apply_purpose_filter() runs BEFORE build_contexts_for_io()
- **No malformed evidence:** excerpts are byte-for-byte preserved
- **No unsupported claims:** entity/temporal/state auditors report NOT_FOUND / UNKNOWN when signals absent
## Tests
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS || `intelligence_core.tests.reliability.v46_evidence_context_tests` | 29 V46 | ✅ PASS |
**Total:** 6/6 modules = 175/175 tests (PASS)
## Constraints Honored
- NO source expansion (existing 1,034-document corpus only)
- NO LLM, no external AI APIs, no embeddings
- NO product integration (News/Trading/Corporate unchanged)
- NO modification of extract.py, detect.py, structural_parser.py, evidence_selection.py, or event taxonomy
- Production modifications limited to: `intelligence_core/contracts.py` (additive EvidenceContextV1) + `intelligence_core/evidence_context.py` (NEW module)
- NO merge of PR #2
## Artifacts Produced (§20)
- `intelligence_core/contracts.py` (additive EvidenceContextV1 dataclass)
- `intelligence_core/evidence_context.py` (NEW module)
- `intelligence_core/tests/reliability/v46_evidence_context_tests.py` (29 dedicated tests)
- `intelligence_core/tests/reliability/v46_evidence_context_results.json`
- `intelligence_core/tests/reliability/v46_semantic_readiness_results.json`
- `docs/evidence/ROUAA_CORE_V46_SEMANTIC_EVIDENCE_CONTEXT_RECOVERY.md` (this file)
- `docs/evidence/ROUAA_CORE_V46_EVIDENCE_CONTEXT_AUDIT.html` (40-IO BEFORE/AFTER audit)
