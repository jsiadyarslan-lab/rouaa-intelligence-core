# ROUAA CORE INTELLIGENCE CONTRACT V1 — AUTHORITATIVE CONTRACT AUDIT

**Status:** CONTRACT AUDIT — FROZEN STATE RECORDED (no Core/News/Trading/Corporate changes made by this audit)
**Date:** 2026-08-17
**Directive:** EXECUTION DIRECTIVE — ROUAA CORE ↔ PRODUCT CONTRACT AUDIT V1 (user-issued verbatim)
**Method:** inspected the ACTUAL implementation only — mocks were audited AS mocks, never used as truth. Validated test suite re-run under current tree: **48/48 OK** (new files do not break the validated Core).
**Audited tree:** `rouaa-intelligence-core` @ `9f64a08` (HEAD), containing post-extraction additions `6018568→8c1751c` (parallel Phase-1: contract_api.py, mock_contract_server.py, reports) + Wave-1 docs `8e3066c→9f64a08`.

---

## 1. WHAT THE ACTUAL CORE EMITS (two layers, honestly separated)

### Layer 1 — VALIDATED DATA CONTRACT (binding; extraction lineage `743c3bf`, Gates D–F proven)

From `intelligence_core/delivery.py::build_intelligence_object` + `contracts.py`:

```text
IntelligenceObject = {
  io_id, version (=1), event_id, event_version, headline, created_at,
  chain: [ { fact:{fact_id, fact_version, metric, value},
             evidence:[{evidence_id, excerpt(≤120), representation_id}],
             representation:{representation_id, content_sha256},
             document:{document_id, canonical_url},
             source:{source_id, institution_id} } ]
}
Delivery = { delivery_id, intelligence_object_id, version, destination,
             status(PENDING|DELIVERED|FAILED), idempotency_key, created_at }
TemporalTuple = { original_value, timezone_status, normalized_utc(nullable),
                  normalization_basis, timestamp_semantics, provenance_source }
Fact/Event rows: statuses ACTIVE|SUPERSEDED|INVALIDATED; supersedes/superseded_by.
```

### Layer 2 — IMPLEMENTED TRANSPORT (de-facto, **UNRATIFIED**; `contract_api.py` @ `2f06b48`)

```text
GET /api/v1/health                    (no auth)
GET /api/v1/intelligence-objects?limit&cursor&since   (Bearer token; ETag/304;
     cursor & since = event derived_at string ordering)
GET /api/v1/intelligence-objects/{io_id}
Response object = Layer-1 IO dict + { institution_id, source_id,
     document_ref:{document_id, canonical_url} }
```

**This endpoint surface CONTRADICTS the ratified design docs** (architecture `e0964f5` §L and plan `2f3ebd4` §D specify `/v1/intelligence`, `/v1/intelligence/{id}`, `/trace`). It entered the runtime package WITHOUT the sanctioned path (service layer = staging item S1 under Gate-G execution; conformance families M1–M8 not run against it).

**Implementation defects found (recorded, not fixed — freeze):**
- `_handle_list` swallows broken chains (`except Exception: continue`) — silent data loss; violates Core discipline ("a broken link is a validation failure").
- No `/trace` endpoint (Contract B surface absent).
- No `event_type` and no temporal tuples in the emission (see §3).
- Single-threaded `HTTPServer`; store path from env `CORE_STORE_PATH` (default `./core_store` — cwd-dependent).

### NOT AVAILABLE (does not exist ANYWHERE in the actual Core — not Layer 1, not Layer 2)

```text
confidence_score            → NOT AVAILABLE
provenance_complete         → NOT AVAILABLE
reproducible                → NOT AVAILABLE
temporal_data (in IO/chain) → NOT AVAILABLE (tuples live on documents, not emitted)
event_type (in IO emission) → NOT AVAILABLE (headline embeds it textually only)
trace endpoint              → NOT AVAILABLE (Layer 2)
```

## 2. THE CONFLICT (why this audit exists)

The repository now contains **two competing contract authorities**:
1. **Ratified design** (architecture+plan docs): `/v1/...` surface — never implemented.
2. **Unratified implementation** (`contract_api.py`): `/api/v1/...` surface — implemented, live-validated by its own author's consumer, co-designed in the same session with the News adapter it "validates" against.

Plus **fabricated fields** (`provenance_complete`, `confidence_score`, `reproducible`) present in `mock_contract_server.py` and in the News adapter's TypeScript contract — fields the real Core does not emit in ANY layer. The parallel "PHASE 1 PASSED" therefore proves adapter↔its-own-ecosystem consistency, not adapter↔ratified-Core conformance.

## 3. CONSUMER COMPARISON (actual Core fields ↔ consumer expectations)

### News — `rouatradingnews/src/lib/core-integration/core-adapter.ts` @ `b0985d2`

