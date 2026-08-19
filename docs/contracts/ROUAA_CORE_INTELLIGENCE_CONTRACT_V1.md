# ROUAA CORE INTELLIGENCE CONTRACT V1 — CANONICAL (R2 RESTORED + K1/K2 PROMOTED)

**Status:** CANONICAL CONTRACT — single authority restored per user decision **R2** (supersedes the CONFLICT audit state recorded at `db3079a`; that audit text remains in git history). K1/K2 promoted per **CORE_SEMANTIC_PROMOTION_K1_K2_V1** — `event_type` and `temporal_data` are now EMITTED canonical fields (no longer architectural capability gaps).
**Date:** 2026-08-17 (R2 restoration) — K1/K2 promotion 2026-08-17
**Authority:** the ratified architecture (`e0964f5` §L) + the validated implementation lineage (`9af81b7→8de74e9`, extraction `743c3bf`, Gates D–F proven). Consumers adapt to the Core; the Core never changes to satisfy a consumer.

---

## 1. CANONICAL ENDPOINT AUTHORITY (one surface)

```text
GET /health                        (public)
GET /v1/intelligence               (Bearer token; cursor pagination; ETag/304)
GET /v1/intelligence/{io_id}       (Bearer token; ETag/304; 404)
GET /v1/intelligence/{io_id}/trace (Bearer token; chain)
POST/PUT/PATCH/DELETE              405 READ_ONLY — products cannot mutate Core truth
```

- **Production implementation: IMPLEMENTED** per S1 staging item (`intelligence_core/production_transport.py`). No alias, no second surface.
- **Canonical development/test reference:** `tools/mock_core/mock_core_server.py` — fixtures are exact real IO shapes from the validated lineage (incl. the v1 SUPERSEDED → v2 ACTIVE pair with `+0.3`/`+0.4`, now with K1 `event_type` and K2 `temporal_data` per promotion). Conformance suite: `tools/mock_core/test_mock_core_contract.py` — **15/15 green** (M1–M8 + K1/K2 promotion tests).
- The parallel `/api/v1/intelligence-objects` surface is **removed from the production Core path** — archived verbatim at `archive/unauthorized-contract/` with a README (historical evidence; do not import or run).

## 2. CANONICAL SCHEMA — exactly what the Core produces (R2 §7 + K1/K2 promotion)

### 2.1 IntelligenceObject item (data contract — IMPLEMENTED, binding)

| Field | Type | Required | Meaning | Source |
|---|---|---|---|---|
| `io_id` | string | yes | canonical identity `io-<sha256(event_id:event_version)[:16]>` | `identity.io_id` |
| `version` | int | yes | IO record version — **constant `1`** in the current implementation | `contracts.IntelligenceObject` |
| `event_id` | string | yes | logical event identity | store events |
| `event_version` | int | yes | D2 derivation version (1, 2, …) — THE versioning axis | store events |
| `headline` | string | yes | template-generated headline | `detect.EVENT_TYPE_RULES` |
| `chain` | array | yes | full traceability chain (§2.2) | `delivery.build_intelligence_object` |
| `created_at` | string | yes | IO creation timestamp | delivery |
| `status` | enum | transport projection | `ACTIVE \| SUPERSEDED` — projected from the event row's real state | store events |
| `supersedes_io_id` | string? | transport projection | prior-version IO identity (version lineage) | derived from event versions |
| **`event_type`** | string | **yes (K1 PROMOTED)** | the Core Event Type (one of 6 supported types) — **direct copy from `Event.event_type`** | `Event.event_type` (store) → `delivery.build_intelligence_object` |
| **`temporal_data`** | object? | **yes (K2 PROMOTED)** | D4 publication/reference period projection — **derived from `Document.publication_tuples`** | `Document.publication_tuples` (store) → `delivery._project_temporal_data` |

### 2.1.1 K2 temporal_data sub-fields (D4 projection)

Per CORE_SEMANTIC_PROMOTION_K1_K2_V1 §4-5. null = NOT_APPLICABLE / UNKNOWN (never fabricated).

| Sub-field | Type | Source |
|-----------|------|--------|
| `publication_time` | string? | `normalized_utc` of the publication tuple (`timestamp_semantics == "publication"`) |
| `publication_time_raw` | string? | `original_value` of the same tuple |
| `publication_timezone_status` | string? | `timezone_status` of the same tuple |
| `reference_period` | string? | `normalized_utc` of the reference-period tuple (`timestamp_semantics == "reporting_period"`) |
| `reference_period_normalized_utc` | string? | same as `reference_period` (kept explicit for D4-clarity) |

