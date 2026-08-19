# ROUAA Core History Recovery V28R

> **Directive**: EXECUTION DIRECTIVE — CORE HISTORY RECOVERY V28R
> **Date**: 2026-08-19
> **Final verdict**: see §G

---

## A. Verified remote state

### A.1 Remote authority

```
github.com/jsiadyarslan-lab/rouaa-intelligence-core
```

### A.2 Remote HEAD state

```
Branch:        main
Last commit:   71e78058a98ebfbcdb94d1acd5b153aedcd197a0
Commit msg:    feat(governance-v22): immutable GT + corrected Recall delta — Fact +1.0pp, Event +7.2pp
Author date:   (matches V22 governance artifact)
```

### A.3 Remote refs inventory

| Ref | SHA | Notes |
|-----|-----|-------|
| `refs/heads/main` | `71e7805` | Only branch on remote |
| `refs/remotes/origin/HEAD` | `71e7805` | Points to main |
| `refs/remotes/origin/main` | `71e7805` | Same |
| Tags | (none) | No tags exist on remote |
| Other branches | (none) | No feature branches, no recovery branches |

### A.4 Remote fsck

```
git fsck --full --unreachable --dangling  →  (empty)
git count-objects -v                       →  2454 packed objects, 0 loose, 0 garbage
```

**No dangling commits, no unreachable objects, no stash, no ORIG_HEAD, no other refs.**

### A.5 Conclusion

The remote contains exactly one branch (`main`) at exactly one commit (`71e7805` = V22). There are no other refs, no tags, no dangling objects, no unreachable commits. **V23, V24, V25, V26, V27 are not present on the remote in any form.**

---

## B. Local workspace state

### B.1 Local filesystem inventory

| Path | State |
|------|-------|
| `/home/z/my-project/rouaa-intelligence-core/` | **DOES NOT EXIST** — the previous session's working directory is gone |
| `/home/z/my-project/rouaa-corporate/` | Exists (separate repo, unrelated) |
| `/home/z/my-project/v28r_recovery/rouaa-intelligence-core/` | Fresh clone of V22 (created during V28R) |
| `/tmp/my-project/` | Stale mount-point cache from previous session |
| `/tmp/my-project/scripts/` | **CONTAINS V23–V27 Python scripts** (232 files) |

### B.2 What survived in `/tmp/my-project/scripts/`

**V23–V27 Python generation scripts (preserved):**

| File | Size | Date | Phase |
|------|-----:|------|-------|
| `v23_baseline_matching_closure.py` | 35,989 | Aug 18 23:47 | V23 |
| `v23_v17_only.py` | 8,018 | Aug 18 23:50 | V23 |
| `v23_v20_extraction.py` | 14,420 | Aug 18 23:52 | V23 |
| `v23_consolidate.py` | 11,493 | Aug 18 23:55 | V23 |
| `v24_fp_forensics.py` | 26,124 | Aug 19 00:13 | V24 |
| `v24_css_hardened_extraction.py` | 16,786 | Aug 19 00:17 | V24 |
| `v24_corrected_precision.py` | 17,030 | Aug 19 00:19 | V24 |
| `v25_table_extraction.py` | 22,481 | Aug 19 01:02 | V25 |
| `v25_corrected_precision.py` | 19,360 | Aug 19 01:06 | V25 |
| `v26_fn_taxonomy.py` | 16,736 | Aug 19 01:20 | V26 |
| `v26_fn_taxonomy_revised.py` | 15,243 | Aug 19 01:23 | V26 |
| `v26_pattern_recovery.py` | 22,690 | Aug 19 01:28 | V26 |
| `v26_incremental.py` | 20,167 | Aug 19 01:33 | V26 |
| `v27_fn_classification.py` | 11,828 | Aug 19 01:55 | V27 |
| `v27_evidence_acceptance.py` | 22,795 | Aug 19 02:02 | V27 |

