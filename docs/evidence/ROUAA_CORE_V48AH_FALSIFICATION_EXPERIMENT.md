# V48AH — Targeted Root-Cause Falsification Experiment
**Executed at (UTC):** 2026-08-21T03:46:32Z
**Base commit:** `0c80e8c` (V48AH) on `recovery/post-v37-intelligence-stack`
**Production unchanged:** YES — no production files modified.
**V2.1 unchanged:** YES — `v48af_v21_evaluator.py` hash `80d857159c6ab416...` (matches V48AF).
**V48AG holdout LOCKED:** SHA256 `bbc1ac6ccea1c3e7...` — diagnostic only, NOT for tuning.
## §1 Hypotheses
### H1 — MODIFIER ambiguity
```role=MODIFIER + effective_event=WEAK + head_noun ∈ ADMINISTRATIVE_HEAD_NOUNS  → AMBIGUOUS (instead of CONTEXT_ONLY)```### H2 — Policy Rate event gap
```Pattern-based candidate injection:  - `held at <number>%` → strong Policy Rate event  - `reduce ... by ... basis points to <number>%` → strong Policy Rate eventWITHOUT adding registry aliases.```## §2 Explanatory Coverage of 24 GENUINE_SEMANTIC_LIMITATION Cases
| Hypothesis | Explained | Not Explained | Verdict ||-----------|----------:|--------------:|---------|| H1 | 18/24 | 6/24 | FALSIFIED || H2 | 2/24 | 22/24 | PARTIALLY_EXPLANATORY || H1+H2 | 20/24 | 4/24 | FALSIFIED |### H1 Explained Case IDs
`[76, 78, 82, 83, 87, 89, 92, 93, 94, 96, 98, 99, 100, 101, 102, 103, 108, 115]`
### H1 Not Explained Case IDs
`[3, 31, 86, 91, 106, 112]`
### H2 Explained Case IDs
`[3, 31]`
### H2 Not Explained Case IDs
`[76, 78, 82, 83, 86, 87, 89, 91, 92, 93, 94, 96, 98, 99, 100, 101, 102, 103, 106, 108, 112, 115]`
### H1+H2 Explained Case IDs
`[3, 31, 76, 78, 82, 83, 87, 89, 92, 93, 94, 96, 98, 99, 100, 101, 102, 103, 108, 115]`
## §3 Counterexamples (V48AG cases where V2.1 was CORRECT but variant made it WRONG)
| Hypothesis | Counterexamples ||-----------|----------------:|| H1 | 11 || H2 | 0 || H1+H2 | 11 |### H1 Counterexample Details
| # | Category | Human | V2.1 | H1 | Text ||---|----------|-------|------|-----|------|| 117 | negative | CONTEXT |  | AMBIGUOUS | Penalty guidelines were issued for industry consultation by  || 119 | negative | CONTEXT |  | AMBIGUOUS | Policy rate corridor was maintained at its existing operatio || 121 | negative | CONTEXT |  | AMBIGUOUS | GDP deflator series was revised in the latest national accou || 122 | negative | CONTEXT |  | AMBIGUOUS | CPI basket composition was updated for the new index series. || 126 | negative | CONTEXT |  | AMBIGUOUS | Inflation targeting framework was reaffirmed in the central  || 130 | negative | CONTEXT |  | AMBIGUOUS | Foreign exchange reserves position was described as adequate || 131 | negative | CONTEXT |  | AMBIGUOUS | Penalty framework review was the subject of committee delibe || 138 | negative | CONTEXT |  | AMBIGUOUS | Penalty appeal process was detailed in the regulatory enforc || 140 | negative | CONTEXT |  | AMBIGUOUS | Inflation data collection was refined per the new statistica || 147 | negative | CONTEXT |  | AMBIGUOUS | Inflation expectations indicator was added to the central ba || 149 | negative | CONTEXT |  | AMBIGUOUS | Unemployment statistics methodology was aligned with the ILO |## §4 H1 Discriminative Test
**Is ADMINISTRATIVE_HEAD_NOUN discriminative?** NO

H1 changed 35 V48AG CONTEXT cases (human=CONTEXT, V2.1=CONTEXT_ONLY=correct) to a different judgment. These are COUNTEREXAMPLES — H1 broke cases that V2.1 had correctly classified.
### Changed CONTEXT Cases
| # | V2.1 | H1 | Text ||---|------|-----|------|| 116 |  | CONTEXT_ONLY | FX turnover data is collected semi-annually by the central b || 117 |  | AMBIGUOUS | Penalty guidelines were issued for industry consultation by  || 118 |  | AMBIGUOUS | Unemployment benefit claims were processed at elevated volum || 119 |  | AMBIGUOUS | Policy rate corridor was maintained at its existing operatio || 120 |  | AMBIGUOUS | Inflation expectation surveys were updated in the central ba || 121 |  | AMBIGUOUS | GDP deflator series was revised in the latest national accou || 122 |  | AMBIGUOUS | CPI basket composition was updated for the new index series. || 123 |  | AMBIGUOUS | Foreign exchange settlement infrastructure was modernized in || 124 |  | CONTEXT_ONLY | Penalty calculation methodology was published in the regulat || 125 |  | AMBIGUOUS | GDP release calendar was published by the statistical office |## §5 Regression Analysis
### V48AE (75 cases — development set)
| Variant | Agreement | Delta ||---------|----------:|------:|| V2.1 baseline | 70/75 | — || H1 | 54/75 | -16 || H2 | 70/75 | +0 || H1+H2 | 54/75 | -16 |### V48AB (150 cases — independent regression)
| Variant | Agreement | Delta ||---------|----------:|------:|| V2.1 baseline | 113/150 | — || H1 | 144/150 | +31 || H2 | 113/150 | +0 || H1+H2 | 144/150 | +31 |## §6 False Promotion / False Rejection
| Hypothesis | False Promotion | False Rejection ||-----------|----------------:|----------------:|| H1 | 1 | 6 || H2 | 1 | 2 || H1+H2 | 1 | 2 |## §7 Verdicts
| Hypothesis | Verdict ||-----------|---------|| H1 | **FALSIFIED** || H2 | **PARTIALLY_EXPLANATORY** || H1+H2 | **FALSIFIED** |## §8 Strategic Implications
- H1 is FALSIFIED — it introduces too many counterexamples.
- H2 is PARTIALLY_EXPLANATORY — it explains the Bank Rate cases but may introduce false promotions.
---
**V48AH is a FALSIFICATION EXPERIMENT, NOT tuning, NOT production integration.**
V2.1 was NOT modified. V48AG holdout was NOT used for tuning. Production was NOT touched.
Per directive: DO NOT create V48AI. DO NOT modify production. STOP — user directive required.
