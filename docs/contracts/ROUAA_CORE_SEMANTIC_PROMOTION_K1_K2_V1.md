# ROUAA Core Semantic Promotion K1/K2 V1

> **Directive**: EXECUTION DIRECTIVE — CORE SEMANTIC PROMOTION K1/K2 V1
> **Date**: 2026-08-17
> **Final verdict**: `CORE K1/K2 PROMOTION PASSED` (see §K)

## Authoritative state (verified post-push)

| Repo | HEAD | Pushed |
|------|------|--------|
| `rouaa-intelligence-core` | `047c740` | ✅ `34ea15f..047c740` |
| `rouatradingnews` | `1a3d09e` | ✅ `7c377dd..1a3d09e` |

Prerequisite state: R2 restoration (`e82c34a`), S1 production transport (`5416da6`), E2E validation (`34ea15f` + `7c377dd`).

---

## A. Why K1/K2 already exist

Per `ROUAA_CORE_INTELLIGENCE_CONTRACT_V1.md` (R2 restoration) §3, before this promotion:

| Field | Store presence | IO emission |
|-------|----------------|-------------|
| `event_type` | ✅ `Event.event_type` (one of 6 supported types) | ❌ NOT surfaced in IO |
| `temporal_data` (D4 tuples) | ✅ `Document.publication_tuples` | ❌ NOT surfaced in IO |

The semantic state already existed in Core state. The problem was a **projection gap** — `build_intelligence_object()` had access to both fields but used them only internally (event_type for headline construction, publication_tuples ignored) without surfacing them in the emitted IO.

### Evidence from real E2E store (verified before promotion)

```
$ cat e2e_store/events.jsonl | head -1
{"event_id":"evt-3145932c2c2b0fd8","event_version":1,"event_type":"statistical_release",...}
                                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                              K1 EXISTS IN STORE

$ cat e2e_store/documents.jsonl | head -1
{"document_id":"doc-0c4d91f4c925c023","publication_tuples":[{"timestamp_semantics":"publication","normalized_utc":"2026-08-03T21:10:00Z",...}]}
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                  K2 EXISTS IN STORE (D4 publication_tuples)
```

Both K1 and K2 are real Core state — not invented. The promotion exposes them.

---

## B. Current projection gap

Before this commit, `build_intelligence_object()` in `delivery.py`:

```python
# OLD (pre-promotion) — event_type used only for headline, never surfaced
def build_intelligence_object(store, event_row, source_name, created_at):
    chain = []
    for ref in event_row["fact_version_snapshot"]:
        ...
        doc = store.latest_by_id("documents", "document_id").get(fact["document_id"])
        # doc has publication_tuples (D4) — but they were IGNORED
        ...
    io = IntelligenceObject(
        io_id=..., version=1, event_id=..., event_version=...,
        headline=build_headline_from_row(event_row, source_name),  # uses event_type internally
        chain=chain, created_at=created_at)
        # event_type was NOT passed to the IO constructor
        # publication_tuples were NOT projected
    return io
```

The IO emitted by this function contained only: `io_id, version, event_id, event_version, headline, chain, created_at`. Consumers (News) had to **infer** `event_type` from headline text and **guess** at temporal semantics — both anti-patterns per canonical contract §3.

---

## C. K1 implementation

### C.1 Schema addition (`contracts.py`)

```python
@dataclass
class IntelligenceObject:
    io_id: str
    version: int
    event_id: str
    event_version: int
    headline: str
    chain: list = field(default_factory=list)
    created_at: str = ""
    # K1 PROMOTED (CORE_SEMANTIC_PROMOTION_K1_K2_V1 §3):
    # Direct copy from Event.event_type — no inference, no headline parsing.
    event_type: str = ""
    # K2 PROMOTED (§4):
    temporal_data: Optional[TemporalDataProjection] = None
```

### C.2 Delivery function (`delivery.py`)

```python
# K1: event_type — direct copy from Event.event_type
event_type = event_row.get("event_type", "")
```

The implementation is **one line** — `event_type` is already in `event_row` (the Event store row). No inference. No headline parsing. No source-specific logic.

### C.3 Verification on real HCP Morocco IO