**D4 §9 distinction (critical):** `reference_period != publication_time` when both exist. For statistical releases, this preserves "when published" vs "what period the statistics cover". For regulatory actions, `reference_period` is null (no statistical reference period).

### 2.2 Chain link (per fact)

`fact{fact_id, fact_version, metric, value}` · `evidence[{evidence_id, excerpt(≤120), representation_id}]` · `representation{representation_id, content_sha256}` · `document{document_id, canonical_url}` · `source{source_id, institution_id}` — all store-derived, all binding. Institution/source/document data is available to consumers HERE (no top-level duplicates).

### 2.3 Feed envelope

`{objects: [item…], next_cursor: string|null}` + `ETag` / `If-None-Match` → `304`. Errors: `{error:{code, message}}` (401/404/405/429/5xx).

## 3. PROHIBITED FIELDS (anti-fabrication register — K1/K2 promotion did NOT add these)

| Field / Endpoint | Status | Rule |
|---|---|---|
| `provenance_complete` | **FABRICATED_CONTRACT_FIELD — PROHIBITED** (exists nowhere in Core) | never added to satisfy a consumer |
| `confidence_score` | **FABRICATED_CONTRACT_FIELD — PROHIBITED** | separate architectural decision only |
| `reproducible` | **FABRICATED_CONTRACT_FIELD — PROHIBITED** | same |
| `quality_metadata` | **FABRICATED_CONTRACT_FIELD — PROHIBITED** | same |
| `provenance_match` | **FABRICATED_CONTRACT_FIELD — PROHIBITED** | same |
| `/trace` production | **design-mandated** (architecture §L); production IMPLEMENTED per S1 | — |

## 4. VERSIONING SEMANTICS (R2 §8)

`io.version = 1` (constant). The lineage axis is `event_version`: a corrected source ⇒ new event version ⇒ **new `io_id`** with `supersedes_io_id` → prior; the prior remains exactly reproducible (D2; unit Cases A–F + simulation-proven). Consumers treat versions as distinct immutable objects — never overwrite, never fork. **No consumer-specific version semantics.**

## 5. FAILURE SEMANTICS (R2 §9)

A broken evidence/document relationship is a **verification failure** — explicit error, never silently ignorable. The archived `contract_api._handle_list` `except: continue` pattern is recorded as the anti-pattern; the canonical mock/tests enforce explicit 404/error paths; production S1 implements explicit failure classification (broken-chain ⇒ `500 CHAIN_BROKEN`, not omission).

## 6. CONSUMER OBLIGATIONS

Consume `/v1` only · Bearer token (env-provided, server-side; never logged, committed, or browser-exposed) · cursor pagination · idempotency by (`io_id`, `event_version`) · no mutations (405 enforced) · no reliance on anything in §3 · K1/K2 fields (`event_type`, `temporal_data`) MAY be consumed directly (no inference, no fabrication).

## 7. K1/K2 PROMOTION HISTORY (CORE_SEMANTIC_PROMOTION_K1_K2_V1)

- **Before promotion** (R2 state, `e82c34a` → pre-K1/K2 promotion): `event_type` and `temporal_data` were declared `ARCHITECTURAL CAPABILITY GAPS` — they existed in store state (Event.event_type, Document.publication_tuples) but were NOT surfaced in IO emission.
- **Promotion rationale**: For a global intelligence platform, `event_type` ("what is the event?") and `temporal_data` ("when was it published? what period does it cover?") are part of the IO's meaning — not optional metadata. Consumers (News, future Trading/Corporate) need them to make product decisions.
- **Promotion implementation**: `delivery.build_intelligence_object()` now copies `event_type` directly from `Event.event_type` (no inference) and projects `temporal_data` from `Document.publication_tuples` per D4 (no fabrication).
- **Promotion is backward-compatible**: `io.version` remains `1` (constant). The new fields are additive — existing consumers that ignored them continue to work. The contract authority (R2 restoration) remains; this is field-additive promotion, not contract redesign.

---

**Freeze remains for consumers: News / Trading / Corporate unchanged until reconciliation is directed. Wave-1 qualification, Source Registry, and activation state untouched — this was contract governance + K1/K2 promotion only.**
