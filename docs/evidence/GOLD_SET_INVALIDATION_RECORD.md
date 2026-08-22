# Gold Set Invalidation Record

## Date: 2026-08-21
## Authority: Gold Set Rebuild V1.1 Directive (Article 1)

## Invalidation

The Gold Set published at commit `e362aaa` is **INVALIDATED IN FULL**. It must not be used as reference in any gate, benchmark, or report effective immediately.

## Reasons for Invalidation (6 IOs)

### IO1: io-abed2ad81fcd4f55 (BEA)
**Failure: WEAK_SOURCE_ANCHOR**
- `canonical_url` = `https://www.bea.gov/news/glance` — this is a permanent "at-a-glance" page that changes content whenever BEA updates. It is NOT a dated, stable release. The content at this URL changes over time, making byte-for-byte verification impossible.
- **Note**: The fact_value (1.5) and evidence_excerpt are correct for the snapshot at the time of extraction, but the URL is not a stable reference.

### IO2: io-0db41fde8c803040 (BEA)
**Failure: SIGN_INFORMATION_LOSS**
- The original document states "–5.6%" (negative change in trade deficit), but the stored `fact_value` = `5.6` (positive, no sign). The negative sign was lost during extraction, reversing the semantic meaning of the statistic.

### IO3: io-1ca8a75ee22968f7 (SEC)
**Failure: EVIDENCE_DOES_NOT_CONTAIN_CLAIM**
- `fact_value` = `disgorgement` but the `evidence_excerpt` ("It also charges Spaventa with control person liability and aiding and abetting violations. The complaint seeks permanent") does NOT contain the word "disgorgement." The excerpt is a mid-sentence fragment that does not support the claimed fact.

### IO4: io-86eb51402109b465 (SEC)
**Failure: EVIDENCE_COMPLETELY_UNRELATED_TO_CLAIM**
- `fact_value` = `disgorgement` but the `evidence_excerpt` ("Smith, Jr., Associate Director of the SEC's New York Regional Office. "In reality, the Jersey Shore triumvirate took adv") is a narrative quote about the fraud, with no connection to the legal remedy of disgorgement. The excerpt is from a completely different part of the document.

### IO5: io-f899fb5c1631e12c (ECB)
**Failure: SEMANTIC_METRIC_MISMATCH + TEMPORAL_CONFUSION**
- `fact_metric` = `policy_rate` and `fact_value` = `90`, but the `evidence_excerpt` states "This compares with 90% in 2024, suggesting that cash acceptance has rebounded." The document is an ECB study on **payment attitudes** (cash acceptance percentages), NOT a monetary policy decision. The value `90` represents `90% cash acceptance in 2024` — a comparison value, not a current policy rate. The metric label is completely wrong.
- Additionally, 5 other facts in the chain (values 88, 36, 68, 25, 13) are ALL labeled `policy_rate` — none are actual policy rates.

### IO6: io-be817f73577ff8e1 (ECB)
**Failure: VALUE_EXCERPT_MISMATCH**
- `fact_value` = `90` but the `evidence_excerpt` says "In 2026, 92% of companies..." — the value `90` does not appear in the excerpt. The value `92` appears instead. The extraction captured a number from a different sentence than the one in the evidence excerpt.
- Same document as IO5 (ECB payment attitudes study).

## Summary

| IO | Source | Failure Type | Core Issue |
|----|--------|--------------|------------|
| IO1 | BEA | WEAK_SOURCE_ANCHOR | URL is a permanent changing page |
| IO2 | BEA | SIGN_INFORMATION_LOSS | –5.6% stored as 5.6 |
| IO3 | SEC | EVIDENCE_DOES_NOT_CONTAIN_CLAIM | Excerpt missing the fact value |
| IO4 | SEC | EVIDENCE_COMPLETELY_UNRELATED_TO_CLAIM | Excerpt is a random narrative fragment |
| IO5 | ECB | SEMANTIC_METRIC_MISMATCH | Cash acceptance % labeled as policy_rate |
| IO6 | ECB | VALUE_EXCERPT_MISMATCH | Value 90 vs excerpt 92% |

## Root Cause

Extraction-layer quality: pattern greediness, sign loss, excerpt positioning, and metric-label mismatches. NOT Subject Judgment or semantic architecture.
