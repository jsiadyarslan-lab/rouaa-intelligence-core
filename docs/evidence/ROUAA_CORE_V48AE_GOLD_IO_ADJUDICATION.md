# V48AE — Gold IO Semantic Human Adjudication

## A. Gold IO Adjudication Table

---

### IO 1: io-abed2ad81fcd4f55

| Field | Value | Verdict |
|-------|-------|---------|
| io_id | io-abed2ad81fcd4f55 | |
| fact_metric | percentage_statistic | METRIC_CORRECT (generic statistical percentage) |
| fact_value | 1.5 | VALUE_CORRECT (excerpt shows "+1.5%") |
| evidence_excerpt | "U.S. Economy at a Glance Table National Economic Accounts GDP (Advance Estimate), 2nd Quarter 2026 Q2 2026 (Adv) +1.5% Q" | EVIDENCE_CORRECT |
| evidence_supports_value | YES — excerpt contains "+1.5%" which matches fact_value 1.5 | |
| temporal_data | publication_time: None; reference_period: None | TEMPORAL_PROPAGATION_GAP |
| canonical_url | https://www.bea.gov/news/glance | SOURCE_CORRECT |
| human_verifiable | YES — human can open URL, find "+1.5%", verify GDP advance estimate | HUMAN_VERIFIABLE |
| **final gold status** | **VALID_GOLD** | |
| failure reason | None — temporal gap is a gap, not a failure of the core claim | |
| chain notes | 31 facts in chain; all labeled percentage_statistic or usd_amount — metric labels are generic but not wrong for BEA statistical tables | |

---

### IO 2: io-0db41fde8c803040

| Field | Value | Verdict |
|-------|-------|---------|
| io_id | io-0db41fde8c803040 | |
| fact_metric | percentage_statistic | METRIC_CORRECT |
| fact_value | 5.6 | VALUE_CORRECT (excerpt shows "–5.6%") |
| evidence_excerpt | "U.S. International Trade in Goods and Services Deficit Deficit: $73.3 Billion –5.6%° Exports: $314.7 Billion –0.9%° Impo" | EVIDENCE_CORRECT |
| evidence_supports_value | YES — excerpt contains "–5.6%" which matches fact_value 5.6 | |
| temporal_data | publication_time: 2026-08-04T12:30:00Z; reference_period: None | TEMPORAL_PARTIAL (publication present, reference period absent) |
| canonical_url | https://www.bea.gov/news/2026/us-international-trade-goods-and-services-june-2026 | SOURCE_CORRECT |
| human_verifiable | YES — human can open URL, find "–5.6%" trade deficit change | HUMAN_VERIFIABLE |
| **final gold status** | **VALID_GOLD** | |
| failure reason | None | |
| chain notes | 78 facts; large extraction from a detailed trade report | |

---

### IO 3: io-1ca8a75ee22968f7

| Field | Value | Verdict |
|-------|-------|---------|
| io_id | io-1ca8a75ee22968f7 | |
| fact_metric | action_type | METRIC_QUESTIONABLE (action_type is not a standard financial metric) |
| fact_value | disgorgement | VALUE_QUESTIONABLE (disgorgement is a remedy sought, not a penalty amount or rate) |
| evidence_excerpt | "It also charges Spaventa with control person liability and aiding and abetting violations. The complaint seeks permanent" | WEAK_EVIDENCE_EXCERPT |
| evidence_supports_value | PARTIAL — the excerpt mentions "charges" and is from a legal filing, but the excerpt is truncated before "disgorgement" appears. The word "disgorgement" does NOT appear in this excerpt. | |
| temporal_data | publication_time: 2026-08-14T20:16:34Z; reference_period: None | TEMPORAL_PARTIAL |
| canonical_url | https://www.sec.gov/newsroom/press-releases/2026-75-sec-charges-boiler-room-operator... | SOURCE_CORRECT |
| human_verifiable | PARTIAL — human can open URL but the evidence_excerpt doesn't contain the word "disgorgement"; human must search the full document to verify | NON_VERIFIABLE_EVIDENCE |
| **final gold status** | **INVALID_GOLD** | |
| failure reason | WEAK_EVIDENCE_EXCERPT + NON_VERIFIABLE_EVIDENCE — the evidence excerpt does not contain the fact value "disgorgement"; the excerpt is a mid-sentence fragment from a random position | |

---

### IO 4: io-86eb51402109b465

