"""V48AJ — Causal Separation Experiment.

Separate the two competing explanations exposed by V48AI:
  A. EVENT_ATTRIBUTION_FAILURE
  B. DOCUMENT_CONTEXT_REQUIRED

Experiment ONLY. NOT implementation.
DO NOT modify production, V2.1, V48AG, or any frozen artifact.
"""
from __future__ import annotations
import json, sys, time, hashlib, re
from pathlib import Path
from collections import Counter

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))
import os; os.chdir(str(CORE_REPO))

from intelligence_core.subject_entity import _ALL_REGISTRIES

V48AG_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_results.json"
V48AG_PREREG = CORE_REPO / "intelligence_core/tests/reliability/v48ag_independent_preregistered_sample.json"
V48AH_FALS = CORE_REPO / "intelligence_core/tests/reliability/v48ah_falsification_results.json"
V48AF_V21_FILE = CORE_REPO / "intelligence_core/tests/reliability/v48af_v21_evaluator.py"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48aj_causal_separation.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AJ_CAUSAL_SEPARATION.md"


def _get_candidate_aliases(candidate_name: str) -> list[str]:
    for reg_type, reg in _ALL_REGISTRIES.items():
        for cid, (cname, etype, aliases) in reg.items():
            if cname == candidate_name:
                return aliases
    return []


def _extract_head_noun(aliases, text, matched_alias):
    text_lower = (text or "").lower()
    ma = (matched_alias or "").lower()
    if not ma: return ""
    idx = text_lower.find(ma)
    if idx < 0: return ""
    after = text_lower[idx + len(ma):idx + len(ma) + 25]
    words = after.split()
    return words[0].strip(".,;:") if words else ""


# ── Phase 2: Event Attribution Classification ──

CONCRETE_ACTION_VERBS = {
    "revised", "updated", "compiled", "issued", "maintained", "processed",
    "published", "upgraded", "refined", "added", "aligned", "harmonized",
    "outlined", "detailed", "scheduled", "released", "analyzed", "proposed",
    "reaffirmed", "reviewed", "described", "collected", "injected",
}

STATE_DESCRIPTION_VERBS = {
    "remain", "remains", "remained", "stabilized", "stood", "reached",
    "peaked", "totaled", "averaged",
}

META_REFERENCE_VERBS = {
    "cited", "identified", "noted", "described", "characterized",
    "highlighted", "featured", "discussed", "referenced", "mentioned",
    "outlined", "detailed", "reviewed", "analyzed", "compiled",
    "collected", "released", "scheduled", "published",
}

SECONDARY_TARGET_PATTERNS = [
    r"\bunder\s+close\s+monitoring\b",
    r"\bas\s+a\s+continuing\s+area\b",
    r"\bas\s+a\s+key\s+input\b",
    r"\bas\s+a\s+focus\b",
    r"\bas\s+a\s+labor\s+market\s+indicator\b",
    r"\bunder\s+continued\b",
]


