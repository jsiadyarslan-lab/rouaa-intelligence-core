# EXTRACTION STATUS V1 — Repository 4

**Repository:** https://github.com/jsiadyarslan-lab/rouaa-intelligence-core (PRIVATE)
**Extraction plan:** `3a64fb7` (Gate B approved by user with default decisions:
name `rouaa-intelligence-core` · visibility PRIVATE · storage JSONL · no LICENSE ·
GovDelivery-class rule remains a D6 extension point)
**Extracted validated lineage:** `9af81b7` + `8de74e9` + `150ae87`.

## Extracted files
26 verbatim files — 14 runtime modules, 6 unit-test files, 3 validation
harnesses, 2 canonical architecture docs (V1.1 + Decisions), package inits —
**SHA-256 equality IDENTICAL for all 26** (see `EXTRACTION_PROVENANCE.md`).
Tests organized into `unit/ replay/ conformance/` per plan §4/J.

## SHA equality
26/26 IDENTICAL. Documented deviations (none touch runtime behavior):
1. `tests/run_all.py` — **EXTRACTION-ONLY CHANGE**: module discovery names after
   the `unit/` split (path strings only).
2. `tests/replay/phase2_analysis.py` — **EXTRACTION-ONLY CHANGE** (one import
   path after the `replay/` split) **+ VALIDATION-HARNESS CORRECTION**: the
   correction scenario previously selected facts by first-sorted-hash, making
   its outcome hash-order-dependent (the `true` observed at `8de74e9` was luck;
   a fresh live capture inverted the order). Fixed by scoping to the modified
   document's event + its snapshot fact — the exact pattern already validated
   in `buyer_simulation_v1.py` @ `150ae87`. Runtime Core untouched
   (byte-identity holds; deterministic unit Cases A–F always proved
   propagation). Recorded transparently; the alternative (hiding it) would
   violate the workstream's evidence discipline.

## Tests (Gate E)
**48/48 PASS from this repository alone** (fresh CPython 3.12.8 embeddable;
no `rouaa-corporate` on the path), double-run deterministic.

## Phase 2 replay (Gate F part 1)
Executed live from this repository: traceability **0 broken links** ·
determinism **TRUE** · description-only classification unchanged
(LIMITATION CONFIRMED — **L-DES DEFERRED/BOUNDED**) · ISTAT pattern boundaries
reproduced · idempotency TRUE · content-change: new representation + old fact
**SUPERSEDED** + **event re-version TRUE** + historical reproducible TRUE.
Result: **PHASE 2 REPLAY PASSED**. Hardening states:
`L-EVT-PROP = RESOLVED · L-REL = RESOLVED · L-SRC = RESOLVED · L-DES = DEFERRED/BOUNDED`.

## Buyer Simulation replay (Gate F part 2 — extraction integrity check)
**Same acceptance result — 11/11 TRUE**: source trust (incl. bmf.de→Ministry
rejection and platform-feed refusal) · two intelligence types to IO
(`regulatory_enforcement`, `statistical_release`) · traceability complete ·
correction new version + history survives · failure isolation · delivery
idempotency · temporal semantics · consumer contract. External transport
remains **SIMULATED**. **No regression.**

## Differences discovered
Only the three documented items above (2 path-only + 1 harness correction).
Zero runtime differences. Secrets scan: **CLEAN**.

## Unresolved issues
None blocking. Open decisions (per directive §17, NOT auto-resolved): SQL
migration timing · public visibility · LICENSE · distribution-platform
entity rule · real external transport · production Railway architecture.

## Gate status
```text
A Simulation accepted            PASSED
B Extraction plan approved       PASSED
C Repository 4 created           PASSED
D Validated Core extracted       PASSED (26/26 SHA-identical)
E Independent 48+ tests          PASSED (48/48, isolated env)
F Phase-2 + Simulation replays   PASSED
G Production readiness           NOT STARTED
H Railway                        NOT STARTED
I First product integration      NOT STARTED
J Remaining integrations         NOT STARTED
```

## Verdict

# `REPOSITORY 4 EXTRACTION PASSED`

`rouaa-corporate` remains untouched (rollback source intact; the original Core
copy stays until a separate deprecation decision). Next phase (separate
review): **PRODUCTIONIZATION + RAILWAY DEPLOYMENT PLAN**. No Railway, no News,
no Trading, no Corporate connections in this task.
