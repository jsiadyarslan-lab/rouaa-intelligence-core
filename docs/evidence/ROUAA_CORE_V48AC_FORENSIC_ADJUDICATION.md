# V48AC — Subject Evidence Adjudication

**Verdict:** `PASS`

## Population Reconciliation

| Category | Total | Pass | Fail |
|----------|-----:|-----:|-----:|
| Positive | 50 | 39 | 11 |
| Negative | 50 | 49 | 1 |
| Ambiguous | 50 | 46 | 4 |
| **Total** | **150** | **134** | **16** |

## Failure Taxonomy

| Class | Count | % | Diagnosis |
|-------|-----:|--:|----------|
| DATA | 1 | 6.2% | Registry alias missing or data not available |
| EXTRACTION | 0 | 0.0% | Primary segment extraction picked wrong segment |
| RULE | 15 | 93.8% | Verb lexicon/measurement regex too narrow; signal≠attribution |
| SEMANTIC | 0 | 0.0% | Genuine semantic limitation — model cannot decide |

## All 16 Failures Individually Accounted For: YES

## Per-Case Forensic Table

| # | Cat | Candidate | Judgment | Class | Text |
|---|-----|-----------|----------|-------|------|
| 10 | pos | NO_CANDIDATE | NO_CANDIDATE | DATA | Bank Rate held at 4.25 percent in August. |
| 13 | pos | Foreign Exchange | AMBIGUOUS | RULE | Foreign exchange volumes climbed 15 percent. |
| 15 | pos | Penalty | AMBIGUOUS | RULE | Financial penalty of £2.5 million levied. |
| 30 | pos | Inflation | AMBIGUOUS | RULE | Inflation stabilized at 2.0 percent. |
| 34 | pos | Policy Rate | AMBIGUOUS | RULE | Policy Rate lowered by 25 basis points. |
| 36 | pos | Penalty | AMBIGUOUS | RULE | Penalty assessed at $750,000 for late filing. |
| 38 | pos | Inflation | AMBIGUOUS | RULE | Inflation reached 5.0 percent, the highest in a de |
| 40 | pos | Unemployment | AMBIGUOUS | RULE | Unemployment stood at 4.8 percent in May. |
| 43 | pos | Penalty | AMBIGUOUS | RULE | Penalty finalized at £1.8 million for misconduct. |
| 44 | pos | Gross Domestic Produ | AMBIGUOUS | RULE | GDP advanced 2.9 percent for the full year. |
| 47 | pos | Unemployment | AMBIGUOUS | RULE | Unemployment improved to 3.9 percent. |
| 85 | neg | Foreign Exchange | TRUE_SUBJECT | RULE | Construction Report. FX turnover in international  |
| 116 | amb | Foreign Exchange | TRUE_SUBJECT | RULE | FX turnover data is collected semi-annually. |
| 131 | amb | Penalty | TRUE_SUBJECT | RULE | Penalty guidelines were published for consultation |
| 135 | amb | Unemployment | TRUE_SUBJECT | RULE | Unemployment registrations increased marginally. |
| 141 | amb | Policy Rate | TRUE_SUBJECT | RULE | Policy Rate corridor was maintained as before. |

## Per-Case Details

### Case #10 — NO_CANDIDATE (DATA)

- **Text:** "Bank Rate held at 4.25 percent in August."
- **Expected:** TRUE_SUBJECT | **Judgment:** NO_CANDIDATE
- **Event:**  | **Measurement:**  | **Verb:** 
- **Failure class:** `DATA`
- **Reason:** Candidate 'NO_CANDIDATE' alias not in text. DATA_GAP.

### Case #13 — Foreign Exchange (RULE)

- **Text:** "Foreign exchange volumes climbed 15 percent."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'climbed' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #15 — Penalty (RULE)

- **Text:** "Financial penalty of £2.5 million levied."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'levied' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #30 — Inflation (RULE)

- **Text:** "Inflation stabilized at 2.0 percent."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'stabilized' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #34 — Policy Rate (RULE)

- **Text:** "Policy Rate lowered by 25 basis points."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** INSUFFICIENT | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'lowered' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #36 — Penalty (RULE)

- **Text:** "Penalty assessed at $750,000 for late filing."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** INSUFFICIENT | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'assessed' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #38 — Inflation (RULE)

- **Text:** "Inflation reached 5.0 percent, the highest in a decade."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'reached' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #40 — Unemployment (RULE)

- **Text:** "Unemployment stood at 4.8 percent in May."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'stood' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #43 — Penalty (RULE)

