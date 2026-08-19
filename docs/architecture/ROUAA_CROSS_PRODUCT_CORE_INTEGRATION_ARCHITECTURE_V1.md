# ROUAA CROSS-PRODUCT CORE INTEGRATION ARCHITECTURE V1

**Status:** ARCHITECTURE (design only — no integration, no migration, no deployment)
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — CROSS-PRODUCT CORE INTEGRATION ARCHITECTURE V1 (user-issued verbatim)
**Authoritative inputs (actual documents read, exact commits):** News discovery @ `e1dd6c2` · Trading discovery @ `12d7d90` · Corporate discovery @ `0d71f61` (main) · Core Architecture V1.1 @ `9298162` · Extraction @ `743c3bf` · Buyer Simulation @ `150ae87` · Productionization review @ `bf69120`.
**Home:** `rouaa-intelligence-core/docs/architecture/` — it defines the ecosystem contract, therefore it belongs with the Core (directive §28).

---

## A. Executive Architecture

One principle governs the ecosystem: **what is canonical becomes canonical ONCE — inside the ROUAA Intelligence Core.** Official-source identity, documents, facts, events, evidence, provenance, temporal semantics, and IntelligenceObjects are produced and versioned exclusively by the Core. Products interpret: News editorializes, Trading decides and executes, Corporate presents. Products may filter, rank, translate, size, and display — they may not re-derive source identity, may not fork canonical truth, and may not become upstream of the Core.

## B. Current-State Systems (as discovered)

| System | Commit | Reality | Canonical duplication |
|---|---|---|---|
| Core (repo4) | `743c3bf`/`bf69120` | validated Minimum Core; staging-authorized | — (THE canonical) |
| News | `e1dd6c2` | 5-locale editorial factory; **4 registries** (RSS_FEEDS ~602, 411-source JSON + 9 waves + metadata, writer-agent list, EDGAR CIKs); provenance lost at NewsItem | source identity, official classification, official fetching, dedup |
| Trading | `12d7d90` | execution platform; **direct News bridge** (sentiment→Redis→Council/Executor gate) + own press lane (CryptoPanic/CT/CD) = 3rd duplication layer | official intelligence input path, news classification |
| Corporate (main) | `0d71f61` | fully static presentation site; **mvp seeded 72-source registry** + manual "411+" copies | source count claims, latent registry |

## C. Canonical Source of Truth

**ONE CANONICAL SOURCE REGISTRY = ROUAA INTELLIGENCE CORE.**
Retire/delegate upon migration (evidence-first, phased — §Q): News `RSS_FEEDS` (official subset), `data/sources/*.json` (411 + waves + metadata), writer-agent registry, EDGAR list → **MUST MOVE**; News press/media feeds → remain product-local (§I). Trading: official/fundamental input lane → **MUST DELEGATE** to Core IO; CryptoPanic/CT/CD press lane → **REMAIN Trading-local** (decision W5). Corporate: `mvp/backend/seed-data.ts` registry → **RETIRE with mvp** (or rebuild as Core client); "411+" manual copies → **MUST DELEGATE** to Core-derived metric (§13 rule below).
Products keep ONLY: relevance filters, editorial categories, trading relevance, presentation metadata.

## D. Entity Resolution (cross-product trust boundary)

`Domain → Verified Institution → Legal Entity → Jurisdiction → Institutional Class → Source Path` — owned by the Core (D6), regression-anchored on **bmf.de ≠ Ministry of Finance** (proven live through simulation). **A product MUST NOT independently decide that a domain is an official source.** News's `isOfficialSource` heuristic and Trading's implicit "news = market-moving" classification become derived reads from Core verified identity (shadow → cutover per §R/S).

## E. Core Domain Ownership

Core owns (exclusively): Source, Institution, Document, Representation, Retrieval Event, Fact, Event, Evidence, Provenance, Temporal semantics, IntelligenceObject, Delivery ledger. News must NOT recreate the document/evidence chain (its lineage fields become Core references); Trading must NOT recreate it; Corporate must NOT recreate it. Products keep product-specific references/metadata only (io_id + version + trace refs).

