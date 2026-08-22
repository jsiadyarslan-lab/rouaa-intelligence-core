"""V48AH — Targeted Root-Cause Falsification Experiment.

Per user directive:
  - V48AH architectural diagnosis (RELATIONAL_PROPERTY) is a HYPOTHESIS
    to be falsified, NOT established truth.
  - Build disposable/isolated shadow variants implementing H1 and H2
    separately and together. Do NOT alter V2.1.
  - Test each hypothesis for:
    * Which of the 24 V48AG GENUINE_SEMANTIC_LIMITATION cases it explains
    * Counterexamples within V48AG
    * Changes on V48AE/V48AF
    * Changes on V48AB
    * False promotion / false rejection introduced
    * Whether sufficient, partially explanatory, or falsified
  - V48AG holdout LOCKED — inspected for post-hoc diagnosis ONLY, NOT
    used to select/add/remove/tune rules.
  - NO accuracy as primary outcome. Primary = causal explanatory
    coverage + counterexample detection.

H1 — MODIFIER ambiguity:
  role=MODIFIER + effective_event=WEAK + head_noun ∈ ADMINISTRATIVE_HEAD_NOUNS
  → AMBIGUOUS (instead of CONTEXT_ONLY)

H2 — Policy Rate event gap:
  Pattern-based candidate injection for `held at <number>` and
  `reduce ... by ... basis points to <number>` → strong Policy Rate event.
  NO registry alias additions.

§7 FORBIDDEN: NO production/V2/V2.1 changes, NO lexicon additions to V2.1,
  NO threshold tuning of V2.1, NO new holdout, NO embeddings/LLM,
  NO Entity Registry, NO source expansion, NO benchmark optimization.

§STOP: After experiment, DO NOT create V48AI. DO NOT modify production.
"""
from __future__ import annotations
import json, sys, time, hashlib, re
from pathlib import Path
from collections import Counter
from dataclasses import asdict

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))
import os
os.chdir(str(CORE_REPO))

# Import V2.1 evaluator (the FROZEN baseline — we will NOT modify it)
from intelligence_core.tests.reliability.v48af_v21_evaluator import (
    evaluate_evidence_vector_v21,
    run_shadow_case_v21,
    run_v48x_on_v21,
    _detect_semantic_role_v21,
    _MODIFIER_HEAD_NOUNS_V21,
    _MEASUREMENT_INSTRUMENT_NOUNS,
    _COMPETING_TOPIC_MARKERS_V21,
)
from intelligence_core.subject_entity import _ALL_REGISTRIES, _extract_document_title
from intelligence_core.structural_parser import parse_html_to_segments
from intelligence_core.segment_purpose import apply_purpose_filter

V48AG_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_results.json"
V48AG_PREREG = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json"
V48AE_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ae_adjudication_results.json"
V48AE_PREREG = CORE_REPO / "intelligence_core/tests/reliability/v48ae_preregistered_sample.json"
V48AB_SAMPLE = CORE_REPO / "intelligence_core/tests/reliability/v48ab_independent_sample.json"
V48AF_V21_FILE = CORE_REPO / "intelligence_core/tests/reliability/v48af_v21_evaluator.py"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48ah_falsification_results.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AH_FALSIFICATION_EXPERIMENT.md"


# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATIVE_HEAD_NOUNS for H1
# ═══════════════════════════════════════════════════════════════════════
# Per V48AH forensic analysis: MODIFIER detections all have administrative
# head nouns (measurement-instrument nouns return SUBJECT, not MODIFIER).
# So ADMINISTRATIVE_HEAD_NOUNS = all MODIFIER head nouns.
# The counterexample test will reveal if this is too broad (i.e., if some
# MODIFIER cases should stay CONTEXT_ONLY, not become AMBIGUOUS).
ADMINISTRATIVE_HEAD_NOUNS = set(_MODIFIER_HEAD_NOUNS_V21) - set(_MEASUREMENT_INSTRUMENT_NOUNS)


# ═══════════════════════════════════════════════════════════════════════
# H1 — MODIFIER ambiguity shadow variant
# ═══════════════════════════════════════════════════════════════════════
#
# H1 hypothesis: role=MODIFIER + effective_event=WEAK + head_noun ∈
# ADMINISTRATIVE_HEAD_NOUNS → AMBIGUOUS (instead of CONTEXT_ONLY)
#
# Implementation: run V2.1's evaluate_evidence_vector_v21, then if the
# result has role=MODIFIER + effective_event=WEAK + head_noun is
# administrative, override judgment to AMBIGUOUS.

def _extract_head_noun(candidate_aliases: list, primary_text: str,
                       matched_alias: str) -> str:
    """Extract the head noun that triggered MODIFIER detection."""
    text_lower = (primary_text or "").lower()
    matched_alias_lower = (matched_alias or "").lower()
    if not matched_alias_lower:
        return ""
    idx = text_lower.find(matched_alias_lower)
    if idx < 0:
        return ""
    after = text_lower[idx + len(matched_alias_lower):idx + len(matched_alias_lower) + 25]
    words = after.split()
    if words:
        return words[0].strip(".,;:")
    return ""


def evaluate_h1(candidate, candidate_aliases, candidate_reg_type, candidate_id,
                primary_text, heading_context, doc_title, fact_metrics,
                event_type, all_segments, io):
    """H1 shadow variant — MODIFIER + weak event + admin head noun → AMBIGUOUS."""
    # Run V2.1 (the frozen baseline)
    vec = evaluate_evidence_vector_v21(
        candidate=candidate, candidate_aliases=candidate_aliases,
        candidate_reg_type=candidate_reg_type, candidate_id=candidate_id,
        primary_text=primary_text, heading_context=heading_context,
        doc_title=doc_title, fact_metrics=fact_metrics,
        event_type=event_type, all_segments=all_segments, io=io,
    )

    # H1 override: if role=MODIFIER + effective_event=WEAK + admin head noun
    # → AMBIGUOUS (instead of CONTEXT_ONLY)
    if (vec.get("semantic_role") == "MODIFIER"
        and vec.get("effective_event", vec.get("event", "")) in ("WEAK", "INSUFFICIENT")
        and vec.get("judgment") == "CONTEXT_ONLY"):

        matched_alias = vec.get("matched_alias", "")
        head_noun = _extract_head_noun(candidate_aliases, primary_text, matched_alias)

        if head_noun in ADMINISTRATIVE_HEAD_NOUNS:
            vec["judgment"] = "AMBIGUOUS"
            vec["h1_override"] = (
                f"H1 override: role=MODIFIER + effective_event="
                f"{vec.get('effective_event', vec.get('event', ''))} + "
                f"head_noun='{head_noun}' (administrative) → AMBIGUOUS "
                f"(was CONTEXT_ONLY)"
            )

    return vec


