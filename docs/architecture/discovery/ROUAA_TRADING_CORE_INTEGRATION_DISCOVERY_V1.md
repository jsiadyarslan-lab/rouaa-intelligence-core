# ROUAA TRADING — CORE INTEGRATION DISCOVERY V1

**Status:** READ-ONLY DISCOVERY (no commits, no modifications — per directive §22)
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — ROUAA TRADING CORE INTEGRATION DISCOVERY V1 (user-issued verbatim)
**Discovered object:** `jsiadyarslan-lab/roua-trading` @ `12d7d907b37f354463a036a38130982f9606b278` (main, 2026-07-18 "fix(socket): Redis adapter timeout + graceful fallback")
**Companion discovery:** ROUAA NEWS @ `e1dd6c2` (previous task)
**Deliverable location:** LOCAL-ONLY (no repository modified, no commit created — same ruling as the News discovery; permanent home = open question §U).

---

## A. Repository Baseline

| Item | Finding |
|---|---|
| Commit | `12d7d90` (main) |
| Structure | Turborepo monorepo: `apps/api` (NestJS), `apps/web`, `packages/shared`; Python side-scripts (trade analysis, translations, safety logs); Docker; Playwright tests |
| Database | PostgreSQL via Prisma 6 — **47 models** |
| Redis | redis 6 + `@socket.io/redis-adapter` (with graceful fallback — latest commit) + BullMQ |
| Queues | `@nestjs/bullmq` 11 / bullmq 5 — order-queue processor, execution workers |
| Schedulers | Nest `@Cron` across app.module, agents, council, analytics, engine/scanner |
| Realtime | Socket.IO gateways: `exchange.gateway`, `notification.gateway`, `mt5.gateway` (+ Redis adapter) |
| External integrations | Binance, OANDA, TwelveData, Yahoo/Coingecko/Bybit/CoinCap, MetaAPI/MT5 (ea-bridge + streaming + execution), Alpaca (execution), CryptoPanic, CoinTelegraph/CoinDesk RSS, **rouatradingnews (direct)** |
| AI systems | Gemini + Groq services, ai-orchestrator, strategic-council, smart-executor, council-intelligence, autonomous-trader (+RL), lazic agent, neural module, prediction-market, scanner, signal, assistant, coach |
| Production assumptions | Single API + web deploy; Redis + Postgres required; exchange credentials user-provided; automated trading default-DISABLED (Smart Executor auto-start disabled; explicit user enable) |

## B. Trading Architecture (current)

```text
Market data:  Binance/OANDA streams · TwelveData · Yahoo/CG/Bybit/CoinCap (ai market-data chain)
News:         CoinTelegraph/CoinDesk RSS · CryptoPanic · rouatradingnews DIRECT bridge
              (fearGreed/arabSentiment/geopoliticalRisk → Redis 15-min TTL)
                    ↓
AI:           StrategicCouncil (prompts include news sentiment + articles) → TradingBrief DTO
              SmartExecutor (news RISK GATE + UnifiedRisk + position sizing + correlation)
              AutonomousTrader (adaptive strategy, RL manager, OANDA order executor)
                    ↓
Execution:    BullMQ order queue → adapters (binance/oanda/mt5/alpaca/paper) → Orders/
              Positions/Trades (+ lifecycle logs, reconciliation)
Realtime:     Socket.IO + Redis adapter → web
```

## C. Market Data

| Provider | Class/assets | Mechanism | Refresh | Realtime? | Storage | Consumers |
|---|---|---|---|---|---|---|
| Binance | crypto | WS streaming + REST ticker | continuous | YES | Redis/in-memory | exchange.gateway, council, executor, scanner |
| OANDA | FX | oanda-stream.controller + adapter | continuous | YES | in-memory | autonomous-trader, execution |
| TwelveData | FX/stocks | REST adapter | on demand | no | — | market-data chain, execution |
| Yahoo/Coingecko/Bybit/CoinCap | multi | REST fallback chain (priority: binance>coingecko>bybit>coincap>yahoo) | on demand | no | — | ai market-data.service |
| MetaAPI/MT5 | FX/CFD | ea-bridge + mt5-streaming gateway | continuous | YES | — | mt5 execution, portfolio |
| (free-fallback adapter) | — | synthetic/fallback | — | — | — | resilience |

