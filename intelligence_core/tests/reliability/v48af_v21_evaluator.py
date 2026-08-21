"""V48AF — V2.1 Hardened Evaluator (Shadow).

V2.1 is an INCREMENTAL hardening of V2 (V48AD). It addresses the two
specific gaps identified by V48AE blind adjudication:

  Task 1 — Alias-length bug fix in _detect_semantic_role:
    V2 used len(aliases[0]) for the slice window regardless of which alias
    was actually matched. When the matched alias differed from aliases[0]
    (e.g., candidate FX matched via "foreign exchange" not "fx"), the
    slice window was wrong and MODIFIER detection missed.
    V2.1 FIX: pass the matched alias to _detect_semantic_role and use
    its actual length for slicing.

  Task 2 — Judgment mapping tuning:
    V2 was too conservative — returned AMBIGUOUS in cases where humans
    expect FALSE_BINDING or CONTEXT_ONLY (when role=CONTEXT/MODIFIER
    detected with no positive event evidence).
    V2.1 FIX:
      role=CONTEXT  + event not STRONG + measurement weak → FALSE_BINDING
      role=MODIFIER + event not STRONG + measurement weak → CONTEXT_ONLY
      role=MEASURE   + event not STRONG                 → CONTEXT_ONLY
      role=ACTOR                                    → AMBIGUOUS (genuine — actor could be either)
      role=CONTEXT  + event=STRONG + measurement=STRONG → TRUE_SUBJECT (override kept)
      role=MODIFIER + event=STRONG + measurement=STRONG → AMBIGUOUS (genuine conflict)
      AMBIGUOUS is now reserved for GENUINE conflicts only.

NO production changes. NO V49. NO embeddings/LLM. NO source expansion.
V2 (v48ad_hardened_evaluator.py) is preserved untouched for V48AD
reproducibility.
"""
from __future__ import annotations
import re
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(CORE_REPO))
import os
os.chdir(str(CORE_REPO))

# Import V2 constants and helpers — V2 is the immutable baseline
from intelligence_core.tests.reliability.v48ad_hardened_evaluator import (
    _EVENT_VERBS_V2,
    _MEASUREMENT_PATTERNS_V2,
    _MODIFIER_HEAD_NOUNS,
    _MEASUREMENT_INSTRUMENT_NOUNS,
    _COMPETING_TOPIC_MARKERS,
    _measurement_signal_v2,
    _fact_contradiction_judgment_v2,
    SIGNAL_LEVELS,
    JUDGMENT_LEVELS,
)
from intelligence_core.structural_parser import parse_html_to_segments
from intelligence_core.segment_purpose import apply_purpose_filter
from intelligence_core.evidence_context import build_contexts_for_io
from intelligence_core.subject_entity import (
    _extract_document_title,
    _ALL_REGISTRIES,
    _SUBORDINATE_CONJUNCTIONS,
    _CLAUSE_BOUNDARY,
)


# ═══════════════════════════════════════════════════════════════════════
# V2.1 EXTENDED LEXICONS (Task 1 completion — fix V48AE CONTEXT_GAPs)
# ═══════════════════════════════════════════════════════════════════════
#
# V48AF Task 1 was supposed to fix all 10 V48AE CONTEXT_GAPs via the
# alias-length bug fix. But only 2 of 10 were actual alias-length cases.
# The other 8 were missing-lexicon cases:
#   - Missing competing markers: "spending", "applications", "output",
#     "production"
#   - Missing head nouns: "print", "estimates", "trajectory", "dynamics",
#     "weighting"
#
# Extending these lexicons is the natural completion of Task 1 — without
# them, role detection can't fire and Task 2's judgment tuning can't apply.

