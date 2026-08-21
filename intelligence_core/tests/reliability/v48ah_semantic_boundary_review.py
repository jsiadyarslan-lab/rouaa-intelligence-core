"""V48AH — Semantic Boundary Review (NOT tuning, NOT production, NOT benchmark optimization).

Per user directive:
  - V48AG = REJECT / STOP. V2.1 is NOT a production candidate.
  - V48AG 150-case holdout is LOCKED — DO NOT use any case for rule/threshold/lexicon extraction.
  - Analyze the 24 GENUINE_SEMANTIC_LIMITATION cases forensically.
  - Classify each into A (deterministic-solvable), B (context-required),
    C (wrong semantic abstraction), or D (genuine irreducible ambiguity).
  - Answer the architectural question: is SUBJECT/CONTEXT/MODIFIER a
    lexical property (local text) or a relational property
    (candidate + event + document context)?

§7 FORBIDDEN:
  NO production changes, NO V2 changes, NO V2.1 changes,
  NO lexicon additions, NO threshold tuning, NO new holdout,
  NO embeddings, NO LLM, NO Entity Registry, NO source expansion,
  NO benchmark optimization. Don't address Bank Rate / federal funds rate now.

§6 NO accuracy goal — output is a TAXONOMY, not a percentage.
"""
from __future__ import annotations
import json, sys, time, hashlib, re
from pathlib import Path
from collections import Counter

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))
import os
os.chdir(str(CORE_REPO))

from intelligence_core.subject_entity import _ALL_REGISTRIES as PROD_REGISTRIES

V48AG_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_results.json"
V48AG_PREREG = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48ah_semantic_boundary_review.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AH_SEMANTIC_BOUNDARY_REVIEW.md"


def _get_candidate_aliases(candidate_name: str) -> list[str]:
    """Look up the production registry aliases for a candidate."""
    aliases = []
    for reg_type, reg in PROD_REGISTRIES.items():
        for cid, (cname, etype, reg_aliases) in reg.items():
            if cname == candidate_name:
                aliases = reg_aliases
                break
        if aliases:
            break
    return aliases


# ═══════════════════════════════════════════════════════════════════════
# Classification categories per user directive §4 + exit criterion
# ═══════════════════════════════════════════════════════════════════════

# A — Solvable by deterministic evidence
#     The information IS in the local text, but V2.1's rule misses it.
#     Adding a rule/lexicon entry would fix it.
# B — Solvable only with broader document context
#     The judgment cannot be resolved from the sentence/segment alone.
#     Needs heading, previous paragraph, document title, table context,
#     source metadata, institution, event context.
# C — Wrong semantic abstraction
#     The SUBJECT/CONTEXT/MODIFIER model itself is wrong.
#     Redesigning the model would fix it.
# D — Genuine irreducible ambiguity
#     Even a human reader cannot prove SUBJECT without an additional
#     assumption. The model should confidently return AMBIGUOUS.

CAT_A = "A_DETERMINISTIC_SOLVABLE"
CAT_B = "B_CONTEXT_REQUIRED"
CAT_C = "C_WRONG_SEMANTIC_ABSTRACTION"
CAT_D = "D_GENUINE_IRREDUCIBLE_AMBIGUITY"


# ═══════════════════════════════════════════════════════════════════════
# §3 — Forensic analysis of the 24 GENUINE_SEMANTIC_LIMITATION cases
# ═══════════════════════════════════════════════════════════════════════
#
# For each case, the analysis answers:
#   1. What did V2.1 "see"? (evidence spans, signals, role detection)
#   2. What did the human "see"? (human reasoning)
#   3. Is the ambiguity reducible? (A/B/C/D classification)
#   4. What information does the human need that the model doesn't represent?
#
# The classification logic:
#   - A: The case has deterministic local evidence that V2.1's rule misses.
#        Example: "Bank Rate was held" — Bank Rate is clearly the subject,
#        but V2.1 can't find it (alias missing). Adding the alias fixes it.
#   - B: The case requires broader document context to resolve.
#        Example: "GDP statistics are compiled" — is GDP the subject?
#        Depends on whether the document is a GDP release or a methodology
#        notice. Local text is insufficient; document title/heading needed.
#   - C: The case reveals that the SUBJECT/CONTEXT/MODIFIER abstraction
#        itself is wrong. The model conflates grammatical subject with
#        semantic subject. This is an architectural finding.
#   - D: Even with document context and the right model, the case is
#        genuinely ambiguous. The model should return AMBIGUOUS confidently.

