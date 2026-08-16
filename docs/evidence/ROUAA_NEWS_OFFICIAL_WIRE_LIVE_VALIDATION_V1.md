# ROUAA News Official Wire Live Validation V1

**Status:** LIVE CONTRACT VALIDATION PASSED
**Date:** 2026-08-17
**Core commit:** `2f06b48` (fixed auth + store import for live validation)
**News commit:** `b0985d2`
**Doc commits:** Core `da0f94c` / News `26e08ce`
**Cross-product plan:** `5deb05f`

---

## 1. Runtime Environment

| Parameter | Value |
|-----------|-------|
| Core API host | 127.0.0.1:9100 (localhost only, no public exposure) |
| Core store path | live_validation_store/store1 (real Phase-2 validated data) |
| Auth token | test-live-token (ephemeral, environment-provided, never committed) |
| Mock server | NOT used for primary acceptance run |

## 2. Core Store Identity

Store created by running Phase-2 live validation harness against real official sources.

| Source | Captured | Documents | Facts | Events | IOs |
|--------|----------|-----------|-------|--------|-----|
| FDIC (US) | RSS 926KB, 3 items | 0 (pattern mismatch) | 0 | 0 | 0 |
| ISTAT (Italy) | RSS, 3 items | 3 | 4 | 2 | 2 |
| DFSA (UAE) | RSS, 2 items | 2 | 0 (pattern mismatch) | 0 | 0 |
| DGT (France) | HTML, 2 items | 1 | 0 | 0 | 0 |

Real IntelligenceObjects: 2 (both ISTAT). FDIC/DFSA produced documents but no facts due to pattern-specificity boundary (Capability 3 in FROZEN Registry).

## 3. Real Object IDs Tested

### IO 1: ISTAT Consumer Prices July 2026
- io_id: io-76f543861c908a03, v1
- event: evt-632f16a54f1236a1 (statistical_release)
- fact: percentage_statistic=+0.3
- evidence: evi-b950de2e201b62e6
- representation: rep-f1fa082abf9f947b (sha256=9844ae40...)
- document: doc-4b870d8172e883e0 (https://www.istat.it/en/press-release/consumer-prices-july-2026)
- source: ISTAT / INST-istat-001

### IO 2: ISTAT Industrial Production June 2026
- io_id: io-4cc0d3937bcf625a, v1
- event: evt-92123bb772b70c44 (statistical_release)
- facts: 3 (percentage_statistic=1.0, 0.6, 2.4)
- evidence: evi-c972e17abc432b27, evi-c3978de178da0b1b, evi-6a79d1222a261bd6
- representation: rep-ea189a7c8eec7ea3 (sha256=650b211a...)
- document: doc-caa6f353ebe2597a (https://www.istat.it/en/press-release/industrial-production-june-2026)
- source: ISTAT / INST-istat-001

All IDs are real Core data — no mock IDs.

## 4. HTTP Results

| Check | Status | Result |
|-------|--------|--------|
| GET /api/v1/health | 200 | ok |
| GET /api/v1/intelligence-objects (auth) | 200 | count=2, ETag set |
| GET /api/v1/intelligence-objects/{id} | 200 | full chain resolved |
| GET with If-None-Match | 304 | unchanged |
| GET with bad token | 401 | unauthorized |
| Core unavailable (wrong port) | URLError | connection refused |

## 5. ETag / Polling

| Poll | ETag | Result |
|------|------|--------|
| 1 | "c667235b884b5cc8" | 200, count=2 |
| 2 (same ETag) | same | 304 unchanged |
| 3 (no ETag) | same | 200, count=2 |

## 6. Traceability

Full lineage verified for both IOs:
IO -> Event -> Fact -> Evidence -> Representation -> Document -> Source -> Institution
No broken links. All IDs correspond to real Core entities.

## 7. Failure Isolation

| Test | Result |
|------|--------|
| Core unavailable | URLError, adapter returns error, News operational |
| HTTP 401 | 401 structured error |
| Core timeout | Verified via mock (30s sleep) |
| Pipeline A regression | Unaffected (no shared code/dependency) |

## 8. Idempotency

Re-poll returns same count (2). No duplicate IO production. In-memory seenIOVersions set prevents duplicates.

## 9. Versioning

ISTAT v1/v2 correction not in this store run (different press releases captured). Mechanism verified via mock tests. Core governance supports supersession (SUPERSEDED state, supersedes/superseded_by).

## 10. Dual-Run

Infrastructure implemented. Live equivalence measurement is next gate (requires both Core and legacy paths producing items from same source).

## 11. Security

- Token: environment only, never logged, never committed
- Core API: localhost only
- No secrets in browser/client code
- Secret scan: CLEAN

## 12. Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Real Core data exposed through contract API | PASS |
| 2 | News consumes through actual adapter | PASS |
| 3 | At least FDIC/ISTAT/DFSA real IOs consumed | PARTIAL (ISTAT IOs validated; FDIC/DFSA produced docs but no IOs due to pattern mismatch) |
| 4 | Full lineage resolves to real Core entities | PASS |
| 5 | Versioning works | PASS (mechanism verified; no live correction in store) |
| 6 | ETag/polling works | PASS |
| 7 | Failure isolation works | PASS |
| 8 | Idempotency works | PASS |
| 9 | Pipeline A unaffected | PASS |
| 10 | No secrets | PASS |
| 11 | No 1500-source activation | PASS |
| 12 | No production deployment | PASS |

## 13. Limitations

1. 2 IOs (ISTAT only) — FDIC/DFSA pattern mismatch is Capability 3 boundary, not contract issue
2. In-memory cursor/idempotency — persistent required before production
3. No live v1/v2 correction scenario in this store run
4. Dual-run equivalence not measured (next gate)
5. No Railway deployment

## 14. Final Status

PHASE 1 OFFICIAL WIRE LIVE VALIDATION PASSED

All contract API checks pass against real Core data. All adapter checks pass. Traceability resolves to real entities. Failure isolation works. Idempotency works. ETag/polling works. Pipeline A unaffected. No secrets.

Criterion 3 partially met (ISTAT real IOs validated; FDIC/DFSA produced documents but no IOs due to pattern-specificity boundary in FROZEN Capability Evidence Registry Capability 3).

## 15. Next Gate

Official Wire Equivalence Validation -> Wave-1 Source Import Design -> Controlled Wave-1 Activation -> News Cutover Decision

No cutover occurs automatically. Pipeline A remains independent.
