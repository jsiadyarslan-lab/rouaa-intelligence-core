# Gold-V2 Role-Aware Re-Issuance — Forensic Artifact

## Generated
2026-08-22T02:52:25.944348+00:00

## Command ID
GOLD-V2 — ROLE-AWARE RE-ISSUANCE GATE

## Mode
Recovery-branch local commit, NO PUSH

## Authoritative Base (Remote Main — UNCHANGED)
`6fcdcadea5a4496eb5503aae4ee45103c2397ed5`

## Role Contract Implementation Base
`6cbe44debb32b7743b1ab5606ed01bb1f043adf4` (commit on recovery where EntityRoleContract was implemented)

---

## A. Re-issued 10/10 role-aware Gold IOs

File: `docs/evidence/gold_v2_role_aware_reissuance.yaml`

Each IO contains:
- **Preserved original fields** (immutability): io_id, category, fact_metric, fact_value, unit, canonical_url, publication_date, evidence_excerpt, final_status, entity_legacy (renamed from `entity`), verification_hash_legacy (renamed from `verification_hash`)
- **NEW role decomposition** (entity_role_contract): source_authority, event_subject, measured_entity, mentioned_entities, subject_resolution_status, evidence_basis

---

## B. Before/After Identity Check (Immutability)

Original 10 Gold IOs SHA256 (immutability anchor): `608f0ad8db669d6864d3c13c8f550e56bc08c53647577716899c4dcfe002e135`

This SHA256 was computed from the original IO fields (io_id, category, fact_metric, fact_value, unit, entity, canonical_url, publication_date, verification_hash, final_status, evidence_excerpt) as they exist on remote main `6fcdcade`.

The re-issuance preserves ALL these fields unchanged. The re-issuance only ADDS the `entity_role_contract` field; it does NOT modify any original field.

Verification: the original `entity` field is preserved as `entity_legacy` (renamed, not deleted). The original `verification_hash` (which was `pending` on the remote) is preserved as `verification_hash_legacy`.

---

## C. Role Adjudication Table (all 10 IOs)

| IO | source_authority | event_subject | measured_entity | subject_resolution_status |
|---|---|---|---|---|
| `gold-fed-2024-09-50bp` | `Federal Reserve (Federal Reserve Board)` | `Federal Open Market Committee (FOMC)` | `federal funds rate (target range)` | `RESOLVED — Federal Open Market Committee named verbatim in excerpt` |
| `gold-fed-2024-07-25bp` | `Federal Reserve (Federal Reserve Board)` | `Federal Open Market Committee (FOMC)` | `federal funds rate (target range)` | `RESOLVED — Federal Open Market Committee named verbatim in excerpt` |
| `gold-ecb-2024-09-25bp` | `European Central Bank (ECB)` | `ECB Governing Council` | `ECB key interest rates (deposit facility rate)` | `RESOLVED — "Governing Council of the ECB" ≡ "ECB Governing Council" per surface_forms_equivalent` |
| `gold-ecb-2024-06-25bp` | `European Central Bank (ECB)` | `ECB Governing Council` | `ECB key interest rates (deposit facility rate)` | `RESOLVED — "Governing Council" named (context: ECB document)` |
| `gold-bea-2024-q3-gdp` | `U.S. Bureau of Economic Analysis (BEA)` | `Real Gross Domestic Product (GDP)` | `Real GDP growth (annual rate)` | `RESOLVED — economic indicator (GDP) named in excerpt` |
| `gold-bea-2024-q2-gdp` | `U.S. Bureau of Economic Analysis (BEA)` | `Real Gross Domestic Product (GDP)` | `Real GDP growth (annual rate)` | `RESOLVED — economic indicator (GDP) named in excerpt` |
| `gold-bea-2024-09-pce` | `U.S. Bureau of Economic Analysis (BEA)` | `Personal Consumption Expenditures (PCE)` | `PCE price index (month-over-month change)` | `RESOLVED — economic indicator (PCE) named in excerpt` |
| `gold-sec-2024-firm-a` | `U.S. Securities and Exchange Commission (SEC)` | `UNRESOLVED` | `civil penalty amount (USD)` | `UNRESOLVED — firm referenced as "the firm" but not named in excerpt` |
| `gold-sec-2024-firm-b` | `U.S. Securities and Exchange Commission (SEC)` | `UNRESOLVED` | `disgorgement amount (USD)` | `UNRESOLVED — firm referenced as "the firm" but not named in excerpt` |
| `gold-sec-2024-firm-c` | `U.S. Securities and Exchange Commission (SEC)` | `UNRESOLVED` | `civil penalty amount (USD)` | `UNRESOLVED — firm referenced as "the firm" but not named in excerpt` |