- **Text:** "Penalty finalized at £1.8 million for misconduct."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'finalized' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #44 — Gross Domestic Product (RULE)

- **Text:** "GDP advanced 2.9 percent for the full year."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'advanced' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #47 — Unemployment (RULE)

- **Text:** "Unemployment improved to 3.9 percent."
- **Expected:** TRUE_SUBJECT | **Judgment:** AMBIGUOUS
- **Event:** WEAK | **Measurement:** STRONG | **Verb:** 
- **Failure class:** `RULE`
- **Reason:** Text contains event verb 'improved' that is NOT in the production _EVENT_VERBS lexicon for the candidate's registry type. event=WEAK because the rule's verb vocabulary is too narrow. The evidence IS in the text — the rule cannot see it.

### Case #85 — Foreign Exchange (RULE)

- **Text:** "Construction Report. FX turnover in international projects."
- **Expected:** UNKNOWN | **Judgment:** TRUE_SUBJECT
- **Event:** STRONG | **Measurement:** INSUFFICIENT | **Verb:** turnover
- **Failure class:** `RULE`
- **Reason:** Rule promoted 'Foreign Exchange' to TRUE_SUBJECT despite the heading naming a competing topic. The event=STRONG signal fired because verb 'turnover' appeared near the candidate, but the signal is about the DOCUMENT's event, not about the CANDIDATE being the subject. Signal strength ≠ Subject attribution. RULE_GAP — the rule conflates 'strong evidence present in document' with 'strong evidence about candidate.'

### Case #116 — Foreign Exchange (RULE)

- **Text:** "FX turnover data is collected semi-annually."
- **Expected:** AMBIGUOUS | **Judgment:** TRUE_SUBJECT
- **Event:** STRONG | **Measurement:** INSUFFICIENT | **Verb:** turnover
- **Failure class:** `RULE`
- **Reason:** Rule promoted to TRUE_SUBJECT because verb 'turnover' matched near candidate. But the candidate is a NOUN MODIFIER in a larger phrase (e.g., 'FX turnover data', 'Penalty guidelines'). The verb applies to the head noun, not the candidate. RULE_GAP — the rule doesn't check syntactic subject-attribution.

### Case #131 — Penalty (RULE)

- **Text:** "Penalty guidelines were published for consultation."
- **Expected:** AMBIGUOUS | **Judgment:** TRUE_SUBJECT
- **Event:** STRONG | **Measurement:** INSUFFICIENT | **Verb:** published
- **Failure class:** `RULE`
- **Reason:** Rule promoted to TRUE_SUBJECT because verb 'published' matched near candidate. But the candidate is a NOUN MODIFIER in a larger phrase (e.g., 'FX turnover data', 'Penalty guidelines'). The verb applies to the head noun, not the candidate. RULE_GAP — the rule doesn't check syntactic subject-attribution.

### Case #135 — Unemployment (RULE)

- **Text:** "Unemployment registrations increased marginally."
- **Expected:** AMBIGUOUS | **Judgment:** TRUE_SUBJECT
- **Event:** STRONG | **Measurement:** INSUFFICIENT | **Verb:** increased
- **Failure class:** `RULE`
- **Reason:** Rule promoted to TRUE_SUBJECT because verb 'increased' matched near candidate. But the candidate is a NOUN MODIFIER in a larger phrase (e.g., 'FX turnover data', 'Penalty guidelines'). The verb applies to the head noun, not the candidate. RULE_GAP — the rule doesn't check syntactic subject-attribution.

### Case #141 — Policy Rate (RULE)

- **Text:** "Policy Rate corridor was maintained as before."
- **Expected:** AMBIGUOUS | **Judgment:** TRUE_SUBJECT
- **Event:** STRONG | **Measurement:** INSUFFICIENT | **Verb:** maintained
- **Failure class:** `RULE`
- **Reason:** Rule promoted to TRUE_SUBJECT because verb 'maintained' matched near candidate. But the candidate is a NOUN MODIFIER in a larger phrase (e.g., 'FX turnover data', 'Penalty guidelines'). The verb applies to the head noun, not the candidate. RULE_GAP — the rule doesn't check syntactic subject-attribution.

## Final Verdict

**PASS**

**Recommendation:** Subject judgment rule needs lexicon expansion and signal-attribution check — not architectural redesign.

Production files changed: 0
Tests: 338/338 PASS

---
**STOP. Do not fix cases or re-run V48AB.**
