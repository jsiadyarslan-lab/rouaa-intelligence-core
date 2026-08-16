# ROUAA CORPORATE — CORE INTEGRATION DISCOVERY V1

**Status:** READ-ONLY DISCOVERY (local deliverable only — no commits, no modifications, per directive §20/§21)
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — ROUAA CORPORATE CORE INTEGRATION DISCOVERY V1 (user-issued verbatim)
**Discovered object:** `jsiadyarslan-lab/rouaa-corporate` @ **main** `0d71f6161dc759687c83c90f3968262d80b95cbf` (2026-08-12 "docs: Vertical Slice Architecture & Runtime Audit — entry point identified")
**Note:** inspected `main` directly — NOT the `top20-prescreening` workstream branch, NOT old summaries. **main does NOT contain the Core or the evidence corpus** (those live on the branch / in repo4).

---

## A. Repository Baseline

| Item | Finding |
|---|---|
| Commit | `0d71f61` (main) |
| Structure | 33 root HTML pages (corporate site) · `rouaa-web/` (31 HTML + audit docs — parallel variant) · `mvp/` (NestJS backend + FastAPI intelligence + Vite web + docker-compose + postgres-init) · `docs/` (**67 foundation + 10 execution** docs) · `archive/` (legacy v19 site) · `assets/`, `design-system/` |
| Runtime | **fully STATIC website** — `main.js` = 116 lines (nav/UX only), **ZERO fetch()/API calls**, no runtime data of any kind |
| Backend | only inside `mvp/` (scaffolding: health + sources CRUD + more; FastAPI intelligence service) — **not deployed as the corporate site** |
| Databases | mvp: Postgres via docker-compose + seed data (not production) |
| Background jobs | none on main |
| Source ingestion | none on main |
| AI services | none in runtime; Python scripts (`update_pages.py`, `apply_hero_design*.py`, `cleanup_hero.py`) = **website content automation (marketing tooling)** |
| Documentation | 15 root *.md positioning docs + docs/foundation 67 + docs/execution 10 (incl. approved messaging blueprints 06–08) |
| Deployment | no Railway/vercel refs; Docker only within mvp infra; static hosting implied |
| Security (public repo) | tree scan **CLEAN** — no tokens/keys/credentials → **no SECURITY BLOCK** |

## B. Corporate Role (classification)

`CORPORATE WEBSITE` (33 pages + rouaa-web variant) — the dominant role · `MARKETING/PRESENTATION` (positioning, blueprints, pricing, proof-assets) · `DOCUMENTATION` (foundation/execution corpora) · `CORPORATE PLATFORM` — **none in runtime** (mvp scaffolding only, EXPERIMENT/LEGACY-adjacent) · `CORE CANDIDATE` — none (main predates the Core; the validated lineage lives elsewhere) · `PRODUCT LOGIC` — none. **Corporate today = static marketing + documentation; NOT a data system.**

## C. Data / Intelligence Consumption