**Classification: MARKET DATA = TRADING-OWNED.** Price/bid-ask/volume/book/candles/ticks/execution state are NOT Core data (directive §3). No schema change.

## D. External Providers (classification)

Market/execution providers (Binance, OANDA, TwelveData, Yahoo et al., MetaAPI, Alpaca) = **TRADING-OWNED**. News/fundamental inputs (CryptoPanic, CT/CD RSS, rouatradingnews bridge) = **CORE-CANDIDATE lane** (official intelligence should arrive as Core IOs; press lane may remain). Python agents (content/sentiment) that already connect to rouatradingnews = integration seam.

## E. Trading Intelligence Inputs (current origin)

- Economic/central-bank/regulatory/sanctions/earnings intelligence: **NOT directly ingested** — arrives only implicitly via rouatradingnews sentiment indices + CryptoPanic headlines (crypto-centric).
- `NewsArticle` model (own copy): url-unique, sentiment ±1.0, impactLevel, affectedAssets, entities, 384-dim embedding (JSON, pgvector upgrade noted), aiAnalysis "from 6 models".
- StrategicCouncil prompt assembly includes: `[i] (sentiment, impact, score, hoursAgo) title — summary | assets` lines + aggregate sentiment; SmartExecutor holds a **news risk gate**.

## F. Core vs Trading Boundary

```text
MARKET DATA (Trading): price, bid/ask, volume, book, candles, ticks, execution state
INTELLIGENCE (Core):   policy decisions, economic releases, regulatory actions,
                       sanctions, official statements, official statistical facts
Correlation happens INSIDE Trading:
   Core IO + Trading Market Data + Trading State → Trading Intelligence/Strategy → Decision/Execution
```
Trading consumes Core intelligence; Core never owns execution (directive §6 ratified by evidence).

## G. AI / Strategy Layer

| Component | Input → Output | Core relevant? | Ownership |
|---|---|---|---|
| StrategicCouncil | market data + **news sentiment/articles** → TradingBrief DTO (action, entry, confidence, timeframe, RR) | YES — replace/augment sentiment lines with Core IO facts/events | TRADING |
| SmartExecutor | Brief → risk-checked order flow (news risk gate, UnifiedRisk V219, dynamic sizing, cross-pair correlation, journal) | YES (gate inputs) | TRADING |
| AutonomousTrader (+RL) | market analyzer, multi-TF, signal evaluator/quality classifier, adaptive strategy selector, A/B, OANDA executor | partially (macro context) | TRADING |
| Council-intelligence | sizing/correlation/journal | indirect | TRADING |
| Scanner/Engine | market-scanner cron | macro filters future | TRADING |
| Neural/Prediction-market/Lazic/Assistant/Coach | product analytics | no (now) | TRADING |
| Gemini/Groq/orchestrator | LLM providers | NO — Core never becomes an LLM dependency | TRADING |

## H. Execution Boundary (Core must NEVER own)

ExchangeCredential (user broker keys) · Orders/OrderEvent/Positions/Trades/TradeLifecycleLog/PositionReconciliation · PaperOrder · BullMQ order queue + algo-execution + connection-resilience · adapters (binance/oanda/mt5/alpaca/paper) · stop-loss/take-profit (TIMEFRAME_RR) · margin/leverage usage · AutonomousTrade/TradingBot/EAToken switches. **All TRADING-OWNED — untouched.**

## I. Database Ownership (47 models — no changes)

- **TRADING-OWNED (≈45):** User/Account/Session/ApiKey/AuditLog, Portfolio/PortfolioAsset, Signal/SignalUsage, ExchangeCredential, Order/OrderEvent/Position/Trade (+logs/reconciliation), PaperOrder, Challenge, StrategyReport, TradingBot, CoachAdvice, ChartPreference, Subscription, AiUsageLog, Notification*, Alert*, AdminSession/Setting/VerificationToken, EAToken, PredictionEvent, AutonomousTrade, AgentSession/Settings, ContentArticle/ContentSchedule, TradingBrief, TradeJournal, CouncilVoteAccuracy, MarketRegimeSnapshot, CrossPairCorrelation, RiskEvent.
- **CORE-CANDIDATE (read-side only, future):** NewsArticle (official lane would become Core-IO references + cached editorial fields), TradingBrief.news-context fields (become io_id references). No schema edits now.

