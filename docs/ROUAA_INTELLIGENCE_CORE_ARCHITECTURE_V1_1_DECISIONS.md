# ROUAA INTELLIGENCE CORE ARCHITECTURE V1.1 — DECISION ADDENDUM

**Status:** FORMAL DECISION RECORD — resolves P0/P1 blockers from Architecture Review V1
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — ROUAA INTELLIGENCE CORE ARCHITECTURE CORRECTIONS V1.1 (user-issued verbatim)
**Resolves:** `ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_REVIEW_V1.md` @ `08d5723` (P0-1…P0-3, P1-1…P1-7)
**Revises:** `ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1.md` @ `a45bd07` (via `ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1_1.md`, this commit)
**Discipline:** Decision addendum + architecture corrections ONLY. No implementation, no Repository 4, no migration, no framework/library selection, no deployment, no frozen-artifact modification.

Decision IDs D1–D10 map to the review's blockers (D1–D3 = P0, D4–D10 = P1).

---

## D1 (P0-1) — DOCUMENT IDENTITY CONTRACT

**Decision.** Document identity is a **three-level model**; no single field is identity:

```text
Document (logical identity)
   ↓ has one-or-more
Document Representation (specific retrieved content)
   ↓ produced by
Retrieval Event (the act of acquisition)
```

**Fields (canonical contract):**

| Field | Level | Definition | Derivation |
|---|---|---|---|
| `document_id` | logical | stable identity across retrievals and content changes | `doc-<sha256(normalized_canonical_url)[:16]>` — deterministic, no central issuance |
| `representation_id` | representation | one specific retrieved content state | `rep-<sha256(document_id + content_sha256)[:16]>` — identical content re-fetched ⇒ same representation (idempotent); changed content ⇒ NEW representation under the SAME `document_id` |
| `retrieval_event_id` | event | one successful acquisition act | `ret-<monotonic/uuid>` — carries method, command, adapter class, HTTP status, timestamp, operator/run |
| `canonical_url` | logical | normalized absolute URL (see rules) | normalization ruleset NR-v1 |
| `content_sha256` | representation | hash of the exact retrieved bytes | SHA-256 (standard already operational: 48 files hashed across Q3/Post-Q3) |
| `retrieved_at` | event | temporal tuple (D4) of the retrieval | — |

**Normalization ruleset NR-v1 (canonical_url):** absolutize relative hrefs against page base (LSE evidence: relative `news-article/…` hrefs); resolve redirects to final URL at acquisition time; record pre-redirect URLs as **aliases**; lowercase scheme/host; strip default ports, trailing slash (path-root excepted), fragment, tracking/session parameters; record every discarded form as an alias.

