# V48AL — Annotation Repair Report

## Summary

9 annotation repairs applied to V48AG independent holdout sample. 3 ontology candidates left OPEN. 10 consistent cases unchanged. 128 non-22 cases unchanged. Production/V2/V2.1 unchanged. 338/338 tests pass.

## 1. Cases Changed (9)

| # | Candidate | Old Label | New Label | Reason |
|---|-----------|-----------|-----------|--------|
| 83 | Gross Domestic Product | AMBIGUOUS | CONTEXT_ONLY | Event "compiled" clearly applies to head noun "statistics"; no secondary target |
| 87 | Consumer Price Index | AMBIGUOUS | CONTEXT_ONLY | Event "revised" clearly applies to head noun "methodology"; no secondary target |
| 89 | Penalty | AMBIGUOUS | CONTEXT_ONLY | Event "outlined" clearly applies to head noun "procedures"; no secondary target |
| 92 | Policy Rate | AMBIGUOUS | CONTEXT_ONLY | Event "scheduled" clearly applies to head noun "decisions"; no secondary target |
| 93 | Unemployment | AMBIGUOUS | CONTEXT_ONLY | Event "released" clearly applies to head noun "statistics"; no secondary target |
| 94 | Consumer Price Index | AMBIGUOUS | CONTEXT_ONLY | Event "analyzed" clearly applies to head noun "sub-indices"; no secondary target |
| 96 | Penalty | AMBIGUOUS | CONTEXT_ONLY | Event "proposed" clearly applies to head noun "revisions"; no secondary target |
| 98 | Inflation | AMBIGUOUS | CONTEXT_ONLY | Event "reaffirmed" clearly applies to head noun "framework"; no secondary target |
| 101 | Consumer Price Index | AMBIGUOUS | CONTEXT_ONLY | Event "updated" clearly applies to head noun "weights"; no secondary target |

## 2. Ontology Candidates (3) — UNCHANGED

| # | Candidate | Label | Status |
|---|-----------|-------|--------|
| 130 | Foreign Exchange | CONTEXT | OPEN_ONTOLOGY_CANDIDATE |
| 131 | Penalty | CONTEXT | OPEN_ONTOLOGY_CANDIDATE |
| 147 | Inflation | CONTEXT | OPEN_ONTOLOGY_CANDIDATE |

## 3. Consistent Cases (10) — UNCHANGED

Cases: #82, #103, #117, #119, #121, #122, #126, #138, #140, #149 — all verified unchanged.

**Note:** Case #115 was incorrectly listed in a prior version of this report. #115 is NOT part of the V48AL-22 identical-dimension population (its dimensions are `modifier, both, weakly_implied, contextual_reference, mixed` — different from the ALL_22 shared dimensions `modifier, head_noun, strongly_implied, contextual_reference, head_noun`). #115 was never repaired and remains unchanged at its original label (AMBIGUOUS). See V48AL Population Reconciliation Gate for details.

## 4. Reconciliation

- Old SHA256: bbc1ac6ccea1c3e7...
- New SHA256: 7fe0616412b27850...
- Files changed: 1 (V48AG pre-reg sample only)
- Cases changed: 9 (only AMBIGUOUS → CONTEXT_ONLY)
- Cases unchanged: 141 (3 ontology + 10 consistent + 128 non-22)
- Production files: 0 modified

## 5. Tests

- 338/338 PASS (all 13 test modules)
- Production/V2/V2.1: verified byte-for-byte unchanged

## 6. Files Modified

| File | Change |
|------|--------|
| intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json | 9 labels repaired + audit trail added |

## 7. Production Files Modified

**0** — production code unchanged.

## 8-11. Git Verification

- Commit SHA: (pending commit)
- Remote SHA: (pending push)
- LOCAL == REMOTE: (pending verification)
- WORKTREE CLEAN: (pending verification)
