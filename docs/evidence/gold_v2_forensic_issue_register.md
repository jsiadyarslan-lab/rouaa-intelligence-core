# GOLD-V2 Forensic Issue Register

## Open Issues

### ISSUE-001: gold-fed-2024-07-25bp — Fact Value Contradicts Evidence

**Status**: RESOLVED — Remediation applied (fact_value corrected to 0)
**Severity**: CRITICAL
**Type**: DATA_DEFECT

**Description**:
The Gold-V2 IO `gold-fed-2024-07-25bp` stores `fact_value = -25` (claiming a 25bp rate cut),
but the evidence excerpt says "voted to maintain the target range" — which is a 0bp change
(no cut). The fact_value directly contradicts the evidence.

**Evidence excerpt**:
"The Federal Open Market Committee voted to maintain the target range for the federal
funds rate at 5-1/4 to 5-1/2 percent."

**Stored fact_value**: -25
**Correct fact_value**: 0 (or the IO should be removed/renamed)

**Provenance trace**:
- Source: `6fcdcade:docs/evidence/ROUAA_GOLD_SET_V2.md` (remote main)
- The value was stored directly in the inline YAML block
- Created by the "Gold Set V2 — Rebuilt Reference Intelligence" commit
- No extraction pipeline produced this value — it was manually entered

**Root cause hypothesis**: Data entry error. The July 2024 FOMC meeting was a hold (0bp).
The -25 value may have been confused with:
- A different meeting (e.g., a 25bp cut at a different date)
- A different central bank
- An intended "what-if" scenario that was accidentally included as fact

**Impact**: This IO cannot serve as a Gold reference. It carries an incorrect fact_value
that contradicts its own evidence excerpt. Any engine reproducing this IO would learn
the wrong fact.

**Recommended remediation** (NOT authorized in this gate):
- Option A: Correct fact_value to 0 and rename io_id to gold-fed-2024-07-0bp
- Option B: Remove this IO from the Gold Set entirely
- Option C: Replace with a different Fed IO (e.g., a real 25bp cut from a different date)

---

### ISSUE-002: gold-bea-2024-09-pce — Measured Entity Semantic Defect

**Status**: RESOLVED — Remediation applied (measured_entity corrected to "PCE spending")
**Severity**: HIGH (non-blocking to fact value, blocking to canonical semantics)
**Type**: SEMANTIC_DEFECT

**Description**:
The Gold-V2 IO `gold-bea-2024-09-pce` stores `measured_entity = "PCE price index
(month-over-month change)"`, but the evidence excerpt describes **PCE spending** —
"Personal consumption expenditures (PCE) increased $54.9 billion, or 0.3 percent."

PCE spending and PCE price index are fundamentally different economic measures:
- PCE spending = how much consumers spent (dollar amount + percentage change)
- PCE price index = how much prices changed (inflation measure)

The 0.3% figure in the evidence refers to the change in PCE spending, not the PCE
price index. The fact_value is numerically correct but attributed to the wrong concept.

**Evidence excerpt**:
"Personal consumption expenditures (PCE) increased $54.9 billion, or 0.3 percent,
in September."

**Stored measured_entity**: "PCE price index (month-over-month change)"
**Correct measured_entity**: "PCE spending (month-over-month change)" or
                            "Personal consumption expenditures (spending change)"

**Provenance trace**:
- Source entity field: `6fcdcade:docs/evidence/ROUAA_GOLD_SET_V2.md` stores
  `entity: Bureau of Economic Analysis` (the source authority, not the measured entity)
- The measured_entity attribution was introduced during role-aware re-issuance
  (commit 34625a5 on recovery) via the `BEA_PCE_CONTRACT` template in
  `intelligence_core/entity_role_contract.py`
- The template maps any io_id containing "pce" to `measured_entity = "PCE price index"`
  without distinguishing between PCE spending and PCE price index

**Root cause**: Template overgeneralization in `entity_role_contract.py`:
```python
BEA_PCE_CONTRACT = EntityRoleContract(
    source_authority="U.S. Bureau of Economic Analysis (BEA)",
    event_subject="Personal Consumption Expenditures (PCE)",
    measured_entity="PCE price index (month-over-month change)",  # ← WRONG: assumes price index
)
```

**Impact**: Any system consuming this IO would believe the 0.3% refers to the PCE
price index (an inflation measure), when it actually refers to PCE spending change.
These are different concepts with different economic meanings.

**Recommended remediation** (NOT authorized in this gate):
- Correct `BEA_PCE_CONTRACT.measured_entity` to "PCE spending (month-over-month change)"
- OR create separate contracts: `BEA_PCE_SPENDING_CONTRACT` and `BEA_PCE_PRICE_INDEX_CONTRACT`
- Add a test that distinguishes PCE spending from PCE price index based on evidence

---

## Summary

| Issue | Severity | Type | Status | Impact |
|---|---|---|---|---|
| ISSUE-001 | CRITICAL | DATA_DEFECT | OPEN | fact_value contradicts evidence |
| ISSUE-002 | HIGH | SEMANTIC_DEFECT | OPEN | measured_entity mislabeling |

Both issues must be remediated before Gold-V2 can become a canonical oracle.
