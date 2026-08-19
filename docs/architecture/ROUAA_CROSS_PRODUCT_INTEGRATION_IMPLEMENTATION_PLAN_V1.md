# ROUAA CROSS-PRODUCT INTEGRATION IMPLEMENTATION PLAN V1

**Status:** IMPLEMENTATION PLAN (planning only — no integration executed, no product code modified, no migration, no Railway)
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — CROSS-PRODUCT INTEGRATION IMPLEMENTATION PLAN V1 (user-issued verbatim)
**Implements:** `ROUAA_CROSS_PRODUCT_CORE_INTEGRATION_ARCHITECTURE_V1.md` @ `e0964f5` (approved for implementation)
**Home:** `rouaa-intelligence-core/docs/architecture/` (with the ecosystem contract it executes)

---

## A. Objectives

Resolve architecture decisions W1–W8 into one executable, evidence-gated integration sequence; define contracts, tests, safety, database mapping, transport, and the local-vs-Railway split; and place the historical discovery artifacts in their canonical home (W7 — executed with this commit).

## B. Authoritative Inputs

Core: `9298162` (V1.1) · `9af81b7` (build) · `0f4139b` (Phase-2) · `8de74e9` (hardening) · `150ae87` (simulation) · `743c3bf` (extraction) · `3a64fb7` (extraction plan) · `bf69120` (productionization) · `e0964f5` (cross-product architecture). Product trees (re-verified in discoveries, commits pinned): News `e1dd6c2` · Trading `12d7d90` · Corporate main `0d71f61`. Discovery documents: now IN THIS REPOSITORY at `docs/architecture/discovery/` (W7).

## C. W1 — Source Registry Cutover Design

Core canonical record per source: `institution_id` (verified entity) · `source_id` (stable) · `source_path` · configuration (config-contract, versioned) · validation state (qualification evidence) · activation state (wave-gated) · health (pipeline states) · product relevance (routing tags, per product).

Classification of every existing registry (mapping only — nothing migrated now):

| Registry (system @ commit) | Class |
|---|---|
| News `RSS_FEEDS` — official-source subset | **CANONICAL → DELEGATE** (Core onboarding input) |
| News `RSS_FEEDS` — press/media subset | **PRODUCT FILTER** (stays News-local) |
| News `data/sources/global-official-sources-v1.json` (411) + 9 waves + metadata registry | **CANONICAL → DELEGATE** (qualification input; authorityScore heuristic NOT carried as truth) |
| News writer-agent `official-sources.config.ts` | **CANONICAL → DELEGATE** |
| News SEC EDGAR CIK watch | **CANONICAL → DELEGATE** |
| News V1081 dead-feed debris | **REMOVE LATER** (evidence-first cleanup, post-cutover) |
| Trading official/fundamental input lane (implicit via bridge) | **CANONICAL → DELEGATE** |
| Trading press lane (CryptoPanic/CT/CD → NewsArticle) | **PRODUCT FILTER** (W5 tracks; consolidation decision at Phase 8) |
| Corporate `mvp/backend/seed-data.ts` (72 sources CRUD) | **LEGACY → REMOVE LATER** (mvp retired or rebuilt as Core client — decision at Phase 9) |
| Corporate hardcoded "411+" claims | **CANONICAL → DELEGATE** (become Core-derived cached metric, §H) |

## D. W2 — Core → News Contract

Core provides: IntelligenceObject (identity+version), Event/Fact, Evidence, Provenance, Document reference, temporal tuple, version, quality/governance metadata. News owns: editorial relevance, story selection, research synthesis, translation, sentiment, impact, article generation, fact checking, images, SEO, publication (unchanged from architecture §F).
Implementation: **REST polling** (§P) of `GET /v1/intelligence?since=<cursor>` (IO summaries) + `GET /v1/intelligence/{id}` (full) + `GET /v1/intelligence/{id}/trace`. Request model: product token header, cursor, optional filters (jurisdiction, event_type). Response model: IO JSON (chain-embedded, per Core delivery format) + `next_cursor`. Auth: product token (News token). Versioning: `/v1` URI. Idempotency: io_id+version keys; redelivery = no-op. Caching: ETag/If-None-Match server-side; News caches read-only with staleness label. Retry: exponential backoff, transport-class only. Failure behavior: **fallback to existing ingestion** (dual-run makes degradation invisible editorially).

## E. W3 — News Dual-Run

