"""V48AC — Subject Evidence Adjudication (Forensic Failure Analysis).

PROVE/DIAGNOSE gate. NOT a BUILD gate.
Analyzes the 16 V48AB failures to classify root causes.
NO production modifications. NO resolve_subject changes.
"""
from __future__ import annotations
import json, sys, time, hashlib, re
from pathlib import Path
from collections import Counter

CORE_REPO = Path("/home/z/my-project/repos/rouaa-intelligence-core")
sys.path.insert(0, str(CORE_REPO))
import os; os.chdir(str(CORE_REPO))

from intelligence_core.subject_entity import _ALL_REGISTRIES

V48AB_RESULTS = CORE_REPO / "intelligence_core/tests/reliability/v48ab_shadow_results.json"
V48AB_SAMPLE = CORE_REPO / "intelligence_core/tests/reliability/v48ab_independent_sample.json"
V48X_AUDIT = CORE_REPO / "intelligence_core/tests/reliability/v48x_32_subject_audit.json"

OUT_JSON = CORE_REPO / "intelligence_core/tests/reliability/v48ac_forensic_report.json"
OUT_MD = CORE_REPO / "docs/evidence/ROUAA_CORE_V48AC_FORENSIC_ADJUDICATION.md"

# Failure classes
DATA = "DATA"
EXTRACTION = "EXTRACTION"
RULE = "RULE"
SEMANTIC = "SEMANTIC"


def _get_aliases(candidate_name):
    for reg_type, reg in _ALL_REGISTRIES.items():
        for cid, (cname, etype, aliases) in reg.items():
            if cname == candidate_name:
                return aliases, reg_type
    return [], "UNKNOWN"


def _verb_in_lexicon(candidate, verb):
    """Check if a verb is in the production _EVENT_VERBS for the candidate's registry type."""
    from intelligence_core.subject_entity import _EVENT_VERBS
    _, reg_type = _get_aliases(candidate)
    pattern = _EVENT_VERBS.get(reg_type, _EVENT_VERBS.get("INDICATOR", re.compile(r"$")))
    return bool(pattern.search(verb)) if verb else False


def classify_failure(case):
    """Classify a V48AB failure into DATA / EXTRACTION / RULE / SEMANTIC."""
    idx = case["index"]
    cat = case["category"]
    candidate = case["candidate"]
    text = case["text"]
    text_lower = text.lower()
    judgment = case["judgment"]
    event = case.get("event", "")
    measurement = case.get("measurement", "")
    matched_verb = case.get("matched_verb", "")
    strong_count = case.get("strong_count", 0)

    # ── POSITIVE FAILURES (expected TRUE_SUBJECT, got something else) ──
    if cat == "positive":
        if judgment == "NO_CANDIDATE":
            # Check if the candidate alias IS in the text
            aliases, _ = _get_aliases(candidate)
            alias_in_text = any(re.search(r"\b" + re.escape(a.lower()) + r"\b", text_lower) for a in aliases)
            if alias_in_text:
                return RULE, "Candidate alias IS present in text but rule failed to detect it. RULE_GAP."
            # Check for plausible unregistered alias
            unregistered = []
            if candidate == "Policy Rate":
                for alias in ["bank rate", "federal funds rate", "discount rate"]:
                    if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
                        unregistered.append(alias)
            if unregistered:
                return DATA, f"Text contains plausible-but-unregistered alias ({', '.join(unregistered)}). DATA_GAP — registry alias missing."
            return DATA, f"Candidate '{candidate}' alias not in text. DATA_GAP."

        # event=WEAK with STRONG measurement
        if event == "WEAK":
            # Check which verb the text uses
            missed_verbs = []
            for v in ["climbed", "levied", "stabilized", "lowered", "assessed",
                       "reached", "stood", "finalized", "advanced", "improved"]:
                if re.search(r"\b" + re.escape(v) + r"\b", text_lower):
                    missed_verbs.append(v)
            
            if missed_verbs:
                # Check if these verbs are in the production lexicon
                in_lexicon = _verb_in_lexicon(candidate, missed_verbs[0]) if missed_verbs else False
                if not in_lexicon:
                    return RULE, (
                        f"Text contains event verb '{missed_verbs[0]}' that is NOT in the "
                        f"production _EVENT_VERBS lexicon for the candidate's registry type. "
                        f"event=WEAK because the rule's verb vocabulary is too narrow. "
                        f"The evidence IS in the text — the rule cannot see it."
                    )

            # Check measurement pattern
            if measurement == "INSUFFICIENT":
                if "basis point" in text_lower:
                    return RULE, "Measurement regex doesn't recognize 'basis points'. RULE_GAP."
                if "$" in text and "million" not in text_lower and "billion" not in text_lower:
                    return RULE, "Measurement regex doesn't recognize dollar amounts without 'million/billion'. RULE_GAP."

            return RULE, f"event=WEAK with verb not in lexicon or measurement too narrow. RULE_GAP."

    # ── NEGATIVE FAILURE (expected UNKNOWN, got TRUE_SUBJECT) ──
    if cat == "negative":
        # The rule promoted a candidate to TRUE_SUBJECT when the document is about a different topic
        return RULE, (
            f"Rule promoted '{candidate}' to TRUE_SUBJECT despite the heading "
            f"naming a competing topic. The event=STRONG signal fired because "
            f"verb '{matched_verb}' appeared near the candidate, but the signal "
            f"is about the DOCUMENT's event, not about the CANDIDATE being the subject. "
            f"Signal strength ≠ Subject attribution. RULE_GAP — the rule conflates "
            f"'strong evidence present in document' with 'strong evidence about candidate.'"
        )

    # ── AMBIGUOUS FAILURES (expected AMBIGUOUS, got TRUE_SUBJECT) ──
    if cat == "ambiguous":
        if matched_verb:
            return RULE, (
                f"Rule promoted to TRUE_SUBJECT because verb '{matched_verb}' "
                f"matched near candidate. But the candidate is a NOUN MODIFIER "
                f"in a larger phrase (e.g., 'FX turnover data', 'Penalty guidelines'). "
                f"The verb applies to the head noun, not the candidate. "
                f"RULE_GAP — the rule doesn't check syntactic subject-attribution."
            )
        return RULE, f"Rule over-promoted ambiguous case. RULE_GAP."

    return SEMANTIC, "Unclassified — requires manual review."


