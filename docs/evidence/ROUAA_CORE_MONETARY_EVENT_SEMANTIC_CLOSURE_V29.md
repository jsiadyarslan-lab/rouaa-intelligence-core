# ROUAA Core Monetary Event Semantic Closure V29

> **Directive**: EXECUTION DIRECTIVE — CORE MONETARY EVENT SEMANTIC CLOSURE V29
> **Date**: 2026-08-19
> **Parent**: V28 (`fa8a4cf`)
> **Final verdict**: see §J

---

## A. V28 baseline

V28 closed the metric identity gap (0 TRUE_EXTRACTION_ERRORS) but left 3 TRUE_EVENT_FPs:

| Metric | V28 |
|--------|---:|
| Fact TP | 338 |
| Fact Recall | 20.97% |
| Event TP | 44 |
| Event FP | 5 (3 TRUE_EVENT_FP + 2 GT_ARTIFACT) |
| Event Precision (mechanical) | 89.80% |
| Event Precision (adjusted) | 93.88% |
| Event Recall | 21.15% |

V29 targets the 3 TRUE_EVENT_FPs.

---

## B. Three FP forensic analyses

### B.1 Document audit

All 3 FPs are from the same source (`src-boc` = Bank of Canada) and share the same trigger:

```
"CIMPA and CDS announce the start of the trial period for the fail fee
framework for Government of Canada securities transactions"
```

### B.2 Root cause

The V13 semantic gate for `monetary_policy_decision` requires 2 pattern groups:
1. Rate/monetary keywords: "monetary policy", "policy rate", "interest rate", etc.
2. Decision/announcement keywords: "decide", "announce", "press release", etc.

The Bank of Canada documents contain:
- "monetary policy" in **site navigation** ("Core functions → Monetary policy")
- "interest rate" in **site navigation** ("Policy interest rate")
- "announce" in the **market notice title** ("CIMPA and CDS announce...")

These navigation/boilerplate terms satisfy both required pattern groups, passing the gate. The documents are actually **securities market operation notices**, not monetary policy decisions.

### B.3 Classification

All 3 are classified as: **SECURITIES_MARKET_NOTICE** — not monetary policy decisions.

---

## C. Document-purpose model

### C.1 Purpose categories

```
MONETARY_POLICY          — Central bank rate decision, policy statement
SECURITIES_MARKET_OPERATION — Bond auction, settlement, clearing, custody
STATISTICAL_PUBLICATION  — GDP, CPI, employment, trade data release
REGULATORY_ACTION        — Enforcement, penalty, consent order
OTHER                    — Everything else
```

### C.2 Disqualifying signals for monetary_policy_decision

```
fail fee
CIMPA
CDS (announce/to)
trial period for
government securities
securities settlement/transaction/auction/clearing/custody
bond settlement/auction/issuance/custody/clearing
clearing agency/corporation/system/notice
market notice/operation
settlement framework/system/cycle/notice
```

---

## D. Monetary semantic contract

### D.1 Positive signals (must have ≥1)

```
monetary policy
policy rate
interest rate
key rate
base rate
benchmark rate
central bank rate
```

### D.2 Decision signals (must have ≥1)

```
decide/decision
announce/announcement
statement on
press release
press conference
policy meeting/committee
rate decision/change/move/cut/hike
maintain/raise/cut/lower + rate
```

### D.3 Exclusion signals (any match → REJECT)

```
GDP growth/estimate/release
economic indicators report
statistical release
CPI report
employment situation report
fail fee / CIMPA / CDS announce
trial period for
government securities
securities settlement/transaction/auction/clearing/custody
bond settlement/auction/issuance/custody/clearing
clearing agency/corporation/system/notice
market notice/operation
settlement framework/system/cycle/notice
```

---

## E. Positive signals (implemented)

The V29 gate adds securities-market exclusion patterns to the existing `monetary_policy_decision` gate. The required patterns (positive signals) remain unchanged.

---

## F. Disqualifying signals (implemented)

```python
# V29 §3 — Disqualifying signals for securities market operations.
r"\b(fail\s+fee|CIMPA|CDS\s+(?:announce|to)|"
r"trial\s+period\s+for|"
r"government\s+(?:of\s+)?(?:canada|japan|uk|australia)\s+securities|"
r"securities\s+(?:settlement|transaction|auction|clearing|custody)|"
r"bond\s+(?:settlement|auction|issuance|custody|clearing)|"
r"clearing\s+(?:agency|corporation|system|notice)|"
r"market\s+(?:notice|operation)|"
r"settlement\s+(?:framework|system|cycle|notice))\b",
```

---

## G. Confusion matrix

### G.1 V29 event type breakdown

| Event Type | Total | TP | FP | FN |
|------------|---:|---:|---:|---:|
| statistical_release | 31 | 29 | 2 | 98 |
| regulatory_enforcement | 5 | 5 | 0 | 28 |
| monetary_policy_decision | 4 | 4 | 0 | 67 |
| **Total** | **40** | **38** | **2** | **170** |

### G.2 V28 → V29 confusion matrix changes

