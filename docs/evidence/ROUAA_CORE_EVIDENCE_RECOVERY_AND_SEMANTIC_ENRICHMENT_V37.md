# ROUAA Core Evidence Recovery and Semantic Enrichment V37

> **Directive**: EXECUTION DIRECTIVE — CORE V37 FRESH-SESSION BOOTSTRAP
> **Date**: 2026-08-19
> **Parent**: V36 (5f1df0e)
> **Status**: IN PROGRESS

---

## A. Source of Truth Declaration

Per strategic directive:

```
Conversation memory = context
GitHub repository = source of truth
Evidence artifacts = measurement source of truth
```

**DO NOT rely on:**
- Previous conversation summaries
- Remembered function signatures
- Previously reported KPIs unless reproduced from repository artifacts
- Reconstructed values from chat history

**GitHub + persisted evidence artifacts are the sole source of truth.**

---

## B. Repository State Verification

### B.1 Baseline Confirmation

| Check | Status | Value |
|-------|--------|-------|
| Git HEAD | ✅ | 5f1df0eb2a65147cab0e9a42aad44cde2c746a46 |
| Branch | ✅ | main (origin/main) |
| Remote | ✅ | github.com/jsiadyarslan-lab/rouaa-intelligence-core |
| Working tree | ✅ | Clean |

### B.2 V36 Governance Document

Located: `docs/evidence/ROUAA_CORE_INTELLIGENCE_OUTPUT_COVERAGE_AUDIT_V36.md`

Key findings from V36:
- 9 durable IOs audited (3 monetary + 3 statistical + 3 regulatory)
- All 9 have complete provenance chains (0 broken links)
- All 9 have evidence records
- 8/9 IOs have `temporal_data = None`
- Headlines are generic (`{source} {event_type}`)
- Entity/unit/period not extracted as separate fields

### B.3 V32 Deep Adjudication Result

Located: `intelligence_core/tests/reliability/v32_adjudication_ledger.json`

| Disposition | Count |
|-------------|------:|
| TRUE_MATERIAL_FACT | 116 |
| REMAINS_AMBIGUOUS | 203 |
| DUPLICATE_SEMANTIC_FACT | 463 |
| LISTING_OVER_CAPTURE | 6 |
| **Total** | **788** |

### B.4 V36 Coverage Gap Map

From V36 audit (§J):

| Gap | Priority | Description |
|-----|:--------:|-------------|
| EVIDENCE_SELECTION_GAP | P0 | 158 HIGH-confidence true FN rejected by evidence classifier |
| RECALL_GAP | P0 | Machine-adjudicated Recall 40.19% — 433 FN on GT_V3 |
| EVENT_RECALL_GAP | P0 | Event Recall 20.67% — 165 events missed |
| ENTITY_EXTRACTION | P1 | Entity not separate field — embedded in excerpt |
| TEMPORAL_DATA_COVERAGE | P1 | temporal_data None for 8/9 IOs |
| HEADLINE_QUALITY | P1 | Generic headlines — not editorial |
| UNIT_FIELD | P2 | Unit embedded in raw_value |
| QUALITY_METADATA | P2 | No confidence_score emitted |

---

## C. Current Architecture Reconstruction

### C.1 Core Components (from repository)

| Component | File | Function |
|-----------|------|----------|
| Fact Extraction | `intelligence_core/extract.py` | `extract_facts()` |
| Event Detection | `intelligence_core/detect.py` | `detect_event()` |
| Intelligence Object | `intelligence_core/delivery.py` | `build_intelligence_object()` |
| Evidence Classification | `intelligence_core/tests/reliability/v10_evidence_closure.py` | `classify_evidence_strict()` |
| Evidence Expansion | `intelligence_core/tests/reliability/v10_evidence_closure.py` | `expand_evidence_for_direct()` |
| Persistence | `intelligence_core/cached_store.py` | `CachedStore` |
| HTTP Delivery | `intelligence_core/production_transport.py` | `/v1/intelligence` |

### C.2 Evidence Classifier Contract

From `v10_evidence_closure.py`:

```python
def classify_evidence_strict(fact, excerpt) -> tuple[str, str]:
    # Returns: (classification, reason)
    # classification ∈ {DIRECT, INDIRECT, INSUFFICIENT, INVALID}
```

**DIRECT requirements per metric:**
- `percentage_statistic`: value pattern + context keywords (rate, growth, change, etc.)
- `policy_rate`: value pattern + context (rate, interest, policy, benchmark)
- `action_type`: value pattern + context (order, action, proceeding, etc.)
- `penalty_amount`: $value + context (penalty, fine, settlement, etc.)

**PERCENT_EQUIV semantic equivalence (V27R):**
```
% = percent = percentage = percentage points = pct
```

### C.3 Canonical Intelligence Contract V1