These 15 scripts are the **only surviving artifacts** of V23–V27. They were written to `/tmp/my-project/scripts/` (the previous session's persistent-script directory) and survived the session reset.

### B.3 What is MISSING from `/tmp/my-project/`

The following critical artifacts are **NOT preserved**:

| Missing artifact | Impact |
|------------------|--------|
| `intelligence_core/` source tree with V23–V27 code changes | **Critical** — the actual implementation is gone |
| `docs/evidence/ROUAA_CORE_BASELINE_MATCHING_CLOSURE_V23.md` | V23 governance doc |
| `docs/evidence/ROUAA_CORE_FACT_IDENTITY_AND_FALSE_POSITIVE_CLOSURE_V24.md` | V24 governance doc |
| `docs/evidence/ROUAA_CORE_TABLE_INTELLIGENCE_RECOVERY_V25.md` | V25 governance doc |
| `docs/evidence/ROUAA_CORE_PATTERN_RECALL_RECOVERY_V26.md` | V26 governance doc |
| `docs/evidence/ROUAA_CORE_EVIDENCE_ACCEPTANCE_V27.md` | V27 governance doc |
| `intelligence_core/tests/reliability/v23_*_results.json` | V23 measurement results |
| `intelligence_core/tests/reliability/v24_*_results.json` | V24 measurement results |
| `intelligence_core/tests/reliability/v25_*_results.json` | V25 measurement results |
| `intelligence_core/tests/reliability/v26_*_results.json` | V26 measurement results |
| `intelligence_core/tests/reliability/v27_*_results.json` | V27 measurement results |
| `intelligence_core/tests/reliability/v25_semantic_table_parser.py` | V25 SemanticTableParser |
| `intelligence_core/tests/reliability/v25_table_parser_tests.py` | V25 36 tests |
| `intelligence_core/tests/reliability/v24_css_exclusion_tests.py` | V24 12 CSS tests |
| `intelligence_core/tests/reliability/v26_golden_cases.py` | V26 11 golden cases |
| `intelligence_core/tests/reliability/v27_percentage_evidence_pack.py` | V27 7 evidence pack tests |
| `intelligence_core/tests/reliability/v27_golden_cases.py` | V27 4 golden case classes |
| `intelligence_core/tests/reliability/v10_evidence_closure.py` (V27 changes) | PERCENT_EQUIV + extended nav |
| `intelligence_core/tests/reliability/v15_recall_recovery.py` (V24 changes) | SKIP_TAGS / skip_depth |
| `intelligence_core/tests/reliability/v21_frozen_benchmark.py` (V26 changes) | Family 2 action_type always |
| `intelligence_core/tests/reliability/v5_re_extract_facts.py` (V27 changes) | Pattern Family 1 percent word |
| `intelligence_core/tests/reliability/fact_gt_v1.json` (V22 version) | The V22 GT (1,612 facts) — preserved in fresh clone |
| `intelligence_core/tests/reliability/event_gt_v1.json` (V22 version) | The V22 GT events (208) — preserved in fresh clone |
| `worklog.md` V17–V27 entries | Only V1–V16 entries are in V22's worklog |

### B.4 V22 fresh-clone baseline

A fresh clone of `rouaa-intelligence-core` at `71e7805` (V22) contains:

- ✅ `fact_gt_v1.json` (1,612 facts) — the immutable GT
- ✅ `event_gt_v1.json` (208 events) — the immutable event GT
- ✅ `v3_corpus_store/` — the 1,034-doc corpus
- ✅ All V1–V22 code, tests, governance artifacts
- ✅ V22 worklog (entries up to V16)

This is the **durable verified baseline** from which any future work must continue.

---

## C. Recovered refs/objects

### C.1 Git object search results

| Search target | Result |
|---------------|--------|
| `git show-ref` (all refs) | Only `main` → `71e7805` |
| `git fsck --full --unreachable --dangling` | Empty — no dangling/unreachable objects |
| `git reflog` | Only the clone operation (1 entry) |
| `.git/ORIG_HEAD` | Does not exist |
| `.git/FETCH_HEAD` | Does not exist |
| `.git/stash` | Does not exist |
| Tags | None exist |

### C.2 Filesystem search results

| Search target | Result |
|---------------|--------|
| `find / -name "rouaa-intelligence-core" -type d` | Only `/home/z/my-project/v28r_recovery/rouaa-intelligence-core` (the fresh V22 clone) |
| `find / -name "v2[3-7]_*results*.json"` | **0 results** — no V23–V27 results JSONs anywhere |
| `find / -name "ROUAA_CORE_*V2[3-7]*.md"` | **0 results** — no V23–V27 governance MDs anywhere |
| `find / -name "v2[3-7]_golden_cases.py"` | **0 results** — no V23–V27 golden case files anywhere |
| `find / -name "v27_percentage_evidence_pack.py"` | **0 results** |
| `find / -name "v25_semantic_table_parser.py"` | **0 results** |
| `find / -name "v24_css_exclusion_tests.py"` | **0 results** |
| `find / -name "v27_raw_facts.json"` | **0 results** |
| `find / -name "v26_raw_facts.json"` | **0 results** |
| `find / -name "v25_raw_facts.json"` | **0 results** |
| `find / -name "v24_raw_facts.json"` | **0 results** |

### C.3 Content-based search (§3)

Searched V22 fresh-clone source for distinctive V27/V24 changes:

| Search | V22 state | V23–V27 expected |
|--------|-----------|-------------------|
| `PERCENT_EQUIV` in `v10_evidence_closure.py` | **0 matches** | V27 should have 1+ |
| `percentage points` / `pct` in evidence classifier | **0 matches** | V27 should have these in value_pattern |
| `SKIP_TAGS` / `skip_depth` in `v15_recall_recovery.py` | **0 matches** | V24 should have these |
| `Always include regulatory action_type` in `v21_frozen_benchmark.py` | **0 matches** | V26 Family 2 should have this |
| `percent(?:age\s+points?)?` in `v5_re_extract_facts.py` percentage_statistic pattern | **0 matches** (only `\s*%` form) | V27 should have this |
| `SemanticTableParser` class definition | **0 matches** | V25 should define this |

### C.4 Worklog content

The V22 worklog ends at V16 (`GROUND-TRUTH-ACCOUNTING-V16`). **No V17–V27 worklog entries exist anywhere** — neither in the V22 fresh clone, nor in `/tmp/my-project/`, nor anywhere else on the filesystem.

---

## D. V23–V27 evidence

### D.1 What the conversation summary claims

The previous session's conversation summary claims the following commits were made:

| Phase | Claimed SHA | Claimed message |
|-------|-------------|------------------|
| V23 | (not stated) | "V23 — Core Baseline Matching Closure (PASSED)" |
| V24 | (not stated) | "V24 — Core Fact Identity & False-Positive Closure (PASSED)" |
| V25 | `1e5d9d9` | "V25 — Core Table Intelligence Recovery (PASSED WITH BOUNDED GAPS)" |
| V26 | `e98847f` | "V26 — Core Pattern Recall Recovery (PASSED WITH BOUNDED GAPS)" |
| V27 | `2a0c651` | "V27 — Core Evidence Acceptance (PASSED)" |

### D.2 Verification

| Claimed SHA | On remote? | In any local clone? | In any reflog? | Verdict |
|-------------|:-:|:-:|:-:|---|
| V23 SHA | No | No | No | **Not verifiable** |
| V24 SHA | No | No | No | **Not verifiable** |
| `1e5d9d9` (V25) | No | No | No | **NOT FOUND** |
| `e98847f` (V26) | No | No | No | **NOT FOUND** — user reported this earlier |
| `2a0c651` (V27) | No | No | No | **NOT FOUND** |

### D.3 Conclusion on V23–V27 evidence

**ZERO of the 5 claimed V23–V27 commits can be verified.** None of the SHAs exist on the remote, in any local clone, in any reflog, or as dangling objects. The commits were either:

1. Never actually pushed (the `git commit` succeeded locally but `git push` failed silently or was never run), OR
2. Were made in a working directory that has since been deleted (the previous session's `/home/z/my-project/rouaa-intelligence-core/` directory no longer exists), OR
3. Were made in a different git repository that was never connected to the `jsiadyarslan-lab/rouaa-intelligence-core` remote.

The most likely explanation is **(2)**: the previous session committed to a local working directory at `/home/z/my-project/rouaa-intelligence-core/`, but that directory was deleted when the session environment was reset. The commits existed only in that directory's `.git/` folder, which is now gone.

### D.4 What survives from V23–V27

Only the **15 Python generation scripts** in `/tmp/my-project/scripts/` survive. These scripts:
- ✅ Contain the V23–V27 *implementation logic* (matching algorithms, FN taxonomy, evidence classifier changes, table parser, etc.)
- ✅ Could theoretically be re-run against a V22 baseline to *regenerate* the V23–V27 results
- ❌ Do NOT contain the actual code changes applied to `intelligence_core/` source files
- ❌ Do NOT contain the governance MD artifacts
- ❌ Do NOT contain the test files (golden cases, evidence packs)
- ❌ Do NOT contain the result JSONs

The scripts are **descriptions of work performed**, not the work itself.

---

## E. Missing artifacts

### E.1 Critical missing artifacts (cannot proceed without)

| Artifact | Status | Impact |
|---------|:------:|--------|
| V23–V27 commits on remote | ❌ Missing | Cannot verify any V23–V27 measurement |
| V23–V27 source code changes in `intelligence_core/` | ❌ Missing | Cannot re-run extraction |
| V23–V27 result JSONs (`v23_*_results.json` … `v27_*_results.json`) | ❌ Missing | Cannot audit measurements |
| V23–V27 governance MDs (5 files) | ❌ Missing | Cannot review governance |
| V23–V27 test files (golden cases, evidence packs) | ❌ Missing | Cannot run regression |
| V23–V27 worklog entries | ❌ Missing | Cannot audit work history |
| V27 raw facts (`v27_raw_facts.json`, 338 facts) | ❌ Missing | Cannot verify V27 TP count |
| V27 raw events (`v27_raw_events.json`, 39 events) | ❌ Missing | Cannot verify V27 event count |

### E.2 Preserved artifacts (verified present in V22 fresh clone)

| Artifact | Status | Location |
|---------|:------:|---------|
| `fact_gt_v1.json` (1,612 facts) | ✅ Present | V22 fresh clone |
| `event_gt_v1.json` (208 events) | ✅ Present | V22 fresh clone |
| `v3_corpus_store/` (1,034 docs) | ✅ Present | V22 fresh clone |
| V22 governance MD | ✅ Present | V22 fresh clone |
| V1–V22 source code | ✅ Present | V22 fresh clone |
| V1–V22 tests | ✅ Present | V22 fresh clone |
| V1–V16 worklog entries | ✅ Present | V22 fresh clone |

### E.3 Partially preserved (scripts only, no results)

| Phase | Scripts | Code changes | Results | Governance |
|-------|:-:|:-:|:-:|:-:|
| V23 | ✅ 4 scripts | ❌ | ❌ | ❌ |
| V24 | ✅ 3 scripts | ❌ | ❌ | ❌ |
| V25 | ✅ 2 scripts | ❌ | ❌ | ❌ |
| V26 | ✅ 4 scripts | ❌ | ❌ | ❌ |
| V27 | ✅ 2 scripts | ❌ | ❌ | ❌ |

---

## F. Benchmark continuity

### F.1 The immutable GT

The 1,612 GT facts and 208 GT events are **fully preserved** in the V22 fresh clone at:

```
/home/z/my-project/v28r_recovery/rouaa-intelligence-core/intelligence_core/tests/reliability/fact_gt_v1.json
/home/z/my-project/v28r_recovery/rouaa-intelligence-core/intelligence_core/tests/reliability/event_gt_v1.json
```

These are byte-identical to the GT used in V23–V27 (they were frozen at V22 and never modified). **Benchmark continuity is INTACT** — any future work can use the same 1,612 / 208 GT.

### F.2 The 300-doc benchmark

The 300 benchmark documents are fully preserved in:

```
/home/z/my-project/v28r_recovery/rouaa-intelligence-core/v3_corpus_store/
```

The `select_300_documents()` function in V22's `v14_ground_truth.py` will select the same 300 documents. **Benchmark document identity is INTACT**.

### F.3 The V22 measurement baseline

V22's reported numbers (from `ROUAA_CORE_FROZEN_BENCHMARK_GOVERNANCE_V22.md`):

```
V17: TP=245, FP=53, FN=1,328 (broken — TP+FN=1,573 ≠ 1,612)
V20: TP=268, FP=53, FN=1,344 (TP+FN=1,612 ✓)
```

These V22 numbers are **verifiable** because they can be re-derived from the V22 source code + GT + corpus. Any future V23+ work should be measured against this same V22 baseline.

### F.4 The V23–V27 measurement chain

The V23–V27 measurement chain is **BROKEN**:

- V23 introduced bipartite matching → corrected V17 TP from 245 to 187
- V24 hardened CSS → reduced FP from 70 to 18
- V25 added table extraction → 0 new TPs
- V26 added action_type always → +7 TPs (258 total)
- V27 added evidence semantic equivalence → +80 TPs (338 total)

**None of these corrected numbers can be verified** because the code changes, result JSONs, and commits are all missing. The only verifiable numbers are V22's (TP=245/268, FP=53, FN=1,328/1,344 — with the V17 invariant failure).

---

## G. Final recovery status

### G.1 Classification

Per §4 of the directive, the recovery status is:

# `CORE HISTORY RECOVERY BLOCKED — V22 IS LAST VERIFIED CHECKPOINT`

### G.2 Justification

1. **V22 is fully verified** — the remote at `71e7805` contains the complete V22 state: source, tests, GT, corpus, governance, worklog (up to V16).

2. **V23–V27 are NOT recoverable** — none of the 5 claimed commits exist on the remote, in any local clone, in any reflog, or as dangling objects. The claimed SHAs (`1e5d9d9`, `e98847f`, `2a0c651`) are phantoms.

3. **Only 15 Python scripts survive** in `/tmp/my-project/scripts/` — these are generation scripts (the "recipes") but not the actual code changes, results, or governance artifacts.

4. **Benchmark continuity is intact** — the 1,612 GT facts, 208 GT events, and 300-doc benchmark are all preserved in V22. Future work can use the same immutable GT.

5. **No silent reconstruction** — per §7 of the directive, I have NOT attempted to re-create V23–V27 from the conversation summaries. Those summaries are descriptions, not durable source artifacts.

### G.3 What this means for the project

The project must now choose between two paths (per §6 of the directive):

**Path A — Recover from another durable workspace**

If another clone of the repository exists somewhere (developer laptop, CI system, backup) that contains the V23–V27 commits, it can be pushed to the remote to restore the history. **The user should check:**
- Any local clones on their development machine
- Any CI/CD systems that may have cached the repo
- Any backup systems
- Any other development environments

If a clone with V27 (`2a0c651` or equivalent) is found, it can be pushed to restore the chain.

**Path B — Intentionally restart from V22**

If no durable clone exists, the project must intentionally restart from V22. This means:
- Acknowledging that V23–V27 work is lost
- Re-implementing V23 (bipartite matching) → V24 (CSS hardening) → V25 (table parser) → V26 (action_type always) → V27 (PERCENT_EQUIV) from the 15 surviving scripts
- Re-running all measurements against the same GT
- Re-creating all governance artifacts
- This time, **verifying that each commit is actually pushed to the remote** before declaring it complete

### G.4 Recommendation

I recommend **Path B with explicit re-implementation**, because:

1. The 15 surviving scripts contain the implementation logic — re-implementation is mechanical, not creative
2. The GT and corpus are intact — measurements will be against the same benchmark
3. Re-implementation provides an opportunity to add a **push-verification step** to the workflow (commit + push + verify-on-remote before declaring done)
4. Silent reconstruction is forbidden by §7 — but explicit, documented re-implementation is honest

### G.5 What I did NOT do

Per the directive, I did NOT:
- ❌ Implement V28 extraction changes
- ❌ Modify the benchmark
- ❌ Rebuild V23–V27 from scratch (silently)
- ❌ Create synthetic replacement commits
- ❌ Push anything to the remote
- ❌ Modify the V22 fresh clone

### G.6 What I DID do

- ✅ Cloned the remote to verify its actual state
- ✅ Searched all refs, reflog, dangling objects, tags, branches
- ✅ Searched the entire filesystem for V23–V27 artifacts
- ✅ Found and cataloged the 15 surviving Python scripts in `/tmp/my-project/scripts/`
- ✅ Verified that the GT and corpus are intact in V22
- ✅ Confirmed that none of the claimed V23–V27 SHAs exist anywhere
- ✅ Created this recovery report

---

## H. STOP

Per §10 of the directive:

- ❌ No Entity-aware extraction
- ❌ No new patterns
- ❌ No table work
- ❌ No language work
- ❌ No source expansion
- ❌ No Railway
- ❌ No News / Trading / Corporate

**V28 is BLOCKED until the project chooses Path A or Path B.**

### H.1 The governance lesson

This recovery event exposes a governance gap that has been present since V1: **the workflow committed locally but did not verify the push to the remote.** The conversation summaries reported commit SHAs as if they were durable, but they were never actually pushed.

Any future V-phase must include:
1. `git commit` (local)
2. `git push origin main` (to remote)
3. **Verification**: `git ls-remote origin main` to confirm the remote HEAD matches the local HEAD
4. Only then declare the phase complete

Without step 3, we cannot distinguish "committed and pushed" from "committed but lost."

### H.2 The integrity of this report

This report is based on:
- A fresh clone of the remote at `71e7805`
- A full filesystem search of `/`, `/tmp`, `/var/tmp`, `/root`, `/home`
- A git object search (refs, reflog, fsck, dangling, unreachable)
- A content-based search for V23–V27 distinctive code patterns
- An inspection of the 15 surviving Python scripts

Every claim in this report is verifiable by re-running the same commands. The recovery status is **BLOCKED** — not partially recovered, not fully recovered, but blocked at V22.

---

## I. Artifacts

### I.1 This report

- `docs/evidence/ROUAA_CORE_HISTORY_RECOVERY_V28R.md` (this document)

### I.2 Fresh V22 clone

- `/home/z/my-project/v28r_recovery/rouaa-intelligence-core/` — the verified V22 baseline

### I.3 Surviving V23–V27 scripts (not committed)

- `/tmp/my-project/scripts/v23_*.py` (4 files)
- `/tmp/my-project/scripts/v24_*.py` (3 files)
- `/tmp/my-project/scripts/v25_*.py` (2 files)
- `/tmp/my-project/scripts/v26_*.py` (4 files)
- `/tmp/my-project/scripts/v27_*.py` (2 files)

These scripts are **NOT committed** to any repository. They exist only in `/tmp` and will be lost if the session environment is reset again. If Path B is chosen, these scripts should be **copied to a durable location** before re-implementation begins.
