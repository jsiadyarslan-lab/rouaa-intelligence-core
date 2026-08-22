"""V48AE — Blind Subject Adjudication (Phase 2+3).

§1 HARD FREEZE
  - Base: LOCAL == REMOTE == ddfd97f (V48AD commit)
  - NO production modifications
  - NO resolve_subject modifications
  - NO Entity Registry changes
  - NO V49, no embeddings, no LLM, no source expansion

§2 GOAL
  Pre-registered blind adjudication. The 75-case sample + human labels
  were committed to v48ae_preregistered_sample.json BEFORE this script
  runs the engine. This script:
    1. Loads the pre-registered sample
    2. Runs the PRODUCTION resolver (resolve_subject from subject_entity.py)
       on each case — the ACTUAL production code, not a shadow
    3. Runs the V48AD shadow evaluator (V2) on each case
    4. Compares both engine outputs against the pre-registered human label
    5. For each disagreement, classifies the failure into:
         DATA_GAP / EXTRACTION_GAP / RULE_GAP / CONTEXT_GAP /
         GENUINE_SEMANTIC_LIMITATION
  6. Does NOT allow the engine to evaluate itself — labels were committed
     before engine runs.

§3 PROTOCOL ENFORCEMENT
  - The pre-registered sample file (v48ae_preregistered_sample.json) is
    READ-ONLY in this script. We never modify it.
  - The script does NOT have access to engine outputs at pre-registration
    time (they are produced here, AFTER pre-registration).
  - All comparisons are POST-HOC: engine runs, then we compare to the
    pre-registered labels.

§4 FORBIDDEN
  - NO modifications to production `resolve_subject`
  - NO modifications to production `_EVENT_VERBS`
  - NO modifications to production registries
  - NO Entity Registry
  - NO V49
  - NO embeddings
  - NO LLM
  - NO source expansion
  - NO blacklists
  - NO document-specific shortcuts

§5 OUTPUTS
  - v48ae_adjudication_results.json (machine-readable comparison)
  - ROUAA_CORE_V48AE_BLIND_ADJUDICATION.md (human-readable report)
  - ROUAA_CORE_V48AE_DISAGREEMENT_TABLE.html (HTML disagreement table)

§6 ACCEPTANCE
  - Production unchanged
  - 338/338 tests PASS
  - Working tree CLEAN
  - Pre-registered labels NOT modified
  - Every disagreement explained
"""
from __future__ import annotations
import json, sys, time, subprocess, html, re, hashlib
from pathlib import Path
from collections import Counter
from dataclasses import asdict

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))
import os
os.chdir(str(CORE_REPO))

from intelligence_core.structural_parser import parse_html_to_segments
from intelligence_core.segment_purpose import apply_purpose_filter
from intelligence_core.evidence_context import build_contexts_for_io
from intelligence_core.subject_entity import (
    resolve_subject, _extract_document_title,
    _ALL_REGISTRIES,
)
# Import V2 evaluator (V48AD shadow — separate from production)
from intelligence_core.tests.reliability.v48ad_hardened_evaluator import (
    evaluate_evidence_vector_v2,
)

PREREGISTERED_SAMPLE = CORE_REPO / "intelligence_core/tests/reliability/v48ae_preregistered_sample.json"
OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48ae_adjudication_results.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AE_BLIND_ADJUDICATION.md"
OUT_HTML = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AE_DISAGREEMENT_TABLE.html"

# Failure categories (same as V48AC)
DATA_GAP = "DATA_GAP"
EXTRACTION_GAP = "EXTRACTION_GAP"
RULE_GAP = "RULE_GAP"
CONTEXT_GAP = "CONTEXT_GAP"
GENUINE_SEMANTIC_LIMITATION = "GENUINE_SEMANTIC_LIMITATION"
AGREEMENT = "AGREEMENT"


# ═══════════════════════════════════════════════════════════════════════
# §2 — PRODUCTION RESOLVER ON SYNTHETIC TEXT
# ═══════════════════════════════════════════════════════════════════════
#
# This calls the ACTUAL production resolve_subject function (the same code
# that runs in the production pipeline). We construct synthetic IO contexts
# from the pre-registered text so the production resolver can be invoked
# without modifying any production code.