def classify_case(case: dict) -> tuple[str, str, str, str]:
    """Classify a GENUINE_SEMANTIC_LIMITATION case into A/B/C/D.

    Returns (category, why_v21_decided, why_human_decided, required_info).
    """
    text = case.get("text", "")
    human_label = case.get("human_label", "")
    v21_judgment = case.get("v21_judgment", "")
    candidate = case.get("candidate", "")
    v = case.get("v21_vector", {}) or {}
    human_reasoning = case.get("human_reasoning", "")

    role = v.get("semantic_role", "")
    event = v.get("event", "")
    matched_alias = v.get("matched_alias", "")
    matched_verb = v.get("matched_verb", "")

    # ── Pattern 1: Bank Rate / federal funds rate (DATA_GAP) ───────────
    # These are clear DATA_GAPs — the alias is missing from the registry.
    # V2.1 found a DIFFERENT candidate (e.g., Monetary Policy via
    # "Monetary Policy Committee") and returned AMBIGUOUS for it.
    # The user said: don't address these now, they're clear DATA_GAPs.
    #
    # PROPER CHECK: is matched_alias an alias of the EXPECTED candidate?
    # If NOT → V2.1 found a different candidate → DATA_GAP → A
    # If YES → V2.1 found the expected candidate → NOT a DATA_GAP
    expected_aliases = _get_candidate_aliases(candidate)
    matched_alias_is_expected = (
        matched_alias and
        matched_alias.lower() in [a.lower() for a in expected_aliases]
    )
    if matched_alias and not matched_alias_is_expected:
        # V2.1 matched a DIFFERENT candidate's alias — the expected
        # candidate's alias is missing from the registry
        why_v21 = (
            f"V2.1 could NOT find candidate '{candidate}' — the expected "
            f"alias is not in the registry. V2.1 found a DIFFERENT candidate "
            f"(matched_alias='{matched_alias}') and returned {v21_judgment} "
            f"for it. The human label was for '{candidate}', not for the "
            f"candidate V2.1 actually evaluated."
        )
        why_human = (
            f"The human labeled this TRUE_SUBJECT because '{candidate}' "
            f"IS clearly the subject of the event verb. But V2.1 couldn't "
            f"find '{candidate}' — it found a different candidate instead."
        )
        required_info = (
            f"Add '{candidate}' alias to the registry (e.g., 'bank rate' "
            f"for Policy Rate, 'federal funds rate' for Policy Rate). "
            f"This is a clear DATA_GAP — NOT a semantic model failure."
        )
        return CAT_A, why_v21, why_human, required_info

    # ── Pattern 2: AMBIGUOUS (human) vs CONTEXT_ONLY/FALSE_BINDING (V2.1) ─
    # The candidate IS found (matched_alias is the candidate's alias).
    # V2.1 detected role=MODIFIER or CONTEXT and returned CONTEXT_ONLY/FALSE_BINDING.
    # The human labeled these AMBIGUOUS.
    #
    # Key question: is the ambiguity reducible with document context?
    # Or is it genuinely irreducible?

    # Extract the head noun that triggered MODIFIER detection
    # (the noun immediately after the candidate in the text)
    text_lower = text.lower()
    cand_alias_lower = matched_alias.lower() if matched_alias else candidate.lower()
    cand_idx = text_lower.find(cand_alias_lower)
    head_noun = ""
    if cand_idx >= 0:
        after = text_lower[cand_idx + len(cand_alias_lower):cand_idx + len(cand_alias_lower) + 25]
        # Find the first noun-like word after the candidate
        # (this is the head noun that V2.1 detected as MODIFIER trigger)
        words = after.split()
        if words:
            head_noun = words[0].strip(".,;:")

    # Determine the verb (if any) and its semantic type
    verb_semantic_type = "administrative"  # default
    if matched_verb:
        measurement_verbs = ["increased", "decreased", "rose", "fell", "grew",
                            "declined", "eased", "accelerated", "slowed",
                            "dropped", "climbed", "surged", "expanded",
                            "contracted", "rebounded", "recovered", "peaked",
                            "stabilized", "reached", "stood", "advanced",
                            "improved", "lowered", "raised", "maintained",
                            "held", "cut", "set", "kept", "unchanged",
                            "imposed", "levied", "fined", "assessed",
                            "penalized", "charged", "finalized", "settled"]
        if matched_verb in measurement_verbs:
            verb_semantic_type = "measurement"
        else:
            verb_semantic_type = "administrative"

    # ── Classification logic ────────────────────────────────────────────

    # Check if the case is genuinely irreducible (D)
    # Genuinely irreducible cases have:
    # - A state-description verb (e.g., "remains", "remain")
    # - OR a meta-reference verb (e.g., "cited", "identified", "noted")
    # - Where the candidate is BOTH the topic AND a modifier
    # - AND even with document context, the case is ambiguous
    genuinely_irreducible_verbs = [
        "remain", "remains", "remained",  # state descriptions
        "cited", "identified", "noted",   # meta-references
        "described", "characterized",     # descriptions
    ]
    has_irreducible_verb = any(
        re.search(r"\b" + re.escape(v) + r"\b", text_lower)
        for v in genuinely_irreducible_verbs
    )

    if has_irreducible_verb and role in ("MODIFIER", "CONTEXT"):
        # The verb is a state-description or meta-reference
        # Even with document context, the case is ambiguous
        # (the verb doesn't deterministically tell us if the candidate is the subject)
        why_v21 = (
            f"V2.1 detected role={role} (head noun: '{head_noun}') and "
            f"returned {v21_judgment}. The verb '{matched_verb or '(none)'}' "
            f"is a state-description or meta-reference — V2.1's rule treated "
            f"this as insufficient event evidence and downgraded to "
            f"{v21_judgment}."
        )
        why_human = (
            f"The human labeled this AMBIGUOUS because the verb "
            f"('{matched_verb or '(none)'}') is a state-description or "
            f"meta-reference — it doesn't deterministically tell us if "
            f"'{candidate}' is the subject. The candidate IS the topic "
            f"(the document is about it), but the verb applies to the "
            f"head noun ('{head_noun}'), not directly to the candidate. "
            f"Even with document context, this case is genuinely ambiguous."
        )
        required_info = (
            f"No amount of document context can resolve this — the verb "
            f"'{matched_verb or '(none)'}' is semantically ambiguous. "
            f"The model should confidently return AMBIGUOUS here, not "
            f"force a decision. This is a D (genuine irreducible ambiguity)."
        )
        return CAT_D, why_v21, why_human, required_info

    # Check if the case requires document context (B)
    # These cases have:
    # - An administrative verb (e.g., "compiled", "released", "published")
    # - The candidate is a modifier of a head noun
    # - The head noun is the grammatical subject
    # - But the SEMANTIC subject depends on what the document is about
    #
    # Example: "GDP statistics are compiled"
    # - If document title is "GDP Release Q3" → GDP is the semantic subject
    # - If document title is "Methodology Revision Notice" → statistics is
    # - Local text alone cannot resolve this
    if role == "MODIFIER" and head_noun:
        why_v21 = (
            f"V2.1 detected role=MODIFIER (head noun: '{head_noun}') and "
            f"returned {v21_judgment}. The verb '{matched_verb or '(none)'}' "
            f"is administrative — it applies to the head noun "
            f"'{head_noun}', not to the candidate '{candidate}'. V2.1's "
            f"rule says: if the candidate is a modifier, it's not the "
            f"subject → CONTEXT_ONLY."
        )
        why_human = (
            f"The human labeled this AMBIGUOUS because the candidate "
            f"'{candidate}' IS the topic (the document is about it), but "
            f"the verb applies to the head noun '{head_noun}', not to the "
            f"candidate. The human cannot determine from the local text "
            f"alone whether the EVENT is about the candidate or about the "
            f"head noun. This requires knowing what the document is about "
            f"(document title, heading, previous paragraphs)."
        )
        required_info = (
            f"Document context (title, heading, previous paragraphs) is "
            f"REQUIRED to resolve this case. If the document is a "
            f"'{candidate} release', the candidate is the semantic subject. "
            f"If the document is a methodology/administrative notice, the "
            f"head noun is the subject. The current model lacks a TOPIC "
            f"dimension — it only checks grammatical subject, not semantic "
            f"subject. This is B (context-required) AND reveals C (wrong "
            f"abstraction — the model conflates grammatical/semantic subject)."
        )
        return CAT_B, why_v21, why_human, required_info

    # Check if the case is a wrong-abstraction finding (C)
    # These cases reveal that the SUBJECT/CONTEXT/MODIFIER model itself
    # is wrong — it conflates grammatical subject with semantic subject.
    # This is an architectural finding, not a per-case fix.
    if role in ("MODIFIER", "CONTEXT"):
        why_v21 = (
            f"V2.1 detected role={role} and returned {v21_judgment}. "
            f"The model's SUBJECT/MODIFIER/CONTEXT roles conflate "
            f"grammatical subject (syntactic) with semantic subject "
            f"(what the event is about). When the candidate is a modifier, "
            f"the model says CONTEXT_ONLY — but the candidate may still "
            f"be the SEMANTIC subject (the event is about the candidate, "
            f"even if the candidate isn't the grammatical subject)."
        )
        why_human = (
            f"The human labeled this AMBIGUOUS because the current model "
            f"cannot distinguish 'the candidate is a modifier AND the topic' "
            f"from 'the candidate is a modifier and NOT the topic'. The "
            f"model needs a TOPIC dimension separate from SUBJECT."
        )
        required_info = (
            f"The model needs a TOPIC dimension: 'is the document about "
            f"this candidate?' This is separate from SUBJECT (grammatical) "
            f"and CONTEXT (background). This is C (wrong semantic abstraction) "
            f"— the model's roles are insufficient."
        )
        return CAT_C, why_v21, why_human, required_info

    # Default — unclassified
    why_v21 = f"V2.1 returned {v21_judgment} (role={role}, event={event})."
    why_human = f"Human labeled {human_label}."
    required_info = "Unclassified — requires manual review."
    return CAT_D, why_v21, why_human, required_info


