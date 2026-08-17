# ROUAA Canonical Intelligence Object Readiness Gate V1

> **Directive**: EXECUTION DIRECTIVE — CANONICAL IO READINESS GATE V1
> **Date**: 2026-08-17
> **Assessment type**: Static contract assessment (no code changes, no redesign)
> **Final verdict**: `CANONICAL IO READY — SHARED CORE PRIMITIVE` (see §M)

---

## A. Exact current IO schema (verified from code)

### A.1 IntelligenceObject dataclass (`intelligence_core/contracts.py`)

```python
@dataclass
class IntelligenceObject:
    io_id: str                                                    # CANONICAL_INTELLIGENCE
    version: int                                                  # CANONICAL_INTELLIGENCE (constant 1)
    event_id: str                                                 # CANONICAL_INTELLIGENCE
    event_version: int                                            # CANONICAL_INTELLIGENCE (lineage axis)
    headline: str                                                 # CANONICAL_INTELLIGENCE
    chain: list = field(default_factory=list)                     # CANONICAL_INTELLIGENCE
    created_at: str = ""                                          # CANONICAL_INTELLIGENCE
    event_type: str = ""                                          # CANONICAL_INTELLIGENCE (K1 promoted)
    temporal_data: Optional[TemporalDataProjection] = None       # CANONICAL_INTELLIGENCE (K2 promoted)
```

### A.2 Transport projections (added by `production_transport.py`)

```python
obj["status"] = ...           # TRANSPORT_PROJECTION (from Event.status: ACTIVE | SUPERSEDED)
obj["supersedes_io_id"] = ... # TRANSPORT_PROJECTION (from event_version lineage)
```

### A.3 Complete field set emitted via `/v1/intelligence`

| # | Field | Type | Classification |
|---|-------|------|----------------|
| 1 | `io_id` | string | CANONICAL_INTELLIGENCE |
| 2 | `version` | int (constant 1) | CANONICAL_INTELLIGENCE |
| 3 | `event_id` | string | CANONICAL_INTELLIGENCE |
| 4 | `event_version` | int | CANONICAL_INTELLIGENCE |
| 5 | `headline` | string | CANONICAL_INTELLIGENCE |
| 6 | `chain` | array | CANONICAL_INTELLIGENCE |
| 7 | `created_at` | string | CANONICAL_INTELLIGENCE |
| 8 | `event_type` | string | CANONICAL_INTELLIGENCE (K1) |
| 9 | `temporal_data` | object? | CANONICAL_INTELLIGENCE (K2) |
| 10 | `status` | enum | TRANSPORT_PROJECTION |
| 11 | `supersedes_io_id` | string? | TRANSPORT_PROJECTION |

### A.4 temporal_data sub-structure

| Sub-field | Type | Source |
|-----------|------|--------|
| `temporal_tuples` | array | D4 `Document.publication_tuples[]` — full cardinality |
| `publication_time` | string? | D4 `normalized_utc` (convenience accessor) |
| `publication_time_raw` | string? | D4 `original_value` (convenience) |
| `publication_timezone_status` | string? | D4 `timezone_status` (convenience) |
| `publication_normalization_basis` | string? | D4 `normalization_basis` (convenience) |
| `publication_timestamp_semantics` | string? | D4 `timestamp_semantics` (convenience) |
| `publication_provenance_source` | string? | D4 `provenance_source` (convenience) |
| `reference_period` | string? | D4 `normalized_utc` (convenience) |
| `reference_period_normalized_utc` | string? | D4 alias (convenience) |
| `reference_period_raw` | string? | D4 `original_value` (convenience) |
| `reference_period_timezone_status` | string? | D4 `timezone_status` (convenience) |
| `reference_period_normalization_basis` | string? | D4 `normalization_basis` (convenience) |
| `reference_period_timestamp_semantics` | string? | D4 `timestamp_semantics` (convenience) |
| `reference_period_provenance_source` | string? | D4 `provenance_source` (convenience) |

### A.5 Chain link structure (per chain element)