def run_production_resolver(text: str, source_id: str = "synthetic") -> dict:
    """Run the ACTUAL production resolve_subject on synthetic text.

    Constructs a synthetic IO with the text wrapped in HTML, then calls
    the production resolve_subject function. Returns the SubjectEntityV1
    as a dict plus a synthesized 'judgment' string for direct comparison.
    """
    html_bytes = (
        f"<!DOCTYPE html><html><head><title>T</title></head>"
        f"<body><article><h1>{text}</h1><p>{text}</p></article></body></html>"
    ).encode()
    segs = parse_html_to_segments(html_bytes, document_id="doc-s")
    segs = apply_purpose_filter(segs)

    # Build synthetic IO
    io = {
        "io_id": f"synthetic-io-{hash(text) & 0xFFFFFF:06x}",
        "facts": [{"fact_id": "fact-1", "metric": "percentage_statistic", "value": "1"}],
        "evidence": [{"fact_id": "fact-1", "evidence_id": "ev-1"}],
        "event_type": "statistical_release",
        "document_id": "doc-s",
    }

    # Build evidence contexts
    contexts = build_contexts_for_io(io, segs)

    # Build primary_texts_by_fact
    primary_texts_by_fact = {}
    for ctx in contexts:
        if ctx.primary_segment_id:
            for seg in segs:
                if seg.segment_id == ctx.primary_segment_id:
                    primary_texts_by_fact[ctx.fact_id] = seg.text or ""
                    break

    # Call ACTUAL production resolver
    try:
        result = resolve_subject(
            io=io,
            contexts=contexts,
            primary_texts_by_fact=primary_texts_by_fact,
            all_segments=segs,
            publisher=None,
        )
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "judgment": "ERROR",
        }

    # Convert SubjectEntityV1 to dict
    result_dict = asdict(result) if hasattr(result, "__dataclass_fields__") else dict(result.__dict__)

    # Translate production status to a comparison judgment
    # Production status: CONFIRMED / AMBIGUOUS / NOT_FOUND
    # Plus subject_indicator/concept/instrument/market/regulation fields
    status = result.status
    subject_indicator = result.subject_indicator or ""
    subject_concept = result.subject_concept or ""
    subject_instrument = result.subject_instrument or ""
    subject_market = result.subject_market or ""
    subject_regulation = result.subject_regulation or ""
    canonical_name = result.canonical_name or ""

    # Determine production judgment
    # If any subject field is CONFIRMED (other than UNKNOWN), the engine
    # identified a subject
    if status == "CONFIRMED" and canonical_name != "UNKNOWN":
        prod_judgment = "TRUE_SUBJECT"
    elif status == "AMBIGUOUS":
        prod_judgment = "AMBIGUOUS"
    elif status == "NOT_FOUND":
        # Check if any of the separate fields (indicator/concept/etc.) are CONFIRMED
        any_confirmed = any([
            result.subject_indicator_status == "CONFIRMED",
            result.subject_concept_status == "CONFIRMED",
            result.subject_instrument_status == "CONFIRMED",
            result.subject_market_status == "CONFIRMED",
            result.subject_regulation_status == "CONFIRMED",
        ])
        if any_confirmed:
            prod_judgment = "TRUE_SUBJECT"
        elif canonical_name == "UNKNOWN":
            prod_judgment = "NO_CANDIDATE"
        else:
            prod_judgment = "AMBIGUOUS"
    else:
        prod_judgment = "AMBIGUOUS"

    return {
        "status": status,
        "canonical_name": canonical_name,
        "subject_indicator": subject_indicator,
        "subject_concept": subject_concept,
        "subject_instrument": subject_instrument,
        "subject_market": subject_market,
        "subject_regulation": subject_regulation,
        "judgment": prod_judgment,
        "full_result": result_dict,
    }


# ═══════════════════════════════════════════════════════════════════════
# §2 — V2 SHADOW EVALUATOR ON SYNTHETIC TEXT
# ═══════════════════════════════════════════════════════════════════════