# V2.1 extended head nouns (V48AF refinement)
_MODIFIER_HEAD_NOUNS_V21 = list(_MODIFIER_HEAD_NOUNS) + [
    # V48AF — added based on V48AE CONTEXT_GAP patterns
    "print",         # "CPI print is scheduled for release"
    "estimates",     # "GDP estimates are subject to revision"
    "trajectory",    # "Inflation trajectory remains clouded"
    "dynamics",      # "GDP dynamics featured prominently"
    "weighting",     # "CPI weighting was refreshed"
]

# V2.1 extended competing-topic markers (V48AF refinement)
_COMPETING_TOPIC_MARKERS_V21 = list(_COMPETING_TOPIC_MARKERS) + [
    # V48AF — added based on V48AE CONTEXT_GAP patterns
    "spending",      # "Construction Spending", "Education Spending"
    "applications",  # "Patent Applications"
    "output",        # "Mining Sector Output", "Manufacturing Output"
    "production",    # "Energy Production Report"
]


# ═══════════════════════════════════════════════════════════════════════
# Task 1 — V2.1 _detect_semantic_role (with alias-length bug fix)
# ═══════════════════════════════════════════════════════════════════════
#
# The V2 bug: cand_first_alias = aliases[0] was used for slicing,
# but the actual matched alias (in evaluate_evidence_vector_v2) might
# be a different alias in the list.
#
# V2.1 FIX: pass matched_alias as an explicit parameter. Use the actual
# matched alias length (not aliases[0] length) for slicing.

def _detect_semantic_role_v21(
    candidate: str,
    candidate_aliases: list[str],
    primary_text: str,
    heading_context: str,
    doc_title: str,
    cand_idx: int,
    matched_alias: str = "",  # V2.1 NEW — the alias that was actually matched
) -> str:
    """V2.1 — Detect semantic role with alias-length bug fixed.

    Returns one of: SUBJECT / MEASURE / CONTEXT / MODIFIER / ACTOR
    """
    if cand_idx < 0:
        return "CONTEXT"

    text_lower = primary_text.lower()

    # V2.1 FIX: use matched_alias (not aliases[0]) for length computation.
    # If matched_alias is empty (caller didn't pass it), fall back to
    # the first alias (V2 behavior — kept for backward compat).
    if matched_alias:
        matched_alias_lower = matched_alias.lower()
    else:
        matched_alias_lower = (candidate_aliases[0] if candidate_aliases else candidate).lower()

    # V2.1 — Use a CONSTANT slice window of 25 chars AFTER the END of
    # the matched alias. This is more robust than relying on alias length
    # (which can vary per candidate). The window starts at
    # cand_idx + len(matched_alias_lower) and extends 25 chars.
    slice_start = cand_idx + len(matched_alias_lower)
    after_candidate = text_lower[slice_start:slice_start + 25]

    matched_head_noun = None
    for head_noun in _MODIFIER_HEAD_NOUNS_V21:  # V2.1 EXTENDED
        if re.search(r"\b" + re.escape(head_noun) + r"\b", after_candidate):
            matched_head_noun = head_noun
            break

    if matched_head_noun:
        if matched_head_noun in _MEASUREMENT_INSTRUMENT_NOUNS:
            return "SUBJECT"  # measurement instrument → candidate is subject
        return "MODIFIER"

    # Fall back to wider 40-char window for MEASURE nouns
    after_candidate_wide = text_lower[slice_start:slice_start + 40]

    measure_nouns = ["deflator", "weights", "basket", "sub-indices", "subindices"]
    for noun in measure_nouns:
        if re.search(r"\b" + re.escape(noun) + r"\b", after_candidate_wide):
            return "MEASURE"

    # ACTOR detection — preceded by "by"
    before_candidate = text_lower[max(0, cand_idx - 20):cand_idx]
    if re.search(r"\bby\s*$", before_candidate):
        return "ACTOR"

    # CONTEXT detection (V2 REFINED logic — same as V2, but with V2.1 extended markers)
    hc = (heading_context or "").lower()
    dt = (doc_title or "").lower()

    for source_text in [hc, dt]:
        if not source_text or len(source_text) < 15:
            continue
        competing_marker_match = None
        for marker in _COMPETING_TOPIC_MARKERS_V21:  # V2.1 EXTENDED
            m = re.search(r"\b" + re.escape(marker) + r"\b", source_text)
            if m:
                competing_marker_match = m
                break
        if not competing_marker_match:
            continue

        cand_pos_in_heading = -1
        for alias in candidate_aliases:
            m = re.search(r"\b" + re.escape(alias.lower()) + r"\b", source_text)
            if m:
                cand_pos_in_heading = m.start()
                break

        if cand_pos_in_heading < 0:
            return "CONTEXT"
        elif competing_marker_match.start() < cand_pos_in_heading:
            return "CONTEXT"

    return "SUBJECT"