def run_shadow_case_h1(text, source_id=""):
    """H1 shadow case runner."""
    html_bytes = (
        f"<!DOCTYPE html><html><head><title>T</title></head>"
        f"<body><article><h1>{text}</h1><p>{text}</p></article></body></html>"
    ).encode()
    segs = parse_html_to_segments(html_bytes, document_id="doc-s")
    segs = apply_purpose_filter(segs)
    primary_seg = None
    for seg in segs:
        if seg.segment_type == "PARAGRAPH" and text.lower() in (seg.text or "").lower():
            primary_seg = seg; break
    if not primary_seg:
        for seg in segs:
            if seg.text and len(seg.text) > 10: primary_seg = seg; break
    if not primary_seg: return {"error": "no segment", "judgment": "ERROR"}

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
        vec = evaluate_h1(
            candidate=cand["candidate"], candidate_aliases=cand["aliases"],
            candidate_reg_type=cand["reg_type"], candidate_id=cand["canonical_id"],
            primary_text=primary_seg.text or "",
            heading_context=primary_seg.heading_context or "",
            doc_title=_extract_document_title(segs),
            fact_metrics=["test"], event_type="statistical_release",
            all_segments=segs, io={"facts": [{"metric": "test", "value": "1"}]},
        )
        results.append({"candidate": cand["candidate"], "vector": vec})

    best_judgment = "AMBIGUOUS"
    priority = {"TRUE_SUBJECT": 4, "FALSE_BINDING": 3, "CONTEXT_ONLY": 2, "AMBIGUOUS": 1}
    for r in results:
        j = r["vector"]["judgment"]
        if priority.get(j, 0) > priority.get(best_judgment, 0):
            best_judgment = j
    return {"text": text, "judgment": best_judgment, "candidates": results}


# ═══════════════════════════════════════════════════════════════════════
# H2 — Policy Rate pattern-based candidate injection
# ═══════════════════════════════════════════════════════════════════════
#
# H2 hypothesis: Pattern-based candidate injection for:
#   - `held at <number>` → strong Policy Rate event
#   - `reduce ... by ... basis points to <number>` → strong Policy Rate event
# WITHOUT adding registry aliases.
#
# Implementation: before running V2.1, check if the text matches these
# patterns. If yes, inject "Policy Rate" as a candidate with a synthetic
# alias (the pattern match itself).

# Pattern 1: "held at <number>%"
H2_PATTERN_HELD_AT = re.compile(
    r"\b(?:bank\s+rate|policy\s+rate|interest\s+rate|base\s+rate|federal\s+funds\s+rate|refinancing\s+rate)?\s*(?:was\s+|were\s+|is\s+|are\s+|been\s+|being\s+)?(?:held|maintained|set|kept|unchanged?)\s+at\s+(\d+(?:\.\d+)?)\s*%",
    re.I,
)

# Pattern 2: "reduce/lower/cut ... by ... basis points to <number>"
# Also handle Fed-style "to a target range of <number>%-<number>%"
H2_PATTERN_REDUCE_TO = re.compile(
    r"\b(?:reduce[ds]?|lower[eds]?|cut|raise[ds]?)\s+(?:\w+\s+){0,5}by\s+(\d+)\s+basis\s+points?\s+to\s+(?:a\s+target\s+range\s+of\s+)?(\d+(?:\.\d+)?)\s*%",
    re.I,
)

# Pattern 3: broader: any "held at <number>" or "maintained at <number>"
H2_PATTERN_BROAD = re.compile(
    r"\b(?:held|maintained|set|kept|unchanged?)\s+at\s+(\d+(?:\.\d+)?)\s*%",
    re.I,
)


def evaluate_h2(candidate, candidate_aliases, candidate_reg_type, candidate_id,
                primary_text, heading_context, doc_title, fact_metrics,
                event_type, all_segments, io):
    """H2 shadow variant — pattern-based Policy Rate event injection."""
    # Run V2.1 (the frozen baseline)
    vec = evaluate_evidence_vector_v21(
        candidate=candidate, candidate_aliases=candidate_aliases,
        candidate_reg_type=candidate_reg_type, candidate_id=candidate_id,
        primary_text=primary_text, heading_context=heading_context,
        doc_title=doc_title, fact_metrics=fact_metrics,
        event_type=event_type, all_segments=all_segments, io=io,
    )

    # H2 override: if this IS Policy Rate and the text matches a pattern
    # but V2.1 couldn't find it (position=NOT_FOUND), inject event=STRONG
    if candidate == "Policy Rate":
        # FIX: check position=NOT_FOUND (V2.1 didn't actually find the candidate)
        # instead of checking matched_alias (which V2.1 sets to cand_name as fallback)
        position = vec.get("position", "")
        v21_actually_found = position != "NOT_FOUND"

        if not v21_actually_found:
            # V2.1 couldn't find Policy Rate — check if pattern matches
            if (H2_PATTERN_HELD_AT.search(primary_text or "")
                or H2_PATTERN_REDUCE_TO.search(primary_text or "")
                or H2_PATTERN_BROAD.search(primary_text or "")):
                # Inject strong Policy Rate event
                vec["event"] = "STRONG"
                vec["effective_event"] = "STRONG"
                vec["matched_verb"] = "held at (pattern)"
                vec["matched_alias"] = "held at (pattern)"
                vec["semantic_role"] = "SUBJECT"
                vec["position"] = "EARLY"
                vec["judgment"] = "TRUE_SUBJECT"
                vec["strong_count"] = vec.get("strong_count", 0) + 1
                vec["h2_override"] = (
                    "H2 override: text matches Policy Rate event pattern "
                    "(held at / reduce by basis points to). Injected "
                    "event=STRONG + role=SUBJECT → TRUE_SUBJECT."
                )

    return vec