```
fact:          {fact_id, fact_version, metric, value}
evidence:      [{evidence_id, excerpt, representation_id}]
representation: {representation_id, content_sha256}
document:      {document_id, canonical_url}
source:        {source_id, institution_id}
```

### A.6 No unexpected fields

The IO contains exactly 11 top-level fields (9 CANONICAL_INTELLIGENCE + 2 TRANSPORT_PROJECTION). No PRESENTATION_DERIVED or CONSUMER_SPECIFIC fields exist.

---

## B. Field classification

| Field | Classification | Rationale |
|-------|---------------|-----------|
| `io_id` | CANONICAL_INTELLIGENCE | SHA-derived identity — the canonical IO identifier |
| `version` | CANONICAL_INTELLIGENCE | IO record version (constant 1 per D7) |
| `event_id` | CANONICAL_INTELLIGENCE | Logical event identity (D2) |
| `event_version` | CANONICAL_INTELLIGENCE | D2 derivation version — THE lineage axis |
| `headline` | CANONICAL_INTELLIGENCE | Template-generated from event_type + source (detect.py) |
| `chain` | CANONICAL_INTELLIGENCE | Full 5-level provenance chain (D7) |
| `created_at` | CANONICAL_INTELLIGENCE | IO construction timestamp |
| `event_type` | CANONICAL_INTELLIGENCE | K1 promoted — direct copy from Event.event_type |
| `temporal_data` | CANONICAL_INTELLIGENCE | K2 promoted — D4 publication_tuples projected |
| `status` | TRANSPORT_PROJECTION | Derived from Event.status (ACTIVE/SUPERSEDED) |
| `supersedes_io_id` | TRANSPORT_PROJECTION | Derived from event_version lineage |

**No PRESENTATION_DERIVED fields.** No CONSUMER_SPECIFIC fields. The IO is pure canonical intelligence + documented transport projections.

---

## C. Semantic sufficiency

Using only the canonical IO, can a consumer answer:

| Question | Answer source | Classification |
|----------|-------------|----------------|
| WHAT happened? | `event_type` (K1) + `headline` | SUPPORTED_DIRECTLY |
| WHEN did it happen / get published? | `temporal_data.publication_time` (K2) | SUPPORTED_DIRECTLY |
| WHAT period does it concern? | `temporal_data.reference_period` (K2, null when N/A) | SUPPORTED_DIRECTLY |
| WHERE did the information originate? | `chain[0].source.institution_id` + `chain[0].document.canonical_url` | SUPPORTED_THROUGH_CHAIN |
| WHAT evidence supports it? | `chain[].evidence[].excerpt` + `chain[].evidence[].evidence_id` | SUPPORTED_THROUGH_CHAIN |
| WHICH event version is this? | `event_version` | SUPPORTED_DIRECTLY |
| WHICH prior version did it supersede? | `supersedes_io_id` (transport projection) | SUPPORTED_DIRECTLY |

**All 7 questions are either SUPPORTED_DIRECTLY or SUPPORTED_THROUGH_CHAIN.** None requires inference. None is NOT_AVAILABLE.

---

## D. Provenance sufficiency

The complete canonical chain is embedded in the IO:

```
IntelligenceObject
  → chain[0].fact       {fact_id, fact_version, metric, value}
  → chain[0].evidence   [{evidence_id, excerpt, representation_id}]
  → chain[0].representation {representation_id, content_sha256}
  → chain[0].document    {document_id, canonical_url}
  → chain[0].source      {source_id, institution_id}
```

A consumer can reconstruct the full provenance chain using **Core IO data only** — no direct Core database access, no external source lookup required.

Every chain link contains:
- Fact identity + version + metric + value (what was extracted)
- Evidence identity + excerpt + representation binding (what text supports it)
- Representation identity + content SHA-256 (content-addressed verification)
- Document identity + canonical URL (where the document lives)
- Source identity + institution identity (who published it)

**Provenance is SUFFICIENT.** The consumer can trace from IO → fact → evidence → representation → document → source → institution using only the IO's chain.

---

## E. Version sufficiency