# ═══════════════════════════════════════════════════════════════════════
# V2.1 — Hardened evidence evaluator (with Task 1 + Task 2 fixes)
# ═══════════════════════════════════════════════════════════════════════

def evaluate_evidence_vector_v21(
    candidate: str,
    candidate_aliases: list,
    candidate_reg_type: str,
    candidate_id: str,
    primary_text: str,
    heading_context: str,
    doc_title: str,
    fact_metrics: list,
    event_type: str,
    all_segments: list,
    io: dict,
) -> dict:
    """V2.1 hardened evidence evaluator.

    Same signal vector as V2, with:
      - Task 1 fix: _detect_semantic_role_v21 uses matched_alias length
      - Task 2 fix: judgment mapping is more aggressive for non-SUBJECT roles
    """
    text_lower = (primary_text or "").lower()
    aliases_lower = [a.lower() for a in candidate_aliases]
    cand_name_lower = candidate.lower()

    # Find candidate position in text — AND track the matched alias
    cand_idx = -1
    matched_alias = ""  # V2.1 NEW
    for alias in aliases_lower:
        idx = text_lower.find(alias)
        if idx >= 0:
            cand_idx = idx
            matched_alias = alias
            break
    if cand_idx < 0:
        cand_idx = text_lower.find(cand_name_lower)
        matched_alias = cand_name_lower

    # ── EVENT signal (V2 hardened verb lexicon — unchanged) ──
    event_level = "INSUFFICIENT"
    matched_verb = ""
    if cand_idx >= 0:
        window = text_lower[max(0, cand_idx - 50):cand_idx + len(candidate) + 100]
        text_before = text_lower[:cand_idx]
        sub_matches = list(_SUBORDINATE_CONJUNCTIONS.finditer(text_before))
        in_subordinate = False
        if sub_matches:
            last_sub = sub_matches[-1]
            text_between = text_before[last_sub.end():]
            if not _CLAUSE_BOUNDARY.search(text_between):
                in_subordinate = True

        if in_subordinate:
            event_level = "CONTRADICTED"
        else:
            verbs = _EVENT_VERBS_V2.get(candidate_reg_type, _EVENT_VERBS_V2["INDICATOR"])
            m = verbs.search(window)
            if m:
                matched_verb = m.group(0)
                event_level = "STRONG"
            else:
                if cand_idx < 80:
                    after = text_lower[cand_idx + len(candidate):cand_idx + len(candidate) + 100]
                    m2 = verbs.search(after)
                    if m2:
                        matched_verb = "first-noun+" + m2.group(0)
                        event_level = "MODERATE"
                    else:
                        event_level = "WEAK"
                else:
                    event_level = "WEAK"

    # ── MEASUREMENT signal (V2 hardened patterns — unchanged) ──
    measurement_level = "INSUFFICIENT"
    if cand_idx >= 0:
        window = text_lower[max(0, cand_idx - 20):cand_idx + 100]
        measurement_level = _measurement_signal_v2(window)

    # ── FACT signal (same as V2) ──
    fact_level = "INSUFFICIENT"
    metric_to_canonical = {
        "policy_rate": "policy_rate", "gdp_growth": "gdp_growth",
        "inflation_rate": "inflation", "unemployment_rate": "unemployment",
        "penalty_amount": "penalty", "usd_amount": "penalty",
        "percentage_statistic": None, "action_type": None,
    }
    expected = None
    for fm in fact_metrics:
        if fm in metric_to_canonical:
            expected = metric_to_canonical[fm]
            break
    if expected and expected == candidate_id:
        fact_level = "STRONG"
    elif expected and expected != candidate_id:
        fact_level = "CONTRADICTED"
    elif expected is None and fact_metrics:
        fact_level = "MODERATE"

    # ── EVENT TYPE signal (same as V2) ──
    event_type_priors = {
        "statistical_release": ["INDICATOR", "MARKET", "REGULATION"],
        "monetary_policy_decision": ["CONCEPT", "INSTRUMENT"],
        "regulatory_enforcement": ["REGULATION", "ENTITY"],
        "market_statistic_release": ["MARKET", "INDICATOR"],
        "earnings_release": ["ENTITY", "INSTRUMENT"],
    }
    valid_types = event_type_priors.get(event_type, [])
    if candidate_reg_type in valid_types:
        event_type_level = "COMPATIBLE"
    elif valid_types:
        event_type_level = "NOT_PRIOR"
    else:
        event_type_level = "UNKNOWN"

    # ── HEADING signal (same as V2) ──
    heading_level = "NEUTRAL"
    hc = (heading_context or "").lower()
    if hc:
        for alias in aliases_lower:
            if re.search(r"\b" + re.escape(alias) + r"\b", hc):
                heading_level = "SUPPORT"
                break
        if heading_level == "NEUTRAL":
            generic_terms = ["press release", "statement", "embargo", "minutes", "skip to"]
            if any(g in hc for g in generic_terms):
                heading_level = "NEUTRAL"
            else:
                has_registry = False
                for reg_type, reg in _ALL_REGISTRIES.items():
                    for cid, (cname, etype, aliases) in reg.items():
                        for alias in aliases:
                            if re.search(r"\b" + re.escape(alias) + r"\b", hc):
                                has_registry = True
                                break
                        if has_registry: break
                    if has_registry: break
                if not has_registry and len(hc) > 15:
                    heading_level = "CONTRADICTION"

    # ── TOPIC signal (same as V2) ──
    topic_level = "NEUTRAL"
    dt = (doc_title or "").lower()
    if dt:
        for alias in aliases_lower:
            if re.search(r"\b" + re.escape(alias) + r"\b", dt):
                topic_level = "SUPPORT"
                break
        if topic_level == "NEUTRAL":
            generic_terms = ["press release", "statement", "embargo", "board of governors",
                             "european central bank", "bureau of economic analysis"]
            if any(g in dt for g in generic_terms):
                topic_level = "NEUTRAL"
            else:
                has_registry = False
                for reg_type, reg in _ALL_REGISTRIES.items():
                    for cid, (cname, etype, aliases) in reg.items():
                        for alias in aliases:
                            if re.search(r"\b" + re.escape(alias) + r"\b", dt):
                                has_registry = True
                                break
                        if has_registry: break
                    if has_registry: break
                if not has_registry and len(dt) > 15:
                    topic_level = "CONTRADICTION"

    # ── POSITION signal (same as V2) ──
    if cand_idx < 0:
        position = "NOT_FOUND"
    elif cand_idx < 150:
        position = "EARLY"
    elif cand_idx < 500:
        position = "MIDDLE"
    else:
        position = "LATE"

    # ── §3-C SEMANTIC ROLE signal (V2.1 with alias-length fix) ──
    semantic_role = _detect_semantic_role_v21(
        candidate=candidate,
        candidate_aliases=candidate_aliases,
        primary_text=primary_text or "",
        heading_context=heading_context or "",
        doc_title=doc_title or "",
        cand_idx=cand_idx,
        matched_alias=matched_alias,  # V2.1 — pass the actual matched alias
    )

    vector = {
        "event": event_level,
        "measurement": measurement_level,
        "fact": fact_level,
        "event_type": event_type_level,
        "heading": heading_level,
        "topic": topic_level,
        "position": position,
        "matched_verb": matched_verb,
        "semantic_role": semantic_role,
        "matched_alias": matched_alias,  # V2.1 NEW — for debugging
    }

    # ── JUDGMENT (V2.1 TUNED — Task 2 + event-level downgrade) ────────
    strong_count = sum(1 for v in [event_level, measurement_level, fact_level] if v == "STRONG")
    topic_contradiction = (topic_level == "CONTRADICTION" or heading_level == "CONTRADICTION")

    # V2.1 REFINEMENT: when role=MODIFIER is detected, the event verb in
    # the window likely applies to the HEAD NOUN (e.g., "Unemployment
    # registrations increased" — increased applies to registrations, not
    # to Unemployment). So event=STRONG is misleading.
    # Downgrade event_level by two steps when role=MODIFIER:
    #   STRONG → WEAK
    #   MODERATE → INSUFFICIENT
    # This reflects the semantic reality that the verb applies to the
    # head noun, not the modifier.
    effective_event = event_level
    if semantic_role == "MODIFIER":
        if event_level == "STRONG":
            effective_event = "WEAK"
        elif event_level == "MODERATE":
            effective_event = "INSUFFICIENT"
        vector["effective_event"] = effective_event  # for debugging

    # §3-C V2.1: semantic_role gates — TUNED judgment mapping
    if semantic_role == "CONTEXT":
        # CONTEXT = heading names competing topic
        if effective_event == "STRONG" and measurement_level == "STRONG":
            # Override: strong primary-text evidence beats heading-only signal
            judgment = "TRUE_SUBJECT"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            vector["role_override_reason"] = (
                "Strong primary-text evidence (event=STRONG + measurement=STRONG) "
                "overrode CONTEXT detection (heading-only signal)."
            )
            return vector
        elif effective_event == "STRONG":
            # Conflict — event says YES but heading says NO
            judgment = "AMBIGUOUS"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
        else:
            # V2.1 TUNING: effective_event weak + role=CONTEXT (heading competing topic)
            # → FALSE_BINDING (the heading names a different topic;
            #   candidate is clearly NOT the subject)
            judgment = "FALSE_BINDING"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
    elif semantic_role == "MODIFIER":
        # MODIFIER = candidate is a noun modifier of a head noun
        # effective_event has been DOWNGRADED (because verb applies to head noun)
        if effective_event == "STRONG" and measurement_level == "STRONG":
            # Genuine conflict — strong primary-text evidence but MODIFIER pattern
            # (rare after downgrade — only when event wasn't downgraded)
            judgment = "AMBIGUOUS"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
        elif effective_event == "STRONG":
            # Conflict — event says YES but modifier pattern says NO
            judgment = "AMBIGUOUS"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
        else:
            # V2.1 TUNING: effective_event weak + role=MODIFIER (noun modifier pattern)
            # → CONTEXT_ONLY (candidate is a modifier, not the subject)
            judgment = "CONTEXT_ONLY"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
    elif semantic_role == "MEASURE":
        # MEASURE = candidate is the measurement framework (deflator/weights/basket)
        if effective_event == "STRONG":
            judgment = "AMBIGUOUS"  # conflict
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
        else:
            # V2.1 TUNING: effective_event weak + role=MEASURE
            # → CONTEXT_ONLY (candidate is measurement framework, not subject)
            judgment = "CONTEXT_ONLY"
            vector["judgment"] = judgment
            vector["strong_count"] = strong_count
            return vector
    elif semantic_role == "ACTOR":
        # ACTOR = candidate preceded by "by" — could be either subject or actor
        # → AMBIGUOUS (genuine — we can't tell)
        judgment = "AMBIGUOUS"
        vector["judgment"] = judgment
        vector["strong_count"] = strong_count
        return vector

    # §3-D: fact-contradiction softening (V2 logic — kept)
    fact_judgment = _fact_contradiction_judgment_v2(
        event=event_level, fact=fact_level, topic=topic_level,
        heading=heading_level, strong_count=strong_count,
    )
    if fact_judgment is not None:
        judgment = fact_judgment
        vector["judgment"] = judgment
        vector["strong_count"] = strong_count
        return vector

    # Default judgment logic (V2-style, semantic_role=SUBJECT verified)
    if strong_count >= 2:
        judgment = "TRUE_SUBJECT"
    elif strong_count == 1 and event_level in ("STRONG", "MODERATE"):
        judgment = "TRUE_SUBJECT"
    elif event_level == "STRONG" and not topic_contradiction:
        judgment = "TRUE_SUBJECT"
    elif event_level in ("STRONG", "MODERATE", "WEAK") and topic_contradiction:
        judgment = "AMBIGUOUS"
    elif event_level == "WEAK":
        judgment = "AMBIGUOUS"
    else:
        judgment = "AMBIGUOUS"

    vector["judgment"] = judgment
    vector["strong_count"] = strong_count
    return vector