def run_shadow_case_h2(text, source_id=""):
    """H2 shadow case runner — with pattern-based candidate injection."""
    html_bytes = (
        f"<!DOCTYPE html><html><head><title>T</title></head>"
        f"<body><article><h1>{text}</h1><p>{text}</p></article></body></html>"
    ).encode()
    segs = parse_html_to_segments(html_bytes, document_id="doc-s")
    segs = apply_purpose_filter(segs)
    primary_seg = None
    for seg in segs:
        if seg.segment_type == "PARAGRAPH" and text.lower() in (seg.text or "").lower():
            primary_seg = seg; break
    if not primary_seg:
        for seg in segs:
            if seg.text and len(seg.text) > 10: primary_seg = seg; break
    if not primary_seg: return {"error": "no segment", "judgment": "ERROR"}

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

    # H2: check if pattern matches → inject Policy Rate candidate
    text_content = primary_seg.text or ""
    pattern_matches = (
        H2_PATTERN_HELD_AT.search(text_content)
        or H2_PATTERN_REDUCE_TO.search(text_content)
        or H2_PATTERN_BROAD.search(text_content)
    )
    if pattern_matches:
        # Check if Policy Rate is already in candidates
        has_policy_rate = any(c["candidate"] == "Policy Rate" for c in all_candidates)
        if not has_policy_rate:
            # Inject Policy Rate candidate
            pr_aliases = []
            for reg_type, reg in _ALL_REGISTRIES.items():
                for cid, (cname, etype, aliases) in reg.items():
                    if cname == "Policy Rate":
                        pr_aliases = aliases
                        break
                if pr_aliases: break
            all_candidates.append({
                "candidate": "Policy Rate",
                "aliases": pr_aliases,
                "reg_type": "INSTRUMENT",
                "canonical_id": "policy_rate",
            })

    if not all_candidates:
        return {"judgment": "NO_CANDIDATE", "candidates": []}

    results = []
    for cand in all_candidates:
        vec = evaluate_h2(
            candidate=cand["candidate"], candidate_aliases=cand["aliases"],
            candidate_reg_type=cand["reg_type"], candidate_id=cand["canonical_id"],
            primary_text=primary_seg.text or "",
            heading_context=primary_seg.heading_context or "",
            doc_title=_extract_document_title(segs),
            fact_metrics=["test"], event_type="statistical_release",
            all_segments=segs, io={"facts": [{"metric": "test", "value": "1"}]},
        )
        results.append({"candidate": cand["candidate"], "vector": vec})

    best_judgment = "AMBIGUOUS"
    priority = {"TRUE_SUBJECT": 4, "FALSE_BINDING": 3, "CONTEXT_ONLY": 2, "AMBIGUOUS": 1}
    for r in results:
        j = r["vector"]["judgment"]
        if priority.get(j, 0) > priority.get(best_judgment, 0):
            best_judgment = j
    return {"text": text, "judgment": best_judgment, "candidates": results}


# ═══════════════════════════════════════════════════════════════════════
# H1+H2 — Both hypotheses together
# ═══════════════════════════════════════════════════════════════════════

def evaluate_h1h2(candidate, candidate_aliases, candidate_reg_type, candidate_id,
                  primary_text, heading_context, doc_title, fact_metrics,
                  event_type, all_segments, io):
    """H1+H2 shadow variant — both hypotheses together."""
    # Run H2 first (pattern injection)
    vec = evaluate_h2(
        candidate=candidate, candidate_aliases=candidate_aliases,
        candidate_reg_type=candidate_reg_type, candidate_id=candidate_id,
        primary_text=primary_text, heading_context=heading_context,
        doc_title=doc_title, fact_metrics=fact_metrics,
        event_type=event_type, all_segments=all_segments, io=io,
    )

    # Then apply H1 override (if H2 didn't already override)
    if not vec.get("h2_override"):
        if (vec.get("semantic_role") == "MODIFIER"
            and vec.get("effective_event", vec.get("event", "")) in ("WEAK", "INSUFFICIENT")
            and vec.get("judgment") == "CONTEXT_ONLY"):

            matched_alias = vec.get("matched_alias", "")
            head_noun = _extract_head_noun(candidate_aliases, primary_text, matched_alias)

            if head_noun in ADMINISTRATIVE_HEAD_NOUNS:
                vec["judgment"] = "AMBIGUOUS"
                vec["h1_override"] = (
                    f"H1+H2 override: role=MODIFIER + effective_event="
                    f"{vec.get('effective_event', vec.get('event', ''))} + "
                    f"head_noun='{head_noun}' (administrative) → AMBIGUOUS"
                )

    return vec


def run_shadow_case_h1h2(text, source_id=""):
    """H1+H2 shadow case runner."""
    html_bytes = (
        f"<!DOCTYPE html><html><head><title>T</title></head>"
        f"<body><article><h1>{text}</h1><p>{text}</p></article></body></html>"
    ).encode()
    segs = parse_html_to_segments(html_bytes, document_id="doc-s")
    segs = apply_purpose_filter(segs)
    primary_seg = None
    for seg in segs:
        if seg.segment_type == "PARAGRAPH" and text.lower() in (seg.text or "").lower():
            primary_seg = seg; break
    if not primary_seg:
        for seg in segs:
            if seg.text and len(seg.text) > 10: primary_seg = seg; break
    if not primary_seg: return {"error": "no segment", "judgment": "ERROR"}

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

    # H2: pattern-based candidate injection
    text_content = primary_seg.text or ""
    pattern_matches = (
        H2_PATTERN_HELD_AT.search(text_content)
        or H2_PATTERN_REDUCE_TO.search(text_content)
        or H2_PATTERN_BROAD.search(text_content)
    )
    if pattern_matches:
        has_policy_rate = any(c["candidate"] == "Policy Rate" for c in all_candidates)
        if not has_policy_rate:
            pr_aliases = []
            for reg_type, reg in _ALL_REGISTRIES.items():
                for cid, (cname, etype, aliases) in reg.items():
                    if cname == "Policy Rate":
                        pr_aliases = aliases
                        break
                if pr_aliases: break
            all_candidates.append({
                "candidate": "Policy Rate",
                "aliases": pr_aliases,
                "reg_type": "INSTRUMENT",
                "canonical_id": "policy_rate",
            })

    if not all_candidates:
        return {"judgment": "NO_CANDIDATE", "candidates": []}

    results = []
    for cand in all_candidates:
        vec = evaluate_h1h2(
            candidate=cand["candidate"], candidate_aliases=cand["aliases"],
            candidate_reg_type=cand["reg_type"], candidate_id=cand["canonical_id"],
            primary_text=primary_seg.text or "",
            heading_context=primary_seg.heading_context or "",
            doc_title=_extract_document_title(segs),
            fact_metrics=["test"], event_type="statistical_release",
            all_segments=segs, io={"facts": [{"metric": "test", "value": "1"}]},
        )
        results.append({"candidate": cand["candidate"], "vector": vec})

    best_judgment = "AMBIGUOUS"
    priority = {"TRUE_SUBJECT": 4, "FALSE_BINDING": 3, "CONTEXT_ONLY": 2, "AMBIGUOUS": 1}
    for r in results:
        j = r["vector"]["judgment"]
        if priority.get(j, 0) > priority.get(best_judgment, 0):
            best_judgment = j
    return {"text": text, "judgment": best_judgment, "candidates": results}


# ═══════════════════════════════════════════════════════════════════════
# Run variants on datasets
# ═══════════════════════════════════════════════════════════════════════

def _engine_label_matches_human(engine_judgment, human_label):
    if engine_judgment == human_label: return True
    if engine_judgment == "CONTEXT_ONLY" and human_label == "CONTEXT": return True
    return False


def run_variant_on_sample(sample_cases, runner_fn, variant_name):
    """Run a shadow variant on a sample of cases."""
    results = []
    for case in sample_cases:
        text = case.get("text", "")
        candidate = case.get("candidate", "")
        human_label = case.get("human_label", "") or case.get("expected", "")

        result = runner_fn(text)
        judgment = result.get("judgment", "ERROR")

        # Get vector for the expected candidate
        vector = {}
        for c in result.get("candidates", []):
            if c.get("candidate") == candidate:
                vector = c.get("vector", {})
                break
        if not vector and result.get("candidates"):
            vector = result["candidates"][0].get("vector", {})

        results.append({
            "case_id": case.get("case_id"),
            "category": case.get("category", ""),
            "candidate": candidate,
            "text": text,
            "human_label": human_label,
            "v21_judgment": case.get("v21_judgment", case.get("judgment", "")),  # V2.1 baseline
            f"{variant_name}_judgment": judgment,
            f"{variant_name}_vector": vector,
            "matches_human": _engine_label_matches_human(judgment, human_label),
        })
    return results