| Field | Value | Consumer can distinguish |
|-------|-------|------------------------|
| `io_id` | SHA-derived from (event_id, event_version) | ✅ Unique per event version |
| `version` | 1 (constant) | ✅ IO record version (always 1 — D7) |
| `event_version` | 1, 2, 3, ... | ✅ THE lineage axis (D2) |
| `status` | ACTIVE \| SUPERSEDED | ✅ Whether this is current |
| `supersedes_io_id` | prior io_id or null | ✅ Which version was superseded |

Consumer can distinguish:
- **ACTIVE** (current version): `status == "ACTIVE"` ✅
- **SUPERSEDED** (historical version): `status == "SUPERSEDED"` ✅
- **Corrected version**: `event_version > 1` + `supersedes_io_id != null` ✅
- **Historical version**: `status == "SUPERSEDED"` + still retrievable (immutable) ✅

The canonical mock's v1 SUPERSEDED → v2 ACTIVE pair demonstrates this:
```
io-cpi-v1: {event_version: 1, status: SUPERSEDED, supersedes_io_id: null}
io-cpi-v2: {event_version: 2, status: ACTIVE,    supersedes_io_id: "io-cpi-v1"}
```

**Versioning is SUFFICIENT.**

---

## F. Temporal sufficiency

| Requirement | Status | Evidence |
|-------------|--------|----------|
| All D4 tuples preserved | ✅ PASS | `temporal_tuples[]` array — cardinality == `Document.publication_tuples.length` |
| All 6 D4 fields per tuple | ✅ PASS | `TemporalTupleProjection` has all 6 fields |
| Tuple ordering | ✅ PASS | Original D4 order preserved (M9.order test) |
| `timestamp_semantics` | ✅ PASS | All 7 values supported distinctly |
| `provenance_source` | ✅ PASS | Per-tuple provenance preserved |
| `normalization_basis` | ✅ PASS | Ordering participation determinable |
| Multiple tuples | ✅ PASS | 3-tuple fixture verified (M9.card) |
| Conflicting tuples | ✅ PASS | Conflicting dates preserved (M9.conflict) |
| Unknown/date-only cases | ✅ PASS | `timezone_status=DATE_ONLY`, `normalization_basis=NONE`, `normalized_utc` preserved as-is |

**Temporal is SUFFICIENT.** D4 is fully represented — fields, semantics, provenance, AND cardinality.

---

## G. Event semantics

`event_type` is authoritative Core state:
- Source: `Event.event_type` (store row) → direct copy to `IntelligenceObject.event_type` (K1)
- One of 6 supported types: `monetary_policy_decision`, `regulatory_enforcement`, `statistical_release`, `earnings_release`, `sanctions_designation`, `market_statistic_release`
- No new Event Types added
- No consumer-side classification or reinterpretation

**News audit (verified from code):**
- `StoryCandidate.event_type = io.event_type` — direct copy, no inference ✅
- News does NOT independently classify events ✅
- News does NOT reinterpret `event_type` ✅
- News does NOT parse headline to infer event type ✅

**Event semantics are AUTHORITATIVE.**

---

## H. News consumer audit

Inspected `rouatradingnews/src/lib/core-integration/core-adapter.ts` at commit `66f4cbb`:

