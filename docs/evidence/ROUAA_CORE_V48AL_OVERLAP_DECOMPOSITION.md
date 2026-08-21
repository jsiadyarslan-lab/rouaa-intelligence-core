# V48AL — Overlap Decomposition & Label Consistency
**Base:** `373c879` (V48AK)
**Verdict:** `ANNOTATION_INCONSISTENCY_SUSPECTED`
## Phase 2: Blind Dimensions (8 overlapping cases)
| # | D1 | D2 | D3 | D4 | D5 | Human |
|---|----|----|----|----|----|-------|
| 76 | modifier | both | weakly_implied | contextual_reference | mixed | AMBIGUOUS || 78 | modifier | both | weakly_implied | contextual_reference | mixed | AMBIGUOUS || 82 | modifier | head_noun | strongly_implied | contextual_reference | head_noun | AMBIGUOUS || 100 | modifier | both | weakly_implied | contextual_reference | mixed | AMBIGUOUS || 103 | modifier | head_noun | strongly_implied | contextual_reference | head_noun | AMBIGUOUS || 115 | modifier | both | weakly_implied | contextual_reference | mixed | AMBIGUOUS || 130 | modifier | head_noun | weakly_implied | contextual_reference | head_noun | CONTEXT || 131 | modifier | head_noun | strongly_implied | contextual_reference | head_noun | CONTEXT |## Phase 7: Critical Negative Test
**FOUND 1 cross-conflicts** — identical dimensions, different human labels:

**Vector:** ('modifier', 'head_noun', 'strongly_implied', 'contextual_reference', 'head_noun')
- #117 (CONTEXT) | Penalty | hn=guidelines | Penalty guidelines were issued for industry consultation by - #119 (CONTEXT) | Policy Rate | hn=corridor | Policy rate corridor was maintained at its existing operatio- #121 (CONTEXT) | Gross Domestic Product | hn=deflator | GDP deflator series was revised in the latest national accou- #122 (CONTEXT) | Consumer Price Index | hn=basket | CPI basket composition was updated for the new index series.- #126 (CONTEXT) | Inflation | hn=targeting | Inflation targeting framework was reaffirmed in the central - #130 (CONTEXT) | Foreign Exchange | hn=reserves | Foreign exchange reserves position was described as adequate- #131 (CONTEXT) | Penalty | hn=framework | Penalty framework review was the subject of committee delibe- #138 (CONTEXT) | Penalty | hn=appeal | Penalty appeal process was detailed in the regulatory enforc- #140 (CONTEXT) | Inflation | hn=data | Inflation data collection was refined per the new statistica- #147 (CONTEXT) | Inflation | hn=expectations | Inflation expectations indicator was added to the central ba- #149 (CONTEXT) | Unemployment | hn=statistics | Unemployment statistics methodology was aligned with the ILO- #82 (AMBIGUOUS) | Penalty | hn=decisions | Penalty decisions were the subject of regulatory committee r- #83 (AMBIGUOUS) | Gross Domestic Product | hn=statistics | GDP statistics are compiled in accordance with international- #87 (AMBIGUOUS) | Consumer Price Index | hn=methodology | CPI methodology was revised in line with the new internation- #89 (AMBIGUOUS) | Penalty | hn=procedures | Penalty procedures were outlined in the updated enforcement - #92 (AMBIGUOUS) | Policy Rate | hn=decisions | Policy rate decisions are scheduled for the next FOMC meetin- #93 (AMBIGUOUS) | Unemployment | hn=statistics | Unemployment statistics are released on the first Friday of - #94 (AMBIGUOUS) | Consumer Price Index | hn=sub-indices | CPI sub-indices were analyzed in the detailed statistical ap- #96 (AMBIGUOUS) | Penalty | hn=framework | Penalty framework revisions were proposed in the latest regu- #98 (AMBIGUOUS) | Inflation | hn=targeting | Inflation targeting framework was reaffirmed in the central - #101 (AMBIGUOUS) | Consumer Price Index | hn=weights | CPI weights were updated in the latest index revision per th- #103 (AMBIGUOUS) | Penalty | hn=guidelines | Penalty guidelines were the subject of industry consultation## Phase 8: Verdict

**ANNOTATION_INCONSISTENCY_SUSPECTED**

Found 1 cases where all 5 dimensions are identical but human labels differ. This suggests the human adjudication is inconsistent, not that the ontology is wrong.

### What V48AK proved
V48AK proved that the three labels (TRUE_SUBJECT / CONTEXT_ONLY / AMBIGUOUS) are PARTIALLY_OVERLAPPING — they conflate multiple independent dimensions (subjecthood, event attribution, contextual relevance, certainty, scope). 72% of cases have a single clearly correct label; 28% have multiple valid labels.

### What V48AL proved
V48AL proved that: (1) the 8 overlapping cases have 3 unique dimension vectors out of 8 cases; (2) CROSS-CONFLICTS WERE FOUND — suggesting annotation inconsistency; (3) the multi-dimension hypothesis is ANNOTATION_INCONSISTENCY_SUSPECTED.

### What remains unknown
Whether a multi-dimensional label would actually improve classifier performance in production. Whether the annotation inconsistency (if found) is systematic or random. Whether real documents (not synthetic) would resolve the ambiguous cases via document context.

### Evidence required before redesigning
Before redesigning the ontology: (1) resolve any annotation inconsistencies found in Phase 7; (2) test the multi-dimensional representation on REAL documents (not synthetic); (3) determine if the 5 dimensions are truly independent or correlated in practice.

---
**V48AL is a FORENSIC EXPERIMENT, NOT implementation.** STOP.
