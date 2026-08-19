# ROUAA Core V37.1 Gap Population Reconciliation

**Date**: 2026-08-19  
**Baseline Commit**: `27d9995f342b47653a0590eab4ad0516f98b8700` (V37 Phase 2)  
**Status**: **BLOCKED — POPULATION RECONCILIATION INCOMPLETE**

---

## Executive Summary

This document reconciles the exact 158-case EVIDENCE_SELECTION_GAP population required for V37.1 Evidence Recovery Validation.

**Key Finding**: The 158-case population is NOT directly extractable from existing ledgers as a pre-defined list. It is a DERIVED statistic from V32 deep adjudication analysis.

**Resolution**: We must construct the population by:
1. Identifying all HIGH-confidence FALSE NEGATIVES (FN)
2. Classifying each by gap taxonomy
3. Filtering to those classified as EVIDENCE_SELECTION_GAP

---

## A. Source Ledgers

### A.1 V31 GT Audit Results

**File**: `intelligence_core/tests/reliability/v31_gt_audit_results.json`

| Metric | Value |
|--------|------:|
| Sample size | 1612 |
| TRUE_MATERIAL_FACT | 399 |
| AMBIGUOUS | 788 |
| OUT_OF_SCOPE | 366 |
| NAVIGATION_OVER_CAPTURE | 46 |
| LISTING_OVER_CAPTURE | 13 |

**Key Insight**: The 399 TRUE_MATERIAL_FACT represent facts that ARE valid material facts. Core should have extracted all of them. Some were extracted (TP), some were missed (FN).

### A.2 V32 Adjudication Ledger

**File**: `intelligence_core/tests/reliability/v32_adjudication_ledger.json`

| Metric | Value |
|--------|------:|
| Total records | 788 |
| TRUE_MATERIAL_FACT (V32) | 116 |
| HIGH confidence TRUE_MATERIAL_FACT | 79 |
| REMAINS_AMBIGUOUS | 203 |
| DUPLICATE_SEMANTIC_FACT | 463 |
| LISTING_OVER_CAPTURE | 6 |

**Key Insight**: These 788 records were AMBIGUOUS in V31 but adjudicated in V32. The 116 TRUE_MATERIAL_FACT are facts that Core MISSED (FN).

### A.3 V32 Deep Adjudication Results

**File**: `intelligence_core/tests/reliability/v32_deep_adjudication_results.json`

```json
{
  "true_fn": {
    "v31_true_material_missed": 143,
    "v32_high_true_material_missed": 32,
    "total_high_confidence_fn": 175,
    "gap_taxonomy": {
      "EVIDENCE_SELECTION_GAP": 158,
      "OTHER": 4,
      "ENTITY_CONTEXT_GAP": 2,
      "METRIC_CONTEXT_GAP": 11
    }
  }
}
```

**Key Insight**: 
- 175 HIGH-confidence FN total
- 143 from V31 TRUE_MATERIAL_FACT that Core missed
- 32 from V32 HIGH TRUE_MATERIAL_FACT (subset of 79)
- 158 of these 175 are classified as EVIDENCE_SELECTION_GAP

---

## B. Population Reconstruction Logic

### B.1 Understanding the Numbers

```
Total HIGH-confidence FN = 175
  ├─ V31 TRUE_MATERIAL_FACT missed (FN): 143
  └─ V32 HIGH TRUE_MATERIAL_FACT: 32

Gap Taxonomy of 175:
  ├─ EVIDENCE_SELECTION_GAP: 158
  ├─ METRIC_CONTEXT_GAP: 11
  ├─ ENTITY_CONTEXT_GAP: 2
  └─ OTHER: 4
```

### B.2 The Reconstruction Challenge

**Problem**: No single ledger contains exactly 158 records with `gap_taxonomy: "EVIDENCE_SELECTION_GAP"`.

**Reason**: The gap taxonomy was derived analytically in V32 deep, not stored per-record.