From `docs/architecture/ROUAA_CORE_CANONICAL_INTELLIGENCE_CONTRACT_V1.md`:

**Required fields:**
- io_id, version, event_id, event_version
- event_type, headline
- facts[] (metric, value, raw_value, pattern_ref, excerpt)
- evidence[] (excerpt, provenance_ref)
- chain[] (source_id, document_id, representation_id)

**Optional fields:**
- temporal_data (None for 8/9 IOs)
- supersedes_io_id

**Not present (V37+ candidates):**
- entity (P1)
- unit (P2)
- period (P1)
- quality_metadata/confidence_score (P2)

---

## D. 158-Case Population Verification

### D.1 Source: V32 Adjudication Ledger

Query: HIGH confidence + TRUE_MATERIAL_FACT cases

From repository analysis:
- Total HIGH confidence TRUE_MATERIAL_FACT: **116 cases**
- These are the cases where ground truth says "this is a real fact"
- Of these 116, some were extracted (TP) and some were missed (FN)

### D.2 EVIDENCE_SELECTION_GAP Definition

From V32/V36 documents:
> "158 of 175 HIGH-confidence true FN (90.3%) are EVIDENCE_SELECTION_GAP — the value exists in semantic content with metric + unit context, but Core's evidence classifier rejects the excerpt as INDIRECT or INVALID."

**Gap classes:**
1. Value + context nearby (sentence-level)
2. Context in adjacent sentence
3. Context in paragraph
4. Metric available but pattern mismatch
5. Entity available but not extracted
6. Unit available but embedded
7. Period available but not extracted
8. Genuinely insufficient context

### D.3 Verification Status

⚠️ **CRITICAL**: The exact 158-case population must be reproduced from repository artifacts.

**Action required:** Run forensic query on v32_adjudication_ledger.json to identify:
- Which 158 cases are EVIDENCE_SELECTION_GAP
- What evidence_gap_class each belongs to
- Whether context is recoverable via sentence/paragraph expansion

---

## E. V37 Execution Plan

### Phase 1: Evidence Recovery (P0)

**E.1 Forensic Analysis of 158 Cases**

For each of the 158 EVIDENCE_SELECTION_GAP cases:
1. Locate the document in corpus
2. Extract the value location (DOM position)
3. Measure context availability:
   - Same sentence? (±150 chars)
   - Adjacent sentence? (±300 chars)
   - Same paragraph? (±600 chars)
   - Metric keyword present?
   - Entity name present?
   - Unit present?
   - Period present?

**E.2 Evidence Expansion Enhancement**

Current `expand_evidence_for_direct()` tries:
1. Current excerpt
2. Sentence containing value + adjacent sentences
3. Paragraph containing value
4. Bounded local context (±300 chars)

**V37 improvement:**
- Add TABLE context expansion (for table-based statistics)
- Add HEADING context expansion (for section headers)
- Add cross-sentence pronoun resolution ("it increased" → find antecedent)
- Relax context requirements for HIGH-confidence metrics

**E.3 Safe Recovery Mechanism**

Per directive §8 (Acceptance Gate):
- New true TP > 0
- No new true FP
- Direct Evidence improves
- Fact Recall improves
- Event Precision does not regress
- Existing regression suite remains green

### Phase 2: Semantic Enrichment (P1/P2)

**ONLY AFTER Evidence Recovery passes acceptance gate.**

**E.4 Entity Enrichment**

Extract entity as separate field:
- Company names (SEC enforcement)
- Country names (statistical releases)
- Institution names (central banks)

Contract addition:
```python
@dataclass
class IntelligenceObject:
    entity: Optional[str] = None  # e.g., "SEC", "Eurostat", "Apple Inc."
```

**E.5 Unit/Currency Enrichment**

Extract unit as separate field:
- Percentage (%)
- Currency (USD, EUR)
- Absolute numbers

Contract addition:
```python
@dataclass
class Fact:
    unit: Optional[str] = None  # e.g., "%", "USD million", "bps"
```

**E.6 Temporal Enrichment**

Improve temporal_data coverage:
- Currently 8/9 IOs have None
- Use document metadata (RSS pubDate, HTML time tags)
- Use URL date patterns
- Use filename date patterns

Contract already supports this via `TemporalDataProjection`.

---

## F. Controlled Experiment Design

### F.1 Baseline Measurement

Run V36 audit script:
```bash
python intelligence_core/tests/reliability/v36_output_audit.py
```

Measure:
- TP, FP, FN
- Fact Recall, Fact Precision
- Direct Evidence count
- Event TP/FP/FN

### F.2 Candidate: Evidence Recovery Only

Apply ONLY evidence recovery improvements:
- Enhanced `expand_evidence_for_direct()`
- Relaxed context requirements for HIGH-confidence metrics
- Table/heading context expansion