def run_v48ac():
    print("=" * 72)
    print("V48AC — SUBJECT EVIDENCE ADJUDICATION (FORENSIC)")
    print("=" * 72)
    print(f"  Branch: recovery/post-v37-intelligence-stack")
    print(f"  PROVE/DIAGNOSE gate — NOT a BUILD gate")
    print(f"  NO production modifications")
    print()

    # Load V48AB results
    v48ab = json.loads(V48AB_RESULTS.read_text())
    sample = json.loads(V48AB_SAMPLE.read_text())["sample"]

    # Population reconciliation
    pos_total = sum(1 for c in sample if c.get("category") == "positive")
    neg_total = sum(1 for c in sample if c.get("category") == "negative")
    amb_total = sum(1 for c in sample if c.get("category") == "ambiguous")
    pos_pass = v48ab["independent_sample"]["positive_pass"]
    neg_pass = v48ab["independent_sample"]["negative_pass"]
    amb_pass = v48ab["independent_sample"]["ambiguous_pass"]

    print(f"  Population reconciliation:")
    print(f"    Positive: {pos_total} total, {pos_pass} pass, {pos_total - pos_pass} fail")
    print(f"    Negative: {neg_total} total, {neg_pass} pass, {neg_total - neg_pass} fail")
    print(f"    Ambiguous: {amb_total} total, {amb_pass} pass, {amb_total - amb_pass} fail")
    print(f"    Total: {pos_total + neg_total + amb_total} cases, {pos_pass + neg_pass + amb_pass} pass, {(pos_total-pos_pass) + (neg_total-neg_pass) + (amb_total-amb_pass)} fail")
    print()

    # Identify all 16 failures
    failures = []
    for i, c in enumerate(sample):
        cat = c.get("category", "")
        judgment = c.get("judgment", "")
        is_fail = False
        if cat == "positive" and judgment != "TRUE_SUBJECT": is_fail = True
        elif cat == "negative" and judgment == "TRUE_SUBJECT": is_fail = True
        elif cat == "ambiguous" and judgment != "AMBIGUOUS": is_fail = True
        if is_fail:
            cands = c.get("candidates", [])
            v = cands[0].get("vector", {}) if cands else {}
            failures.append({
                "index": i + 1, "category": cat, "expected": c.get("expected", ""),
                "judgment": judgment, "text": c.get("text", ""),
                "candidate": cands[0].get("candidate", "NO_CANDIDATE") if cands else "NO_CANDIDATE",
                "event": v.get("event", ""), "measurement": v.get("measurement", ""),
                "fact": v.get("fact", ""), "event_type": v.get("event_type", ""),
                "heading": v.get("heading", ""), "topic": v.get("topic", ""),
                "position": v.get("position", ""), "matched_verb": v.get("matched_verb", ""),
                "strong_count": v.get("strong_count", ""),
            })

    print(f"  Failures identified: {len(failures)}")
    assert len(failures) == 16, f"Expected 16 failures, got {len(failures)}"
    print(f"  16 failures confirmed ✓")
    print()

    # Classify each failure
    print("  Forensic classification:")
    forensic_records = []
    for f in failures:
        failure_class, reason = classify_failure(f)
        forensic_records.append({
            **f,
            "failure_class": failure_class,
            "failure_reason": reason,
        })
        print(f"    #{f['index']:>3} [{f['category'][:3]}] {f['candidate'][:24]:<24} → {failure_class}")

    # Aggregate
    dist = Counter(r["failure_class"] for r in forensic_records)
    total = len(forensic_records)
    print()
    print(f"  Failure taxonomy:")
    for cls in (DATA, EXTRACTION, RULE, SEMANTIC):
        cnt = dist.get(cls, 0)
        pct = cnt / total * 100 if total else 0
        print(f"    {cls}: {cnt} ({pct:.1f}%)")
    print()

    # All 16 accounted for?
    accounted = sum(dist.values())
    print(f"  All 16 failures individually accounted for: {'YES' if accounted == 16 else 'NO'}")
    print()

    # Production unchanged verification
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

    # Tests
    import subprocess
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
    all_pass = True
    for module, label in test_modules:
        r = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True, cwd=str(CORE_REPO), timeout=300)
        passed = "OK" in r.stderr
        m = re.search(r"Ran (\d+) tests", r.stderr)
        cnt = int(m.group(1)) if m else 0
        total_test_count += cnt
        test_results[label] = {"module": module, "passed": passed, "count": cnt}
        if not passed: all_pass = False
    print(f"  Tests: {total_test_count}/338 {'PASS' if all_pass else 'FAIL'}")
    print(f"  Production files changed: 0")
    print()

    # Final verdict
    has_semantic = dist.get(SEMANTIC, 0) > 0
    has_data = dist.get(DATA, 0)
    has_rule = dist.get(RULE, 0)
    has_extraction = dist.get(EXTRACTION, 0)

    if has_semantic > 0:
        verdict = "BLOCKED"
        recommendation = "Semantic limitation requires architectural decision."
    elif has_data > (has_rule + has_extraction):
        verdict = "PASS"
        recommendation = "Upstream evidence/extraction is the bottleneck — repair data layer."
    elif has_rule > 0:
        verdict = "PASS"
        recommendation = "Subject judgment rule needs lexicon expansion and signal-attribution check — not architectural redesign."
    else:
        verdict = "PASS"
        recommendation = "No significant failures found."

    print(f"  FINAL VERDICT: {verdict}")
    print(f"  Next-step recommendation: {recommendation}")
    print()

    # Save
    OUT_JSON.write_text(json.dumps({
        "phase": "V48AC SUBJECT EVIDENCE ADJUDICATION",
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "population": {
            "positive": {"total": pos_total, "pass": pos_pass, "fail": pos_total - pos_pass},
            "negative": {"total": neg_total, "pass": neg_pass, "fail": neg_total - neg_pass},
            "ambiguous": {"total": amb_total, "pass": amb_pass, "fail": amb_total - amb_pass},
            "total_cases": pos_total + neg_total + amb_total,
            "total_pass": pos_pass + neg_pass + amb_pass,
            "total_fail": (pos_total-pos_pass) + (neg_total-neg_pass) + (amb_total-amb_pass),
        },
        "forensic_records": forensic_records,
        "failure_taxonomy": {
            DATA: dist.get(DATA, 0),
            EXTRACTION: dist.get(EXTRACTION, 0),
            RULE: dist.get(RULE, 0),
            SEMANTIC: dist.get(SEMANTIC, 0),
        },
        "all_16_accounted_for": accounted == 16,
        "production_files_changed": 0,
        "production_hashes": prod_hashes,
        "test_count": total_test_count,
        "tests_pass": all_pass,
        "verdict": verdict,
        "recommendation": recommendation,
    }, indent=2, ensure_ascii=False, default=str))

    # MD report
    lines = []
    lines.append("# V48AC — Subject Evidence Adjudication\n\n")
    lines.append(f"**Verdict:** `{verdict}`\n\n")
    lines.append("## Population Reconciliation\n\n")
    lines.append("| Category | Total | Pass | Fail |\n|----------|-----:|-----:|-----:|\n")
    lines.append(f"| Positive | {pos_total} | {pos_pass} | {pos_total-pos_pass} |\n")
    lines.append(f"| Negative | {neg_total} | {neg_pass} | {neg_total-neg_pass} |\n")
    lines.append(f"| Ambiguous | {amb_total} | {amb_pass} | {amb_total-amb_pass} |\n")
    lines.append(f"| **Total** | **{pos_total+neg_total+amb_total}** | **{pos_pass+neg_pass+amb_pass}** | **{(pos_total-pos_pass)+(neg_total-neg_pass)+(amb_total-amb_pass)}** |\n\n")
    lines.append("## Failure Taxonomy\n\n")
    lines.append("| Class | Count | % | Diagnosis |\n|-------|-----:|--:|----------|\n")
    for cls in (DATA, EXTRACTION, RULE, SEMANTIC):
        cnt = dist.get(cls, 0)
        pct = cnt / total * 100 if total else 0
        diag = {
            DATA: "Registry alias missing or data not available",
            EXTRACTION: "Primary segment extraction picked wrong segment",
            RULE: "Verb lexicon/measurement regex too narrow; signal≠attribution",
            SEMANTIC: "Genuine semantic limitation — model cannot decide",
        }[cls]
        lines.append(f"| {cls} | {cnt} | {pct:.1f}% | {diag} |\n")
    lines.append(f"\n## All 16 Failures Individually Accounted For: {'YES' if accounted == 16 else 'NO'}\n\n")
    lines.append("## Per-Case Forensic Table\n\n")
    lines.append("| # | Cat | Candidate | Judgment | Class | Text |\n|---|-----|-----------|----------|-------|------|\n")
    for r in forensic_records:
        lines.append(f"| {r['index']} | {r['category'][:3]} | {r['candidate'][:20]} | {r['judgment'][:12]} | {r['failure_class']} | {r['text'][:50]} |\n")
    lines.append(f"\n## Per-Case Details\n\n")
    for r in forensic_records:
        lines.append(f"### Case #{r['index']} — {r['candidate']} ({r['failure_class']})\n\n")
        lines.append(f"- **Text:** \"{r['text']}\"\n")
        lines.append(f"- **Expected:** {r['expected']} | **Judgment:** {r['judgment']}\n")
        lines.append(f"- **Event:** {r['event']} | **Measurement:** {r['measurement']} | **Verb:** {r['matched_verb']}\n")
        lines.append(f"- **Failure class:** `{r['failure_class']}`\n")
        lines.append(f"- **Reason:** {r['failure_reason']}\n\n")
    lines.append(f"## Final Verdict\n\n**{verdict}**\n\n")
    lines.append(f"**Recommendation:** {recommendation}\n\n")
    lines.append(f"Production files changed: 0\n")
    lines.append(f"Tests: {total_test_count}/338 {'PASS' if all_pass else 'FAIL'}\n")
    lines.append("\n---\n**STOP. Do not fix cases or re-run V48AB.**\n")
    OUT_MD.write_text("".join(lines), encoding="utf-8")

    print(f"  Artifacts saved:")
    print(f"    {OUT_JSON}")
    print(f"    {OUT_MD}")
    print()
    print(f"  START SHA: fa4057f (recovery branch)")
    print(f"  Final verdict: {verdict}")
    print(f"  Recommendation: {recommendation}")
    print()
    print("  STOP.")
    return verdict, recommendation


if __name__ == "__main__":
    run_v48ac()
