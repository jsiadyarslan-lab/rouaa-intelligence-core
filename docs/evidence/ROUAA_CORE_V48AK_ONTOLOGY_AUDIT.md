# V48AK — Label Ontology / Semantic Target Audit
**Executed at (UTC):** 2026-08-21T13:57:01Z
**Base:** `6a3c386` (V48AJ)
**Verdict:** `ONTOLOGY_PARTIALLY_OVERLAPPING`
## Phase 1: Label Semantics
### TRUE_SUBJECT
**Documented:** The candidate IS the semantic subject of the event — the event verb applies to the candidate, and the measurement (if any) describes the candidate.
**Implementation:** V2.1 code: judgment='TRUE_SUBJECT' when:
  1. role=SUBJECT + strong_count>=2 (event+measurement+fact STRONG)
  2. role=SUBJECT + strong_count==1 + event in (STRONG, MODERATE)
  3. role=SUBJECT + event...
**Test/Fixture:** V48AE pre-reg: 'The candidate IS the semantic subject of the event — the event verb applies to the candidate, and the measurement (if any) describes the candidate.'
V48AG pre-reg: same definition....
**Discrepancies:**
1. IMPLEMENTATION vs DOCUMENTATION: V2.1 checks whether an event verb appears in a WINDOW near the candidate, NOT whether the event verb APPLIES TO the candidate. 'GDP increased' and 'GDP statistics are compiled' both match event=STRONG (via verb proximity), but the event only applies to GDP in the first case.
2. OVERRIDE: V2.1 returns TRUE_SUBJECT even when role=CONTEXT (heading names competing topic) if event+measurement are both STRONG. This contradicts the documented definition which requires the candidate to BE the semantic subject.
3. NO EVENT-ATTRIBUTION CHECK: V2.1 never verifies that the event verb's syntactic subject IS the candidate. It only checks verb proximity.
### CONTEXT_ONLY
**Documented:** The candidate appears as a noun modifier or context-only reference (e.g., 'FX turnover data is collected' — FX is a modifier of 'data', not the subject of an action).
**Implementation:** V2.1 code: judgment='CONTEXT_ONLY' when:
  1. role=MODIFIER + effective_event not STRONG
  2. role=MEASURE + effective_event not STRONG
Implementation uses PROXY: head noun follows candidate (not sema...
**Test/Fixture:** V48AE pre-reg: 'The candidate appears as a noun modifier or context-only reference (e.g., FX turnover data is collected — FX is a modifier of data, not the subject of an action).'
V48AG pre-reg: same ...
**Discrepancies:**
1. IMPLEMENTATION vs DOCUMENTATION: V2.1 detects MODIFIER via head-noun presence (syntactic proxy), NOT via semantic determination that the candidate is context-only. A candidate followed by a head noun is automatically MODIFIER, regardless of whether the event is about the candidate or the head noun.
2. NO EVENT-ATTRIBUTION CHECK: V2.1 doesn't verify that the event verb applies to the HEAD NOUN (not the candidate). It only checks that the candidate has a head noun (syntactic) and that the event is weak (insufficient).
3. MEASURE conflation: V2.1 returns CONTEXT_ONLY for role=MEASURE (GDP deflator, CPI basket) — but the documented definition doesn't explicitly cover this case.
### AMBIGUOUS
**Documented:** The case has conflicting signals or is genuinely unclear to a human reader — the candidate is mentioned but its role as subject cannot be determined with confidence.
**Implementation:** V2.1 code: judgment='AMBIGUOUS' when:
  1. role=CONTEXT + event=STRONG (conflict, no measurement)
  2. role=MODIFIER + event=STRONG + measurement=STRONG (conflict)
  3. role=MODIFIER + event=STRONG (c...
**Test/Fixture:** V48AE pre-reg: 'The case has conflicting signals or is genuinely unclear to a human reader — the candidate is mentioned but its role as subject cannot be determined with confidence.'
V48AG pre-reg: sa...
**Discrepancies:**
1. CONFLATION: AMBIGUOUS is used for at least 4 SEMANTICALLY DIFFERENT situations: (a) conflicting evidence (event=STRONG + fact=CONTRADICTED), (b) insufficient evidence (event=WEAK), (c) role conflict (MODIFIER + event=STRONG), (d) default fallback. These are epistemically different but the label doesn't distinguish them.
2. NO CERTAINTY DIMENSION: The documented definition says 'genuinely unclear,' but V2.1 returns AMBIGUOUS even when the case is NOT genuinely unclear — it's just insufficient evidence (event=WEAK).
3. NO ATTRIBUTION DISTINCTION: V2.1 doesn't distinguish 'I can't tell if the event applies to the candidate or the head noun' from 'I found no event evidence at all.' Both return AMBIGUOUS.
## Phase 3: Label Compatibility
- Single label (cleanly separable): 21/29
- Multiple labels valid (overlapping): 8/29
- None adequate (under-specified): 0/29
## Phase 5: Three-Label Assumption
Phase 1 found that:
1. TRUE_SUBJECT conflates syntactic subjecthood (verb proximity) with semantic event attribution (verb applies to candidate). V2.1 checks proximity, not attribution.
2. CONTEXT_ONLY conflates noun-modifier role (syntactic) with contextual relevance (semantic). V2.1 detects head-noun presence, not whether the candidate is context-only.
3. AMBIGUOUS is used as a catch-all for at least 4 epistemically different situations: (a) conflicting evidence, (b) insufficient evidence, (c) role conflict, (d) default fallback. These are NOT semantically equivalent.
Phase 3 found that 8/29 cases have MULTIPLE labels that are semantically valid — the labels overlap.
Phase 4 found similar pairs (same candidate, same head noun, same syntactic structure) with DIFFERENT human labels — the distinguishing dimension (event attribution certainty, secondary target, document topic) is NOT represented by the three labels.
## Phase 6: Decision
**Verdict:** `ONTOLOGY_PARTIALLY_OVERLAPPING`

**Evidence for:**
Phase 1 found that:
1. TRUE_SUBJECT conflates syntactic subjecthood (verb proximity) with semantic event attribution (verb applies to candidate). V2.1 checks proximity, not attribution.
2. CONTEXT_ONLY conflates noun-modifier role (syntactic) with contextual relevance (semantic). V2.1 detects head-noun presence, not whether the candidate is context-only.
3. AMBIGUOUS is used as a catch-all for at least 4 epistemically different situations: (a) conflicting evidence, (b) insufficient evidence, (c) role conflict, (d) default fallback. These are NOT semantically equivalent.
Phase 3 found that 8/29 cases have MULTIPLE labels that are semantically valid — the labels overlap.
Phase 4 found similar pairs (same candidate, same head noun, same syntactic structure) with DIFFERENT human labels — the distinguishing dimension (event attribution certainty, secondary target, document topic) is NOT represented by the three labels.

**Counter-evidence:**
Counter-evidence: 21/29 cases DO have a single clearly correct label — the ontology IS sufficient for those cases. The conflation only manifests when the case has conflicting signals (secondary target, meta-reference verb, or ambiguous event attribution).

**Unresolved cases:** [130, 131, 76, 78, 82, 100, 103, 115]

**Missing info:**
To decide confidently whether the ontology needs replacement vs extension, we need to: (1) test on REAL documents (not synthetic) to determine if document context resolves the ambiguous cases; (2) determine if a multi-dimensional label (separate subjecthood/event-attribution/certainty) would cleanly separate the populations that V48AJ couldn't separate.
---
**V48AK is an ONTOLOGY AUDIT, NOT implementation.**
No new ontology designed. No labels renamed. No classifier modified. STOP.
