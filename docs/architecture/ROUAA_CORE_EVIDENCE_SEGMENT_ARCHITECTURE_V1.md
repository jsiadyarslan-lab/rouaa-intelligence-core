# ROUAA Core — Evidence Segment Architecture V1

> **Status**: DESIGN ONLY — No implementation  
> **Date**: 2026-08-19  
> **Directive**: V37.2 EVIDENCE ARCHITECTURE DESIGN REVIEW  
> **Author**: Architecture Review (Claude)  
> **Parent**: V37.1 Phase 1–5.2 BLOCKED

---

## 1. Why Sentence Slicing Failed

### 1.1 Root Cause Analysis from V37.1 Phase 1–5.2

The V37.1 experiment confirmed three distinct failure modes in `expand_evidence_for_direct()` that cannot be individually patched:

**Failure A — Abbreviation Boundaries (gtf-0765, gtf-0799, gtf-0805)**

The sentence boundary regex `[.!?\n]` treats `U.S.` as two sentences: `U.S` and the remainder. The decimal-safe guard introduced in V37.1 only protected digit-adjacent periods (`3.5%`, `1.2T`), not abbreviation periods. Adding an abbreviation whitelist (`U.S.`, `Fed.`, `Dept.`, `Jan.`, etc.) solves this case but creates a maintenance list that grows unboundedly with domain expansion (ISO codes, agency acronyms, foreign abbreviations in multilingual sources).

**Failure B — Navigation/Domain Leakage (gtf-0199)**

`is_navigation_content()` uses keyword regex over flattened text. When domain names are concatenated during HTML stripping (e.g., `bls.gov In May 2026...`), the navigation filter fails because `bls.gov` is not a keyword match and the pattern `"com In May"` looks like prose. The problem is that `strip_html()` discards the structural signal (this was an `<a>` or `<nav>` element) that would have identified it as non-content.

**Failure C — Flattened HTML Structural Loss**

`strip_html()` in `normalize.py` is a 7-line regex chain:
```python
_SCRIPT.sub(" ") → _STYLE.sub(" ") → entity decode → _TAGS.sub(" ") → whitespace collapse
```
This reduces `<table>`, `<tr>`, `<td>`, `<h2>`, `<p>`, `<li>` to undifferentiated whitespace. All structural signals — table membership, heading hierarchy, list membership, cell boundaries — are destroyed. The resulting string cannot be re-segmented by regex because the boundary information was never preserved in the first place.

### 1.2 Why Patching Is Unsafe

Each patch moves the problem rather than solving it:
- Abbreviation list → grows unbounded; fails on new domains; fails on Arabic/multilingual sources
- Extended navigation regex → false positives on valid content containing social media discussion
- Lookahead/lookbehind in sentence regex → computational cost, edge case proliferation

After 3+ heuristic layers, the failure mode shifts from `incorrect boundary` to `untestable boundary logic`. The 158-case GT population cannot distinguish `correctly sliced` from `accidentally correct`.

---

## 2. Existing Structural Infrastructure Audit

### 2.1 What Exists (TEST FILES — not production)

| Component | Location | Status |
|-----------|----------|--------|
| `HTMLStructureParser` | `v15_recall_recovery.py` | Test-only, not imported in production |
| `SemanticTableParser` | `v25r_semantic_table_parser.py` | Test-only, not imported in production |
| `is_navigation_content()` | `v9_navigation_exclusion.py` | Test-only, imported by v10 test |
| `extract_html_structure()` | `v15_recall_recovery.py` | Test-only |

### 2.2 What Is in Production

| Component | Location | Behavior |
|-----------|----------|----------|
| `strip_html()` | `normalize.py` | Destructs all HTML structure |
| `Evidence` contract | `contracts.py` | `excerpt: str`, `location: str` — flat string only |
| `Fact` contract | `contracts.py` | `excerpt: str` — flat string only |
| `expand_evidence_for_direct()` | `v10_evidence_closure.py` | Test-only, applies string offsets on stripped text |