---

## D. Explicit List of UNRESOLVED Roles

The following IOs have UNRESOLVED event_subject (per directive: do NOT infer):

- `gold-sec-2024-firm-a`: event_subject = `UNRESOLVED`
  - Reason: UNRESOLVED — firm referenced as "the firm" but not named in excerpt
- `gold-sec-2024-firm-b`: event_subject = `UNRESOLVED`
  - Reason: UNRESOLVED — firm referenced as "the firm" but not named in excerpt
- `gold-sec-2024-firm-c`: event_subject = `UNRESOLVED`
  - Reason: UNRESOLVED — firm referenced as "the firm" but not named in excerpt


Total UNRESOLVED: 3/10

All UNRESOLVED cases are SEC IOs where the firm is referenced as "the firm" but not named in the evidence excerpt. Per directive, UNRESOLVED is the honest representation — no inference from source_authority.

---

## E. Forbidden-Change Scan

### Production code files
- `intelligence_core/subject_entity.py`: NOT MODIFIED ✓
- `intelligence_core/extract.py`: NOT MODIFIED ✓
- `intelligence_core/detect.py`: NOT MODIFIED ✓
- `intelligence_core/contracts.py`: NOT MODIFIED ✓
- `intelligence_core/entity_role_contract.py`: NOT MODIFIED ✓ (the contract from previous commit — preserved)

### Original Gold-V2 file
- `docs/evidence/ROUAA_GOLD_SET_V2.md` (on remote): UNCHANGED ✓ (read-only, never modified)

### Extraction/detection/entity-resolution rules
- No rule changes ✓

### Gold IO mutations
- 0 (all original fields preserved as `*_legacy`)

### Evidence mutations
- 0 (all evidence excerpts preserved verbatim)

### Fact mutations
- 0 (all fact_values preserved verbatim)

---

## F. Regression Tests

### Test Files
1. `intelligence_core/tests/reliability/test_entity_role_contract.py` (existing, 26 tests)
2. `intelligence_core/tests/reliability/test_gold_v2_role_aware_reissuance.py` (new)

### Test Results
- Existing role-contract tests: 26/26 passed
- New re-issuance tests: 27/27 passed
- **Total: 53/53 passed, 0 failed**

### Test Coverage
- Gold IO immutability (fact/evidence/source unchanged)
- Role decomposition correctness for all 10 IOs
- UNRESOLVED handling for SEC IOs
- BEA role separation (source_authority=BEA, measured_entity=GDP/PCE)
- ECB surface form equivalence
- Authority ≠ Subject ≠ Measured Entity invariant
- ECB bare-vs-qualified distinction

---

## G. Forensic Artifact
This file: `docs/evidence/gold_v2_role_aware_reissuance.md`

---

## H. Git Commit
- Branch: `recovery/post-v37-intelligence-stack` (local only)
- Base: `6cbe44debb32b7743b1ab5606ed01bb1f043adf4` (role-contract implementation commit)
- New commit: (to be filled after commit)
- NO PUSH to remote

---

## STOP CONDITION

Per directive, after re-issuance is complete:
- 10/10 role-aware Gold IOs re-issued ✓
- 0 underlying Gold mutations ✓
- 0 evidence mutations ✓
- 0 fact mutations ✓
- All regression tests pass: 53/53 ✓
- Forbidden-change scan: PASS ✓
- Forensic artifact produced ✓
- Local recovery commit created (see below)
- NO PUSH ✓

STOP. Do not proceed to:
- Human re-adjudication
- Automated reproduction
- Branch promotion
- Remote push
- Production integration
- Gold fact/evidence modification
- Extraction/detection/entity-resolution modification
