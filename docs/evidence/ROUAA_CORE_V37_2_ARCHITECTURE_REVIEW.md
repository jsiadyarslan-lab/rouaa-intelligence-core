# ROUAA Core V37.2 — Evidence Architecture Review

> **Status**: DESIGN REVIEW COMPLETE  
> **Date**: 2026-08-19  
> **Directive**: V37.2 EVIDENCE ARCHITECTURE DESIGN REVIEW  
> **Parent**: V37.1 Phase 1–5.2 BLOCKED (no commit)  
> **Next**: Pending approval to implement V37.2

---

## Section 1 — V37.1 Phase 1–5.2 Failure Summary

### What Was Attempted

`expand_evidence_for_direct()` in `v10_evidence_closure.py` was modified to replace the raw ±200-char window with a boundary-respecting expansion chain: sentence → sentence+adjacent → paragraph → structured segment → bounded → UNRESOLVED_BOUNDARY.

### Results

| Metric | Value |
|--------|------:|
| Baseline DIRECT | 20 |
| Candidate DIRECT (new logic) | 71 |
| Apparent recovery | +51 |
| True malformed outputs | 4 |
| True malformed rate | ~7.8% of new recoveries |
| 48-core test pass rate | 48/48 |
| Regression test pass rate | 11/11 |

### True Malformed Cases

| Record | Failure Mode | Root Cause |
|--------|-------------|-----------|
| gtf-0765 | Sentence split after "U.S." | Abbreviation period treated as sentence end |
| gtf-0799 | Sentence split after "U.S." | Same |
| gtf-0805 | Sentence split after "U.S." | Same |
| gtf-0199 | Domain text leaked into excerpt | `bls.gov` concatenated with content during strip_html |

### Gate Decision

BLOCKED per §10 of the directive. No commit was made. Production baseline unchanged.

### Why No Patch Was Applied

The abbreviation boundary problem requires a domain-specific whitelist that:
- Grows unbounded as new sources are added
- Fails silently on new abbreviation forms
- Cannot be validated by the 158-case GT (too small to catch edge cases)

Adding `U.S.` → add `Fed.` → add `Dept.` → add `Sec.` → add `Jan.` → ... is a maintenance path with no defined endpoint. The sentence-slicing model itself is insufficient.

---

## Section 2 — Existing Infrastructure Audit

### 2.1 Structural Parsers (in test suite, not production)

**HTMLStructureParser** (`v15_recall_recovery.py`, ~120 lines)

Proven on the actual document corpus from V15 forward. Capabilities:
- Skips `<style>`, `<script>`, `<template>`, `<noscript>` (V24R hardening) ✓
- Emits typed segments: TABLE_ROW, LIST_ITEM, HEADING, PARAGRAPH ✓
- Preserves table headers alongside row cells ✓
- Tracks `context_stack` for structural ancestry ✓

Gaps relative to EvidenceSegmentV1 needs:
- No FOOTNOTE or QUOTE segment types
- No `parent_segment_id` linking
- No structural exclusion of `<nav>`, `<header>`, `<footer>` elements

**SemanticTableParser** (`v25r_semantic_table_parser.py`, ~280 lines)

Proven on table-heavy documents (Census, BEA statistics tables). Capabilities:
- Multi-row header support ✓
- `row_label`, `column_label`, `cell_value` extracted per cell ✓
- `source_location` as `{document_id}#table{n}` ✓
- Period and unit detection per cell ✓

Gaps:
- No integration with surrounding paragraph/heading context
- Table segments not linked to parent section

**is_navigation_content()** (`v9_navigation_exclusion.py`)

Keyword-based, catches: menus, social media, copyright, cookie notices, page numbers ✓

Gap: fails on structural navigation (domain names in `<a>` tags concatenated during strip_html). Structural exclusion must precede keyword detection.

### 2.2 Production Evidence Model

Current `Evidence` contract (`contracts.py`):

```python
@dataclass
class Evidence:
    evidence_id: str
    event_or_fact_id: str
    representation_id: str
    location: str = ""        # free-form string
    excerpt: str = ""         # flat string — only output
    provenance_ref: str = ""
    created_at: str = ""
```

The contract carries **no structural information**. `excerpt` is a flat string. `location` is a free-form string currently set to document URL.

The `Fact` contract (`contracts.py`) has `occurrence: int = 0` — this field already exists to distinguish multiple occurrences of the same value in a document. It is set during extraction in `extract.py`.

### 2.3 Production Pipeline Gap

`normalize.py::strip_html()` is called at document ingest and discards all structure. There is no path from archived HTML blobs to structured segments in the current production flow. The connection must be established in V37.2 by reading `Representation.raw_location` (the archived HTML blob path).

---

## Section 3 — EvidenceSegmentV1 Design Summary

Full schema in `docs/architecture/ROUAA_CORE_EVIDENCE_SEGMENT_ARCHITECTURE_V1.md §3`.

### Critical Properties

1. **Structural position determines exclusion** — not keyword content. A `<p>` inside `<nav>` is excluded as NAVIGATION before its text is inspected. This eliminates the domain-leakage failure class.

2. **No string-offset reconstruction** — evidence excerpts are taken verbatim from segments as they were parsed from HTML. No slicing, no boundary detection, no abbreviation handling.

3. **Table evidence preserves row/column context** — `row_label | column_label: value (period)` format. No forced conversion to prose.

4. **Multi-number disambiguation uses `fact.occurrence`** — already in the `Fact` contract. The nth segment containing `fact.value` maps to `fact.occurrence == n`.

5. **INSUFFICIENT_EVIDENCE with no fallback** — if no valid segment contains `fact.value`, the result is INSUFFICIENT_EVIDENCE. No string-offset fallback. No fabricated combined sentence.

