# ROUAA Core Semantic Enrichment Contract V1

> **Directive**: CORE V37 — Evidence Recovery and Semantic Enrichment
> **Date**: 2026-08-19
> **Parent**: Canonical Intelligence Contract V1 (from V36)
> **Status**: PROPOSED

---

## A. Purpose

This contract extends the Canonical Intelligence Contract V1 to add semantic enrichment fields:
- Entity (P1)
- Unit (P2)
- Period (P1)
- Quality Metadata (P2)

**Design principle:** These fields are ADDITIVE — existing consumers remain compatible.

---

## B. Extended Intelligence Object

### B.1 New Optional Fields

| Section | Field | Type | Status | Example |
|---------|-------|------|--------|---------|
| I. CONTEXT | entity | string \| null | Optional | "SEC", "Eurostat", "Apple Inc." |
| I. CONTEXT | unit | string \| null | Optional | "%", "USD million", "bps" |
| I. CONTEXT | period | string \| null | Optional | "Q1 2026", "2025", "YoY" |
| H. QUALITY | confidence_score | float \| null | Optional | 0.95 |
| H. QUALITY | quality_metadata | object \| null | Optional | see §C |

### B.2 Field Semantics

#### entity (I.CONTEXT)

The primary entity associated with the intelligence:
- **Statistical releases**: Country or region (e.g., "United States", "Euro Area")
- **Monetary policy decisions**: Central bank (e.g., "ECB", "Federal Reserve")
- **Regulatory enforcement**: Company or individual (e.g., "Goldman Sachs", "John Doe")

**Extraction source:**
- From fact excerpt (named entity recognition)
- From document metadata (source institution)
- From evidence context

**Null semantics:** `null` = entity not extracted or ambiguous (NOT "unknown")

#### unit (I.CONTEXT)

The unit of measurement for the fact value:
- **Percentages**: "%", "percent", "percentage points", "bps"
- **Currency**: "USD", "EUR", "USD million", "EUR billion"
- **Absolute**: "level", "index", "count"

**Normalization rules:**
- "%" → "percent"
- "pct" → "percent"
- "basis points" → "bps"
- "$" → "USD"
- "€" → "EUR"

**Null semantics:** `null` = unit embedded in raw_value or not determinable

#### period (I.CONTEXT)

The reference period for the fact:
- **Quarterly**: "Q1 2026", "Q2 2025"
- **Annual**: "2025", "FY2026"
- **Monthly**: "June 2026", "2026-06"
- **Change type**: "YoY", "MoM", "QoQ"

**Extraction source:**
- From fact excerpt (temporal expressions)
- From document temporal tuples (reporting_period)
- From URL patterns

**Null semantics:** `null` = period not specified or ambiguous

#### confidence_score (H.QUALITY)

A float between 0.0 and 1.0 indicating extraction confidence:
- **1.0**: Direct evidence, exact pattern match, strong context
- **0.9-0.99**: Direct evidence, minor ambiguity
- **0.7-0.89**: Indirect evidence recovered, moderate confidence
- **<0.7**: Weak evidence, high ambiguity (likely rejected)

**Computation:**
```
confidence_score = weighted_average(
    evidence_classification_weight,  # DIRECT=1.0, INDIRECT=0.7
    pattern_confidence_weight,       # Exact match=1.0, fuzzy=0.8
    context_completeness_weight      # All fields present=1.0, partial=0.7
)
```

**Null semantics:** `null` = confidence not computed (legacy extraction)

#### quality_metadata (H.QUALITY)

Detailed quality information:

```json
{
  "evidence_classification": "DIRECT" | "INDIRECT" | "RECOVERED",
  "pattern_match_type": "EXACT" | "FUZZY" | "HEURISTIC",
  "context_fields_present": {
    "metric": true,
    "unit": false,
    "entity": true,
    "period": false
  },
  "recovery_method": null | "SENTENCE_EXPANSION" | "TABLE_CONTEXT" | "HEADING_CONTEXT",
  "ambiguity_flags": []
}
```

---

## C. Extended Fact Contract

### C.1 New Optional Fields

```python
@dataclass
class Fact:
    # Existing fields (V1):
    fact_id: str
    fact_version: int
    representation_id: str
    document_id: str
    metric: str
    value: str
    raw_value: str
    pattern_ref: str
    occurrence: int
    excerpt: str
    status: ObjState
    
    # V37 additions:
    unit: Optional[str] = None       # Normalized unit
    entity: Optional[str] = None     # Extracted entity
    period: Optional[str] = None     # Reference period
    confidence_score: Optional[float] = None
```