**Do NOT change:**
- Metric ontology
- Event gate
- Source registry
- Language patterns

### F.3 Comparison

| Metric | Baseline | Candidate | Delta |
|--------|----------|-----------|-------|
| TP | ? | ? | ? |
| FP | ? | ? | ? |
| FN | ? | ? | ? |
| Fact Recall | 40.19% | ? | ? |
| Fact Precision | ? | ? | ? |
| Direct Evidence | ? | ? | ? |
| Event TP | ? | ? | ? |

---

## G. Acceptance Criteria

Per directive §8:

**Evidence Recovery ACCEPTED if:**
- ✅ New true TP > 0
- ✅ No new true FP
- ✅ Direct Evidence improves
- ✅ Fact Recall improves
- ✅ Event Precision does not regress
- ✅ Regression suite green

**Evidence Recovery REJECTED if:**
- ❌ New FP introduced
- ❌ Event Precision regresses
- ❌ Regression failures

---

## H. Required Artifacts

### H.1 Documentation

1. `docs/evidence/ROUAA_CORE_EVIDENCE_RECOVERY_AND_SEMANTIC_ENRICHMENT_V37.md` (this file)
2. `docs/architecture/ROUAA_CORE_SEMANTIC_ENRICHMENT_CONTRACT_V1.md` (new)

### H.2 Machine-Readable Results

JSON result file containing:
```json
{
  "baseline": {...},
  "candidate_population": {...},
  "accepted_recoveries": [...],
  "rejected_recoveries": [...],
  "kpis": {...},
  "regression_results": {...}
}
```

### H.3 Real IO Validation

Per directive §10:
- 2 monetary IOs
- 2 statistical IOs
- 2 regulatory IOs

Each must survive:
- Persist
- Restart
- HTTP retrieval

---

## I. Git Durability

Per directive §12:

```bash
git status
git commit -m "V37 — Evidence Recovery and Semantic Enrichment"
git push origin main
git ls-remote origin main
```

**Require:** LOCAL HEAD == REMOTE HEAD

---

## J. Final Verdict

Per directive §13, return exactly one:

- `CORE V37 PASSED`
- `CORE V37 PASSED WITH BOUNDED GAPS`
- `CORE V37 BLOCKED — SOURCE STATE INCONSISTENT`
- `CORE V37 REJECTED — QUALITY REGRESSION`

---

## K. STOP Conditions

Per directive §14:

**Do NOT:**
- Expand sources
- Integrate products
- Deploy Railway
- Implement broad Entity-Aware extraction
- Add new language packs

**UNTIL V37 is independently validated from repository state.**

---

## L. Execution Log

### L.1 Session Bootstrap

| Step | Timestamp | Status | Notes |
|------|-----------|--------|-------|
| 1. Repository Recovery | 2026-08-19 | ✅ | HEAD = 5f1df0e |
| 2. Read V36 State | 2026-08-19 | ✅ | V36 audit doc located |
| 3. Read V32 Ledger | 2026-08-19 | ✅ | 788 cases, 116 TRUE_MATERIAL_FACT |
| 4. Verify 158 Cases | 2026-08-19 | ⏳ | In progress |
| 5. V37 Plan | 2026-08-19 | ✅ | This document |
| 6. Evidence Recovery | TBD | ⏳ | Pending |
| 7. Controlled Experiment | TBD | ⏳ | Pending |
| 8. Acceptance Gate | TBD | ⏳ | Pending |
| 9. Semantic Enrichment | TBD | ⏳ | Pending |
| 10. Real IO Validation | TBD | ⏳ | Pending |
| 11. Artifacts | TBD | ⏳ | Pending |
| 12. Git Push | TBD | ⏳ | Pending |

### L.2 Key Findings So Far

1. **Repository state confirmed**: V36 = 5f1df0e, clean working tree
2. **158 EVIDENCE_SELECTION_GAP documented** in V32 and V36
3. **Evidence classifier located**: `v10_evidence_closure.py::classify_evidence_strict()`
4. **Expansion mechanism located**: `v10_evidence_closure.py::expand_evidence_for_direct()`
5. **Canonical contract confirmed**: 8 sections (A-I), entity/unit/period not present

---

## M. Next Steps

1. **Forensic query on 158 cases** — identify exact population from v32 ledger
2. **Implement evidence recovery** — enhance expand_evidence_for_direct()
3. **Run controlled experiment** — baseline vs candidate
4. **Measure KPIs** — TP/FP/FN, Recall, Precision, Direct Evidence
5. **Apply acceptance gate** — pass/fail decision
6. **If passed: semantic enrichment** — entity, unit, temporal
7. **Validate real IOs** — 6 IOs (2+2+2) persist/restart/retrieve
8. **Commit and push** — git durability
9. **Final verdict** — PASSED/PASSED WITH BOUNDED GAPS/BLOCKED/REJECTED