**Critical finding**: The production `Evidence` contract in `contracts.py` carries only `excerpt: str` and `location: str`. There is no `segment_type`, no `structural_context`, no `table_id`, no `heading_context`. The structural parsers from V15 and V25R were never promoted to production.

### 2.3 Reuse Assessment

`HTMLStructureParser` (V15/V24R) is production-ready in quality:
- Handles `SKIP_TAGS` (`style`, `script`, `template`, `noscript`) ✓
- Emits `(text, context, table_headers)` tuples ✓
- Handles TABLE_ROW, LIST_ITEM, HEADING, PARAGRAPH contexts ✓
- Missing: FOOTNOTE, QUOTE, DOCUMENT_HEADER segment types
- Missing: `parent_segment_id`, heading hierarchy nesting

`SemanticTableParser` (V25R) is production-ready in quality:
- Preserves `row_label`, `column_label`, `cell_value`, `period`, `unit` ✓
- Emits `source_location` as `{doc_id}#table{n}` ✓
- Missing: integration with paragraph/heading context
- Missing: `parent_segment_id` linking table to surrounding section

`is_navigation_content()` (V9) is partially useful:
- Correctly handles keyword-based navigation ✓
- Fails on domain-leakage case ✗ (needs segment-level, not text-level check)

---

## 3. EvidenceSegmentV1 Design

### 3.1 Conceptual Model

```
Canonical Document (HTML bytes)
        ↓
[HTMLStructureParser + SemanticTableParser]
        ↓
List[EvidenceSegmentV1]          ← new layer
        ↓
fact.value search over segments
        ↓
Candidate EvidenceSegmentV1 list
        ↓
Structural scoring → best segment
        ↓
Evidence object (existing contract, enriched)
```

### 3.2 EvidenceSegmentV1 Schema

```python
@dataclass
class EvidenceSegmentV1:
    # ── Identity ──────────────────────────────────────────────────────
    document_id: str                  # SOURCE-DERIVED: from document record
    segment_id: str                   # DERIVED: stable hash(document_id + segment_index)
    segment_index: int                # DERIVED: ordinal position in parse sequence

    # ── Type ──────────────────────────────────────────────────────────
    segment_type: str                 # SOURCE-DERIVED: see §4
    parent_segment_id: Optional[str]  # DERIVED: heading/table that contains this segment

    # ── Content ───────────────────────────────────────────────────────
    text: str                         # SOURCE-DERIVED: raw text of this segment
    source_location: str              # DERIVED: "{document_id}#{segment_type}{index}"

    # ── Structural context ────────────────────────────────────────────
    heading_context: Optional[str]    # DERIVED: nearest ancestor heading text
    table_id: Optional[str]           # SOURCE-DERIVED: if segment is within a table
    row_label: Optional[str]          # SOURCE-DERIVED: table row header (if TABLE_ROW/CELL)
    column_label: Optional[str]       # SOURCE-DERIVED: table column header (if TABLE_CELL)
    list_depth: int = 0               # DERIVED: nesting depth (0 if not in list)

    # ── Exclusion flags ───────────────────────────────────────────────
    excluded: bool = False            # DERIVED: True if segment_type in EXCLUDED_TYPES
    exclusion_reason: Optional[str]   # DERIVED: reason if excluded
```

**SOURCE-DERIVED** — taken directly from parsed HTML attributes/content, no inference.  
**DERIVED** — computed from parse position, parent relationships, or hash functions.

### 3.3 Segment ID Generation

```python
segment_id = sha256(f"{document_id}::{segment_type}::{segment_index}").hexdigest()[:16]
```

Stable across re-parses of the same document (assumes stable parse order from same HTML bytes).

---

## 4. Segment Types

### 4.1 Type Inventory