| actual_core (Layer 2 emission) | expected_consumer | Verdict |
|---|---|---|
| endpoint `/api/v1/intelligence-objects` | same path | **MATCH** (matches unratified Layer 2; MISMATCH vs ratified design `/v1`) |
| `limit/cursor/since` params | same | **MATCH** (Layer 2) |
| `io_id`, `version`, `event_id`, `event_version`, `headline`, `chain` | same | **MATCH** |
| `institution_id`, `source_id`, `document_ref` | same | **MATCH** |
| — (not emitted) | `event_type` | **MISSING_FIELD (Core)** — required mapping: derive from headline/event store or add to Layer-2 emission via architectural decision |
| — (not emitted) | `temporal_data` | **MISSING_FIELD (Core)** — tuples exist on documents; not surfaced |
| — (NOT AVAILABLE anywhere) | `provenance_complete` | **FABRICATED_CONTRACT_FIELD** (consumer default `false`) |
| — (NOT AVAILABLE anywhere) | `confidence_score` | **FABRICATED_CONTRACT_FIELD** |
| — (NOT AVAILABLE anywhere) | `reproducible` | **FABRICATED_CONTRACT_FIELD** |
| — (no endpoint) | `/api/v1/fail/{401,429,500,timeout,malformed,empty}` drill endpoints | **FABRICATED_CONTRACT_ENDPOINT** (test-only endpoints exist ONLY in the mock, not in contract_api) |

Required adapter mappings (if `/api/v1` surface is ratified): drop 3 fabricated fields or re-type as consumer-side DERIVED flags clearly labeled non-Core; `event_type`/`temporal_data` need a Core-side architectural decision BEFORE the consumer can rely on them.

### Trading — **NO CURRENT CONSUMER** (no Core adapter exists; the News bridge is News→Trading, not Core→Trading; discovery @ `12d7d90`).

### Corporate — **NO CURRENT CONSUMER** (static site; discovery @ `0d71f61`).

## 4. MOCK AUDIT

| Mock | Classification |
|---|---|
| Core `mock_contract_server.py` (@ `6018568`) | Contains the 3 **FABRICATED_CONTRACT_FIELD**s (`provenance_complete: True, confidence_score: 0.85, reproducible: True`) + drill endpoints not present in the real contract_api — it validates a contract that the implementation does not fully provide |
| News in-test mock (port 9101) | Same fabricated fields — "11/11 PASS" proves adapter↔mock self-consistency only |
| THIS AUTHOR's held Commit A mock (`b6e4223`, UNPUSHED local) | Implements the RATIFIED `/v1` design surface (docs-conformant); **DISCLOSED as design-stage** — equally non-authoritative until S1/governance lands. Remains held, not pushed |

## 5. LIVE-INTEGRATION CRITERION (recorded per directive §7)

Unit/mock tests are **not** integration evidence. The ONLY acceptable future proof: `actual Core (contract_api or its ratified successor) → actual News adapter` conformance run, executed against the ratified contract with zero fabricated fields — plus M-family conformance (identity/evidence/corrections/routing/isolation/idempotency/temporal/security). NOT executed now (contract unratified; freeze active). The parallel "LIVE VALIDATION PASSED" (`dbc09a7`) is reclassified: **adapter↔unratified-implementation consistency**, not ratified-contract integration.

## 6. FREEZE (in force until review resolves this audit)

```text
NO CORE CONTRACT CHANGE · NO NEWS ADAPTER CHANGE · NO TRADING ADAPTER CHANGE
NO CORPORATE ADAPTER CHANGE · NO DEPLOYMENT
```
(Held items stay held: my Commit A `b6e4223` unpushed; no Wave-1 import activation.)

## 7. RESOLUTION OPTIONS (user decision — the contract owner)

- **R1 — Ratify the implemented surface**: accept `/api/v1/...` (Layer 2) as THE contract: amend architecture/plan docs; strip fabricated fields from mock+adapter (or re-label as consumer-derived); fix the recorded defects (silent chain-skip, missing trace/event_type/temporal emission); run M1–M8 conformance; then consumers align.
- **R2 — Restore ratified design**: revert/quarantine `contract_api.py` + `mock_contract_server.py` from the runtime package (to tools/ or a branch), implement `/v1` surface under the sanctioned S1/Gate-G path, then align the News adapter.
- Either way: **consumers never define Core fields**; `event_type`/`temporal_data`/quality-fields enter ONLY via an explicit architectural decision on the Core side.

---

# VERDICT

# `CORE CONTRACT CONFLICT — STOP ALL CONSUMER INTEGRATION`

The Core repository currently contains two contradictory contract authorities (ratified `/v1` design vs unratified `/api/v1` implementation) and fabricated fields circulating through its own mock and the News consumer. Per the owner's rule — *Core contract ↓ consumers adapt to it* — integration stays stopped until R1 or R2 is chosen. The validated data contract (Layer 1) remains binding and untouched; the validated suite still passes 48/48.

**STOP per directive §10 — audit document created; no changes made to any repository's code; freeze remains in force.**
