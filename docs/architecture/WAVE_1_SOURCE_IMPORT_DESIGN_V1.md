# Wave-1 Source Import Design V1

**Status:** WAVE-1 IMPORT DESIGN READY
**Date:** 2026-08-17
**Authoritative state:**
- Core repository: `743c3bf`
- Cross-Product Architecture: `e0964f5`
- Integration Plan: `5deb05f`
- Official Wire implementation: `6018568` + `b0985d2`
- Live validation correction: `67f5313`
- Equivalence validation: `8c1751c`

This task is **design + import preparation only**. No activation. No cutover. No Railway.

---

## 1. Input File

| Field | Value |
|-------|-------|
| File name | `rouatradingnews/data/sources/global-official-sources-v1.json` |
| SHA256 (first 32) | `1ccc6299952949aee44c71fee451db5d` |
| Row count | 411 |
| Schema fields | `name, slug, type, country, countryCode, region, website, language, updateFrequency, authorityScore, shortName, relatedAssets` |
| Duplicate count | 0 (each slug is unique) |
| Missing required fields | 0 |
| Malformed entries | 0 |

**Note:** The file contains 411 official financial sources (not 1500+). The user's "1500+" likely refers to the total RSS feed count in `news-sources.ts` (602 feeds, many non-official). The 411 records in `global-official-sources-v1.json` are the authoritative official-source universe. This file was NOT modified.

### Cross-reference

The same 411 sources appear in `source-metadata-registry.json` with wave assignments and operational metadata. 100% overlap confirmed (411 slugs match exactly).

### Duplicate detection (name-level)

128 duplicate names exist across waves — these are NOT true duplicates. They represent the same institution appearing in both the global file AND the wave-specific files (e.g., "Federal Reserve" appears in both `global-official-sources-v1.json` and `wave-1-central-banks.json`). The slug field is unique and is the canonical identifier.

---

## 2. Import Lifecycle

```text
IMPORTED
    ↓
DISCOVERED
    ↓
ENTITY REVIEW (hostname → institution → legal entity → jurisdiction → class)
    ↓
PATH REVIEW (content-path qualification)
    ↓
CONFIGURATION REVIEW (event_type + trigger_metrics + content_keywords)
    ↓
QUALIFIED
    ↓
READY FOR ACTIVATION
    ↓
ACTIVE
```

**Explicit rule:** Presence in the source file does NOT mean the source is active. A source is `ACTIVE` only when all lifecycle stages pass and activation is explicitly approved.

---

## 3. Source Normalization

Each input record is normalized into a staging representation with these fields:

| Field | Source | Verified? |
|-------|--------|-----------|
| import_id | Generated (`imp-<slug>`) | N/A |
| institution_name | Input `name` | Declared — NOT verified |
| jurisdiction | Input `country` / `countryCode` | Declared — NOT verified |
| institutional_class | Input `type` (mapped to B1-B9) | Declared — NOT verified |
| primary_domain | Input `website` (domain extracted) | Declared — NOT verified |
| candidate_paths | None in input (discovered during qualification) | N/A |
| source_description | None in input | N/A |
| declared_intelligence_types | None in input (inferred from class during qualification) | N/A |
| declared_priority | Input `authorityScore` (0-100) | Declared — NOT verified |
| source_language | Input `language` | Declared — NOT verified |
| input_row_reference | Array index in source file | N/A |

**Rule:** Every imported field remains distinguishable from Core-verified metadata. Declared fields are prefixed `declared_` until verified through the qualification lifecycle.

---

## 4. Duplicate / Identity Check

### Detection rules

1. **Duplicate institutions**: same legal entity name + same jurisdiction
2. **Duplicate domains**: same hostname (with/without `www.`)
3. **Aliases**: multiple names for the same institution (e.g., "Fed" vs "Federal Reserve")
4. **Subdomains**: different subdomains of the same parent domain
5. **Multiple source paths**: one institution with multiple feed URLs

### Resolution

Identity is resolved through:
```text
hostname → institution → legal entity → jurisdiction → institutional class
```

**The `bmf.de` lesson remains mandatory:** `bmf.de` was initially assumed to be the German Ministry of Finance (Bundesministerium der Finanzen) but entity resolution proved it is Bürener Maschinenfabrik GmbH. Hostname does NOT determine entity — entity verification is required.

---

## 5. Source Classification

Classification uses the existing canonical institutional classes from Global Source Universe V1:

| Input `type` | Maps to | B-class |
|--------------|---------|---------|
| `central_bank` | Central Banks | B1 |
| `regulator` | Financial Regulators | B2 |
| `statistics` | Statistical Agencies | B3 |
| `ministry` | Ministries of Finance | B4 |
| `exchange` | Market Infrastructure | B5 |
| `energy` / `commodity` | Public/Sovereign (energy/commodity) | B6 |
| `intl_org` | Multilateral | B7 |
| `rating` | Disclosure Systems (rating agencies) | B8 |
| `other` | Other Authoritative | B9 |

Unknown types are classified `UNRESOLVED` — NOT guessed.

---

## 6. Wave-1 Selection Policy

### Deterministic selection (seed = 20260817)

Wave 1 is NOT the first N rows. Selection maximizes:
- Architectural diversity (different adapter types: RSS, HTML, API)
- Institutional diversity (central banks, regulators, statistics, etc.)
- Geographic diversity (US, UK, EU, Japan, China, Middle East, etc.)
- Intelligence-type diversity (monetary policy, statistical, enforcement, etc.)
- Known validation confidence (sources already validated in Core Phase 2)
- Product relevance (News/Trading/Corporate)

while minimizing:
- Duplicate patterns
- Known inaccessible sources (MINISTRY 403, OBR 403)
- Speculative source assignments

### Proportional allocation

| Type | Pool size | Wave-1 allocation | Rationale |
|------|-----------|-------------------|----------|
| central_bank | 54 | 6 | Core intelligence type; highest authority |
| regulator | 78 | 5 | Enforcement intelligence; regulatory coverage |
| statistics | 40 | 4 | Statistical release intelligence |
| ministry | 47 | 4 | Fiscal policy candidates |
| exchange | 65 | 3 | Market infrastructure; browser-rendering test candidates |
| energy | 53 | 3 | Commodity intelligence |
| intl_org | 40 | 3 | Financial coordination candidates |
| rating | 20 | 2 | Rating/credit intelligence |
| other | 8 | 0 | Low priority for Wave 1 |
| commodity | 6 | 0 | Low priority for Wave 1 |
| **Total** | **411** | **30** | |

### Within-type selection

For each type:
1. Sort by `authorityScore` descending
2. First pass: select highest-authority source from each unique country
3. Second pass: fill remaining slots from highest-authority sources (allowing country overlap)

---

## 7. Wave-1 Shape

**Target: 30 sources** (within 25-40 range).

### Wave-1 Distribution by Type

| Type | Count |
|------|-------|
| central_bank | 6 |
| regulator | 5 |
| statistics | 4 |
| ministry | 4 |
| exchange | 3 |
| energy | 3 |
| intl_org | 3 |
| rating | 2 |
| **Total** | **30** |

### Wave-1 Distribution by Region

| Region | Count |
|--------|-------|
| Europe | 11 |
| North America | 8 |
| Asia-Pacific | 6 |
| Global | 4 |
| Middle East | 1 |
| **Total** | **30** |

### Wave-1 Distribution by Country

| Country | Count |
|---------|-------|
| USA | 7 |
| UK | 5 |
| Japan | 5 |
| Global | 4 |
| EU | 3 |
| Germany | 3 |
| China | 1 |
| Saudi Arabia | 1 |
| Canada | 1 |

### Wave-1 Sources (30)

| # | Type | Name | Country |
|---|------|------|--------|
| 1 | central_bank | Federal Reserve | USA |
| 2 | central_bank | European Central Bank | EU |
| 3 | central_bank | Bank of England | UK |
| 4 | central_bank | Bank of Japan | Japan |
| 5 | central_bank | Deutsche Bundesbank | Germany |
| 6 | central_bank | People's Bank of China | China |
| 7 | regulator | US SEC | USA |
| 8 | regulator | FCA | UK |
| 9 | regulator | ESMA | EU |
| 10 | regulator | Financial Services Agency | Japan |
| 11 | regulator | BaFin | Germany |
| 12 | statistics | US Bureau of Labor Statistics | USA |
| 13 | statistics | UK ONS | UK |
| 14 | statistics | Eurostat | EU |
| 15 | statistics | Statistics Japan | Japan |
| 16 | ministry | US Treasury | USA |
| 17 | ministry | HM Treasury | UK |
| 18 | ministry | German Federal Ministry of Finance | Germany |
| 19 | ministry | Japanese Ministry of Finance | Japan |
| 20 | exchange | NYSE | USA |
| 21 | exchange | LSE | UK |
| 22 | exchange | Japan Exchange Group | Japan |
| 23 | energy | US EIA | USA |
| 24 | energy | Saudi Aramco | Saudi Arabia |
| 25 | energy | IRENA | Global |
| 26 | intl_org | IMF | Global |
| 27 | intl_org | World Bank | Global |
| 28 | intl_org | BIS | Global |
| 29 | rating | S&P Global Ratings | USA |
| 30 | rating | DBRS Morningstar | Canada |