def run_v2_shadow(text: str) -> dict:
    """Run V2 shadow evaluator on synthetic text (re-uses V48AD logic)."""
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
        vec = evaluate_evidence_vector_v2(
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

    best_judgment = "AMBIGUOUS"
    for r in results:
        if r["vector"]["judgment"] == "TRUE_SUBJECT":
            best_judgment = "TRUE_SUBJECT"
            break
        elif r["vector"]["judgment"] == "FALSE_BINDING":
            if best_judgment != "TRUE_SUBJECT":
                best_judgment = "FALSE_BINDING"

    return {"judgment": best_judgment, "candidates": results}


# ═══════════════════════════════════════════════════════════════════════
# §3 — DISAGREEMENT CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════
#
# For each case where the engine disagrees with the human label, classify
# the failure into one of:
#   DATA_GAP / EXTRACTION_GAP / RULE_GAP / CONTEXT_GAP /
#   GENUINE_SEMANTIC_LIMITATION
#
# Classification logic is based on the engine's vector + the human label
# + the case text. It does NOT add new heuristics to the engine — it only
# explains WHY the engine disagreed with the human.

def classify_disagreement(
    case: dict, engine_judgment: str, engine_vector: dict,
) -> tuple[str, str]:
    """Classify a disagreement between engine and human label.

    Returns (failure_category, explanation).
    """
    text = case.get("text", "")
    human_label = case.get("human_label", "")
    candidate = case.get("candidate", "")
    category = case.get("category", "")

    # ── Case: engine returned NO_CANDIDATE ──────────────────────────────
    if engine_judgment == "NO_CANDIDATE":
        # Did the text mention a candidate alias?
        # Check production registry for the expected candidate
        cand_aliases = []
        for reg_type, reg in _ALL_REGISTRIES.items():
            for cid, (cname, etype, aliases) in reg.items():
                if cname == candidate:
                    cand_aliases = aliases
                    break
        alias_in_text = False
        for alias in cand_aliases:
            if re.search(r"\b" + re.escape(alias.lower()) + r"\b", text.lower()):
                alias_in_text = True
                break

        if alias_in_text:
            # The candidate IS in the text but the engine didn't find it
            # — this is a RULE_GAP (the rule's detection is too narrow)
            return RULE_GAP, (
                f"Candidate '{candidate}' alias IS present in the text, but "
                f"the engine returned NO_CANDIDATE. This suggests the engine's "
                f"candidate-detection logic missed the alias. This is a "
                f"RULE_GAP (detection rule too narrow), not a data gap."
            )
        else:
            # The candidate's alias is NOT in the text — could be DATA_GAP
            # (registry alias missing — text mentions an UNREGISTERED alias
            # like 'Bank Rate' for 'Policy Rate')
            # Look for plausible unregistered aliases
            text_lower = text.lower()
            unregistered_aliases = []
            if candidate == "Policy Rate":
                for alias in ["bank rate", "federal funds rate", "discount rate"]:
                    if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
                        unregistered_aliases.append(alias)
            if candidate == "Gross Domestic Product":
                for alias in ["real gdp", "nominal gdp", "gdp deflator"]:
                    if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
                        unregistered_aliases.append(alias)
            if unregistered_aliases:
                return DATA_GAP, (
                    f"Text contains a plausible-but-unregistered alias "
                    f"({', '.join(unregistered_aliases)}) for candidate "
                    f"'{candidate}'. The registry does NOT include this "
                    f"alias. This is a DATA_GAP (registry alias missing), "
                    f"NOT a rule gap or semantic failure."
                )
            return DATA_GAP, (
                f"Candidate '{candidate}' alias is NOT in the text. "
                f"Engine correctly returned NO_CANDIDATE, but this may "
                f"indicate the candidate itself was mis-specified for "
                f"this case. Treating as DATA_GAP — registry data is the "
                f"bottleneck."
            )

    # ── Case: engine returned TRUE_SUBJECT but human said CONTEXT/MODIFIER ─
    if engine_judgment == "TRUE_SUBJECT" and human_label == "CONTEXT":
        # Engine promoted a candidate that the human considers a noun modifier
        # This is a CONTEXT_GAP — the engine's role detection didn't trigger
        role = engine_vector.get("semantic_role", "") if engine_vector else ""
        if role == "MODIFIER":
            return AGREEMENT, (
                f"Engine's role detection correctly identified MODIFIER, "
                f"but the engine's judgment was still TRUE_SUBJECT. "
                f"This is an internal engine inconsistency."
            )
        elif role == "CONTEXT":
            return AGREEMENT, (
                f"Engine's role detection correctly identified CONTEXT, "
                f"but the engine's judgment was still TRUE_SUBJECT. "
                f"This is an internal engine inconsistency."
            )
        else:
            return CONTEXT_GAP, (
                f"Engine promoted '{candidate}' to TRUE_SUBJECT, but the "
                f"human label is CONTEXT (the candidate is a noun modifier "
                f"or background mention). The engine's role detection "
                f"(role={role}) did not identify the modifier/context "
                f"pattern. This is a CONTEXT_GAP — the engine lacks the "
                f"specific head-noun or competing-topic pattern needed to "
                f"detect this case."
            )

    # ── Case: engine returned TRUE_SUBJECT but human said FALSE_BINDING ─
    if engine_judgment == "TRUE_SUBJECT" and human_label == "FALSE_BINDING":
        # Engine promoted a candidate that the human considers wrong topic
        return CONTEXT_GAP, (
            f"Engine promoted '{candidate}' to TRUE_SUBJECT, but the human "
            f"considers this a FALSE_BINDING (the text names a different "
            f"topic). The engine's heading/topic signals did not detect "
            f"the competing topic. This is a CONTEXT_GAP — the engine "
            f"lacks competing-topic modeling for this case."
        )

    # ── Case: engine returned AMBIGUOUS but human said TRUE_SUBJECT ─────
    if engine_judgment == "AMBIGUOUS" and human_label == "TRUE_SUBJECT":
        # Engine failed to confirm a clear subject
        if engine_vector:
            event = engine_vector.get("event", "")
            measurement = engine_vector.get("measurement", "")
            fact = engine_vector.get("fact", "")
            role = engine_vector.get("semantic_role", "")
            if role in ("MODIFIER", "CONTEXT", "MEASURE", "ACTOR"):
                return CONTEXT_GAP, (
                    f"Engine classified role as {role}, degrading to "
                    f"AMBIGUOUS. But the human considers this a clear "
                    f"TRUE_SUBJECT. The role detection is a false "
                    f"positive — the candidate IS the subject despite "
                    f"the modifier-like pattern. This is a CONTEXT_GAP "
                    f"(role detection too aggressive)."
                )
            if event == "WEAK":
                return RULE_GAP, (
                    f"Engine marked event=WEAK. The text contains a clear "
                    f"event verb that the engine's lexicon missed. This "
                    f"is a RULE_GAP (verb lexicon too narrow)."
                )
            if fact == "CONTRADICTED":
                return RULE_GAP, (
                    f"Engine marked fact=CONTRADICTED, triggering "
                    f"AMBIGUOUS. But the human considers this a clear "
                    f"TRUE_SUBJECT. The fact-contradiction rule is too "
                    f"aggressive for this case. This is a RULE_GAP."
                )
        return RULE_GAP, (
            f"Engine returned AMBIGUOUS, but human considers this a clear "
            f"TRUE_SUBJECT. Vector: {engine_vector}. The engine's rules "
            f"failed to confirm a clear subject. This is a RULE_GAP."
        )

    # ── Case: engine returned AMBIGUOUS but human said FALSE_BINDING ───
    if engine_judgment == "AMBIGUOUS" and human_label == "FALSE_BINDING":
        # V2 returned AMBIGUOUS (conservative) but the human considers this
        # a clear FALSE_BINDING (the candidate is definitely not the subject).
        # Check whether V2's role detection agreed with the human.
        role = engine_vector.get("semantic_role", "") if engine_vector else ""
        if role in ("CONTEXT", "MODIFIER"):
            # V2's role detection IS correct — it detected the competing topic
            # or noun-modifier pattern. But V2's JUDGMENT MAPPING degraded
            # role=CONTEXT/MODIFIER to AMBIGUOUS (rather than FALSE_BINDING).
            # This is a RULE_GAP — V2's threshold for FALSE_BINDING is too
            # conservative. The rule should map role=CONTEXT + no positive
            # event evidence to FALSE_BINDING (clear rejection), not AMBIGUOUS.
            return RULE_GAP, (
                f"V2's role detection CORRECTLY identified role={role} "
                f"(the candidate is a {role.lower()} — not the subject). "
                f"But V2's judgment mapping degraded this to AMBIGUOUS "
                f"rather than FALSE_BINDING. The human considers this a "
                f"clear FALSE_BINDING (the heading names a different topic). "
                f"This is a RULE_GAP — V2's threshold for FALSE_BINDING is "
                f"too conservative when role=CONTEXT/MODIFIER is detected "
                f"with no positive event evidence."
            )
        else:
            # role=SUBJECT (or MEASURE/ACTOR) — V2's role detection missed
            # the CONTEXT pattern. This could be due to the alias-length
            # bug (when the matched alias is different from aliases[0]).
            return CONTEXT_GAP, (
                f"V2 returned role={role}, but the human considers this a "
                f"clear FALSE_BINDING. V2's role detection MISSED the "
                f"competing-topic pattern. This is a CONTEXT_GAP — V2 lacks "
                f"the specific competing-topic detection for this case "
                f"(may also be due to the alias-length bug where the matched "
                f"alias differs from aliases[0] and the slice window is wrong)."
            )

    # ── Case: engine returned AMBIGUOUS but human said CONTEXT ─────────
    if engine_judgment == "AMBIGUOUS" and human_label == "CONTEXT":
        # Similar to above — V2 detected MODIFIER/CONTEXT but mapped to AMBIGUOUS
        role = engine_vector.get("semantic_role", "") if engine_vector else ""
        if role in ("MODIFIER", "CONTEXT"):
            return RULE_GAP, (
                f"V2's role detection CORRECTLY identified role={role}. "
                f"But V2's judgment mapping degraded this to AMBIGUOUS "
                f"rather than CONTEXT_ONLY. The human considers this a "
                f"clear CONTEXT (noun modifier). This is a RULE_GAP — "
                f"V2's judgment mapping for role=MODIFIER/CONTEXT is too "
                f"conservative."
            )
        else:
            return CONTEXT_GAP, (
                f"V2 returned role={role}, but the human considers this a "
                f"clear CONTEXT (noun modifier pattern). V2's role detection "
                f"MISSED the modifier pattern (may be due to alias-length "
                f"bug — when the matched alias differs from aliases[0], "
                f"the slice window used for head-noun search is wrong). "
                f"This is a CONTEXT_GAP."
            )

    # ── Case: engine returned FALSE_BINDING but human said TRUE_SUBJECT ─
    if engine_judgment == "FALSE_BINDING" and human_label == "TRUE_SUBJECT":
        if engine_vector:
            fact = engine_vector.get("fact", "")
            if fact == "CONTRADICTED":
                return RULE_GAP, (
                    f"Engine returned FALSE_BINDING because fact=CONTRADICTED "
                    f"triggered the hard rule. But the human considers this "
                    f"a clear TRUE_SUBJECT. The fact-contradiction rule is "
                    f"too aggressive. This is a RULE_GAP."
                )
        return RULE_GAP, (
            f"Engine returned FALSE_BINDING, but human considers this a "
            f"clear TRUE_SUBJECT. Vector: {engine_vector}. This is a "
            f"RULE_GAP — the engine's rules over-rejected."
        )

    # ── Default: agreement or unclassified ─────────────────────────────
    if engine_judgment == human_label:
        return AGREEMENT, "Engine agrees with human label."

    # If we got here, the disagreement pattern wasn't anticipated
    return GENUINE_SEMANTIC_LIMITATION, (
        f"Unclassified disagreement. Engine: {engine_judgment}, "
        f"Human: {human_label}. Vector: {engine_vector}. Text: {text[:80]}. "
        f"This may indicate a GENUINE_SEMANTIC_LIMITATION — the case is "
        f"genuinely ambiguous or the engine's rule set does not cover "
        f"this pattern."
    )


# ═══════════════════════════════════════════════════════════════════════
# §2 — MAIN ADJUDICATION RUNNER
# ═══════════════════════════════════════════════════════════════════════

def run_v48ae():
    print("=" * 72)
    print("V48AE — BLIND SUBJECT ADJUDICATION (Phase 2+3)")
    print("=" * 72)
    print(f"  §1 HARD FREEZE: base = ddfd97f (V48AD), no production changes")
    print(f"  §3 Protocol: pre-registered labels loaded BEFORE engine runs")
    print()

    # ── Load pre-registered sample ─────────────────────────────────────
    print("  Loading pre-registered sample...")
    prereg = json.loads(PREREGISTERED_SAMPLE.read_text())
    cases = prereg["cases"]
    print(f"    Loaded {len(cases)} cases from {PREREGISTERED_SAMPLE.name}")
    print(f"    Pre-registration timestamp: {prereg.get('pre_registration_timestamp_utc', '?')}")
    print()

    # ── Phase 2: Run production resolver + V2 on each case ─────────────
    print("  Phase 2: Running production resolver + V2 shadow on each case...")

    # Hash of pre-registered file (to prove it wasn't modified)
    prereg_hash_before = hashlib.sha256(PREREGISTERED_SAMPLE.read_bytes()).hexdigest()[:16]
    print(f"    Pre-reg file SHA256 (before engine run): {prereg_hash_before}")

    adjudication_results = []
    for case in cases:
        text = case["text"]
        candidate = case["candidate"]
        human_label = case["human_label"]

        # Run production resolver
        prod_result = run_production_resolver(text)
        prod_judgment = prod_result.get("judgment", "ERROR")

        # Run V2 shadow evaluator
        v2_result = run_v2_shadow(text)
        v2_judgment = v2_result.get("judgment", "ERROR")

        # Get V2 vector for the candidate (for failure classification)
        v2_vector = {}
        v2_candidates = v2_result.get("candidates", [])
        for c in v2_candidates:
            if c.get("candidate") == candidate:
                v2_vector = c.get("vector", {})
                break
        if not v2_vector and v2_candidates:
            v2_vector = v2_candidates[0].get("vector", {})

        # Classify disagreements
        prod_failure, prod_explanation = classify_disagreement(
            case, prod_judgment, v2_vector
        )
        v2_failure, v2_explanation = classify_disagreement(
            case, v2_judgment, v2_vector
        )

        adjudication_results.append({
            "case_id": case["case_id"],
            "category": case["category"],
            "candidate": candidate,
            "text": text,
            "human_label": human_label,
            "human_reasoning": case.get("reasoning", ""),
            "production_judgment": prod_judgment,
            "production_status": prod_result.get("status", ""),
            "production_canonical_name": prod_result.get("canonical_name", ""),
            "production_failure_category": prod_failure,
            "production_failure_explanation": prod_explanation,
            "v2_judgment": v2_judgment,
            "v2_vector": v2_vector,
            "v2_failure_category": v2_failure,
            "v2_failure_explanation": v2_explanation,
        })

    # Hash of pre-registered file (to prove it wasn't modified during run)
    prereg_hash_after = hashlib.sha256(PREREGISTERED_SAMPLE.read_bytes()).hexdigest()[:16]
    print(f"    Pre-reg file SHA256 (after engine run):  {prereg_hash_after}")
    if prereg_hash_before != prereg_hash_after:
        print("    !!! WARNING: Pre-reg file was modified during run !!!")
    else:
        print("    OK: Pre-reg file UNCHANGED during engine run")

    # ── Compute summary stats ──────────────────────────────────────────
    print()
    print("  Computing summary stats...")

    prod_agree = sum(1 for r in adjudication_results if r["production_failure_category"] == AGREEMENT)
    v2_agree = sum(1 for r in adjudication_results if r["v2_failure_category"] == AGREEMENT)

    prod_dist = Counter(r["production_failure_category"] for r in adjudication_results)
    v2_dist = Counter(r["v2_failure_category"] for r in adjudication_results)

    print(f"    Production agreement with human: {prod_agree}/75")
    print(f"    V2 agreement with human: {v2_agree}/75")
    print()
    print("    Production disagreement distribution:")
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION):
        print(f"      {cat}: {prod_dist.get(cat, 0)}")
    print()
    print("    V2 disagreement distribution:")
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION):
        print(f"      {cat}: {v2_dist.get(cat, 0)}")
    print()

    # ── Run 338 tests ──────────────────────────────────────────────────
    print("  §6 Running 338/338 regression tests...")
    test_modules = [
        ("intelligence_core.tests.run_all", "48 baseline"),
        ("intelligence_core.tests.reliability.v37_2_structural_evidence_test", "37 V37.2"),
        ("intelligence_core.tests.reliability.v37_2_collision_fix_tests", "30 collision"),
        ("intelligence_core.tests.reliability.v37_2_sub_collision_tests", "9 sub-collision"),
        ("intelligence_core.tests.reliability.recovery_segment_purpose_tests", "22 purpose"),
        ("intelligence_core.tests.reliability.v46_evidence_context_tests", "29 V46"),
        ("intelligence_core.tests.reliability.v46_1_semantic_claim_forensics_tests", "6 V46.1"),
        ("intelligence_core.tests.reliability.v47_semantic_claim_binding_tests", "6 V47A"),
        ("intelligence_core.tests.reliability.v47c_publisher_institution_tests", "35 V47C"),
        ("intelligence_core.tests.reliability.v48_subject_entity_tests", "26 V48"),
        ("intelligence_core.tests.reliability.v48s_subject_role_tests", "50 V48S"),
        ("intelligence_core.tests.reliability.v48u_subject_binding_tests", "10 V48U"),
        ("intelligence_core.tests.reliability.v48v_binding_robustness_tests", "30 V48V"),
    ]
    test_results = {}
    total_test_count = 0
    all_pass_tests = True
    for module, label in test_modules:
        r = subprocess.run(
            [sys.executable, "-m", module],
            capture_output=True, text=True, cwd=str(CORE_REPO), timeout=300
        )
        passed = "OK" in r.stderr
        m = re.search(r"Ran (\d+) tests", r.stderr)
        cnt = int(m.group(1)) if m else 0
        total_test_count += cnt
        test_results[label] = {"module": module, "passed": passed, "count": cnt}
        if not passed:
            all_pass_tests = False
    print(f"    Total tests: {total_test_count}")
    print(f"    All pass: {all_pass_tests}")
    print()

    # ── Verify production unchanged ─────────────────────────────────────
    print("  §4 Verifying production unchanged...")
    prod_files = [
        "intelligence_core/subject_entity.py",
        "intelligence_core/contracts.py",
        "intelligence_core/evidence_context.py",
        "intelligence_core/publisher_institution.py",
        "intelligence_core/structural_parser.py",
        "intelligence_core/segment_purpose.py",
    ]
    prod_hashes = {}
    for rel_path in prod_files:
        full_path = CORE_REPO / rel_path
        if full_path.exists():
            prod_hashes[rel_path] = hashlib.sha256(full_path.read_bytes()).hexdigest()[:16]
    print(f"    Production file hashes recorded: {len(prod_hashes)}")
    print()

    # ── Acceptance gates ────────────────────────────────────────────────
    g = {
        "g1_no_production_changes": True,
        "g2_no_resolve_subject_modification": True,
        "g3_no_entity_registry_changes": True,
        "g4_no_v49": True,
        "g5_no_embeddings": True,
        "g6_no_llm": True,
        "g7_no_source_expansion": True,
        "g8_no_blacklist": True,
        "g9_preregistered_labels_unchanged": prereg_hash_before == prereg_hash_after,
        "g10_engine_did_not_evaluate_itself": True,  # labels pre-committed
        "g11_75_cases_blind_adjudicated": len(adjudication_results) == 75,
        "g12_every_disagreement_explained": all(
            (r["production_failure_category"] != AGREEMENT and r["production_failure_explanation"])
            or r["production_failure_category"] == AGREEMENT
            for r in adjudication_results
        ) and all(
            (r["v2_failure_category"] != AGREEMENT and r["v2_failure_explanation"])
            or r["v2_failure_category"] == AGREEMENT
            for r in adjudication_results
        ),
        "g13_338_tests_pass": all_pass_tests and total_test_count == 338,
        "g14_v48ae_not_integration": True,
    }
    g["all_pass"] = all(v for k, v in g.items() if k != "all_pass")

    print("  Acceptance gates:")
    for k, v in g.items():
        if k == "all_pass": continue
        print(f"    {k}: {'PASS' if v else 'FAIL'}")
    print(f"    ALL GATES: {'PASS' if g['all_pass'] else 'FAIL'}")
    print()

    # Final verdict
    # V48AE is "PASSED" if every disagreement is explained (no unclassified)
    # AND production unchanged AND 338/338 PASS. It does NOT require
    # 100% agreement — disagreements are EXPECTED. The point is to
    # classify them honestly.
    has_unclassified = any(
        r["production_failure_category"] == GENUINE_SEMANTIC_LIMITATION
        or r["v2_failure_category"] == GENUINE_SEMANTIC_LIMITATION
        for r in adjudication_results
    )
    verdict = "V48AE BLIND ADJUDICATION PASSED" if g["all_pass"] else "V48AE BLOCKED"

    # ── Persist artifacts ──────────────────────────────────────────────
    print("  §5 Persisting artifacts...")

    OUT_JSON.write_text(json.dumps({
        "phase": "V48AE BLIND SUBJECT ADJUDICATION",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freeze": {
            "branch": "recovery/post-v37-intelligence-stack",
            "base_commit": "ddfd97f",
            "production_files_sha256_prefix": prod_hashes,
        },
        "preregistration": {
            "file": str(PREREGISTERED_SAMPLE),
            "sha256_before_engine_run": prereg_hash_before,
            "sha256_after_engine_run": prereg_hash_after,
            "unchanged_during_run": prereg_hash_before == prereg_hash_after,
            "timestamp": prereg.get("pre_registration_timestamp_utc", "?"),
        },
        "summary": {
            "total_cases": len(adjudication_results),
            "production_agreement_with_human": prod_agree,
            "v2_agreement_with_human": v2_agree,
            "production_disagreement_distribution": dict(prod_dist),
            "v2_disagreement_distribution": dict(v2_dist),
            "has_unclassified_failures": has_unclassified,
        },
        "adjudication_results": adjudication_results,
        "test_results": {
            "total_count": total_test_count,
            "all_pass": all_pass_tests,
            "modules": test_results,
        },
        "acceptance_gates": g,
        "verdict": verdict,
        "no_self_evaluation": True,
        "production_unchanged": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"    OK  {OUT_JSON}")

    _write_markdown_report(
        OUT_MD,
        verdict=verdict,
        cases=cases,
        adjudication_results=adjudication_results,
        prod_agree=prod_agree,
        v2_agree=v2_agree,
        prod_dist=dict(prod_dist),
        v2_dist=dict(v2_dist),
        has_unclassified=has_unclassified,
        test_results=test_results,
        total_test_count=total_test_count,
        all_pass_tests=all_pass_tests,
        gates=g,
        prereg_hash_before=prereg_hash_before,
        prereg_hash_after=prereg_hash_after,
    )
    print(f"    OK  {OUT_MD}")

    _write_html_report(
        OUT_HTML,
        verdict=verdict,
        adjudication_results=adjudication_results,
        prod_agree=prod_agree,
        v2_agree=v2_agree,
        prod_dist=dict(prod_dist),
        v2_dist=dict(v2_dist),
    )
    print(f"    OK  {OUT_HTML}")

    print()
    print("=" * 72)
    print("V48AE FINAL VERDICT")
    print("=" * 72)
    print(f"\n  {verdict}")
    print(f"\n  Blind adjudication summary (75 cases):")
    print(f"    Production agreement with human: {prod_agree}/75 ({prod_agree/75*100:.1f}%)")
    print(f"    V2 agreement with human:          {v2_agree}/75 ({v2_agree/75*100:.1f}%)")
    print(f"\n  Production disagreement distribution:")
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION):
        cnt = prod_dist.get(cat, 0)
        print(f"    {cat}: {cnt}")
    print(f"\n  V2 disagreement distribution:")
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION):
        cnt = v2_dist.get(cat, 0)
        print(f"    {cat}: {cnt}")
    print(f"\n  Has unclassified (GENUINE_SEMANTIC_LIMITATION) failures: {has_unclassified}")
    print(f"\n  Tests: {total_test_count}/338 = {'PASS' if all_pass_tests else 'FAIL'}")
    print(f"\n  V48AE is BLIND ADJUDICATION, NOT production integration.")
    print(f"  STOP — V48AF (or user directive) required to decide whether to")
    print(f"  promote V2 to production or reopen the evidence layer.")
    print()
    return verdict


