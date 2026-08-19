# ROUAA Intelligence Core

Canonical ROUAA Intelligence Core — evidence-backed financial intelligence
infrastructure. Extracted verbatim from the validated lineage in
`jsiadyarslan-lab/rouaa-corporate` (extraction plan @ 3a64fb7; validated Core
@ 9af81b7 + 8de74e9 + 150ae87).

## Scope (Minimum Core)
Direct HTTP acquisition (RSS/Atom + static/server HTML) · entity resolution
(verified-domain bindings; brand never identity) · 3-level document identity
(document/representation/retrieval-event, SHA-256 content addressing) ·
normalization · fact extraction (config-defined patterns; PATTERN_TYPE_METADATA
normalization) · event detection (6 existing event types, data-driven) ·
evidence + provenance · 6-field temporal semantics (no silent inference;
ordering guard) · governance (append-only supersession, event re-versioning,
historical reproducibility) · IntelligenceObject-first delivery (idempotent
ledger) · health/observability · configuration contract (config ≠ core code).

## Excluded capabilities (deferred by design)
Browser rendering integration · XLS/PDF special adapters · Insight layer ·
new event types · multilingual engines · advanced reasoning · external
production transport (delivery ledger only) · product UIs.

## Test commands
```
python -m intelligence_core.tests.run_all                             # 48 unit/regression tests (deterministic, offline)
python -m intelligence_core.tests.replay.phase2_live_validation       # Phase-2 live replay (network)
python -m intelligence_core.tests.replay.phase2_analysis             # Phase-2 analysis (offline, on capture)
python -m intelligence_core.tests.conformance.buyer_simulation_v1    # Buyer Simulation conformance (network)
```

Standard library only (Python 3.12). Storage: append-only JSONL +
content-addressed blobs (SQL is a separate future decision).

## Current validation status
Phase 1 build 48/48 · Phase 2 live validation PASSED WITH BOUNDED LIMITATIONS ·
Pre-simulation hardening PASSED (L-EVT-PROP/L-REL/L-SRC RESOLVED; L-DES
DEFERRED) · Institutional Buyer Simulation PASSED WITH BOUNDED LIMITATIONS
(acceptance 11/11) · Extraction Gates C–F PASSED in this repository
(independent 48/48, Phase-2 replay, Buyer Simulation replay).

## Provenance
See `docs/EXTRACTION_PROVENANCE.md` (per-file SHA-256 before/after) and
`docs/EXTRACTION_STATUS_V1.md`. Historical evidence remains canonical in
`rouaa-corporate` (Evidence Expansion 654e7f8/73b7668 · Q1 ee7ca83 · Q2 a72d5d8 ·
Q3 c7109ca · Post-Q3 f6c5a8b · Consolidation a45bd07 · Review 08d5723 ·
V1.1 9298162 · Build 9af81b7 · Validation 0f4139b · Hardening 8de74e9 ·
Simulation 150ae87 · Plan 3a64fb7).
