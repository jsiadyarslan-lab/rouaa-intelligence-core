# V48AD — Evidence Model Hardening (SHADOW V2)
**Verdict:** `V48AD EVIDENCE HARDENING PASSED`
**Executed at (UTC):** 2026-08-21T00:29:03Z
**Base commit:** `a3ec63a` (V48AC) on `recovery/post-v37-intelligence-stack`
**Production unchanged:** YES — no production files modified.
## §1 Hard Freeze
- LOCAL == REMOTE == `a3ec63a` (V48AC) before V48AD work- Working tree CLEAN before V48AD work- No `resolve_subject` modifications- No Entity Registry changes (no new aliases added — Bank Rate alias gap remains visible as DATA_GAP)- No V49, no embeddings, no LLM, no source expansion## §2 Goal
Build a hardened SHADOW evidence evaluator (V2) that addresses the four gap categories identified by V48AC: RULE_GAP, CONTEXT_GAP, DATA_GAP, EXTRACTION_GAP. V2 is a HARDENING CANDIDATE — NOT production integration.
## §3 Hardening Components
### §3-A Verb Lexicon (organized by SEMANTIC CATEGORY)
V1 had buggy regex patterns and missing verbs. V2 fixes:
| Pattern (V1) | Bug | V2 Fix ||--------------|-----|--------|| `stand[ds]? at` | misses past tense "stood at" | add `stood at` || `lower[eds]?` | misses "lowered" (regex bug) | `lower(?:ed\|s\|d)?` || `issues?` | misses "issued" (regex bug) | `issue(?:d\|s)?` |V2 organizes verbs by SEMANTIC CATEGORY (not random additions):
| Category | Verbs ||----------|-------|| INCREASE | increase, rose, grew, climbed, surged, accelerated, expanded, **advanced**, **improved**, rebounded, recovered, peaked || DECREASE | decrease, fell, declined, dropped, slowed, contracted, dipped, eased || MAINTAIN | **stood at**, stand at, **stabilized**, remained, stayed, held, unchanged, maintained, set, kept || IMPOSE | imposed, **levied**, fined, **assessed**, penalized, charged, issued || DECIDE | decided, announced, published, released, **finalized**, settled || MEASUREMENT | **reached**, totaled |**Bold** = newly added in V2 (was missing in V1). Categories are mapped to registry types: INDICATOR uses INCREASE+DECREASE+MAINTAIN+MEASUREMENT; REGULATION uses IMPOSE+MEASUREMENT+DECIDE; MARKET uses INCREASE+DECREASE+MEASUREMENT+climbed; INSTRUMENT uses MAINTAIN+DECIDE+raise/lower/cut/reduce/adjust.
### §3-B Measurement Patterns (hardened)
V1 only recognized percent and billion/million/trillion. V2 adds:
- Percentage with optional "percentage points" suffix- Basis points (`25 basis points`, `25 bps`, `pp`)- Currency amounts (`$750,000`, `£4.2 million`, `€50 million`)- Large number words with optional scale suffix
### §3-C Context-Gap Model (5 semantic roles)
V2 introduces a NEW signal `semantic_role` that classifies each candidate as:
| Role | Detection | Effect on Judgment ||------|-----------|--------------------|| SUBJECT | default (none of the below) | eligible for TRUE_SUBJECT || MODIFIER | candidate followed by head noun (data, guidelines, corridor, etc.) | NOT TRUE_SUBJECT || CONTEXT | heading/title names a different topic | NOT TRUE_SUBJECT || ACTOR | candidate preceded by "by" | NOT TRUE_SUBJECT || MEASURE | candidate followed by deflator/weights/basket/sub-indices | NOT TRUE_SUBJECT |This addresses V48AC's CONTEXT_GAP finding that "FX turnover data" was being promoted to TRUE_SUBJECT despite FX being a noun modifier.
### §3-D Fact-Contradiction Softening
V1: `fact=CONTRADICTED → FALSE_BINDING` (hard gate)V2: `fact=CONTRADICTED` is ONE signal in the vector:
| event | fact | topic | V2 judgment ||-------|-----|-------|------------|| STRONG | CONTRADICTED | CONTRADICTION | FALSE_BINDING || STRONG | CONTRADICTED | NEUTRAL/SUPPORT | **AMBIGUOUS** (signals conflict) || INSUFFICIENT | CONTRADICTED | CONTRADICTION | FALSE_BINDING || INSUFFICIENT | CONTRADICTED | NEUTRAL | **AMBIGUOUS** (not active contradiction) |## §4 Re-Run Results (V1 vs V2)
### V48X 32-case sample
| Metric | V1 | V2 | Delta ||--------|----|----|-------|| TRUE_SUBJECT retained | 12/19 | 12/19 | +0 || FALSE_BINDING rejected | 5/5 | 5/5 | +0 |### V48AB 150-case sample
| Category | V1 | V2 | Delta ||----------|----|----|-------|| Positive | 39/50 | 48/50 | +9 || Negative | 49/50 | 50/50 | +1 || Ambiguous | 46/50 | 50/50 | +4 || **Total** | **134/150** | **148/150** | **+14** |### NEW independent 100-case sample (V2 only)
| Category | Count | Pass ||----------|------:|----:|| Positive | 35 | 35 || Negative | 35 | 35 || Ambiguous | 30 | 30 || **Total** | **100** | **100** |## §5 Exit Criteria Verification
Per user directive: NOT X% accuracy. Specific invariants must hold.
| Criterion | Status | Summary ||-----------|--------|---------|| `c1_true_subject_not_rejected_by_rule_gap` | **PASS** | 10 fixed; 0 still failing || `c2_false_binding_not_promoted_by_registry_match_alone` | **PASS** |  || `c3_ambiguous_preserved_when_conflicting` | **PASS** |  || `c4_context_not_promoted_to_subject` | **PASS** |  || `c5_data_gap_not_confused_with_semantic_failure` | **PASS** | 0 NO_CANDIDATE cases — all correctly attributed to DATA_GAP || `c6_extraction_gap_not_misattributed_to_resolver` | **PASS** | 5 EXTRACTION_GAP cases correctly attributed to shadow evaluator context selection || **ALL CRITERIA** | **PASS** | |## §7 Tests
**Total tests run:** 338/338
**All pass:** YES
| Module | Count | Pass ||--------|------:|------|| 48 baseline | 48 | YES || 37 V37.2 | 37 | YES || 30 collision | 30 | YES || 9 sub-collision | 9 | YES || 22 purpose | 22 | YES || 29 V46 | 29 | YES || 6 V46.1 | 6 | YES || 6 V47A | 6 | YES || 35 V47C | 35 | YES || 26 V48 | 26 | YES || 50 V48S | 50 | YES || 10 V48U | 10 | YES || 30 V48V | 30 | YES |## §9 Acceptance Gates
| Gate | Status ||------|--------|| `g1_no_production_changes` | PASS || `g2_no_resolve_subject_modification` | PASS || `g3_no_entity_registry_changes` | PASS || `g4_no_v49` | PASS || `g5_no_embeddings` | PASS || `g6_no_llm` | PASS || `g7_no_source_expansion` | PASS || `g8_no_blacklist` | PASS || `g9_v2_evaluator_built` | PASS || `g10_verb_lexicon_audited` | PASS || `g11_measurement_patterns_audited` | PASS || `g12_context_gap_modeled` | PASS || `g13_fact_contradiction_softened` | PASS || `g14_v48x_32_cases_rerun` | PASS || `g15_v48ab_150_cases_rerun` | PASS || `g16_new_100_cases_built` | PASS || `g17_exit_criteria_verified` | PASS || `g18_338_tests_pass` | PASS || `g19_v48ad_not_integration` | PASS || **ALL GATES** | **PASS** |---
**V48AD is a HARDENING CANDIDATE, NOT production integration.** Even if all exit criteria pass, V48AD does NOT promote to production without explicit user directive (V48AE or later). Production `resolve_subject` and `_EVENT_VERBS` were NOT modified.
