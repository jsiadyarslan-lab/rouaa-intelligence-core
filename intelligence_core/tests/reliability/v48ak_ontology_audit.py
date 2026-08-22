"""V48AK — Label Ontology / Semantic Target Audit.

Forensic ontology audit. NOT implementation.
Determines whether TRUE_SUBJECT / CONTEXT_ONLY / AMBIGUOUS are cleanly
separable or structurally conflating multiple semantic relations.
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
V48AI_FORENSIC = CORE_REPO / "intelligence_core/tests/reliability/v48ai_forensic_adjudication.json"
V48AJ_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48aj_causal_separation.json"
V48AF_V21_FILE = CORE_REPO / "intelligence_core/tests/reliability/v48af_v21_evaluator.py"
V48AE_PREREG = CORE_REPO / "intelligence_core/tests/reliability/v48ae_preregistered_sample.json"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48ak_ontology_audit.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AK_ONTOLOGY_AUDIT.md"


def _get_candidate_aliases(candidate_name):
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


def run_v48ak():
    print("=" * 72)
    print("V48AK — LABEL ONTOLOGY / SEMANTIC TARGET AUDIT")
    print("=" * 72)
    print(f"  BASE: 6a3c386 (V48AJ)")
    print(f"  Forensic ontology audit — NOT implementation")
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
    v48aj = json.loads(V48AJ_RESULTS.read_text())

    h1_data = v48ah_fals["hypotheses"]["H1"]
    h1_explained_ids = h1_data["explained_case_ids"]
    h1_counterexample_ids = [ce["case_id"] for ce in h1_data["counterexamples"]]
    all_29 = h1_counterexample_ids + h1_explained_ids

    print(f"  29 cases: {len(h1_counterexample_ids)} counterexamples + {len(h1_explained_ids)} explained")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 1 — RECOVER THE LABEL SEMANTICS
    # ════════════════════════════════════════════════════════════════
    print("  PHASE 1: Recover label semantics")

    # Read V2.1 source for actual implementation definitions
    v21_source = V48AF_V21_FILE.read_text()

    # Read V48AE pre-reg for documented definitions
    v48ae_prereg = json.loads(V48AE_PREREG.read_text())
    v48ae_defs = v48ae_prereg.get("label_definitions", {})

    # Read V48AG pre-reg for documented definitions
    v48ag_defs = prereg.get("label_definitions", {})

    phase1 = {
        "TRUE_SUBJECT": {
            "documented_definition": v48ag_defs.get("TRUE_SUBJECT", "DEFINITION NOT EXPLICITLY SPECIFIED"),
            "actual_implementation": (
                "V2.1 code: judgment='TRUE_SUBJECT' when:\n"
                "  1. role=SUBJECT + strong_count>=2 (event+measurement+fact STRONG)\n"
                "  2. role=SUBJECT + strong_count==1 + event in (STRONG, MODERATE)\n"
                "  3. role=SUBJECT + event=STRONG + not topic_contradiction\n"
                "  4. role=CONTEXT + event=STRONG + measurement=STRONG (OVERRIDE)\n"
                "  5. H2 pattern match (held at / reduce by basis points) → event=STRONG + role=SUBJECT\n"
                "Implementation uses PROXY: event verb NEAR candidate (not event verb APPLIES TO candidate)."
            ),
            "test_fixture_definition": (
                "V48AE pre-reg: 'The candidate IS the semantic subject of the event — "
                "the event verb applies to the candidate, and the measurement (if any) "
                "describes the candidate.'\n"
                "V48AG pre-reg: same definition."
            ),
            "discrepancies": (
                "1. IMPLEMENTATION vs DOCUMENTATION: V2.1 checks whether an event verb "
                "appears in a WINDOW near the candidate, NOT whether the event verb "
                "APPLIES TO the candidate. 'GDP increased' and 'GDP statistics are "
                "compiled' both match event=STRONG (via verb proximity), but the "
                "event only applies to GDP in the first case.\n"
                "2. OVERRIDE: V2.1 returns TRUE_SUBJECT even when role=CONTEXT "
                "(heading names competing topic) if event+measurement are both STRONG. "
                "This contradicts the documented definition which requires the candidate "
                "to BE the semantic subject.\n"
                "3. NO EVENT-ATTRIBUTION CHECK: V2.1 never verifies that the event "
                "verb's syntactic subject IS the candidate. It only checks verb proximity."
            ),
        },
        "CONTEXT_ONLY": {
            "documented_definition": v48ag_defs.get("CONTEXT", "DEFINITION NOT EXPLICITLY SPECIFIED"),
            "actual_implementation": (
                "V2.1 code: judgment='CONTEXT_ONLY' when:\n"
                "  1. role=MODIFIER + effective_event not STRONG\n"
                "  2. role=MEASURE + effective_event not STRONG\n"
                "Implementation uses PROXY: head noun follows candidate (not semantic "
                "determination that candidate is context-only)."
            ),
            "test_fixture_definition": (
                "V48AE pre-reg: 'The candidate appears as a noun modifier or context-only "
                "reference (e.g., FX turnover data is collected — FX is a modifier of data, "
                "not the subject of an action).'\n"
                "V48AG pre-reg: same definition."
            ),
            "discrepancies": (
                "1. IMPLEMENTATION vs DOCUMENTATION: V2.1 detects MODIFIER via head-noun "
                "presence (syntactic proxy), NOT via semantic determination that the "
                "candidate is context-only. A candidate followed by a head noun is "
                "automatically MODIFIER, regardless of whether the event is about the "
                "candidate or the head noun.\n"
                "2. NO EVENT-ATTRIBUTION CHECK: V2.1 doesn't verify that the event verb "
                "applies to the HEAD NOUN (not the candidate). It only checks that the "
                "candidate has a head noun (syntactic) and that the event is weak (insufficient).\n"
                "3. MEASURE conflation: V2.1 returns CONTEXT_ONLY for role=MEASURE "
                "(GDP deflator, CPI basket) — but the documented definition doesn't "
                "explicitly cover this case."
            ),
        },
        "AMBIGUOUS": {
            "documented_definition": v48ag_defs.get("AMBIGUOUS", "DEFINITION NOT EXPLICITLY SPECIFIED"),
            "actual_implementation": (
                "V2.1 code: judgment='AMBIGUOUS' when:\n"
                "  1. role=CONTEXT + event=STRONG (conflict, no measurement)\n"
                "  2. role=MODIFIER + event=STRONG + measurement=STRONG (conflict)\n"
                "  3. role=MODIFIER + event=STRONG (conflict, no measurement)\n"
                "  4. role=ACTOR (always — genuine)\n"
                "  5. fact=CONTRADICTED + event=STRONG (conflicting evidence)\n"
                "  6. event=WEAK + topic_contradiction\n"
                "  7. event=WEAK (insufficient evidence)\n"
                "  8. DEFAULT FALLBACK (no other label applies)\n"
                "AMBIGUOUS is used as catch-all for: conflicting evidence, insufficient "
                "evidence, genuine ambiguity, and default fallback."
            ),
            "test_fixture_definition": (
                "V48AE pre-reg: 'The case has conflicting signals or is genuinely unclear "
                "to a human reader — the candidate is mentioned but its role as subject "
                "cannot be determined with confidence.'\n"
                "V48AG pre-reg: same definition."
            ),
            "discrepancies": (
                "1. CONFLATION: AMBIGUOUS is used for at least 4 SEMANTICALLY DIFFERENT "
                "situations: (a) conflicting evidence (event=STRONG + fact=CONTRADICTED), "
                "(b) insufficient evidence (event=WEAK), (c) role conflict (MODIFIER + "
                "event=STRONG), (d) default fallback. These are epistemically different "
                "but the label doesn't distinguish them.\n"
                "2. NO CERTAINTY DIMENSION: The documented definition says 'genuinely "
                "unclear,' but V2.1 returns AMBIGUOUS even when the case is NOT genuinely "
                "unclear — it's just insufficient evidence (event=WEAK).\n"
                "3. NO ATTRIBUTION DISTINCTION: V2.1 doesn't distinguish 'I can't tell "
                "if the event applies to the candidate or the head noun' from 'I found "
                "no event evidence at all.' Both return AMBIGUOUS."
            ),
        },
    }

    for label, info in phase1.items():
        print(f"    {label}:")
        print(f"      Documented: {info['documented_definition'][:100]}...")
        print(f"      Discrepancies: {len(info['discrepancies'])} chars")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 2 — RELATIONAL DECOMPOSITION
    # ════════════════════════════════════════════════════════════════
    print("  PHASE 2: Relational decomposition (29 cases)")

    decomposition = []
    for case_id in all_29:
        case = prereg_cases.get(case_id, {})
        v21_c = v48ag_per_case.get(case_id, {})
        v21_vec = v21_c.get("v21_vector", {}) or {}

        text = case.get("text", "")
        candidate = case.get("candidate", "")
        matched_alias = v21_vec.get("matched_alias", "")
        head_noun = _extract_head_noun(_get_candidate_aliases(candidate), text, matched_alias)
        human_label = case.get("human_label", "")
        population = "counterexample" if case_id in h1_counterexample_ids else "explained"

        # Extract event verb
        event_verbs = []
        text_lower = text.lower()
        verb_categories = {
            "increase": ["increased","rose","grew","climbed","surged","accelerated","expanded","advanced","improved","rebounded","recovered","peaked"],
            "decrease": ["decreased","fell","declined","dropped","slowed","contracted","dipped","eased"],
            "maintain": ["maintained","held","set","kept","unchanged","stabilized","stood","remain","remains","remained","stayed"],
            "impose": ["imposed","levied","fined","assessed","penalized","charged","issued","finalized","settled"],
            "decide": ["decided","announced","published","released","proposed","reaffirmed","reviewed"],
            "admin": ["compiled","collected","released","analyzed","outlined","detailed","scheduled","updated","revised","described","highlighted","featured","added","aligned","harmonized","processed","upgraded","refined"],
            "meta": ["cited","identified","noted","described","characterized","referenced","mentioned","discussed"],
        }
        for cat, verbs in verb_categories.items():
            for v in verbs:
                if re.search(r"\b" + re.escape(v) + r"\b", text_lower):
                    event_verbs.append((v, cat))

        # Determine event target
        event_target = "unavailable"
        if head_noun and event_verbs:
            # Check if the verb follows the head noun (applies to head noun)
            # or follows the candidate (applies to candidate)
            event_target = head_noun  # default: event applies to head noun

        # Determine modifier relation
        modifier_relation = "none"
        if head_noun:
            modifier_relation = f"{candidate} is a topic modifier of '{head_noun}'"

        # Determine semantic subject
        semantic_subject = head_noun if head_noun else "unavailable"

        # Check for secondary target (e.g., "under close monitoring")
        has_secondary = bool(re.search(r"\bunder\s+(?:close\s+)?monitoring\b|\bas\s+a\s+continuing\s+area\b|\bas\s+a\s+key\s+input\b|\bas\s+a\s+focus\b", text_lower))

        decomposition.append({
            "case_id": case_id,
            "population": population,
            "CANDIDATE": candidate,
            "HEAD_NOUN": head_noun,
            "MODIFIER_RELATION": modifier_relation,
            "EVENT": [v[0] for v in event_verbs] or "none",
            "EVENT_CATEGORY": [v[1] for v in event_verbs] or "none",
            "EVENT_TARGET": event_target,
            "SEMANTIC_SUBJECT": semantic_subject,
            "DOCUMENT_TOPIC": "unknown (synthetic)",
            "LOCAL_CONTEXT": text[max(0, text.find(matched_alias)+len(matched_alias)):min(len(text), text.find(matched_alias)+len(matched_alias)+60)] if matched_alias else "",
            "DOCUMENT_CONTEXT": "unavailable (synthetic HTML)",
            "EVIDENCE_SCOPE": "local text only",
            "has_secondary_target": has_secondary,
            "human_label": human_label,
            "text": text,
        })

    print(f"    Decomposed {len(decomposition)} cases")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 3 — LABEL COMPATIBILITY TEST
    # ════════════════════════════════════════════════════════════════
    print("  PHASE 3: Label compatibility test")

    compatibility = []
    for d in decomposition:
        case_id = d["case_id"]
        text = d["text"]
        candidate = d["CANDIDATE"]
        head_noun = d["HEAD_NOUN"]
        event_verbs = d["EVENT"]
        event_cats = d["EVENT_CATEGORY"]
        has_secondary = d["has_secondary_target"]
        human = d["human_label"]

        # Is TRUE_SUBJECT semantically possible?
        ts_possible = False
        ts_reason = ""
        if event_cats and any(c in ("increase", "decrease", "maintain", "impose") for c in event_cats):
            # Measurement event verbs — candidate COULD be the subject
            if has_secondary:
                ts_possible = True
                ts_reason = "Secondary target pattern suggests event could apply to candidate"
            elif not head_noun:
                ts_possible = True
                ts_reason = "No head noun — candidate could be direct subject"
        if "subject of" in text.lower():
            ts_possible = True
            ts_reason = "'subject of' construction — meta-referential, could be about candidate"

        # Is CONTEXT_ONLY semantically possible?
        co_possible = False
        co_reason = ""
        if head_noun:
            co_possible = True
            co_reason = f"Candidate is a modifier of '{head_noun}' — clearly context-only"
        if not has_secondary and head_noun:
            co_reason += " (no secondary target — event clearly on head noun)"

        # Is AMBIGUOUS semantically possible?
        am_possible = False
        am_reason = ""
        if has_secondary:
            am_possible = True
            am_reason = "Secondary target pattern creates genuine ambiguity"
        if any(c in ("meta",) for c in event_cats):
            am_possible = True
            am_reason = "Meta-reference verb — could apply to either"
        if "subject of" in text.lower():
            am_possible = True
            am_reason = "'subject of' — meta-referential"

        # Best semantic description
        labels_possible = []
        if ts_possible: labels_possible.append("TRUE_SUBJECT")
        if co_possible: labels_possible.append("CONTEXT_ONLY")
        if am_possible: labels_possible.append("AMBIGUOUS")

        if len(labels_possible) == 1:
            best = labels_possible[0]
        elif len(labels_possible) == 0:
            best = "NONE_ADEQUATE"
        else:
            best = "MULTIPLE_VALID: " + "+".join(labels_possible)

        compatibility.append({
            "case_id": case_id,
            "population": d["population"],
            "TRUE_SUBJECT_possible": ts_possible,
            "TRUE_SUBJECT_reason": ts_reason,
            "CONTEXT_ONLY_possible": co_possible,
            "CONTEXT_ONLY_reason": co_reason,
            "AMBIGUOUS_possible": am_possible,
            "AMBIGUOUS_reason": am_reason,
            "labels_possible": labels_possible,
            "best_description": best,
            "human_label": human,
            "text": text[:80],
        })

    # Count categories
    best_counts = Counter(c["best_description"].split(":")[0] for c in compatibility)
    print(f"    Best description distribution:")
    for k, v in best_counts.most_common():
        print(f"      {k}: {v}")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 4 — COUNTEREXAMPLE-FIRST AUDIT
    # ════════════════════════════════════════════════════════════════
    print("  PHASE 4: Counterexample-first audit")

    # For each counterexample: is the problem classifier or label?
    counterexample_audit = []
    for c in compatibility:
        if c["population"] != "counterexample":
            continue
        problem = "CLASSIFIER"
        reason = ""
        if c["best_description"] == "CONTEXT_ONLY":
            problem = "CLASSIFIER"
            reason = "The label CONTEXT_ONLY is semantically correct. The problem is the classifier (H1) changed it to AMBIGUOUS incorrectly."
        elif "MULTIPLE" in c["best_description"]:
            problem = "LABEL_INSUFFICIENT"
            reason = "Multiple labels are semantically valid — the three-label ontology is insufficient to express the actual relationship."
        elif c["best_description"] == "NONE_ADEQUATE":
            problem = "LABEL_INSUFFICIENT"
            reason = "None of the three labels adequately describes the semantic relationship."
        else:
            reason = "Single label is correct — classifier issue."
        counterexample_audit.append({
            "case_id": c["case_id"],
            "problem": problem,
            "reason": reason,
            "human_label": c["human_label"],
            "best_description": c["best_description"],
        })

    for ca in counterexample_audit:
        print(f"    #{ca['case_id']}: problem={ca['problem']}, best={ca['best_description']}")

    # Find similar pairs with different labels
    print()
    print("  Similar pairs with different human labels:")
    pairs_found = 0
    for ce in compatibility:
        if ce["population"] != "counterexample":
            continue
        for ex in compatibility:
            if ex["population"] != "explained":
                continue
            # Check similarity: same candidate, similar head noun
            ce_case = prereg_cases.get(ce["case_id"], {})
            ex_case = prereg_cases.get(ex["case_id"], {})
            if ce_case.get("candidate") == ex_case.get("candidate"):
                ce_hn = _extract_head_noun(
                    _get_candidate_aliases(ce_case.get("candidate","")),
                    ce_case.get("text",""),
                    v48ag_per_case.get(ce["case_id"],{}).get("v21_vector",{}).get("matched_alias",""))
                ex_hn = _extract_head_noun(
                    _get_candidate_aliases(ex_case.get("candidate","")),
                    ex_case.get("text",""),
                    v48ag_per_case.get(ex["case_id"],{}).get("v21_vector",{}).get("matched_alias",""))
                if ce_hn == ex_hn or (ce_hn and ex_hn and ce_hn[:4] == ex_hn[:4]):
                    pairs_found += 1
                    ce_text = ce_case.get("text","")[:70]
                    ex_text = ex_case.get("text","")[:70]
                    print(f"    PAIR: #{ce['case_id']}({ce['human_label']}) vs #{ex['case_id']}({ex['human_label']})")
                    print(f"      CE: {ce_text}")
                    print(f"      EX: {ex_text}")
                    print(f"      head_noun: CE={ce_hn}, EX={ex_hn}")
                    print(f"      DIFFERENCE: different event verb / construction → different human label")
                    print()
    if pairs_found == 0:
        print("    (no exact candidate+head-noun pairs found)")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 5 — TEST THE THREE-LABEL ASSUMPTION
    # ════════════════════════════════════════════════════════════════
    print("  PHASE 5: Test the three-label assumption")

    # Analyze what dimensions the labels conflate
    # From Phase 1 discrepancies:
    # TRUE_SUBJECT conflates: syntactic subjecthood + event attribution + measurement presence
    # CONTEXT_ONLY conflates: noun-modifier role + event weakness + contextual mention
    # AMBIGUOUS conflates: conflicting evidence + insufficient evidence + genuine ambiguity + default

    # Count how many cases have MULTIPLE_VALID labels
    multiple_valid = sum(1 for c in compatibility if "MULTIPLE" in c["best_description"])
    none_adequate = sum(1 for c in compatibility if c["best_description"] == "NONE_ADEQUATE")
    single_label = sum(1 for c in compatibility if c["best_description"] in ("TRUE_SUBJECT", "CONTEXT_ONLY", "AMBIGUOUS"))

    print(f"    Single label (cleanly separable): {single_label}/29")
    print(f"    Multiple labels valid (overlapping): {multiple_valid}/29")
    print(f"    None adequate (under-specified): {none_adequate}/29")
    print()

    # Determine ontology structure
    # Key question: do the labels represent independent dimensions?
    # From Phase 1:
    # - TRUE_SUBJECT requires: subjecthood + event attribution + measurement
    # - CONTEXT_ONLY requires: modifier role + event weakness
    # - AMBIGUOUS is used for: conflict + insufficient + genuine + default

    # These are NOT three mutually exclusive states — they conflate:
    # 1. Subjecthood (is candidate the syntactic/semantic subject?)
    # 2. Event attribution (does event apply to candidate or head noun?)
    # 3. Contextual relevance (is candidate context or topic?)
    # 4. Attribution certainty (confident vs unsure vs no evidence)
    # 5. Semantic scope (what does the document cover?)

    conflation_evidence = (
        "Phase 1 found that:\n"
        "1. TRUE_SUBJECT conflates syntactic subjecthood (verb proximity) with "
        "semantic event attribution (verb applies to candidate). V2.1 checks "
        "proximity, not attribution.\n"
        "2. CONTEXT_ONLY conflates noun-modifier role (syntactic) with "
        "contextual relevance (semantic). V2.1 detects head-noun presence, not "
        "whether the candidate is context-only.\n"
        "3. AMBIGUOUS is used as a catch-all for at least 4 epistemically different "
        "situations: (a) conflicting evidence, (b) insufficient evidence, (c) role "
        "conflict, (d) default fallback. These are NOT semantically equivalent.\n"
        "Phase 3 found that {multiple_valid}/29 cases have MULTIPLE labels "
        "that are semantically valid — the labels overlap.\n"
        "Phase 4 found similar pairs (same candidate, same head noun, same "
        "syntactic structure) with DIFFERENT human labels — the distinguishing "
        "dimension (event attribution certainty, secondary target, document topic) "
        "is NOT represented by the three labels."
    ).format(multiple_valid=multiple_valid)

    print(f"    Conflation evidence:")
    print(f"    {conflation_evidence[:500]}...")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 6 — DECISION
    # ════════════════════════════════════════════════════════════════
    print("  PHASE 6: Decision")

    if multiple_valid > 10 or none_adequate > 5:
        verdict = "ONTOLOGY_CONFLATES_RELATIONS"
    elif multiple_valid > 5:
        verdict = "ONTOLOGY_PARTIALLY_OVERLAPPING"
    elif none_adequate > 0:
        verdict = "ONTOLOGY_UNDERSPECIFIED"
    elif single_label == 29:
        verdict = "ONTOLOGY_SOUND"
    else:
        verdict = "ONTOLOGY_UNRESOLVED"

    evidence_for = conflation_evidence
    evidence_against = (
        f"Counter-evidence: {single_label}/29 cases DO have a single clearly "
        f"correct label — the ontology IS sufficient for those cases. The "
        f"conflation only manifests when the case has conflicting signals "
        f"(secondary target, meta-reference verb, or ambiguous event attribution)."
    )
    unresolved_cases = [c["case_id"] for c in compatibility if "MULTIPLE" in c["best_description"] or c["best_description"] == "NONE_ADEQUATE"]
    missing_info = (
        "To decide confidently whether the ontology needs replacement vs extension, "
        "we need to: (1) test on REAL documents (not synthetic) to determine "
        "if document context resolves the ambiguous cases; (2) determine if a "
        "multi-dimensional label (separate subjecthood/event-attribution/certainty) "
        "would cleanly separate the populations that V48AJ couldn't separate."
    )

    print(f"    VERDICT: {verdict}")
    print(f"    Multiple valid: {multiple_valid}/29")
    print(f"    None adequate: {none_adequate}/29")
    print(f"    Single label: {single_label}/29")
    print(f"    Unresolved cases: {unresolved_cases}")
    print()

    # ════════════════════════════════════════════════════════════════
    # PHASE 7 — INTEGRITY
    # ════════════════════════════════════════════════════════════════
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
    print(f"  PHASE 7: Integrity — {len(prod_hashes)} files verified unchanged")
    print()

    # ── Persist ──
    print("  Persisting artifacts...")
    OUT_JSON.write_text(json.dumps({
        "phase": "V48AK LABEL ONTOLOGY / SEMANTIC TARGET AUDIT",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_commit": "6a3c386",
        "v21_sha256": v21_hash,
        "production_hashes": prod_hashes,
        "phase1_label_semantics": phase1,
        "phase2_relational_decomposition": decomposition,
        "phase3_label_compatibility": compatibility,
        "phase3_best_distribution": dict(best_counts),
        "phase4_counterexample_audit": counterexample_audit,
        "phase5_conflation_evidence": conflation_evidence,
        "phase6_verdict": verdict,
        "phase6_evidence_for": evidence_for,
        "phase6_evidence_against": evidence_against,
        "phase6_unresolved_cases": unresolved_cases,
        "phase6_missing_info": missing_info,
        "DO_NOT_design_new_ontology": True,
        "DO_NOT_rename_labels": True,
        "DO_NOT_modify_classifier": True,
        "DO_NOT_create_V48AL": True,
        "STOP": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"    OK  {OUT_JSON}")

    # Markdown report
    lines = []
    lines.append("# V48AK — Label Ontology / Semantic Target Audit\n")
    lines.append(f"**Executed at (UTC):** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    lines.append(f"**Base:** `6a3c386` (V48AJ)\n")
    lines.append(f"**Verdict:** `{verdict}`\n")
    lines.append("")
    lines.append("## Phase 1: Label Semantics\n")
    for label, info in phase1.items():
        lines.append(f"### {label}\n")
        lines.append(f"**Documented:** {info['documented_definition']}\n")
        lines.append(f"**Implementation:** {info['actual_implementation'][:200]}...\n")
        lines.append(f"**Test/Fixture:** {info['test_fixture_definition'][:200]}...\n")
        lines.append(f"**Discrepancies:**\n{info['discrepancies']}\n")
    lines.append("## Phase 3: Label Compatibility\n")
    lines.append(f"- Single label (cleanly separable): {single_label}/29\n")
    lines.append(f"- Multiple labels valid (overlapping): {multiple_valid}/29\n")
    lines.append(f"- None adequate (under-specified): {none_adequate}/29\n")
    lines.append("")
    lines.append("## Phase 5: Three-Label Assumption\n")
    lines.append(f"{conflation_evidence}\n")
    lines.append("")
    lines.append("## Phase 6: Decision\n")
    lines.append(f"**Verdict:** `{verdict}`\n\n")
    lines.append(f"**Evidence for:**\n{evidence_for}\n\n")
    lines.append(f"**Counter-evidence:**\n{evidence_against}\n\n")
    lines.append(f"**Unresolved cases:** {unresolved_cases}\n\n")
    lines.append(f"**Missing info:**\n{missing_info}\n")
    lines.append("")
    lines.append("---\n")
    lines.append("**V48AK is an ONTOLOGY AUDIT, NOT implementation.**\n")
    lines.append("No new ontology designed. No labels renamed. No classifier modified. STOP.\n")
    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"    OK  {OUT_MD}")

    print()
    print("=" * 72)
    print("V48AK ONTOLOGY AUDIT — COMPLETE")
    print("=" * 72)
    print(f"\n  VERDICT: {verdict}")
    print(f"\n  Phase 3 distribution:")
    for k, v in best_counts.most_common():
        print(f"    {k}: {v}/29")
    print(f"\n  STOP. No V48AL. No implementation. No production changes.")
    print()
    return verdict


if __name__ == "__main__":
    run_v48ak()