---

## 8. Geographic Diversity

Wave 1 covers: US, UK, EU, Japan, Germany, China, Saudi Arabia, Canada, Global.

**Not represented in Wave 1:** Australia/NZ, emerging markets (Brazil, India, Mexico, etc.). These are deferred to Wave 2.

---

## 9. Intelligence-Type Diversity

| Intelligence type | Wave-1 sources | Status |
|-------------------|----------------|--------|
| monetary_policy | 6 central banks | Supported (event_type exists) |
| statistical_release | 4 statistics agencies | Supported |
| regulatory_enforcement | 5 regulators | Supported |
| fiscal_policy candidates | 4 ministries | NOT supported (no event type yet — Capability 6) |
| financial_coordination candidates | 3 intl orgs | NOT supported (no event type yet — Capability 6) |
| market_structure candidates | 3 exchanges | NOT supported (no event type yet — Capability 6) |
| energy/commodity | 3 energy + 2 rating | NOT supported (no event type yet) |

Unsupported types are labeled, NOT forced into existing event types.

---

## 10. Product Relevance Annotation

| Product | Relevant Wave-1 sources | Notes |
|---------|------------------------|-------|
| News | All 30 | All produce official intelligence suitable for editorial transformation |
| Trading | 6 central banks + 4 statistics + 3 exchanges | Rate decisions, statistical releases, market data |
| Corporate | All 30 (reference) | Coverage/demo value for institutional clients |

No commercial demand inferred. Internal product strategy only.

---

## 11. Qualification Gate

Every Wave-1 source must pass the existing qualification methodology:

```text
Gate 1 — Access (HTTP probe)
Gate 2 — Provenance (date metadata)
Gate 3 — Content (substantive content check)
Gate 4 — Pattern Category Applicability
Content-Path Alignment
Configuration Contract Verification
Semantic Representation Assessment
QUALIFICATION_READY → Gate 5 (where applicable)
```

The frozen v2 qualification methodology (`bda3ffb` / `e48281a`) is NOT modified. No exceptions.

---

## 12. Configuration Authoring

After qualification, source configurations are created. Separation:

| Configuration type | Description | Status |
|---------------------|-------------|--------|
| Verified configuration | Created after qualification passes; patterns tested against real content | Active |
| Candidate configuration | Created before qualification; patterns NOT tested | Staging only |

Speculative regexes do NOT enter Active configuration. Pattern-specificity remains attributable to the source.

---

## 13. Activation

A source becomes `ACTIVE` only when:

```text
Entity verified (hostname → institution → legal entity)
+ Content path aligned (v2 Content-Path Alignment)
+ Configuration compatible (v2 Configuration Contract Verification)
+ Semantic representation compatible (v2 Semantic Representation)
+ Qualification passed
+ Activation explicitly approved
```

Activation creates:
- Source health state (healthy/degraded/blocked)
- Monitoring policy (per-source)
- Configuration version
- Activation timestamp
- Evidence reference (qualification commit)

---

## 14. Monitoring Policy

Per-source monitoring fields:

| Field | Description |
|-------|-------------|
| Polling frequency | Daily for most; real-time for breaking; weekly for low-priority |
| Retrieval timeout | 15-30 seconds (varies by source response time) |
| Retry policy | 3 retries with exponential backoff |
| Expected content type | RSS XML, HTML, or PDF |
| Expected intelligence type | Event type configured for this source |
| Health threshold | 3 consecutive failures → degraded; 10 → blocked |
| Failure alerting | Logged to audit; no email/SMS in Wave 1 |
| Inactive condition | Blocked status → source monitoring paused |

Not every source runs at identical frequency.

---

## 15. Product Routing

After activation:

```text
Source → Core (acquire → normalize → extract → detect → evidence → IO)
    ↓
IntelligenceObject
    ↓
Product Routing
    ├── News (Official Intelligence Wire) — Pipeline B
    ├── Trading (future — NOT connected in Wave 1)
    └── Corporate (future — NOT connected in Wave 1)
```

Only News is connected in Wave 1. Trading and Corporate are NOT connected.

---

## 16. Data Quality Metrics

Wave 1 is measured using actual operational metrics:

| Metric | What it measures |
|--------|------------------|
| Sources imported | Count entering the lifecycle |
| Sources entity-verified | Count passing entity resolution |
| Sources qualified | Count passing all v2 stages |
| Sources rejected | Count failing at any stage |
| Sources inconclusive | Count with insufficient evidence |
| Sources activated | Count reaching ACTIVE state |
| Documents fetched | Count of documents acquired |
| Facts extracted | Count of structured facts |
| Events detected | Count of financial events |
| IntelligenceObjects generated | Count of canonical IOs |
| Evidence records | Count of evidence chains |
| Provenance verification | Count of verified provenance chains |
| Source failures | Count of sources that failed |

These are NOT turned into universe prevalence claims.

---

## 17. Source-Level Failure Taxonomy

Each rejected/inconclusive source receives one primary classification:

| Classification | Meaning |
|----------------|---------|
| ENTITY | Entity resolution failed (hostname → institution mismatch) |
| ACCESS | HTTP 403, timeout, or connection refused |
| CONTENT-PATH | Selected path does not contain expected intelligence type |
| CONFIGURATION | event_type or trigger_metrics incompatible |
| SEMANTIC-REPRESENTATION | No semantically compatible event type exists |
| PATTERN-SPECIFICITY | Content present, patterns do not match phrasing |
| PROVENANCE | Date metadata unavailable or unparseable |
| IMPLEMENTATION | Pipeline/engineering issue (not source-specific) |
| UNKNOWN | Cause not determined |

Failures are NOT collapsed into "0 facts."

---

## 18. 1500+ Roll-Out Architecture

Long-term process:

```text
1500+ Import Registry (411 sources)
    ↓
Wave Selection (deterministic, documented policy)
    ↓
Qualification (v2 methodology, no exceptions)
    ↓
Configuration (verified vs candidate separation)
    ↓
Activation (explicit approval per source)
    ↓
Monitoring (per-source policy)
    ↓
Intelligence Production (Core pipeline)
    ↓
Product Routing (News → Pipeline B; Trading/Corporate → future)
```

Each future wave is independently measurable and reversible.

---

## 19. News Consumption

For Wave 1:
- Pipeline B consumes only Core's verified IntelligenceObjects
- Pipeline A (Global News Aggregation) remains unchanged
- Raw source documents are NOT routed directly into Pipeline A

---

## 20. Cost / Capacity Estimation

No fake capacity numbers. Measurements needed before scaling:

| Measurement | How to obtain |
|-------------|---------------|
| Average source retrieval time | Measure during Wave-1 execution |
| Processing time per document | Measure during Wave-1 execution |
| Documents per source per day | Measure during Wave-1 monitoring |
| Storage growth | Track JSONL + blob sizes |
| Failed retrieval rate | Count failures / total attempts |
| Retry volume | Count retry events |
| IntelligenceObject yield | Count IOs / count documents |
| API polling volume | Count contract API requests |
| News candidate volume | Count StoryCandidates produced |

These measurements determine whether Wave 2 can scale.

---

## 21. Import Artifacts

### Design document

`docs/architecture/WAVE_1_SOURCE_IMPORT_DESIGN_V1.md` (this document)

### Manifest

`docs/evidence/WAVE_1_SOURCE_IMPORT_MANIFEST_V1.json`

The manifest includes:
- `import_id` per source
- Original row reference (array index)
- Normalized institution name
- Domain
- Class (B1-B9 mapping)
- Jurisdiction
- Selected wave (wave-1 or not)
- Verification state (`NOT_STARTED`)
- Qualification state (`NOT_STARTED`)
- Activation state (`NOT_STARTED`)

No secrets included.

---

## 22. No Activation in This Task

This task prepares:
- Normalized manifest (411 sources, 30 selected for Wave 1)
- Wave-1 selection (deterministic, documented)
- Candidate configurations (NOT verified — to be qualified)
- Import validator (schema check, duplicate detection, classification)

This task does NOT:
- Activate sources
- Import into production Core
- Connect News feeds
- Start Trading
- Start Corporate
- Deploy Railway

---

## 23. Final Verdict

```
WAVE-1 IMPORT DESIGN READY
```

Input file: 411 official sources (not 1500+ — the 1500+ likely refers to total RSS feeds including non-official). No input data issues detected.

---

## 24. Stop Condition

```
STOP
```

Do NOT:
- Activate sources
- Import into production Core
- Connect more News feeds
- Start Trading
- Start Corporate
- Deploy Railway
- Cut over News

Next phase:
```text
Wave-1 Import Execution
    ↓
Qualification
    ↓
Controlled Activation
    ↓
Official Intelligence Wire Production Test
```

Pipeline A remains independent throughout.