## J. API Boundary

NestJS controllers across 21 modules (ai, analytics, assistant, coach, ea-bridge, engine, exchange, execution, integration, maintenance, neural, news, notification, portfolio, prediction-market, scanner, signal, trading, auth, audit). Classification: market-data/execution/portfolio/analysis/scanner/AI = **TRADING API**; news controllers = **CORE CONSUMER (future)**; shared brief/order DTOs = **SHARED CONTRACT**; scratch/legacy scripts = LEGACY. No changes.

## K. Realtime

Socket.IO + Redis adapter; channels: exchange stream, notifications, MT5 streaming. **Core intelligence arrival mode: UNDECIDED** (poll / stream / API / webhook / queue) — deliberately not designed here; note Redis pub/sub already exists as a natural candidate but no decision made.

## L. Queues / Schedulers

BullMQ: order-queue processor (execution), algo-execution workers. Cron: council cycles, scanner/engine, analytics tracker, content agents, autonomous-trader ticks. Principle ratified: **Trading scheduling/execution stays Trading-owned; Core publishes canonical intelligence independently** — no queue migration.

## M. Temporal Model

Trading timestamps today: naive `DateTime` (Order.createdAt, Trade.timestamp, NewsArticle.publishedAt/fetchedAt), provider timestamps raw, TradingBrief timeframes (M1…). No timezone semantics anywhere. **Core D4 tuples (publication semantics + tz-safe normalized_utc) become the trustworthy ordering layer** Trading should consume for official events; Trading keeps its own execution/order timestamps untouched. No new rules created.

## N. Failure Isolation

