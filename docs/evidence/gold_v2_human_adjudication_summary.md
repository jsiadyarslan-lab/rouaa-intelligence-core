# GOLD-V2 Human Adjudication Summary

## Timestamp
2026-08-22T03:48:43.468771+00:00

## Reviewer
Independent human adjudicator (not the coding/execution agent)

## Population
10 Gold-V2 IOs

## Verdict Distribution

| Verdict | Count | IOs |
|---|---|---|
| CONFIRMED_VALID | 4 | gold-fed-2024-09-50bp, gold-bea-2024-q3-gdp, gold-bea-2024-q2-gdp, gold-sec-2024-firm-a, gold-sec-2024-firm-c |
| CONFIRMED_VALID_WITH_NOTE | 1 | gold-ecb-2024-06-25bp |
| CONFIRMED_VALID_WITH_SCOPE_NOTE | 1 | gold-sec-2024-firm-b |
| INVALID_GOLD | 1 | gold-fed-2024-07-25bp |
| SEMANTIC_MEASUREMENT_DEFECT | 1 | gold-bea-2024-09-pce |

## Critical Findings

### Finding 1: gold-fed-2024-07-25bp — FACT_VALUE_CONTRADICTS_EVIDENCE
- **Evidence**: "voted to maintain the target range" (0bp)
- **fact_value**: -25 (claims 25bp cut)
- **Verdict**: INVALID_GOLD
- **Root cause**: Data entry error in Gold Set V2 generation
- **Forensic trace**: Value stored directly in ROUAA_GOLD_SET_V2.md at commit 6fcdcade

### Finding 2: gold-bea-2024-09-pce — SEMANTIC_MEASUREMENT_DEFECT
- **Evidence**: "PCE increased $54.9 billion, or 0.3 percent" (PCE spending)
- **measured_entity**: "PCE price index (month-over-month change)" (wrong concept)
- **Verdict**: SEMANTIC_MEASUREMENT_DEFECT
- **Root cause**: Template mapping in entity_role_contract.py assumes "PCE" = price index
- **Forensic trace**: Introduced during role-aware re-issuance at commit 34625a5

### Finding 3: SEC UNRESOLVED discipline — EXEMPLARY
- All 3 SEC IOs correctly maintain event_subject = UNRESOLVED
- Engine refused to infer firm names from URL, registry, or memory
- This is the correct institutional behavior

## Canonical Oracle Status

```
HUMAN_REVIEW_COMPLETE_FORENSIC_REMEDIATION_REQUIRED
```

The Gold-V2 set is NOT canonical. Two defects must be remediated before the set
can serve as a canonical oracle for automated reproduction.

## Not a Score

This adjudication does NOT produce a "Core accuracy = 80%" metric.
It produces a defect taxonomy:
- 1 data defect (fact_value contradicts evidence)
- 1 semantic defect (measured_entity mislabeling)
- 3 exemplary UNRESOLVED cases
- 5 fully valid cases
- 2 valid with notes

The value of this adjudication is in the defect register, not in a percentage.
