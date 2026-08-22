# V48 Human Adjudication Gate — Reconciliation

## Generated
2026-08-22T10:27:33.250244+00:00

## Authoritative State
- origin/main: 5a255bd4af2509cd57e7c9db68aa2710708d75bc
- Gold-V2: ACCEPTED_WITH_EXCEPTIONS (FROZEN)
- V48AD: PROMOTED_AND_VERIFIED

## Population Reconciliation
- Total: 480
- Unique IDs: 480
- Duplicates: 0
- Missing: 0
- Invalid: 0

## Stratum Distribution


## Adjudication State
- PENDING_HUMAN: 480
- Adjudicated: 0

## Contextual Support (tool observation)
- AMBIGUOUS_CONTEXT: 59
- DIRECT_CONTEXTUAL_SUPPORT: 103
- DOCUMENT_PRESENCE_ONLY: 318

## §5 Distinction
- fact_value_present: 480/480
- fact_context_supported: 103/480

## Integrity Checks
- ✓ no_duplicate_case_ids: PASS
- ✓ population_is_480: PASS
- ✓ all_pending_human: PASS
- ✓ no_gold_v2_mutation: PASS
- ✓ no_production_code_mutation: PASS
- ✓ canonical_document_resolution: PASS
- ✓ representation_id_coverage: PASS
- ✓ evidence_segment_id_coverage: PASS
- ✓ machine_human_separation: PASS

## Production Code on Main
- intelligence_core/__init__.py
- intelligence_core/acquisition.py
- intelligence_core/cached_store.py
- intelligence_core/config.py
- intelligence_core/contracts.py
- intelligence_core/delivery.py
- intelligence_core/detect.py
- intelligence_core/entity_resolution.py
- intelligence_core/evidence_selection.py
- intelligence_core/extract.py
- intelligence_core/governance.py
- intelligence_core/health.py
- intelligence_core/identity.py
- intelligence_core/normalize.py
- intelligence_core/pipeline.py
- intelligence_core/production_transport.py
- intelligence_core/source_network/__init__.py
- intelligence_core/source_network/discovery_catalog.py
- intelligence_core/source_network/discovery_catalog_wave_b.py
- intelligence_core/source_network/discovery_catalog_wave_c.py
- intelligence_core/source_network/discovery_catalog_wave_d.py
- intelligence_core/source_network/qualification.py
- intelligence_core/source_network/registry.py
- intelligence_core/source_network/reharden_sources.py
- intelligence_core/source_network/wave_b_qualification.py
- intelligence_core/source_network/wave_c_qualification.py
- intelligence_core/source_network/wave_d_qualification.py
- intelligence_core/store.py
- intelligence_core/structural_parser.py
- intelligence_core/subject_entity.py
- intelligence_core/temporal.py

## Conclusion
All checks PASS — HUMAN_GATE_READY
