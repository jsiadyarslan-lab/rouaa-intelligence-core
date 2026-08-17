# ROUAA CORE CONTRACT CONFORMANCE V1

**Status:** R2 RESTORATION CONFORMANCE RECORD (single authority)
**Date:** 2026-08-17
**Directive:** EXECUTION DIRECTIVE — CORE CONTRACT RESTORATION R2 V1 (user-issued verbatim)
**Pre-modification freeze record (§1):** HEAD `db3079a` (clean tree) · validated suite 48/48 OK under pre-state · endpoints in production path: `/api/v1/*` (unauthorized ×2 files) · News adapter endpoint: `/api/v1/intelligence-objects` (@ `b0985d2`, frozen) · mock schema: consumer-invented + fabricated fields. **Rollback reference:** git history (`db3079a`); no history rewritten — unauthorized artifacts MOVED, not deleted.

## A. Canonical Core contract
`/v1` surface per ratified architecture; schema = real IO shapes + documented transport projections (`status`, `supersedes_io_id`) only; production transport `NOT_IMPLEMENTED` (S1); canonical dev reference `tools/mock_core/` (fixtures from the validated lineage). Full text: `ROUAA_CORE_INTELLIGENCE_CONTRACT_V1.md`.

## B. Removed / isolated unauthorized contract
`intelligence_core/contract_api.py` + `intelligence_core/mock_contract_server.py` → **`archive/unauthorized-contract/`** (git-mv, verbatim, README states origin commits `6018568`/`2f06b48`, the three reasons, and do-not-run). Production package back to the validated 15-file set (14 modules + `__init__`).

## C. Fabricated-field audit
`provenance_complete` / `confidence_score` / `reproducible` — **FABRICATED** (zero occurrences in the actual Core, including the archived contract_api itself; they lived only in the consumer mock + News TS interface). Rule recorded: never added for a consumer; any future provenance/confidence semantics = separate architectural decision. Canonical mock enforces their absence (M2 anti-fabrication test).

## D. Endpoint authority
ONE: `/v1/intelligence` family (architecture `e0964f5` §L). No alias for `/api/v1/...`; drill hooks (`?_force_status=`) are test-only and documented as such.

## E. Schema authority
Section 2 of the canonical contract — every field carries type/required/meaning/source; undecided capabilities are marked by their true status (`NOT_IMPLEMENTED`, `ARCHITECTURAL CAPABILITY GAP`) — never `OPTIONAL`.

## F. Versioning
`io.version=1` constant; `event_version` is the lineage axis; v1 SUPERSEDED → v2 ACTIVE verified in fixtures (values `+0.3`/`+0.4`, `supersedes_io_id` set, histories intact) and by the validated governance suite (Cases A–F). No consumer version semantics.

## G. Core gaps (recorded, not implemented)
`event_type` field emission · `temporal_data` surfacing · `/trace` production implementation (design-mandated, S1) · production transport itself (S1/Gate-G).

## H. Consumer conformance (read-only comparison; NO consumer code changed)

| Consumer | Endpoint Match | Schema Match | Fabricated Fields | Missing Fields | Status |
|---|---|---|---|---|---|
| News (`core-adapter.ts` @ `b0985d2`, FROZEN) | **MISMATCH** (`/api/v1/intelligence-objects` vs canonical `/v1/intelligence`) | PARTIAL (IO-chain fields match; expects absent top-level fields) | **3** (`provenance_complete`, `confidence_score`, `reproducible`) | 2 (`event_type`, `temporal_data` = Core capability gaps) | MUST ALIGN AFTER Core-side decision — mismatch report delivered; no auto-adaptation |
| Trading | NO CURRENT CONSUMER | — | 0 | — | drift prevented (no adapter exists to drift) |
| Corporate | NO CURRENT CONSUMER | — | 0 | — | same |

## I. Test results (this run, post-restoration tree)
- Validated Core suite: **48/48 OK** (unauthorized files out of the production path — nothing imported them).
- Canonical contract conformance `tools/mock_core/test_mock_core_contract.py`: **11/11 OK** — M1 endpoint (health/feed/pagination/401), M2 schema (+ anti-fabrication: 9 absent fields asserted), M3 versioning (v1/v2 immutable histories), M4 identity (404/304/429), M5 errors (405 read-only, error envelope, 500 drill), M6 provenance (64-hex representation sha in chain, evidence ids), M7 temporal honesty (tuples asserted ABSENT pending decision), M8 trace endpoint. Only architecture-present requirements tested; nothing invented.
- The unauthorized contract had NO tests of its own (verified: the six parallel commits added only the two runtime files + docs) — nothing to convert; its behavior is preserved as archived evidence.

## J. Review / comment / CI inspection (§17 — MANDATORY, executed post-push)
Recorded in the execution report accompanying this commit: GitHub commit comments, review comments, issues, and check-runs were queried for the affected commits/PRs with the directive's keyword set (`contract`, `endpoint`, `schema`, `provenance`, `confidence`, `reproducibility`, `version`, `News`, `Trading`, `Corporate`). Any unresolved contract-affecting comment would block closure — findings listed in the report; none blocking at push time (re-verified).

## K. Future architectural decisions (queued, owner = user)
K1 Surface `event_type` in the transport projection (store-derived; trivial once decided). K2 Surface `temporal_data` tuples (D4 semantics already exist in the store). K3 Provenance/confidence/reproducibility semantics (if ever — as real Core capabilities, not consumer-shaped fields). K4 S1 production transport under Gate-G (implements this contract). K5 News adapter reconciliation (after K1/K2 decided or explicitly declined).

---

# VERDICT (§21)

# `CORE CONTRACT RESTORED — SINGLE AUTHORITY ESTABLISHED`

Required state achieved: ONE canonical contract (`/v1`, this document) · ONE canonical endpoint authority (architecture §L + canonical mock) · ZERO fabricated consumer fields in the canonical path · ZERO competing production contracts (unauthorized surface archived out) · ZERO consumer modifications (News/Trading/Corporate untouched). Consumers remain frozen pending directed reconciliation (K5).