Existing: connection-resilience (execution), free-fallback adapter (market data), Redis-adapter graceful fallback (latest commit), BullMQ retries. **Not present:** Core-intelligence failure path (no Core yet). Rule to adopt at integration (directive §14): Core unavailability must NOT halt trading unless a strategy/risk rule explicitly declares the dependency; council prompts degrade to market-data-only mode (same pattern as today's news-bridge failures).

## O. Risk Boundary (actual current architecture — documented, not assumed)

Today, **news sentiment DOES influence execution**: SmartExecutor runs a **news risk gate** (explicitly logged: "with news risk gate") and Council prompts embed sentiment — i.e., externally-sourced AI sentiment can suppress/shape order flow. Core IOs will REPLACE that input with evidence-backed facts, but per the intended rule: **Core provides evidence-backed intelligence; Trading decides whether and how it is used** — the gate remains a Trading-owned policy into which Core evidence flows. Core never generates orders, alters risk, or changes positions.

## P. News Dependency (architecture risk — documented)

**YES — direct dependency exists:** `NewsIntegrationService` polls rouatradingnews (fearGreed/arabSentiment/geopoliticalRisk + aiSummary → Redis 15-min TTL) consumed by Council + Executor; Python content/sentiment agents also connect to rouatradingnews; plus Trading's OWN NewsArticle lane (CT/CD/CryptoPanic). So BOTH paths already coexist:
`News article → Trading input` (bridge) **and** independent press ingestion — a third intelligence duplication layer besides News's own. Future canonical: `Official Source → Core → IO → {News editorial; Trading gate}` with press lane optional per product.

## Q. 1500+ Source Strategy

Never imported into Trading. `1500+ sources → Core → relevant IOs → Trading relevance filter (asset linkage, jurisdiction, event type, market session, portfolio exposure, strategy subscription) → trading systems`. Filtering happens IN Trading (its models: CrossPairCorrelation, MarketRegime, portfolio exposure); Core stays source-complete, product-agnostic.

## R. Core → Trading Data Contract (requirements)

IO with: identity (io_id/version) · event type+version · facts (metric/value/unit) · verified institution · temporal tuple (publication, tz-safe) · evidence excerpt+location · representation sha256 + canonical_url · provenance chain ref. **MISSING today in Core (mark honestly):** affected-assets/entity mapping (Core has none — directive §19: do not invent; Trading maps assets itself via its own linkage), confidence/quality metadata beyond pipeline state, and any streaming/webhook transport. Version = D2 lineage (corrections = new versions).

## S. Migration Risks

1. Sentiment-gate semantics change (heuristic news → evidence-backed facts) alters council/executor behavior — needs shadow-mode A/B (StrategyReport/A-B infra exists).
2. Direct rouatradingnews coupling (env NEWS_SITE_URL/API_KEY/ADMIN_SECRET) — replace with Core consumer behind flag; keep bridge as fallback during transition.
3. Naive timestamps everywhere — correlation of official events vs market candles requires D4 adoption at the seam only.
4. Redis caching layer (15-min TTL) delays intelligence — decide freshness SLA per event type.
5. Third duplication layer (Trading's own NewsArticle lane) — dedupe strategy vs Core/News lanes.
6. AutonomousTrader autonomy + RL must never receive un-vetted auto-ingested intelligence without the explicit dependency rule (§N/O).
7. 47-model schema sensitivity — additive-only references (io_id columns) later, no rewrites.

## T. Recommended Integration Sequence (after Cross-Product Architecture)

1. Core staging (Gates G→H) with CORE API (health/IO-feed/trace). 2. Trading adds read-only Core consumer behind flag; council prompts gain an "official intelligence" section (shadow, logged, no execution effect). 3. News risk gate input switches from sentiment-only to sentiment+Core-evidence (A/B via existing strategy testing). 4. io_id references stored on briefs/trades (additive). 5. rouatradingnews bridge retired to fallback → removed later. 6. Trading-local press lane (CT/CD/CryptoPanic) remains or migrates by decision. 7. Freshness/SLA + failure-mode policy formalized.

## U. Unresolved Questions

1. Permanent home of this document (none modified per directive). 2. Core→Trading transport (poll/stream/webhook/queue). 3. Affected-asset mapping ownership (Core extension vs Trading-side mapping table). 4. Freshness SLA per event type (rate decisions vs statistical releases). 5. Whether Trading's press lane collapses into News or stays. 6. Corporate discovery still pending before the Cross-Product Architecture. 7. Core API auth for product consumers.

---

## Critical Questions (§20 — from actual code)

1. **Intelligence today:** CryptoPanic + CT/CD RSS (own lane) + rouatradingnews sentiment bridge (fearGreed/arabSentiment/geopolitical) → Redis → Council/Executor prompts & news risk gate. No direct official-source ingestion.
2. **Move to Core:** official-source acquisition/classification/provenance for the intelligence Trading consumes (as IO feed + trace); the sentiment INDICES themselves remain product-side editorial analytics unless later decided otherwise.
3. **Remain Trading:** everything in §H/§I — execution, market data, risk, strategies, accounts, realtime.
4. **News dependency:** YES, direct (§P) — documented as architecture risk.
5. **Affecting Trading:** rate decisions, statistical releases, regulatory enforcement, sanctions, earnings (mapped to Trading assets), market-statistic releases — all 6 Core types RELEVANT but only via Trading-side filters; not every IO affects trading.
6. **Latency:** market data = realtime (WS); news bridge = 15-min TTL today; official intelligence = event-driven — Core feed must beat/track that; exact SLA = open (§U.4).
7. **Persisted Core identifiers:** io_id + version (+ trace ref) on TradingBrief/news-context and (later) trades influenced by them — additive columns.
8. **Corrections:** Core D2 → new IO version → Trading consumer re-evaluates open briefs/positions per its OWN policy (gate re-run), never silent mutation.
9. **Core unavailable:** degrade to current behavior (market-data + local press/sentiment); trading continues (§N rule).
10. **Safe without new Core intelligence:** YES — that is today's mode; Core adds evidence depth, never a hard runtime dependency unless Trading declares one.

**STOP per §23 — no cross-product architecture created yet. Next phase: CROSS-PRODUCT CORE INTEGRATION ARCHITECTURE (Core ├ News ├ Trading └ Corporate) after the Corporate pass.**