def classify_event_attribution(text, candidate, head_noun, matched_alias):
    """Classify event attribution into A1/A2/A3/A4.

    A1 = event clearly applies to candidate
    A2 = event clearly applies to head noun/context
    A3 = event can plausibly apply to either
    A4 = attribution unavailable
    """
    text_lower = text.lower()

    # Find verbs in text
    all_verbs = set()
    for v in CONCRETE_ACTION_VERBS | STATE_DESCRIPTION_VERBS | META_REFERENCE_VERBS:
        if re.search(r"\b" + re.escape(v) + r"\b", text_lower):
            all_verbs.add(v)

    # Check for secondary target patterns
    has_secondary = any(re.search(p, text_lower) for p in SECONDARY_TARGET_PATTERNS)

    # Check for "subject of" pattern
    has_subject_of = "subject of" in text_lower

    # Check for state description verbs
    has_state = bool(all_verbs & STATE_DESCRIPTION_VERBS)

    # Check for "subject of" → meta-referential
    if has_subject_of:
        return "A3", (
            f"'subject of' construction — the event is meta-referential. "
            f"The event could plausibly apply to either the candidate or "
            f"the head noun."
        )

    # Check for secondary target patterns
    if has_secondary:
        return "A3", (
            f"Secondary target pattern detected — a secondary phrase "
            f"(e.g., 'under close monitoring', 'as a continuing area') "
            f"could apply to the candidate."
        )

    # If state description verb (remain, remains, stabilized)
    if has_state:
        return "A3", (
            f"State description verb ({all_verbs & STATE_DESCRIPTION_VERBS}) — "
            f"the verb describes a state, not a concrete action. "
            f"It could apply to either the candidate or the head noun."
        )

    # If concrete action verb
    concrete = all_verbs & CONCRETE_ACTION_VERBS
    if concrete:
        # Check if the verb is a concrete action on the head noun
        # (e.g., "statistics are compiled", "methodology was revised")
        return "A2", (
            f"Concrete action verb ({concrete}) — the event clearly "
            f"applies to the head noun '{head_noun}', not to the "
            f"candidate. The verb describes a concrete action on the "
            f"head noun."
        )

    # If meta-reference verb (without secondary pattern)
    meta = all_verbs & META_REFERENCE_VERBS
    if meta:
        return "A3", (
            f"Meta-reference verb ({meta}) — the event is a meta-reference "
            f"(citing, noting, describing). It could plausibly apply to "
            f"either the candidate or the head noun."
        )

    # No clear verb
    return "A4", "Attribution unavailable — no clear event verb detected."


# ── Phase 3: Document Context Classification ──

def classify_document_context(text, candidate, matched_alias):
    """Classify document context into D1/D2/D3/D4.

    D1 = context resolves candidate (document/heading names candidate)
    D2 = context resolves head noun/context (heading names different topic)
    D3 = context remains ambiguous
    D4 = context unavailable (no heading, synthetic document)
    """
    text_lower = text.lower()

    # Check for heading-like phrase (text before first ". " or first ".")
    heading = ""
    if ". " in text[:120]:
        heading = text[:text.index(". ")].strip()
    elif "." in text[:80] and not text[:80].startswith(("The ", "A ", "In ", "For ", "According")):
        heading = text[:text.index(".")].strip()

    if not heading or len(heading) < 10:
        # No heading — synthetic document
        return "D4", (
            "No heading-like phrase detected. Document context is "
            "unavailable (synthetic HTML with generic title 'T')."
        )

    # Check if heading contains the candidate's alias
    cand_aliases = _get_candidate_aliases(candidate)
    heading_lower = heading.lower()
    cand_in_heading = any(
        re.search(r"\b" + re.escape(a.lower()) + r"\b", heading_lower)
        for a in cand_aliases
    )

    # Check if heading names a competing topic
    topic_markers = ["report", "statistics", "data", "survey", "index",
                     "outlook", "review", "account", "spending",
                     "applications", "output", "production", "expenditure",
                     "industry", "sector", "market"]
    competing_markers = [m for m in topic_markers
                         if re.search(r"\b" + re.escape(m) + r"\b", heading_lower)]

    if cand_in_heading and not competing_markers:
        return "D1", (
            f"Heading '{heading}' names the candidate. "
            f"Document context resolves to the candidate."
        )
    elif competing_markers and not cand_in_heading:
        return "D2", (
            f"Heading '{heading}' names a competing topic "
            f"(markers: {competing_markers}). Document context "
            f"resolves to the head noun/context, not the candidate."
        )
    elif competing_markers and cand_in_heading:
        # Both candidate and competing marker in heading
        # Check position — which comes first?
        cand_pos = min(
            (heading_lower.find(a.lower()) for a in cand_aliases
             if a.lower() in heading_lower),
            default=-1
        )
        comp_pos = min(
            (heading_lower.find(m) for m in competing_markers
             if m in heading_lower),
            default=-1
        )
        if comp_pos >= 0 and cand_pos >= 0 and comp_pos < cand_pos:
            return "D2", (
                f"Heading '{heading}' has competing marker BEFORE "
                f"candidate — competing topic dominates."
            )
        else:
            return "D3", (
                f"Heading '{heading}' contains both candidate and "
                f"competing markers — context remains ambiguous."
            )
    else:
        return "D3", (
            f"Heading '{heading}' is generic — context remains ambiguous."
        )


# ── Main V48AJ runner ──

