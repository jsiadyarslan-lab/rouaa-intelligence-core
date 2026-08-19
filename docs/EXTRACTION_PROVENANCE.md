# EXTRACTION PROVENANCE — rouaa-intelligence-core

Source: `jsiadyarslan-lab/rouaa-corporate` branch `top20-prescreening`, tree at `150ae87`
(commit 3a64fb7 is docs-only; the Core tree is unchanged). Runtime Core + unit
tests: **26/26 files byte-identical (SHA-256 equality)**. Documented deviations:
2 extraction-only path adjustments + 1 validation-harness correction (last row).

| Source path (rouaa-corporate, tree @ 150ae87) | Destination (this repo) | SHA-256 before | Equality |
|---|---|---|---|
| `intelligence_core\__init__.py` | `intelligence_core\__init__.py` | `a38a330d6a116f0b…` | IDENTICAL |
| `intelligence_core\acquisition.py` | `intelligence_core\acquisition.py` | `b3a0f207cb090795…` | IDENTICAL |
| `intelligence_core\config.py` | `intelligence_core\config.py` | `c53121d079130d52…` | IDENTICAL |
| `intelligence_core\contracts.py` | `intelligence_core\contracts.py` | `d3f88d39fe2004bc…` | IDENTICAL |
| `intelligence_core\delivery.py` | `intelligence_core\delivery.py` | `29855ca23240acef…` | IDENTICAL |
| `intelligence_core\detect.py` | `intelligence_core\detect.py` | `3bc3a0d47a1b8216…` | IDENTICAL |
| `intelligence_core\entity_resolution.py` | `intelligence_core\entity_resolution.py` | `57e0a6cb894cab07…` | IDENTICAL |
| `intelligence_core\extract.py` | `intelligence_core\extract.py` | `b69eab6ce5c4bf57…` | IDENTICAL |
| `intelligence_core\governance.py` | `intelligence_core\governance.py` | `49b586ae91ccafc1…` | IDENTICAL |
| `intelligence_core\health.py` | `intelligence_core\health.py` | `2e39a7444388112f…` | IDENTICAL |
| `intelligence_core\identity.py` | `intelligence_core\identity.py` | `a7d950ad01639343…` | IDENTICAL |
| `intelligence_core\normalize.py` | `intelligence_core\normalize.py` | `eff0ab1a51e6e507…` | IDENTICAL |
| `intelligence_core\pipeline.py` | `intelligence_core\pipeline.py` | `335dbf9a7232b386…` | IDENTICAL |
| `intelligence_core\store.py` | `intelligence_core\store.py` | `46a92d502d46a040…` | IDENTICAL |
| `intelligence_core\temporal.py` | `intelligence_core\temporal.py` | `6b2c1f57b3fe947d…` | IDENTICAL |
| `intelligence_core\tests\test_entity.py` | `intelligence_core\tests\unit\test_entity.py` | `89f98919f894d030…` | IDENTICAL |
| `intelligence_core\tests\test_document_identity.py` | `intelligence_core\tests\unit\test_document_identity.py` | `f7c6d75da6b1f00e…` | IDENTICAL |
| `intelligence_core\tests\test_temporal.py` | `intelligence_core\tests\unit\test_temporal.py` | `755ce1f1185d63fd…` | IDENTICAL |
| `intelligence_core\tests\test_governance.py` | `intelligence_core\tests\unit\test_governance.py` | `852ab56fe843074a…` | IDENTICAL |
| `intelligence_core\tests\test_pipeline.py` | `intelligence_core\tests\unit\test_pipeline.py` | `a6023ffe338aaa8c…` | IDENTICAL |
| `intelligence_core\tests\test_hardening.py` | `intelligence_core\tests\unit\test_hardening.py` | `85c20cb4d97a5294…` | IDENTICAL |
| `intelligence_core\tests\phase2_live_validation.py` | `intelligence_core\tests\replay\phase2_live_validation.py` | `30101944b92ccab2…` | IDENTICAL |
| `intelligence_core\tests\phase2_analysis.py` | `intelligence_core\tests\replay\phase2_analysis.py` | `1480b221a48018c7…` | IDENTICAL |
| `intelligence_core\tests\buyer_simulation_v1.py` | `intelligence_core\tests\conformance\buyer_simulation_v1.py` | `13c9d0fcaa7a7d9a…` | IDENTICAL |
| `docs\architecture\ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1_1.md` | `docs\ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1_1.md` | `f06fde1d98358fb2…` | IDENTICAL |
| `docs\architecture\ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1_1_DECISIONS.md` | `docs\ROUAA_INTELLIGENCE_CORE_ARCHITECTURE_V1_1_DECISIONS.md` | `ffa458464e1221cc…` | IDENTICAL |
| `intelligence_core/tests/run_all.py` | `intelligence_core/tests/run_all.py` | `c0cc69878c2ae273…` | EXTRACTION-ONLY CHANGE — test discovery paths after unit/ subdirectory split (plan section 4) (module name strings only) |
| `intelligence_core/tests/replay/phase2_analysis.py` | `intelligence_core/tests/replay/phase2_analysis.py` | `7a1ca8dfe5fd699b…` | EXTRACTION-ONLY CHANGE — harness import path after replay/ subdirectory split (one import statement) |
| `intelligence_core/tests/replay/phase2_analysis.py` | same | — | VALIDATION-HARNESS CORRECTION — scoping mirrors validated buyer_simulation_v1.py @ 150ae87 (see EXTRACTION_STATUS) |

## Identity/behavior check (directive §12)
Runtime files byte-identical ⇒ identical deterministic id derivations
(document/representation/fact/event/evidence/IO/delivery). Verified live from
this repository: 48/48 tests (double-run deterministic), Phase-2 replay
determinism TRUE, Buyer Simulation replay acceptance identical (11/11).
No identity drift.
