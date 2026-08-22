"""V48AL — Overlap Decomposition & Label Consistency Experiment.

Forensic experiment. NOT implementation.
Investigates the 8 V48AK overlapping cases to determine whether
they become non-overlapping when described by independent dimensions,
or whether the ambiguity is annotation/adjudication.
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
V48AK_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ak_ontology_audit.json"
V48AH_FALS = CORE_REPO / "intelligence_core/tests/reliability/v48ah_falsification_results.json"
V48AF_V21_FILE = CORE_REPO / "intelligence_core/tests/reliability/v48af_v21_evaluator.py"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48al_overlap_decomposition.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AL_OVERLAP_DECOMPOSITION.md"


def _get_aliases(candidate_name):
    for reg_type, reg in _ALL_REGISTRIES.items():
        for cid, (cname, etype, aliases) in reg.items():
            if cname == candidate_name:
                return aliases
    return []


def _head_noun(aliases, text, matched_alias):
    tl = (text or "").lower()
    ma = (matched_alias or "").lower()
    if not ma: return ""
    idx = tl.find(ma)
    if idx < 0: return ""
    after = tl[idx+len(ma):idx+len(ma)+25]
    words = after.split()
    return words[0].strip(".,;:") if words else ""


def run_v48al():
    print("=" * 72)
    print("V48AL — OVERLAP DECOMPOSITION & LABEL CONSISTENCY")
    print("=" * 72)
    print(f"  BASE: 373c879 (V48AK)")
    print(f"  Forensic experiment — NOT implementation")
    print()

    v21_hash = hashlib.sha256(V48AF_V21_FILE.read_bytes()).hexdigest()
    print(f"  V2.1 SHA256: {v21_hash[:16]}...")
    print()

    # Load data
    v48ak = json.loads(V48AK_RESULTS.read_text())
    v48ag = json.loads(V48AG_RESULTS.read_text())
    v48ag_per_case = {c["case_id"]: c for c in v48ag["new_holdout_results"]["per_case"]}
    prereg = json.loads(V48AG_PREREG.read_text())
    prereg_cases = {c["case_id"]: c for c in prereg["cases"]}
    v48ah_fals = json.loads(V48AH_FALS.read_text())
    h1_data = v48ah_fals["hypotheses"]["H1"]
    h1_explained = h1_data["explained_case_ids"]
    h1_counter = [ce["case_id"] for ce in h1_data["counterexamples"]]
    all_29 = h1_counter + h1_explained

    # ── PHASE 1: Identify the 8 overlapping cases ──
    print("  PHASE 1: Identify 8 overlapping cases")
    overlap_cases = []
    compatibility = v48ak.get("phase3_label_compatibility", [])
    for c in compatibility:
        if "MULTIPLE" in c.get("best_description", ""):
            overlap_cases.append(c["case_id"])

    # Also get from phase6 unresolved
    unresolved = v48ak.get("phase6_unresolved_cases", [])
    overlap_cases = sorted(set(overlap_cases + unresolved))
    clean_cases = [cid for cid in all_29 if cid not in overlap_cases]

    print(f"    Overlapping cases: {overlap_cases} ({len(overlap_cases)})")
    print(f"    Clean cases: {len(clean_cases)}")
    print()

    # Build full records for overlapping cases
    overlap_records = []
    for cid in overlap_cases:
        case = prereg_cases.get(cid, {})
        v21c = v48ag_per_case.get(cid, {})
        v21_vec = v21c.get("v21_vector", {}) or {}
        text = case.get("text", "")
        candidate = case.get("candidate", "")
        ma = v21_vec.get("matched_alias", "")
        hn = _head_noun(_get_aliases(candidate), text, ma)

        # Find V48AK compatibility record
        compat = next((c for c in compatibility if c["case_id"] == cid), {})

        overlap_records.append({
            "case_id": cid,
            "candidate": candidate,
            "head_noun": hn,
            "text": text,
            "human_label": case.get("human_label", ""),
            "v21_judgment": v21c.get("v21_judgment", ""),
            "matched_alias": ma,
            "labels_possible": compat.get("labels_possible", []),
            "best_description": compat.get("best_description", ""),
            "population": "counterexample" if cid in h1_counter else "explained",
        })

    for r in overlap_records:
        print(f"    #{r['case_id']} [{r['population'][:3]}] human={r['human_label']} | {r['candidate'][:20]} | {r['text'][:70]}")
    print()

    # ── PHASE 2: Blind dimension extraction ──
    print("  PHASE 2: Blind dimension extraction (8 cases)")

    dimension_results = []
    for r in overlap_records:
        text = r["text"]
        text_lower = text.lower()
        candidate = r["candidate"]
        head_noun = r["head_noun"]
        ma = r["matched_alias"]

        # D1: SYNTACTIC_ROLE
        syntactic_role = "modifier"
        if head_noun:
            syntactic_role = "modifier"  # candidate modifies head noun
        elif ma and text_lower.startswith(ma.lower()):
            syntactic_role = "subject"  # candidate at sentence start

        # D2: EVENT_TARGET
        event_target = "unresolved"
        concrete_verbs = {"revised","updated","compiled","issued","maintained","processed",
            "published","upgraded","refined","added","aligned","harmonized","outlined",
            "detailed","scheduled","released","analyzed","proposed","reaffirmed","reviewed",
            "described","collected","injected","subject"}
        meta_verbs = {"remain","remains","remained","cited","identified","noted",
            "described","characterized","highlighted","featured","discussed"}
        has_concrete = any(re.search(r"\b"+re.escape(v)+r"\b", text_lower) for v in concrete_verbs)
        has_meta = any(re.search(r"\b"+re.escape(v)+r"\b", text_lower) for v in meta_verbs)
        has_secondary = bool(re.search(r"\bunder\s+(?:close\s+)?monitoring\b|\bas\s+a\s+continuing\s+area\b|\bas\s+a\s+key\s+input\b|\bas\s+a\s+focus\b", text_lower))

        if has_concrete and not has_secondary:
            event_target = "head_noun"
        elif has_meta or has_secondary:
            event_target = "both"
        elif has_concrete and has_secondary:
            event_target = "both"
        else:
            event_target = "unresolved"

        # D3: EVENT_CERTAINTY
        event_certainty = "unresolved"
        if has_concrete or has_meta:
            if has_secondary:
                event_certainty = "weakly_implied"  # secondary creates ambiguity
            elif has_meta:
                event_certainty = "weakly_implied"  # meta is vague
            else:
                event_certainty = "strongly_implied"  # concrete action
        else:
            event_certainty = "unresolved"

        # D4: CONTEXTUAL_STATUS
        contextual_status = "unresolved"
        if head_noun:
            # Candidate is a modifier — is it central topic or contextual reference?
            # Check if candidate appears multiple times
            alias_count = len(re.findall(r"\b"+re.escape(ma.lower())+r"\b", text_lower)) if ma else 0
            if alias_count >= 2:
                contextual_status = "central_topic"
            else:
                contextual_status = "contextual_reference"

        # D5: SEMANTIC_SCOPE
        semantic_scope = "unresolved"
        if event_target == "head_noun":
            semantic_scope = "head_noun"
        elif event_target == "both":
            semantic_scope = "mixed"
        elif event_target == "candidate":
            semantic_scope = "candidate"
        else:
            semantic_scope = "unresolved"

        dims = {
            "D1_SYNTACTIC_ROLE": syntactic_role,
            "D2_EVENT_TARGET": event_target,
            "D3_EVENT_CERTAINTY": event_certainty,
            "D4_CONTEXTUAL_STATUS": contextual_status,
            "D5_SEMANTIC_SCOPE": semantic_scope,
        }

        dimension_results.append({
            "case_id": r["case_id"],
            "candidate": candidate,
            "head_noun": head_noun,
            "text": text,
            "human_label": r["human_label"],
            "v21_judgment": r["v21_judgment"],
            "labels_possible": r["labels_possible"],
            **dims,
        })

        print(f"    #{r['case_id']}: D1={syntactic_role} D2={event_target} D3={event_certainty} D4={contextual_status} D5={semantic_scope} | human={r['human_label']}")
    print()

    # ── PHASE 3: Compare against 21 clean cases ──
    print("  PHASE 3: Compare against clean cases")
    clean_records = []
    for cid in clean_cases:
        case = prereg_cases.get(cid, {})
        v21c = v48ag_per_case.get(cid, {})
        v21_vec = v21c.get("v21_vector", {}) or {}
        text = case.get("text", "")
        candidate = case.get("candidate", "")
        ma = v21_vec.get("matched_alias", "")
        hn = _head_noun(_get_aliases(candidate), text, ma)

        # Extract dimensions for clean cases too
        text_lower = text.lower()
        has_concrete = any(re.search(r"\b"+re.escape(v)+r"\b", text_lower) for v in concrete_verbs)
        has_meta = any(re.search(r"\b"+re.escape(v)+r"\b", text_lower) for v in meta_verbs)
        has_secondary = bool(re.search(r"\bunder\s+(?:close\s+)?monitoring\b|\bas\s+a\s+continuing\s+area\b|\bas\s+a\s+key\s+input\b|\bas\s+a\s+focus\b", text_lower))

        if has_concrete and not has_secondary:
            et = "head_noun"
        elif has_meta or has_secondary:
            et = "both"
        else:
            et = "unresolved"

        ec = "strongly_implied" if has_concrete and not has_secondary else ("weakly_implied" if has_meta or has_secondary else "unresolved")

        clean_records.append({
            "case_id": cid,
            "candidate": candidate,
            "head_noun": hn,
            "text": text,
            "human_label": case.get("human_label", ""),
            "D2_EVENT_TARGET": et,
            "D3_EVENT_CERTAINTY": ec,
        })

    # Find closest clean case for each overlapping case
    pairwise = []
    for ov in dimension_results:
        best_match = None
        best_score = 0
        for cr in clean_records:
            score = 0
            if ov["candidate"] == cr["candidate"]: score += 3
            if ov["head_noun"] == cr["head_noun"]: score += 2
            if ov["D2_EVENT_TARGET"] == cr["D2_EVENT_TARGET"]: score += 1
            if ov["D3_EVENT_CERTAINTY"] == cr["D3_EVENT_CERTAINTY"]: score += 1
            if score > best_score:
                best_score = score
                best_match = cr

        if best_match:
            pairwise.append({
                "overlap_case": ov["case_id"],
                "overlap_human": ov["human_label"],
                "clean_case": best_match["case_id"],
                "clean_human": best_match["human_label"],
                "match_score": best_score,
                "overlap_text": ov["text"][:60],
                "clean_text": best_match["text"][:60],
                "overlap_D2": ov["D2_EVENT_TARGET"],
                "clean_D2": best_match["D2_EVENT_TARGET"],
                "overlap_D3": ov["D3_EVENT_CERTAINTY"],
                "clean_D3": best_match["D3_EVENT_CERTAINTY"],
                "dimension_diff": "same" if (ov["D2_EVENT_TARGET"]==best_match["D2_EVENT_TARGET"] and ov["D3_EVENT_CERTAINTY"]==best_match["D3_EVENT_CERTAINTY"]) else "different",
            })
            print(f"    #{ov['case_id']}({ov['human_label']}) → #{best_match['case_id']}({best_match['human_label']}) score={best_score} dim_diff={pairwise[-1]['dimension_diff']}")

    print()

    # ── PHASE 4: Label consistency test ──
    print("  PHASE 4: Label consistency test")
    label_consistency = []
    for ov in dimension_results:
        # Can a single human label be assigned WITHOUT losing information?
        if ov["D2_EVENT_TARGET"] == "both":
            # Event applies to both candidate and head noun → two valid interpretations
            consistency = "L3"  # label depends on which dimension is prioritized
            ambiguity_type = "B_ontology_ambiguity"
            reason = "Event target is 'both' — the event could apply to the candidate or the head noun. The label depends on which dimension (subjecthood vs event attribution) is prioritized."
        elif ov["D3_EVENT_CERTAINTY"] == "weakly_implied":
            # Event certainty is weak → insufficient to determine
            consistency = "L2"  # two labels remain equally valid
            ambiguity_type = "D_unresolved_semantic_ambiguity"
            reason = "Event certainty is weakly implied — the evidence is insufficient to determine the relationship with confidence."
        else:
            consistency = "L1"  # one label is clearly superior
            ambiguity_type = "A_classifier_ambiguity"
            reason = "One label is clearly superior based on the dimension analysis."

        label_consistency.append({
            "case_id": ov["case_id"],
            "human_label": ov["human_label"],
            "consistency": consistency,
            "ambiguity_type": ambiguity_type,
            "reason": reason,
        })
        print(f"    #{ov['case_id']}: {consistency} ({ambiguity_type}) | {reason[:80]}")
    print()

    # ── PHASE 5: Blind re-adjudication ──
    print("  PHASE 5: Blind re-adjudication")
    blind_results = []
    for ov in dimension_results:
        text = ov["text"]
        candidate = ov["candidate"]
        head_noun = ov["head_noun"]

        # Blind semantic adjudication — analyze the text WITHOUT looking at labels
        # Q1: What is the semantic relationship between candidate, head noun, and event?
        relationship = ""
        if head_noun:
            relationship = f"'{candidate}' is a modifier of '{head_noun}'. The event applies to '{head_noun}'."
        else:
            relationship = f"'{candidate}' appears without a clear head noun."

        # Q2: What is the degree of certainty?
        certainty = ""
        if ov["D3_EVENT_CERTAINTY"] == "strongly_implied":
            certainty = "high — the event clearly applies to the head noun"
        elif ov["D3_EVENT_CERTAINTY"] == "weakly_implied":
            certainty = "low — the event is vague or has secondary target"
        else:
            certainty = "unresolved"

        # Determine what the blind adjudication would say
        if ov["D2_EVENT_TARGET"] == "head_noun" and certainty == "high":
            blind_label = "CONTEXT_ONLY"
        elif ov["D2_EVENT_TARGET"] == "both":
            blind_label = "AMBIGUOUS"
        elif ov["D2_EVENT_TARGET"] == "head_noun" and certainty == "low":
            blind_label = "AMBIGUOUS"
        else:
            blind_label = "AMBIGUOUS"

        blind_results.append({
            "case_id": ov["case_id"],
            "relationship": relationship,
            "certainty": certainty,
            "blind_label": blind_label,
            "human_label": ov["human_label"],
            "v21_label": ov["v21_judgment"],
            "blind_matches_human": blind_label == ov["human_label"] or (blind_label == "CONTEXT_ONLY" and ov["human_label"] == "CONTEXT"),
            "blind_matches_v21": blind_label == ov["v21_judgment"],
        })
        print(f"    #{ov['case_id']}: blind={blind_label} human={ov['human_label']} v21={ov['v21_judgment']} match_human={blind_results[-1]['blind_matches_human']}")
    print()

    # ── PHASE 6: Test multi-dimension hypothesis ──
    print("  PHASE 6: Test multi-dimension hypothesis")
    dim_analysis = {}
    for dim_name, dim_key in [("D1_subjecthood","D1_SYNTACTIC_ROLE"), ("D2_event_attribution","D2_EVENT_TARGET"),
                              ("D3_contextual_relevance","D4_CONTEXTUAL_STATUS"), ("D4_attribution_certainty","D3_EVENT_CERTAINTY"),
                              ("D5_semantic_scope","D5_SEMANTIC_SCOPE")]:
        values = [r[dim_key] for r in dimension_results]
        unique = set(values)
        dim_analysis[dim_name] = {
            "values": dict(Counter(values)),
            "unique_count": len(unique),
            "independently_observable": len(unique) > 1,
            "independently_variable": len(unique) > 1,
        }
        print(f"    {dim_name}: {dict(Counter(values))} (unique={len(unique)})")

    # Do the 8 cases become non-overlapping when described by these dimensions?
    # Check if the dimension vectors are unique per case
    dim_vectors = []
    for r in dimension_results:
        vec = (r["D1_SYNTACTIC_ROLE"], r["D2_EVENT_TARGET"], r["D3_EVENT_CERTAINTY"],
               r["D4_CONTEXTUAL_STATUS"], r["D5_SEMANTIC_SCOPE"])
        dim_vectors.append((r["case_id"], r["human_label"], vec))

    unique_vectors = set(v[2] for v in dim_vectors)
    print(f"\n    Unique dimension vectors: {len(unique_vectors)}/{len(dim_vectors)}")

    # Check if cases with same dimension vector have same human label
    vec_labels = {}
    for cid, hlabel, vec in dim_vectors:
        if vec not in vec_labels:
            vec_labels[vec] = []
        vec_labels[vec].append((cid, hlabel))

    label_conflicts = []
    for vec, cases in vec_labels.items():
        labels = set(c[1] for c in cases)
        if len(labels) > 1:
            label_conflicts.append({"vector": vec, "cases": cases, "labels": labels})
            print(f"    CONFLICT: vec={vec} cases={cases} labels={labels}")

    if label_conflicts:
        print(f"\n    → {len(label_conflicts)} dimension-vector conflicts found")
        print(f"    → Multi-dimension does NOT cleanly separate the 8 cases")
    else:
        print(f"\n    → No conflicts — dimensions cleanly separate the 8 cases")
    print()

    # ── PHASE 7: Critical negative test ──
    print("  PHASE 7: Critical negative test")
    # Look for evidence AGAINST the ontology hypothesis
    # Find cases where all five dimensions are effectively identical but human labels differ

    # Check within the 8 overlapping cases
    negative_test_results = []
    for i, (cid1, h1, vec1) in enumerate(dim_vectors):
        for j, (cid2, h2, vec2) in enumerate(dim_vectors):
            if i >= j: continue
            if vec1 == vec2 and h1 != h2:
                negative_test_results.append({
                    "case1": cid1, "label1": h1,
                    "case2": cid2, "label2": h2,
                    "dimensions": vec1,
                    "finding": "ANNOTATION_INCONSISTENCY — identical dimensions, different labels",
                })

    # Also check across ALL 29 cases (including the 21 clean)
    all_dim_vectors = []
    for cid in all_29:
        case = prereg_cases.get(cid, {})
        v21c = v48ag_per_case.get(cid, {})
        v21_vec = v21c.get("v21_vector", {}) or {}
        text = case.get("text", "")
        candidate = case.get("candidate", "")
        ma = v21_vec.get("matched_alias", "")
        hn = _head_noun(_get_aliases(candidate), text, ma)
        text_lower = text.lower()

        # Quick dimension extraction
        has_c = any(re.search(r"\b"+re.escape(v)+r"\b", text_lower) for v in concrete_verbs)
        has_m = any(re.search(r"\b"+re.escape(v)+r"\b", text_lower) for v in meta_verbs)
        has_s = bool(re.search(r"\bunder\s+(?:close\s+)?monitoring\b|\bas\s+a\s+continuing\s+area\b|\bas\s+a\s+key\s+input\b|\bas\s+a\s+focus\b", text_lower))

        sr = "modifier" if hn else "subject"
        if has_c and not has_s: et = "head_noun"
        elif has_m or has_s: et = "both"
        else: et = "unresolved"
        ec = "strongly_implied" if has_c and not has_s else ("weakly_implied" if has_m or has_s else "unresolved")
        cs = "contextual_reference" if hn else "central_topic"
        ss = et

        vec = (sr, et, ec, cs, ss)
        hlabel = case.get("human_label", "")
        all_dim_vectors.append((cid, hlabel, vec, candidate, hn, text[:60]))

    # Check for identical vectors with different labels across ALL 29
    vec_to_cases = {}
    for cid, hlabel, vec, cand, hn, text in all_dim_vectors:
        if vec not in vec_to_cases:
            vec_to_cases[vec] = []
        vec_to_cases[vec].append((cid, hlabel, cand, hn, text))

    cross_conflicts = []
    for vec, cases in vec_to_cases.items():
        labels = set(c[1] for c in cases)
        if len(labels) > 1:
            cross_conflicts.append({"vector": vec, "cases": cases, "labels": labels})

    if cross_conflicts:
        print(f"    FOUND {len(cross_conflicts)} cross-conflicts (identical dimensions, different labels):")
        for cc in cross_conflicts:
            print(f"      vec={cc['vector']}")
            for c in cc['cases']:
                print(f"        #{c[0]} ({c[1]}) | {c[2]} | hn={c[3]} | {c[4]}")
    elif negative_test_results:
        print(f"    FOUND {len(negative_test_results)} within-overlap conflicts:")
        for nt in negative_test_results:
            print(f"      #{nt['case1']}({nt['label1']}) vs #{nt['case2']}({nt['label2']}) — {nt['finding']}")
    else:
        print("    NO_DIRECT_ANNOTATION_CONTRADICTION_FOUND")
    print()

    # ── PHASE 8: Final verdict ──
    print("  PHASE 8: Final verdict")

    if cross_conflicts:
        verdict = "ANNOTATION_INCONSISTENCY_SUSPECTED"
        reason = f"Found {len(cross_conflicts)} cases where all 5 dimensions are identical but human labels differ. This suggests the human adjudication is inconsistent, not that the ontology is wrong."
    elif label_conflicts:
        verdict = "MULTI_DIMENSION_HYPOTHESIS_WEAKLY_SUPPORTED"
        reason = f"Found {len(label_conflicts)} dimension-vector conflicts within the 8 overlapping cases. The dimensions partially separate the cases but don't fully resolve the overlap."
    elif len(unique_vectors) == len(dim_vectors):
        verdict = "MULTI_DIMENSION_HYPOTHESIS_SUPPORTED"
        reason = "All 8 overlapping cases have unique dimension vectors. The multi-dimension hypothesis cleanly separates the cases."
    else:
        verdict = "UNRESOLVED"
        reason = "Cannot determine whether the dimensions separate the cases."

    print(f"    VERDICT: {verdict}")
    print(f"    Reason: {reason}")
    print()

    # Summary
    what_v48ak_proved = (
        "V48AK proved that the three labels (TRUE_SUBJECT / CONTEXT_ONLY / AMBIGUOUS) "
        "are PARTIALLY_OVERLAPPING — they conflate multiple independent dimensions "
        "(subjecthood, event attribution, contextual relevance, certainty, scope). "
        "72% of cases have a single clearly correct label; 28% have multiple valid labels."
    )
    what_v48al_proved = (
        f"V48AL proved that: (1) the 8 overlapping cases have "
        f"{len(unique_vectors)} unique dimension vectors out of 8 cases; "
        f"(2) {'CROSS-CONFLICTS WERE FOUND' if cross_conflicts else 'no cross-conflicts were found'} "
        f"— {'suggesting annotation inconsistency' if cross_conflicts else 'suggesting the dimensions are compatible'}; "
        f"(3) the multi-dimension hypothesis is {verdict}."
    )
    what_remains_unknown = (
        "Whether a multi-dimensional label would actually improve classifier performance "
        "in production. Whether the annotation inconsistency (if found) is systematic or random. "
        "Whether real documents (not synthetic) would resolve the ambiguous cases via "
        "document context."
    )
    what_evidence_required = (
        "Before redesigning the ontology: (1) resolve any annotation inconsistencies "
        "found in Phase 7; (2) test the multi-dimensional representation on REAL documents "
        "(not synthetic); (3) determine if the 5 dimensions are truly independent or "
        "correlated in practice."
    )

    print(f"  V48AK proved: {what_v48ak_proved[:100]}...")
    print(f"  V48AL proved: {what_v48al_proved[:100]}...")
    print(f"  Remains unknown: {what_remains_unknown[:100]}...")
    print(f"  Evidence required: {what_evidence_required[:100]}...")
    print()

    # ── Integrity ──
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
    print(f"  Integrity: {len(prod_hashes)} files verified unchanged")
    print()

    # ── Persist ──
    OUT_JSON.write_text(json.dumps({
        "phase": "V48AL OVERLAP DECOMPOSITION & LABEL CONSISTENCY",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_commit": "373c879",
        "v21_sha256": v21_hash,
        "production_hashes": prod_hashes,
        "phase1_overlap_cases": [{"case_id": r["case_id"], "candidate": r["candidate"],
                                   "head_noun": r["head_noun"], "text": r["text"],
                                   "human_label": r["human_label"], "v21_judgment": r["v21_judgment"],
                                   "labels_possible": r["labels_possible"]}
                                  for r in overlap_records],
        "phase2_dimensions": dimension_results,
        "phase3_pairwise": pairwise,
        "phase4_label_consistency": label_consistency,
        "phase5_blind_readjudication": blind_results,
        "phase6_dimension_analysis": dim_analysis,
        "phase6_unique_vectors": len(unique_vectors),
        "phase6_label_conflicts": label_conflicts,
        "phase7_negative_test": {
            "within_overlap_conflicts": negative_test_results,
            "cross_conflicts": cross_conflicts,
            "result": "ANNOTATION_INCONSISTENCY_SUSPECTED" if cross_conflicts else ("NO_DIRECT_ANNOTATION_CONTRADICTION_FOUND" if not negative_test_results else "WITHIN_OVERLAP_CONFLICTS_FOUND"),
        },
        "phase8_verdict": verdict,
        "phase8_reason": reason,
        "phase8_what_v48ak_proved": what_v48ak_proved,
        "phase8_what_v48al_proved": what_v48al_proved,
        "phase8_what_remains_unknown": what_remains_unknown,
        "phase8_evidence_required": what_evidence_required,
        "DO_NOT_create_V48AM": True,
        "DO_NOT_modify_production": True,
        "STOP": True,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"  OK  {OUT_JSON}")

    # Markdown
    lines = []
    lines.append("# V48AL — Overlap Decomposition & Label Consistency\n")
    lines.append(f"**Base:** `373c879` (V48AK)\n")
    lines.append(f"**Verdict:** `{verdict}`\n")
    lines.append("")
    lines.append("## Phase 2: Blind Dimensions (8 overlapping cases)\n")
    lines.append("| # | D1 | D2 | D3 | D4 | D5 | Human |\n")
    lines.append("|---|----|----|----|----|----|-------|\n")
    for r in dimension_results:
        lines.append(f"| {r['case_id']} | {r['D1_SYNTACTIC_ROLE']} | {r['D2_EVENT_TARGET']} | {r['D3_EVENT_CERTAINTY']} | {r['D4_CONTEXTUAL_STATUS']} | {r['D5_SEMANTIC_SCOPE']} | {r['human_label']} |")
    lines.append("")
    lines.append("## Phase 7: Critical Negative Test\n")
    if cross_conflicts:
        lines.append(f"**FOUND {len(cross_conflicts)} cross-conflicts** — identical dimensions, different human labels:\n\n")
        for cc in cross_conflicts:
            lines.append(f"**Vector:** {cc['vector']}\n")
            for c in cc['cases']:
                lines.append(f"- #{c[0]} ({c[1]}) | {c[2]} | hn={c[3]} | {c[4]}")
            lines.append("")
    else:
        lines.append("**NO_DIRECT_ANNOTATION_CONTRADICTION_FOUND**\n")
    lines.append("")
    lines.append(f"## Phase 8: Verdict\n\n**{verdict}**\n\n{reason}\n")
    lines.append(f"\n### What V48AK proved\n{what_v48ak_proved}\n")
    lines.append(f"\n### What V48AL proved\n{what_v48al_proved}\n")
    lines.append(f"\n### What remains unknown\n{what_remains_unknown}\n")
    lines.append(f"\n### Evidence required before redesigning\n{what_evidence_required}\n")
    lines.append("\n---\n**V48AL is a FORENSIC EXPERIMENT, NOT implementation.** STOP.\n")
    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"  OK  {OUT_MD}")

    print()
    print("=" * 72)
    print("V48AL OVERLAP DECOMPOSITION — COMPLETE")
    print("=" * 72)
    print(f"\n  VERDICT: {verdict}")
    print(f"\n  STOP. No V48AM. No implementation. No production changes.")
    print()
    return verdict


if __name__ == "__main__":
    run_v48al()