| Field | Value | Verdict |
|-------|-------|---------|
| io_id | io-86eb51402109b465 | |
| fact_metric | action_type | METRIC_QUESTIONABLE |
| fact_value | disgorgement | VALUE_QUESTIONABLE |
| evidence_excerpt | "Smith, Jr., Associate Director of the SEC's New York Regional Office. "In reality, the Jersey Shore triumvirate took adv" | WEAK_EVIDENCE_EXCERPT |
| evidence_supports_value | NO — the excerpt is a quote from an SEC official about the fraud; it does NOT mention "disgorgement" | |
| temporal_data | publication_time: 2026-08-13T20:32:19Z; reference_period: None | TEMPORAL_PARTIAL |
| canonical_url | https://www.sec.gov/newsroom/press-releases/2026-74-sec-charges-toms-river-trio... | SOURCE_CORRECT |
| human_verifiable | NO — the evidence_excerpt doesn't support the fact_value at all | NON_VERIFIABLE_EVIDENCE |
| **final gold status** | **INVALID_GOLD** | |
| failure reason | WEAK_EVIDENCE_EXCERPT + NON_VERIFIABLE_EVIDENCE — the excerpt is a narrative quote, not the legal claim for disgorgement | |

---

### IO 5: io-f899fb5c1631e12c

| Field | Value | Verdict |
|-------|-------|---------|
| io_id | io-f899fb5c1631e12c | |
| fact_metric | policy_rate | **SEMANTIC_METRIC_MISMATCH** — the document is about cash acceptance rates, NOT policy rates |
| fact_value | 90 | VALUE_INCORRECT_FOR_METRIC — 90 is a cash acceptance percentage, not a policy rate |
| evidence_excerpt | "This compares with 90% in 2024, suggesting that cash acceptance has rebounded after the decline observed during and afte" | EVIDENCE_CORRECT (for cash acceptance, NOT for policy_rate) |
| evidence_supports_value | NO — the excerpt supports "90% cash acceptance" not "policy_rate = 90" | |
| temporal_data | publication_time: 2026-08-13T09:00:00Z; reference_period: None | TEMPORAL_PARTIAL |
| canonical_url | https://www.ecb.europa.eu//press/pr/date/2026/html/ecb.pr260813~389729d6a9.en.html | SOURCE_CORRECT (ECB press release — but about cash acceptance, not monetary policy) |
| human_verifiable | NO — a human opening this URL would find a study about payment attitudes, not a policy rate decision | PROVENANCE_ONLY_NOT_SEMANTIC |
| **final gold status** | **INVALID_GOLD** | |
| failure reason | SEMANTIC_METRIC_MISMATCH + VALUE_EXCERPT_MISMATCH + PROVENANCE_ONLY_NOT_SEMANTIC — the extraction pattern matched "90" near ECB content and labeled it "policy_rate" when the document is about cash acceptance percentages | |
| chain notes | 6 facts all labeled "policy_rate" with values 90, 88, 36, 68, 25, 13 — ALL are cash acceptance/payment statistics, NONE are policy rates | |

---

### IO 6: io-be817f73577ff8e1

| Field | Value | Verdict |
|-------|-------|---------|
| io_id | io-be817f73577ff8e1 | |
| fact_metric | percentage_statistic | METRIC_CORRECT (generic percentage) |
| fact_value | 90 | **VALUE_EXCERPT_MISMATCH** — the excerpt says "92%" not "90%" |
| evidence_excerpt | "In 2026, 92% of companies selling goods and services in physical locations in the retail trade, restaurants and cafés, h" | EVIDENCE_CORRECT (but for 92, not 90) |
| evidence_supports_value | NO — the excerpt contains "92%" but the fact_value is "90" | |
| temporal_data | publication_time: 2026-08-13T09:00:00Z; reference_period: None | TEMPORAL_PARTIAL |
| canonical_url | https://www.ecb.europa.eu//press/pr/date/2026/html/ecb.pr260813~389729d6a9.en.html | SOURCE_CORRECT |
| human_verifiable | NO — a human would find 92% in the text, not 90% | VALUE_EXCERPT_MISMATCH |
| **final gold status** | **INVALID_GOLD** | |
| failure reason | VALUE_EXCERPT_MISMATCH — the fact_value (90) does not match the evidence_excerpt (92%); the extraction captured a different number than what the excerpt shows | |
| chain notes | Same document as IO5; 6 facts with values 90, 88, 36, 68, 25, 13 — the 90 may have been extracted from a different sentence mentioning 90% | |

---

## B. Gold Set Reconciliation

