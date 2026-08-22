# Fact-Evidence Gate Report

## Population
- Total cases: 480
- Source: golden_corpus_frozen.json (51 IOs, 480 fact/evidence pairs)

## Tool Suggestions (NOT human adjudication)
- LITERAL: 162 (33.8%)
- NORMALIZED_SUPPORTED: 0 (0.0%)
- TABLE_SUPPORTED: 0 (0.0%)
- DERIVED_SUPPORTED: 0 (0.0%)
- UNSUPPORTED: 318 (66.2%)

## Human Adjudication Status
- human_reviewed_n: 0
- pending_human_n: 480
- All cases PENDING_HUMAN

## Systemic Gate (§10)
- Pre-registered threshold: 10%
- human_unsupported_rate: N/A (no human review yet)
- SYSTEMIC_FACT_EVIDENCE_DEFECT: PENDING_HUMAN_REVIEW

## Critical Invariant
```
MACHINE OBSERVATION ≠ HUMAN ADJUDICATION
```

The tool's candidate_support_class is a SHADOW suggestion.
It MUST NOT be silently promoted into a human label.

## Acceptance Conditions (§18)
- [ ] 480-case population reconciled → 480 cases extracted
- [x] All raw case fields present
- [x] Machine suggestions separated from human judgments
- [x] Normalization rules frozen before review (N1-N5)
- [x] 10% systemic threshold frozen before review
- [x] Human review status explicitly tracked (all PENDING)
- [x] No production changes
- [x] Benchmark denominator explicitly reported
- [x] Provenance retained
- [x] Artifacts reproducible

STATUS: PREPARATION_COMPLETE — HUMAN_REVIEW_PENDING
