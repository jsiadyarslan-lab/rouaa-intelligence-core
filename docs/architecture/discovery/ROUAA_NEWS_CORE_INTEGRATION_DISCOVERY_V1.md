# ROUAA NEWS — CORE INTEGRATION DISCOVERY V1

**Status:** READ-ONLY DISCOVERY (no commits, no modifications — per directive §19/§20)
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — ROUAA NEWS INTEGRATION DISCOVERY V1 (user-issued verbatim)
**Discovered object:** `jsiadyarslan-lab/rouatradingnews` @ `e1dd6c2dcbbdfa737a2b31283466c8dcbc5b90e6` (main, 2026-07-18 "Sprint 3.1: Add IntelligenceSection to tr homepage")
**Reference Core:** `rouaa-intelligence-core` @ `bf69120` (public; Gate-G staging recommendation)
**Deliverable location:** THIS DOCUMENT IS LOCAL-ONLY — no repository was modified and no commit was created (directive forbids modifying rouatradingnews / rouaa-intelligence-core / rouaa-corporate). Its permanent home is an open question (§S).

---

## A. Repository Baseline

| Item | Finding |
|---|---|
| Commit | `e1dd6c2` (main) |
| Framework | Next.js 16.1.1 (App Router) + React, Tailwind, next-auth (+Passkey), next-themes |
| Runtime | Node (bun.lock present), Docker + Caddy, standalone build scripts |
| Database | PostgreSQL via Prisma 5 (`@prisma/client`), 40+ models, migrations + runtime auto-migrate |
| Major surfaces | 339 API routes; 5 locale site trees (ar/en/es/fr/tr); dashboard/admin/alerts/academy/markets/… |
| Entry points | Next server; **in-process orchestrator loops** (ar `orchestrator.ts`, en/es/fr/tr variants) + `src/app/api/cron/*` (11 cron routes) |
| AI providers | Multi-provider chain: **Bedrock Claude (#1 for Arabic)**, Groq, Gemini 2.5-flash (tiered quota), DeepSeek, GLM, HuggingFace, Ollama, OpenRouter, Mistral-Nemo, z.ai SDK (`ZAI_*` env) — fallback chain + degraded mode |
| Ingestion | RSS feeds array; Finnhub; Google-RSS web search; official-sources collector; horde polling; internal content feeds; DB fallback |
| Publication | publisher agent + quality gates + publish quota; isReady (IRREVERSIBLE) → isPublished |

## B. Current News Architecture (current-state diagram)

```text
RSS_FEEDS (~602 in code) ─┐
Finnhub API ──────────────┤
Google-RSS web search ────┤→ news-sources.ts fetchers → NewsItem (DB) → per-locale pipeline:
official-sources collector┤      (ar/en/es/fr/tr orchestrator loops, 60–90 s cycles, watchdogs)
internal content feeds ───┤          fetcher → content-loader → analyzer (AI) → imager (Gemini)
DB fallback ──────────────┘          → publisher → published article (+reports: daily/weekly/…)
                                                    └→ archive, newsletter, telegram, alerts
```

## C. Ingestion System

- **RSS** `src/lib/news-sources.ts`: `RSS_FEEDS` ≈ **602 entries** (post "V1081 cleanup of 585 broken feeds"); `fetchRSSFeed()`; category+language per feed.
- **Official collector** `src/lib/pipeline/collectors/official-sources.ts` + config registry ("VERIFIED WORKING… extracted from news-sources.ts"; public RSS/APIs only; per-source rate limiter; RSS/API timeouts; SEC EDGAR watch CIKs). Feeds the news-writer agent.
- **APIs**: Finnhub; EDGAR; horde-poll cron.
- **Dedup**: `findFirst({url})` + `[url]`/`[url,locale]` indexes (§NewsItem); Google-RSS result dedup filter.
- **Persistence**: Prisma `NewsItem` (+`NewsFetchLog`, `PipelineRun`, `AgentLog`).
- Manual inputs: news-writer agent path (LLM-edited originals).

## D. Source Registry (DUPLICATED ×4 — flagrant per §3)

1. `RSS_FEEDS` in code (~602: mostly press/media feeds, category+language).
2. `data/sources/*.json`: **global-official-sources-v1.json (411 sources** with `authorityScore`, type, country, relatedAssets) + 9 wave files + `source-metadata-registry.json` (priority/importance/expectedFactYield/expectedEventYield per wave).
3. `official-sources.config.ts` registry (verified-working subset for the writer agent).
4. `SEC_EDGAR_WATCH_CIKs` watch list.

None is entity-verified (no domain→legal-entity binding, no imprint evidence). `authorityScore` is a heuristic number, not evidence.

## E. NewsItem Model (field-by-field)

| Field | Class | Note |
|---|---|---|
| id, createdAt/updatedAt | NEWS-PRODUCT | |
| title / titleAr / summary / summaryAr / content / contentAr | **EDITORIAL/DERIVED** | content = fetched full text (closest thing to evidence); *_Ar = AI translation |
| source (slug) / sourceName | **CORE-CANDIDATE** (as display echo) | canonical identity must come from Core Source Registry |
| **isOfficialSource** | **CORE-CANDIDATE (re-derive)** | currently heuristically set (content-feed flags internal/Rouaa content true; collector implies official) — NOT trustworthy vs D6 |
| url (originalUrl) | **CORE-CANDIDATE** | Core canonical_url supersedes (NR-v1) |
| category / categoryId | NEWS-PRODUCT (editorial classification) | Core event types are different axis |
| sentiment / sentimentScore | NEWS-PRODUCT (editorial AI) | |
| impactLevel / impactScore | NEWS-PRODUCT (editorial AI, V101) | |
| originalLanguage / locale | NEWS-PRODUCT (multilingual editorial) | |
| newsType (live/breaking/article) | NEWS-PRODUCT | |
| affectedAssets (JSON string) | NEWS-PRODUCT (AI-derived) | |
| aiAnalysis (JSON incl. fullContent) | NEWS-PRODUCT | contains editorial analysis |
| isPublished / isReady (irreversible) / processingStage / retryCount / rejectCount / lastError | NEWS-PRODUCT (workflow) | |
| imageUrl / generatedImage (base64) / slug / views | NEWS-PRODUCT | |
| publishedAt / fetchedAt | split: publishedAt=article lifecycle (NEWS); source publication semantics missing → **CORE-CANDIDATE** via temporal tuples | |
| bookmarks/comments relations | USER/ENGAGEMENT | |

## F. Agent / AI Pipeline (29 agent files + orchestrators)

fetcher → content-loader → analyzer(+locale variants) → imager(+infographic generators) → publisher → archiver; report generators (daily/weekly/monthly/quarterly/technical); news-writer; guardian/raqeeb monitors; geopolitical + stock pipelines.

| Step | Input→Output | Provider | Should remain News-owned? | Consumes Core IO? |
|---|---|---|---|---|
| fetcher | feeds→NewsItem rows | — | NO — **Core replaces** (official sources) | — |
| content-loader | url→content | fetch+cheerio(+playwright dep) | NO for official sources — **Core representations replace** | yes (representation text) |
| analyzer | content→sentiment/impact/assets/aiAnalysis | Bedrock/Groq/Gemini/… chain | YES (editorial) | yes (IO as anchored input) |
| translator (titleAr/contentAr…) | EN→AR | same chain | YES | — |
| news-writer | sources→edited original | LLM | YES (editorial) | yes (IO feed) |
| imager/infographics | article→image | Gemini | YES | — |
| fact-checker | (planned per NEWS_WRITER_AGENT_PLAN) | LLM | YES — **must cite Core evidence** | yes (trace contract B) |
| publisher/quality-gates/quota | ready article→published | — | YES | — |
| SEO (slug) | title→slug | — | YES | — |

## G. Editorial Boundary (raw content → article)

summarization · Arabic (+es/fr/tr) translation · sentiment · impact scoring · affected-assets · category classification · headline/title · LLM article writing · image generation · fact-check (planned) · publication decision (quota/gates/irreversible-ready). **All editorial — remain News-owned.** The future boundary: `Core IntelligenceObjects (facts/events/evidence/temporal) → News Editorial Intelligence (everything above)`.

## H. Evidence / Provenance (what survives source→NewsItem)

Retained: url, fetchedAt (retrieval date), content (full fetched text — best-effort), aiAnalysis.fullContent, source/sourceName.
**Lost:** exact source excerpt/paragraph refs · content hash/representation identity · retrieval event · SOURCE publication date/timezone semantics (D4 tuple) · document versioning · transformation history (which AI model/when) · evidence chain · correction propagation (irreversible isReady + url-only dedup mean a corrected source page yields a NEW item, not a version). **This is the single largest gap vs the Core's promise** — the future article must reference Core lineage (representation sha256 + fact/event versions via Contract B).

## I. Database Ownership

- **Core-owned candidates (eventually stop receiving News-side canonical writes):** source identity/url/isOfficialSource (→ Core Source Registry); raw fetched content (→ Core Document/Representation); any fact/event-ish fields News derives from official sources (→ Core Facts/Events/IO). NewsFetchLog/PipelineRun/AgentLog stay NEWS (operational logs of the editorial factory).
- **News-owned:** NewsItem editorial columns, Archive, Bookmark, Comment, Notification, PriceAlert, Subscription, NewsletterSubscriber, Advertisement, Discussion(+replies), TelegramAccount, Report/Infographic/VideoReport/ReportView, TradingSignal/CouncilBrief/MarketAnalysis/StockAnalysis (product analytics), User/Account/Session/Passkey/ApiKey/SiteSetting/UserProfile/PersonalizedRecommendation, CalendarEvent/EconomicEvent/MarketIndicator (news-side views until a future decision).
No schema changes now (§9).

## J. API Boundary

339 routes. Classification summary: **PRODUCT API** (public news/markets/alerts/auth/…), **INTERNAL PIPELINE API** (cron/*, admin/pipeline, stock-pipeline-debug, ai/*), **ADMIN API** (admin/*, keys, models). **CORE-CONSUMING API (future):** news read paths + analyzer inputs would call Core: health, sources list, IO feed (by jurisdiction/type/time), trace (Contract B), delivery status. Do not implement now.

## K. Scheduling

In-process loops (AR 90 s, EN 60 s; watchdogs 5 min; empty-cycle resets) + 11 cron routes (advisor, economic-data, generate-reports, guardian, horde-poll, raqeeb, raqeeb-en, newsletter, stock-analysis, stock-pipeline, telegram). **Future:** official-source acquisition scheduling belongs to the **Core** (S1/S4 staging items); editorial cycles, reports, newsletter, images remain **News**.

## L. Current vs Target Architecture

```text
TARGET:
Official Sources → ROUAA Intelligence Core (registry/entity/acquire/represent/
extract/detect/evidence/provenance/temporal/IO/delivery)
   → Canonical Intelligence (IO + trace) → News Editorial Pipeline (translate/
     analyze/write/image/fact-check/publish) → Published Article (cites lineage)
News keeps: press/media RSS for GENERAL news (non-official lane), editorial,
engagement, product surfaces.
```

## M. Duplicate Responsibilities (vs Core)

| News today | Class |
|---|---|
| Official-source discovery/registry (4 registries) | **MUST MOVE** (Core Source Registry; D6 entity verification) |
| isOfficialSource heuristic | **MUST MOVE** (Core verified-source flag; re-derive from Core) |
| Official document fetching + content loading | **MUST MOVE** (Core representations, hashes, retrieval events) |
| URL dedup | **SHOULD DELEGATE** (representation identity; News keeps slug/locale dedup for its articles) |
| Provenance/evidence retention | **MUST MOVE** (Core chain; article cites lineage) |
| Fact/event-ish extraction on official content | **SHOULD DELEGATE** (Core facts/events; News may keep editorial tags) |
| Source health (fetch logs) | **SHOULD DELEGATE** for official sources (Core health); News keeps its own press-feed ops |
| Press/media RSS fetching (non-official lane) | **MUST REMAIN** (out of Core scope) |
| Sentiment/impact/translation/images/publishing/SEO | **MUST REMAIN** |
| Old V1081-dead-feed debris + duplicate registries | **SHOULD BE REMOVED LATER** (post-integration, evidence-first) |

## N. 1500+ Source Strategy (conceptual — nothing imported)

`Global Source Registry (Core) → Core processing (config-contract onboarding waves) → Event/IO routing → News relevance filter (jurisdiction/asset/category订阅) → Editorial pipeline`. News needs: **filterable IO stream + trace**, NOT raw sources; onboard by wave priority (central banks → statistics → regulators → …) using Core qualification; press/media lane stays News-side. All sources are NOT equal: authorityScore heuristics get replaced by Core verified-entity + evidence-backed importance.

## O. Core → News Data Contract (draft)

IO-first delivery containing: io_id/version · event type+version · facts(metric,value,unit) · evidence excerpt+location · representation sha256 · document canonical_url · source institution (verified) · temporal tuples (publication semantics, tz-safe). News may cache read-only, transform editorially, never write back; corrections arrive as new IO versions (D2) — News re-renders affected articles with history preserved.

## P. News-Owned Responsibilities (unchanged)

editorial classification/story ranking/headlines/article structure/Arabic+multi-locale translation/editorial style/images/publishing/SEO/user engagement — per directive §16, outside the Core unless evidence later dictates otherwise.

## Q. Migration Risks

1. **isOfficialSource semantics drift** (heuristic vs verified) — articles may flip classification; needs mapping table + editorial review window.
2. **Provenance backfill impossible** — existing NewsItems lack lineage; only NEW items can cite Core. Historical articles stay as-is (explicitly documented).
3. **Duplicate registries conflict** — 4 registries disagree; consolidation must be evidence-first (Core qualification), not a bulk import.
4. **Irreversible isReady + quota gates** — correction propagation must NOT fight the editorial workflow; corrections enter as new items/versions with explicit editorial state.
5. **In-process orchestrators + 339 routes** — integration points must be additive (consume Core API) without destabilizing loops/watchdogs.
6. **AI provider sprawl** — keep editorial chain untouched; Core never becomes an AI dependency of News's editorial layer (it delivers evidence, not prose).
7. **Playwright dependency** exists in News for content loading — Core scope excludes rendering; News may keep its own for the press lane (documented divergence).

## R. Recommended Integration Sequence (after Trading discovery + Cross-Product Architecture)

1. Core staging (Gate G→H) with CORE API: health/sources/IO-feed/trace.
2. News adds a **read-only Core consumer** behind a flag: analyzer/fetcher for OFFICIAL sources start preferring Core IOs (dual-write observation period; no ingestion removal).
3. isOfficialSource re-derivation from Core registry (shadow mode → cutover).
4. Official-source ingestion in News switches to Core feed (News FetchLog keeps operational notes; canonical acquisition retired gradually — "SHOULD BE REMOVED LATER").
5. Article lineage fields (io_id/version + trace link) added; corrections flow as new IO versions.
6. Press/media lane remains News-native. Registry debris cleanup LAST, evidence-first.

## S. Unresolved Questions

1. Permanent home of this discovery document (corporate? Core? News?) — none modified per directive.
2. Does News's press/media lane (non-official) ever need Core-style provenance? (Open; default NO.)
3. Trading/Corporate discovery pending — same methodology next (per STOP condition).
4. Cross-Product Core Integration Architecture (Core├News├Trading└Corporate) — to be authored after both discoveries.
5. Core API auth model for product consumers (staging token vs per-product keys).
6. Handling of legacy NewsItems without lineage (archive policy).
7. Multi-locale: does the Core ever carry locale variants of IOs, or is locale purely editorial? (Current answer: purely editorial.)

---

## Critical Architectural Questions (§17 — direct answers)

1. **Exact Core→News data:** IO-first payloads with full trace (facts/events/evidence/representation sha/document/verified institution/temporal tuples) + health + delivery status.
2. **What Core replaces:** official-source discovery/registry/fetching/content-loading/dedup(official)/official-source health/official provenance.
3. **What Core must NOT replace:** sentiment, impact, translation, headlines, article writing, images, fact-checking judgment, publishing, SEO, engagement, press/media RSS lane.
4. **Editorial pipeline start:** at the IO boundary — analyzer/writer consume Core IOs (+ optionally raw press items) as anchored inputs.
5. **Canonical article source:** News DB remains canonical for ARTICLES; Core is canonical for SOURCE INTELLIGENCE. Article cites io_id/version.
6. **Citation of evidence:** embedded trace (Contract B) — excerpt + representation sha256 + canonical_url, rendered in article footer/evidence panel.
7. **Correction propagation:** Core supersession → new IO version → News re-render/derives follow-up article with history preserved (never silent rewrite; isReady semantics untouched).
8. **Consume without becoming a registry:** News subscribes to Core sources/IO feed; its own registries shrink to the press lane; official lane reads Core IDs only.
9. **Tables remaining:** all News-owned tables (§I) stay.
10. **Tables stopping canonical source data:** NewsItem.source/url/isOfficialSource/content (official lane) become echoes of Core references post-cutover; source registries 1–3 (§D) retire.

**STOP per §20 — no integration started, no ingestion removed, Core not connected. Next: same-methodology discovery of ROUAA Trading, then a single Cross-Product Core Integration Architecture.**
