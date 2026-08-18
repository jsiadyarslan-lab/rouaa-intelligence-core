"""V4 — Fix: Identify and exclude PDF documents from extraction.

Root cause of 9.2% false positives: PDF documents are being processed as text,
extracting random byte sequences that match patterns.

Per D10 boundary: PDFs should be skipped (binary format, not text-extractable).
"""
from __future__ import annotations
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore


def identify_pdf_documents(store_root: str = "v3_corpus_store"):
    """Find all documents whose content is actually PDF (binary), not HTML/text."""
    print(f"\n--- Identifying PDF/binary documents ---")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    pdf_docs = []
    binary_docs = []
    text_docs = []

    for rep_id, rep in reps_by_id.items():
        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue

        try:
            data = Path(blob_path).read_bytes()
            # Check if it's PDF
            if data[:5] == b"%PDF-":
                pdf_docs.append({"rep_id": rep_id, "doc_id": rep.get("document_id", "")})
            # Check if it's binary (non-text)
            elif b"\x00" in data[:1000]:
                binary_docs.append({"rep_id": rep_id, "doc_id": rep.get("document_id", "")})
            else:
                text_docs.append({"rep_id": rep_id, "doc_id": rep.get("document_id", "")})
        except Exception:
            pass

    print(f"  PDF documents: {len(pdf_docs)}")
    print(f"  Binary documents: {len(binary_docs)}")
    print(f"  Text/HTML documents: {len(text_docs)}")
    print(f"  Total: {len(pdf_docs) + len(binary_docs) + len(text_docs)}")

    return pdf_docs, binary_docs, text_docs


def clean_pdf_facts_and_events(store_root: str = "v3_corpus_store"):
    """Remove facts + events that were extracted from PDF/binary documents.

    These are false positives — PDF binary content was incorrectly processed
    as text, matching patterns in random byte sequences.
    """
    print(f"\n--- Cleaning PDF/binary-derived facts + events ---")

    store = CachedStore(AppendOnlyStore(store_root))
    pdf_docs, binary_docs, text_docs = identify_pdf_documents(store_root)

    # Collect all doc_ids that are PDF or binary
    bad_doc_ids = set()
    for d in pdf_docs:
        bad_doc_ids.add(d["doc_id"])
    for d in binary_docs:
        bad_doc_ids.add(d["doc_id"])

    print(f"  Bad document IDs: {len(bad_doc_ids)}")

    # Find facts + events to remove
    facts_to_remove = []
    events_to_remove = []

    for f in store.iter("facts"):
        if f.get("document_id") in bad_doc_ids:
            facts_to_remove.append(f["fact_id"])

    for ev in store.iter("events"):
        if ev.get("document_id") in bad_doc_ids:
            events_to_remove.append((ev["event_id"], ev["event_version"]))

    print(f"  Facts to remove (from PDF/binary): {len(facts_to_remove)}")
    print(f"  Events to remove (from PDF/binary): {len(events_to_remove)}")

    # Rewrite events.jsonl without PDF-derived events
    events_path = Path(store_root) / "events.jsonl"
    facts_path = Path(store_root) / "facts.jsonl"
    evidence_path = Path(store_root) / "evidence.jsonl"

    import json

    # Filter events
    all_events = list(store.iter("events"))
    clean_events = [ev for ev in all_events
                    if ev.get("document_id") not in bad_doc_ids]
    print(f"  Events before: {len(all_events)}, after: {len(clean_events)}")

    with open(events_path, "w", encoding="utf-8") as f:
        for ev in clean_events:
            f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")

    # Filter facts
    all_facts = list(store.iter("facts"))
    clean_facts = [f for f in all_facts
                   if f.get("document_id") not in bad_doc_ids]
    print(f"  Facts before: {len(all_facts)}, after: {len(clean_facts)}")

    with open(facts_path, "w", encoding="utf-8") as f:
        for fact in clean_facts:
            f.write(json.dumps(fact, ensure_ascii=False, sort_keys=True) + "\n")

    # Filter evidence (remove evidence for removed facts)
    bad_fact_ids = set(f["fact_id"] for f in all_facts if f.get("document_id") in bad_doc_ids)
    all_evidence = list(store.iter("evidence"))
    clean_evidence = [e for e in all_evidence
                      if e.get("event_or_fact_id") not in bad_fact_ids]
    print(f"  Evidence before: {len(all_evidence)}, after: {len(clean_evidence)}")

    with open(evidence_path, "w", encoding="utf-8") as f:
        for e in clean_evidence:
            f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    # Verify
    store2 = CachedStore(AppendOnlyStore(store_root))
    final_events = sum(1 for _ in store2.iter("events"))
    final_facts = sum(1 for _ in store2.iter("facts"))
    print(f"\n  Final events: {final_events}")
    print(f"  Final facts: {final_facts}")

    return final_events, final_facts


if __name__ == "__main__":
    final_events, final_facts = clean_pdf_facts_and_events()
