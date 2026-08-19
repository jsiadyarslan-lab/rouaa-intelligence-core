# ROUAA Core Baseline Matching Closure V23R

> **Directive**: CORE V23→V27 CONTROLLED RECONSTRUCTION — V23R
> **Date**: 2026-08-19
> **Parent**: V22 (`71e7805`) → V28R (`17eea7a`) → **V23R**
> **Final verdict**: see §F

---

## A. V22 baseline

V22 reported these numbers (with the V17 invariant FAILURE):

```
V17: TP=245, FP=53, FN=1,328  →  TP+FN=1,573 ≠ GT(1,612)  ✗
V20: TP=268, FP=53, FN=1,344  →  TP+FN=1,612 = GT(1,612)  ✓
```

V22's matching used set-based deduplication on `(document_id, value)`. The GT contains 1,612 facts across only 681 unique `(document_id, value)` keys — 931 duplicate facts. When V17 produced one core fact matching a GT key with multiplicity M, V22 marked all M GT duplicates as "matched" (not FN), creating a 39-fact "matching gap" for V17.

V23R fixes this with bipartite matching with multiplicities.

---

## B. Canonical fact identity

### B.1 Identity tuple

```
canonical_identity = (document_id, canonical_metric, canonical_value)
```

### B.2 Canonical value normalization

| Input | Canonical | Rule |
|-------|-----------|------|
| `"2.1"` | `"2.1"` | Plain decimal |
| `"2.10"` | `"2.1"` | Trailing zero normalized |
| `"5.25%"` | `"5.25"` | Percent sign stripped (NO scale conversion) |
| `"$74"` | `"74"` | Dollar prefix stripped |
| `"1,000"` | `"1000"` | Thousand separator stripped |
| `"maintain"` | `"maintain"` | Lowercase string |

### B.3 Canonical metric normalization

Reuses V19 corrected metric equivalence ONLY — no new equivalences:
- `percentage` → `percentage_statistic`
- `structured_rate` → `percentage_statistic`
- `basis_points` stays distinct
- `yield_rate` stays distinct
- `volume` stays distinct
- etc.

---

## C. Bipartite matching algorithm

For each canonical identity `I = (doc, canonical_metric, canonical_value)`:

```
GT_count   = multiplicity of I in GT
Core_count = multiplicity of I in Core

TP       += min(GT_count, Core_count)
FN       += max(0, GT_count - Core_count)
FP       += max(0, Core_count - GT_count)
DUPLICATE += (Core_count - GT_count)   if Core_count > GT_count AND GT_count > 0
```

**By construction**: `TP + FN = GT_TOTAL` — every GT fact is either matched (TP) or unmatched (FN). This guarantees the invariant.

---

## D. V17 re-matching results

### D.1 V17 raw facts

```
V17 raw facts (in benchmark):  298
V17 raw events (in benchmark):  38
```

### D.2 V17 V23R bipartite matching

| Metric | Value |
|--------|------:|
| Fact TP | 187 |
| Fact FP | 111 |
| Fact FN | 1,425 |
| Fact DUPLICATE | 41 |
| **Fact Invariant** | **TP(187) + FN(1,425) = 1,612 = GT ✓** |
| Fact Precision | 62.75% |
| Fact Recall | 11.60% |
| Event TP | 32 |
| Event FP | 6 |
| Event FN | 176 |
| **Event Invariant** | **TP(32) + FN(176) = 208 = GT ✓** |
| Event Precision | 84.21% |
| Event Recall | 15.38% |

### D.3 V17 invariant closure

The V22 matching gap of 39 facts (1,573 vs 1,612) is now **CLOSED**. Every GT fact is classified as exactly one of TP or FN.

---

## E. V20 re-matching results

### E.1 V20 raw facts (re-extracted using V21 pipeline)

```
V20 raw facts:  321
V20 raw events:  55
Extraction time: 70.9s
```

### E.2 V20 V23R bipartite matching

| Metric | Value |
|--------|------:|
| Fact TP | 251 |
| Fact FP | 70 |
| Fact FN | 1,361 |
| Fact DUPLICATE | 0 |
| **Fact Invariant** | **TP(251) + FN(1,361) = 1,612 = GT ✓** |
| Fact Precision | 78.19% |
| Fact Recall | 15.57% |
| Event TP | 47 |
| Event FP | 8 |
| Event FN | 161 |
| **Event Invariant** | **TP(47) + FN(161) = 208 = GT ✓** |
| Event Precision | 85.45% |
| Event Recall | 22.60% |

### E.3 V20 invariants hold

Both fact and event invariants PASS for V20 under V23R bipartite matching.

---

## F. V17 → V20 comparison (V23R)

| Metric | V17 | V20 | Delta |
|--------|---:|----:|------:|
| GT facts | 1,612 | 1,612 | 0 |
| Fact TP | 187 | 251 | +64 |
| Fact FP | 111 | 70 | -41 |
| Fact FN | 1,425 | 1,361 | -64 |
| Fact Precision | 62.75% | 78.19% | +15.44pp |
| Fact Recall | 11.60% | 15.57% | **+3.97pp** |
| GT events | 208 | 208 | 0 |
| Event TP | 32 | 47 | +15 |
| Event FP | 6 | 8 | +2 |
| Event FN | 176 | 161 | -15 |
| Event Precision | 84.21% | 85.45% | +1.24pp |
| Event Recall | 15.38% | 22.60% | **+7.21pp** |

### F.1 Invariant verification

| Invariant | V17 | V20 | Status |
|-----------|---:|---:|--------|
| Fact: TP+FN=GT | 187+1425=1612 | 251+1361=1612 | **both ✓ PASS** |
| Event: TP+FN=GT | 32+176=208 | 47+161=208 | **both ✓ PASS** |

**All 4 invariants hold.** The V22 matching gap is CLOSED.

---

## G. Final verdict

### `CORE BASELINE MATCHING CLOSURE PASSED`

The V23R bipartite matching closure is **PASSED**:

1. **Canonical identity defined** ✅ — `(doc, canonical_metric, canonical_value)`
2. **Bipartite matching with multiplicities** ✅ — guarantees `TP + FN = GT_TOTAL`
3. **V17 invariant closure** ✅ — `TP(187) + FN(1,425) = 1,612` (gap CLOSED)
4. **V20 invariants hold** ✅ — `TP(251) + FN(1,361) = 1,612`
5. **Event invariants hold** ✅ — both V17 and V20 at 208

### Independent measurement (NOT using previous V23 reported metrics)

```
Fact Recall:    11.60% → 15.57%   (+3.97pp)
Event Recall:   15.38% → 22.60%   (+7.21pp)
Fact Precision: 62.75% → 78.19%   (+15.44pp)
Event Precision: 84.21% → 85.45%  (+1.24pp)
```

These numbers were measured fresh from V22 source + V22 GT + V22 corpus. They are NOT copied from the previous V23 session — they are independently derived.

---

## H. Artifacts

### H.1 Code

- `intelligence_core/tests/reliability/v23r_bipartite_matching.py` — V23R matching + measurement

### H.2 Results

- `intelligence_core/tests/reliability/v23r_results.json` — V23R results
- `intelligence_core/tests/reliability/v20_raw_facts.json` — V20 raw facts (321)
- `intelligence_core/tests/reliability/v20_raw_events.json` — V20 raw events (55)

### H.3 Governance

- `docs/evidence/ROUAA_CORE_BASELINE_MATCHING_CLOSURE_V23R.md` — this document