## F. Core → News

**Core delivers:** IntelligenceObjects (identity+version), facts/events, evidence, provenance, source-document reference, temporal semantics, quality/governance metadata. **News retains:** editorial selection, story ranking, article composition, Arabic/multi-locale translation, sentiment, impact, editorial reasoning, headlines, structure, images, SEO, publication, engagement. Rule: **Core supplies evidence-backed intelligence; News creates editorial output. Core never generates News prose.**

## G. Core → Trading

**Core provides:** supported financial events, facts, source, institution, temporal semantics, evidence, provenance, version, quality metadata. **Trading adds:** market prices, instruments, portfolio exposure, strategy state, risk state, market regime, execution state. Flow: `Core Intelligence + Market Data + Portfolio/Risk State → Trading Intelligence → Strategy → Decision → Execution`. **Core must NEVER own execution** (credentials, orders, positions, risk — inviolable Trading boundary, discovery §H).

## H. Core → Corporate

Read-only presentation consumer. Minimal contract: `Core → verified coverage / platform metadata (+ optional curated evidence examples) → Corporate`. Corporate does NOT ingest the 1500+ sources, does NOT reproduce source truth, does NOT hard-code dynamic Core metrics (cached snapshots with measurement definition + date allowed). Exposure classes: PUBLIC (verified counts, capability claims) · AUTHENTICATED (health detail, demo traces curation) · INTERNAL ONLY (raw IO feeds, delivery internals).

## I. News → Trading Relationship (critical current-state issue)

**Current** (`12d7d90`): `News (rouatradingnews) → sentiment indices → Redis → Strategic Council / Smart Executor risk gate` — a direct product-to-product dependency for market-relevant intelligence, plus Trading's own press lane: three intelligence duplication layers.
**Target:** `Official Source → Core → Canonical IO ├→ News Editorial Layer └→ Trading Intelligence Layer`. Trading must NOT consume News as the canonical intelligence path; News may remain an *additional editorial input* (headline context), while **canonical official intelligence comes from Core only**.
Transition strategy: **dual-read** (Core consumer added behind flag) → **shadow comparison** (council prompts log both inputs; no execution change) → **source-by-source cutover** (official events switch to Core IOs) → **deprecation** (News bridge → optional fallback → removed). Not executed now.

## J. 1500+ Source Operating Model

Not 1500 identical jobs. Hierarchy per source: `Source → Institution → Content Path → Acquisition Method → Intelligence Type → Priority → Monitoring Policy → Product Relevance`, carrying jurisdiction, institutional class, language, frequency, health, consumer products. **Onboarding pipeline:** `Registry → Qualification → Configuration → Activation → Monitoring → Evidence → Product Routing` — activation by waves (central banks → statistics → regulators → exchanges → ministries → international), qualification-gated exactly as the validated pipeline proved (config-contract, per-source isolation). No requirement to activate all 1500 immediately; nothing activates without qualification evidence.

## K. Cross-Product Database Ownership

Core: the §E set + delivery metadata. News: Article, editorial workflow, translation, images, publication, engagement, subscriptions. Trading: market data, instrument mapping, accounts, orders, positions, portfolio, risk, strategies, execution, trading state. Corporate: CMS, website content, leads, briefing requests, analytics, presentation metadata. **No shared mutable ownership** — cross-references are ids (io_id/version/source_id), never foreign writes.

## L. Cross-Product API Contracts (conceptual — NOT implemented)

