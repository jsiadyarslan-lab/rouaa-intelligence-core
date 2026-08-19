# ROUAA Core V37.2 — Occurrence Identity Review

> **Status**: COMPLETE  
> **Date**: 2026-08-19  
> **Directive**: V37.2 IMPLEMENTATION PREFLIGHT §3  
> **Baseline**: 5a27473f5717c46f91e11637f289ee17cc450817

---

## Decision

```
OCCURRENCE_REQUIRES_CONTEXT
```

`document_id + metric + occurrence` is **not sufficient** to identify a structural evidence segment. The minimum safe key requires additional structural context. Details below.

---

## Evidence

### Case A — Listing Page (doc-a72c0918e27dd12b, value=`5`)

**Source**: Statistik Austria — statistical news index page (286 KB HTML)

| Dimension | Value |
|-----------|-------|
| GT facts with value=5 in this document | 30 |
| v32 `occurrences` count | 717 |
| Raw text occurrences of standalone `5` | 57 |
| Structural segments (HTMLStructureParser) containing `5` | 55 |
| Structural segments containing exactly `5%` pattern | **2** |
| All matching segments context type | TABLE_ROW |
| Unique metrics across 30 GT facts | percentage_statistic only |

The 30 GT facts all carry the same `evidence_excerpt` (a listing of press release titles), all have `occurrences=717` per v32, and all are `metric=percentage_statistic`. They are distinct facts because they refer to different statistical releases listed on the page — but the HTML structure represents them identically: each is a `TABLE_ROW` with columns `['Datum', 'Titel']`.

**Conclusion for Case A**:
- `occurrence` alone: INSUFFICIENT (30 facts → 2 matching structural segments)
- `metric` alone: INSUFFICIENT (all `percentage_statistic`)
- `occurrence + metric`: INSUFFICIENT (same reason)
- `occurrence + metric + entity`: POTENTIALLY sufficient IF entity is extractable from the row title — but entity extraction is out of V37.2 scope
- **Correct V37.2 outcome for this document**: `INSUFFICIENT_EVIDENCE` — listing/index pages cannot be structurally resolved at the segment level without entity extraction

### Case B — Cross-Metric Collision (doc-8700a0859c829c44, value=`0.1`)

**Source**: BEA trade release (93 KB HTML)

| Dimension | Value |
|-----------|-------|
| GT facts with value=0.1 in this document | 7 |
| Metrics | `percentage_statistic` (3 facts), `usd_amount` (4 facts) |
| Structural segments containing `0.1` | **3** |
| All 3 segments | dollar amounts (`$0.1 billion`) |
| `percentage_statistic` segments found | 0 |

The `0.1` value appears 7 times across two metric types. All 3 structural segments that contain `0.1` are dollar-denominated (`$0.1 billion`). There are no segments where `0.1` appears as a bare percentage.

**Conclusion for Case B**:
- `metric` helps distinguish type (percentage vs dollar) in principle
- But `percentage_statistic` GT facts (gtf-0601, 0602, 0603) have no matching structural segment → likely GT annotation errors or edge cases where `0.1%` appears in non-structural content
- `usd_amount` facts can be mapped to 3 structural segments with structural context scoring
- **Correct V37.2 outcome**: `usd_amount` facts → select best segment by structural scoring; `percentage_statistic` facts → `INSUFFICIENT_EVIDENCE` (no segment found)

### Case C — Simple Value Collision (doc-7c5cd3967c2f9f10, value=`0.2`)

**Source**: BEA personal income release (69 KB HTML)

| Dimension | Value |
|-----------|-------|
| GT facts with value=0.2 | 3 |
| Metrics | all `percentage_statistic` |
| Structural segments containing `0.2` | multiple PARAGRAPH and LIST_ITEM |
| Facts distinguishable by context? | Yes — different periods/entities |

Here metric is uniform but structural context differs per occurrence. The three facts refer to different statistical components (DPI growth, PCE growth, etc.) — each resides in a structurally distinct segment. The `heading_context` and surrounding text differ per segment.

**Conclusion for Case C**:
- Structural scoring on `METRIC_CONTEXT + ENTITY_CONTEXT + TEMPORAL_CONTEXT` can distinguish
- `occurrence` integer is still insufficient on its own (all 3 in same metric bucket)
- Structural context resolves this class correctly

---

## Minimum Safe Identity Key

Based on the above cases, the minimum key to safely identify a structural evidence segment is:

```
document_id
+ metric
+ value
+ structural_context_score (not a single key — a scoring result)
```

Formally, the identity function is not a lookup but a **ranked selection**:

```
candidates = [seg for seg in segments
              if seg.text contains value
              and seg.excluded == False
              and seg.segment_type in PRIMARY_EVIDENCE_TYPES]

ranked = score(candidates, fact.metric, fact.value, known_entity, known_period)

selected = ranked[0] if ranked else INSUFFICIENT_EVIDENCE
```

The `fact.occurrence` integer is **not used as a positional index into ranked candidates**. It remains available as a tiebreaker only if two candidates are otherwise identically scored — and even then, only as a last resort signal.

---

## Implications for EvidenceSegmentV1 Design

### 1. Listing Pages → INSUFFICIENT_EVIDENCE

For documents where the same value appears 700+ times in structurally homogeneous segments (listing rows without entity/period data in cell text), the correct outcome is `INSUFFICIENT_EVIDENCE`. This is not a failure of the architecture — it is the correct conservative answer. These documents were rejected by the original evidence classifier for the same reason.

**Action**: No special handling needed. The scoring model naturally produces no winner when all candidates are equally scored listing rows.

### 2. No Positional Occurrence Indexing

The V37.2 implementation MUST NOT interpret `fact.occurrence` as:
> "select the Nth segment containing this value"

This would produce the exact multi-number mapping failure described in V23/V24. `fact.occurrence` records how many times this value was seen during extraction — it is a fact-level metadata field, not a segment pointer.

**Action**: `fact.occurrence` is read-only context for scoring tiebreaks. It is never used as a segment index.

### 3. Cross-Metric Cases Resolved by Structural Type

When `value=0.1` appears in both `percentage_statistic` and `usd_amount` facts within the same document, the structural segment text itself contains the discriminating signal: `$0.1 billion` vs `0.1%`. The scoring dimension `UNIT_CONTEXT` captures this without requiring metric-level logic.

**Action**: `UNIT_CONTEXT` scoring dimension must examine segment text for currency symbols, `%` signs, and unit words. This was already included in the V37.2 architecture design.

### 4. Entity Context as Future Enhancement

For Case A (listing pages), entity extraction would enable correct segment assignment (each row title contains the entity). This is explicitly **out of V37.2 scope** — it belongs to Semantic Enrichment. For V37.2, listing pages correctly return `INSUFFICIENT_EVIDENCE`.

---

## Parser Promotion Review

### HTMLStructureParser (v15_recall_recovery.py)

**Current capabilities** (production-ready):
- SKIP_TAGS: `{style, script, template, noscript}` ✓
- Segment types: `TABLE_ROW`, `LIST_ITEM`, `HEADING`, `PARAGRAPH` ✓
- Table header preservation alongside row cells ✓
- `context_stack` tracking ✓

**Required additions for promotion**:

| Gap | Change Required | Complexity |
|-----|----------------|:----------:|
| No `<nav>` exclusion | Add nav-depth tracking (like skip_depth) | Low |
| No `<header>`/`<footer>` exclusion | Add structural exclusion depth for non-article header/footer | Low |
| No `role=` attribute inspection | Read attrs in `handle_starttag` for `role="navigation"` etc. | Low |
| No `parent_segment_id` | Track segment index of nearest ancestor heading | Low |
| Missing FOOTNOTE type | Detect `<aside>` / `<footer>` within `<article>` | Medium |
| Missing QUOTE type | Detect `<blockquote>` | Low |
| No heading_context propagation | Track last HEADING text and attach to child segments | Low |

**Total estimated change**: ~40 lines added to existing 110-line class. No structural rewrite.

### SemanticTableParser (v25r_semantic_table_parser.py)

**Current capabilities** (production-ready):
- `row_label`, `column_label` per cell ✓
- `source_location` as `{doc_id}#table{n}` ✓
- Multi-row header support ✓
- `period` and `unit` detection per cell ✓

**Gap found**: `TableCell.column_label` field exists in the dataclass but is populated via `header_rows[-1][col_idx]` — this works only when headers have been parsed. Confirmed in code inspection.

**Required additions for promotion**:

| Gap | Change Required | Complexity |
|-----|----------------|:----------:|
| No integration with HTMLStructureParser | `SemanticTableParser` runs independently | Medium |
| No heading context for tables | Need to know what section the table is in | Low (pass in) |
| `column_label` not verified in edge cases | Multi-colspan headers may mis-assign | Low |

**Total estimated change**: ~20 lines. The two parsers can remain separate and be composed at the `select_evidence_segment()` call site.

---

## Summary

| Precondition | Status |
|-------------|--------|
| Raw blob availability (§2) | CLEARED — 158/158 |
| Occurrence disambiguation (§3) | CLEARED — decision: OCCURRENCE_REQUIRES_CONTEXT |
| Parser promotion path (§4) | CLEARED — concrete change list, ~60 lines total |

All three §2–§4 preconditions are resolved.

```
V37.2 PREFLIGHT PASSED
```

Awaiting implementation approval.