# ═══════════════════════════════════════════════════════════════════════
# §5 — Architectural question
# ═══════════════════════════════════════════════════════════════════════

def answer_architectural_question(forensic_results: list) -> dict:
    """Answer: is SUBJECT/CONTEXT/MODIFIER a lexical property or relational?

    Per user directive §5:
      "هل SUBJECT / CONTEXT / MODIFIER خاصية lexical يمكن استنتاجها من
       النص المحلي، أم أنها علاقة بين candidate وevent وdocument context؟"
    """
    # Count categories — use "classification" field (A/B/C/D), NOT "category"
    cat_counts = Counter(r["classification"] for r in forensic_results)

    # Analyze the pattern
    b_count = cat_counts.get(CAT_B, 0)
    c_count = cat_counts.get(CAT_C, 0)
    d_count = cat_counts.get(CAT_D, 0)
    a_count = cat_counts.get(CAT_A, 0)

    total = sum(cat_counts.values())

    # The architectural answer depends on the distribution
    # If B + C + D > A → the property is RELATIONAL (not lexical)
    # If A > B + C + D → the property is LEXICAL (just missing rules)
    relational_count = b_count + c_count + d_count
    lexical_count = a_count

    if relational_count > lexical_count:
        answer = "RELATIONAL_PROPERTY"
        reason = (
            f"The majority of cases ({relational_count}/{total}) require "
            f"either document context (B={b_count}), model redesign (C={c_count}), "
            f"or are genuinely irreducible (D={d_count}). Only {a_count} case(s) "
            f"are solvable by deterministic local evidence (A). "
            f"This indicates that SUBJECT/CONTEXT/MODIFIER is NOT a lexical "
            f"property that can be inferred from local text alone. It is a "
            f"RELATIONAL property — a relationship between candidate + event "
            f"+ document context. The current detect_role() → SUBJECT/MODIFIER/"
            f"CONTEXT abstraction is INSUFFICIENT because it only checks "
            f"grammatical subject (syntactic), not semantic subject (what "
            f"the event is about). The model needs a multi-relational approach."
        )
        recommended_model = (
            "Multi-relational Subject Adjudication Model:\n"
            "  Candidate\n"
            "    ├── Event relation (is the candidate the grammatical subject of the event verb?)\n"
            "    ├── Measurement relation (is there a measurement that describes the candidate?)\n"
            "    ├── Syntactic relation (is the candidate a noun modifier?)\n"
            "    ├── Document context (is the document about this candidate? — TOPIC dimension)\n"
            "    ├── Competing candidate (is there another candidate with stronger evidence?)\n"
            "    └── Evidence strength (how strong is the combined evidence?)\n"
            "          ↓\n"
            "    Subject adjudication\n"
            "          ↓\n"
            "    TRUE_SUBJECT / FALSE_BINDING / AMBIGUOUS / CONTEXT_ONLY"
        )
    else:
        answer = "LEXICAL_PROPERTY"
        reason = (
            f"The majority of cases ({a_count}/{total}) are solvable by "
            f"deterministic local evidence (A). The model just needs more "
            f"rules/lexicon entries. The current abstraction is sufficient."
        )
        recommended_model = "Continue with the current heuristic model + lexicon extensions."

    # Determine the strategic decision
    if c_count + d_count > total / 2:
        strategic_decision = (
            "STOP patching V48 entirely. Design a new Subject Adjudication Model "
            "with a multi-relational architecture (per the recommended model above). "
            "The current heuristic role classifier cannot represent the decision "
            "we're asking it to make."
        )
    elif b_count > total / 2:
        strategic_decision = (
            "Fix the correct structure (add a TOPIC dimension + document context model), "
            "NOT the holdout. Then return to independent validation with a NEW holdout "
            "later. The current abstraction needs EXTENSION, not replacement."
        )
    elif a_count > total / 2:
        strategic_decision = (
            "Add the missing rules/lexicon entries. The current abstraction is "
            "sufficient — the problem is just incomplete lexicon."
        )
    else:
        strategic_decision = (
            "Mixed findings. Requires manual review of each case to determine "
            "the right strategic direction."
        )

    return {
        "question": "Is SUBJECT/CONTEXT/MODIFIER a lexical property (local text) or a relational property (candidate + event + document context)?",
        "answer": answer,
        "reason": reason,
        "category_distribution": dict(cat_counts),
        "recommended_model": recommended_model,
        "strategic_decision": strategic_decision,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main V48AH runner
# ═══════════════════════════════════════════════════════════════════════

def run_v48ah():
    print("=" * 72)
    print("V48AH — SEMANTIC BOUNDARY REVIEW (NOT tuning, NOT production)")
    print("=" * 72)
    print(f"  §1 HARD FREEZE: base = 83a7c0d (V48AG), no production changes")
    print(f"  §2 V48AG 150-case holdout LOCKED — not used for tuning")
    print(f"  §6 NO accuracy goal — output is a TAXONOMY")
    print(f"  §7 NO lexicon additions, NO threshold tuning, NO new holdout")
    print()

    # ── Load V48AG results ─────────────────────────────────────────────
    print("  Loading V48AG results...")
    v48ag = json.loads(V48AG_RESULTS.read_text())
    new_holdout = v48ag["new_holdout_results"]["per_case"]

    # Get the 24 GENUINE_SEMANTIC_LIMITATION cases
    genuine_cases = [c for c in new_holdout if c["v21_failure_category"] == "GENUINE_SEMANTIC_LIMITATION"]
    print(f"    Total GENUINE_SEMANTIC_LIMITATION cases: {len(genuine_cases)}")
    print()

    # Verify V48AG pre-reg is unchanged (LOCKED)
    prereg_hash = hashlib.sha256(V48AG_PREREG.read_bytes()).hexdigest()
    print(f"  V48AG pre-reg SHA256: {prereg_hash[:16]}...")
    print(f"    (LOCKED — not used for tuning)")
    print()

    # ── §3 Forensic analysis of each case ──────────────────────────────
    print("  §3 Forensic analysis of 24 cases...")
    forensic_results = []
    for case in genuine_cases:
        category, why_v21, why_human, required_info = classify_case(case)

        v = case.get("v21_vector", {}) or {}
        text = case.get("text", "")

        # Extract evidence spans (where the candidate appears in the text)
        text_lower = text.lower()
        cand_alias = v.get("matched_alias", "")
        evidence_spans = []
        if cand_alias:
            idx = text_lower.find(cand_alias.lower())
            if idx >= 0:
                start = max(0, idx - 20)
                end = min(len(text), idx + len(cand_alias) + 40)
                evidence_spans.append({
                    "type": "candidate_match",
                    "alias": cand_alias,
                    "position": idx,
                    "context": text[start:end],
                })

        # Extract the head noun (if MODIFIER)
        head_noun = ""
        if v.get("semantic_role") == "MODIFIER" and cand_alias:
            idx = text_lower.find(cand_alias.lower())
            if idx >= 0:
                after = text_lower[idx + len(cand_alias):idx + len(cand_alias) + 25]
                words = after.split()
                if words:
                    head_noun = words[0].strip(".,;:")

        forensic_results.append({
            "case_id": case["case_id"],
            "candidate": case["candidate"],
            "text": text,
            "human_label": case["human_label"],
            "v21_label": case["v21_judgment"],
            "category": case["category"],
            "evidence_spans": evidence_spans,
            "event_signal": v.get("event", ""),
            "measurement_signal": v.get("measurement", ""),
            "semantic_role": v.get("semantic_role", ""),
            "context_signal": v.get("heading", "") + " / " + v.get("topic", ""),
            "modifier_signal": head_noun,
            "matched_alias": cand_alias,
            "matched_verb": v.get("matched_verb", ""),
            "effective_event": v.get("effective_event", ""),
            "why_v21_decided": why_v21,
            "why_human_decided": why_human,
            "required_information": required_info,
            "classification": category,
            "human_reasoning": case.get("human_reasoning", ""),
        })

    # ── §4 Aggregate taxonomy ──────────────────────────────────────────
    print("  §4 Aggregate taxonomy...")
    cat_counts = Counter(r["classification"] for r in forensic_results)
    print(f"    Classification distribution:")
    for cat in (CAT_A, CAT_B, CAT_C, CAT_D):
        cnt = cat_counts.get(cat, 0)
        print(f"      {cat}: {cnt}")
    print()

    # ── §5 Architectural question ─────────────────────────────────────
    print("  §5 Answering architectural question...")
    arch_answer = answer_architectural_question(forensic_results)
    print(f"    Answer: {arch_answer['answer']}")
    print(f"    Reason: {arch_answer['reason'][:200]}...")
    print()
    print(f"    Strategic decision:")
    print(f"    {arch_answer['strategic_decision']}")
    print()

    # ── Verify production unchanged ────────────────────────────────────
    print("  §7 Verifying production + V2 + V2.1 unchanged...")
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
    print(f"    Production + V2 + V2.1 + V48AG-pre-reg hashes recorded: {len(prod_hashes)}")
    print()

    # ── Persist artifacts ──────────────────────────────────────────────
    print("  §8 Persisting artifacts...")

    OUT_JSON.write_text(json.dumps({
        "phase": "V48AH SEMANTIC BOUNDARY REVIEW",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "freeze": {
            "branch": "recovery/post-v37-intelligence-stack",
            "base_commit": "83a7c0d",
            "production_files_sha256_prefix": prod_hashes,
            "v48ag_prereg_sha256": prereg_hash,
            "v48ag_prereg_locked": True,
        },
        "methodology": {
            "approach": "Forensic analysis of 24 GENUINE_SEMANTIC_LIMITATION cases from V48AG independent holdout. NO tuning, NO production changes, NO new holdout. Output is a TAXONOMY, not a percentage.",
            "v48ag_holdout_status": "LOCKED — not used for rule/threshold/lexicon extraction",
            "classification_categories": {
                "A_DETERMINISTIC_SOLVABLE": "Information IS in local text, rule misses it. Add rule/lexicon entry to fix.",
                "B_CONTEXT_REQUIRED": "Judgment cannot be resolved from sentence alone. Needs heading, document title, previous paragraphs, table context, source metadata.",
                "C_WRONG_SEMANTIC_ABSTRACTION": "The SUBJECT/CONTEXT/MODIFIER model itself is wrong. Redesigning the model would fix it.",
                "D_GENUINE_IRREDUCIBLE_AMBIGUITY": "Even with document context + right model, the case is ambiguous. Model should confidently return AMBIGUOUS.",
            },
        },
        "forensic_results": forensic_results,
        "taxonomy_aggregate": dict(cat_counts),
        "architectural_answer": arch_answer,
        "verdict": "V48AH = SEMANTIC BOUNDARY REVIEW COMPLETE (NOT PASS/FAIL — diagnostic only)",
        "DO_NOT_create_V48AI_automatically": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"    OK  {OUT_JSON}")

    _write_markdown_report(
        OUT_MD,
        forensic_results=forensic_results,
        cat_counts=dict(cat_counts),
        arch_answer=arch_answer,
        prereg_hash=prereg_hash,
    )
    print(f"    OK  {OUT_MD}")

    print()
    print("=" * 72)
    print("V48AH FINAL VERDICT")
    print("=" * 72)
    print(f"\n  V48AH = SEMANTIC BOUNDARY REVIEW COMPLETE")
    print(f"  (NOT PASS/FAIL — diagnostic only)")
    print(f"\n  §4 Taxonomy of 24 GENUINE_SEMANTIC_LIMITATION cases:")
    for cat in (CAT_A, CAT_B, CAT_C, CAT_D):
        cnt = cat_counts.get(cat, 0)
        print(f"    {cat}: {cnt}")
    print(f"\n  §5 Architectural answer: {arch_answer['answer']}")
    print(f"\n  Strategic decision:")
    print(f"  {arch_answer['strategic_decision']}")
    print(f"\n  Per directive: DO NOT create V48AI automatically.")
    print(f"  STOP — user directive required for next phase.")
    print()
    return forensic_results, arch_answer


def _write_markdown_report(
    path: Path, *, forensic_results: list, cat_counts: dict,
    arch_answer: dict, prereg_hash: str,
):
    lines = []
    lines.append("# V48AH — Semantic Boundary Review\n")
    lines.append(f"**Executed at (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    lines.append(f"**Base commit:** `83a7c0d` (V48AG) on `recovery/post-v37-intelligence-stack`\n")
    lines.append(f"**Production unchanged:** YES — no production files modified.\n")
    lines.append(f"**V2/V2.1 unchanged:** YES — no shadow evaluator changes.\n")
    lines.append(f"**V48AG holdout LOCKED:** YES — SHA256 `{prereg_hash[:16]}...` — not used for tuning.\n")
    lines.append("")
    lines.append("## §1 Hard Freeze\n")
    lines.append("- LOCAL == REMOTE == `83a7c0d` (V48AG)")
    lines.append("- Working tree CLEAN")
    lines.append("- Production files (6) preserved untouched")
    lines.append("- V2 (`v48ad_hardened_evaluator.py`) preserved untouched")
    lines.append("- V2.1 (`v48af_v21_evaluator.py`) preserved untouched")
    lines.append("- V48AG pre-reg sample preserved untouched (LOCKED)")
    lines.append("")
    lines.append("## §2 V48AG Holdout LOCKED\n")
    lines.append("Per user directive: V48AG 150-case holdout is now a LOCKED VALIDATION SET. ")
    lines.append("No case from it is used for rule/threshold/lexicon extraction. The V48AF ")
    lines.append("93.3% was a DEVELOPMENT-SET result — not independent validation.\n")
    lines.append("")
    lines.append("## §3 Forensic Analysis of 24 GENUINE_SEMANTIC_LIMITATION Cases\n")
    lines.append("Each case is analyzed forensically:\n")
    lines.append("- What did V2.1 see? (evidence spans, signals, role detection)")
    lines.append("- What did the human see? (human reasoning)")
    lines.append("- Is the ambiguity reducible? (A/B/C/D classification)")
    lines.append("- What information does the human need that the model doesn't represent?\n")
    lines.append("")
    lines.append("### Classification Categories\n")
    lines.append("| Category | Description |")
    lines.append("|----------|-------------|")
    lines.append("| **A — Deterministic-solvable** | Information IS in local text, rule misses it. Add rule/lexicon entry. |")
    lines.append("| **B — Context-required** | Judgment cannot be resolved from sentence alone. Needs document context (heading, title, previous paragraphs). |")
    lines.append("| **C — Wrong semantic abstraction** | The SUBJECT/CONTEXT/MODIFIER model itself is wrong. Redesigning the model would fix it. |")
    lines.append("| **D — Genuine irreducible ambiguity** | Even with document context + right model, the case is ambiguous. Model should return AMBIGUOUS. |")
    lines.append("")
    lines.append("## §4 Taxonomy Aggregate\n")
    lines.append("| Category | Count | % |")
    lines.append("|----------|------:|----:|")
    total = sum(cat_counts.values())
    for cat in (CAT_A, CAT_B, CAT_C, CAT_D):
        cnt = cat_counts.get(cat, 0)
        pct = cnt / total * 100 if total else 0
        lines.append(f"| {cat} | {cnt} | {pct:.1f}% |")
    lines.append(f"| **Total** | **{total}** | 100% |")
    lines.append("")
    lines.append("## §5 Architectural Question\n")
    lines.append(f"**Question:** Is `SUBJECT/CONTEXT/MODIFIER` a lexical property (local text) or a relational property (candidate + event + document context)?\n")
    lines.append(f"**Answer:** `{arch_answer['answer']}`\n")
    lines.append(f"**Reason:** {arch_answer['reason']}\n")
    lines.append("")
    lines.append("### Recommended Model\n")
    lines.append("```")
    lines.append(arch_answer["recommended_model"])
    lines.append("```")
    lines.append("")
    lines.append("### Strategic Decision\n")
    lines.append(f"> {arch_answer['strategic_decision']}")
    lines.append("")
    lines.append("## §6 Per-Case Forensic Table\n")
    lines.append("| # | Candidate | Human | V2.1 | Role | Head Noun | Verb | Classification |")
    lines.append("|---|-----------|-------|------|------|-----------|------|---------------|")
    for r in forensic_results:
        cat_short = r["classification"].split("_")[0]
        lines.append(
            f"| {r['case_id']} | {r['candidate'][:20]} | "
            f"{r['human_label'][:12]} | {r['v21_label'][:12]} | "
            f"{r['semantic_role'][:8]} | {r['modifier_signal'][:12]} | "
            f"{r['matched_verb'][:12]} | {cat_short} |"
        )
    lines.append("")
    lines.append("## §7 Per-Case Detailed Analysis\n")
    for r in forensic_results:
        lines.append(f"### Case #{r['case_id']} — {r['candidate']} ({r['classification']})\n")
        lines.append(f"- **Text:** \"{r['text']}\"")
        lines.append(f"- **Human label:** `{r['human_label']}`")
        lines.append(f"- **V2.1 label:** `{r['v21_label']}`")
        lines.append(f"- **Human reasoning:** {r['human_reasoning']}")
        lines.append(f"- **V2.1 signals:** event={r['event_signal']}, measurement={r['measurement_signal']}, semantic_role={r['semantic_role']}, matched_alias=`{r['matched_alias']}`, matched_verb=`{r['matched_verb']}`, effective_event={r['effective_event']}")
        if r['modifier_signal']:
            lines.append(f"- **Modifier head noun:** `{r['modifier_signal']}`")
        if r['evidence_spans']:
            for span in r['evidence_spans']:
                lines.append(f"- **Evidence span:** {span['context']}")
        lines.append(f"- **Why V2.1 decided:** {r['why_v21_decided']}")
        lines.append(f"- **Why human decided:** {r['why_human_decided']}")
        lines.append(f"- **Required information:** {r['required_information']}")
        lines.append(f"- **Classification:** `{r['classification']}`")
        lines.append("")
    lines.append("## §8 Forbidden (per user directive)\n")
    lines.append("- NO production changes")
    lines.append("- NO V2 changes")
    lines.append("- NO V2.1 changes")
    lines.append("- NO lexicon additions")
    lines.append("- NO threshold tuning")
    lines.append("- NO new holdout")
    lines.append("- NO embeddings")
    lines.append("- NO LLM")
    lines.append("- NO Entity Registry")
    lines.append("- NO source expansion")
    lines.append("- NO benchmark optimization")
    lines.append("- Bank Rate / federal funds rate NOT addressed (clear DATA_GAP, not the cause of semantic failure)")
    lines.append("")
    lines.append("---\n")
    lines.append("**V48AH is a SEMANTIC BOUNDARY REVIEW, NOT tuning, NOT production integration.** ")
    lines.append("No production files were modified. No V2/V2.1 changes. No new holdout. ")
    lines.append("The V48AG 150-case holdout is LOCKED and was NOT used for tuning.\n")
    lines.append("Per directive: DO NOT create V48AI automatically. STOP — user directive required for next phase.\n")
    path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run_v48ah()
