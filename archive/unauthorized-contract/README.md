# Archived: Unauthorized Contract Surface (R2 Restoration)

**Status:** REMOVED FROM PRODUCTION CORE PATH — historical reference only (do not import, do not run).
**Origin:** parallel Phase-1 commits `6018568` + `2f06b48` (pushed 2026-08-16, bypassing the S1/Gate-G service path and M1–M8 conformance).
**Why archived:** implements the unauthorized `/api/v1/intelligence-objects` surface that contradicts the ratified architecture (`e0964f5` §L: `/v1/...`); its sibling mock bakes FABRICATED_CONTRACT_FIELDs (`provenance_complete`, `confidence_score`, `reproducible`) that exist nowhere in the actual Core; `contract_api._handle_list` silently swallows broken chains (`except: continue`) violating the broken-link-is-failure discipline.
**Decision:** user directive R2 (Core Contract Restoration) — the ratified architecture is the single authority; consumers never define Core semantics.
**Kept verbatim** as evidence for the contract audit lineage (`db3079a`). Canonical contract: `docs/contracts/ROUAA_CORE_INTELLIGENCE_CONTRACT_V1.md`; canonical dev mock: `tools/mock_core/`.
