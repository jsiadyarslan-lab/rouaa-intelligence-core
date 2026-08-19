# ROUAA News Official Wire Live Validation V1

**Status:** PHASE 1 OFFICIAL WIRE LIVE VALIDATION PASSED WITH BOUNDED SOURCE-COVERAGE LIMITATION
**Date:** 2026-08-17
**Authoritative implementation commits:**
- Core contract API + mock: `6018568`
- Core live-validation fix (auth + store import): `2f06b48`
- News adapter + flags + tests: `b0985d2`
- Documentation (Core): `da0f94c`
- Documentation (News): `26e08ce`
- Live validation evidence (this document, original): `dbc09a7`
- Status correction (this commit): documentation-only
**Cross-product plan:** `5deb05f`

---

## 0. Status Correction (this commit)

The original verdict `PHASE 1 OFFICIAL WIRE LIVE VALIDATION PASSED` was too broad — it did not separate contract validation from multi-source coverage. This correction:

1. Separates **Core Contract Validation** (PASSED) from **Multi-Source Intelligence Coverage** (NOT ESTABLISHED).
2. Classifies FDIC/DFSA as **pattern-specificity limitations**, not Core API or News adapter failures.
3. Corrects the verdict to: **PASSED WITH BOUNDED SOURCE-COVERAGE LIMITATION**.
4. Updates the acceptance matrix to show per-source results.
5. Updates the next gate to explicitly separate the two objectives.

No runtime code modified. No News adapter modified. No source patterns added. No sources imported.

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

| Source | Captured | Documents | Facts | Events | IOs | Classification |
|--------|----------|-----------|-------|--------|-----|----------------|
| FDIC (US) | RSS 926KB, 3 items | 0 (pattern mismatch) | 0 | 0 | 0 | Pattern-specificity limitation |
| ISTAT (Italy) | RSS, 3 items | 3 | 4 | 2 | 2 | Live Core → News contract validated |
| DFSA (UAE) | RSS, 2 items | 2 | 0 (pattern mismatch) | 0 | 0 | Pattern-specificity limitation |
| DGT (France) | HTML, 2 items | 1 | 0 | 0 | 0 | No extraction patterns configured |

**Real IntelligenceObjects: 2 (both ISTAT).**

FDIC and DFSA captured real documents from real official RSS feeds, but their extraction patterns did not match the specific phrasing used in those sources. This is a **pattern-specificity limitation** (Capability 3 — Pattern Specificity in the FROZEN Capability Evidence Registry at `dd66cc1`), NOT a Core API failure, NOT a News adapter failure, NOT a provenance failure, and NOT an architecture failure.

---

## 3. Two Independent Results

### A. Core Contract Live Validation — PASSED

| Evidence | Status |
|----------|--------|
| Real Core JSONL store used (not mock) | ✅ |
| Real ISTAT IntelligenceObjects produced from real RSS feed | ✅ |
| REST authentication (Bearer token) | ✅ |
| ETag / 304 conditional requests | ✅ |
| Pagination / list endpoint | ✅ |
| Single-object retrieval with full chain | ✅ |
| Full traceability (IO → Event → Fact → Evidence → Representation → Document → Source → Institution) | ✅ |
| Idempotent re-poll (same count, no duplicates) | ✅ |
| Core-unavailable handling (URLError, structured error) | ✅ |
| Secret scan CLEAN (both repos) | ✅ |
| Pipeline A unaffected | ✅ |

### B. Multi-Source Intelligence Coverage — NOT ESTABLISHED

| Source | IOs produced | Reason |
|--------|-------------|--------|
| ISTAT | 2 | Patterns matched — IntelligenceObjects produced ✅ |
| FDIC | 0 | Documents captured, patterns did not match source phrasing (pattern-specificity limitation) |
| DFSA | 0 | Documents captured, patterns did not match source phrasing (pattern-specificity limitation) |

> The live contract works against real Core data, but multi-source semantic equivalence across all three selected sources has not yet been demonstrated.

This is a **bounded data/pattern limitation**, not a contract failure.

---

## 4. FDIC / DFSA Classification

```text
FDIC   = pattern-specificity limitation (Capability 3)
DFSA   = pattern-specificity limitation (Capability 3)
ISTAT  = live Core → News contract validated
```

These are NOT classified as:
- Core API failure
- News adapter failure
- Provenance failure
- Architecture failure

The FED_ENF → config-only remediation evidence (`f16bc00`) in the FROZEN Capability Evidence Registry remains the governing precedent. Any FDIC/DFSA pattern remediation must be a separate task.

---

## 5. Real Object IDs Tested

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

---

## 6. HTTP Results