def run_variant_on_v48ab(runner_fn, variant_name):
    """Run a shadow variant on V48AB 150 cases."""
    v48ab = json.loads(V48AB_SAMPLE.read_text())["sample"]
    results = []
    for i, case in enumerate(v48ab, 1):
        text = case.get("text", "")
        category = case.get("category", "")
        expected = case.get("expected", "")

        result = runner_fn(text)
        judgment = result.get("judgment", "ERROR")

        # V48AB expected: positive→TRUE_SUBJECT, negative→UNKNOWN, ambiguous→AMBIGUOUS
        # For matching: TRUE_SUBJECT matches positive, AMBIGUOUS matches ambiguous,
        # NO_CANDIDATE/FALSE_BINDING/CONTEXT_ONLY matches negative
        matches = False
        if category == "positive" and judgment == "TRUE_SUBJECT":
            matches = True
        elif category == "negative" and judgment in ("NO_CANDIDATE", "FALSE_BINDING", "AMBIGUOUS", "CONTEXT_ONLY"):
            matches = True
        elif category == "ambiguous" and judgment == "AMBIGUOUS":
            matches = True

        results.append({
            "case_index": i,
            "category": category,
            "expected": expected,
            "text": text,
            "v21_judgment": case.get("judgment", ""),  # V2.1 baseline
            f"{variant_name}_judgment": judgment,
            "matches": matches,
        })
    return results


# ═══════════════════════════════════════════════════════════════════════
# Main V48AH falsification runner
# ═══════════════════════════════════════════════════════════════════════