| IO | Source | Final Status | Failure Reason |
|----|--------|-------------|----------------|
| io-abed2ad81fcd4f55 | BEA | **VALID_GOLD** | None (temporal gap noted but not blocking) |
| io-0db41fde8c803040 | BEA | **VALID_GOLD** | None |
| io-1ca8a75ee22968f7 | SEC | **INVALID_GOLD** | WEAK_EVIDENCE_EXCERPT + NON_VERIFIABLE_EVIDENCE |
| io-86eb51402109b465 | SEC | **INVALID_GOLD** | WEAK_EVIDENCE_EXCERPT + NON_VERIFIABLE_EVIDENCE |
| io-f899fb5c1631e12c | ECB | **INVALID_GOLD** | SEMANTIC_METRIC_MISMATCH + PROVENANCE_ONLY_NOT_SEMANTIC |
| io-be817f73577ff8e1 | ECB | **INVALID_GOLD** | VALUE_EXCERPT_MISMATCH |

**VALID_GOLD: 2/6**
**INVALID_GOLD: 4/6**

---

## C. Failure Distribution

| Failure Type | Count | Affected IOs |
|-------------|------:|-------------|
| SEMANTIC_METRIC_MISMATCH | 1 | IO5 |
| VALUE_EXCERPT_MISMATCH | 1 | IO6 |
| WEAK_EVIDENCE_EXCERPT | 2 | IO3, IO4 |
| NON_VERIFIABLE_EVIDENCE | 2 | IO3, IO4 |
| TEMPORAL_PROPAGATION_GAP | 3 | IO1, IO3, IO4 (publication_time=None or reference_period=None) |
| PROVENANCE_ONLY_NOT_SEMANTIC | 1 | IO5 |

---

## Root Cause Analysis

The 4 invalid IOs share a common upstream cause: **extraction layer quality**.

### IO5 + IO6 (ECB): Extraction pattern greediness
The ECB press release is about **payment attitudes** (cash acceptance, card payments, mobile payments). The extraction patterns matched numbers in this document and labeled them `policy_rate` and `percentage_statistic` because:
- The patterns are keyword-agnostic — they match any number near ECB content
- The `policy_rate` pattern matched "90" because the number appeared in an ECB document
- The `percentage_statistic` pattern captured "90" from one sentence and "92" from another, creating a value-excerpt mismatch

### IO3 + IO4 (SEC): Evidence excerpt positioning
The SEC press releases contain legal charges including "disgorgement" — but the evidence excerpt was captured at the position where the regex matched, not at the position where "disgorgement" appears in the text. The excerpts are:
- IO3: "It also charges Spaventa..." (mid-charge description)
- IO4: "Smith, Jr., Associate Director..." (a quote about the fraud)

Neither excerpt contains the word "disgorgement."

### IO1 + IO2 (BEA): Valid
The BEA statistical releases contain tabular data where the extracted values directly appear in the evidence excerpts. The `percentage_statistic` metric is semantically appropriate for GDP growth rates and trade deficit changes. These IOs are human-verifiable.

---

## Decision

**GOLD SET PARTIALLY VALID — ADJUDICATED SUBSET ONLY**

- 2/6 IOs are VALID_GOLD (IO1 BEA GDP, IO2 BEA Trade)
- 4/6 IOs are INVALID_GOLD (IO3-4 SEC evidence excerpts; IO5-6 ECB semantic mismatch)
- The Gold Set cannot be used as human ground truth without rebuilding the invalid IOs
- The root cause is extraction-layer quality, not Subject Judgment or semantic architecture

---

## Impact on Previous Gates

| Gate | Previous Verdict | Revised Understanding |
|------|-----------------|----------------------|
| Intelligence Asset Gate | PASSED | Passed for STRUCTURAL integrity (provenance chain, HTTP delivery, persistence). Did NOT verify SEMANTIC correctness of fact values. |
| Reuse Gate | PASSED | Passed for HTTP contract reuse. The reused IOs may carry incorrect semantic content. |
| V48AC (Subject Judgment) | PASS | Subject Judgment failures are real, but the Gold Set used for adjudication was partially invalid. The 2 BEA IOs are trustworthy; the 4 others are not. |

---

## What Must Happen Before Any Benchmark

1. **Extraction layer repair**: Fix the patterns that label cash acceptance percentages as `policy_rate`
2. **Evidence excerpt quality**: Ensure excerpts contain the fact_value verbatim
3. **Temporal propagation**: Ensure temporal_data appears in the verification artifact, not just in the stored IO
4. **Re-adjudicate Gold Set**: After extraction repair, re-run this gate on the rebuilt IOs
5. **Only then**: Run any benchmark that depends on Gold Set as ground truth

---

## Production Files Changed: 0

No production code was modified. This is an adjudication-only artifact.

## Tests: Unchanged (no new tests run — this is human adjudication)

---

**STOP.** Do not repair extraction. Do not modify resolve_subject. Do not re-run benchmarks. Wait for explicit directive on whether to repair extraction layer or proceed with the 2 valid IOs only.
