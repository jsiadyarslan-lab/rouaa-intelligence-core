# ROUAA Core Live Delivery & Restart Validation V35

> **Directive**: EXECUTION DIRECTIVE — CORE LIVE DELIVERY & RESTART VALIDATION V35
> **Date**: 2026-08-19
> **Parent**: V34 (`ed2a98c`)
> **Final verdict**: see §M

---

## A. V34 baseline

V34 closed the persistence contract — 45/45 IOs rebuilt from persisted state after restart. V35 extends this to **live HTTP delivery** through the production transport server.

---

## B. Live server configuration

```
Server:     intelligence_core.production_transport (ThreadingHTTPServer)
Port:       9173
Store:      v3_corpus_store (persisted by V34)
Auth:       Bearer token
Endpoints:  GET /health
            GET /v1/intelligence (list + cursor)
            GET /v1/intelligence/{io_id} (single IO)
```

No mocks. Real HTTP server against real persisted store.

---

## C. First-process results (Process A)

### C.1 HTTP retrieval

```
List endpoint returned:  45 IOs
Queried:                  20 IOs via GET /v1/intelligence/{io_id}
All returned HTTP 200:    20/20 ✓
Complete IO structure:   20/20 (io_id + event_id + chain + version) ✓
```

---

## D. Restart results (Process B)

### D.1 Methodology

1. Process A: query 20 IOs → terminate
2. Process B: fresh server, same persisted store → query same 20 IOs

### D.2 Results

```
Restart retrieval:   20/20 success ✓
Broken:              0
100% retrieval:      ✓
Semantic equivalence: ✓ (same io_id, same event_id, same chain)
```

**100% restart recovery.** All 20 IOs retrieved with same IDs after process restart.

---

## E. HTTP retrieval results

### E.1 Single-IO latency

```
p50:  0.7ms
p95:  0.9ms
p99:  1.0ms
Success rate: 100%
```

### E.2 List endpoint latency

```
p50: 2.6ms
p95: 2.8ms
```

---

## F. Cursor resume results

### F.1 Pagination

```
Total pages:     2 (at limit=25)
Total IOs:       45
Duplicates:      0
Omissions:       0
Cursor stable:   ✓
```

---

## G. Concurrent load

| Readers | Success | Rate | Time |
|--------:|--------:|-----:|-----:|
| 10 | 10/10 | 100% | 0.0s |
| 25 | 25/25 | 100% | 0.0s |
| 50 | 50/50 | 100% | 0.0s |

**100% success at 50 concurrent readers.** No dropped connections.

---

## H. Version lineage

Version lineage tests are covered by Core unit tests (test_production_transport.py — 14 tests). All pass, including:
- v1 SUPERSEDED status preserved
- v2 ACTIVE status preserved
- supersedes_io_id preserved
- Both versions retrievable after restart

---

## I. Provenance walk

```
IOs walked:      10
Chain complete:  10/10
Broken links:    0
```

For each IO, the full chain resolves:
```
IO → Event → Fact → Evidence → Representation/Document → Source
```

**0 broken links.** 100% provenance resolution after restart.

---

## J. Real durable IO examples via HTTP

### J.1 9 complete examples (3+3+3)

| # | Category | IO ID | Chain | Status |
|---|----------|-------|------:|--------|
| 1 | monetary_policy_decision | io-2700fe5da75c2818 | 10 | ACTIVE |
| 2 | monetary_policy_decision | io-f899fb5c1631e12c | 6 | ACTIVE |
| 3 | monetary_policy_decision | io-9e2848265ad5928d | 3 | ACTIVE |
| 4 | statistical_release | io-f92aa209b5d5c885 | 10 | ACTIVE |
| 5 | statistical_release | io-724c8945ab5830f2 | 1 | ACTIVE |
| 6 | statistical_release | io-00c155a6e63a1aa8 | 1 | ACTIVE |
| 7 | regulatory_enforcement | io-f76ffc30691c854c | 2 | ACTIVE |
| 8 | regulatory_enforcement | io-86eb51402109b465 | 6 | ACTIVE |
| 9 | regulatory_enforcement | io-e7f1ab14fa41db16 | 1 | ACTIVE |

**9/9 target achieved.** All retrieved via live HTTP after restart, all with complete provenance chains.

---

## K. Performance

| Endpoint | p50 | p95 | p99 |
|----------|---:|---:|---:|
| Single IO (`GET /v1/intelligence/{io_id}`) | 0.7ms | 0.9ms | 1.0ms |
| List (`GET /v1/intelligence?limit=25`) | 2.6ms | 2.8ms | — |

Sub-millisecond single-IO retrieval. Sub-3ms list retrieval.

---

## L. Regression

| Suite | Count | Result |
|-------|------:|--------|
| Core unit tests | 83 | ✓ 83/83 PASS |
| V24R CSS exclusion | 8 | ✓ 8/8 PASS |
| V19 normalization | 11+6 | ✓ 17/17 PASS |
| V29 monetary event | 12 | ✓ 12/12 PASS |
| **Total** | **120** | **✓ ALL PASS** |

No code changes — no regression.

---

## M. Final verdict

### `CORE LIVE DELIVERY VALIDATION PASSED`

The V35 Live Delivery & Restart Validation is **PASSED**:

1. **Live server started** ✅ — real HTTP server against persisted store
2. **20/20 IOs retrieved via HTTP** ✅ — all HTTP 200, complete structure
3. **100% restart recovery** ✅ — 20/20 after process restart, 0 broken
4. **Cursor stable** ✅ — 45 IOs, 0 duplicates, 0 omissions
5. **Sub-millisecond latency** ✅ — p50=0.7ms, p95=0.9ms, p99=1.0ms
6. **100% concurrent success** ✅ — 50/50 readers at 100%
7. **10/10 provenance walk** ✅ — 0 broken links
8. **9 real durable examples** ✅ — 3 monetary + 3 statistical + 3 regulatory
9. **120 regression tests pass** ✅

### What this proves

Core now delivers **durable, reconstructable IntelligenceObjects through live HTTP** after process restart:

```
Persisted intelligence
        ↓
Process restart
        ↓
Live HTTP service
        ↓
GET /v1/intelligence
        ↓
same IO (same io_id, same event_id, same chain, same provenance)
```

This is the **standalone intelligence engine** — not just a test pipeline.

---

## N. STOP

Per directive §16:

- ❌ No extraction improvements
- ❌ No new patterns
- ❌ No source expansion
- ❌ No Entity-Aware Recovery
- ❌ No product integration
- ❌ No Railway deployment

**V35 has validated the full durable delivery path.** Core is now a standalone intelligence engine that:
- Extracts real intelligence from official sources ✅
- Persists it durably ✅
- Survives process restart ✅
- Delivers via live HTTP ✅
- Supports cursor pagination ✅
- Handles concurrent readers ✅
- Maintains provenance chains ✅

---

## O. Artifacts

- `intelligence_core/tests/reliability/v35_live_delivery.py` — validation script
- `intelligence_core/tests/reliability/v35_live_delivery_results.json` — results
- `docs/evidence/ROUAA_CORE_LIVE_DELIVERY_RESTART_VALIDATION_V35.md` — this document
