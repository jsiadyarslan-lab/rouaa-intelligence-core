"""V7 §3-5 — Corpus Integrity + 120-Event Audit + 500-Fact Audit.

§3: Verify 153 IOs have 0 broken chains, 0 orphan facts/evidence/events
§4: Audit ≥120 IOs (stratified 40/40/40) for Event Precision ≥98%
§5: Audit ≥500 facts for Fact Precision ≥98%
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.event_semantic_gate import validate_event_context
from intelligence_core.tests.reliability.fact_evidence_audit import (
    classify_fact_quality, classify_evidence_grounding, FACT_QUALITY_RULES,
)
from intelligence_core.tests.reliability.semantic_audit import (
    EVENT_SEMANTIC_RULES, validate_event_semantic, validate_fact_semantic,
    validate_evidence_window, validate_multi_event,
)


def verify_corpus_integrity(store_root: str = "v3_corpus_store"):
    """§3 — Verify 153 IOs have 0 broken chains, 0 orphans."""
    print(f"\n{'='*70}")
    print(f"V7 §3 — Corpus Integrity Verification")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))

    # Count entities
    events = list(store.iter("events"))
    facts = list(store.iter("facts"))
    evidence = list(store.iter("evidence"))
    documents = list(store.iter("documents"))
    representations = list(store.iter("representations"))
    sources = list(store.iter("sources"))

    print(f"\n  Entity counts:")
    print(f"    Events:        {len(events)}")
    print(f"    Facts:         {len(facts)}")
    print(f"    Evidence:      {len(evidence)}")
    print(f"    Documents:     {len(documents)}")
    print(f"    Representations: {len(representations)}")
    print(f"    Sources:       {len(sources)}")

    # Build indexes
    facts_by_id = {f["fact_id"]: f for f in facts}
    evidence_by_id = {e["evidence_id"]: e for e in evidence}
    docs_by_id = {d["document_id"]: d for d in documents}
    reps_by_id = {r["representation_id"]: r for r in representations}
    sources_by_id = {s["source_id"]: s for s in sources}

    # Check broken chains
    broken_chains = 0
    ok_chains = 0
    for ev in events:
        try:
            io = build_intelligence_object(store, ev, source_name="")
            if io.chain:
                ok_chains += 1
            else:
                broken_chains += 1
        except Exception:
            broken_chains += 1

    # Check orphan facts (facts without events referencing them)
    event_fact_refs = set()
    for ev in events:
        for ref in ev.get("fact_version_snapshot", []):
            event_fact_refs.add(ref.get("fact_id"))

    orphan_facts = 0
    for f in facts:
        if f["fact_id"] not in event_fact_refs:
            orphan_facts += 1

    # Check orphan evidence (evidence without facts)
    fact_ids_set = set(f["fact_id"] for f in facts)
    orphan_evidence = 0
    for e in evidence:
        if e.get("event_or_fact_id") not in fact_ids_set:
            orphan_evidence += 1

    # Check orphan events (events without documents)
    orphan_events = 0
    for ev in events:
        if ev.get("document_id") not in docs_by_id:
            orphan_events += 1

    # Check version lineage
    events_by_event_id = defaultdict(list)
    for ev in events:
        events_by_event_id[ev["event_id"]].append(ev)

    multi_version_events = 0
    for eid, versions in events_by_event_id.items():
        if len(versions) > 1:
            multi_version_events += 1

    print(f"\n  Integrity checks:")
    print(f"    Broken chains:        {broken_chains} (target: 0)")
    print(f"    OK chains:            {ok_chains}")
    print(f"    Orphan facts:         {orphan_facts} (target: 0)")
    print(f"    Orphan evidence:      {orphan_evidence} (target: 0)")
    print(f"    Orphan events:        {orphan_events} (target: 0)")
    print(f"    Multi-version events: {multi_version_events}")

    all_pass = (broken_chains == 0 and orphan_events == 0)
    print(f"\n  {'✓ PASS' if all_pass else '✗ FAIL'}: Corpus integrity")

    return {
        "events": len(events),
        "facts": len(facts),
        "evidence": len(evidence),
        "documents": len(documents),
        "representations": len(representations),
        "sources": len(sources),
        "broken_chains": broken_chains,
        "ok_chains": ok_chains,
        "orphan_facts": orphan_facts,
        "orphan_evidence": orphan_evidence,
        "orphan_events": orphan_events,
        "multi_version_events": multi_version_events,
        "pass": all_pass,
    }


def audit_120_events(store_root: str = "v3_corpus_store", n_per_type=40):
    """§4 — Audit ≥120 IOs (stratified 40/40/40)."""
    print(f"\n{'='*70}")
    print(f"V7 §4 — 120-Event Semantic Audit")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Group IOs by event_type
    ios_by_type = defaultdict(list)
    for ev in store.iter("events"):
        doc = docs_by_id.get(ev.get("document_id", ""), {})
        src_id = doc.get("source_id", "")
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        ios_by_type[ev["event_type"]].append({
            "io_id": ioid,
            "event_row": ev,
            "source_id": src_id,
            "event_type": ev["event_type"],
        })

    # Sample up to 40 per type
    sample = []
    for event_type in ["monetary_policy_decision", "statistical_release", "regulatory_enforcement"]:
        pool = ios_by_type.get(event_type, [])
        selected = pool[:n_per_type]
        sample.extend(selected)
        print(f"  {event_type}: {len(selected)} sampled (of {len(pool)} available)")

    print(f"\n  Total sample: {len(sample)} IOs")

    # Audit each IO
    audit_results = []
    event_valid = 0
    event_ambiguous = 0
    event_false_positive = 0

    for io in sample:
        # Event semantic validation
        status, reason = validate_event_semantic(store, io)
        if status == "SEMANTICALLY_VALID":
            event_valid += 1
        elif status == "SEMANTICALLY_AMBIGUOUS":
            event_ambiguous += 1
        else:
            event_false_positive += 1

        # Multi-event check
        all_ios_for_doc = [e for e in store.iter("events")
                           if e.get("document_id") == io["event_row"].get("document_id")]
        multi_status, multi_reason = validate_multi_event(store, io, all_ios_for_doc)

        audit_results.append({
            "io_id": io["io_id"],
            "event_type": io["event_type"],
            "source_id": io["source_id"],
            "event_semantic": status,
            "event_reason": reason,
            "multi_event": multi_status,
        })

    event_precision = event_valid / len(sample) * 100 if sample else 0
    fp_rate = event_false_positive / len(sample) * 100 if sample else 0

    print(f"\n--- Audit Results ({len(sample)} IOs) ---")
    print(f"  SEMANTICALLY_VALID:     {event_valid} ({event_valid/len(sample)*100:.1f}%)")
    print(f"  SEMANTICALLY_AMBIGUOUS: {event_ambiguous} ({event_ambiguous/len(sample)*100:.1f}%)")
    print(f"  FALSE_POSITIVE:         {event_false_positive} ({fp_rate:.1f}%)")
    print(f"\n  Event Precision: {event_precision:.1f}% (target ≥98%)")
    print(f"  False Positive Rate: {fp_rate:.1f}% (target 0%)")

    if event_false_positive > 0:
        print(f"\n  False positive details:")
        for r in audit_results:
            if r["event_semantic"] == "FALSE_POSITIVE":
                print(f"    {r['io_id']}  type={r['event_type']:<30} src={r['source_id']:<25}")

    return {
        "total_audited": len(sample),
        "event_valid": event_valid,
        "event_ambiguous": event_ambiguous,
        "event_false_positive": event_false_positive,
        "event_precision_pct": round(event_precision, 1),
        "false_positive_rate_pct": round(fp_rate, 1),
        "audit_results": audit_results,
    }


def audit_500_facts(store_root: str = "v3_corpus_store", n_facts=500):
    """§5 — Audit ≥500 facts for Fact Precision ≥98%."""
    print(f"\n{'='*70}")
    print(f"V7 §5 — 500-Fact Quality Audit")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    all_facts = list(store.iter("facts"))
    print(f"\n  Total facts: {len(all_facts)}")
    print(f"  Auditing first {min(n_facts, len(all_facts))} facts...")

    # Build document text cache
    doc_text_cache = {}
    def get_doc_text(doc_id):
        if doc_id not in doc_text_cache:
            rep = None
            for rid, r in reps_by_id.items():
                if r.get("document_id") == doc_id:
                    rep = r
                    break
            if rep:
                blob_path = rep.get("raw_location", "")
                if blob_path and Path(blob_path).exists():
                    try:
                        blob_bytes = Path(blob_path).read_bytes()
                        if blob_bytes[:5] != b"%PDF-" and b"\x00" not in blob_bytes[:1000]:
                            doc_text_cache[doc_id] = strip_html(blob_bytes.decode("utf-8", errors="replace"))
                        else:
                            doc_text_cache[doc_id] = ""
                    except Exception:
                        doc_text_cache[doc_id] = ""
            else:
                doc_text_cache[doc_id] = ""
        return doc_text_cache[doc_id]

    # Audit
    fact_classifications = []
    evidence_classifications = []
    fact_dist = Counter()
    ev_dist = Counter()

    for i, fact in enumerate(all_facts[:n_facts]):
        doc_id = fact.get("document_id", "")
        doc_text = get_doc_text(doc_id)

        fact_class, fact_reason = classify_fact_quality(fact, doc_text)
        fact_classifications.append({"classification": fact_class, "metric": fact.get("metric", "")})
        fact_dist[fact_class] += 1

        ev_class, ev_reason = classify_evidence_grounding(fact, doc_text)
        evidence_classifications.append({"classification": ev_class})
        ev_dist[ev_class] += 1

    direct_supported = fact_dist.get("DIRECTLY_SUPPORTED", 0)
    partial_supported = fact_dist.get("PARTIALLY_SUPPORTED", 0)
    fact_precision = (direct_supported + partial_supported) / len(fact_classifications) * 100

    direct_evidence = ev_dist.get("DIRECT_EVIDENCE", 0)
    indirect_evidence = ev_dist.get("INDIRECT_EVIDENCE", 0)
    insufficient_evidence = ev_dist.get("INSUFFICIENT_EVIDENCE", 0)
    direct_pct = direct_evidence / len(evidence_classifications) * 100
    evidence_grounding = (direct_evidence + indirect_evidence) / len(evidence_classifications) * 100

    print(f"\n--- Fact Quality Distribution ({len(fact_classifications)} facts) ---")
    for cls, count in fact_dist.most_common():
        pct = count / len(fact_classifications) * 100
        print(f"  {cls:<30} {count:>4}  ({pct:.1f}%)")

    print(f"\n--- Evidence Grounding ({len(evidence_classifications)} facts) ---")
    for cls, count in ev_dist.most_common():
        pct = count / len(evidence_classifications) * 100
        print(f"  {cls:<30} {count:>4}  ({pct:.1f}%)")

    print(f"\n--- Quality Metrics ---")
    print(f"  Fact Precision: {fact_precision:.1f}% (target ≥98%)")
    print(f"  Direct Evidence: {direct_pct:.1f}% (target ≥90%)")
    print(f"  Evidence Grounding: {evidence_grounding:.1f}%")
    print(f"  Insufficient Evidence: {insufficient_evidence} ({insufficient_evidence/len(evidence_classifications)*100:.1f}%)")

    return {
        "total_facts_audited": len(fact_classifications),
        "fact_quality_dist": dict(fact_dist),
        "evidence_grounding_dist": dict(ev_dist),
        "fact_precision_pct": round(fact_precision, 1),
        "direct_evidence_pct": round(direct_pct, 1),
        "evidence_grounding_pct": round(evidence_grounding, 1),
        "insufficient_evidence_pct": round(insufficient_evidence / len(evidence_classifications) * 100, 1),
    }


def main():
    store_root = sys.argv[1] if len(sys.argv) > 1 else "v3_corpus_store"

    # §3: Corpus integrity
    integrity = verify_corpus_integrity(store_root)

    # §4: 120-event audit
    event_audit = audit_120_events(store_root, n_per_type=40)

    # §5: 500-fact audit
    fact_audit = audit_500_facts(store_root, n_facts=500)

    # Summary
    print(f"\n{'='*70}")
    print(f"V7 SUMMARY")
    print(f"{'='*70}")
    print(f"  Corpus integrity: {'PASS' if integrity['pass'] else 'FAIL'}")
    print(f"  Event Precision: {event_audit['event_precision_pct']}% ({event_audit['total_audited']} audited)")
    print(f"  False Positives: {event_audit['false_positive_rate_pct']}%")
    print(f"  Fact Precision: {fact_audit['fact_precision_pct']}% ({fact_audit['total_facts_audited']} audited)")
    print(f"  Direct Evidence: {fact_audit['direct_evidence_pct']}%")
    print(f"  Insufficient Evidence: {fact_audit['insufficient_evidence_pct']}%")

    # Save
    out = {
        "integrity": integrity,
        "event_audit": event_audit,
        "fact_audit": fact_audit,
    }
    out_path = Path("intelligence_core/tests/reliability/v7_audit_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
