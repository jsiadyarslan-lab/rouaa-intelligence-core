# ROUAA CORE V46.1 — SEMANTIC CLAIM FORENSICS

## Verdict
`V46.1 BLOCKED — SEMANTIC CLAIM ELIGIBILITY NOT PROVEN`

V46 proved that structural context can be attached without changing evidence. It did **not** prove that an institution, date, or state found anywhere in that window belongs to the represented event.

## Population
- NEW IOs examined: **371**
- Entity confirmations dependent on source/publisher match: **55**
- Temporal claims requiring event-local review: **116**
- Event-state claims requiring event-local review: **189**
- Event types independently validated by V46: **0**

## Root cause
The entity auditor marks a candidate CONFIRMED when it appears in evidence *and matches `source_name`. This establishes publisher identity, not the subject entity of the fact or event. The temporal and state auditors search the complete aggregate evidence string, so they do not retain a fact-local/event-local relation for the matched signal.

## Required next change
Do not create a source-to-subject registry. First introduce a typed semantic contract that distinguishes `publisher_institution` from `subject_entity` and requires every event-level entity, date, and state claim to cite a segment that also contains (or structurally binds to) the represented fact/event.

## Ledger
The machine-readable ledger is `intelligence_core/tests/reliability/v46_1_semantic_claim_forensics.json`. It preserves IO, document, fact, evidence, and document URL identifiers for human adjudication.