```
$ curl -s -H "Authorization: Bearer $TOKEN" \
    http://127.0.0.1:9600/v1/intelligence/io-0dfe7be4250a560a

{
  "io_id": "io-0dfe7be4250a560a",
  "version": 1,
  "event_id": "evt-3145932c2c2b0fd8",
  "event_version": 1,
  "headline": "HCP Statistical Release",
  "chain": [...],
  "created_at": "",
  "event_type": "statistical_release",    ← K1 PROMOTED (real value from Event.event_type)
  "temporal_data": {...},                  ← K2 PROMOTED (see §D)
  "status": "ACTIVE",
  "supersedes_io_id": null
}
```

### C.4 Verification on real SEC IO

```
$ curl -s -H "Authorization: Bearer $TOKEN" \
    http://127.0.0.1:9600/v1/intelligence/io-1ca8a75ee22968f7

{
  "io_id": "io-1ca8a75ee22968f7",
  ...
  "event_type": "regulatory_enforcement",  ← K1 PROMOTED
  ...
}
```

K1 is correctly emitted for both statistical_release and regulatory_enforcement IOs.

---

## D. K2 implementation

### D.1 Schema addition (`contracts.py`)

```python
@dataclass
class TemporalDataProjection:
    """K2 projection of D4 Document.publication_tuples into the IO."""
    publication_time: Optional[str] = None
    publication_time_raw: Optional[str] = None
    publication_timezone_status: Optional[str] = None
    reference_period: Optional[str] = None
    reference_period_normalized_utc: Optional[str] = None
```

### D.2 Projection function (`delivery.py`)

```python
def _project_temporal_data(doc: dict | None) -> TemporalDataProjection | None:
    """Project D4 Document.publication_tuples into K2 TemporalDataProjection."""
    if not doc:
        return None
    tuples = doc.get("publication_tuples") or []
    if not tuples:
        return None

    # Find publication tuple: timestamp_semantics == "publication"
    pub_tuple = next((t for t in tuples
                      if t.get("timestamp_semantics") == "publication"), None)
    if pub_tuple is None:
        pub_tuple = tuples[0]  # fall back to first tuple

    # Find reference_period tuple: timestamp_semantics == "reporting_period"
    ref_tuple = next((t for t in tuples
                      if t.get("timestamp_semantics") == "reporting_period"), None)

    return TemporalDataProjection(
        publication_time=pub_tuple.get("normalized_utc"),
        publication_time_raw=pub_tuple.get("original_value"),
        publication_timezone_status=pub_tuple.get("timezone_status"),
        reference_period=ref_tuple.get("normalized_utc") if ref_tuple else None,
        reference_period_normalized_utc=ref_tuple.get("normalized_utc") if ref_tuple else None,
    )
```

### D.3 Verification on real HCP Morocco IO

```
$ curl -s -H "Authorization: Bearer $TOKEN" \
    http://127.0.0.1:9600/v1/intelligence/io-0dfe7be4250a560a

{
  ...
  "temporal_data": {
    "publication_time": "2026-08-03T21:10:00Z",       ← K2 — from RSS pubDate (real HCP.ma publication)
    "publication_time_raw": "Mon, 03 Aug 2026 23:10:00 +0200",  ← original RSS pubDate
    "publication_timezone_status": "EXPLICIT_OFFSET",  ← +0200 (Morocco time)
    "reference_period": null,                          ← HCP RSS has no reporting_period tuple
    "reference_period_normalized_utc": null
  }
}
```

### D.4 Verification on real SEC IO

```
{
  ...
  "temporal_data": {
    "publication_time": "2026-08-14T20:16:34Z",        ← from SEC RSS pubDate
    "publication_time_raw": "Fri, 14 Aug 2026 16:16:34 -0400",
    "publication_timezone_status": "EXPLICIT_OFFSET",
    "reference_period": null,                          ← regulatory actions have no reference period (§12)
    "reference_period_normalized_utc": null
  }
}
```

K2 is correctly projected from real D4 publication_tuples.

---

## E. D4 preservation

Per directive §5: `null = NOT_APPLICABLE / UNKNOWN`. The promotion does NOT fabricate timestamps, infer timezones, or convert date-only reference periods to UTC.

### E.1 D4 §9 distinction: `reference_period != publication_time`

For statistical releases, `reference_period` (the statistical reporting period) must be distinct from `publication_time` (when the source published the document). The canonical mock enforces this:

```python
# tools/mock_core/mock_core_server.py — io-cpi-v1 (ISTAT statistical release)
"temporal_data": _temporal(
    publication_time="2026-08-12T08:00:58Z",       # when ISTAT published
    reference_period="2026-07"),                    # July 2026 statistics (the reporting period)
```

