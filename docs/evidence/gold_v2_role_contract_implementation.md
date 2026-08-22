# Gold-V2 Role Contract Implementation — Forensic Artifact

## Generated
2026-08-22T02:45:38.728105+00:00

## Command ID
GOLD-V2-ROLE-CONTRACT-IMPLEMENTATION-GATE

## Mode
CONTROLLED RECOVERY-BRANCH MUTATION

## Authoritative Base (Remote Main — UNCHANGED)
`6fcdcadea5a4496eb5503aae4ee45103c2397ed5`

## Working Base (Recovery Tip Before Implementation)
`ea6abd5dfaf2762c6d20bab8302502e8046095c3`

## New Commit (Recovery Branch — Local Only, NOT Pushed)
To be filled after amend.

## Branch
`recovery/post-v37-intelligence-stack` (local commit, no push to remote)

---

## Implementation Note — Test Bug Fix

During initial implementation, one over-specified test pair was included:
- `("Governing Council", "ECB Governing Council")` — INCORRECT
  - The bare phrase "Governing Council" is ambiguous (could be any central bank's council)
  - The contract correctly REJECTS this equivalence (token sets differ)
  - The test was wrong; the contract was right

Fix applied:
- Removed the over-specified pair from `ECB_SURFACE_FORM_EQUIVALENCE_PAIRS`
- Added a NEGATIVE test `test_bare_governing_council_not_equivalent_to_ecb_qualified`
  that explicitly verifies the contract correctly rejects this false equivalence

This proves the contract distinguishes:
- Equivalent surface forms (e.g., "ECB Governing Council" == "Governing Council of the ECB")
- From non-equivalent bare phrases (e.g., "Governing Council" != "ECB Governing Council")

---

## Contract Definition

The contract is defined in `intelligence_core/entity_role_contract.py`. 
It defines three independent semantic roles for entities in IntelligenceObjects:

### Critical Semantic Rule
```
source_authority != event_subject != measured_entity
```

### Roles

| Role | Definition | Example |
|------|------------|---------|
| `source_authority` | Institution responsible for issuing the document/source | "U.S. Bureau of Economic Analysis (BEA)" |
| `event_subject` | Entity to which the event itself is attributed. MUST be UNRESOLVED when the evidence does not identify it. NEVER infer from source_authority. | "Federal Open Market Committee (FOMC)" or "UNRESOLVED" |
| `measured_entity` | Entity/metric actually measured or represented by the fact | "Real GDP growth (annual rate)" or "civil penalty amount (USD)" |
| `mentioned_entities` | All named entities in the evidence excerpt | ["Federal Reserve", "Committee"] |

### Special Cases (from adjudication)

- **SEC IO8/9/10**: `source_authority=SEC`, `event_subject=UNRESOLVED` (firm not named in evidence), `measured_entity=penalty`
- **BEA IO5/6/7**: `source_authority=BEA`, `event_subject=economic indicator`, `measured_entity=GDP/PCE`
- **ECB IO3**: surface form equivalence (`"ECB Governing Council" == "The Governing Council of the ECB"`) via token-set normalization, NOT substring matching

---

## Files Created (Additive Only — No Modifications to Existing Production Code)

1. `intelligence_core/entity_role_contract.py` — contract schema definition
2. `intelligence_core/tests/reliability/test_entity_role_contract.py` — contract-level tests
3. `docs/evidence/gold_v2_role_contract_implementation.md` — this forensic artifact

---

## Tests

### Test File
`intelligence_core/tests/reliability/test_entity_role_contract.py`

### Test Classes

1. `TestRoleContractIndependence` — verifies `source_authority != event_subject != measured_entity`
2. `TestECBSurfaceFormEquivalence` — verifies ECB IO3 surface form equivalence (including negative test for bare phrase)
3. `TestContractValidation` — verifies contract validation methods
4. `TestForbiddenConflation` — verifies the contract does NOT perform forbidden conflation

### Test Results (after fix)
- Total tests: 26
- Passed: 26
- Failed: 0
- Status: ALL PASS ✓

---

## Forbidden Changes — Verification

### Production Code Files (MUST NOT be modified)
- `intelligence_core/subject_entity.py`: NOT MODIFIED ✓
- `intelligence_core/extract.py`: NOT MODIFIED ✓
- `intelligence_core/detect.py`: NOT MODIFIED ✓
- `intelligence_core/contracts.py`: NOT MODIFIED ✓

### Gold IOs (MUST NOT be modified)
- Gold IO changes: 0 ✓

### Evidence Excerpts (MUST NOT be modified)
- Evidence changes: 0 ✓

### Fact Values (MUST NOT be modified)
- Fact changes: 0 ✓

### Extraction/Detection/Entity-Resolution Rules (MUST NOT be modified)
- Rule changes: 0 ✓

---

## Forbidden Actions — Verified NOT Performed

- ✓ No push to main
- ✓ No push to remote (local commit only)
- ✓ No main branch modification
- ✓ No authoritative remote mutation
- ✓ No original Gold-V2 IO modification
- ✓ No evidence excerpt modification
- ✓ No fact_value modification
- ✓ No extraction-rule changes
- ✓ No event detection rule changes
- ✓ No entity-resolution implementation
- ✓ No LLM / embeddings
- ✓ No V49
- ✓ No AMQP
- ✓ No benchmark rerun
- ✓ No automated reproduction
- ✓ No re-issuance of Gold IOs (deferred to next gate)

---

## STOP CONDITION

Per directive, after the implementation artifact and commit are verified,
STOP. Do not proceed automatically to Gold-V2 re-issuance.

Status: **STOPPED — awaiting regulator review of this artifact before
the next gate (Gold-V2 Re-issuance) is authorized.**