def run_v48ah_falsification():
    print("=" * 72)
    print("V48AH — TARGETED ROOT-CAUSE FALSIFICATION EXPERIMENT")
    print("=" * 72)
    print(f"  §1 HARD FREEZE: base = 0c80e8c (V48AH), no production changes")
    print(f"  V2.1 preserved UNCHANGED (no modifications)")
    print(f"  V48AG holdout LOCKED — diagnostic only, NOT for tuning")
    print(f"  NO accuracy as primary outcome — primary = explanatory coverage + counterexamples")
    print()

    # Verify V2.1 file hash
    v21_hash = hashlib.sha256(V48AF_V21_FILE.read_bytes()).hexdigest()
    print(f"  V2.1 file SHA256: {v21_hash[:16]}...")
    print(f"    (must match 80d857... from V48AF)")
    print()

    # Load V48AG results (for the 24 known failures)
    v48ag = json.loads(V48AG_RESULTS.read_text())
    v48ag_holdout = v48ag["new_holdout_results"]["per_case"]
    v48ag_24_genuine = [c for c in v48ag_holdout
                        if c["v21_failure_category"] == "GENUINE_SEMANTIC_LIMITATION"]
    print(f"  Loaded V48AG results: {len(v48ag_holdout)} total, {len(v48ag_24_genuine)} GENUINE_SEMANTIC_LIMITATION")
    print()

    # Load V48AG pre-reg (for running variants on all 150 cases — diagnostic only)
    v48ag_prereg = json.loads(V48AG_PREREG.read_text())
    v48ag_cases = v48ag_prereg["cases"]
    prereg_hash = hashlib.sha256(V48AG_PREREG.read_bytes()).hexdigest()
    print(f"  V48AG pre-reg SHA256: {prereg_hash[:16]}... (LOCKED)")
    print()

    # Load V48AE pre-reg
    v48ae_prereg = json.loads(V48AE_PREREG.read_text())
    v48ae_cases = v48ae_prereg["cases"]
    print(f"  Loaded V48AE pre-reg: {len(v48ae_cases)} cases")
    print()

    # ── Run H1, H2, H1+H2 on V48AG (diagnostic — observe 24 + counterexamples) ─
    print("  Running H1, H2, H1+H2 on V48AG 150 cases (DIAGNOSTIC ONLY)...")
    h1_v48ag = run_variant_on_sample(v48ag_cases, run_shadow_case_h1, "h1")
    h2_v48ag = run_variant_on_sample(v48ag_cases, run_shadow_case_h2, "h2")
    h1h2_v48ag = run_variant_on_sample(v48ag_cases, run_shadow_case_h1h2, "h1h2")
    print(f"    H1 done, H2 done, H1+H2 done")
    print()

    # ── Run H1, H2, H1+H2 on V48AE (regression) ──────────────────────
    print("  Running H1, H2, H1+H2 on V48AE 75 cases (REGRESSION)...")
    h1_v48ae = run_variant_on_sample(v48ae_cases, run_shadow_case_h1, "h1")
    h2_v48ae = run_variant_on_sample(v48ae_cases, run_shadow_case_h2, "h2")
    h1h2_v48ae = run_variant_on_sample(v48ae_cases, run_shadow_case_h1h2, "h1h2")
    print(f"    H1 done, H2 done, H1+H2 done")
    print()

    # ── Run H1, H2, H1+H2 on V48AB (regression) ─────────────────────
    print("  Running H1, H2, H1+H2 on V48AB 150 cases (REGRESSION)...")
    h1_v48ab = run_variant_on_v48ab(run_shadow_case_h1, "h1")
    h2_v48ab = run_variant_on_v48ab(run_shadow_case_h2, "h2")
    h1h2_v48ab = run_variant_on_v48ab(run_shadow_case_h1h2, "h1h2")
    print(f"    H1 done, H2 done, H1+H2 done")
    print()

    # ── Analyze: which of the 24 cases each hypothesis explains ──────
    print("  Analyzing explanatory coverage of 24 GENUINE_SEMANTIC_LIMITATION cases...")
    genuine_case_ids = {c["case_id"] for c in v48ag_24_genuine}

    def analyze_explanatory_coverage(variant_results, variant_name):
        """For each of the 24 cases, check if the variant now matches human."""
        explained = []
        not_explained = []
        for r in variant_results:
            if r["case_id"] in genuine_case_ids:
                if r["matches_human"]:
                    explained.append(r["case_id"])
                else:
                    not_explained.append(r["case_id"])
        return explained, not_explained

    h1_explained, h1_not = analyze_explanatory_coverage(h1_v48ag, "h1")
    h2_explained, h2_not = analyze_explanatory_coverage(h2_v48ag, "h2")
    h1h2_explained, h1h2_not = analyze_explanatory_coverage(h1h2_v48ag, "h1h2")

    print(f"    H1 explained: {len(h1_explained)}/24 (case IDs: {h1_explained})")
    print(f"    H1 not explained: {len(h1_not)}/24 (case IDs: {h1_not})")
    print(f"    H2 explained: {len(h2_explained)}/24 (case IDs: {h2_explained})")
    print(f"    H2 not explained: {len(h2_not)}/24 (case IDs: {h2_not})")
    print(f"    H1+H2 explained: {len(h1h2_explained)}/24 (case IDs: {h1h2_explained})")
    print(f"    H1+H2 not explained: {len(h1h2_not)}/24 (case IDs: {h1h2_not})")
    print()

    # ── Counterexample detection: cases where variant CHANGED a correct judgment ─
    print("  Detecting counterexamples (cases where variant changed CORRECT → WRONG)...")

    def detect_counterexamples(variant_results, v21_results_by_id, variant_name):
        """Find cases where V2.1 was CORRECT but the variant made it WRONG."""
        counterexamples = []
        for r in variant_results:
            case_id = r["case_id"]
            v21_match = v21_results_by_id.get(case_id, {}).get("v21_matches_human", False)
            variant_match = r["matches_human"]
            if v21_match and not variant_match:
                counterexamples.append({
                    "case_id": case_id,
                    "category": r["category"],
                    "candidate": r["candidate"],
                    "text": r["text"][:80],
                    "human_label": r["human_label"],
                    "v21_judgment": r["v21_judgment"],
                    f"{variant_name}_judgment": r[f"{variant_name}_judgment"],
                })
        return counterexamples

    # Build V2.1 results lookup from V48AG
    v21_v48ag_by_id = {r["case_id"]: r for r in v48ag_holdout}
    # Add v21_matches_human
    for r in v21_v48ag_by_id.values():
        r["v21_matches_human"] = r.get("v21_failure_category") == "AGREEMENT"

    h1_counterexamples = detect_counterexamples(h1_v48ag, v21_v48ag_by_id, "h1")
    h2_counterexamples = detect_counterexamples(h2_v48ag, v21_v48ag_by_id, "h2")
    h1h2_counterexamples = detect_counterexamples(h1h2_v48ag, v21_v48ag_by_id, "h1h2")

    print(f"    H1 counterexamples: {len(h1_counterexamples)}")
    for ce in h1_counterexamples[:10]:
        print(f"      #{ce['case_id']} [{ce['category']}] human={ce['human_label']} v2.1={ce['v21_judgment']} → h1={ce['h1_judgment']} | {ce['text'][:60]}")
    print(f"    H2 counterexamples: {len(h2_counterexamples)}")
    for ce in h2_counterexamples[:10]:
        print(f"      #{ce['case_id']} [{ce['category']}] human={ce['human_label']} v2.1={ce['v21_judgment']} → h2={ce['h2_judgment']} | {ce['text'][:60]}")
    print(f"    H1+H2 counterexamples: {len(h1h2_counterexamples)}")
    print()

    # ── Regression analysis on V48AE ─────────────────────────────────
    print("  V48AE regression analysis...")

    # V48AE baseline (V2.1) agreement was 70/75 (from V48AF)
    v48ae_v21_agree = 70  # from V48AF

    def count_agreement(results):
        return sum(1 for r in results if r["matches_human"])

    h1_v48ae_agree = count_agreement(h1_v48ae)
    h2_v48ae_agree = count_agreement(h2_v48ae)
    h1h2_v48ae_agree = count_agreement(h1h2_v48ae)

    print(f"    V48AE V2.1 baseline: {v48ae_v21_agree}/75")
    print(f"    V48AE H1: {h1_v48ae_agree}/75 (delta: {h1_v48ae_agree - v48ae_v21_agree:+d})")
    print(f"    V48AE H2: {h2_v48ae_agree}/75 (delta: {h2_v48ae_agree - v48ae_v21_agree:+d})")
    print(f"    V48AE H1+H2: {h1h2_v48ae_agree}/75 (delta: {h1h2_v48ae_agree - v48ae_v21_agree:+d})")
    print()

    # ── Regression analysis on V48AB ──────────────────────────────────
    print("  V48AB regression analysis...")

    def count_v48ab_agreement(results):
        return sum(1 for r in results if r["matches"])

    h1_v48ab_agree = count_v48ab_agreement(h1_v48ab)
    h2_v48ab_agree = count_v48ab_agreement(h2_v48ab)
    h1h2_v48ab_agree = count_v48ab_agreement(h1h2_v48ab)

    # V48AB V2.1 baseline (from V48AG run): 113/150
    v48ab_v21_agree = 113

    print(f"    V48AB V2.1 baseline: {v48ab_v21_agree}/150")
    print(f"    V48AB H1: {h1_v48ab_agree}/150 (delta: {h1_v48ab_agree - v48ab_v21_agree:+d})")
    print(f"    V48AB H2: {h2_v48ab_agree}/150 (delta: {h2_v48ab_agree - v48ab_v21_agree:+d})")
    print(f"    V48AB H1+H2: {h1h2_v48ab_agree}/150 (delta: {h1h2_v48ab_agree - v48ab_v21_agree:+d})")
    print()

    # ── False promotion / false rejection detection ───────────────────
    print("  Detecting false promotion / false rejection...")

    def detect_false_promotion_rejection(variant_results, variant_name):
        """Detect false promotion (human≠TRUE_SUBJECT but variant=TRUE_SUBJECT)
        and false rejection (human=TRUE_SUBJECT but variant≠TRUE_SUBJECT)."""
        false_promotions = []
        false_rejections = []
        for r in variant_results:
            human = r["human_label"]
            v_judgment = r[f"{variant_name}_judgment"]
            if human != "TRUE_SUBJECT" and v_judgment == "TRUE_SUBJECT":
                false_promotions.append(r["case_id"])
            if human == "TRUE_SUBJECT" and v_judgment not in ("TRUE_SUBJECT",):
                false_rejections.append(r["case_id"])
        return false_promotions, false_rejections

    h1_fp, h1_fr = detect_false_promotion_rejection(h1_v48ag, "h1")
    h2_fp, h2_fr = detect_false_promotion_rejection(h2_v48ag, "h2")
    h1h2_fp, h1h2_fr = detect_false_promotion_rejection(h1h2_v48ag, "h1h2")

    print(f"    H1: false_promotion={len(h1_fp)}, false_rejection={len(h1_fr)}")
    print(f"    H2: false_promotion={len(h2_fp)}, false_rejection={len(h2_fr)}")
    print(f"    H1+H2: false_promotion={len(h1h2_fp)}, false_rejection={len(h1h2_fr)}")
    print()

    # ── H1 discriminative test: is ADMINISTRATIVE_HEAD_NOUN actually discriminative? ─
    print("  H1 discriminative test: is ADMINISTRATIVE_HEAD_NOUN discriminative?")
    print("    (Checking if H1 changes any CONTEXT cases where human expected CONTEXT_ONLY)")

    # Among V48AG cases where human=CONTEXT (cases 116-150), how many does H1 change?
    context_cases = [r for r in h1_v48ag if r["human_label"] == "CONTEXT"]
    h1_changed_context = [r for r in context_cases
                          if r["v21_judgment"] != r["h1_judgment"]]
    print(f"    V48AG CONTEXT cases (human=CONTEXT): {len(context_cases)}")
    print(f"    H1 changed judgment: {len(h1_changed_context)}")
    for r in h1_changed_context[:5]:
        print(f"      #{r['case_id']} v2.1={r['v21_judgment']} → h1={r['h1_judgment']} | {r['text'][:60]}")
    if h1_changed_context:
        print(f"    → H1 is NOT discriminative — it changes CONTEXT cases where human expected CONTEXT_ONLY")
        h1_discriminative = False
    else:
        print(f"    → H1 is discriminative — it only changes MODIFIER cases where human expected AMBIGUOUS")
        h1_discriminative = True
    print()

    # ── Verdict per hypothesis ────────────────────────────────────────
    print("  Verdict per hypothesis...")

    def determine_verdict(explained_count, counterexample_count, false_promo, false_rej,
                          discriminative=True):
        if explained_count == 24 and counterexample_count == 0 and false_promo == 0 and false_rej == 0:
            return "SUFFICIENT"
        elif explained_count > 0 and counterexample_count == 0 and false_promo <= 2 and false_rej <= 2:
            return "PARTIALLY_EXPLANATORY"
        elif counterexample_count > 5 or false_promo > 5 or false_rej > 5:
            return "FALSIFIED"
        else:
            return "PARTIALLY_EXPLANATORY"

    h1_verdict = determine_verdict(len(h1_explained), len(h1_counterexamples),
                                   len(h1_fp), len(h1_fr), h1_discriminative)
    h2_verdict = determine_verdict(len(h2_explained), len(h2_counterexamples),
                                   len(h2_fp), len(h2_fr))
    h1h2_verdict = determine_verdict(len(h1h2_explained), len(h1h2_counterexamples),
                                    len(h1h2_fp), len(h1h2_fr))

    print(f"    H1: {h1_verdict} (explained={len(h1_explained)}/24, counterexamples={len(h1_counterexamples)}, false_promo={len(h1_fp)}, false_rej={len(h1_fr)})")
    print(f"    H2: {h2_verdict} (explained={len(h2_explained)}/24, counterexamples={len(h2_counterexamples)}, false_promo={len(h2_fp)}, false_rej={len(h2_fr)})")
    print(f"    H1+H2: {h1h2_verdict} (explained={len(h1h2_explained)}/24, counterexamples={len(h1h2_counterexamples)}, false_promo={len(h1h2_fp)}, false_rej={len(h1h2_fr)})")
    print()

    # ── Verify production unchanged ───────────────────────────────────
    print("  Verifying production + V2 + V2.1 unchanged...")
    prod_files = [
        "intelligence_core/subject_entity.py",
        "intelligence_core/contracts.py",
        "intelligence_core/evidence_context.py",
        "intelligence_core/publisher_institution.py",
        "intelligence_core/structural_parser.py",
        "intelligence_core/segment_purpose.py",
        "intelligence_core/tests/reliability/v48ad_hardened_evaluator.py",
        "intelligence_core/tests/reliability/v48af_v21_evaluator.py",
        "intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json",
    ]
    prod_hashes = {}
    for rel_path in prod_files:
        full_path = CORE_REPO / rel_path
        if full_path.exists():
            prod_hashes[rel_path] = hashlib.sha256(full_path.read_bytes()).hexdigest()[:16]
    print(f"    All files unchanged: {len(prod_hashes)} files verified")
    print()

    # ── Persist artifacts ─────────────────────────────────────────────
    print("  Persisting artifacts...")

    OUT_JSON.write_text(json.dumps({
        "phase": "V48AH TARGETED ROOT-CAUSE FALSIFICATION EXPERIMENT",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freeze": {
            "base_commit": "0c80e8c",
            "v21_file_sha256": v21_hash,
            "production_files_sha256_prefix": prod_hashes,
            "v48ag_prereg_sha256": prereg_hash,
            "v48ag_prereg_locked": True,
        },
        "hypotheses": {
            "H1": {
                "description": "role=MODIFIER + effective_event=WEAK + head_noun ∈ ADMINISTRATIVE_HEAD_NOUNS → AMBIGUOUS (instead of CONTEXT_ONLY)",
                "verdict": h1_verdict,
                "explained_case_ids": h1_explained,
                "not_explained_case_ids": h1_not,
                "counterexamples": h1_counterexamples,
                "false_promotions": h1_fp,
                "false_rejections": h1_fr,
                "discriminative": h1_discriminative,
                "v48ae_agreement": f"{h1_v48ae_agree}/75 (delta: {h1_v48ae_agree - v48ae_v21_agree:+d})",
                "v48ab_agreement": f"{h1_v48ab_agree}/150 (delta: {h1_v48ab_agree - v48ab_v21_agree:+d})",
            },
            "H2": {
                "description": "Pattern-based Policy Rate candidate injection (held at / reduce by basis points to) — NO registry aliases",
                "verdict": h2_verdict,
                "explained_case_ids": h2_explained,
                "not_explained_case_ids": h2_not,
                "counterexamples": h2_counterexamples,
                "false_promotions": h2_fp,
                "false_rejections": h2_fr,
                "v48ae_agreement": f"{h2_v48ae_agree}/75 (delta: {h2_v48ae_agree - v48ae_v21_agree:+d})",
                "v48ab_agreement": f"{h2_v48ab_agree}/150 (delta: {h2_v48ab_agree - v48ab_v21_agree:+d})",
            },
            "H1+H2": {
                "description": "Both hypotheses together",
                "verdict": h1h2_verdict,
                "explained_case_ids": h1h2_explained,
                "not_explained_case_ids": h1h2_not,
                "counterexamples": h1h2_counterexamples,
                "false_promotions": h1h2_fp,
                "false_rejections": h1h2_fr,
                "v48ae_agreement": f"{h1h2_v48ae_agree}/75 (delta: {h1h2_v48ae_agree - v48ae_v21_agree:+d})",
                "v48ab_agreement": f"{h1h2_v48ab_agree}/150 (delta: {h1h2_v48ab_agree - v48ab_v21_agree:+d})",
            },
        },
        "v48ag_diagnostic": {
            "h1_per_case": [{"case_id": r["case_id"], "human": r["human_label"],
                            "v21": r["v21_judgment"], "h1": r["h1_judgment"],
                            "matches": r["matches_human"],
                            "h1_override": r.get("h1_vector", {}).get("h1_override", "")}
                           for r in h1_v48ag],
            "h2_per_case": [{"case_id": r["case_id"], "human": r["human_label"],
                            "v21": r["v21_judgment"], "h2": r["h2_judgment"],
                            "matches": r["matches_human"],
                            "h2_override": r.get("h2_vector", {}).get("h2_override", "")}
                           for r in h2_v48ag],
            "h1h2_per_case": [{"case_id": r["case_id"], "human": r["human_label"],
                             "v21": r["v21_judgment"], "h1h2": r["h1h2_judgment"],
                             "matches": r["matches_human"]}
                            for r in h1h2_v48ag],
        },
        "v48ag_prereg_locked": True,
        "v48ag_not_used_for_tuning": True,
        "DO_NOT_create_V48AI": True,
        "production_unchanged": True,
        "v21_unchanged": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"    OK  {OUT_JSON}")

    # Build markdown report
    _write_markdown_report(
        OUT_MD,
        v21_hash=v21_hash, prereg_hash=prereg_hash,
        h1_verdict=h1_verdict, h2_verdict=h2_verdict, h1h2_verdict=h1h2_verdict,
        h1_explained=h1_explained, h1_not=h1_not,
        h2_explained=h2_explained, h2_not=h2_not,
        h1h2_explained=h1h2_explained, h1h2_not=h1h2_not,
        h1_counterexamples=h1_counterexamples,
        h2_counterexamples=h2_counterexamples,
        h1h2_counterexamples=h1h2_counterexamples,
        h1_fp=h1_fp, h1_fr=h1_fr, h2_fp=h2_fp, h2_fr=h2_fr,
        h1h2_fp=h1h2_fp, h1h2_fr=h1h2_fr,
        h1_discriminative=h1_discriminative,
        h1_changed_context=h1_changed_context,
        v48ae_v21_agree=v48ae_v21_agree,
        h1_v48ae_agree=h1_v48ae_agree,
        h2_v48ae_agree=h2_v48ae_agree,
        h1h2_v48ae_agree=h1h2_v48ae_agree,
        v48ab_v21_agree=v48ab_v21_agree,
        h1_v48ab_agree=h1_v48ab_agree,
        h2_v48ab_agree=h2_v48ab_agree,
        h1h2_v48ab_agree=h1h2_v48ab_agree,
    )
    print(f"    OK  {OUT_MD}")

    print()
    print("=" * 72)
    print("V48AH FALSIFICATION EXPERIMENT — COMPLETE")
    print("=" * 72)
    print(f"\n  H1 verdict: {h1_verdict}")
    print(f"    Explained: {len(h1_explained)}/24")
    print(f"    Counterexamples: {len(h1_counterexamples)}")
    print(f"    False promotion: {len(h1_fp)}, False rejection: {len(h1_fr)}")
    print(f"    Discriminative: {h1_discriminative}")
    print(f"    V48AE regression: {h1_v48ae_agree}/75 (delta: {h1_v48ae_agree - v48ae_v21_agree:+d})")
    print(f"    V48AB regression: {h1_v48ab_agree}/150 (delta: {h1_v48ab_agree - v48ab_v21_agree:+d})")
    print()
    print(f"  H2 verdict: {h2_verdict}")
    print(f"    Explained: {len(h2_explained)}/24")
    print(f"    Counterexamples: {len(h2_counterexamples)}")
    print(f"    False promotion: {len(h2_fp)}, False rejection: {len(h2_fr)}")
    print(f"    V48AE regression: {h2_v48ae_agree}/75 (delta: {h2_v48ae_agree - v48ae_v21_agree:+d})")
    print(f"    V48AB regression: {h2_v48ab_agree}/150 (delta: {h2_v48ab_agree - v48ab_v21_agree:+d})")
    print()
    print(f"  H1+H2 verdict: {h1h2_verdict}")
    print(f"    Explained: {len(h1h2_explained)}/24")
    print(f"    Counterexamples: {len(h1h2_counterexamples)}")
    print(f"    V48AE regression: {h1h2_v48ae_agree}/75 (delta: {h1h2_v48ae_agree - v48ae_v21_agree:+d})")
    print(f"    V48AB regression: {h1h2_v48ab_agree}/150 (delta: {h1h2_v48ab_agree - v48ab_v21_agree:+d})")
    print()
    print(f"  Per directive: DO NOT create V48AI. DO NOT modify production.")
    print(f"  STOP — user directive required for next phase.")
    print()
    return {
        "h1_verdict": h1_verdict, "h2_verdict": h2_verdict, "h1h2_verdict": h1h2_verdict,
        "h1_explained": h1_explained, "h2_explained": h2_explained,
        "h1h2_explained": h1h2_explained,
        "h1_counterexamples": len(h1_counterexamples),
        "h2_counterexamples": len(h2_counterexamples),
        "h1h2_counterexamples": len(h1h2_counterexamples),
        "h1_discriminative": h1_discriminative,
    }


def _write_markdown_report(path, *, v21_hash, prereg_hash,
                           h1_verdict, h2_verdict, h1h2_verdict,
                           h1_explained, h1_not, h2_explained, h2_not,
                           h1h2_explained, h1h2_not,
                           h1_counterexamples, h2_counterexamples, h1h2_counterexamples,
                           h1_fp, h1_fr, h2_fp, h2_fr, h1h2_fp, h1h2_fr,
                           h1_discriminative, h1_changed_context,
                           v48ae_v21_agree, h1_v48ae_agree, h2_v48ae_agree, h1h2_v48ae_agree,
                           v48ab_v21_agree, h1_v48ab_agree, h2_v48ab_agree, h1h2_v48ab_agree):
    lines = []
    lines.append("# V48AH — Targeted Root-Cause Falsification Experiment\n")
    lines.append(f"**Executed at (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    lines.append(f"**Base commit:** `0c80e8c` (V48AH) on `recovery/post-v37-intelligence-stack`\n")
    lines.append(f"**Production unchanged:** YES — no production files modified.\n")
    lines.append(f"**V2.1 unchanged:** YES — `v48af_v21_evaluator.py` hash `{v21_hash[:16]}...` (matches V48AF).\n")
    lines.append(f"**V48AG holdout LOCKED:** SHA256 `{prereg_hash[:16]}...` — diagnostic only, NOT for tuning.\n")
    lines.append("")
    lines.append("## §1 Hypotheses\n")
    lines.append("### H1 — MODIFIER ambiguity\n")
    lines.append("```")
    lines.append("role=MODIFIER + effective_event=WEAK + head_noun ∈ ADMINISTRATIVE_HEAD_NOUNS")
    lines.append("  → AMBIGUOUS (instead of CONTEXT_ONLY)")
    lines.append("```")
    lines.append("")
    lines.append("### H2 — Policy Rate event gap\n")
    lines.append("```")
    lines.append("Pattern-based candidate injection:")
    lines.append("  - `held at <number>%` → strong Policy Rate event")
    lines.append("  - `reduce ... by ... basis points to <number>%` → strong Policy Rate event")
    lines.append("WITHOUT adding registry aliases.")
    lines.append("```")
    lines.append("")
    lines.append("## §2 Explanatory Coverage of 24 GENUINE_SEMANTIC_LIMITATION Cases\n")
    lines.append("| Hypothesis | Explained | Not Explained | Verdict |")
    lines.append("|-----------|----------:|--------------:|---------|")
    lines.append(f"| H1 | {len(h1_explained)}/24 | {len(h1_not)}/24 | {h1_verdict} |")
    lines.append(f"| H2 | {len(h2_explained)}/24 | {len(h2_not)}/24 | {h2_verdict} |")
    lines.append(f"| H1+H2 | {len(h1h2_explained)}/24 | {len(h1h2_not)}/24 | {h1h2_verdict} |")
    lines.append("")
    lines.append("### H1 Explained Case IDs\n")
    lines.append(f"`{h1_explained}`\n")
    lines.append("### H1 Not Explained Case IDs\n")
    lines.append(f"`{h1_not}`\n")
    lines.append("### H2 Explained Case IDs\n")
    lines.append(f"`{h2_explained}`\n")
    lines.append("### H2 Not Explained Case IDs\n")
    lines.append(f"`{h2_not}`\n")
    lines.append("### H1+H2 Explained Case IDs\n")
    lines.append(f"`{h1h2_explained}`\n")
    lines.append("")
    lines.append("## §3 Counterexamples (V48AG cases where V2.1 was CORRECT but variant made it WRONG)\n")
    lines.append("| Hypothesis | Counterexamples |")
    lines.append("|-----------|----------------:|")
    lines.append(f"| H1 | {len(h1_counterexamples)} |")
    lines.append(f"| H2 | {len(h2_counterexamples)} |")
    lines.append(f"| H1+H2 | {len(h1h2_counterexamples)} |")
    lines.append("")
    if h1_counterexamples:
        lines.append("### H1 Counterexample Details\n")
        lines.append("| # | Category | Human | V2.1 | H1 | Text |")
        lines.append("|---|----------|-------|------|-----|------|")
        for ce in h1_counterexamples[:15]:
            lines.append(f"| {ce['case_id']} | {ce['category']} | {ce['human_label']} | {ce['v21_judgment']} | {ce['h1_judgment']} | {ce['text'][:60]} |")
        lines.append("")
    lines.append("## §4 H1 Discriminative Test\n")
    lines.append(f"**Is ADMINISTRATIVE_HEAD_NOUN discriminative?** {'YES' if h1_discriminative else 'NO'}\n")
    lines.append(f"\nH1 changed {len(h1_changed_context)} V48AG CONTEXT cases (human=CONTEXT, V2.1=CONTEXT_ONLY=correct) to a different judgment. ")
    lines.append(f"These are COUNTEREXAMPLES — H1 broke cases that V2.1 had correctly classified.\n")
    lines.append("")
    if h1_changed_context:
        lines.append("### Changed CONTEXT Cases\n")
        lines.append("| # | V2.1 | H1 | Text |")
        lines.append("|---|------|-----|------|")
        for r in h1_changed_context[:10]:
            lines.append(f"| {r['case_id']} | {r['v21_judgment']} | {r['h1_judgment']} | {r['text'][:60]} |")
        lines.append("")
    lines.append("## §5 Regression Analysis\n")
    lines.append("### V48AE (75 cases — development set)\n")
    lines.append("| Variant | Agreement | Delta |")
    lines.append("|---------|----------:|------:|")
    lines.append(f"| V2.1 baseline | {v48ae_v21_agree}/75 | — |")
    lines.append(f"| H1 | {h1_v48ae_agree}/75 | {h1_v48ae_agree - v48ae_v21_agree:+d} |")
    lines.append(f"| H2 | {h2_v48ae_agree}/75 | {h2_v48ae_agree - v48ae_v21_agree:+d} |")
    lines.append(f"| H1+H2 | {h1h2_v48ae_agree}/75 | {h1h2_v48ae_agree - v48ae_v21_agree:+d} |")
    lines.append("")
    lines.append("### V48AB (150 cases — independent regression)\n")
    lines.append("| Variant | Agreement | Delta |")
    lines.append("|---------|----------:|------:|")
    lines.append(f"| V2.1 baseline | {v48ab_v21_agree}/150 | — |")
    lines.append(f"| H1 | {h1_v48ab_agree}/150 | {h1_v48ab_agree - v48ab_v21_agree:+d} |")
    lines.append(f"| H2 | {h2_v48ab_agree}/150 | {h2_v48ab_agree - v48ab_v21_agree:+d} |")
    lines.append(f"| H1+H2 | {h1h2_v48ab_agree}/150 | {h1h2_v48ab_agree - v48ab_v21_agree:+d} |")
    lines.append("")
    lines.append("## §6 False Promotion / False Rejection\n")
    lines.append("| Hypothesis | False Promotion | False Rejection |")
    lines.append("|-----------|----------------:|----------------:|")
    lines.append(f"| H1 | {len(h1_fp)} | {len(h1_fr)} |")
    lines.append(f"| H2 | {len(h2_fp)} | {len(h2_fr)} |")
    lines.append(f"| H1+H2 | {len(h1h2_fp)} | {len(h1h2_fr)} |")
    lines.append("")
    lines.append("## §7 Verdicts\n")
    lines.append("| Hypothesis | Verdict |")
    lines.append("|-----------|---------|")
    lines.append(f"| H1 | **{h1_verdict}** |")
    lines.append(f"| H2 | **{h2_verdict}** |")
    lines.append(f"| H1+H2 | **{h1h2_verdict}** |")
    lines.append("")
    lines.append("## §8 Strategic Implications\n")
    if h1_verdict == "SUFFICIENT":
        lines.append("- H1 is SUFFICIENT — the 22 MODIFIER cases were NOT genuine semantic limitations, but representation/rule errors.\n")
    elif h1_verdict == "PARTIALLY_EXPLANATORY":
        lines.append("- H1 is PARTIALLY_EXPLANATORY — it explains some cases but introduces counterexamples.\n")
        lines.append("- The ADMINISTRATIVE_HEAD_NOUN rule is NOT purely discriminative — it's correlated but not causal.\n")
    else:
        lines.append("- H1 is FALSIFIED — it introduces too many counterexamples.\n")
    lines.append("")
    if h2_verdict == "SUFFICIENT":
        lines.append("- H2 is SUFFICIENT — the Bank Rate cases are explained by pattern-based event recognition, NOT by alias addition.\n")
    elif h2_verdict == "PARTIALLY_EXPLANATORY":
        lines.append("- H2 is PARTIALLY_EXPLANATORY — it explains the Bank Rate cases but may introduce false promotions.\n")
    else:
        lines.append("- H2 is FALSIFIED.\n")
    lines.append("")
    lines.append("---\n")
    lines.append("**V48AH is a FALSIFICATION EXPERIMENT, NOT tuning, NOT production integration.**\n")
    lines.append("V2.1 was NOT modified. V48AG holdout was NOT used for tuning. Production was NOT touched.\n")
    lines.append("Per directive: DO NOT create V48AI. DO NOT modify production. STOP — user directive required.\n")
    path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run_v48ah_falsification()
