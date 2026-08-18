"""V8 §7-9 — Full Survivor Audit + Full Fact Audit + Direct Evidence.

§7: Audit ALL 153 surviving IOs (not sample)
§8: Audit ALL facts attached to 153 IOs (not 500 sample)
§9: Direct evidence with strict definition
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
from intelligence_core.tests.reliability.fact_evidence_audit import classify_fact_quality, classify_evidence_grounding
from intelligence_core.tests.reliability.v7_direct_evidence_closure import re_classify_evidence_with_expansion


def full_survivor_audit(store_root: str = "v3_corpus_store"):
    """§7 — Audit ALL 153 surviving IOs (not sample)."""
    print(f"\n{'='*70}")
    print(f"V8 §7 — Full 153/153 Survivor Audit")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Get ALL events
    all_events = list(store.iter("events"))
    print(f"\n  Total surviving events: {len(all_events)}")

    # Audit EVERY event
    valid = 0
    ambiguous = 0
    false_positive = 0
    results = []

    for ev in all_events:
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        doc_id = ev.get("document_id", "")
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")

        # Get document text
        rep = None
        for rid, r in reps_by_id.items():
            if r.get("document_id") == doc_id:
                rep = r
                break

        doc_text = ""
        if rep:
            blob_path = rep.get("raw_location", "")
            if blob_path and Path(blob_path).exists():
                try:
                    blob_bytes = Path(blob_path).read_bytes()
                    if blob_bytes[:5] != b"%PDF-" and b"\x00" not in blob_bytes[:1000]:
                        doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
                except Exception:
                    pass

        # Semantic validation
        is_valid, reason = validate_event_context(ev["event_type"], doc_text)

        # Also check non-English
        ascii_chars = sum(1 for c in doc_text if ord(c) < 128)
        total_chars = len(doc_text) if doc_text else 1
        non_ascii_ratio = 1 - (ascii_chars / total_chars) if total_chars > 0 else 0

        if is_valid:
            valid += 1
            status = "SEMANTICALLY_VALID"
        elif non_ascii_ratio > 0.3:
            ambiguous += 1
            status = "SEMANTICALLY_AMBIGUOUS"
        else:
            false_positive += 1
            status = "FALSE_POSITIVE"

        results.append({
            "io_id": ioid,
            "event_type": ev["event_type"],
            "source_id": src_id,
            "status": status,
            "reason": reason,
        })

    total = len(all_events)
    event_precision = valid / total * 100 if total else 0
    fp_rate = false_positive / total * 100 if total else 0

    print(f"\n--- Full Survivor Audit Results ({total} IOs) ---")
    print(f"  SEMANTICALLY_VALID:     {valid} ({valid/total*100:.1f}%)")
    print(f"  SEMANTICALLY_AMBIGUOUS: {ambiguous} ({ambiguous/total*100:.1f}%)")
    print(f"  FALSE_POSITIVE:         {false_positive} ({fp_rate:.1f}%)")

    print(f"\n  Event Precision: {event_precision:.1f}% (numerator={valid}, denominator={total})")
    print(f"  False Positive Rate: {fp_rate:.1f}% (numerator={false_positive}, denominator={total})")

    if false_positive > 0:
        print(f"\n  False positives:")
        for r in results:
            if r["status"] == "FALSE_POSITIVE":
                print(f"    {r['io_id']}  type={r['event_type']:<30} src={r['source_id']:<25}")

    return {
        "total": total,
        "valid": valid,
        "ambiguous": ambiguous,
        "false_positive": false_positive,
        "event_precision_pct": round(event_precision, 1),
        "false_positive_rate_pct": round(fp_rate, 1),
        "numerator": valid,
        "denominator": total,
        "universe": "all surviving events",
        "sample": "census (100% of corpus)",
        "results": results,
    }


def full_fact_audit(store_root: str = "v3_corpus_store"):
    """§8 — Audit ALL facts attached to 153 IOs (not 500 sample)."""
    print(f"\n{'='*70}")
    print(f"V8 §8 — Full Fact Audit (ALL facts)")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Get ALL facts that are attached to surviving events
    surviving_fact_ids = set()
    for ev in store.iter("events"):
        for ref in ev.get("fact_version_snapshot", []):
            surviving_fact_ids.add(ref.get("fact_id"))

    # Get ALL facts in store
    all_facts = list(store.iter("facts"))
    # Filter to only those attached to surviving events
    attached_facts = [f for f in all_facts if f["fact_id"] in surviving_fact_ids]

    print(f"\n  Total facts in store: {len(all_facts)}")
    print(f"  Facts attached to surviving events: {len(attached_facts)}")
    print(f"  Auditing ALL {len(attached_facts)} attached facts...")

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

    fact_dist = Counter()
    evidence_dist = Counter()
    direct_with_expansion = 0
    results = []

    for fact in attached_facts:
        doc_id = fact.get("document_id", "")
        doc_text = get_doc_text(doc_id)

        # Fact quality
        fact_class, fact_reason = classify_fact_quality(fact, doc_text)
        fact_dist[fact_class] += 1

        # Evidence grounding with expansion (V7)
        ev_class, expanded_excerpt, ev_reason = re_classify_evidence_with_expansion(fact, doc_text)
        evidence_dist[ev_class] += 1
        if ev_class == "DIRECT_EVIDENCE":
            direct_with_expansion += 1

        results.append({
            "fact_id": fact["fact_id"],
            "metric": fact.get("metric", ""),
            "fact_quality": fact_class,
            "evidence_grounding": ev_class,
        })

    total = len(attached_facts)
    direct_supported = fact_dist.get("DIRECTLY_SUPPORTED", 0)
    partial = fact_dist.get("PARTIALLY_SUPPORTED", 0)
    fact_precision = (direct_supported + partial) / total * 100 if total else 0

    direct_ev = evidence_dist.get("DIRECT_EVIDENCE", 0)
    indirect_ev = evidence_dist.get("INDIRECT_EVIDENCE", 0)
    insufficient_ev = evidence_dist.get("INSUFFICIENT_EVIDENCE", 0)
    direct_pct = direct_ev / total * 100 if total else 0

    print(f"\n--- Fact Quality Distribution ({total} facts) ---")
    for cls, count in fact_dist.most_common():
        print(f"  {cls:<30} {count:>5}  ({count/total*100:.1f}%)")

    print(f"\n--- Evidence Grounding ({total} facts) ---")
    for cls, count in evidence_dist.most_common():
        print(f"  {cls:<30} {count:>5}  ({count/total*100:.1f}%)")

    print(f"\n--- Quality Metrics (governed KPIs) ---")
    print(f"  Fact Precision: {fact_precision:.1f}%")
    print(f"    numerator={direct_supported + partial}, denominator={total}")
    print(f"    universe=all facts attached to surviving events")
    print(f"    sample=census (100%)")

    print(f"\n  Direct Evidence: {direct_pct:.1f}%")
    print(f"    numerator={direct_ev}, denominator={total}")
    print(f"    universe=all facts attached to surviving events")
    print(f"    sample=census (100%)")

    print(f"\n  Insufficient Evidence: {insufficient_ev} ({insufficient_ev/total*100:.1f}%)")

    return {
        "total_facts": total,
        "fact_quality_dist": dict(fact_dist),
        "evidence_grounding_dist": dict(evidence_dist),
        "fact_precision_pct": round(fact_precision, 1),
        "direct_evidence_pct": round(direct_pct, 1),
        "insufficient_evidence_count": insufficient_ev,
        "insufficient_evidence_pct": round(insufficient_ev / total * 100, 1) if total else 0,
        "numerator_fact": direct_supported + partial,
        "denominator_fact": total,
        "universe_fact": "all facts attached to surviving events",
        "sample_fact": "census (100%)",
        "numerator_direct": direct_ev,
        "denominator_direct": total,
        "universe_direct": "all facts attached to surviving events",
        "sample_direct": "census (100%)",
    }


def main():
    store_root = sys.argv[1] if len(sys.argv) > 1 else "v3_corpus_store"

    # §7: Full survivor audit
    survivor_audit = full_survivor_audit(store_root)

    # §8-9: Full fact audit
    fact_audit = full_fact_audit(store_root)

    # Summary
    print(f"\n{'='*70}")
    print(f"V8 SUMMARY")
    print(f"{'='*70}")
    print(f"  Survivor audit: {survivor_audit['valid']}/{survivor_audit['total']} valid")
    print(f"  Event Precision: {survivor_audit['event_precision_pct']}%")
    print(f"  False Positives: {survivor_audit['false_positive_rate_pct']}%")
    print(f"  Fact Precision: {fact_audit['fact_precision_pct']}%")
    print(f"  Direct Evidence: {fact_audit['direct_evidence_pct']}%")
    print(f"  Insufficient Evidence: {fact_audit['insufficient_evidence_pct']}%")

    # Save
    out = {
        "survivor_audit": survivor_audit,
        "fact_audit": fact_audit,
    }
    out_path = Path("intelligence_core/tests/reliability/v8_full_audit_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