| Check | Status | Result |
|-------|--------|--------|
| GET /api/v1/health | 200 | ok |
| GET /api/v1/intelligence-objects (auth) | 200 | count=2, ETag set |
| GET /api/v1/intelligence-objects/{id} | 200 | full chain resolved |
| GET with If-None-Match | 304 | unchanged |
| GET with bad token | 401 | unauthorized |
| Core unavailable (wrong port) | URLError | connection refused |

---

## 7. ETag / Polling

| Poll | ETag | Result |
|------|------|--------|
| 1 | "c667235b884b5cc8" | 200, count=2 |
| 2 (same ETag) | same | 304 unchanged |
| 3 (no ETag) | same | 200, count=2 |

---

## 8. Traceability

Full lineage verified for both ISTAT IntelligenceObjects:

```
IntelligenceObject (io_id)
  → Event (event_id, event_version)
    → Fact (fact_id, fact_version, metric, value)
      → Evidence (evidence_id, excerpt)
        → Representation (representation_id, content_sha256)
          → Document (document_id, canonical_url)
            → Source (source_id, institution_id)
              → Institution (institution_id)
```

No broken links. All IDs correspond to real Core entities.

---

## 9. Failure Isolation

| Test | Result |
|------|--------|
| Core unavailable | URLError, adapter returns error, News operational |
| HTTP 401 | 401 structured error |
| Core timeout | Verified via mock (30s sleep) |
| Pipeline A regression | Unaffected (no shared code/dependency) |

---

## 10. Idempotency

Re-poll returns same count (2). No duplicate IO production. In-memory seenIOVersions set prevents duplicates. Persistent idempotency required before production cutover.

---

## 11. Versioning

ISTAT v1/v2 correction not in this store run (different press releases captured). Mechanism verified via mock tests. Core governance supports supersession (SUPERSEDED state, supersedes/superseded_by fields).

---

## 12. Dual-Run

Infrastructure implemented. Live equivalence measurement is the next gate.

---

## 13. Security

- Token: environment only, never logged, never committed
- Core API: localhost only
- No secrets in browser/client code
- Secret scan: CLEAN (both repos)

---

## 14. Corrected Acceptance Matrix

| Criterion | Result |
|-----------|--------|
| Real Core contract API | PASS |
| Real IntelligenceObject consumption | PASS |
| Full traceability | PASS |
| Authentication | PASS |
| ETag / polling | PASS |
| Idempotency | PASS |
| Failure isolation | PASS |
| Pipeline A unaffected | PASS |
| FDIC real IO consumed | NOT ESTABLISHED |
| ISTAT real IO consumed | PASS |
| DFSA real IO consumed | NOT ESTABLISHED |
| 1500-source activation | NOT PERFORMED |
| Secrets | CLEAN |
| No production deployment | PASS |

---

## 15. Source-Coverage Limitation (explicit)

> The Phase 1 contract has been validated against real Core data. The selected multi-source coverage criterion remains open because two validated source captures (FDIC, DFSA) did not produce IntelligenceObjects under their current pattern configurations.

This is a **bounded data/pattern limitation**, not a contract failure. The contract API and News adapter are validated; the pattern-specificity gap is tracked in the FROZEN Capability Evidence Registry (Capability 3 — Pattern Specificity).

---

## 16. What Was NOT Done

- Do NOT add FDIC patterns
- Do NOT add DFSA patterns
- Do NOT run remediation
- Do NOT activate more sources
- Do NOT import 1500 sources
- Do NOT cut over News
- Do NOT begin Trading integration
- Do NOT begin Corporate integration
- Do NOT deploy Railway
- Do NOT modify runtime code
- Do NOT modify the News adapter

---

## 17. Final Status

```
PHASE 1 OFFICIAL WIRE LIVE VALIDATION PASSED WITH BOUNDED SOURCE-COVERAGE LIMITATION
```

The Core → News contract integration is validated against real Core data (2 ISTAT IntelligenceObjects with full traceability). The multi-source coverage criterion (FDIC + ISTAT + DFSA) is NOT ESTABLISHED because FDIC and DFSA did not produce IntelligenceObjects under their current pattern configurations — a pattern-specificity limitation, not a contract or adapter failure.

---

## 18. Next Gate

```
OFFICIAL WIRE EQUIVALENCE VALIDATION V1
```

With two separate objectives:

### Objective A — Validate News consuming real Core IntelligenceObjects

Already demonstrated for ISTAT (this document).

### Objective B — Measure semantic equivalence against the legacy official-source path

This requires actual comparable source/event pairs where both Core and the legacy path produce intelligence from the same source. This is a separate measurement exercise, not a contract validation.

---

No cutover occurs automatically. Pipeline A remains independent throughout.