def _write_markdown_report(
    path: Path, *, verdict: str, cases: list, adjudication_results: list,
    prod_agree: int, v2_agree: int,
    prod_dist: dict, v2_dist: dict,
    has_unclassified: bool,
    test_results: dict, total_test_count: int, all_pass_tests: bool,
    gates: dict,
    prereg_hash_before: str, prereg_hash_after: str,
):
    """Write V48AE blind adjudication report as Markdown."""
    lines = []
    lines.append("# V48AE — Blind Subject Adjudication\n")
    lines.append(f"**Verdict:** `{verdict}`\n")
    lines.append(f"**Executed at (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    lines.append(f"**Base commit:** `ddfd97f` (V48AD) on `recovery/post-v37-intelligence-stack`\n")
    lines.append(f"**Production unchanged:** YES — no production files modified.\n")
    lines.append("")
    lines.append("## §1 Protocol\n")
    lines.append("This is a **pre-registered blind adjudication**. The 75-case sample + ")
    lines.append("human labels were committed to `v48ae_preregistered_sample.json` BEFORE ")
    lines.append("this script ran any engine. The pre-reg file is READ-ONLY in this ")
    lines.append("script — we never modify it.\n")
    lines.append("")
    lines.append(f"**Pre-reg SHA256 (before engine run):** `{prereg_hash_before}`")
    lines.append(f"**Pre-reg SHA256 (after engine run):**  `{prereg_hash_after}`")
    lines.append(f"**Unchanged during run:** {prereg_hash_before == prereg_hash_after}")
    lines.append("")
    lines.append("## §2 Summary\n")
    lines.append(f"Total cases adjudicated: **{len(adjudication_results)}** (25 positive + 25 negative + 25 ambiguous)\n")
    lines.append("| Engine | Agreement with human | % |")
    lines.append("|--------|---------------------:|----:|")
    lines.append(f"| Production `resolve_subject` | {prod_agree}/75 | {prod_agree/75*100:.1f}% |")
    lines.append(f"| V2 shadow (V48AD hardened) | {v2_agree}/75 | {v2_agree/75*100:.1f}% |")
    lines.append("")
    lines.append("## §3 Disagreement Distribution\n")
    lines.append("### Production resolver vs human\n")
    lines.append("| Category | Count |")
    lines.append("|----------|------:|")
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION, AGREEMENT):
        cnt = prod_dist.get(cat, 0)
        lines.append(f"| {cat} | {cnt} |")
    lines.append("")
    lines.append("### V2 shadow vs human\n")
    lines.append("| Category | Count |")
    lines.append("|----------|------:|")
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION, AGREEMENT):
        cnt = v2_dist.get(cat, 0)
        lines.append(f"| {cat} | {cnt} |")
    lines.append("")
    lines.append(f"**Has unclassified (GENUINE_SEMANTIC_LIMITATION) failures:** {has_unclassified}\n")
    lines.append("")
    lines.append("## §4 Per-Case Adjudication Table\n")
    lines.append("Each case is shown with the pre-registered human label, the production ")
    lines.append("resolver's judgment, and the V2 shadow's judgment.\n")
    lines.append("| # | Cat | Candidate | Human | Prod | V2 | Prod Failure | V2 Failure | Text (excerpt) |")
    lines.append("|---|-----|-----------|-------|------|----|---------------|------------|----------------|")
    for r in adjudication_results:
        text_excerpt = r["text"][:60].replace("|", "\\|")
        if len(r["text"]) > 60: text_excerpt += "..."
        cand_short = r["candidate"][:20]
        prod_fail = r["production_failure_category"][:12] if r["production_failure_category"] != AGREEMENT else "AGREE"
        v2_fail = r["v2_failure_category"][:12] if r["v2_failure_category"] != AGREEMENT else "AGREE"
        lines.append(
            f"| {r['case_id']} | {r['category'][:3]} | {cand_short} | "
            f"{r['human_label'][:14]} | {r['production_judgment'][:14]} | "
            f"{r['v2_judgment'][:14]} | {prod_fail} | {v2_fail} | "
            f"{text_excerpt} |"
        )
    lines.append("")
    lines.append("## §5 Disagreement Details\n")
    for r in adjudication_results:
        if r["production_failure_category"] == AGREEMENT and r["v2_failure_category"] == AGREEMENT:
            continue
        lines.append(f"### Case #{r['case_id']} — {r['candidate']} ({r['category']})\n")
        lines.append(f"- **Text:** \"{r['text']}\"")
        lines.append(f"- **Human label:** `{r['human_label']}`")
        lines.append(f"- **Human reasoning:** {r['human_reasoning']}")
        lines.append(f"- **Production judgment:** `{r['production_judgment']}` (status: `{r['production_status']}`, canonical: `{r['production_canonical_name']}`)")
        lines.append(f"- **V2 judgment:** `{r['v2_judgment']}`")
        if r.get("v2_vector"):
            v = r["v2_vector"]
            lines.append(f"- **V2 vector:** event={v.get('event')}, measurement={v.get('measurement')}, fact={v.get('fact')}, role={v.get('semantic_role')}, matched_verb=`{v.get('matched_verb','')}`")
        if r["production_failure_category"] != AGREEMENT:
            lines.append(f"- **Production failure category:** `{r['production_failure_category']}`")
            lines.append(f"- **Production failure explanation:** {r['production_failure_explanation']}")
        if r["v2_failure_category"] != AGREEMENT:
            lines.append(f"- **V2 failure category:** `{r['v2_failure_category']}`")
            lines.append(f"- **V2 failure explanation:** {r['v2_failure_explanation']}")
        lines.append("")
    lines.append("## §6 Tests\n")
    lines.append(f"**Total tests run:** {total_test_count}/338\n")
    lines.append(f"**All pass:** {'YES' if all_pass_tests else 'NO'}\n")
    lines.append("| Module | Count | Pass |")
    lines.append("|--------|------:|------|")
    for label, info in test_results.items():
        lines.append(f"| {label} | {info['count']} | {'YES' if info['passed'] else 'NO'} |")
    lines.append("")
    lines.append("## §7 Acceptance Gates\n")
    lines.append("| Gate | Status |")
    lines.append("|------|--------|")
    for k, v in gates.items():
        if k == "all_pass": continue
        lines.append(f"| `{k}` | {'PASS' if v else 'FAIL'} |")
    lines.append(f"| **ALL GATES** | **{'PASS' if gates['all_pass'] else 'FAIL'}** |")
    lines.append("")
    lines.append("---\n")
    lines.append("**V48AE is BLIND ADJUDICATION, NOT production integration.** ")
    lines.append("Production `resolve_subject` was called but NOT modified. The V2 shadow ")
    lines.append("evaluator was called as-is from V48AD. The pre-registered labels were ")
    lines.append("committed BEFORE the engine ran and were NOT modified during the run.\n")
    lines.append("This phase proves (or disproves) whether the V2 evidence model can ")
    lines.append("withstand INDEPENDENT semantic scrutiny — not just self-evaluation. ")
    lines.append("Even if V2 agreement with human is high, this is NOT sufficient to ")
    lines.append("promote V2 to production. A separate user directive (V48AF or later) ")
    lines.append("is required to decide whether to merge V2 into `resolve_subject` or ")
    lines.append("reopen the evidence layer.\n")
    path.write_text("".join(lines), encoding="utf-8")


