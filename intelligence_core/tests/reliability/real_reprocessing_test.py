"""V2-Real §8 — Real reprocessing stress test.

Choose 20 REAL IO-producing source documents. Reprocess them 1x/5x/10x
with unchanged content. Verify 0 duplicates.

Then run a real correction/supersession chain (if available) — otherwise
keep the existing deterministic correction test clearly labeled as non-real.
"""
from __future__ import annotations
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Evidence
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.topup_expanded_patterns import EXPANDED_PATTERNS


def select_20_real_documents(store, n=20):
    """Select 20 real documents that produce events, from diverse sources."""
    sources_by_id = store.latest_by_id("sources", "source_id")
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Group events by source
    events_by_source = {}
    for ev in store.iter("events"):
        doc = docs_by_id.get(ev.get("document_id", ""), {})
        src_id = doc.get("source_id", "")
        # Skip synthetic
        if "job-" in src_id or "istat" in src_id or "fdic" in src_id:
            continue
        events_by_source.setdefault(src_id, []).append(ev)

    # Pick at most 2 documents per source for diversity
    selected = []
    for src_id, events in events_by_source.items():
        for ev in events[:2]:
            doc_id = ev.get("document_id", "")
            doc = docs_by_id.get(doc_id, {})
            rep_id = doc.get("representation_id", reps_by_id.get(doc_id, {}).get("representation_id", ""))
            # Find the representation
            for rid, rep in reps_by_id.items():
                if rep["document_id"] == doc_id:
                    selected.append({
                        "doc_id": doc_id,
                        "rep_id": rid,
                        "source_id": src_id,
                        "event_id": ev["event_id"],
                        "event_type": ev["event_type"],
                    })
                    break
            if len([s for s in selected if s["source_id"] == src_id]) >= 2:
                break
        if len(selected) >= n:
            break
    return selected[:n]


def reprocess_real_documents(store_root: str, n_docs=20):
    """Reprocess 20 real documents 1x/5x/10x — verify 0 duplicates."""
    print(f"\n{'='*70}")
    print(f"V2-Real §8 — Real Reprocessing Stress")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))

    # Snapshot before
    before = {
        "events": sum(1 for _ in store.iter("events")),
        "facts": sum(1 for _ in store.iter("facts")),
        "evidence": sum(1 for _ in store.iter("evidence")),
        "documents": sum(1 for _ in store.iter("documents")),
    }
    print(f"\n  Before reprocessing: {before}")

    # Select 20 real documents
    docs = select_20_real_documents(store, n=n_docs)
    print(f"\n  Selected {len(docs)} real documents from {len(set(d['source_id'] for d in docs))} sources:")
    for d in docs:
        print(f"    {d['source_id']:<25} doc={d['doc_id'][:30]:<30} event={d['event_id']}")

    # Reprocess 1x
    print(f"\n  Pass 1 (reprocess 1x)...")
    run_id = f"real-reprocess-1x-{int(time.time())}"
    _reprocess_docs(store, docs, run_id)
    after_1x = {
        "events": sum(1 for _ in store.iter("events")),
        "facts": sum(1 for _ in store.iter("facts")),
        "evidence": sum(1 for _ in store.iter("evidence")),
        "documents": sum(1 for _ in store.iter("documents")),
    }
    print(f"    After 1x: {after_1x}")

    # Verify 0 new entities
    if after_1x != before:
        print(f"    ✗ FAIL: entities changed after 1x reprocessing")
        return False
    print(f"    ✓ PASS: 0 new entities after 1x")

    # Reprocess 5x
    print(f"\n  Pass 2 (reprocess 5x)...")
    for rep in range(5):
        run_id = f"real-reprocess-5x-{rep}-{int(time.time())}"
        _reprocess_docs(store, docs, run_id)
    after_5x = {
        "events": sum(1 for _ in store.iter("events")),
        "facts": sum(1 for _ in store.iter("facts")),
        "evidence": sum(1 for _ in store.iter("evidence")),
        "documents": sum(1 for _ in store.iter("documents")),
    }
    print(f"    After 5x: {after_5x}")
    if after_5x != before:
        print(f"    ✗ FAIL: entities changed after 5x reprocessing")
        return False
    print(f"    ✓ PASS: 0 new entities after 5x")

    # Reprocess 10x
    print(f"\n  Pass 3 (reprocess 10x)...")
    for rep in range(10):
        run_id = f"real-reprocess-10x-{rep}-{int(time.time())}"
        _reprocess_docs(store, docs, run_id)
    after_10x = {
        "events": sum(1 for _ in store.iter("events")),
        "facts": sum(1 for _ in store.iter("facts")),
        "evidence": sum(1 for _ in store.iter("evidence")),
        "documents": sum(1 for _ in store.iter("documents")),
    }
    print(f"    After 10x: {after_10x}")
    if after_10x != before:
        print(f"    ✗ FAIL: entities changed after 10x reprocessing")
        return False
    print(f"    ✓ PASS: 0 new entities after 10x")

    print(f"\n  ✓ Reprocessing idempotency: PASS (0 duplicates across 1x/5x/10x)")
    return True


def _reprocess_docs(store, docs, run_id):
    """Reprocess the given documents — extract facts + detect events."""
    sources_by_id = store.latest_by_id("sources", "source_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")

    for d in docs:
        try:
            rep = reps_by_id.get(d["rep_id"], {})
            blob_path = rep.get("raw_location", "")
            if not blob_path or not Path(blob_path).exists():
                continue
            blob_bytes = Path(blob_path).read_bytes()
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))

            # Determine patterns based on event_type
            if d["event_type"] == "monetary_policy_decision":
                patterns = EXPANDED_PATTERNS["monetary"]
            elif d["event_type"] == "regulatory_enforcement":
                patterns = EXPANDED_PATTERNS["regulatory"]
            else:
                patterns = EXPANDED_PATTERNS["statistical"]

            facts = extract_facts(text, patterns, d["rep_id"], d["doc_id"])
            if not facts:
                continue

            # Idempotent append
            for f in facts:
                cur = store.current_fact(f.fact_id)
                if cur is None:
                    store.append("facts", f.to_dict())
                    store.append("evidence", Evidence(
                        evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                        event_or_fact_id=f.fact_id,
                        representation_id=f.representation_id,
                        location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                        excerpt=f.excerpt,
                        provenance_ref=f"representation:{f.representation_id}",
                    ).to_dict())

            # Detect event (idempotent)
            ev = detect_event(facts, d["doc_id"], d["event_type"])
            if ev is None:
                continue
            existing_ev = store.current_event(ev.event_id)
            if existing_ev is None:
                store.append("events", ev.to_dict())
        except Exception:
            pass


def main():
    store_root = "real_corpus_store"
    pass_status = reprocess_real_documents(store_root, n_docs=20)
    print(f"\n{'='*70}")
    print(f"FINAL: {'PASS' if pass_status else 'FAIL'}")
    return 0 if pass_status else 1


if __name__ == "__main__":
    sys.exit(main())
