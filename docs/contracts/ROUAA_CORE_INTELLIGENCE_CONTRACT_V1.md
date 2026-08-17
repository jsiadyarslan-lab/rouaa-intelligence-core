# ROUAA CORE INTELLIGENCE CONTRACT V1 — CANONICAL (R2 RESTORED)

**Status:** CANONICAL CONTRACT — single authority restored per user decision **R2** (supersedes the CONFLICT audit state recorded at `db3079a`; that audit text remains in git history)
**Date:** 2026-08-17 (R2 restoration)
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

- **Production implementation: `NOT_IMPLEMENTED`** (service layer = staging item S1 under Gate-G execution; no alias, no second surface).
- **Canonical development/test reference:** `tools/mock_core/mock_core_server.py` — fixtures are exact real IO shapes from the validated lineage (incl. the v1 SUPERSEDED → v2 ACTIVE pair with `+0.3`/`+0.4`). Conformance suite: `tools/mock_core/test_mock_core_contract.py` — **11/11 green** (M1–M8).
- The parallel `/api/v1/intelligence-objects` surface is **removed from the production Core path** — archived verbatim at `archive/unauthorized-contract/` with a README (historical evidence; do not import or run).

## 2. CANONICAL SCHEMA — exactly what the Core produces (R2 §7)

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

### 2.2 Chain link (per fact)

`fact{fact_id, fact_version, metric, value}` · `evidence[{evidence_id, excerpt(≤120), representation_id}]` · `representation{representation_id, content_sha256}` · `document{document_id, canonical_url}` · `source{source_id, institution_id}` — all store-derived, all binding. Institution/source/document data is available to consumers HERE (no top-level duplicates).

### 2.3 Feed envelope

`{objects: [item…], next_cursor: string|null}` + `ETag` / `If-None-Match` → `304`. Errors: `{error:{code, message}}` (401/404/405/429/5xx).

## 3. NOT AVAILABLE / DELIBERATELY ABSENT (anti-fabrication register)

| Field / Endpoint | Status | Rule |
|---|---|---|
| `provenance_complete` | **NOT AVAILABLE — FABRICATED_CONTRACT_FIELD** (exists nowhere in Core) | never added to satisfy a consumer |
| `confidence_score` | **NOT AVAILABLE — FABRICATED_CONTRACT_FIELD** | separate architectural decision only |
| `reproducible` | **NOT AVAILABLE — FABRICATED_CONTRACT_FIELD** | same |
| `event_type` (as an emitted field) | **ARCHITECTURAL CAPABILITY GAP** (exists in store event rows; NOT surfaced in IO emission) | separate Core contract decision |
| `temporal_data` (in IO/chain) | **ARCHITECTURAL CAPABILITY GAP** (tuples live on documents; NOT surfaced) | separate Core contract decision |
| `/trace` production | **design-mandated** (architecture §L); production `NOT_IMPLEMENTED` | lands with S1 |

## 4. VERSIONING SEMANTICS (R2 §8)

`io.version = 1` (constant). The lineage axis is `event_version`: a corrected source ⇒ new event version ⇒ **new `io_id`** with `supersedes_io_id` → prior; the prior remains exactly reproducible (D2; unit Cases A–F + simulation-proven). Consumers treat versions as distinct immutable objects — never overwrite, never fork. **No consumer-specific version semantics.**

## 5. FAILURE SEMANTICS (R2 §9)

A broken evidence/document relationship is a **verification failure** — explicit error, never silently ignorable. The archived `contract_api._handle_list` `except: continue` pattern is recorded as the anti-pattern; the canonical mock/tests enforce explicit 404/error paths; production S1 must implement explicit failure classification (broken-chain ⇒ error, not omission).

## 6. CONSUMER OBLIGATIONS

Consume `/v1` only · Bearer token (env-provided, server-side; never logged, committed, or browser-exposed) · cursor pagination · idempotency by (`io_id`, `event_version`) · no mutations (405 enforced) · no reliance on anything in §3.

---

**Freeze remains for consumers: News / Trading / Corporate unchanged until reconciliation is directed. Wave-1 qualification, Source Registry, and activation state untouched — this was contract governance only.**