**Rules (explicit):**
1. Canonical URL alone is NOT identity — it is the identity *seed* (two documents can successively live at one URL; one document can be reachable at many URLs → alias list lives on the logical document).
2. Content hash alone is NOT logical identity (it is representation identity input).
3. Retrieval timestamp alone is NOT identity (it keys the event only).
4. **A changed document never silently overwrites prior evidence**: new representation is appended; all prior representations are retained; existing evidence keeps pointing at the exact `representation_id` it was derived from.
5. **Extraction provenance binds to `representation_id`** — Facts/Evidence reference the exact retrieved bytes, not merely the logical document. (Satisfies the directive's exact-representation provenance requirement.)
6. Feed items: item GUID recorded as an alias identifier; if a source provides a stable GUID with unstable link URL, the GUID is the preferred identity anchor and both are stored.
7. Failed retrieval attempts are recorded in source-health/audit, not as retrieval events on documents (successful retrievements only create representations).

**Evidence/logic:** Q1 LSE (relative→absolute URLs, same article reachable from list and detail), Q3 hash standard, BMF redirect evidence (`bmf.de/feed` → final `bmf.de/feed/`), DGT stable URLs (byte-identical re-captures across sessions — same representation, deterministic `representation_id` confirmed conceptually).

**Remaining ambiguity (bounded):** NR-v1 parameter list will grow as new sources are onboarded; extension is additive alias handling, not an identity-model change.

---

## D2 (P0-2) — FACT / EVENT CORRECTION AND VERSION SEMANTICS

**Decision.** All intelligence objects (Fact, Event, Evidence) are **immutable once created**. Correction = creating a successor object linked to its predecessor. The BMF entity-supersession principle (append-only, history-preserving, never silent) is retained; the *mechanism* is adapted, not reused blindly: entities are registry rows, while facts/events are **derived objects** and therefore get a derivation-versioned model.

**States (deliberately 3, not 4):**

```text
ACTIVE       — current accepted truth
SUPERSEDED   — replaced by a successor version (any reason)
INVALIDATED  — withdrawn internally without successor (unrecoverable extraction/ingestion defect)
```

> **Documented deviation from the directive's example list:** `RETRACTED` is NOT a fourth state. Retraction-by-source is a **supersession reason**, not a distinct machine state — the operational handling (successor version, predecessor linked, evidence retained) is identical to any supersession. Fewer states = fewer invariants to maintain. Recorded here as a conscious reduction, permitted by the directive ("do not add states unless necessary").

**Versioned identity (symmetry with D1):**

| Object | Logical identity | Version |
|---|---|---|
| Fact | `fact-key = (representation_id, metric, pattern_ref, occurrence_index)` | a re-extraction producing a different value from the SAME representation = new fact version (predecessor → SUPERSEDED, reason EXTRACTION_ERROR) |
| Event | `event-key = (document_id, configured event_type, occurrence_index)` | `event_version` carries a **derivation snapshot** = the exact fact versions used |

**Supersession link contract (every correction carries):** successor id, predecessor id, reason code (`EXTRACTION_ERROR | SOURCE_REVISION | RETRACTION_BY_SOURCE | ENTITY_CORRECTION | RE-EXTRACTION`), evidence reference (the representation/document justifying the correction — a later source document CAN supersede a previous fact, but only through this evidence link), actor (run/operator), temporal tuple.

**Downstream propagation rule:** when any input fact changes state, the event's derivation is **recomputed as a new event version** (same `event-key`); the prior event version → SUPERSEDED. Delivered objects (D8) reference the event *versions* they were built from.

**The two-truths rule (directive requirement) is preserved structurally:**
- *Historical truth* (what ROUAA previously knew): retained representations + immutable facts/events + versioned derivations ⇒ any historical output remains exactly reproducible.
- *Current truth* (what ROUAA currently accepts): the ACTIVE transitive closure over supersession chains.

**Remaining ambiguity (bounded):** recomputation batching/triggering (immediate vs. scheduled re-derivation) is an implementation-scheduling detail, not a semantic one.

---

## D3 (P0-3) — INSIGHT LAYER DISPOSITION

**Decision.**

```text
INSIGHT = DEFERRED ARCHITECTURAL DOMAIN
```

- Insight is **removed from the minimum Core canonical model** and recorded as a deferred domain.
- Minimum Core canonical set: **Source · Document (3-level) · Fact · Event · Evidence · Provenance · Temporal tuples · IntelligenceObject/Delivery abstraction (D7, D8)** — i.e., the directive's list with Publication renamed per D5.
- Evidence/Event/Insight separation recorded: Evidence = justifying chain; Event = metric-triggered occurrence; Insight = *deferred* (document-level intelligence remains carried by Document + provenance; cross-document synthesis is NOT supported in minimum Core).

**Deferral rationale (recorded):** product scope unresolved; catch-all-bucket risk (Review §I — negative-definition object); insufficient evidence for a stable canonical contract; must not become a dumping ground for content outside the Event Model.

**Re-entry condition (all four required):** (1) product scope explicitly defined; (2) ≥1 concrete institutional workflow requires it; (3) a bounded contract designed (identity, references, derivation record, temporal tuple, quality/confidence, review state, lifecycle); (4) an architecture review approves it.

**Consequence:** the two scoped representation gaps (DG Trésor analysis class; Ministry fiscal-communication class) remain **scoped-out content classes** — representable in the Core only as Documents (acquired, provenance-stamped), never as Events, until the Insight re-entry condition fires.

**Remaining ambiguity:** none — deferral is complete and its reversal is condition-gated.

---

## D4 (P1-1) — TEMPORAL SEMANTICS CONTRACT

**Decision.** Six-field tuple (the review's option (a), ratified):

```text
original_value          # exact observed string
timezone_status         # EXPLICIT_ZONE | EXPLICIT_OFFSET | NAIVE_LOCAL | UNKNOWN | DATE_ONLY
normalized_utc          # NULLABLE
normalization_basis     # EXPLICIT_SOURCE_TIMEZONE | SOURCE_DOCUMENT_METADATA | JURISDICTION_RULE | INFERRED | NONE
timestamp_semantics     # publication | update | effective | reporting_period | document_date | event_occurrence | unknown
provenance_source       # rss_pubdate | html_time_attr | meta_date | url_date | rendered_text | js_title | filename | file_metadata
```

**Rules:**
1. `normalized_utc = NULL` whenever the timezone cannot be established reliably. No silent inference — ever.
2. Timezone-naive values: `timezone_status ∈ {NAIVE_LOCAL, UNKNOWN}` ⇒ `normalized_utc = NULL`, `basis = NONE`, **unless a separately approved basis exists** (see rule 4).
3. **Cross-jurisdiction ordering participates ONLY on non-NULL `normalized_utc`** whose basis ∈ {EXPLICIT_SOURCE_TIMEZONE, SOURCE_DOCUMENT_METADATA, approved JURISDICTION_RULE}. `INFERRED` values are captured but excluded from ordering until promoted by an approved basis.
4. `JURISDICTION_RULE` and `INFERRED` require a recorded, reviewable rule entry (e.g., "FDIC press releases: US Eastern") with rationale + evidence — a governance artifact, not a code constant.
5. **Conflicting dates are representable without destroying either value**: multiple temporal tuples coexist on the same object, each with its own `timestamp_semantics` + `provenance_source` (DGT A1 evidence: URL `/2026/06/25/` as `document_date/url_date` alongside `<time>` `2026-07-17` as `publication/html_time_attr`).

**Evidence anchors:** LSE naive rendered times; FDIC offset RSS + date-only HTML; ISTAT/DFSA `+0000`; DGT conflict + naive ISO; ministry feed-vs-display; MoF filename/XLS-serial (captured as `filename`/`file_metadata` semantics `document_date`, `normalized_utc` NULL until parsing is validated).

**Remaining ambiguity (bounded):** the JURISDICTION_RULE approval workflow (who records, where stored) is a governance implementation detail.

---

## D5 (P1-2) — PUBLICATION vs INTELLIGENCE DELIVERY TERMINOLOGY

**Decision.** The V1 term `Publication` is **split** into two canonically named concepts:

| Canonical name | Meaning | Layer |
|---|---|---|
| **SourcePublication** | what the **source institution** published — the act and its metadata (publication temporal tuple, channel, source reference) | provenance-side, part of Document/Provenance model |
| **Delivery** | what **ROUAA** delivers downstream — the output act over an IntelligenceObject version (D8 Contract C) | output-side |

The pipeline's existing canonical output unit name — **IntelligenceObject** — is preserved unchanged (`intelligence_object.py` lineage). "Publication" without qualifier is banned from canonical vocabulary.

**Provenance preservation:** SourcePublication retains full provenance meaning (it anchors `publication` temporal semantics in D4). No provenance meaning is removed from the source-side concept.

**Remaining ambiguity:** none.

---

## D6 (P1-3) — INSTITUTION / LEGAL-ENTITY IDENTITY

**Decision.** Internal stable identity scheme; **no external identifier provider** (evidence does not require one — directive's test satisfied):

```text
Institution  (INST-<slug>-<seq>  — Core-issued, immutable)
 ├── legal_entities   (name + jurisdiction; append-only history)
 ├── brands           (names/abbreviations — NON-authoritative for identity)
 ├── domains          (hostname aliases; EACH binding carries verification_method + evidence link)
 └── source_paths     (registered acquisition paths, each institution-bound)
```

**Rules:** identity anchors on Institution (internal ID); **brand/abbreviation is NEVER identity** (the `bmf.de` lesson — "BMF" collides across a ministry and a machinery company); every domain→legal-entity binding requires a recorded verification (imprint/legal-notice check or authoritative cross-reference — Post-Q3 precedent); a single domain exposing multiple legal entities is handled by an owning-institution plus hosted-entity/path-level bindings; renames and government domain changes are append-only metadata history events (never rewrites), with superseding-evidence records where attribution changes.

**BMF test (passes):** Institution `INST-bundesministerium-der-finanzen` ↔ domain `bundesfinanzministerium.de` (verified); Institution `INST-buerener-maschinenfabrik` ↔ domain `bmf.de` (verified). Brand "BMF" collides; identity does not. The mandatory domain→entity verification is exactly the stage whose absence enabled the original misattribution.

**Remaining ambiguity (bounded):** multi-entity path-binding granularity (when a site hosts sub-agencies) resolved case-by-case at onboarding with recorded evidence.

---

## D7 (P1-4) — EXTERNAL API ABSTRACTION

**Decision.** **IntelligenceObject-first** is the primary Core delivery abstraction.

| Option | Verdict | Reason |
|---|---|---|
| Event-first | rejected as primary | events lack the quality-threshold packaging; permitted later as a secondary stream view |
| **IntelligenceObject-first** | **CHOSEN** | the IO is already the pipeline's publishable unit with quality threshold and provenance (`intelligence_object.py`, PUBLISHABLE terminal state) |
| Document-first | rejected | documents are not distilled intelligence; would leak acquisition concerns to products |

**Mandatory traceability carried in the abstraction (directive requirement):** every delivered object exposes the navigable chain `IntelligenceObject → Event(+version) → Fact(+version) → Evidence → Representation (content_sha256) → Document → Source (verified entity)`. Facts/events are detail layers beneath the object, retrievable by reference.

**Remaining ambiguity (bounded):** wire format/schema = build-phase detail; the abstraction decision does not depend on it.

---

## D8 (P1-5) — INSTITUTIONAL BUYER SIMULATION CONTRACTS

**Decision.** Three conceptual contracts defined (implementation excluded):

**Contract A — Request → Source Selection.** `IntelligenceRequest {requesting_party, scope descriptor (jurisdiction / institutional class / topic), constraints}` → resolved **against the entity-resolved Source Registry** (never ad-hoc web search) → `{selected institutions + source_paths, selection rationale, or explicit NO_MATCH}`. The registry's scope attributes (jurisdiction, class) are the matching dimensions (D6).

**Contract B — Traceability Query.** Input: delivered-object identifier (IO id + version). Output (read-only, guaranteed fields): full chain per D7 — event versions, fact versions, evidence, representation (incl. `content_sha256`), document, source (incl. entity verification reference). No mutation surface exists on this contract by design.

**Contract C — External Delivery.** `Delivery` object: canonical payload (IO + referenced event/fact summaries) · canonical identifiers (+ **version information** for the object and every chain element) · provenance references (chain endpoints + hashes) · `delivery_status ∈ {PENDING, DELIVERED, FAILED}` · failure semantics: transport failures are retryable and idempotent per IO version (re-delivery of the same version = deduplicable no-op); content-level failures are terminal for that version and surface through the traceability contract, never through silent omission.

**Remaining ambiguity (bounded):** exact schemas finalized at build; contract elements above are the frozen requirements any schema must satisfy.

---

## D9 (P1-6) — STORAGE VERSIONING / RETENTION PRINCIPLES

**Decision.** Architectural principles only (no commercial retention periods invented):

1. **Append-only canonical store** — no in-place mutation of any evidence-bearing object (D1/D2 make this structural, not procedural).
2. **Representations retained immutably**; reproducibility window ⇒ a representation is retained at least as long as any non-expired delivery references it (directly or through the derivation chain).
3. **Supersession links are immutable**; the audit history IS the chain plus governance events (corrections, entity verifications, rule approvals).
4. **Deletions: tombstones only**; provenance-bearing objects are never hard-deleted. Legal/retention-driven redaction policy = deferred (P2, requires input that does not exist yet).
5. **Reproducibility guarantee:** retained representation + versioned derivation ⇒ exact re-derivation of any historical output.

**Remaining ambiguity (accepted):** retention periods deliberately undefined (no evidence basis to set them — setting them now would violate the workstream's discipline).

---

## D10 (P1-7) — MINIMUM CORE BOUNDARY

**Decision.** Minimum Core components (the verified-evidence contract preserved at smallest scope):

```text
Source Registry (entity-resolved, D6)
Entity Resolution (verification stage)
Acquisition — direct-http adapter class ONLY
Document Identity / Representation (D1)
Normalization
Fact Extraction
Event Detection (6 existing types, unchanged)
Evidence
Provenance (+ SourcePublication, D5)
Temporal Semantics (D4)
Correction/Version model (D2)
Configuration Contract
Governance (supersession, rules, audit)
Canonical Delivery Interface (D7/D8)
Observability / Health (source states + pipeline states)
```

**Explicitly excluded (unless separately justified by new evidence + review):** Insight (D3) · product UI / News UI / Trading execution / Corporate website / marketing / customer-specific workflows · advanced reasoning · **rendering integration** (remains instrument-validated external capability; integration is a separate engineering decision) · XLS/PDF format adapters beyond current evidence.

**Goal ratified:** *smallest Core that preserves the verified evidence contract.*

**Remaining ambiguity:** none.

---

## PHASE 3 — SELF-ADVERSARIAL RECHECK

| Issue | Previous failure (Review V1) | V1.1 decision | Evidence/logic | Resolved? | Remaining ambiguity |
|---|---|---|---|---|---|
| P0-1 Document identity | no identity scheme; traceability unverifiable | D1: 3-level model, NR-v1, representation-bound provenance | Q1 URL forms; hash standard operational; redirect evidence | **YES** | NR-v1 param growth (additive, bounded) |
| P0-2 Fact/Event corrections | supersession existed for entities only | D2: immutable objects + versioned derivation + 3 states + reason-coded links | BMF principle adapted to derived objects; two-truths rule structural | **YES** | recompute scheduling (implementation detail) |
| P0-3 Insight | catch-all bucket risk, no contract | D3: DEFERRED + re-entry conditions | Review §I; no evidence forcing existence | **YES** | none |
| P1-1 Temporal | normalized_utc unsafe when zone unknown | D4: NULL + basis + ordering-participation guard | LSE/DGT naive evidence | **YES** | JURISDICTION_RULE approval workflow (bounded) |
| P1-2 Publication collision | Publication ambiguous Core/product | D5: SourcePublication vs Delivery; IO preserved | terminology-only split, zero semantic loss | **YES** | none |
| P1-3 Institution identity | no canonical identifier | D6: internal IDs, brand-never-identity, verified domain bindings | BMF test passes | **YES** | multi-entity path granularity (case-by-case, bounded) |
| P1-4 API abstraction | undecided | D7: IO-first + mandatory chain | pipeline semantics (PUBLISHABLE unit) | **YES** | wire schema (build detail) |
| P1-5 Simulation contracts | 3 missing | D8: Contracts A/B/C with required elements | simulation flow mapping (Review §Q) | **YES** | schema finalization (build detail) |
| P1-6 Storage/versioning | unstated | D9: 5 principles | mirrors evidence discipline | **YES** | retention periods (deliberately undefined) |
| P1-7 Minimum Core | boundary implied | D10: 15 components + exclusion list | verified-evidence contract | **YES** | none |

No decision is claimed resolved by mere presence of a sentence: each row names the structural mechanism that enforces it (D1 rule 4/5; D2 two-truths closure; D4 ordering guard; D8 idempotency; etc.).

## PHASE 4 — REMAINING BLOCKERS

- **P0 = 0.**
- **P1 remaining:** none unresolved. Accepted bounded implementation details (explicitly permitted by the directive): NR-v1 parameter extension; recompute scheduling; JURISDICTION_RULE approval workflow; simulation contract schemas; wire format; multi-entity path-binding cases; retention periods (deferred with cause).
- **P2 (deferred, unchanged):** production requirements per Review §P phase map; rendering execution mode; adapter-pool mechanics; caching staleness; redaction policy.

## PHASE 5 — BUILD AUTHORIZATION RECOMMENDATION

Ten-condition check (directive-mandated):

1. Document identity defined — **D1** ✓
2. Fact/Event correction semantics defined — **D2** ✓
3. Insight explicitly bounded/deferred — **D3** ✓
4. Temporal semantics safe — **D4** ✓
5. Publication terminology unambiguous — **D5** ✓
6. Institution identity defined — **D6** ✓
7. External abstraction defined — **D7** ✓
8. Buyer Simulation contracts defined — **D8** ✓
9. Storage/versioning principles defined — **D9** ✓
10. Minimum Core boundary explicit — **D10** ✓

# `MINIMUM CORE BUILD AUTHORIZED`

**Scope of authorization (narrow, explicit):** the minimum Core of D10 — direct-http acquisition only, the 6 existing event types unchanged, no Insight, no rendering integration, no XLS/PDF adapters. **Nothing is built by this record**; framework/library selection remains the next phase's opening act, and the Institutional Buyer Simulation remains the final gate before Repository 4 extraction, unchanged.