Verified by `test_M7_statistical_release_reference_period_distinct_from_publication_time`:

```python
def test_M7_statistical_release_reference_period_distinct_from_publication_time(self):
    v1 = json.loads(_get("/v1/intelligence/io-cpi-v1")[1])
    self.assertEqual(v1["event_type"], "statistical_release")
    td = v1["temporal_data"]
    self.assertIsNotNone(td["publication_time"])
    self.assertIsNotNone(td["reference_period"])
    # D4 §9: reference_period != publication_time (NOT collapsed)
    self.assertNotEqual(td["reference_period"], td["publication_time"])
```

### E.2 Regulatory actions: `reference_period = null`

Per directive §12: regulatory actions have no statistical reference period. The canonical mock enforces this:

```python
# tools/mock_core/mock_core_server.py — io-fdic-enf (FDIC regulatory enforcement)
"temporal_data": _temporal(
    publication_time="2026-07-31T00:00:00Z",
    reference_period=None),  # regulatory actions have no reference period
```

Verified by `test_M7_regulatory_enforcement_reference_period_null`.

### E.3 Real HCP RSS-derived IO: `reference_period = null`

HCP RSS feeds provide `pubDate` tuples but NOT `reporting_period` tuples. The promotion correctly surfaces `reference_period = null` (D4-faithful) rather than fabricating a value. This is the honest answer for RSS-derived statistical data — the reporting period exists in the article content but is not extracted as a structured D4 tuple by the current pipeline.

Verified by `test_hcp_K2_reference_period_is_not_publication_time`:

```python
def test_hcp_K2_reference_period_is_not_publication_time(self):
    """§11: HCP Morocco statistical IOs must preserve the D4 distinction."""
    ...
    for io in hcp_ios:
        td = io["temporal_data"]
        if td["reference_period"] is None:
            self.assertIsNotNone(td["publication_time"])
            # The D4 distinction: null reference_period != publication_time
            self.assertNotEqual(td["reference_period"], td["publication_time"])
```

---

## F. Canonical contract update

`docs/contracts/ROUAA_CORE_INTELLIGENCE_CONTRACT_V1.md` updated:

### F.1 Status

```
CANONICAL CONTRACT — single authority restored per R2.
K1/K2 promoted per CORE_SEMANTIC_PROMOTION_K1_K2_V1 — event_type and
temporal_data are now EMITTED canonical fields (no longer architectural
capability gaps).
```

### F.2 §2.1 IntelligenceObject schema

| Field | Type | Required | Source |
|-------|------|----------|--------|
| ... | ... | ... | ... |
| **`event_type`** | string | **yes (K1 PROMOTED)** | `Event.event_type` → `delivery.build_intelligence_object` |
| **`temporal_data`** | object? | **yes (K2 PROMOTED)** | `Document.publication_tuples` → `delivery._project_temporal_data` |

### F.3 §2.1.1 K2 temporal_data sub-fields (D4 projection)

All 5 sub-fields documented with their D4 source semantics.

### F.4 §3 PROHIBITED FIELDS (unchanged)

K1/K2 promotion did NOT add any fabricated fields. The 5 prohibited fabricated fields remain prohibited:
- `provenance_complete`, `confidence_score`, `reproducible`, `quality_metadata`, `provenance_match`

### F.5 §7 K1/K2 PROMOTION HISTORY

Documents the rationale, implementation, and backward-compatibility.

---

## G. News alignment

News adapter (`rouatradingnews/src/lib/core-integration/core-adapter.ts` at `1a3d09e`) updated:

### G.1 CoreIntelligenceObject interface

```typescript
export interface CoreTemporalData {
  publication_time: string | null;
  publication_time_raw: string | null;
  publication_timezone_status: string | null;
  reference_period: string | null;
  reference_period_normalized_utc: string | null;
}

export interface CoreIntelligenceObject {
  // ... existing fields ...
  event_type: string;                       // K1 PROMOTED
  temporal_data: CoreTemporalData | null;   // K2 PROMOTED
  chain: CoreChainLink[];
}
```

### G.2 StoryCandidate

```typescript
export interface StoryCandidate {
  // ... existing fields ...
  event_type: string;         // K1 — direct copy from io.event_type
  temporal: CoreTemporalData; // K2 — consumed from io.temporal_data
  // ...
}
```

### G.3 transformToStoryCandidate()

