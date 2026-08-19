# ROUAA Core Canonical Intelligence Contract V1

> Derived from V36 forensic audit of 9 real durable IntelligenceObjects.
> This contract defines what Core produces and what downstream systems consume.

## Core Owns

| Responsibility | Description |
|----------------|-------------|
| INTELLIGENCE GENERATION | Extraction of facts, evidence, events from official sources |
| PROVENANCE | Source → Document → Fact → Evidence → Event → IO chain |
| PERSISTENCE | Durable store, restart recovery, version lineage |
| DELIVERY | HTTP API, cursor pagination, concurrent readers |

## Downstream Owns

| Responsibility | Description |
|----------------|-------------|
| PRESENTATION | Editorial, visual, video, infographic rendering |
| WORKFLOW | News publication, trading execution, compliance case management |
| DECISION LOGIC | BUY/SELL, alerting rules, risk thresholds |
| EDITIALIZATION | Headline writing, story framing, language adaptation |
| VISUALIZATION | Charts, dashboards, reports |
| EXECUTION | Trade execution, alert dispatch, report generation |

## Canonical IO Payload

### Required Fields

| Section | Field | Type | Immutable | Versioned | Derived |
|---------|-------|------|:---------:|:---------:|:-------:|
| A. IDENTITY | io_id | string | ✓ | | |
| | version | integer | | ✓ | |
| | status | enum(ACTIVE\|SUPERSEDED) | | | ✓ |
| | event_id | string | ✓ | | |
| B. EVENT | event_type | enum | ✓ | | |
| | headline | string | | | ✓ |
| C. FACTS | facts[] | array | | | ✓ |
| | fact.metric | string | ✓ | | |
| | fact.value | string | ✓ | | |
| | fact.raw_value | string | ✓ | | |
| | fact.pattern_ref | string | ✓ | | |
| | fact.excerpt | string | ✓ | | |
| D. EVIDENCE | evidence[] | array | | | ✓ |
| | evidence.excerpt | string | ✓ | | |
| | evidence.provenance_ref | string | ✓ | | |
| F. PROVENANCE | chain[] | array | | | ✓ |
| | source_id | string | | | ✓ |
| | document_id | string | | | ✓ |
| G. VERSION | event_version | integer | | ✓ | |

### Optional Fields

| Section | Field | Type | Status |
|---------|-------|------|--------|
| E. TEMPORAL | temporal_data | object | None for 8/9 IOs |
| | publication_date | string | From document metadata |
| G. VERSION | supersedes_io_id | string | When superseded |

### Not Present (Future V37+)

| Section | Field | Gap Priority |
|---------|-------|:------------:|
| I. CONTEXT | entity | P1 |
| I. CONTEXT | unit | P2 |
| I. CONTEXT | period | P1 |
| H. QUALITY | quality_metadata | P2 |
| H. QUALITY | confidence_score | P2 |

## Boundary Rule

Core MUST NOT create:
- BUY / SELL / ENTRY / SL / TP / POSITION SIZE
- Editorial headlines (only generic source+type)
- Story narratives
- Risk assessments
- Compliance decisions

Core MUST provide:
- Structured facts with evidence
- Event classification
- Provenance chain
- Version lineage
- Durable persistence
- HTTP delivery