---

## Section 4 — Evidence Selection Model

Full design in `docs/architecture/ROUAA_CORE_EVIDENCE_SEGMENT_ARCHITECTURE_V1.md §5`.

### Scoring Summary

Candidates are filtered first (excluded=False, segment_type in PRIMARY_EVIDENCE_TYPES), then scored across 9 dimensions. The highest-scored candidate becomes the evidence excerpt.

For the 158-case GT population:
- Abbreviation cases (gtf-0765, 0799, 0805): The U.S. abbreviation stays inside a PARAGRAPH segment — the segment boundary is the HTML block boundary, not a period. These cases would be resolved.
- Navigation leakage (gtf-0199): The `bls.gov` anchor is a NAVIGATION or OTHER segment. It would be excluded and the containing PARAGRAPH (which has the actual content) would be selected instead.

---

## Section 5 — Backward Compatibility Assessment

### No Breaking Changes

| Layer | Change | Breaking? |
|-------|--------|-----------|
| `contracts.py::Evidence` | +2 nullable fields (`segment_id`, `segment_type`) | No |
| `contracts.py::Fact` | None | No |
| `contracts.py::IntelligenceObject` | None | No |
| Store schema | None | No |
| IO IDs | None | No |
| Existing evidence records | `segment_id=None` → valid as Phase-0 evidence | No |

### Migration Signal

`segment_id is None` → Phase-0 evidence (string-offset excerpt, may have malformed boundaries)  
`segment_id is not None` → Phase-1 evidence (EvidenceSegmentV1-derived, structurally valid)

Consumers can distinguish evidence quality by this field without schema changes.

---

## Section 6 — Performance and Scale

| Scale | Approach | Feasible? |
|-------|---------|-----------|
| 1,000 docs | Parse on-demand per evidence request | Yes |
| 100,000 docs | Parse on-demand, discard segments after selection | Yes (memory OK) |
| 1,000,000 docs | Stream parse, never materialize all segments | Yes (with streaming) |

At production scale (currently hundreds of documents per corpus), on-demand parsing is sufficient. Batch mode: parse → select → discard. No persistent segment store required in V37.2.

---

## Section 7 — Implementation Scope Estimate

| Component | Action | Estimated LOC |
|-----------|--------|:------------:|
| `EvidenceSegmentV1` dataclass | New, in `contracts.py` | ~30 |
| `parse_evidence_segments()` | Promote + extend HTMLStructureParser | ~60 |
| `select_evidence_segment()` | New selection function | ~80 |
| `contracts.py::Evidence` | +2 nullable fields | ~4 |
| Navigation structural exclusion | Extend HTMLStructureParser | ~30 |
| Tests (8 boundary cases + regression) | New test file | ~150 |
| **Total new production code** | | **~200** |

No changes to: `pipeline.py`, `extract.py`, `delivery.py`, `store.py`, `acquisition.py`, `normalize.py`.

This is a self-contained addition to the evidence layer with no pipeline impact.

---

## Section 8 — Open Questions Before Implementation

These are not blockers, but require decisions before writing code:

**Q1: Segment persistence**  
Option A: Parse segments on-demand at evidence-selection time (V37.2 scope)  
Option B: Store segments as a new record type in the append-only store (V38+ scope)  
*Recommendation: Option A for V37.2. Option B deferred.*

**Q2: Heading context depth**  
How many levels of heading ancestry to include in `heading_context`? (h2 only? h2+h3?)  
*Recommendation: Nearest ancestor only for V37.2.*

**Q3: Missing raw_location blobs**  
Some `Representation` records may have `raw_location` pointing to absent files. The 158-case GT population must be audited for blob availability before running the selection algorithm.  
*Action required before implementation: count records with available blobs.*

**Q4: Arabic/multilingual documents**  
`HTMLStructureParser` handles Unicode transparently. Sentence/paragraph boundaries in Arabic text are not affected because the new design does not use sentence splitting. No special handling needed for V37.2.

---

## Final Verdict

```
V37.2 ARCHITECTURE REVIEW PASSED WITH BOUNDED GAPS
```

### Passed Criteria

- [x] V37.1 failure root causes identified and confirmed (not patched)
- [x] Existing infrastructure (HTMLStructureParser, SemanticTableParser) confirmed as reusable
- [x] EvidenceSegmentV1 schema designed with clear SOURCE-DERIVED vs DERIVED distinction
- [x] Segment type inventory defined with eligibility criteria for primary evidence
- [x] Evidence selection model designed (selection flow, scoring dimensions, no-fallback rule)
- [x] Navigation/template safety: structural exclusion precedes keyword detection
- [x] Multi-number disambiguation: uses existing `fact.occurrence` field
- [x] Table evidence design: row_label + column_label preserved without prose conversion
- [x] Output contract: 2 nullable fields, fully backward compatible
- [x] Performance: on-demand parsing feasible for current and 100K+ scale
- [x] Backward compatibility: no existing IO IDs or evidence records broken
- [x] V37.2 decision: B (HYBRID STRUCTURAL EVIDENCE) with full justification
- [x] Implementation scope: ~200 LOC, no pipeline changes

### Bounded Gaps (not blockers)

- Segment persistence strategy deferred to V38+
- Heading context depth to be decided at implementation time
- `raw_location` blob availability audit required before running on full 158-case population
- Scoring weights not yet calibrated (design only — calibration requires GT runs)

### What Was Not Done

- No production code was modified
- No ledger was modified
- No ground truth was modified
- No extraction patterns were modified
- No commit was made (design documents only pending review)

---

*Awaiting: approval to commit these two design documents to main and proceed to V37.2 implementation.*