**Solution**: Construct the population from two sources:

1. **V31 TRUE_MATERIAL_FACT that Core missed (143 records)**
   - These are in `v31_gt_audit_results.json` with `disposition: "TRUE_MATERIAL_FACT"`
   - But we need to identify which 143 of 399 were MISSED (not extracted by Core)

2. **V32 HIGH TRUE_MATERIAL_FACT (79 records)**
   - These are in `v32_adjudication_ledger.json`
   - But only 32 of 79 count toward the 175 (the rest overlap with V31 or are not evidence gaps)

### B.3 Overlap Analysis

The 79 V32 HIGH TRUE_MATERIAL_FACT and 143 V31 missed facts may overlap:
- Some V32 HIGH TMF might also be among the 143 V31 missed
- The "32" in V32 deep suggests 79 - 47 overlap = 32 unique V32 additions

**Invariant to verify**:
```
|V31_missed ∪ V32_high_tmf| = 175
|V31_missed| = 143
|V32_high_tmf_unique| = 32
Overlap = 47 (if any)
```

---

## C. Gap Taxonomy Classification

For each of the 175 HIGH-confidence FN, we must classify:

| Taxonomy | Count | Description |
|----------|------:|-------------|
| EVIDENCE_SELECTION_GAP | 158 | Evidence exists but classifier rejected it |
| METRIC_CONTEXT_GAP | 11 | Metric context missing from evidence |
| ENTITY_CONTEXT_GAP | 2 | Entity context missing from evidence |
| OTHER | 4 | Other reasons |

**Forensic Sub-classification for EVIDENCE_SELECTION_GAP (158)**:

| Sub-class | Description |
|-----------|-------------|
| VALUE_AND_CONTEXT_PRESENT | Value + metric context both present in excerpt |
| VALUE_PRESENT_CONTEXT_NEARBY | Value present, context in adjacent sentence |
| METRIC_PRESENT_CONTEXT_NEARBY | Metric present, context nearby |
| UNIT_PRESENT_CONTEXT_NEARBY | Unit present, context nearby |
| ENTITY_PRESENT_CONTEXT_NEARBY | Entity present, context nearby |
| TRUE_INSUFFICIENT_CONTEXT | Context genuinely insufficient |
| NAVIGATION_UI | Navigation/UI filtering issue |
| OTHER | Other evidence selection issues |

---

## D. Reconstruction Status

### D.1 What We Have

| Source | Records | Status |
|--------|--------:|--------|
| V31 TRUE_MATERIAL_FACT | 399 | ✅ Available |
| V32 HIGH TRUE_MATERIAL_FACT | 79 | ✅ Available |
| V32 deep aggregate stats | 1 summary | ✅ Available |

### D.2 What We Need

| Requirement | Status |
|-------------|--------|
| Identify 143 V31 missed facts | ❌ Not directly available |
| Identify 32 V32 unique HIGH TMF | ❌ Not directly available |
| Per-record gap taxonomy | ❌ Not available |
| Forensic sub-classification | ❌ Not available |
| Exact 158-case ledger | ❌ Must be constructed |

### D.3 Construction Plan

**Step 1**: Extract all V31 TRUE_MATERIAL_FACT (399 records)

**Step 2**: Determine which 143 were MISSED by Core
- Cross-reference with Core extraction results
- Facts not extracted = FN (missed)

**Step 3**: Extract all V32 HIGH TRUE_MATERIAL_FACT (79 records)

**Step 4**: Deduplicate V31 missed ∪ V32 HIGH TMF
- Remove overlaps using canonical fact identity (gt_fact_id)

**Step 5**: Classify each record by gap taxonomy
- Use evidence analysis heuristics
- Assign EVIDENCE_SELECTION_GAP, METRIC_CONTEXT_GAP, etc.

**Step 6**: Filter to EVIDENCE_SELECTION_GAP only
- Should yield exactly 158 records