| Type | HTML Source | Primary Evidence? | Rationale |
|------|-------------|:-----------------:|-----------|
| `DOCUMENT_HEADER` | `<title>`, `<meta name="description">` | NO | Metadata, not content |
| `HEADING` | `<h1>`–`<h6>` | Contextual only | Provides heading_context to children, rarely standalone evidence |
| `PARAGRAPH` | `<p>`, block `<div>` | **YES** | Primary evidence carrier |
| `LIST_ITEM` | `<li>` | **YES** | Valid evidence when self-contained |
| `TABLE_ROW` | `<tr>` aggregate | **YES** (with row+col labels) | Evidence with structural richness |
| `TABLE_CELL` | `<td>`, `<th>` | Contextual only | Too granular; use TABLE_ROW |
| `QUOTE` | `<blockquote>`, `<q>` | **YES** | Valid evidence |
| `FOOTNOTE` | `<aside>`, `<footer>` within `<article>` | **YES** | Valid evidence if within article scope |
| `OTHER` | Unclassified blocks | NO | Conservative default |

### 4.2 Excluded Segment Types (never primary evidence)

```
NAVIGATION       ← <nav>, role="navigation"
HEADER_UI        ← <header> outside <article>
FOOTER_UI        ← <footer> outside <article>
SOCIAL           ← segments matching social pattern in structural position
COOKIE           ← cookie/consent elements
CSS              ← style elements (already skip_depth in parser)
JS               ← script elements (already skip_depth in parser)
TEMPLATE         ← template/noscript (already skip_depth in parser)
ADVERTISEMENT    ← <aside role="complementary">, ad-class patterns
LISTING          ← <nav>-adjacent listing blocks, breadcrumbs
```

**Key principle**: exclusion is by structural position first, keyword match second. A `<p>` inside `<nav>` is NAVIGATION regardless of text content. This solves the domain-leakage case from V37.1.

---

## 5. Evidence Selection Model

### 5.1 Selection Flow

```
fact.value
    ↓
Search all EvidenceSegmentV1 for segments containing fact.value
    ↓
Filter: segment.excluded == False
    ↓
Filter: segment.segment_type in PRIMARY_EVIDENCE_TYPES
    ↓
Score each candidate
    ↓
Sort descending by score
    ↓
Take top candidate
    ↓
If no candidate: INSUFFICIENT_EVIDENCE
```

### 5.2 Scoring Dimensions (design only — not weighted yet)

| Dimension | Description |
|-----------|-------------|
| `VALUE_PRESENT` | fact.value appears in segment.text (prerequisite) |
| `METRIC_CONTEXT` | segment.text contains metric-related keywords (percent, rate, GDP...) |
| `ENTITY_CONTEXT` | segment.text contains known entity name |
| `UNIT_CONTEXT` | segment.text contains unit indicators consistent with fact.unit |
| `TEMPORAL_CONTEXT` | segment.text contains period indicators consistent with fact.period |
| `STRUCTURAL_RELEVANCE` | segment_type in {TABLE_ROW, PARAGRAPH} > LIST_ITEM > QUOTE |
| `HEADING_MATCH` | segment.heading_context contains metric or entity keyword |
| `NAVIGATION_PENALTY` | -∞ if segment.excluded (makes it unreachable after filter) |
| `BOILERPLATE_PENALTY` | negative score for high ratio of non-alphanumeric content |
| `DISTANCE` | ordinal distance from document centroid (prefer body over header/footer) |

### 5.3 Multi-Number Disambiguation

When the same `fact.value` (e.g., `4%`) appears in multiple segments:

1. Score all candidates as above
2. Apply `METRIC_CONTEXT` and `ENTITY_CONTEXT` to disambiguate
3. The `fact.occurrence` field (existing in `Fact` contract) maps to segment ordinal position
4. `fact.occurrence == 1` → first matching segment; `fact.occurrence == 2` → second, etc.

This requires `fact.occurrence` to be set at extraction time (it already exists in the `Fact` dataclass).

### 5.4 No-Segment Fallback

If no `EvidenceSegmentV1` contains `fact.value`:
- Return `INSUFFICIENT_EVIDENCE`
- Do NOT fall back to string-offset slicing of stripped text
- Do NOT fabricate a combined sentence from adjacent segments