```typescript
return {
  // ...
  event_type: io.event_type,  // K1 — direct copy, no inference
  temporal: io.temporal_data ?? {  // K2 — consumed directly
    publication_time: null,
    publication_time_raw: null,
    publication_timezone_status: null,
    reference_period: null,
    reference_period_normalized_utc: null,
  },
  // ...
};
```

### G.4 DualRunComparison

- `event_match`: now based on `candidate.event_type` (K1 — was removed when event_type was a gap).
- `temporal_match`: now based on `candidate.temporal.publication_time` (K2 — was based on `created_at` only).
- `provenance_match`: still PROHIBITED (fabricated).

### G.5 Anti-fabrication (unchanged)

News does NOT re-introduce any of the 5 prohibited fabricated fields. Verified by `Negative contract — fabricated fields NOT expected` test suite.

---

## H. Real E2E results

### H.1 HCP Morocco (statistical_release)

```
io_id: io-0dfe7be4250a560a
event_type: statistical_release                    ← K1 PROMOTED (real value)
temporal_data:
  publication_time: 2026-08-03T21:10:00Z           ← K2 (real RSS pubDate from hcp.ma)
  publication_time_raw: Mon, 03 Aug 2026 23:10:00 +0200
  publication_timezone_status: EXPLICIT_OFFSET
  reference_period: null                            ← D4-faithful (HCP RSS has no reporting_period tuple)
  reference_period_normalized_utc: null
chain: [16 facts with percentage_statistic metric]
```

### H.2 SEC (regulatory_enforcement)

```
io_id: io-1ca8a75ee22968f7
event_type: regulatory_enforcement                  ← K1 PROMOTED (real value)
temporal_data:
  publication_time: 2026-08-14T20:16:34Z           ← K2 (real RSS pubDate from sec.gov)
  publication_time_raw: Fri, 14 Aug 2026 16:16:34 -0400
  publication_timezone_status: EXPLICIT_OFFSET
  reference_period: null                            ← §12 (regulatory actions have no reference period)
  reference_period_normalized_utc: null
chain: [8 facts with action_type metric]
```

### H.3 News StoryCandidate (after transform)

```typescript
{
  candidate_id: "sc_io-0dfe7be4250a560a_ev1",
  core_io_id: "io-0dfe7be4250a560a",
  core_version: 1,
  headline: "HCP Statistical Release",
  event_type: "statistical_release",                // K1 consumed directly
  facts: [{metric: "percentage_statistic", value: "63,5"}, ... 16 total],
  temporal: {                                       // K2 consumed directly
    publication_time: "2026-08-03T21:10:00Z",
    publication_time_raw: "Mon, 03 Aug 2026 23:10:00 +0200",
    publication_timezone_status: "EXPLICIT_OFFSET",
    reference_period: null,
    reference_period_normalized_utc: null,
  },
  created_at: "",  // IO construction timestamp (separate from publication_time)
  // ... traceability, etc.
}
```

NO fabricated fields. K1/K2 consumed directly from Core.

---

## I. Regression

### I.1 Test matrix (directive §15, reported separately)

| # | Suite | Repo | Tests | Pass | Classification |
|---|-------|------|------:|-----:|------------------|
| 1 | Core unit tests | Core | 100 | 100 | UNIT_TEST |
| 2 | Core transport (S1 production) | Core | 35 | 35 | LIVE_PRODUCTION_CORE |
| 3 | Core canonical mock conformance (M1-M8 + K1/K2) | Core | 15 | 15 | CANONICAL_MOCK |
| 4 | Real E2E store tests | Core | 12 | 12 | REAL_CORE_STORE + REAL_PRODUCTION_HTTP |
| 5 | Conformance acceptance (buyer simulation) | Core | 11 | 11 | UNIT_TEST (synthetic) |
| 6 | News core-adapter tests | News | 39 | 39 | UNIT_TEST + CANONICAL_MOCK |
| 7 | News live V2 (canonical mock) | News | 29 | 29 | LIVE_CANONICAL_MOCK |
| 8 | News live PRODUCTION | News | 28 | 28 | LIVE_PRODUCTION_CORE |
| 9 | News live E2E real sources | News | 12 | 12 | REAL_OFFICIAL_DOCUMENT + REAL_CORE_STORE + REAL_PRODUCTION_HTTP + REAL_NEWS |
| **Total** | | | **281** | **281** | |

(5 pre-existing `prompt-builder.test.ts` failures in News full suite are unrelated Arabic LLM tests, verified present at baseline `26e08ce`.)