### C.2 Backward Compatibility

Existing consumers reading `fact.value` and `fact.raw_value` continue to work:
- `raw_value` still contains the full extracted text (e.g., "0.3%")
- `value` still contains the normalized value (e.g., "0.3")
- New `unit` field provides explicit separation (e.g., "percent")

---

## D. Extended IntelligenceObject Contract

### D.1 New Optional Fields

```python
@dataclass
class IntelligenceObject:
    # Existing fields (V1):
    io_id: str
    version: int
    event_id: str
    event_version: int
    headline: str
    chain: list
    created_at: str
    event_type: str
    temporal_data: Optional[TemporalDataProjection]
    
    # V37 additions:
    entity: Optional[str] = None         # Primary entity (institution/country/company)
    summary_facts: list = None           # Top facts for headline generation
```

### D.2 Summary Facts for Headline Generation

```python
@dataclass
class SummaryFact:
    metric: str
    value: str
    unit: Optional[str]
    period: Optional[str]
```

**Usage in headline generation:**
```
"{entity} {metric} {value}{unit} {period}"
→ "Euro Area Inflation Rate 2.3% YoY"
→ "SEC Charges Goldman Sachs $50M Penalty"
```

---

## E. Implementation Constraints

### E.1 Do Not Break Existing Consumers

- All new fields are OPTIONAL (default `None`)
- Existing required fields unchanged
- JSON schema backward-compatible

### E.2 Do Not Fabricate Data

- `null` = NOT_APPLICABLE / UNKNOWN / NOT_EXTRACTED
- Never infer timezone from date-only values
- Never guess entity from partial context
- Never fabricate confidence scores

### E.3 Deterministic Extraction

- Same input → same output (no randomness)
- Versioned extraction logic (extraction_version field)
- Reproducible via stored excerpts

---

## F. Acceptance Criteria

Semantic enrichment ACCEPTED if:

1. **No regression in existing fields**
   - fact_id, value, raw_value unchanged for existing extractions
   - event_type, headline unchanged
   - chain integrity preserved

2. **New fields correctly populated**
   - Entity extracted for ≥80% of statistical releases
   - Unit extracted for ≥90% of percentage/currency facts
   - Period extracted for ≥70% of time-series facts

3. **Quality metadata accurate**
   - confidence_score correlates with human judgment
   - quality_metadata flags true ambiguities

4. **Performance acceptable**
   - No more than +10% latency in extraction
   - No more than +5% memory usage

---

## G. Migration Path

### G.1 Phase 1: Evidence Recovery (V37.0)

- Enhance `expand_evidence_for_direct()`
- Recover 158 EVIDENCE_SELECTION_GAP cases
- Measure TP/FP/FN impact

### G.2 Phase 2: Unit Enrichment (V37.1)

- Add `unit` field to Fact
- Normalize percentage expressions
- Normalize currency expressions

### G.3 Phase 3: Entity Enrichment (V37.2)

- Add `entity` field to Fact and IntelligenceObject
- Named entity recognition for institutions/companies/countries

### G.4 Phase 4: Period Enrichment (V37.3)

- Add `period` field to Fact
- Temporal expression extraction
- Link to Document.temporal_tuples

### G.5 Phase 5: Quality Metadata (V37.4)

- Add `confidence_score` and `quality_metadata`
- Compute based on evidence classification and context completeness

---

## H. Relationship to Downstream Contracts

### H.1 News Workflow

Consumes: entity, unit, period, summary_facts
Produces: Editorial headline, story narrative

### H.2 Trading Workflow

Consumes: entity, unit, period, confidence_score
Produces: Market impact assessment, position logic

### H.3 Corporate Workflow

Consumes: entity (company name), penalty_amount, action_type
Produces: Compliance alert, case management entry

### H.4 Research Workflow

Consumes: All fields including quality_metadata
Produces: Analysis, comparison, historical trends

---

## I. Version History

| Version | Date | Change |
|---------|------|--------|
| V1 (base) | 2026-08-19 | From V36 Canonical Contract |
| V1.1 (proposed) | 2026-08-19 | Added entity/unit/period/quality fields |

