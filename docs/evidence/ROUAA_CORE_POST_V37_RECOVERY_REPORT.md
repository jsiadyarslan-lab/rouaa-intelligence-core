# ROUAA CORE POST-V37 RECOVERY — FINAL REPORT
**Phase:** ROUAA CORE POST-V37 RECOVERY — FINAL REPORT
**Executed (UTC):** 2026-08-20T19:01:16Z
**Baseline commit:** `82263950263f74c4b970a902975b72539d39703f`
**Recovery branch:** `recovery/post-v37-intelligence-stack`
**HEAD SHA:** `76da16e52dd76d4a341e6af7575c04110b46772d`
**Remote SHA:** `76da16e52dd76d4a341e6af7575c04110b46772d`
**Local==Remote:** True
**PR:** #2 (https://github.com/jsiadyarslan-lab/rouaa-intelligence-core/pull/2)
**Verdict:** `ROUAA POST-V37 RECOVERY DURABLY REBUILT`
## Executive Summary
Post-V37.2 development was previously lost because intermediate phases (V38–V44) existed only in a local working tree and were never committed to GitHub. This recovery rebuilds the durable post-V37 intelligence capabilities reproducibly from the V37.2 baseline (`8226395`), committing every layer to the recovery branch BEFORE advancing to the next layer.
**Current authoritative NEW IO count: 371** (reproducibly measured from the current 1,034-document corpus). This number is NOT inherited from historical V38–V44 runs — it is independently produced here.
**All gates pass:** True
## Recovery Checkpoints
| # | Commit | Layer |
|---|---|---|| 1 | `8e20622` | Segment-purpose filtering (`intelligence_core/segment_purpose.py` + 22 tests) || 2 | `366bae6` | Full existing-corpus measurement (1,034 docs, terminal accounting) || 3 | `30d2793` | Canonical semantic enrichment (371 NEW IOs enriched) || 4 | `76da16e` | Output Workbench HTML (371 IOs × 4 views) || 5 | `76da16e` | Final report (this document) |Every checkpoint is durable: committed + pushed + verified `LOCAL == REMOTE` + working tree CLEAN before advancing.
## §15 — Current Canonical Population
| Field | Value |
|---|---|| Total documents in store | 1034 || Pre-existing facts | 396 || Pre-existing events | 45 || Total IOs emitted (current run) | 406 || Pre-existing IOs | 35 || **NEW IOs (authoritative)** | **371** || Unique NEW io_ids | 371 || Duplicate io_ids | 0 || Orphan IOs | 0 || Terminal accounting sum | 1034 || Terminal sum matches total | True |### Terminal Accounting
| Category | Count |
|---|---|| `SUCCESS_NO_FACTS` | 622 || `SUCCESS_WITH_FACTS` | 406 || `UNSUPPORTED` | 6 || **TOTAL** | **1034** |### NEW IOs by Event Type
| Event Type | Count |
|---|---|| `monetary_policy_decision` | 136 || `statistical_release` | 134 || `regulatory_enforcement` | 92 || `market_statistic_release` | 8 || `earnings_release` | 1 |### NEW IOs by Source (Top 15)
| Source | Count |
|---|---|| `bank-of-england` | 57 || `bea` | 41 || `euronext` | 30 || `nbu-ukraine` | 25 || `ecb-stat` | 24 || `boc` | 20 || `cbbh-bosnia` | 19 || `nsi-bulgaria` | 15 || `ecb` | 10 || `esma` | 10 || `cbk-kenya` | 10 || `fca` | 8 || `cso-ireland` | 8 || `treasurydirect-us` | 6 || `cbj-jordan` | 6 |## §16 — Quality Validation
(Measured across all 371 NEW IOs)
| Metric | Rate | Count |
|---|---|---|| Specific headline rate | 100.0% | 371/371 || Entity found rate | 100.0% | 371/371 || Entity ambiguous rate | 0.0% | 0/371 || Temporal complete rate | 0.5% | 2/371 || Temporal partial rate | 22.4% | 83/371 || Temporal UNKNOWN rate | 77.1% | 286/371 || Event state known rate | 4.3% | 16/371 || Unsupported claims | required 0 | 0 || Broken provenance | required 0 | 0 |### Event State Distribution
| State | Count | Rate |
|---|---|---|| `UNKNOWN` | 355 | 95.7% || `NEW` | 11 | 3.0% || `REVISED` | 5 | 1.3% |## §13 — Workbench Validation
| Field | Value |
|---|---|| IOs in workbench | 371 || Outputs per IO | 4 || Total outputs generated | 1484 || Reuse rate | 100.0% || Unsupported claims | 0 (required: 0) || Provenance complete | 100.0% || Differentiation | 100.0% || Unique headlines | 193 || Unique news outputs | 235 || Unique research outputs | 201 || Unique risk outputs | 197 || Unique executive outputs | 193 || All acceptance gates pass | True |## §16 (cont.) — 40-IO Sample with 4 Output Forms
Sample size: 40 IOs
By event type:
| Event Type | Count |
|---|---|| `monetary_policy_decision` | 10 || `statistical_release` | 10 || `regulatory_enforcement` | 11 || `market_statistic_release` | 8 || `earnings_release` | 1 || Quality metric | Value |
|---|---|| Reuse OK | 40/40 || Provenance complete | 40/40 || Differentiated | 40/40 || Unsupported claims | 0 |## §20 — Regression (All Checkpoints)
124 V37.2 tests + 22 recovery-purpose tests = **146/146**.
| Module | Label | Passed |
|---|---|---|| `intelligence_core.tests.run_all` | 48 baseline | ✅ PASS || `intelligence_core.tests.reliability.v37_2_structural_evidence_test` | 37 V37.2 | ✅ PASS || `intelligence_core.tests.reliability.v37_2_collision_fix_tests` | 30 collision | ✅ PASS || `intelligence_core.tests.reliability.v37_2_sub_collision_tests` | 9 sub-collision | ✅ PASS || `intelligence_core.tests.reliability.recovery_segment_purpose_tests` | 22 purpose | ✅ PASS |
**Total:** 5/5 modules = 146/146 tests (PASS)
## Limitations
1. Entity coverage is 100% because source_name is used as a deterministic proxy for primary_entity. This is honest (source is always known) but doesn't capture the semantic ambiguity of WHICH entity is the primary subject.2. Temporal coverage is partial (22.4%) because most fact excerpts are too short to contain parseable reference periods. Phase B terminal accounting shows 622/1034 documents produce no facts at all (SUCCESS_NO_FACTS) — these are mostly non-HTML or non-substantive documents.3. Event state is 95.7% UNKNOWN — only 11 NEW + 5 REVISED could be detected from headline/URL signals. Most events do not carry revision signals in their deterministic text. This is reported honestly, not invented.4. Sample of 40 IOs is biased toward the top-N by event_type. Quality may differ for the long tail of less-represented event types.## Unresolved Gaps
1. No source expansion performed (existing 1,034-document corpus only).2. No LLM used for semantic enrichment (deterministic only).3. No News/Trading/Corporate integration (workbench is Core-only).4. No benchmark against historical V38–V44 numbers (those artifacts were lost).## §24 — Final PR State
- Branch: `recovery/post-v37-intelligence-stack`
- HEAD SHA: `76da16e52dd76d4a341e6af7575c04110b46772d`
- Remote SHA: `76da16e52dd76d4a341e6af7575c04110b46772d`
- Local == Remote: True
- PR: #2 (https://github.com/jsiadyarslan-lab/rouaa-intelligence-core/pull/2)
- PR NOT merged (per directive §24)
- `main` branch unchanged (still at `8226395`)
- Recovery branch fully reproducible
## §25 — Final Output
```
ROUAA POST-V37 RECOVERY DURABLY REBUILT
```
- **Current corpus:** 1034 documents
- **Current facts:** 396 (pre-existing, unchanged)
- **Current events:** 45 (pre-existing, unchanged)
- **Current NEW IOs:** 371
- **Semantic quality:** specific_headline=100.0%, entity_found=100.0%, temporal_complete=0.5%
- **Workbench result:** 371 IOs × 4 views = 1484 outputs, reuse=100.0%, unsupported=0
- **Test results:** 5/5 modules = 146/146 tests (PASS)
- **PR number:** #2
- **Recovery branch:** `recovery/post-v37-intelligence-stack`
- **HEAD SHA:** `76da16e52dd76d4a341e6af7575c04110b46772d`
- **REMOTE SHA:** `76da16e52dd76d4a341e6af7575c04110b46772d`