---

## 6. Navigation / Template Safety

### 6.1 Structural Exclusion (Primary)

At parse time, any segment whose HTML ancestor is:
```
<nav>, <header> (outside article), <footer> (outside article),
role="navigation", role="banner", role="contentinfo",
class containing: "nav", "menu", "footer", "header", "cookie", "consent",
                  "sidebar", "social", "ad-", "advertisement"
```
...receives `excluded=True, exclusion_reason="NAVIGATION"` before any text check.

### 6.2 Content Exclusion (Secondary)

After structural exclusion, apply the existing `is_navigation_content()` check (V9) on segments not yet excluded. This catches cases where navigation HTML lacks semantic attributes.

### 6.3 Domain-Leakage Prevention

The specific V37.1 failure (`bls.gov In May 2026...`) is prevented because:
1. The `<a>` tag containing `bls.gov` is structural — its text is accumulated into a segment
2. The segment's parent is identified (nav? article? sidebar?)
3. If parent is non-content, segment is excluded at step 6.1
4. If parent is content, the `bls.gov` text would still be part of a valid PARAGRAPH segment, which is correct — the domain was accidentally concatenated during strip_html but is now preserved as a separate segment with its own structural position

---

## 7. Table Evidence

### 7.1 Evidence from Table Cells

For `TABLE_ROW` segments, the excerpt in the `Evidence` contract is constructed as:

```
{row_label} | {column_label}: {cell_value} ({period if available})
```

Example:
```
GDP Growth Rate | Q1 2026: 2.4%
```

This preserves the full semantic context without forcing table data into prose.

### 7.2 Table Evidence in Evidence Contract

The existing `Evidence.location` field carries `{document_id}#{segment_type}{index}`, which for tables becomes `{document_id}#table{n}#row{m}`. No schema change required — the location string is already free-form.

The existing `Evidence.excerpt` carries the constructed row string above.

---

## 8. Output Contract (Fact → Evidence → Event → IO)

### 8.1 Minimal Changes Required

The existing `Evidence` contract needs **one addition** to support EvidenceSegmentV1:

```python
@dataclass
class Evidence:
    evidence_id: str
    event_or_fact_id: str
    representation_id: str
    location: str = ""
    excerpt: str = ""
    provenance_ref: str = ""
    created_at: str = ""
    # NEW (optional, backward compatible):
    segment_id: Optional[str] = None     # links to EvidenceSegmentV1
    segment_type: Optional[str] = None   # for audit without segment lookup
```

Both new fields are `Optional[str] = None` — fully backward compatible. Existing evidence records without these fields remain valid.

### 8.2 IO Chain Impact

The `IntelligenceObject.chain` list already carries `[fact_id, evidence_id, representation_id, document_id, source_id]`. No change required.

---

## 9. Performance Estimates

### 9.1 Segments per Document

Based on observed HTMLStructureParser output from V15 test runs:

| Document type | Typical segments |
|--------------|:---------------:|
| BEA press release (HTML, 8KB) | 40–80 |
| Census statistical release (HTML, 15KB) | 80–150 |
| Fed minutes/statement (HTML, 20KB) | 100–200 |
| Large agency report (HTML, 50KB+) | 300–600 |

### 9.2 Memory Impact

```
EvidenceSegmentV1 per instance ≈ 500–2000 bytes (text + metadata)
80 segments × 1000 bytes = ~80KB per document
```

For 1,000 documents simultaneously: ~80MB. Acceptable for batch processing.  
For 100,000 documents: segments must not be held in memory simultaneously. Process document → select evidence → discard segments.  
For millions: streaming parse — never materialize all segments. Process segment by segment, keep only candidates.

### 9.3 Indexing Cost

Building segments: O(HTML_bytes) — single parse pass.  
Searching segments for value: O(n_segments × len(value)) — linear, fast.  
Scoring: O(n_candidates × n_dimensions) — typically < 10 candidates.