Every "data point" on the site is **STATIC CONTENT** in HTML: "411+" sources counters (`data-v="411"` animated ×2 + narrative uses across business-case/catalog/architecture/design-reference/developer-intelligence/evidence-explorer), product counts (4 products, 7 layers, 6 …), narrative "facts/documents/evidence" phrases. **No RUNTIME DATA exists; no fetch calls; therefore nothing is currently product-derived or core-derived.** All quantitative claims classify: `STATIC MARKETING CLAIM` (with "411+" interestingly matching the News repo's 411-source global file — a **manually synchronized cross-repo claim**, the only real coupling of metrics today).

## D. Source / Intelligence Registries

- `source-registry.html`, `source-explorer.html`, `evidence-explorer.html`, `infrastructure-report.html` = **static explanatory pages** (0 external source URLs embedded in source-explorer — conceptual illustrations, not registry copies).
- **The real duplication:** `mvp/backend/src/config/seed-data.ts` — a **seeded Source Registry** (~72 code/name entries: FED, ECB, BOE, BOJ, PBOC, SNB, BOC, RBA, MAS, BIS, …) with full CRUD REST (`/api/v1/sources`, stats endpoint, soft-delete) + Postgres schema. Unvalidated scaffolding, but architecturally a **competing Source Registry** → `MUST DELEGATE TO CORE` (when/ if mvp is ever activated; otherwise retire with mvp).
- Intelligence taxonomy/lists: foundation docs describe taxonomies (DOCUMENTATION, not registries).

## E. Architecture / Corporate Pages

architecture.html, platform.html, methodology.html, trust-framework.html, evidence-explorer.html, infrastructure-report.html, developers/developer-intelligence, products/solutions/catalog, why-roua, news.html, trading-platform.html (30 pages link to it), financial-intelligence… — all **static narratives**. Classification: architecture explanations = STATIC DOCUMENTATION (must track the Core's real architecture — currently describe the pre-Core design); evidence/provenance showcases = illustrative, **SHOULD EVENTUALLY BE CORE-DERIVED** (live counts, real examples); source-coverage claims = STATIC MARKETING CLAIM → `SHOULD EVENTUALLY BE CORE-DERIVED`; product/platform capabilities = marketing narrative (kept). **Corporate must never invent system state** — ratified: today it invents nothing dynamically, but its static numbers (411+) will drift from Core truth unless fed.

## F. Data Model / API

Only mvp/: Sources CRUD (+entities) = **CORE-CANDIDATE duplicates** (D registry above); everything else (none live) — Corporate-owned data would be (future): leads, briefing requests, contacts, CMS content, analytics — **none exist today** (no backend for the site itself).

## G. AI / Automation

Python page-update/design-application scripts = `MARKETING` (website content generation tooling). No source analysis / research / intelligence synthesis / metrics generation exists. Nothing to classify CORE/PRODUCT.

## H. Evidence / Provenance

Corporate displays **no real evidence** — illustrative mockups/flows only; no source URLs, no verification statuses, no live counts. Historical evidence dependence: none directly (the evidence corpus lives on the workstream branch + repo4, not main). Everything evidence-ish should eventually be **runtime-backed from Core** (counts, verified examples, trace demos).

## I. Corporate vs Core Boundary

Corporate MUST own: positioning, institutional messaging, product/solution presentation, architecture *explanation*, lead/briefing workflows (when built), docs presentation, branding. Core MUST own: canonical source truth, intelligence, evidence, provenance, source health, verified metrics, runtime system truth. **Overlaps found:** (1) "411+" source-count claims (Core-derived later), (2) mvp seeded registry (duplicate registry — delegate/retire), (3) architecture docs describing the platform (must be updated to describe Core-based reality — content task, not ownership).

## J. Runtime Metrics

All enumerated: "411+ sources" (×~6 pages incl. animated counters) · "4 intelligence products" · "7 layers" · 6 (layers/whatever) · narrative "10K+/1,247/219-style" numbers do **not** appear on main (only the old plan mentioned them). Classification: every one = `STATIC MARKETING CLAIM`; "411+" specifically = `SHOULD EVENTUALLY BE CORE-DERIVED` (verified source count). No live metrics manufactured now (directive honored).

## K. Corporate Consumption Contract (future)

From Core, read-only, pre-approved aggregates: verified-source coverage (count by jurisdiction/class — replacing "411+"), verified intelligence statistics (IOs/events by type), source-health summary, evidence/provenance demonstration objects (a curated public trace example), platform capability/architecture status, developer-API metadata. Exposure classes: counts/coverage = **PUBLIC**; health detail & examples = **AUTHENTICATED** (internal dashboard) or curated-public; raw IO feed = **INTERNAL ONLY** (products, not the website).

## L. News / Trading Relationship

No direct consumption of rouatradingnews or roua-trading (no fetches/APIs). Coupling is presentational only: news.html + trading-platform.html market the products (30 internal links to trading-platform). Shared deployment/services: none. Duplicated metrics: "411+" shared manually with News's 411-source file (drift risk). **No circular dependencies; Corporate is not an upstream of anything today — the correct direction.**

## M. 1500+ Source Strategy

Corporate never ingests sources. `1500+ sources → Core → verified coverage/intelligence aggregates → approved read-only contract → Corporate` presents system truth without owning it. What Corporate actually needs: a handful of verified aggregate numbers + 1–3 curated evidence demos — not source-level data.

## N. Deployment / Operations

Corporate runtime = static hosting (no config found — no Railway/vercel files on main). mvp docker-compose = experiment infra only. Boundary: Corporate static hosting stays; Core production = repo4 staging (Gate G/H track). Nothing to split today.

## O. Security

Public-repo scan of main tree: **CLEAN** (tokens/keys/credentials/private endpoints: none). No `CORPORATE PUBLIC REPOSITORY SECURITY BLOCK`. (History depth-3 scanned; full-history scan advisable if ever in doubt, current HEAD clean.)

## P. Cross-Product Duplication

| Item | Class |
|---|---|
| "411+" source-count claims (Corporate + News's 411-file) | `MUST DELEGATE TO CORE` (become Core-verified counts) |
| mvp seeded Source Registry + CRUD | `MUST DELEGATE TO CORE` (or retire with mvp) |
| Architecture/platform narratives | `STATIC DOCUMENTATION` (update to Core reality — editorial task) |
| Evidence/provenance showcases | `REQUIRES FUTURE DECISION` (curated public demos vs internal-only) |
| Positioning/branding/products/pricing/docs | `MUST REMAIN CORPORATE` |

## Q. Integration Risks

1. **Metric drift** — static "411+" silently diverges from Core truth (already two manual copies: Corporate pages + News data file).
2. **mvp reactivation trap** — the scaffolding's registry/API could be mistaken for the Core path (must be explicitly retired or bound to Core).
3. **Docs-vs-reality gap** — 67 foundation docs describe the pre-Core architecture; risk of marketing claims outrunning validated capability (governance: claims must cite Core-verified numbers post-integration).
4. rouaa-web parallel variant (31 pages) — duplication of the corporate surface itself (a product decision, pre-existing).
5. Evidence demos: exposing real traces publicly must scrub any sensitive destination data (none today; Contract-C objects are internal test destinations — fine).

## R. Recommended Integration Sequence (post Cross-Product Architecture)

1. Cross-Product Architecture ratifies the Corporate read-only contract (K). 2. Core staging exposes `/public/coverage` style aggregate (part of CORE API, cached). 3. Corporate replaces hardcoded "411+" with the aggregate + graceful static fallback. 4. Curated evidence demo page fed by a real trace (authenticated/cached). 5. mvp registry explicitly retired (README pointer to Core) or rebuilt as Core client. 6. Architecture docs updated to the Core-based reality (editorial).

## S. Unresolved Questions

1. Permanent home for this + the News/Trading discovery docs (all local-only now). 2. Which aggregates are public vs authenticated (K needs product decision). 3. rouaa-web vs root-site consolidation (pre-existing). 4. mvp fate (retire vs rebuild as Core consumer). 5. Whether Corporate ever needs product-status dashboards (live News/Trading health) — REQUIRES FUTURE DECISION. 6. Evidence-demo curation policy. 7. Cross-Product Architecture authorship timing (next phase, after this discovery).

---

## Current-State Diagram

```text
ROUAA Corporate (main @ 0d71f61)
├── 33 static HTML pages (+ rouaa-web 31-page variant)  [marketing/docs, ZERO runtime data]
├── docs/ (67 foundation + 10 execution)                [documentation corpus]
├── mvp/ (NestJS+FastAPI scaffolding, seeded 72-source registry CRUD) [EXPERIMENT — not live]
└── archive/ (legacy v19)
   (no backend, no jobs, no ingestion, no AI runtime; "411+" claims hardcoded,
    manually synchronized with News's data/sources 411-file)
```

## Target-State Conceptual Diagram

```text
              ROUAA Intelligence Core
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
      News          Trading       Corporate
   (editorial)   (execution)   (presentation:
                                 verified aggregates,
                                 curated evidence demos,
                                 read-only contract)
```

## Critical Questions (§18 — from actual code)

1. **Consumes from News?** Nothing (no fetches). Only a manually-synced "411" number origin and product-marketing links.
2. **From Trading?** Nothing (trading-platform.html is marketing).
3. **Directly from Core (future)?** Verified coverage counts, verified intelligence stats, source-health summary, curated evidence/trace demos, architecture/API metadata — via a read-only approved contract.
4. **Runtime-derived metrics:** "411+" sources (→ Core verified count); later stats/health if approved.
5. **Static marketing forever:** positioning, product/solution narratives, pricing, brand, layer/product counts as design language.
6. **Never public:** raw IO feeds, trace details of non-curated objects, internal health detail, destinations/audit internals.
7. **Canonical intelligence data today?** NONE (main has no intelligence data; the validated Core lives in repo4).
8. **Duplicate registries to disappear:** the mvp seeded registry (+CRUD); the "411+" manual copies (Corporate + News) become Core-derived.
9. **Evidence/provenance examples:** eventually real, Core-fed (curated Contract-B traces), not mockups.
10. **Minimal Corporate→Core contract:** `GET verified coverage aggregate (+ optionally 1 curated demo trace)` — one read-only endpoint, cached, with static fallback.

**STOP per §21 — document local-only, not committed; Cross-Product Architecture NOT started. Next phase: CROSS-PRODUCT CORE INTEGRATION ARCHITECTURE V1 (1500+ sources → Core → canonical intelligence → News / Trading / Corporate).**