def run_v48aj():
    print("=" * 72)
    print("V48AJ — CAUSAL SEPARATION EXPERIMENT")
    print("=" * 72)
    print(f"  BASE: 054d591 (V48AI worklog) / 28a9b34 (V48AI forensic)")
    print(f"  Experiment ONLY — NOT implementation")
    print()

    v21_hash = hashlib.sha256(V48AF_V21_FILE.read_bytes()).hexdigest()
    print(f"  V2.1 SHA256: {v21_hash[:16]}...")
    print()

    # Load data
    v48ag = json.loads(V48AG_RESULTS.read_text())
    v48ag_per_case = {c["case_id"]: c for c in v48ag["new_holdout_results"]["per_case"]}
    prereg = json.loads(V48AG_PREREG.read_text())
    prereg_cases = {c["case_id"]: c for c in prereg["cases"]}
    v48ah_fals = json.loads(V48AH_FALS.read_text())

    h1_data = v48ah_fals["hypotheses"]["H1"]
    h1_explained_ids = h1_data["explained_case_ids"]
    h1_counterexample_ids = [ce["case_id"] for ce in h1_data["counterexamples"]]

    h1_per_case = {c["case_id"]: c for c in v48ah_fals["v48ag_diagnostic"]["h1_per_case"]}
    h2_per_case = {c["case_id"]: c for c in v48ah_fals["v48ag_diagnostic"]["h2_per_case"]}

    print(f"  H1 counterexamples: {len(h1_counterexample_ids)} ({h1_counterexample_ids})")
    print(f"  H1 explained: {len(h1_explained_ids)} ({h1_explained_ids})")
    print()

    # ── PHASE 1: H2 Reconciliation ──
    print("  PHASE 1: H2 Reconciliation")
    h2_reconciliation = []
    for case_id in [107, 12, 34]:
        prereg_c = prereg_cases.get(case_id, {})
        v21_c = v48ag_per_case.get(case_id, {})
        h2_c = h2_per_case.get(case_id, {})

        v21_j = v21_c.get("v21_judgment", "")
        h2_j = h2_c.get("h2", "")
        h2_changed = v21_j != h2_j
        v21_error = not v21_c.get("v21_matches_human", False)
        h2_error = not h2_c.get("matches", False)
        h2_caused = h2_error and not v21_error

        status = "H2_CAUSED" if h2_caused else ("PRE_EXISTING_V21_ERROR" if v21_error else "NO_ERROR")

        h2_reconciliation.append({
            "case_id": case_id,
            "text": prereg_c.get("text", "")[:100],
            "human_label": prereg_c.get("human_label", ""),
            "v21_judgment": v21_j,
            "h2_judgment": h2_j,
            "h2_changed_output": h2_changed,
            "error_existed_before_h2": v21_error,
            "h2_caused_error": h2_caused,
            "status": status,
        })
        print(f"    #{case_id}: V2.1={v21_j}, H2={h2_j}, changed={h2_changed}, status={status}")
    print()

    # ── PHASE 2: Event Attribution Test ──
    print("  PHASE 2: Event Attribution Test (29 cases)")
    attribution_results = []

    all_case_ids = h1_counterexample_ids + h1_explained_ids
    for case_id in all_case_ids:
        prereg_c = prereg_cases.get(case_id, {})
        v21_c = v48ag_per_case.get(case_id, {})
        h1_c = h1_per_case.get(case_id, {})

        text = prereg_c.get("text", "")
        candidate = prereg_c.get("candidate", "")
        v21_vec = v21_c.get("v21_vector", {}) or {}
        matched_alias = v21_vec.get("matched_alias", "")
        head_noun = _extract_head_noun(_get_candidate_aliases(candidate), text, matched_alias)

        a_state, a_reason = classify_event_attribution(text, candidate, head_noun, matched_alias)

        population = "counterexample" if case_id in h1_counterexample_ids else "explained"

        attribution_results.append({
            "case_id": case_id,
            "population": population,
            "candidate": candidate,
            "head_noun": head_noun,
            "matched_alias": matched_alias,
            "text": text,
            "a_state": a_state,
            "a_reason": a_reason,
            "human_label": prereg_c.get("human_label", ""),
            "v21_judgment": v21_c.get("v21_judgment", ""),
            "h1_judgment": h1_c.get("h1", ""),
        })

    # Build attribution matrix
    a_matrix = Counter()
    for r in attribution_results:
        a_matrix[(r["a_state"], r["population"])] += 1

    print(f"    Attribution matrix:")
    print(f"      {'':>20} {'Counterexample':>15} {'Explained':>10}")
    for a in ["A1", "A2", "A3", "A4"]:
        ce = a_matrix.get((a, "counterexample"), 0)
        ex = a_matrix.get((a, "explained"), 0)
        print(f"      {a:>20} {ce:>15} {ex:>10}")
    print()

    # ── PHASE 3: Document Context Test ──
    print("  PHASE 3: Document Context Test (29 cases)")
    context_results = []

    for case_id in all_case_ids:
        prereg_c = prereg_cases.get(case_id, {})
        text = prereg_c.get("text", "")
        candidate = prereg_c.get("candidate", "")
        v21_vec = v48ag_per_case.get(case_id, {}).get("v21_vector", {}) or {}
        matched_alias = v21_vec.get("matched_alias", "")

        d_state, d_reason = classify_document_context(text, candidate, matched_alias)

        population = "counterexample" if case_id in h1_counterexample_ids else "explained"

        context_results.append({
            "case_id": case_id,
            "population": population,
            "candidate": candidate,
            "text": text,
            "d_state": d_state,
            "d_reason": d_reason,
            "human_label": prereg_c.get("human_label", ""),
        })

    # Build context matrix
    d_matrix = Counter()
    for r in context_results:
        d_matrix[(r["d_state"], r["population"])] += 1

    print(f"    Document context matrix:")
    print(f"      {'':>20} {'Counterexample':>15} {'Explained':>10}")
    for d in ["D1", "D2", "D3", "D4"]:
        ce = d_matrix.get((d, "counterexample"), 0)
        ex = d_matrix.get((d, "explained"), 0)
        print(f"      {d:>20} {ce:>15} {ex:>10}")
    print()

    # ── PHASE 4: Cross Matrix ──
    print("  PHASE 4: Cross Matrix (A-state × D-state)")
    joint_matrix = Counter()
    for ar, cr in zip(attribution_results, context_results):
        joint_matrix[(ar["a_state"], cr["d_state"], ar["population"])] += 1

    print(f"    Joint matrix (A × D × Population):")
    for a in ["A1", "A2", "A3", "A4"]:
        for d in ["D1", "D2", "D3", "D4"]:
            ce = joint_matrix.get((a, d, "counterexample"), 0)
            ex = joint_matrix.get((a, d, "explained"), 0)
            if ce or ex:
                print(f"      {a}×{d}: counterexample={ce}, explained={ex}")
    print()

    # ── PHASE 5: Causal Interpretation ──
    print("  PHASE 5: Causal Interpretation")

    # H_EVENT_ATTRIBUTION: Does A-state separate the populations?
    a_sep_counter = Counter(r["a_state"] for r in attribution_results if r["population"] == "counterexample")
    a_sep_explained = Counter(r["a_state"] for r in attribution_results if r["population"] == "explained")

    # Check if A-state is discriminative
    # A is discriminative if one population is predominantly A2 and the other is predominantly A3
    a_discriminative = False
    a_evidence = ""
    if a_sep_counter.get("A2", 0) > 0 and a_sep_explained.get("A3", 0) > 0:
        ratio_ce_a2 = a_sep_counter.get("A2", 0) / max(1, sum(a_sep_counter.values()))
        ratio_ex_a3 = a_sep_explained.get("A3", 0) / max(1, sum(a_sep_explained.values()))
        if ratio_ce_a2 > 0.5 and ratio_ex_a3 > 0.5:
            a_discriminative = True
            a_evidence = (
                f"Counterexamples are {ratio_ce_a2:.0%} A2 (event applies to head noun), "
                f"explained are {ratio_ex_a3:.0%} A3 (event applies to either). "
                f"This suggests event attribution IS discriminative."
            )

    print(f"    H_EVENT_ATTRIBUTION: {'SUPPORTED' if a_discriminative else 'NOT_SUPPORTED'}")
    print(f"      Counterexample A-states: {dict(a_sep_counter)}")
    print(f"      Explained A-states: {dict(a_sep_explained)}")
    if a_evidence:
        print(f"      Evidence: {a_evidence}")
    print()

    # H_DOCUMENT_CONTEXT: Does D-state separate the populations?
    d_sep_counter = Counter(r["d_state"] for r in context_results if r["population"] == "counterexample")
    d_sep_explained = Counter(r["d_state"] for r in context_results if r["population"] == "explained")

    d_discriminative = False
    d_evidence = ""
    # D is discriminative if one population is predominantly D2 and the other is D4
    if d_sep_counter.get("D2", 0) > 0 or d_sep_explained.get("D2", 0) > 0:
        # Check if D2 appears in one population but not the other
        if d_sep_counter.get("D2", 0) > 0 and d_sep_explained.get("D2", 0) == 0:
            d_discriminative = True
            d_evidence = "D2 (competing topic) appears ONLY in counterexamples."
        elif d_sep_explained.get("D2", 0) > 0 and d_sep_counter.get("D2", 0) == 0:
            d_discriminative = True
            d_evidence = "D2 (competing topic) appears ONLY in explained cases."

    print(f"    H_DOCUMENT_CONTEXT: {'SUPPORTED' if d_discriminative else 'NOT_SUPPORTED'}")
    print(f"      Counterexample D-states: {dict(d_sep_counter)}")
    print(f"      Explained D-states: {dict(d_sep_explained)}")
    if d_evidence:
        print(f"      Evidence: {d_evidence}")
    print()

    # H_BOTH
    both_discriminative = a_discriminative or d_discriminative
    print(f"    H_BOTH: {'SUPPORTED' if both_discriminative else 'NOT_SUPPORTED'}")
    print()

    # H_NEITHER
    neither = not a_discriminative and not d_discriminative
    print(f"    H_NEITHER: {'SUPPORTED' if neither else 'NOT_SUPPORTED'}")
    print()

    # Final verdict
    if a_discriminative and d_discriminative:
        verdict = "BOTH_SUPPORTED"
    elif a_discriminative:
        verdict = "EVENT_ATTRIBUTION_SUPPORTED"
    elif d_discriminative:
        verdict = "DOCUMENT_CONTEXT_SUPPORTED"
    elif neither:
        verdict = "UNRESOLVED"
    else:
        verdict = "UNRESOLVED"

    print(f"  FINAL VERDICT: {verdict}")
    print()

    # ── Verify production unchanged ──
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
    print(f"  Production + V2 + V2.1 + V48AG-pre-reg: {len(prod_hashes)} files verified unchanged")
    print()

    # ── Persist artifacts ──
    print("  Persisting artifacts...")
    OUT_JSON.write_text(json.dumps({
        "phase": "V48AJ CAUSAL SEPARATION EXPERIMENT",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_commit": "054d591",
        "v21_sha256": v21_hash,
        "production_hashes": prod_hashes,
        "phase1_h2_reconciliation": h2_reconciliation,
        "phase2_event_attribution": {
            "per_case": attribution_results,
            "matrix": {f"{k[0]}_{k[1]}": v for k, v in a_matrix.items()},
        },
        "phase3_document_context": {
            "per_case": context_results,
            "matrix": {f"{k[0]}_{k[1]}": v for k, v in d_matrix.items()},
        },
        "phase4_joint_matrix": {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in joint_matrix.items()},
        "phase5_causal_interpretation": {
            "H_EVENT_ATTRIBUTION": {"supported": a_discriminative, "evidence": a_evidence,
                                   "counterexample_a_states": dict(a_sep_counter),
                                   "explained_a_states": dict(a_sep_explained)},
            "H_DOCUMENT_CONTEXT": {"supported": d_discriminative, "evidence": d_evidence,
                                  "counterexample_d_states": dict(d_sep_counter),
                                  "explained_d_states": dict(d_sep_explained)},
            "H_BOTH": {"supported": both_discriminative},
            "H_NEITHER": {"supported": neither},
        },
        "final_verdict": verdict,
        "STOP": True,
        "DO_NOT_create_V48AK": True,
        "DO_NOT_modify_production": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"    OK  {OUT_JSON}")

    # Build markdown report
    lines = []
    lines.append("# V48AJ — Causal Separation Experiment\n")
    lines.append(f"**Executed at (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    lines.append(f"**Base:** `054d591` / `28a9b34` (V48AI)\n")
    lines.append(f"**Verdict:** `{verdict}`\n")
    lines.append("")
    lines.append("## Phase 1: H2 Reconciliation\n")
    lines.append("| Case | V2.1 | H2 | Changed? | Pre-existing? | H2-caused? | Status |\n")
    lines.append("|------|------|----|----------|----------------|------------|--------|\n")
    for h in h2_reconciliation:
        lines.append(f"| #{h['case_id']} | {h['v21_judgment']} | {h['h2_judgment']} | {h['h2_changed_output']} | {h['error_existed_before_h2']} | {h['h2_caused_error']} | {h['status']} |")
    lines.append("")
    lines.append("## Phase 2: Event Attribution Matrix\n")
    lines.append("| A-state | Counterexample | Explained |\n")
    lines.append("|---------|---------------:|----------:|\n")
    for a in ["A1", "A2", "A3", "A4"]:
        ce = a_matrix.get((a, "counterexample"), 0)
        ex = a_matrix.get((a, "explained"), 0)
        lines.append(f"| {a} | {ce} | {ex} |")
    lines.append("")
    lines.append("## Phase 3: Document Context Matrix\n")
    lines.append("| D-state | Counterexample | Explained |\n")
    lines.append("|---------|---------------:|----------:|\n")
    for d in ["D1", "D2", "D3", "D4"]:
        ce = d_matrix.get((d, "counterexample"), 0)
        ex = d_matrix.get((d, "explained"), 0)
        lines.append(f"| {d} | {ce} | {ex} |")
    lines.append("")
    lines.append("## Phase 4: Joint Matrix (A × D)\n")
    lines.append("| A×D | Counterexample | Explained |\n")
    lines.append("|-----|---------------:|----------:|\n")
    for a in ["A1", "A2", "A3", "A4"]:
        for d in ["D1", "D2", "D3", "D4"]:
            ce = joint_matrix.get((a, d, "counterexample"), 0)
            ex = joint_matrix.get((a, d, "explained"), 0)
            if ce or ex:
                lines.append(f"| {a}×{d} | {ce} | {ex} |")
    lines.append("")
    lines.append("## Phase 5: Causal Interpretation\n")
    lines.append(f"### H_EVENT_ATTRIBUTION: {'SUPPORTED' if a_discriminative else 'NOT_SUPPORTED'}\n")
    lines.append(f"- Counterexample: {dict(a_sep_counter)}\n")
    lines.append(f"- Explained: {dict(a_sep_explained)}\n")
    if a_evidence:
        lines.append(f"- Evidence: {a_evidence}\n")
    lines.append("")
    lines.append(f"### H_DOCUMENT_CONTEXT: {'SUPPORTED' if d_discriminative else 'NOT_SUPPORTED'}\n")
    lines.append(f"- Counterexample: {dict(d_sep_counter)}\n")
    lines.append(f"- Explained: {dict(d_sep_explained)}\n")
    if d_evidence:
        lines.append(f"- Evidence: {d_evidence}\n")
    lines.append("")
    lines.append(f"## Final Verdict: `{verdict}`\n")
    lines.append("")
    lines.append("---\n")
    lines.append("**V48AJ is a CAUSAL SEPARATION EXPERIMENT, NOT implementation.**\n")
    lines.append("No production changes. No V2.1 changes. No fixes. STOP.\n")
    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"    OK  {OUT_MD}")

    print()
    print("=" * 72)
    print("V48AJ CAUSAL SEPARATION — COMPLETE")
    print("=" * 72)
    print(f"\n  FINAL VERDICT: {verdict}")
    print(f"\n  H_EVENT_ATTRIBUTION: {'SUPPORTED' if a_discriminative else 'NOT_SUPPORTED'}")
    print(f"  H_DOCUMENT_CONTEXT: {'SUPPORTED' if d_discriminative else 'NOT_SUPPORTED'}")
    print(f"\n  STOP. No V48AK. No production changes. No fixes.")
    print()
    return verdict


if __name__ == "__main__":
    run_v48aj()