No secondary index required at current scale. At 100K+ documents, a value-to-segment inverted index would be needed.

### 9.4 Lookup Complexity

Current (string offset): O(1) — but produces malformed results.  
EvidenceSegmentV1: O(n_segments) — slower but correct.

Acceptable tradeoff: evidence selection is not the latency-critical path. Acquisition and HTTP are dominant.

---

## 10. Backward Compatibility

### 10.1 Existing Evidence Records

All existing `Evidence` records have `segment_id=None, segment_type=None`. These remain valid. The new fields are nullable.

### 10.2 Migration Path (V1 → EvidenceSegmentV1)

```
Phase 0 (current): Evidence.excerpt = arbitrary string slice
Phase 1 (V37.2):   Evidence.excerpt = selected from EvidenceSegmentV1
                   Evidence.segment_id = EvidenceSegmentV1.segment_id
                   Evidence.segment_type = EvidenceSegmentV1.segment_type
Phase 2 (future):  Re-derive evidence for existing IOs from archived HTML
```

Phase 1 and Phase 0 are distinguished by `segment_id is None` (Phase 0) vs. `segment_id is not None` (Phase 1). No IO ID changes required.

### 10.3 Existing IO IDs

`IntelligenceObject.io_id` is derived from `event_id` and `event_version`, not from evidence content. Evidence improvement does not change IO IDs.

---

## 11. V37.2 Decision

**Decision: B — HYBRID STRUCTURAL EVIDENCE**

### Justification

**Option A (Keep sentence slicing)** is rejected. The V37.1 experiment confirmed that sentence slicing on flattened text cannot be made reliable for BEA/Census/Fed documents at the level required by the DIRECT evidence standard. The 4 true malformed outputs in +51 recoveries represent a ~7.8% corruption rate. Adding more heuristics (abbreviation whitelist, domain-leak detection) will reduce this number temporarily but cannot eliminate the class of failure.

**Option C (Full structural evidence)** is premature. Full structural evidence requires:
1. Parsing ALL documents on ingest (not just at evidence-selection time)
2. Storing segments persistently
3. Re-deriving all existing evidence records
4. Changing the acquisition pipeline

This is correct architecturally but the scope is Document Intelligence Engine-level, not Evidence Layer-level.

**Option B (Hybrid)** is correct because:

1. `HTMLStructureParser` and `SemanticTableParser` already exist in the test suite, are proven on the actual document corpus, and handle the failure cases from V37.1.
2. The `Evidence` contract needs only two nullable fields added — no breaking change.
3. Segments can be parsed at evidence-selection time from already-archived HTML blobs (via `Representation.raw_location`) without touching the acquisition pipeline.
4. The `fact.occurrence` field already exists to handle multi-number disambiguation.
5. The migration is gradual: new evidence records carry `segment_id`; old ones remain valid.

The boundary between B and C: in Hybrid mode, segments are derived on-demand from archived HTML. In Full mode, segments are stored as first-class objects in the store. The Hybrid approach can be implemented without schema changes to the store.

---

## 12. Implementation Readiness Assessment

If V37.2 ARCHITECTURE REVIEW PASSES, the following are available for immediate promotion to production:

| Component | Source | Readiness |
|-----------|--------|-----------|
| `HTMLStructureParser` | `v15_recall_recovery.py` | Promote with minor additions (FOOTNOTE, QUOTE types) |
| `SemanticTableParser` | `v25r_semantic_table_parser.py` | Promote as-is |
| `is_navigation_content()` | `v9_navigation_exclusion.py` | Promote, supplement with structural exclusion |
| `EvidenceSegmentV1` dataclass | NEW | ~50 lines |
| `select_evidence_segment()` | NEW | ~80 lines |
| `Evidence` contract addition | `contracts.py` | 2 nullable fields |

Total new production code estimate: ~200 lines. No changes to pipeline.py, extract.py, delivery.py, or store.py.

---

*Design document only. No code has been implemented or committed.*