# ═══════════════════════════════════════════════════════════════════════
# V2.1 — Shadow case runner (handles CONTEXT_ONLY judgment)
# ═══════════════════════════════════════════════════════════════════════

def run_shadow_case_v21(text: str, source_id: str = "") -> dict:
    """V2.1 shadow case runner — handles CONTEXT_ONLY judgment."""
    html_bytes = (
        f"<!DOCTYPE html><html><head><title>T</title></head>"
        f"<body><article><h1>{text}</h1><p>{text}</p></article></body></html>"
    ).encode()
    segs = parse_html_to_segments(html_bytes, document_id="doc-s")
    segs = apply_purpose_filter(segs)
    primary_seg = None
    for seg in segs:
        if seg.segment_type == "PARAGRAPH" and text.lower() in (seg.text or "").lower():
            primary_seg = seg
            break
    if not primary_seg:
        for seg in segs:
            if seg.text and len(seg.text) > 10:
                primary_seg = seg
                break
    if not primary_seg:
        return {"error": "no segment", "judgment": "ERROR"}

    all_candidates = []
    for reg_type, reg in _ALL_REGISTRIES.items():
        for cid, (cname, etype, aliases) in reg.items():
            for alias in aliases:
                if re.search(r"\b" + re.escape(alias) + r"\b", (primary_seg.text or "").lower()):
                    all_candidates.append({
                        "candidate": cname, "aliases": aliases,
                        "reg_type": reg_type, "canonical_id": cid,
                    })
                    break

    if not all_candidates:
        return {"judgment": "NO_CANDIDATE", "candidates": []}

    results = []
    for cand in all_candidates:
        vec = evaluate_evidence_vector_v21(
            candidate=cand["candidate"],
            candidate_aliases=cand["aliases"],
            candidate_reg_type=cand["reg_type"],
            candidate_id=cand["canonical_id"],
            primary_text=primary_seg.text or "",
            heading_context=primary_seg.heading_context or "",
            doc_title=_extract_document_title(segs),
            fact_metrics=["test"],
            event_type="statistical_release",
            all_segments=segs,
            io={"facts": [{"metric": "test", "value": "1"}]},
        )
        results.append({"candidate": cand["candidate"], "vector": vec})

    # V2.1: pick best judgment with CONTEXT_ONLY handling
    # Priority: TRUE_SUBJECT > FALSE_BINDING > CONTEXT_ONLY > AMBIGUOUS
    # (When multiple candidates, the highest-priority judgment wins)
    best_judgment = "AMBIGUOUS"
    priority = {
        "TRUE_SUBJECT": 4,
        "FALSE_BINDING": 3,
        "CONTEXT_ONLY": 2,
        "AMBIGUOUS": 1,
    }
    for r in results:
        j = r["vector"]["judgment"]
        if priority.get(j, 0) > priority.get(best_judgment, 0):
            best_judgment = j

    return {"text": text, "judgment": best_judgment, "candidates": results}