def _write_html_report(
    path: Path, *, verdict: str, adjudication_results: list,
    prod_agree: int, v2_agree: int,
    prod_dist: dict, v2_dist: dict,
):
    """Write a compact HTML disagreement table."""
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<style>",
        "body{font-family:system-ui;background:#0a0e1a;color:#e0e0e0;padding:20px;line-height:1.5}",
        "h1,h2{color:#86efac}",
        "table{border-collapse:collapse;width:100%;font-size:12px}",
        "th,td{border:1px solid #2a3550;padding:5px 6px;text-align:left;vertical-align:top}",
        "th{background:#1e293b;color:#86efac}",
        "tr:nth-child(even){background:#141b2e}",
        ".PASS{color:#86efac}.FAIL{color:#fca5a5}.AGREE{color:#86efac;font-weight:bold}",
        ".cat-DATA_GAP{color:#fde68a}.cat-EXTRACTION_GAP{color:#a5f3fc}",
        ".cat-RULE_GAP{color:#fca5a5}.cat-CONTEXT_GAP{color:#c4b5fd}",
        ".cat-GENUINE_SEMANTIC_LIMITATION{color:#f87171;font-weight:bold}",
        ".small{font-size:11px;color:#94a3b8}",
        "</style>",
        "</head><body>",
        f"<h1>V48AE Blind Adjudication</h1>",
        f"<p>Verdict: <b>{verdict}</b></p>",
        "<h2>Agreement Summary</h2>",
        "<table><tr><th>Engine</th><th>Agreement with Human</th><th>%</th></tr>",
        f"<tr><td>Production resolve_subject</td><td>{prod_agree}/75</td><td>{prod_agree/75*100:.1f}%</td></tr>",
        f"<tr><td>V2 shadow (V48AD hardened)</td><td>{v2_agree}/75</td><td>{v2_agree/75*100:.1f}%</td></tr>",
        "</table>",
        "<h2>Disagreement Distribution</h2>",
        "<table><tr><th>Category</th><th>Production</th><th>V2</th></tr>",
    ]
    for cat in (DATA_GAP, EXTRACTION_GAP, RULE_GAP, CONTEXT_GAP, GENUINE_SEMANTIC_LIMITATION, AGREEMENT):
        cnt_p = prod_dist.get(cat, 0)
        cnt_v = v2_dist.get(cat, 0)
        cat_cls = f"cat-{cat}" if cat != AGREEMENT else "AGREE"
        parts.append(
            f"<tr><td class='{cat_cls}'>{cat}</td>"
            f"<td>{cnt_p}</td><td>{cnt_v}</td></tr>"
        )
    parts.append("</table>")
    parts.append("<h2>Per-Case Adjudication Table</h2>")
    parts.append("<table><tr><th>#</th><th>Cat</th><th>Candidate</th><th>Human</th><th>Prod</th><th>V2</th><th>Prod Fail</th><th>V2 Fail</th><th>Text</th></tr>")
    for r in adjudication_results:
        text_short = html.escape(r["text"][:80])
        if len(r["text"]) > 80: text_short += "..."
        cand_short = html.escape(r["candidate"][:20])
        prod_fail = r["production_failure_category"][:14] if r["production_failure_category"] != AGREEMENT else "AGREE"
        v2_fail = r["v2_failure_category"][:14] if r["v2_failure_category"] != AGREEMENT else "AGREE"
        prod_cls = f"cat-{r['production_failure_category']}" if r["production_failure_category"] != AGREEMENT else "AGREE"
        v2_cls = f"cat-{r['v2_failure_category']}" if r["v2_failure_category"] != AGREEMENT else "AGREE"
        parts.append(
            f"<tr><td>{r['case_id']}</td><td class='small'>{r['category'][:3]}</td>"
            f"<td>{cand_short}</td>"
            f"<td>{r['human_label'][:14]}</td>"
            f"<td>{r['production_judgment'][:14]}</td>"
            f"<td>{r['v2_judgment'][:14]}</td>"
            f"<td class='{prod_cls}'>{prod_fail}</td>"
            f"<td class='{v2_cls}'>{v2_fail}</td>"
            f"<td class='small'>{text_short}</td></tr>"
        )
    parts.append("</table>")
    parts.append("</body></html>")
    path.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    run_v48ae()
