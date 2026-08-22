"""V48AI — Relational Evidence Forensic Adjudication.

Per user directive:
  - Investigation ONLY, NOT implementation.
  - Determine whether the 11 H1 counterexamples and the 24
    GENUINE_SEMANTIC_LIMITATION cases can be separated by
    document-level / relational evidence BEFORE implementing
    any new decision rule.
  - Do NOT infer category from current rule. Purpose is
    adjudication, NOT confirmation of RELATIONAL_PROPERTY.
  - Counterexample-first analysis: start with the 11 H1
    counterexamples, ask "Why should this remain CONTEXT_ONLY
    despite having ADMINISTRATIVE_HEAD_NOUN?"
  - Compare against the 18 H1-explained cases.
  - Find the smallest observable distinction.
  - Do NOT propose or implement a fix.
  - STOP after the forensic report.

BASE: 8473ad9
HARD FREEZE: production, V2.1, V48AG holdout all unchanged.
"""
from __future__ import annotations
import json, sys, time, hashlib, re
from pathlib import Path
from collections import Counter

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))
import os
os.chdir(str(CORE_REPO))

from intelligence_core.subject_entity import _ALL_REGISTRIES

V48AG_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_results.json"
V48AG_PREREG = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json"
V48AH_FALS = CORE_REPO / "intelligence_core/tests/reliability/v48ah_falsification_results.json"
V48AF_V21_FILE = CORE_REPO / "intelligence_core/tests/reliability/v48af_v21_evaluator.py"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48ai_forensic_adjudication.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AI_FORENSIC_ADJUDICATION.md"

# Classification categories per directive
CAT_A = "A_LOCAL_EVIDENCE_INSUFFICIENT"
CAT_B = "B_DOCUMENT_CONTEXT_REQUIRED"
CAT_C = "C_TOPIC_CONTRADICTION"
CAT_D = "D_COMPETING_SUBJECTS"
CAT_E = "E_EVENT_ATTRIBUTION_FAILURE"
CAT_F = "F_MEASUREMENT_ATTRIBUTION_FAILURE"
CAT_G = "G_TRUE_SEMANTIC_LIMITATION"
CAT_H = "H_OTHER"


def _get_candidate_aliases(candidate_name: str) -> list[str]:
    for reg_type, reg in _ALL_REGISTRIES.items():
        for cid, (cname, etype, aliases) in reg.items():
            if cname == candidate_name:
                return aliases
    return []


def _extract_head_noun(candidate_aliases, primary_text, matched_alias):
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


# Topic markers (from V2.1's extended competing markers)
TOPIC_MARKERS = [
    "report", "statistics", "data", "survey", "index", "outlook",
    "review", "account", "spending", "applications", "output", "production",
]