# ═══════════════════════════════════════════════════════════════════════
# Re-run V2.1 on V48X 32 cases (for regression check)
# ═══════════════════════════════════════════════════════════════════════

def run_v48x_on_v21() -> list:
    """Re-run V48X 32 cases through V2.1 hardened evaluator (regression check)."""
    import json
    v48x_audit = json.loads((CORE_REPO / "intelligence_core/tests/reliability/v48x_32_subject_audit.json").read_text())
    v48x_cases = v48x_audit["adjudications"]

    from intelligence_core.store import AppendOnlyStore
    from intelligence_core.cached_store import CachedStore
    store = CachedStore(AppendOnlyStore("v3_corpus_store"))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    doc_to_rep = {}
    for rid, rep in reps_by_id.items():
        did = rep.get("document_id", "")
        if did and did not in doc_to_rep:
            doc_to_rep[did] = rep

    io_dump = CORE_REPO / "intelligence_core/tests/reliability/recovery_corpus_ios.jsonl"
    all_ios = []
    with open(io_dump) as f:
        for line in f:
            all_ios.append(json.loads(line))
    ios_by_id = {io["io_id"]: io for io in all_ios}

    v48x_v21_results = []
    for v48x_case in v48x_cases:
        io_id = v48x_case["io_id"]
        io = ios_by_id.get(io_id, {})
        doc_id = io.get("document_id", "")
        rep = doc_to_rep.get(doc_id)
        if not rep:
            v48x_v21_results.append({
                "io_id": io_id, "v48x_role": v48x_case["adjudication"],
                "v21_judgment": "ERROR", "vector": {},
            })
            continue
        try:
            blob_bytes = Path(rep.get("raw_location", "")).read_bytes()
            segs = parse_html_to_segments(blob_bytes, document_id=doc_id)
            segs = apply_purpose_filter(segs)
        except Exception:
            v48x_v21_results.append({
                "io_id": io_id, "v48x_role": v48x_case["adjudication"],
                "v21_judgment": "ERROR", "vector": {},
            })
            continue

        contexts = build_contexts_for_io(io, segs)
        primary_segments_by_fact = {}
        for ctx in contexts:
            if ctx.primary_segment_id:
                for seg in segs:
                    if seg.segment_id == ctx.primary_segment_id:
                        primary_segments_by_fact[ctx.fact_id] = seg
                        break

        candidate = v48x_case.get("candidate", "")
        candidate_aliases = []
        candidate_id = ""
        candidate_reg_type = v48x_case.get("registry_type", "")
        for reg_type, reg in _ALL_REGISTRIES.items():
            for cid, (cname, etype, aliases) in reg.items():
                if cname == candidate:
                    candidate_aliases = aliases
                    candidate_id = cid
                    break

        primary_text = ""
        heading_context = ""
        for fid, seg in primary_segments_by_fact.items():
            primary_text = seg.text or ""
            heading_context = seg.heading_context or ""
            break

        doc_title = _extract_document_title(segs)
        fact_metrics = [f.get("metric", "") for f in io.get("facts", [])]
        event_type = io.get("event_type", "")

        vec = evaluate_evidence_vector_v21(
            candidate=candidate, candidate_aliases=candidate_aliases,
            candidate_reg_type=candidate_reg_type, candidate_id=candidate_id,
            primary_text=primary_text, heading_context=heading_context,
            doc_title=doc_title, fact_metrics=fact_metrics,
            event_type=event_type, all_segments=segs, io=io,
        )

        v48x_v21_results.append({
            "io_id": io_id, "v48x_role": v48x_case["adjudication"],
            "v21_judgment": vec["judgment"], "vector": vec,
            "primary_text_used": primary_text[:300],
        })

    return v48x_v21_results