**Step 7**: Add forensic sub-classification
- Analyze evidence excerpts for each of 158

**Step 8**: Create machine-readable ledger
- `v37_1_evidence_selection_gap_ledger.json`

---

## E. Invariant Checks

Before declaring reconstruction complete:

| Invariant | Required | Current |
|-----------|---------:|--------:|
| Total HIGH-confidence FN | 175 | TBD |
| EVIDENCE_SELECTION_GAP | 158 | TBD |
| Unique gt_fact_ids | 158 | TBD |
| All records have V31 or V32 lineage | 158/158 | TBD |
| No duplicate canonical identities | 0 | TBD |
| Sum of gap taxonomy = 175 | 175 | TBD |

---

## F. Machine-Readable Ledger Schema

The reconstructed ledger will have this schema:

```json
{
  "population": "V37.1_EVIDENCE_SELECTION_GAP",
  "version": "1.0",
  "denominator": 158,
  "source_derivation": {
    "v31_true_material_missed": 143,
    "v32_high_true_material_missed": 32,
    "overlap_removed": 0,
    "gap_taxonomy_filtered": 17
  },
  "records": [
    {
      "gt_fact_id": "gtf-XXXX",
      "document_id": "doc-XXXX",
      "source_id": "XXX",
      "metric": "XXX",
      "value": "X.X",
      "raw_value": "...",
      "language": "en/de/etc",
      "v31_disposition": "TRUE_MATERIAL_FACT",
      "v32_disposition": "TRUE_MATERIAL_FACT",
      "confidence": "HIGH",
      "gap_taxonomy": "EVIDENCE_SELECTION_GAP",
      "forensic_subclass": "VALUE_AND_CONTEXT_PRESENT",
      "evidence_excerpt": "...",
      "lineage": ["V31", "V32"]
    }
  ]
}
```

---

## G. Next Steps

1. **Execute reconstruction script** to build the 158-case ledger
2. **Verify all invariants** pass
3. **Create governance artifact** (this document, updated)
4. **Create machine-readable ledger** (`v37_1_evidence_selection_gap_ledger.json`)
5. **Run evidence recovery experiment** on the exact 158 cases
6. **Report baseline vs candidate** comparison

---

## H. Verdict

**CORE V37.1 BLOCKED — GAP POPULATION NOT RECONCILED**

The exact 158-case EVIDENCE_SELECTION_GAP population must be explicitly constructed before V37.1 Evidence Recovery Validation can proceed.

**Blocker Type**: Data reconstruction required (not a code issue)

**Estimated Effort**: 1-2 hours to build reconstruction script and verify invariants

**Risk**: Low — source data exists, requires analytical reconstruction

---

## Appendix A: Source File Locations

| File | Path |
|------|------|
| V31 GT Audit | `intelligence_core/tests/reliability/v31_gt_audit_results.json` |
| V32 Adjudication Ledger | `intelligence_core/tests/reliability/v32_adjudication_ledger.json` |
| V32 Deep Results | `intelligence_core/tests/reliability/v32_deep_adjudication_results.json` |
| V37 Phase 2 Results | `intelligence_core/tests/reliability/v37_evidence_recovery_results.json` |
| V37 Plan | `docs/evidence/ROUAA_CORE_EVIDENCE_RECOVERY_AND_SEMANTIC_ENRICHMENT_V37.md` |

## Appendix B: Related Documents

- V36 Coverage Audit: `docs/evidence/ROUAA_CORE_INTELLIGENCE_OUTPUT_COVERAGE_AUDIT_V36.md`
- Canonical Contract V1: `docs/architecture/ROUAA_CORE_CANONICAL_INTELLIGENCE_CONTRACT_V1.md`
- Semantic Enrichment Contract (proposed): `docs/architecture/ROUAA_CORE_SEMANTIC_ENRICHMENT_CONTRACT_V1.md`