| Canonical meaning | News behavior | Classification |
|-------------------|--------------|----------------|
| `event_type` | Consumed directly from `io.event_type` | ✅ CORE_CANONICAL (no gap) |
| `temporal_data` | Consumed directly from `io.temporal_data` | ✅ CORE_CANONICAL (no gap) |
| `temporal_tuples[]` | Consumed directly from `io.temporal_data.temporal_tuples` | ✅ CORE_CANONICAL (no gap) |
| `created_at` | Consumed directly from `io.created_at` | ✅ CORE_CANONICAL (no gap) |
| `status` | Consumed directly from `io.status` | ✅ CORE_CANONICAL (no gap) |
| `supersedes_io_id` | Consumed directly from `io.supersedes_io_id` | ✅ CORE_CANONICAL (no gap) |
| `headline` | Consumed directly from `io.headline` | ✅ CORE_CANONICAL (no gap) |
| `chain` facts/evidence/representation/document/source | Extracted into `facts`, `evidence_refs`, `document_ref`, `traceability` | LEGITIMATE_PRODUCT_DERIVATION (reorganization for News's internal use) |
| `candidate_id` | News-constructed (`sc_{io_id}_ev{event_version}`) | LEGITIMATE_PRODUCT_DERIVATION |
| `received_at` | News-constructed timestamp | LEGITIMATE_PRODUCT_DERIVATION |
| `compareDualRun.event_match` | Based on `candidate.event_type` (from Core) | ✅ CORE_CANONICAL |
| `compareDualRun.temporal_match` | Based on `candidate.temporal.publication_time` (from Core) | ✅ CORE_CANONICAL |

**News does NOT infer, reconstruct, or reinterpret any canonical meaning.** All canonical fields are consumed directly. Product-specific derivations (`candidate_id`, `received_at`, traceability reorganization) are legitimate product concerns — not Core gaps.

### No CORE_CANONICAL_GAP found in News.

---

## I. Trading simulation (static contract simulation)

**Can Trading consume the current IO without defining new canonical Core semantics?**

| Trading need | IO source | Available? |
|-------------|-----------|:----------:|
| What type of event? | `event_type` (e.g. `monetary_policy_decision`) | ✅ |
| What was the rate decision? | `chain[].fact` where `metric == "policy_rate"` or `"rate_decision"` | ✅ |
| When was the decision published? | `temporal_data.publication_time` | ✅ |
| Which central bank? | `chain[0].source.institution_id` | ✅ |
| Is this the latest version? | `status == "ACTIVE"` | ✅ |
| What did it supersede? | `supersedes_io_id` | ✅ |
| Document URL for verification? | `chain[0].document.canonical_url` | ✅ |
| Evidence excerpt for the rate? | `chain[].evidence[].excerpt` | ✅ |

**Trading CAN consume the current IO without new canonical fields.** All required semantic information is available.

### No CORE_CANONICAL_GAP for Trading.

---

## J. Corporate simulation (static contract simulation)

**Can Corporate consume the current IO without defining new canonical Core semantics?**

| Corporate need | IO source | Available? |
|---------------|-----------|:----------:|
| What type of enforcement? | `event_type` (e.g. `regulatory_enforcement`) | ✅ |
| What action was taken? | `chain[].fact` where `metric == "action_type"` | ✅ |
| What was the penalty? | `chain[].fact` where `metric == "penalty_amount"` | ✅ |
| When was it published? | `temporal_data.publication_time` | ✅ |
| Which regulator? | `chain[0].source.institution_id` | ✅ |
| Is this the latest version? | `status == "ACTIVE"` | ✅ |
| Document URL for compliance? | `chain[0].document.canonical_url` | ✅ |
| Evidence excerpt? | `chain[].evidence[].excerpt` | ✅ |

**Corporate CAN consume the current IO without new canonical fields.** All required semantic information is available.

### No CORE_CANONICAL_GAP for Corporate.

---

## K. Gap classification

| # | Gap | Classification | Severity | Blocks readiness? |
|---|-----|---------------|----------|:-----------------:|
| 1 | Real HCP `reference_period` is null (RSS provides publication but not reporting period) | DATA_AVAILABILITY_GAP | Low | ❌ No — D4-faithful null; future extraction capability |
| 2 | ECB E2E timeout (100K+ byte HTML pages) | SOURCE_ACQUISITION_GAP | Low | ❌ No — environmental, not contract |
| 3 | Cursor pagination with concurrent `derived_at` | TRANSPORT_GAP | Low | ❌ No — future composite cursor |
| 4 | PDF document ingestion not supported | OUT_OF_SCOPE | — | ❌ No — D10 design decision |
| 5 | No `monetary_policy_decision` IO in real E2E store | DATA_AVAILABILITY_GAP | Low | ❌ No — canonical mock covers it |

**No CORE_CANONICAL_GAP found.** All gaps are data availability, source acquisition, or transport limitations — not contract semantic gaps.

---

## L. Required changes

**None.** The current IntelligenceObject schema is semantically sufficient as a shared canonical primitive. No canonical field additions, removals, or semantic changes are required for News, Trading, or Corporate consumption.

The bounded gaps (§K) are environmental/extraction limitations — not contract gaps. They can be addressed in future tasks without modifying the IO schema.

---

## M. Readiness verdict

### `CANONICAL IO READY — SHARED CORE PRIMITIVE`

### Conditions evaluated

| Condition | Result |
|-----------|--------|
| IO schema is complete and stable | ✅ 11 fields (9 canonical + 2 transport) — no unexpected fields |
| Semantic sufficiency: all 7 consumer questions answerable | ✅ All SUPPORTED_DIRECTLY or SUPPORTED_THROUGH_CHAIN |
| Provenance sufficiency: full chain reconstructable from IO | ✅ chain[0] → fact → evidence → representation → document → source → institution |
| Version sufficiency: ACTIVE/SUPERSEDED/corrected/historical distinguishable | ✅ status + event_version + supersedes_io_id |
| Temporal sufficiency: D4 fully preserved (fields + semantics + provenance + cardinality) | ✅ temporal_tuples[] with all 6 D4 fields per tuple |
| Event semantics: authoritative, no consumer inference | ✅ event_type direct copy from Event.event_type |
| News audit: no CORE_CANONICAL_GAP | ✅ All canonical meaning consumed directly |
| Trading simulation: can consume without new canonical fields | ✅ All required info available |
| Corporate simulation: can consume without new canonical fields | ✅ All required info available |
| Field governance: no fabricated/forbidden fields | ✅ 0 of 8 forbidden fields present |
| No CORE_CANONICAL_GAP discovered | ✅ All gaps are DATA_AVAILABILITY / SOURCE_ACQUISITION / TRANSPORT |
| Tests: 244/244 PASS | ✅ Core 100 + Mock 36 + News 39+29+28+12 |
| Secret scan: 0 findings | ✅ |

### What this means

The IntelligenceObject is the **correct permanent boundary** between ROUAA Core and all future products. It carries:

- **WHAT happened** → `event_type` (K1)
- **WHEN it was published** → `temporal_data.publication_time` (K2)
- **WHAT period it covers** → `temporal_data.reference_period` (K2, D4 §9)
- **WHERE it originated** → `chain[0].source.institution_id` + `chain[0].document.canonical_url`
- **WHAT evidence supports it** → `chain[].evidence[].excerpt`
- **WHICH version** → `event_version` + `status` + `supersedes_io_id`
- **FULL D4 temporal multiplicity** → `temporal_data.temporal_tuples[]`

No consumer (News, Trading, Corporate) needs to define new canonical Core semantics to use this IO. The IO is the shared primitive.

---

## N. Test results (§12)

| # | Suite | Tests | Pass |
|---|-------|------:|-----:|
| 1 | Core unit | 100 | 100 |
| 2 | Canonical mock (M1-M9) | 36 | 36 |
| 3 | News adapter | 39 | 39 |
| 4 | News live V2 (canonical mock) | 29 | 29 |
| 5 | News live production | 28 | 28 |
| 6 | News real E2E | 12 | 12 |
| **Total** | | **244** | **244** |

Secret scan: 0 findings across both repos.

---

## O. Field governance verification (§9)

| Forbidden field | Present in IO? |
|-----------------|:--------------:|
| `confidence_score` | ❌ ABSENT ✅ |
| `quality_metadata` | ❌ ABSENT ✅ |
| `provenance_complete` | ❌ ABSENT ✅ |
| `reproducible` | ❌ ABSENT ✅ |
| `recommendation` | ❌ ABSENT ✅ |
| `trading_signal` | ❌ ABSENT ✅ |
| `editorial_score` | ❌ ABSENT ✅ |
| `customer_specific` | ❌ ABSENT ✅ |

**0 of 8 forbidden fields present. Contract boundary is clean.**