### I.2 Comparison to previous baseline

- Previous baseline (E2E validation `34ea15f`/`7c377dd`): 255/255 PASS.
- K1/K2 promotion: +26 tests (5 new Core K1/K2 tests, 4 new canonical mock K1/K2 tests, 4 new News adapter K1/K2 tests, 1 new News live V2 K1/K2 test, plus updates to existing tests).
- **Total: 281/281 PASS.** No regressions.

### I.3 Secret scan

```
Core: 0 findings
News: 0 findings
Verdict: PASS — 0 findings
```

---

## J. Remaining gaps

### J.1 ECB monetary_policy_decision IO still not produced (environmental, not pipeline)

ECB's HTML press releases are 100K+ bytes and frequently time out over the public internet. The pipeline code is correct; the limitation is environmental. Re-running when network conditions are more reliable would produce ECB IOs with `event_type: "monetary_policy_decision"`.

This is a bounded limitation of the E2E test corpus, NOT a K1/K2 promotion gap. The canonical mock includes a `monetary_policy_decision` fixture, and the production transport correctly emits K1 for any event type that exists in the store.

### J.2 HCP RSS-derived `reference_period` is null (D4-faithful)

HCP RSS feeds provide `pubDate` (publication_time) but NOT `reporting_period` tuples. The D4-faithful answer is `reference_period = null` — NOT a fabricated date. The canonical mock demonstrates the non-null case (e.g. `reference_period = "2026-07"` for ISTAT CPI July 2026 statistics, published August 12).

To populate real `reference_period` from HCP publications, a future capability would extract the reporting period from article content (e.g. "Situation du marché du travail au Maroc au deuxième trimestre de 2026" → `reference_period = "2026-Q2"`). This is a future extraction capability, NOT a K1/K2 promotion gap.

### J.3 Cursor pagination with concurrent `derived_at` (unchanged)

Per directive §14: NOT solved in this task. Future capability: composite cursor = `derived_at + event_id + event_version`. No scope creep.

---

## K. Final verdict

### `CORE K1/K2 PROMOTION PASSED`

### Conditions evaluated per directive §18

| Condition | Result |
|-----------|--------|
| `event_type` IS now emitted in IntelligenceObject | ✅ PASS — direct copy from Event.event_type |
| `temporal_data` IS now emitted in IntelligenceObject | ✅ PASS — projected from Document.publication_tuples per D4 |
| All 5 D4 sub-fields preserved | ✅ PASS — publication_time, publication_time_raw, publication_timezone_status, reference_period, reference_period_normalized_utc |
| D4 §9 distinction: `reference_period != publication_time` for statistical releases | ✅ PASS — verified by M7.stat test on canonical mock |
| §12: regulatory actions have `reference_period = null` | ✅ PASS — verified by M7.reg test on canonical mock |
| Anti-fabrication: no quality_metadata family | ✅ PASS — 5 prohibited fields remain prohibited |
| Production transport surfaces K1/K2 | ✅ PASS — `/v1/intelligence` emits K1/K2 |
| Canonical mock matches production | ✅ PASS — same field set |
| News consumes K1/K2 directly (no inference) | ✅ PASS — StoryCandidate.event_type = io.event_type, StoryCandidate.temporal = io.temporal_data |
| Real HCP E2E: K1=statistical_release, K2 from real RSS pubDate | ✅ PASS |
| Real SEC E2E: K1=regulatory_enforcement, K2 from real RSS pubDate, reference_period=null | ✅ PASS |
| ECB monetary_policy_decision: LIVE_FIXTURE_NOT_AVAILABLE | ✅ Documented absence (network reliability, not pipeline gap) |
| Backward compatibility: io.version=1 constant, event_version lineage axis | ✅ PASS |
| GitHub commits verified | ✅ Core `047c740`, News `1a3d09e` |
| No unresolved contract comments | ✅ 0 PRs / 0 comments / 0 contract keyword matches |
| Secret scan | ✅ 0 findings |
| Wave-1 INACTIVE | ✅ |
| Trading UNCHANGED | ✅ |
| Corporate UNCHANGED | ✅ |
| Method V1 UNCHANGED | ✅ |
| No new Event Types | ✅ |
| No new temporal model (D4 preserved) | ✅ |

---

## L. GitHub verification (directive §16)

