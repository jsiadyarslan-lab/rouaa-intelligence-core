# ROUAA INTELLIGENCE CORE ARCHITECTURE V1.1

**Status:** ARCHITECTURAL REVISION OF V1 — corrected per Review V1 (design only)
**Date:** 2026-08-16
**Lineage (explicit, history preserved):**
- **V1** — `docs/architecture/ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1.md` @ `a45bd07`
- **Review V1** — `docs/architecture/ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_REVIEW_V1.md` @ `08d5723` → verdict BUILD BLOCKED (3 P0, 7 P1)
- **V1.1 Decisions** — `docs/architecture/ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1_1_DECISIONS.md` (D1–D10, this commit)
- **This document** = V1 + Decision Addendum. V1 text stands as history; where V1.1 corrects it, the correction is stated inline with its decision ID. Frozen artifacts untouched.

---

## 0. Change Map V1 → V1.1

| # | Section | V1 said | V1.1 corrects to | Decision |
|---|---|---|---|---|
| 1 | Domain model | `Publication` in canonical chain; Insight as canonical object | `SourcePublication` (provenance-side) + `Delivery` (output-side); **Insight = DEFERRED**; Document gets 3-level identity | D1, D3, D5 |
| 2 | Domain model | Document identity listed but undefined | full identity contract (document/representation/retrieval-event) | D1 |
| 3 | Correction semantics | superseding evidence for entities only | immutable intelligence objects + versioned derivation + 3 states + reason-coded supersession | D2 |
| 4 | Temporal model | 5-field tuple; nullability unstated | 6-field tuple; `normalized_utc` NULL rule; `normalization_basis`; ordering-participation guard | D4 |
| 5 | Entity model | hostname→institution chain, identifier unchosen | Institution/LegalEntity/Brand/Domain/Source hierarchy; internal IDs; brand-never-identity; verified domain bindings | D6 |
| 6 | API boundary | abstraction undecided | IntelligenceObject-first + mandatory traceability chain | D7 |
| 7 | Simulation | 3 contracts missing | Contracts A/B/C defined conceptually | D8 |
| 8 | Storage | principles implied | 5 explicit versioning/retention principles | D9 |
| 9 | Minimum Core | "minimum" described qualitatively | 15-component explicit boundary + exclusion list | D10 |
| 10 | Unchanged | config-never-code, adapter/source separation, failure isolation, governance, repository boundary | reaffirmed verbatim (Review B confirmed these survive intact) | — |

## 1. Canonical Domain Model (corrected)

```text
Source → Document → Fact → Event → Evidence → Provenance → IntelligenceObject → Delivery
```

| Entity | V1.1 definition | Decision |
|---|---|---|
| **Source** | entity-resolved institution path: Institution (internal ID) → verified domain → source_path; trust tier + jurisdiction on the ENTITY | D6 |
| **Document** | 3-level: logical `document_id` → `representation_id` (content_sha256) → `retrieval_event_id`; canonical_url + aliases (NR-v1); SourcePublication temporal tuples attached | D1, D5 |
| **Fact** | immutable; identity `(representation_id, metric, pattern_ref, occurrence)`; versioned via supersession | D2 |
| **Event** | immutable; identity `(document_id, event_type, occurrence)`; versions carry derivation snapshots (exact fact versions) | D2 |
| **Evidence** | immutable justifying chain; binds to exact `representation_id` | D1, D2 |
| **Provenance** | origin metadata incl. 6-field temporal tuples and SourcePublication anchors | D4, D5 |
| **IntelligenceObject** | canonical output unit (quality-threshold, PUBLISHABLE lineage); exposes full traceability chain | D7 |
| **Delivery** | output act over an IO version; idempotent per version; statuses PENDING/DELIVERED/FAILED | D5, D8-C |
| **Insight** | **DEFERRED ARCHITECTURAL DOMAIN** — not in minimum Core; re-entry condition-gated | D3 |

## 2. Identity Model (corrected — D6)

Institution-anchored: `INST-<slug>-<seq>` immutable; legal entities (name+jurisdiction, append-only); brands recorded but **never identity**; every domain binding carries verification_method + evidence (the anti-bmf.de-de lesson); multi-entity domains via owning-institution + path-level bindings; renames/domain changes = append-only history. BMF test passes by construction (§D6 of Decisions).

## 3. Temporal Model (corrected — D4)