| Endpoint | Consumer | Auth | Payload essence | Versioning | Latency | Failure semantics |
|---|---|---|---|---|---|---|
| `GET /health` | all | none/token | status, storage writable | /v1 | <1s | 5xx → consumers enter fallback |
| `GET /sources`, `/sources/{id}` | News, Trading, Corporate | product token | verified identity, jurisdiction, class, health summary | /v1 | seconds | 404 unknown; cacheable |
| `GET /documents/{id}` | products (detail) | token | metadata + representation refs (not blobs) | /v1 | seconds | 404; never partial |
| `GET /intelligence/{id}` | News, Trading | token | IO + version + chain summary | /v1 | seconds | immutable once issued |
| `GET /intelligence/{id}/trace` | News, Trading, Corporate(curated) | token | Contract-B full chain | /v1 | seconds | read-only, no mutation surface |
| `GET /evidence/{id}` | products | token | excerpt + location + representation sha | /v1 | seconds | 404 |
| `GET /deliveries/{id}` | products (acks) | token | delivery status/idempotency | /v1 | seconds | ledger truth |

Error model `{code, message, trace_ref}`; cursor pagination; rate limits per token; idempotent reads.

## M. Event / Intelligence Routing

One IO may feed many products: `ECB rate decision → Core IO ├→ News (article/research) └→ Trading (strategy input)`. **Same canonical object, different product interpretation. Products must not fork Core truth** (no local "corrected" copies — they consume versions).

## N. Corrections / Version Propagation

`Core correction → new representation → new fact/event version → new IO version → consumer notification/polling`. News: article correction/republication policy driven by new IO version (history preserved; isReady semantics untouched — re-derivation is editorial policy). Trading: strategy/state response — gates re-evaluate open briefs/positions per Trading policy; never silent mutation. Corporate: runtime metric refresh. **No product rewrites Core truth.**

## O. Temporal Contract at the Ecosystem Edge

`source temporal tuple → Core normalized representation (D4, ordering-safe UTC) → product-specific temporal interpretation`. Trading preserves: source publication time, normalized UTC, market timestamp, execution time (distinct columns/clock domains — today all-naive; adoption at the seam). News preserves: source publication, retrieval, editorial/publication times. Corporate: measurement time + runtime generation time. **These clocks are never collapsed.**

## P. Failure Isolation Across Products

`Core failure ≠ News failure ≠ Trading failure ≠ Corporate failure`. News serves published content regardless of Core availability; Trading continues market operations under explicit safe behavior (Core absence degrades intelligence depth, never halts execution unless a strategy/risk rule explicitly declares the dependency); Corporate falls back to cached verified presentation data (static fallback with dated measurement). Contracts defined now; mechanisms implemented later.

## Q. Migration Strategy (gated — no cutover without equivalence evidence)

**Phase 1** Read-only Core integration (flagged consumers). **Phase 2** Dual observation: current product intelligence vs Core intelligence (logged, diffed). **Phase 3** Core becomes canonical for official intelligence (cutover per source-class). **Phase 4** Disable duplicated official-source ingestion. **Phase 5** Remove obsolete registries. **Phase 6** Product-specific optimization.

## R. News Migration

`Core source registry → News consumes Core IOs (official lane) → retain editorial pipeline → dual-run old ingestion → compare (coverage/provenance/latency) → disable official-source duplicate ingestion → retain non-official/editorial feeds locally`. Legacy NewsItems keep pre-Core status (lineage backfill impossible — documented).

## S. Trading Migration

`Core official intelligence → Trading consumer adapter (flagged) → preserve market data/execution untouched → dual-run News-sentiment AND Core-signals where relevant → compare (A/B via existing strategy-testing infra) → define replacement boundaries → cut over canonical official intelligence → News bridge demoted to fallback → removed`. The news risk gate stays Trading-owned; only its input changes.

## T. Corporate Migration

`Core runtime metrics → read-only Corporate contract → replace hard-coded dynamic metrics ("411+" → cached Core-derived count with measurement definition+date) → preserve static marketing narrative → retire duplicate mvp source registry`.

## U. Conformance Tests (required before ANY production integration)