`Existing News Ingestion ├─ current path ──┐ └─ Core path ─→ Equivalence Layer ←─┘`. Comparison fields per document: source identity (News source slug ↔ Core institution/source ids via mapping table) · document identity (NewsItem.url ↔ Core canonical_url under NR-v1) · content (fetched text ↔ representation blob hash of normalized text) · publication time (NewsItem fetchedAt/publishedAt ↔ Core temporal tuple semantics) · event type (News category heuristics ↔ Core event_type) · facts (none in News ↔ Core facts — gap expected, recorded not failed) · evidence (absent in News ↔ Core chain — same) · duplicate behavior (url-dedup ↔ representation dedup) · final editorial eligibility (analyzer acceptance parity).
**Cutover success criteria (all required):** (1) ≥95% of Core official documents in a 14-day window matched to a News ingestion event or explainably unmatched (source-class coverage diff); (2) zero provenance regressions on new items (100% of Core-path articles carry lineage refs); (3) editorial eligibility parity within ±5% on matched documents; (4) duplicate rate on Core path ≤ current path; (5) latency: Core path → NewsItem ≤ 2× current fetch-to-row time. Evidence logged in the equivalence store; no cutover without it.

## F. W4 — Core → Trading Contract

Payload (exact): `intelligence_object_id, version, institution, source, event/facts, temporal tuple, evidence, provenance, quality`. **No asset mapping invented in Core** (architecture W3 resolved: mapping is product-owned). Trading performs relevance: **asset relevance** — Trading-side mapping tables (institution→instruments, jurisdiction→currencies, event type→asset classes; seeded from its existing CrossPairCorrelation/portfolio models); **portfolio relevance** — exposure lookup at consumption; **strategy relevance** — per-strategy event-type subscriptions; **risk relevance** — gate policy per event type + market-regime context (gate itself untouched, input swaps per architecture §G).

## G. W5 — News → Trading Transition

Stages: (1) **dual-read** — Trading Core consumer (flagged) runs beside the News bridge; council prompts gain an "official intelligence" section, zero execution change. (2) **shadow comparison** — both inputs logged per council cycle; divergence report (signal presence, timing, source quality). (3) **per-source cutover** — official event classes switch input to Core IOs, class-by-class (rates first — validated evidence base). (4) **fallback** — bridge retained; Core outage ⇒ automatic revert for the affected class (drilled). (5) **deprecation** — bridge demoted to fallback-only. (6) **retirement** — bridge removed. **Retirement conditions (all):** Core official coverage ≥ bridge signal surface for 6 consecutive weeks; shadow A/B equal-or-better council input quality (logged decision metrics); 2 successful fallback drills; explicit user approval. The bridge is NOT removed in any earlier phase.

## H. W6 — Core → Corporate Contract

Read-only: source coverage (verified counts by class/jurisdiction) · verified metrics (IOs/events by type) · source-health summaries · selected evidence demonstrations (curated traces) · platform metadata. Classification: **PUBLIC** — verified coverage/metric aggregates (cached snapshot + measurement definition + date) · **AUTHENTICATED** — health detail, demo curation interface · **INTERNAL** — raw IO feeds, delivery internals. Dynamic metrics originate from Core only; static marketing narrative remains Corporate-owned. Not connected now.

## I. W7 — Discovery Artifact Governance — **RESOLVED (Option A, executed)**

The three discovery documents are placed **verbatim** (content unaltered) in this repository at `docs/architecture/discovery/` in THIS commit: `ROUAA_NEWS_CORE_INTEGRATION_DISCOVERY_V1.md`, `ROUAA_TRADING_CORE_INTEGRATION_DISCOVERY_V1.md`, `ROUAA_CORPORATE_CORE_INTEGRATION_DISCOVERY_V1.md`. Justification: they are the evidence base of the ecosystem contract (@ `e0964f5`) and must live beside it; local originals remain untouched (copy, not move).

## J. W8 — 1500+ Source Rollout (after contracts stable — Phase 10)

Pipeline per source: `Universe → Qualification → Entity Verification → Content Path → Configuration Contract → Activation → Monitoring → Evidence → Product Routing`. **Wave principles:** institutional class first (central banks → statistics → regulators → exchanges → ministries → international — matching validated evidence), jurisdiction diversity within each wave, intelligence-type product value, architecture-class risk (RSS before html_index before anything harder), validation confidence (validated-pattern sources before new phrasing families). No simultaneous mass onboarding; every wave evidence-gated; **no prevalence or success-rate claims** (per-case evidence discipline holds).

## K. Integration Order (10 phases — entry/exit criteria)

| Phase | Content | Exit criterion |
|---|---|---|
| 1 | Core contract preparation (S1 service + CORE API read endpoints `/v1`) | endpoints + health live locally; conformance suite M green |
| 2 | News read-only consumption (flagged) | News reads IO feed; zero editorial change |
| 3 | News dual-run | equivalence layer live; E-criteria measurable |
| 4 | Trading Core consumer (flagged, shadow) | council logs both inputs; zero execution change |
| 5 | Trading dual-read | shadow reports per class |
| 6 | Corporate read-only runtime metrics | "411+" ← Core cached aggregate (static fallback) |
| 7 | Equivalence validation | E-criteria + G-conditions evidenced |
| 8 | Canonical cutover | per-class, evidence-gated |
| 9 | Legacy registry retirement | W1 REMOVE-LATER items, one by one |
| 10 | 1500+ expansion | wave onboarding per J |