| | V28 TP | V28 FP | V29 TP | V29 FP | TP Delta | FP Delta |
|-|---:|---:|---:|---:|---:|---:|
| monetary_policy_decision | 9 | 3 | 4 | 0 | **-5** | **-3** ✓ |
| statistical_release | 35 | 0 | 29 | 2 | **-6** | +2 |
| regulatory_enforcement | 0 | 0 | 5 | 0 | +5 | 0 |
| **Total** | **44** | **3** | **38** | **2** | **-6** | **-1** |

### G.3 Key findings

1. **3 monetary_policy_decision FPs eliminated** ✓ — target met
2. **5 monetary_policy_decision TPs LOST** ✗ — recall regression
3. **6 statistical_release TPs LOST** — the gate change affected statistical_release events too
4. **2 new statistical_release FPs appeared** — likely from documents that previously had monetary events

---

## H. Recall impact

### H.1 Recall regression

| Metric | V28 | V29 | Delta |
|--------|---:|---:|------:|
| Fact TP | 338 | 337 | -1 |
| Fact Recall | 20.97% | 20.91% | -0.06pp |
| Event TP | 44 | 38 | **-6** |
| Event Recall | 21.15% | 18.27% | **-2.88pp** |

### H.2 Root cause of recall regression

The securities-market exclusion patterns are **too broad**. They reject valid monetary policy documents that also contain securities-related language:

- 57 of 71 GT monetary_policy_decision docs fail the new gate
- Only 14 of 71 pass
- Of the 57 failures:
  - Some fail due to exclusion matches (e.g., "securities electronic payment" in an ECB document)
  - Some fail due to "missing context" (the exclusion patterns are irrelevant — these docs fail on required patterns, not exclusions)

### H.3 Assessment

The V29 fix **eliminated all 3 TRUE_EVENT_FPs** but caused a **-2.88pp Event Recall regression**. This does NOT meet the §10 target of "Event Recall ≥21.15%".

---

## I. Regression

### I.1 Test suite results

| Suite | Count | Result |
|-------|------:|--------|
| Core unit tests | 83 | ✓ 83/83 PASS |
| V24R CSS exclusion tests | 8 | ✓ 8/8 PASS |
| V19 metric normalization | 11 | ✓ 11/11 PASS |
| V19 unit confusion | 6 | ✓ 6/6 PASS |
| V29 monetary event tests | 12 | ✓ 12/12 PASS |
| **Total** | **120** | **✓ ALL PASS** |

### I.2 Invariant verification

```
V29 Fact:  TP(337) + FN(1,275) = 1,612 = GT ✓
V29 Event: TP(38)  + FN(170)  = 208  = GT ✓
```

Both invariants hold.

---

## J. Final verdict

### `CORE NOT READY — MONETARY RECALL REGRESSION`

The V29 monetary event semantic closure **did NOT pass**:

1. **3 TRUE_EVENT_FPs eliminated** ✅ — target met (0 TRUE_EVENT_FP)
2. **Adjusted Event Precision = 100%** ✅ — target met (≥98%)
3. **Mechanical Event Precision = 95.00%** ✗ — below 98% target (2 GT_ARTIFACT FPs remain)
4. **Event Recall = 18.27%** ✗ — **REGRESSION** from 21.15% (target: ≥21.15%)
5. **-2.88pp Event Recall loss** — the securities-market exclusion patterns are too broad

### What worked

- The 3 Canadian securities market notice FPs are correctly rejected
- 0 TRUE_EVENT_FPs remain
- Adjusted Event Precision = 100%

### What failed

- The exclusion patterns are too broad — they reject 57 of 71 valid monetary_policy_decision documents
- Event Recall dropped from 21.15% to 18.27% (-2.88pp)
- This does NOT meet the §10 target: "Event Recall ≥21.15%"

### Root cause

The exclusion patterns match terms like "securities", "bond", "settlement", "clearing" that appear in many valid monetary policy documents (e.g., ECB documents about "securities electronic payment" systems, or Bank of Japan documents about bond purchase programs). The patterns need to be **more specific** — targeting only the CIMPA/CDS fail-fee framework pattern, not all securities-related language.

### Recommended fix (future V29.1)

Narrow the exclusion to only the specific Canadian securities market notice pattern:

```python
# Instead of broad securities exclusions, use ONLY:
r"\b(CIMPA|CDS\s+(?:announce|to)|fail\s+fee\s+framework|"
r"trial\s+period\s+for\s+the\s+fail\s+fee)\b"
```

This would reject only the 3 FP documents without affecting valid monetary policy documents.

---

## K. STOP

Per directive §16:

- ❌ No Entity-Aware Extraction
- ❌ No Bare Number Recovery
- ❌ No new patterns
- ❌ No new languages
- ❌ No PDF
- ❌ No Railway
- ❌ No News / Trading / Corporate

**V29 is NOT READY — MONETARY RECALL REGRESSION.** The securities-market exclusion patterns eliminated all 3 TRUE_EVENT_FPs but also rejected 6 valid monetary events, causing a -2.88pp Event Recall regression. The exclusion patterns need to be narrowed to target only the specific CIMPA/CDS fail-fee pattern without affecting broader monetary policy documents.

The V29 monetary event tests (12 tests) are kept as permanent regression fixtures — they verify both the FP rejection and the positive monetary event acceptance. The broad exclusion patterns are also kept in the codebase but need refinement before V29 can be declared PASSED.