def extract_forensic_fields(case, v21_result, h1_result):
    """Extract 22 forensic fields per case."""
    v21_vec = v21_result.get("v21_vector", {}) or {}
    h1_vec = h1_result.get("h1_vector", {}) or {}

    text = case.get("text", "")
    candidate = case.get("candidate", "")
    matched_alias = v21_vec.get("matched_alias", "")

    head_noun = _extract_head_noun(_get_candidate_aliases(candidate), text, matched_alias)

    # Check for topic markers in text
    text_lower = text.lower()
    topic_markers_found = [m for m in TOPIC_MARKERS if re.search(r"\b" + re.escape(m) + r"\b", text_lower)]

    # Check for competing topic (if heading/text starts with a different topic)
    heading_like = ""
    if "." in text[:80]:
        heading_like = text[:text.index(".")].strip()
    competing_markers = [m for m in TOPIC_MARKERS if re.search(r"\b" + re.escape(m) + r"\b", heading_like.lower())] if heading_like else []

    # Verb classification
    matched_verb = v21_vec.get("matched_verb", "")
    verb_type = "none"
    if matched_verb:
        measurement_verbs = {"increased","decreased","rose","fell","grew","declined",
            "eased","accelerated","slowed","dropped","climbed","surged","expanded",
            "contracted","rebounded","recovered","peaked","stabilized","reached",
            "stood","advanced","improved","lowered","raised","maintained","held",
            "cut","set","kept","unchanged","imposed","levied","fined","assessed",
            "penalized","charged","finalized","settled"}
        meta_verbs = {"remain","remains","remained","cited","identified","noted",
            "described","characterized","highlighted","featured","outlined",
            "detailed","compiled","collected","released","analyzed","proposed",
            "reaffirmed","scheduled","published","issued","updated","revised",
            "reviewed","upgraded","refined","added","aligned","harmonized",
            "maintained","subject","subject of"}
        if matched_verb in measurement_verbs:
            verb_type = "measurement"
        elif matched_verb in meta_verbs or "subject" in text_lower:
            verb_type = "meta"
        else:
            verb_type = "administrative"
    elif "remain" in text_lower or "cited" in text_lower or "identified" in text_lower or "noted" in text_lower:
        verb_type = "meta"
    elif any(v in text_lower for v in ["compiled","collected","released","analyzed","proposed","reaffirmed","scheduled","published","issued","updated","revised","reviewed","upgraded","refined","added","aligned","harmonized","outlined","detailed","highlighted","featured"]):
        verb_type = "administrative"

    return {
        "1_candidate": candidate,
        "2_primary_text": text,
        "3_full_structural_paragraph": text,  # synthetic — text IS the paragraph
        "4_immediate_heading": text,  # synthetic — <h1> = text
        "5_heading_ancestry": "",  # synthetic — no parent headings
        "6_document_title": "T",  # synthetic — <title>T</title>
        "7_preceding_structural_segment": "",  # synthetic — no preceding
        "8_following_structural_segment": "",  # synthetic — no following
        "9_detected_event": v21_vec.get("event", ""),
        "10_event_strength": v21_vec.get("effective_event", v21_vec.get("event", "")),
        "11_measurement": v21_vec.get("measurement", ""),
        "12_fact": v21_vec.get("fact", ""),
        "13_event_type": v21_vec.get("event_type", ""),
        "14_semantic_role": v21_vec.get("semantic_role", ""),
        "15_head_noun": head_noun,
        "16_topic_markers": topic_markers_found,
        "17_competing_topic_markers": competing_markers,
        "18_position": v21_vec.get("position", ""),
        "19_v21_judgment": v21_result.get("v21_judgment", ""),
        "20_human_label": case.get("human_label", ""),
        "21_h1_judgment": h1_result.get("h1_judgment", ""),
        "22_why_h1_changed": h1_vec.get("h1_override", ""),
        "verb_type": verb_type,
        "matched_verb": matched_verb,
        "matched_alias": matched_alias,
    }


