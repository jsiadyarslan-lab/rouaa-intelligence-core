# V48 480-Case Evidence Reconstruction Report

## Generated
2026-08-22T09:06:47.952910+00:00

## Source
- Original commit: `94bb47ef7741cdc3a88b8d0d1d7300831d8c90b2`
- Original dataset: v48_480case_adjudication_dataset.json (UNTOUCHED)
- Reconstructed dataset: v48_480case_adjudication_dataset_reconstructed.json

## Recovery Chain
```
case → evidence_segment_id → v3_corpus_store/evidence.jsonl
     → representation_id → v3_corpus_store/representations.jsonl
     → raw_location → blob store → FULL document content
     → find fact_value → extract contextual evidence
```

## Recovery Statistics

| Metric | Count |
|---|---|
| Total cases | 480 |
| Resolved via evidence store | 178 |
| Resolved via representation | 178 |
| Resolved via blob | 178 |
| Unresolved | 0 |
| Evidence changed (recovered ≠ original) | 432 |
| Fact found in recovered evidence | 178 |
| Original 120-char truncation | 455 |

## Quality Audit (12 Metrics)

1. Total cases: 480 (expected 480) ✓
2. Cases with evidence_segment_id: 480
3. Cases resolved to canonical evidence: 480
4. Cases unresolved: 0
5. Cases with 120-char truncation: 455
6. Cases where recovered differs: 432
7. Cases where fact_value in recovered: 211
8. LITERAL + literal_match=false: 45 (artifact inconsistency)
9. UNSUPPORTED + recovered contains fact_value: 120 (NOT proof of failure)
10. Duplicate evidence_segment_id: 0
11. Resolution failures by IO: 0
12. Resolution method distribution: {'BLOB_RECOVERED': 178, 'FROZEN_CORPUS_CHAIN': 302}

## Critical Notes

- The original 480-case dataset is UNTOUCHED
- The reconstructed dataset is a NEW artifact
- All human_support_class remain PENDING_HUMAN
- All candidate_support_class remain unchanged (original machine labels)
- No production code changes
- No population changes (same 480 cases, same IDs)
- No normalization rule changes (N1-N5 frozen)
- No threshold changes (10% frozen)

## Machine Label Integrity

Original machine labels (candidate_support_class) were NOT recomputed.
They are preserved as-is from the original dataset.

The LITERAL + literal_match=false inconsistency (45 cases) is reported
as an artifact generation issue, not a classifier defect.

The UNSUPPORTED + recovered evidence contains fact_value (120 cases) is
reported as requiring later adjudication, NOT as proof of machine failure.
