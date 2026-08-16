# ROUAA News Official Wire Phase 1 Report V1

**Status:** PHASE 1 REPORT — implementation summary
**Date:** 2026-08-17
**Repository:** rouaa-intelligence-core
**Cross-product plan:** `rouaa-corporate/docs/architecture/ROUAA_CROSS_PRODUCT_INTEGRATION_IMPLEMENTATION_PLAN_V1.md` (`5deb05f`)

---

## 1. Files Changed (Core-side)

| File | Type | Description |
|------|------|-------------|
| `intelligence_core/contract_api.py` | NEW | Read-only REST contract API server exposing IntelligenceObjects via polling |
| `intelligence_core/mock_contract_server.py` | NEW | Local dev fixture with hardcoded mock data (FDIC, ISTAT v1+v2, DFSA) + failure simulation endpoints |

**No existing Core modules modified.** No Core runtime code changed. No Core tests changed.

---

## 2. Contract API

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/health` | GET | None | Health check |
| `/api/v1/intelligence-objects` | GET | Bearer | List IntelligenceObjects with cursor pagination |
| `/api/v1/intelligence-objects/<io_id>` | GET | Bearer | Single IntelligenceObject with full traceability chain |

### Transport features

- Bearer token auth (`CORE_API_TOKEN`, environment-provided, server-side only)
- Cursor-based pagination (`?cursor=&limit=&since=`)
- ETag / conditional requests (`If-None-Match` → 304)
- Structured errors (`{ error: { code, message } }`)
- Token never logged (handler suppresses default logging)

### Contract fields per IntelligenceObject

```
io_id (core_intelligence_object_id)
version
institution_id
source_id
event_type
facts (via chain)
evidence_refs (via chain)
document_ref (document_id + canonical_url)
temporal_data (via chain timestamps)
quality_metadata (provenance_complete, confidence_score, reproducible)
```

### Traceability chain

```
IntelligenceObject → Event → Fact → Evidence → Representation → Document → Source → Institution
```

The API does NOT expose:
- Core database internals
- Core filesystem paths (beyond JSONL store path)
- Core internal module structure

---

## 3. Mock Contract Server

Local dev fixture with hardcoded IntelligenceObject data:

| Source | IO ID | Event Type | Version | Notes |
|--------|-------|------------|---------|-------|
| FDIC | `io_fdic_2026_001` | regulatory_enforcement | 1 | penalty_amount=$1.5M |
| ISTAT | `io_istat_2026_001` | statistical_release | 1 | inflation_rate=0.3% |
| ISTAT | `io_istat_2026_002` | statistical_release | 2 | CORRECTED: inflation_rate=0.4% (supersedes v1) |
| DFSA | `io_dfsa_2026_001` | regulatory_enforcement | 1 | penalty_amount=AED 2.5M |

Failure simulation endpoints:
- `/api/v1/fail/401` — unauthorized
- `/api/v1/fail/429` — rate limited
- `/api/v1/fail/500` — internal error
- `/api/v1/fail/timeout` — 30s sleep (simulates timeout)
- `/api/v1/fail/malformed` — broken JSON
- `/api/v1/fail/empty` — empty result

---

## 4. News Adapter (cross-repo)

The News adapter is in `rouatradingnews` repository:
- `src/lib/core-integration/core-adapter.ts` — adapter implementation
- `src/lib/core-integration/__tests__/core-adapter.test.ts` — tests

See: `rouatradingnews/docs/integration/OFFICIAL_INTELLIGENCE_WIRE_PHASE1.md`

---

## 5. Acceptance Criteria

| # | Criterion | Core-side | News-side |
|---|-----------|-----------|-----------|
| 1 | Core IntelligenceObjects consumed by News | ✅ API exposes them | ✅ Adapter polls them |
| 2 | Pipeline B separate from Pipeline A | ✅ Contract API is separate | ✅ Adapter is separate module |
| 3 | Global News pipeline remains operational | ✅ Core does not affect News | ✅ Pipeline A untouched |
| 4 | Core failure does not break News | ✅ API returns structured errors | ✅ Adapter handles errors gracefully |
| 5 | Full traceability works | ✅ Chain embedded in IO | ✅ Resolver resolves full lineage |
| 6 | Versioning works | ✅ Mock includes v1→v2 | ✅ Tests verify v1→v2 |
| 7 | Idempotency works | ✅ io_id:vN is unique | ✅ Seen-set prevents duplicates |
| 8 | Dual-run comparison works | ✅ | ✅ Semantic match/partial/core-only |
| 9 | No source registry removed | ✅ | ✅ |
| 10 | No 1500-source bulk activation | ✅ | ✅ |
| 11 | No secret committed | ✅ Secret scan: CLEAN | ✅ Secret scan: CLEAN |

---

## 6. Live Validation

**Status:** PENDING — mock server tests pass. Live validation against actual Core with real store data requires:
1. Railway deployment of Core, OR
2. Local Core with real JSONL store data (FDIC, ISTAT, DFSA)

**Planned live validation:** Controlled test using ONLY FDIC, ISTAT, DFSA sources.

---

## 7. Limitations

1. Mock server uses hardcoded data — live Core store integration not tested yet
2. No Railway deployment
3. No 1500 source import
4. Core contract API uses Python stdlib HTTP server (suitable for Phase 1; production would use proper ASGI)

---

## 8. Security

- ✅ Token is environment-provided (`CORE_API_TOKEN`), never hardcoded
- ✅ Token never logged (handler suppresses logging)
- ✅ No secrets committed (secret scan: CLEAN)
- ✅ No Core internal URLs exposed to browser code
- ✅ Server-side only (adapter runs on server, not client)