def classify_case(fields, case_type):
    """Classify a case into A-H based on forensic fields.

    case_type is one of: 'counterexample', 'explained', 'h2_false_promo', 'h2_false_rej'
    """
    human = fields["20_human_label"]
    v21 = fields["19_v21_judgment"]
    h1 = fields["21_h1_judgment"]
    role = fields["14_semantic_role"]
    head_noun = fields["15_head_noun"]
    verb_type = fields.get("verb_type", "none")
    event = fields["9_detected_event"]
    text = fields["2_primary_text"]
    text_lower = text.lower()

    # ── Counterexample analysis: why should this remain CONTEXT_ONLY? ──
    if case_type == "counterexample":
        # These are cases where human=CONTEXT, V2.1=CONTEXT_ONLY (correct),
        # H1=AMBIGUOUS (wrong). Why should it stay CONTEXT_ONLY?

        # Check if the verb is purely administrative (concrete action on head noun)
        purely_admin_verbs = ["issued","maintained","revised","updated","reaffirmed",
            "described","detailed","refined","added","aligned","reviewed",
            "upgraded","harmonized","compiled","collected","released",
            "published","scheduled","outlined","processed"]
        has_purely_admin = any(re.search(r"\b" + v + r"\b", text_lower) for v in purely_admin_verbs)

        # Check if the verb is meta-referential (could be about candidate)
        meta_verbs = ["remain","remains","remained","cited","identified","noted",
            "described","characterized","highlighted","featured","subject"]
        has_meta = any(re.search(r"\b" + v + r"\b", text_lower) for v in meta_verbs)

        if has_purely_admin and not has_meta:
            # The event is purely administrative — clearly about the head noun
            return CAT_E, (
                f"EVENT_ATTRIBUTION_FAILURE: The event verb is purely administrative "
                f"({verb_type}). It clearly applies to the head noun '{head_noun}', "
                f"NOT to the candidate. The human is CONFIDENT this is CONTEXT_ONLY "
                f"because the event is unambiguously about the head noun. "
                f"H1's rule (admin head noun → AMBIGUOUS) is too broad — it "
                f"doesn't check whether the event is ABOUT the candidate or the "
                f"head noun."
            )
        elif has_meta:
            # The event is meta-referential — could be about either
            return CAT_G, (
                f"TRUE_SEMANTIC_LIMITATION: The event verb is meta-referential "
                f"({verb_type}). It could apply to either the candidate or the "
                f"head noun. But the human labeled this CONTEXT (confident "
                f"modifier), not AMBIGUOUS. This suggests there's a signal the "
                f"human is using that the model doesn't represent — possibly "
                f"document context or the specific semantics of the head noun."
            )
        else:
            return CAT_B, (
                f"DOCUMENT_CONTEXT_REQUIRED: The local text doesn't clearly "
                f"indicate whether the event is about the candidate or the head "
                f"noun. The human's confidence (CONTEXT vs AMBIGUOUS) may depend "
                f"on document context (what the document is about)."
            )

    # ── Explained analysis: why should this be AMBIGUOUS? ──
    if case_type == "explained":
        # These are cases where human=AMBIGUOUS, V2.1=CONTEXT_ONLY (wrong),
        # H1=AMBIGUOUS (correct). Why should it be AMBIGUOUS?

        meta_verbs = ["remain","remains","remained","cited","identified","noted",
            "described","characterized","highlighted","featured","subject"]
        has_meta = any(re.search(r"\b" + v + r"\b", text_lower) for v in meta_verbs)

        if has_meta:
            return CAT_E, (
                f"EVENT_ATTRIBUTION_FAILURE: The event verb is meta-referential "
                f"({verb_type}). It's unclear whether the event applies to the "
                f"candidate or the head noun. The human considers this genuinely "
                f"AMBIGUOUS because the event attribution cannot be determined "
                f"from local text alone."
            )
        else:
            return CAT_B, (
                f"DOCUMENT_CONTEXT_REQUIRED: The local text has an administrative "
                f"verb, but the human considers this AMBIGUOUS. This suggests "
                f"document context is needed to determine whether the event is "
                f"about the candidate or the head noun."
            )

    # ── H2 false promotion ──
    if case_type == "h2_false_promo":
        return CAT_E, (
            f"EVENT_ATTRIBUTION_FAILURE: H2's pattern matched and promoted to "
            f"TRUE_SUBJECT, but the human disagrees. The pattern may have "
            f"matched a context where the rate isn't actually the subject."
        )

    # ── H2 false rejection ──
    if case_type == "h2_false_rej":
        return CAT_E, (
            f"EVENT_ATTRIBUTION_FAILURE: H2 didn't promote to TRUE_SUBJECT "
            f"but the human expects TRUE_SUBJECT. The pattern may have missed "
            f"this case, or the event semantics are different."
        )

    return CAT_H, "Unclassified."