## L. Contracts

D (News), F (Trading), H (Corporate) above + the architecture's endpoint table (@ `e0964f5` §L). All: `/v1`, product tokens, cursor pagination, immutable IOs, `{code,message,trace_ref}` errors.

## M. Tests (mandatory before integration — 8 families, concrete specs)

1. **Identity:** same official source resolved through News/Trading/Corporate consumers yields ONE Core identity; bmf.de regression + govdelivery platform refusal at consumer level. 2. **Evidence:** every consumed IO trace-walks to representation with blob-hash match. 3. **Corrections:** injected source revision → new IO version reaches consumers; v1 still reproducible. 4. **Routing:** one ECB-decision IO consumed by News AND Trading adapters independently (same io_id+version). 5. **Isolation:** Core stopped mid-test ⇒ products retain state, enter documented fallbacks, no corruption on Core restart. 6. **Idempotency:** duplicated feed delivery ⇒ no duplicate product records (News item count, Trading brief refs). 7. **Temporal:** publication tuple ≠ retrieval ≠ editorial publish ≠ market/execution timestamps remain distinct fields. 8. **Security:** attempt to POST/PUT/PATCH Core from product tokens ⇒ rejected; read-only proof.

## N. Migration Safety

Every phase ships with: feature flag · dual-run path · comparison logging · rollback (flag off = previous behavior) · audit entries · preservation of historical product state (legacy NewsItems never rewritten; Trading history untouched). **No destructive cutover; no removal before equivalence evidence.**

## O. Database Mapping (mapping only — no schema changes now)

**Unchanged:** all News editorial/engagement tables; all Trading tables (market/orders/risk/execution); Corporate none-live. **Receive Core references (additive, later phases):** News `NewsItem` (+core_io_id, +core_io_version, +trace_ref, official-lane columns become echoes); Trading `TradingBrief`/news-context (+core_io refs), optional trade-influence refs; Corporate none (stateless consumer). **Deprecated after cutover:** News official-source ingestion columns (source/url/isOfficialSource for official lane → echoes), the four News registries, Trading press-lane tables IF W5 consolidation chooses retirement (decision Phase 8), Corporate mvp registry tables (with mvp).

## P. Transport Decision

Evaluated: REST / polling / queue-event / webhook. **Selected for Phase 1–2: REST polling** (minimum viable; Core's S1 service exposes `/v1` read endpoints; News's existing 60–90 s cycles and Trading's council cadence are natural pollers; zero new distributed infrastructure — premature queue/webhook rejected per directive §14). Re-evaluation trigger: freshness SLA (per-event-type config) unmet in Phase 5 shadow data ⇒ design stream/webhook as a Phase 8+ enhancement.

## Q. Railway Dependency

**CAN EXECUTE NOW LOCALLY:** Phase 1 contract prep + CORE API (S1 service local), News/Trading flagged consumers against local Core, dual-run + equivalence tooling, Corporate metric consumption against local Core, all M-tests. **REQUIRES RAILWAY:** staging/prod hosting of Core (Gate H), cross-product network integration beyond dev, persistent public metrics endpoint for Corporate production, real delivery SLAs. Architecture/integration planning is NOT blocked on Railway billing; production deployment remains later (per Gate-G scope S1–S7).

## R. Rollback

Per phase: flag-off restores prior behavior (products keep their current ingestion until Phase 8+ removals). Core rollback = corporate/repo4 lineage (volume-preserving). Registry removals (Phase 9) each carry a git-level restore path and are executed only after their consumers' evidence files.

## S. Execution Gates

Phase entry requires: previous phase exit evidence + M-family results attached + user approval for every phase that touches product repos (Phases 2–6, 8–9) — Core-only phases (1) require Gate-G track approval. Cutover (8) and retirements (9) require explicit user sign-off on equivalence reports.

## T. Unresolved Decisions (execution-level; none blocks plan approval)

T1 freshness SLA numbers per event type (set in Phase 5 shadow config). T2 product-token issuance mechanics (Core config file vs admin endpoint). T3 Trading press-lane consolidation (Phase 8 decision). T4 mvp rebuild-vs-retire (Phase 9). T5 Corporate demo-trace curation list. T6 exact equivalence-report format (Phase 3 deliverable).

---

# VERDICT

# `INTEGRATION PLAN READY`

W1–W8 resolved (W7 executed with this commit); phases, contracts, tests, safety, mapping, transport, and Railway split defined; remaining T-items are execution-time configurations explicitly owned by their phases — not plan blockers. **Implementation is NOT authorized by this document** — the next task (per directive §19) after your approval: `IMPLEMENTATION PHASE 1 — Core contract adapters → News read-only consumption → controlled dual-run`.

**STOP per §19.**