1. **Identity:** one source → one canonical Core identity (bmf.de regression at ecosystem level). 2. **Evidence:** one IO → exact representation/provenance (chain hash walk). 3. **Correction:** Core correction propagates without historical loss (v1 reproducible at every consumer). 4. **Routing:** same Core object consumed independently by News and Trading (same io_id+version). 5. **Isolation:** Core outage does not corrupt product state (fallback contract test). 6. **Idempotency:** repeated Core delivery does not duplicate product entities. 7. **Temporal:** product timestamps remain semantically distinct (no clock collapse). 8. **Security:** products cannot mutate canonical Core intelligence (read-only proof + authz test).

## V. Risks

**P0 (from directive, confirmed by discoveries):** competing Source Registries (News×4 + Corporate mvp + Trading lanes) · duplicate canonical intelligence (3 layers) · ambiguous data ownership (resolved by §K; enforce) · direct News→Trading dependency for official intelligence (§I) · loss of provenance during migration (News legacy gap — mitigate with dual-run + new-item lineage only).
**P1:** synchronization latency (News 15-min Redis TTL precedent) · dual-run divergence (comparison harness needed) · correction propagation into irreversible-ready editorial flows · product cache behavior · asset/entity mapping (absent in Core — W3).
**P2:** performance, advanced routing, future rendering integration, SQL migration, advanced Insight — all deferred with cause.

## W. Unresolved Decisions (for the Integration Implementation Plan; none blocks this architecture's approval, all block execution)

W1 Core→product transport (poll/stream/webhook/queue). W2 Core API auth model (product tokens). W3 asset/entity mapping ownership (Core extension vs product-side tables). W4 freshness SLA per event type. W5 press-lane consolidation (Trading CT/CD/CryptoPanic; News media feeds). W6 mvp fate. W7 permanent home of the three discovery documents. W8 public-metric curation policy (Corporate).

## X. Final Integration Roadmap (post-approval sequence)

```text
Integration Implementation Plan (resolves W1–W8)
→ Core → News controlled integration (flagged, read-only)
→ Core → Trading controlled integration (shadow, gate-input only)
→ Core → Corporate read-only integration (aggregate metric)
→ Dual-run / equivalence validation (per §U conformance)
→ Cutover (per-class, evidence-gated)
→ Registry retirement (Phase 5)
→ 1500+ source onboarding program (begins ONLY after contracts approved)
```

---

## Current-State Diagram

```text
Official Sources
   ├── News ingestion (4 registries; provenance lost; editorial factory)
   │        └──(direct sentiment bridge)──→ Trading Council/Executor gate
   ├── Trading ingestion (press lane: CryptoPanic/CT/CD + NewsArticle copies)
   └── Corporate metadata (static "411+" claims; mvp seeded registry latent)
```

## Target-State Diagram

```text
             1500+ Official Sources
                      ↓
            ROUAA Intelligence Core
          (registry · entity resolution · documents ·
           facts · events · evidence · provenance ·
           temporal · IO · delivery — canonical ONCE)
                      ↓
             Canonical Intelligence
          ┌───────────┼───────────┐
          ↓           ↓           ↓
         News       Trading    Corporate
      Editorial    Strategy     Presentation
      Intelligence  + Risk      (verified aggregates,
      (translate/   (decides,    curated evidence,
       analyze/      executes —   read-only contract)
       publish)      Core never owns execution)
```

---

# VERDICT

# `CROSS-PRODUCT ARCHITECTURE READY FOR IMPLEMENTATION`

Readiness is conditional by construction: the Integration Implementation Plan must resolve W1–W8 before Phase-1 execution, every cutover is equivalence-evidence-gated (§Q/U), and **migration is NOT authorized by this document** — only the architecture is. The 1500+ source onboarding program begins only after the integration contracts are approved.

**STOP per §30 — no product integration, no source migration, no Railway deployment, no registry removal, no schema changes. Next phase after approval: Integration Implementation Plan → controlled News → Trading → Corporate integrations → dual-run validation → cutover.**