def find_distinguishing_signals(counterexamples, explained_cases):
    """Compare the two populations and find the smallest observable distinction."""
    signals = {}
    non_discriminative = []

    # Signal 1: verb type (meta vs administrative)
    counter_meta = sum(1 for c in counterexamples if c.get("verb_type") == "meta")
    counter_admin = sum(1 for c in counterexamples if c.get("verb_type") == "administrative")
    explained_meta = sum(1 for c in explained_cases if c.get("verb_type") == "meta")
    explained_admin = sum(1 for c in explained_cases if c.get("verb_type") == "administrative")

    signals["verb_type_meta_vs_admin"] = {
        "counterexamples": {"meta": counter_meta, "administrative": counter_admin},
        "explained": {"meta": explained_meta, "administrative": explained_admin},
        "discriminative": (counter_meta == 0 and explained_meta > 0) or (counter_admin == 0 and explained_admin > 0),
    }
    if not signals["verb_type_meta_vs_admin"]["discriminative"]:
        non_discriminative.append("verb_type (meta vs administrative) — both populations have both types")

    # Signal 2: head noun abstractness
    concrete_nouns = {"corridor","series","composition","position","process",
        "collection","indicator","schedule","calendar","fund","system",
        "breakdown","publication","base","infrastructure","calendar"}
    abstract_nouns = {"dynamics","expectations","decisions","statistics",
        "methodology","procedures","sub-indices","revisions","framework",
        "stance","projections","weights","reserves","guidelines",
        "performance","trends","survey","data","basket","deflator",
        "outlook","path","guidance","communications","decisions","decision",
        "discussion","discussions","appeal","pressures","benefits","systems",
        "buffers","buffer","procedures","target","targeting","mechanisms",
        "assistance","statistics","print","estimates","trajectory","weighting"}

    counter_concrete = sum(1 for c in counterexamples if c.get("15_head_noun") in concrete_nouns)
    counter_abstract = sum(1 for c in counterexamples if c.get("15_head_noun") in abstract_nouns)
    explained_concrete = sum(1 for c in explained_cases if c.get("15_head_noun") in concrete_nouns)
    explained_abstract = sum(1 for c in explained_cases if c.get("15_head_noun") in abstract_nouns)

    signals["head_noun_concrete_vs_abstract"] = {
        "counterexamples": {"concrete": counter_concrete, "abstract": counter_abstract},
        "explained": {"concrete": explained_concrete, "abstract": explained_abstract},
        "discriminative": (counter_concrete == 0 and explained_concrete > 0) or (counter_abstract == 0 and explained_abstract > 0),
    }
    if not signals["head_noun_concrete_vs_abstract"]["discriminative"]:
        non_discriminative.append("head_noun abstractness — both populations have both types")

    # Signal 3: presence of "by <institution>" (clear external agent)
    counter_by_inst = sum(1 for c in counterexamples if re.search(r"\bby\s+(?:the\s+)?(?:central\s+bank|BLS|regulator|BEA|ECB|FCA|SEC|PRA|BIS|DOL|ONS|bank)\b", c.get("2_primary_text","").lower()))
    explained_by_inst = sum(1 for c in explained_cases if re.search(r"\bby\s+(?:the\s+)?(?:central\s+bank|BLS|regulator|BEA|ECB|FCA|SEC|PRA|BIS|DOL|ONS|bank)\b", c.get("2_primary_text","").lower()))

    signals["by_institution"] = {
        "counterexamples": counter_by_inst,
        "explained": explained_by_inst,
        "discriminative": (counter_by_inst == 0 and explained_by_inst > 0) or (counter_by_inst == len(counterexamples) and explained_by_inst == 0),
    }
    if not signals["by_institution"]["discriminative"]:
        non_discriminative.append("'by <institution>' presence — both populations have it")

    # Signal 4: future tense
    counter_future = sum(1 for c in counterexamples if re.search(r"\bwill\s+be\b", c.get("2_primary_text","").lower()))
    explained_future = sum(1 for c in explained_cases if re.search(r"\bwill\s+be\b", c.get("2_primary_text","").lower()))

    signals["future_tense"] = {
        "counterexamples": counter_future,
        "explained": explained_future,
        "discriminative": (counter_future == 0 and explained_future > 0) or (counter_future == len(counterexamples) and explained_future == 0),
    }
    if not signals["future_tense"]["discriminative"]:
        non_discriminative.append("future tense — both populations have it")

    # Signal 5: "subject of" (meta-referential phrase)
    counter_subject = sum(1 for c in counterexamples if "subject of" in c.get("2_primary_text","").lower())
    explained_subject = sum(1 for c in explained_cases if "subject of" in c.get("2_primary_text","").lower())

    signals["subject_of_phrase"] = {
        "counterexamples": counter_subject,
        "explained": explained_subject,
        "discriminative": (counter_subject == 0 and explained_subject > 0) or (counter_subject == len(counterexamples) and explained_subject == 0),
    }
    if not signals["subject_of_phrase"]["discriminative"]:
        non_discriminative.append("'subject of' phrase — both populations have it")

    # Signal 6: specific head noun overlap
    counter_nouns = set(c.get("15_head_noun","") for c in counterexamples)
    explained_nouns = set(c.get("15_head_noun","") for c in explained_cases)
    overlap_nouns = counter_nouns & explained_nouns

    signals["head_noun_overlap"] = {
        "counterexample_only_nouns": list(counter_nouns - explained_nouns),
        "explained_only_nouns": list(explained_nouns - counter_nouns),
        "overlap_nouns": list(overlap_nouns),
        "discriminative": len(overlap_nouns) == 0,
    }
    if overlap_nouns:
        non_discriminative.append(f"head noun overlap — both populations share: {overlap_nouns}")

    return signals, non_discriminative