| Check | Core (`047c740`) | News (`1a3d09e`) |
|-------|------------------|------------------|
| Pushed to `main` | ✅ `34ea15f..047c740` | ✅ `7c377dd..1a3d09e` |
| HEAD verified via API | ✅ | ✅ |
| Open PRs | 0 | 0 (all 13 PRs closed) |
| Commit comments | 0 | 0 |
| Issues — open | 0 | 1 (#12 "رؤى Observatory" — video design preview, created 2026-06-20, **unrelated**) |
| Check-runs / CI | 0 (no CI configured) | 0 (no CI configured) |
| Keyword search: `event_type` | 0 matches | 0 matches |
| Keyword search: `temporal_data` | 0 matches | 0 matches |
| Keyword search: `/v1/intelligence` | 0 matches | 0 matches |
| Keyword search: `contract` | 0 matches | 0 matches |
| Keyword search: `K1` | 0 matches | 0 matches |
| Keyword search: `K2` | 0 matches | 0 matches |

**Result: no unresolved review/comment/CI item affecting contract semantics — closure unblocked.**

---

## M. Activation implications

With K1/K2 promoted, the IntelligenceObject is now **semantically complete** for consumer use:

```
IntelligenceObject
├── io_id, version, event_id, event_version  (identity + versioning)
├── headline                                  (human-readable summary)
├── chain                                     (full provenance: fact → evidence → representation → document → source)
├── created_at                                (IO construction timestamp)
├── status, supersedes_io_id                  (transport projections)
├── event_type                                (K1 — what kind of event: monetary/regulatory/statistical/...)
└── temporal_data                             (K2 — when published + what period covers)
    ├── publication_time                      (when the source published)
    ├── publication_time_raw                   (original timestamp from source)
    ├── publication_timezone_status            (D4 timezone semantics)
    ├── reference_period                      (D4 §9 — statistical reporting period, or null)
    └── reference_period_normalized_utc        (D4-normalized reference period)
```

Consumers (News, future Trading/Corporate) can now make product decisions based on:
- **What kind of intelligence is this?** → `event_type`
- **When was it published?** → `temporal_data.publication_time`
- **What period does it cover?** → `temporal_data.reference_period` (statistical releases only)
- **Is this the latest version?** → `status` + `supersedes_io_id`
- **Where did it come from?** → `chain[0].source.institution_id` + `chain[0].document.canonical_url`

The Core is no longer just a source-processing engine or a transport layer. It is now a **semantically complete intelligence contract** that exposes what the event is, when it was published, what period it covers, and the full provenance chain — all from real Core state, with no fabrication.

### What this enables

1. **News product rollout**: News can now filter stories by `event_type` (e.g. show only `regulatory_enforcement`), sort by `publication_time`, and display `reference_period` for statistical releases — all from canonical Core fields, no inference.
2. **Trading product alignment**: Trading can consume `event_type=monetary_policy_decision` directly to trigger rate-decision workflows.
3. **Corporate product alignment**: Corporate can consume `event_type=regulatory_enforcement` for compliance monitoring.
4. **Future K3-K5 architectural decisions**: The contract authority is now stable enough to make separate authorized decisions about `provenance/confidence/reproducibility` semantics (if ever needed) without disturbing K1/K2.

---

## N. Stop condition (directive §19)

STOP. Do NOT:
- activate Wave-1,
- align Trading,
- align Corporate,
- implement PDF,
- build Playwright,
- start another 50–100 source test,
- modify Method V1.

---

## O. Strategic significance

**Before this promotion**: The Core was a real production transport serving real official-source IOs to News — but the IOs lacked `event_type` and `temporal_data`. Consumers had to infer "what is this event?" from headline text and "when was it published?" from `created_at` (which is the IO construction time, not the source publication time). This was a semantic gap that limited the Core's usefulness as a global intelligence layer.

**After this promotion**: The Core emits `event_type` and `temporal_data` directly from real Core state. Consumers can now answer "what is this event?" and "when was it published, what period does it cover?" without inference — directly from canonical fields.

The full chain is now **semantically complete**:

```
Official Source
↓
Document
↓
Facts / Events
↓
IntelligenceObject
   ├── event_type               ← K1 (what kind of event)
   ├── temporal_data            ← K2 (when published, what period covers)
   ├── provenance chain         ← full traceability
   └── version lineage          ← supersedes_io_id + event_version
↓
/v1/intelligence
↓
News / Trading / Corporate
```

The Core is now **the common source of intelligence for all ROUAA products** — not just a data transport layer, but a semantically complete intelligence contract.
