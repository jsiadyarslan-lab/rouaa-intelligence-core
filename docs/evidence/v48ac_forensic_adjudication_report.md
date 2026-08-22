# V48AC Forensic Subject-Evidence Adjudication Report

## Generated
2026-08-22T10:15:33.857386+00:00

## Authoritative State
- origin/main: 15f8afe3bbca8db2eda8df4a5ddd668782e674cc (Gold-V2 ACCEPTED_WITH_EXCEPTIONS)
- origin/recovery: 29967099aad552e363525f8da8077f0bf7c62cf2 (V48AD chain)

## Population Reconciliation

| Category | Total | Pass | Fail |
|----------|------:|-----:|-----:|
| Positive | 50 | 39 | 11 |
| Negative | 50 | 49 | 1 |
| Ambiguous | 50 | 46 | 4 |
| **Total** | **150** | **134** | **16** |

## Failure Taxonomy

| Class | Count | % | Diagnosis |
|-------|------:|--:|----------|
| DATA | 1 | 6.2% | Bank Rate alias missing from registry |
| EXTRACTION | 0 | 0.0% | — |
| RULE | 15 | 93.8% | Verb lexicon too narrow + signal≠attribution |
| SEMANTIC | 0 | 0.0% | — |

## Per-Case Forensic Table

| # | Cat | Candidate | Judgment | Class | Text |
|---|-----|-----------|----------|-------|------|
| 10 | posi | NO_CANDIDATE | NO_CANDIDATE | DATA | Bank Rate held at 4.25 percent in August. |
| 13 | posi | Foreign Exchange | AMBIGUOUS | RULE | Foreign exchange volumes climbed 15 percent. |
| 15 | posi | Penalty | AMBIGUOUS | RULE | Financial penalty of £2.5 million levied. |
| 30 | posi | Inflation | AMBIGUOUS | RULE | Inflation stabilized at 2.0 percent. |
| 34 | posi | Policy Rate | AMBIGUOUS | RULE | Policy Rate lowered by 25 basis points. |
| 36 | posi | Penalty | AMBIGUOUS | RULE | Penalty assessed at $750,000 for late filing. |
| 38 | posi | Inflation | AMBIGUOUS | RULE | Inflation reached 5.0 percent, the highest in a de |
| 40 | posi | Unemployment | AMBIGUOUS | RULE | Unemployment stood at 4.8 percent in May. |
| 43 | posi | Penalty | AMBIGUOUS | RULE | Penalty finalized at £1.8 million for misconduct. |
| 44 | posi | Gross Domestic Product | AMBIGUOUS | RULE | GDP advanced 2.9 percent for the full year. |
| 47 | posi | Unemployment | AMBIGUOUS | RULE | Unemployment improved to 3.9 percent. |
| 85 | nega | Foreign Exchange | TRUE_SUBJECT | RULE | Construction Report. FX turnover in international  |
| 116 | ambi | Foreign Exchange | TRUE_SUBJECT | RULE | FX turnover data is collected semi-annually. |
| 131 | ambi | Penalty | TRUE_SUBJECT | RULE | Penalty guidelines were published for consultation |
| 135 | ambi | Unemployment | TRUE_SUBJECT | RULE | Unemployment registrations increased marginally. |
| 141 | ambi | Policy Rate | TRUE_SUBJECT | RULE | Policy Rate corridor was maintained as before. |


## Key Distinction Proven

STRONG EVIDENCE ABOUT CANDIDATE ≠ STRONG EVIDENCE PRESENT IN DOCUMENT

The 15 RULE failures break down as:
- 10 positive: event verb in text but not in _EVENT_VERBS lexicon
- 1 negative: event=STRONG fired because verb 'turnover' appeared near candidate,
  but the document is about Construction, not FX. Signal strength ≠ Subject attribution.
- 4 ambiguous: candidate is noun modifier (FX turnover data, Penalty guidelines, etc.)
  but rule promoted to TRUE_SUBJECT because verb matched near candidate.

## V48AD Remediation Status (on recovery only, NOT on main)

| Metric | Baseline (V48AB) | Post-V48AD | Delta |
|--------|----------------:|-----------:|------:|
| Total pass | 134/150 (89.3%) | 143/150 (95.3%) | +9 |
| Positive pass | 39/50 | 48/50 | +9 |
| Negative pass | 49/50 | 49/50 | 0 |
| Ambiguous pass | 46/50 | 46/50 | 0 |

V48AD fixed 9 of 16 failures. 7 remain.

## Final Verdict

**EVIDENCE_MODEL_SUFFICIENT**

0 SEMANTIC failures → the semantic model is NOT broken.
The multi-signal triangulation framework is fundamentally sound.

Bottleneck = RULE lexicon (verbs) + signal-attribution check,
NOT the semantic architecture.

V48AD partially addressed this on recovery, but:
- V48AD changes are on recovery only (NOT on origin/main)
- 7 failures remain (2 positive + 1 negative + 4 ambiguous)
- V48AD's subject_entity.py changes need separate promotion authorization

No architectural redesign needed.
No LLM/embeddings needed.
No V49 needed.

## What IS Needed Before Integration

1. Promote V48AD's subject_entity.py changes to main (separate authorization)
2. Fix remaining 7 failures
3. Only then: production integration

## Production Changes
- 0 (forensic analysis only)
- No resolve_subject changes
- No Gold-V2 changes
- No V49 / Entity Resolution / embeddings / LLM

## Stop
STOP — forensic verdict complete.
Do NOT proceed to production integration until V48AC is independently reviewed.