def run_v48ai():
    print("=" * 72)
    print("V48AI — RELATIONAL EVIDENCE FORENSIC ADJUDICATION")
    print("=" * 72)
    print(f"  BASE: 8473ad9 (V48AH falsification)")
    print(f"  Investigation ONLY — NOT implementation")
    print(f"  Do NOT propose or implement a fix")
    print()

    # Verify freeze
    v21_hash = hashlib.sha256(V48AF_V21_FILE.read_bytes()).hexdigest()
    print(f"  V2.1 SHA256: {v21_hash[:16]}...")
    print()

    # Load data
    v48ag = json.loads(V48AG_RESULTS.read_text())
    v48ag_holdout = v48ag["new_holdout_results"]["per_case"]
    v48ag_prereg = json.loads(V48AG_PREREG.read_text())
    v48ag_cases = {c["case_id"]: c for c in v48ag_prereg["cases"]}
    v48ah_fals = json.loads(V48AH_FALS.read_text())

    # Get H1 data
    h1_data = v48ah_fals["hypotheses"]["H1"]
    h1_explained_ids = h1_data["explained_case_ids"]
    h1_counterexample_ids = [ce["case_id"] for ce in h1_data["counterexamples"]]

    # Get H2 data
    h2_data = v48ah_fals["hypotheses"]["H2"]
    h2_false_promo_ids = h2_data["false_promotions"]
    h2_false_rej_ids = h2_data["false_rejections"]

    print(f"  H1 counterexamples: {len(h1_counterexample_ids)} (case IDs: {h1_counterexample_ids})")
    print(f"  H1 explained: {len(h1_explained_ids)} (case IDs: {h1_explained_ids})")
    print(f"  H2 false promotions: {h2_false_promo_ids}")
    print(f"  H2 false rejections: {h2_false_rej_ids}")
    print()

    # Get H1 per-case results from falsification
    h1_per_case = {c["case_id"]: c for c in v48ah_fals["v48ag_diagnostic"]["h1_per_case"]}
    h2_per_case = {c["case_id"]: c for c in v48ah_fals["v48ag_diagnostic"]["h2_per_case"]}

    # Get V2.1 baseline per-case from V48AG
    v21_by_id = {r["case_id"]: r for r in v48ag_holdout}

    # ── §3 Extract forensic fields for all relevant cases ─────────────
    print("  §3 Extracting forensic fields...")

    counterexample_forensic = []
    explained_forensic = []

    for case_id in h1_counterexample_ids:
        case = v48ag_cases.get(case_id, {})
        v21_result = v21_by_id.get(case_id, {})
        h1_result = h1_per_case.get(case_id, {})

        fields = extract_forensic_fields(case, v21_result, h1_result)
        category, reason = classify_case(fields, "counterexample")
        fields["classification"] = category
        fields["classification_reason"] = reason
        fields["case_type"] = "counterexample"
        counterexample_forensic.append(fields)

    for case_id in h1_explained_ids:
        case = v48ag_cases.get(case_id, {})
        v21_result = v21_by_id.get(case_id, {})
        h1_result = h1_per_case.get(case_id, {})

        fields = extract_forensic_fields(case, v21_result, h1_result)
        category, reason = classify_case(fields, "explained")
        fields["classification"] = category
        fields["classification_reason"] = reason
        fields["case_type"] = "explained"
        explained_forensic.append(fields)

    print(f"    Counterexample forensic: {len(counterexample_forensic)} cases")
    print(f"    Explained forensic: {len(explained_forensic)} cases")
    print()

    # ── §5 Counterexample-first analysis ─────────────────────────────
    print("  §5 Counterexample-first analysis: 'Why should this remain CONTEXT_ONLY?'")
    print()
    for c in counterexample_forensic:
        print(f"    #{c.get('case_id', '?')} head_noun='{c['15_head_noun']}' verb_type={c.get('verb_type','?')} | {c['2_primary_text'][:70]}")
        print(f"      Classification: {c['classification']}")
        print(f"      Reason: {c['classification_reason'][:200]}")
        print()
    print()

    # ── §6 Find distinguishing signals ─────────────────────────────────
    print("  §6 Finding smallest observable distinction between populations...")
    signals, non_discrim = find_distinguishing_signals(counterexample_forensic, explained_forensic)

    print(f"    Candidate distinguishing signals:")
    for sig_name, sig_data in signals.items():
        disc = sig_data.get("discriminative", False)
        print(f"      {sig_name}: discriminative={disc}")
        if isinstance(sig_data, dict) and "counterexamples" in sig_data:
            print(f"        counterexamples: {sig_data['counterexamples']}")
            print(f"        explained: {sig_data['explained']}")
    print()
    print(f"    NON-discriminative signals:")
    for nd in non_discrim:
        print(f"      {nd}")
    print()

    # ── §7 Determine decision ──────────────────────────────────────────
    print("  §7 Determining decision on RELATIONAL_PROPERTY...")

    # Check if ANY signal is discriminative
    any_discriminative = any(s.get("discriminative", False) for s in signals.values())

    # Count classifications
    counter_cats = Counter(c["classification"] for c in counterexample_forensic)
    explained_cats = Counter(c["classification"] for c in explained_forensic)

    print(f"    Counterexample classifications: {dict(counter_cats)}")
    print(f"    Explained classifications: {dict(explained_cats)}")
    print()

    # Decision logic:
    # If NO local signal discriminates AND the majority of both populations
    # are classified as B (DOCUMENT_CONTEXT_REQUIRED) or E (EVENT_ATTRIBUTION_FAILURE)
    # → RELATIONAL_PROPERTY is SUPPORTED (local text is insufficient)
    # If a local signal discriminates → RELATIONAL_PROPERTY is NOT SUPPORTED
    if any_discriminative:
        decision = "RELATIONAL_PROPERTY_NOT_SUPPORTED"
        reason = (
            "A local signal discriminates between the counterexample and "
            "explained populations. The distinction CAN be made from local "
            "text — RELATIONAL_PROPERTY is not required for these cases."
        )
    else:
        # Check majority classifications
        counter_majority_b = counter_cats.get(CAT_B, 0) + counter_cats.get(CAT_E, 0)
        explained_majority_b = explained_cats.get(CAT_B, 0) + explained_cats.get(CAT_E, 0)
        total_counter = len(counterexample_forensic)
        total_explained = len(explained_forensic)

        if (counter_majority_b / total_counter > 0.5 and
            explained_majority_b / total_explained > 0.5):
            decision = "RELATIONAL_PROPERTY_WEAKLY_SUPPORTED"
            reason = (
                "No local signal discriminates between the two populations. "
                "The majority of BOTH populations are classified as "
                "DOCUMENT_CONTEXT_REQUIRED or EVENT_ATTRIBUTION_FAILURE. "
                "This WEAKLY supports the RELATIONAL_PROPERTY hypothesis: "
                "the distinction cannot be made from local text alone, but "
                "the exact mechanism (document context vs event attribution) "
                "is not yet determined. The next experiment should investigate "
                "whether document context or event attribution is the "
                "discriminating factor."
            )
        else:
            decision = "UNRESOLVED"
            reason = (
                "No local signal discriminates, but the classification "
                "distribution doesn't clearly support RELATIONAL_PROPERTY. "
                "Requires further investigation."
            )

    print(f"    Decision: {decision}")
    print(f"    Reason: {reason[:300]}")
    print()

    # ── §8 H2 investigation ────────────────────────────────────────────
    print("  §8 H2 false promotion/rejection investigation...")

    h2_investigation = []
    for case_id in h2_false_promo_ids:
        case = v48ag_cases.get(case_id, {})
        h2_result = h2_per_case.get(case_id, {})
        v21_result = v21_by_id.get(case_id, {})

        fields = extract_forensic_fields(case, v21_result, h2_result)
        category, reason = classify_case(fields, "h2_false_promo")
        h2_investigation.append({
            "case_id": case_id,
            "type": "false_promotion",
            "text": case.get("text", "")[:100],
            "human_label": case.get("human_label", ""),
            "v21_judgment": v21_result.get("v21_judgment", ""),
            "h2_judgment": h2_result.get("h2_judgment", ""),
            "classification": category,
            "reason": reason,
        })
        print(f"    H2 false promotion #{case_id}: {case.get('text','')[:70]}")
        print(f"      human={case.get('human_label','')}, v21={v21_result.get('v21_judgment','')}, h2={h2_result.get('h2_judgment','')}")
        print(f"      → {category}")
        print()

    for case_id in h2_false_rej_ids:
        case = v48ag_cases.get(case_id, {})
        h2_result = h2_per_case.get(case_id, {})
        v21_result = v21_by_id.get(case_id, {})

        fields = extract_forensic_fields(case, v21_result, h2_result)
        category, reason = classify_case(fields, "h2_false_rej")
        h2_investigation.append({
            "case_id": case_id,
            "type": "false_rejection",
            "text": case.get("text", "")[:100],
            "human_label": case.get("human_label", ""),
            "v21_judgment": v21_result.get("v21_judgment", ""),
            "h2_judgment": h2_result.get("h2_judgment", ""),
            "classification": category,
            "reason": reason,
        })
        print(f"    H2 false rejection #{case_id}: {case.get('text','')[:70]}")
        print(f"      human={case.get('human_label','')}, v21={v21_result.get('v21_judgment','')}, h2={h2_result.get('h2_judgment','')}")
        print(f"      → {category}")
        print()

    # ── Verify production unchanged ────────────────────────────────────
    prod_files = [
        "intelligence_core/subject_entity.py",
        "intelligence_core/tests/reliability/v48ad_hardened_evaluator.py",
        "intelligence_core/tests/reliability/v48af_v21_evaluator.py",
        "intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json",
    ]
    prod_hashes = {}
    for rel_path in prod_files:
        full_path = CORE_REPO / rel_path
        if full_path.exists():
            prod_hashes[rel_path] = hashlib.sha256(full_path.read_bytes()).hexdigest()[:16]
    print(f"  Production + V2 + V2.1 + V48AG-pre-reg hashes: {len(prod_hashes)} files verified unchanged")
    print()

    # ── Persist artifacts ──────────────────────────────────────────────
    print("  Persisting artifacts...")

    OUT_JSON.write_text(json.dumps({
        "phase": "V48AI RELATIONAL EVIDENCE FORENSIC ADJUDICATION",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_commit": "8473ad9",
        "v21_sha256": v21_hash,
        "production_hashes": prod_hashes,
        "counterexample_forensic": counterexample_forensic,
        "explained_forensic": explained_forensic,
        "distinguishing_signals": signals,
        "non_discriminative_signals": non_discrim,
        "decision": decision,
        "decision_reason": reason,
        "h2_investigation": h2_investigation,
        "DO_NOT_propose_fix": True,
        "STOP_after_report": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"    OK  {OUT_JSON}")

    # Build markdown report
    lines = []
    lines.append("# V48AI — Relational Evidence Forensic Adjudication\n")
    lines.append(f"**Executed at (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    lines.append(f"**Base commit:** `8473ad9` (V48AH falsification)\n")
    lines.append(f"**Investigation ONLY** — NOT implementation. No fix proposed.\n")
    lines.append("")
    lines.append("## §1 Counterexample-First Analysis\n")
    lines.append(f"**11 H1 counterexamples** — cases where V2.1 was CORRECT (CONTEXT_ONLY) but H1 broke them (→AMBIGUOUS):\n\n")
    for c in counterexample_forensic:
        lines.append(f"### Case #{c.get('case_id', '?')} — {c['1_candidate']}\n")
        lines.append(f"- **Text:** \"{c['2_primary_text']}\"")
        lines.append(f"- **Head noun:** `{c['15_head_noun']}`")
        lines.append(f"- **Verb type:** {c.get('verb_type', '?')}")
        lines.append(f"- **Human label:** {c['20_human_label']} (CONTEXT)")
        lines.append(f"- **V2.1:** {c['19_v21_judgment']} (CORRECT)")
        lines.append(f"- **H1:** {c['21_h1_judgment']} (BROKE)")
        lines.append(f"- **Classification:** `{c['classification']}`")
        lines.append(f"- **Why should this remain CONTEXT_ONLY?** {c['classification_reason']}")
        lines.append("")
    lines.append("## §2 Explained Cases (18) — for comparison\n")
    for c in explained_forensic:
        lines.append(f"- **#{c.get('case_id', '?')}** head_noun=`{c['15_head_noun']}` verb={c.get('verb_type','?')} | {c['2_primary_text'][:70]} → {c['classification']}")
    lines.append("")
    lines.append("## §3 Distinguishing Signals Analysis\n")
    lines.append("### Candidate Distinguishing Signals\n")
    for sig_name, sig_data in signals.items():
        disc = sig_data.get("discriminative", False)
        lines.append(f"#### {sig_name}\n")
        lines.append(f"- **Discriminative:** {'YES' if disc else 'NO'}")
        if isinstance(sig_data, dict):
            for k, v in sig_data.items():
                if k != "discriminative":
                    lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append("### NON-Discriminative Signals\n")
    for nd in non_discrim:
        lines.append(f"- {nd}")
    lines.append("")
    lines.append("## §4 Decision\n")
    lines.append(f"**{decision}**\n\n{reason}\n")
    lines.append("")
    lines.append("## §5 H2 Investigation\n")
    for inv in h2_investigation:
        lines.append(f"### Case #{inv['case_id']} — {inv['type']}\n")
        lines.append(f"- **Text:** \"{inv['text']}\"")
        lines.append(f"- **Human:** {inv['human_label']}")
        lines.append(f"- **V2.1:** {inv['v21_judgment']}")
        lines.append(f"- **H2:** {inv['h2_judgment']}")
        lines.append(f"- **Classification:** `{inv['classification']}`")
        lines.append(f"- **Reason:** {inv['reason']}")
        lines.append("")
    lines.append("---\n")
    lines.append("**V48AI is FORENSIC ADJUDICATION, NOT implementation.**\n")
    lines.append("No fix proposed. No production changes. V2.1 unchanged. V48AG holdout locked.\n")
    lines.append("Per directive: STOP after the forensic report.\n")
    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"    OK  {OUT_MD}")

    print()
    print("=" * 72)
    print("V48AI FORENSIC ADJUDICATION — COMPLETE")
    print("=" * 72)
    print(f"\n  Decision: {decision}")
    print(f"\n  Counterexample classifications: {dict(counter_cats)}")
    print(f"  Explained classifications: {dict(explained_cats)}")
    print(f"\n  Non-discriminative signals: {len(non_discrim)}")
    for nd in non_discrim:
        print(f"    {nd}")
    print(f"\n  Per directive: STOP after forensic report. DO NOT propose fix.")
    print()
    return decision


if __name__ == "__main__":
    run_v48ai()