Six-field tuple; `normalized_utc` NULL when zone unreliable; no silent inference; `normalization_basis` gating (explicit metadata, or approved JURISDICTION_RULE; INFERRED captured but non-ordering); conflicting dates = coexisting tuples with distinct semantics/provenance; ordering only on non-NULL UTC with qualifying basis.

## 4. Correction / Version Model (new — D2)

Immutable objects; SUPERSEDED/INVALIDATED via reason-coded links with evidence references; event versions recompute from fact versions; two-truths preserved structurally (historical = retained representations + immutable chain; current = ACTIVE closure). Source-driven changes (revision, retraction) enter ONLY through new documents → evidence links.

## 5. Evidence / Provenance (reinforced — D1, D2, D4)

Chain: `IntelligenceObject → Event(+version) → Fact(+version) → Evidence → Representation(sha256) → Document → Source(verified)`. Every link immutable; retrieval events carry method/command/actor; transformation history via raw_value + version chain; content hash closes the verification loop.

## 6. Event Model (unchanged — reaffirmed)

6 types, data-driven `EVENT_TYPE_RULES`, config-bound patterns; extension = dict entries, never pipeline branching (code-verified @ `c7109ca`). The two scoped content classes (DGT analysis; Ministry fiscal communication) remain **scoped-out** pending Insight re-entry or product-scope decision (D3). No types added.

## 7. Acquisition Boundary (minimum — D10)

Direct-http adapter class ONLY in minimum Core (RSS/Atom, static/server HTML) — the evidence-VALIDATED class. Document-repository + rendering classes remain architecture-defined but **deferred**: rendering is instrument-validated (not pipeline-integrated — separate engineering decision); XLS/PDF format parsing UNTESTED. Canonical Document contract regardless of mechanism (acquisition metadata embedded). Anti-bot-hard and TLS failures remain source access states (BLOCKED/UNMEASURED); **configuration never encodes access-control evasion**.

## 8. Configuration Boundary (unchanged — reaffirmed, K-lessons carried)

URLs/paths/patterns/keywords/event-bindings/format hints = config. Entity verification, temporal semantics, evidence construction, adapter implementations, new normalization families, quality governance = Core. FED_ENF = config ✓; BMF = entity-stage (not config); DMO = BLOCKED (never config-workaround).

## 9. Storage / Data Ownership (principled — D9)

Core owns canonical store (all §1 entities); append-only; representations retained ≥ lifetime of referencing deliveries; tombstone-only deletions; audit = chain + governance events; products cache read-only, never mutate, never source-of-truth (V1 principle reaffirmed without change).

## 10. API Boundary (decided — D7, D8)

**IntelligenceObject-first** primary; events/facts = detail layers by reference; mandatory traceability chain in the abstraction. Simulation contracts: A (Request→Source Selection, registry-driven, NO_MATCH explicit) · B (Traceability Query, read-only, guaranteed chain) · C (External Delivery, versioned+idempotent, failure semantics split transport/content). Wire schemas = build-phase.

## 11. Product Boundary (unchanged — reaffirmed)

News / Trading / Corporate consume canonical intelligence via Delivery; they never fetch, never own provenance, never define canonical semantics. V1 §B list unchanged.

## 12. Minimum Core (explicit — D10)

15 components as listed in D10 (registry → observability). Excluded: Insight, product surfaces, trading execution, marketing, customer workflows, advanced reasoning, rendering integration, XLS/PDF adapters. **Goal: smallest Core preserving the verified evidence contract.**

## 13. Deferred Areas (registry)

Insight (condition-gated, D3) · rendering pipeline integration (engineering decision, evidence exists) · structured-file adapters (MoF precedent, parsing untested) · ISTAT pattern remediation candidate (config-domain, FED_ENF-precedented) · retention periods (no evidence basis) · production requirements per Review §P phase map · redaction policy.

## 14. Readiness (carried, updated)

V1 §N answers stand, amended: minimum Core now = D10 boundary; Repository 4 extraction criteria unchanged (Architecture V1.1 review passed → Core build → validation → **Institutional Buyer Simulation passed** → extraction).

---

**V1.1 complete. Design only — no implementation, no framework selection, no Repository 4, no deployment, no simulation. Authorization verdict recorded in the Decision Addendum (Phase 5): `MINIMUM CORE BUILD AUTHORIZED` (scope: D10).**
