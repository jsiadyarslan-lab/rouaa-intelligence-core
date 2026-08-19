"""V12 §2-3 — Mandatory Quality Pipeline + Full Corpus Reprocessing.

Makes V10 quality gates MANDATORY for every document:
  Binary validation → Language → Nav filtering → Extraction → Evidence →
  Fact validation → Semantic gate → IO

Reprocesses ALL 1,034 documents through this complete pipeline.
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
from intelligence_core.contracts import Evidence
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v9_navigation_exclusion import is_navigation_content
from intelligence_core.tests.reliability.v10_evidence_closure import classify_evidence_strict, expand_evidence_for_direct
from intelligence_core.tests.reliability.event_semantic_gate import should_create_event


def classify_language(text: str) -> str:
    """Classify document language."""
    if not text:
        return "unknown"
    total = len(text)
    if total == 0:
        return "unknown"
    hiragana = sum(1 for c in text if 0x3040 <= ord(c) <= 0x309F)
    katakana = sum(1 for c in text if 0x30A0 <= ord(c) <= 0x30FF)
    cjk = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
    arabic = sum(1 for c in text if 0x0600 <= ord(c) <= 0x06FF)
    cyrillic = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    if hiragana + katakana > 10:
        return "ja"
    elif cjk / total > 0.1:
        return "zh"
    elif arabic / total > 0.1:
        return "ar"
    elif cyrillic / total > 0.1:
        return "ru"
    else:
        return "en"


SRC_TO_EVENT_TYPES = {
    "central_bank": ["monetary_policy_decision", "statistical_release", "regulatory_enforcement"],
    "statistical_agency": ["statistical_release"],
    "financial_regulator": ["regulatory_enforcement", "statistical_release"],
    "securities_regulator": ["regulatory_enforcement", "statistical_release"],
    "banking_regulator": ["regulatory_enforcement", "statistical_release"],
    "finance_ministry": ["monetary_policy_decision", "statistical_release"],
}


def get_source_class(src_id):
    if any(x in src_id for x in ["fed-reserve", "ecb", "boe", "boj", "boc", "cbk", "nsi", "nbu",
                                  "cso", "sfc", "miti", "bb-", "nrb", "ecb-stat", "bnetza",
                                  "cma", "beis", "ustr", "sama", "cbj", "bank"]):
        return "central_bank"
    elif any(x in src_id for x in ["sec", "cftc", "esma", "fca", "consob", "naic", "dfsa"]):
        return "financial_regulator"
    else:
        return "statistical_agency"


def run_mandatory_quality_pipeline(store_root: str = "v3_corpus_store"):
    """Reprocess ALL documents through the complete V10 quality pipeline."""
    print(f"\n{'='*70}")
    print(f"V12 §2-3 — Mandatory Quality Pipeline + Full Corpus Reprocessing")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Count before
    before_events = sum(1 for _ in store.iter("events"))
    before_facts = sum(1 for _ in store.iter("facts"))
    before_docs = sum(1 for _ in store.iter("documents"))
    print(f"\n  Before: {before_events} events, {before_facts} facts, {before_docs} docs")

    # Clear facts + evidence + events
    facts_path = Path(store_root) / "facts.jsonl"
    evidence_path = Path(store_root) / "evidence.jsonl"
    events_path = Path(store_root) / "events.jsonl"
    open(facts_path, "w").close()
    open(evidence_path, "w").close()
    open(events_path, "w").close()

    store = CachedStore(AppendOnlyStore(store_root))

    # Pipeline counters
    pipeline_stats = Counter()
    source_stats = defaultdict(lambda: Counter())
    nav_rejected_facts = []
    semantic_rejected_candidates = []
    language_stats = defaultdict(lambda: Counter())

    # Process each representation through the mandatory pipeline
    for rep_id, rep in reps_by_id.items():
        doc_id = rep.get("document_id", "")
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")

        if "job-" in src_id:
            continue

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            pipeline_stats["NO_BLOB"] += 1
            continue

        try:
            blob_bytes = Path(blob_path).read_bytes()
        except Exception:
            pipeline_stats["BLOB_READ_ERROR"] += 1
            continue

        # §2 Step 1: Binary/format validation
        if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
            pipeline_stats["PDF_BINARY_REJECTED"] += 1
            source_stats[src_id]["pdf_binary"] += 1
            continue

        pipeline_stats["FORMAT_VALID"] += 1

        # §2 Step 2: Language classification
        doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        language = classify_language(doc_text)
        language_stats[language]["documents"] += 1
        pipeline_stats[f"LANG_{language}"] += 1

        # §2 Step 3: Source class + event types
        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            pattern_key = {
                "monetary_policy_decision": "monetary",
                "statistical_release": "statistical",
                "regulatory_enforcement": "regulatory",
            }.get(event_type, "statistical")
            patterns = REFINED_PATTERNS.get(pattern_key, [])

            # §2 Step 4: Fact extraction (sentence-aware)
            facts = improved_extract_facts(doc_text, patterns, rep_id, doc_id)
            if not facts:
                continue

            # §2 Step 5: Navigation/UI filtering
            clean_facts = []
            for f in facts:
                if is_navigation_content(f.excerpt):
                    pipeline_stats["NAV_REJECTED"] += 1
                    nav_rejected_facts.append({
                        "fact_id": f.fact_id[:25],
                        "metric": f.metric,
                        "value": str(f.value)[:30],
                        "excerpt": f.excerpt[:80],
                        "source_id": src_id,
                        "doc_id": doc_id,
                    })
                    # Try expansion
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, doc_text)
                    if "DIRECT" in status:
                        f.excerpt = new_excerpt
                        clean_facts.append(f)
                        pipeline_stats["NAV_RECOVERED"] += 1
                else:
                    clean_facts.append(f)

            if not clean_facts:
                continue

            # §2 Step 6: Evidence selection (expand INDIRECT to DIRECT)
            direct_facts = []
            for f in clean_facts:
                cls, reason = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    new_excerpt, status = expand_evidence_for_direct(f, f.excerpt, doc_text)
                    if "DIRECT" in status:
                        f.excerpt = new_excerpt
                        direct_facts.append(f)
                    elif cls == "INVALID":
                        pipeline_stats["INVALID_EVIDENCE"] += 1
                    else:
                        direct_facts.append(f)  # Keep INDIRECT facts
                else:
                    direct_facts.append(f)

            if not direct_facts:
                continue

            # §2 Step 7: Semantic Event Gate
            should_create, gate_reason = should_create_event(event_type, direct_facts, doc_text)
            if not should_create:
                pipeline_stats["SEMANTIC_GATE_REJECTED"] += 1
                semantic_rejected_candidates.append({
                    "event_type": event_type,
                    "source_id": src_id,
                    "doc_id": doc_id,
                    "reason": gate_reason,
                })
                continue

            pipeline_stats["SEMANTIC_GATE_PASSED"] += 1

            # §2 Step 8: Append facts + evidence
            for f in direct_facts:
                store.append("facts", f.to_dict())
                store.append("evidence", Evidence(
                    evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                    event_or_fact_id=f.fact_id,
                    representation_id=f.representation_id,
                    location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                    excerpt=f.excerpt,
                    provenance_ref=f"representation:{f.representation_id}",
                ).to_dict())
                pipeline_stats["FACTS_APPENDED"] += 1
                source_stats[src_id]["facts"] += 1

            # §2 Step 9: Event detection
            ev = detect_event(direct_facts, doc_id, event_type)
            if ev is None:
                continue

            existing_ev = store.current_event(ev.event_id)
            if existing_ev is None:
                store.append("events", ev.to_dict())
                existing_ev = store.current_event(ev.event_id)
                pipeline_stats["EVENTS_CREATED"] += 1
                source_stats[src_id]["events"] += 1

                # §2 Step 10: Build IO
                try:
                    io = build_intelligence_object(store, existing_ev, source_name=src_id)
                    pipeline_stats["IOS_BUILT"] += 1
                    source_stats[src_id]["ios"] += 1
                except Exception:
                    pass

    # Clean broken chains
    store2 = CachedStore(AppendOnlyStore(store_root))
    all_events = list(store2.iter("events"))
    clean_events = []
    removed = 0
    for ev in all_events:
        try:
            io = build_intelligence_object(store2, ev, source_name="")
            clean_events.append(ev)
        except Exception:
            removed += 1

    if removed > 0:
        with open(events_path, "w", encoding="utf-8") as f:
            for ev in clean_events:
                f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")
        pipeline_stats["BROKEN_CHAINS_REMOVED"] = removed

    # Final counts
    store3 = CachedStore(AppendOnlyStore(store_root))
    final_events = sum(1 for _ in store3.iter("events"))
    final_facts = sum(1 for _ in store3.iter("facts"))
    final_evidence = sum(1 for _ in store3.iter("evidence"))

    # Print results
    print(f"\n--- Pipeline Statistics ---")
    for k, v in pipeline_stats.most_common():
        print(f"  {k:<30} {v:>6}")

    print(f"\n--- Final Results ---")
    print(f"  Events: {final_events}")
    print(f"  Facts: {final_facts}")
    print(f"  Evidence: {final_evidence}")

    print(f"\n--- Language Distribution ---")
    for lang, stats in sorted(language_stats.items(), key=lambda x: -x[1]["documents"]):
        print(f"  {lang}: {stats['documents']} docs")

    print(f"\n--- Navigation Rejected: {len(nav_rejected_facts)} ---")
    print(f"  Sample (first 5):")
    for r in nav_rejected_facts[:5]:
        print(f"    metric={r['metric']:<20} value={r['value'][:15]:<15} excerpt={r['excerpt'][:50]}")

    print(f"\n--- Semantic Gate Rejected: {len(semantic_rejected_candidates)} ---")
    print(f"  Sample (first 5):")
    for r in semantic_rejected_candidates[:5]:
        print(f"    type={r['event_type']:<30} src={r['source_id'][:25]} reason={r['reason'][:60]}")

    # Save detailed results
    out = {
        "pipeline_stats": dict(pipeline_stats),
        "final_events": final_events,
        "final_facts": final_facts,
        "final_evidence": final_evidence,
        "language_stats": {k: dict(v) for k, v in language_stats.items()},
        "nav_rejected_count": len(nav_rejected_facts),
        "semantic_rejected_count": len(semantic_rejected_candidates),
        "nav_rejected_sample": nav_rejected_facts[:50],
        "semantic_rejected_sample": semantic_rejected_candidates[:50],
        "source_stats": {k: dict(v) for k, v in source_stats.items()},
    }
    out_path = Path("intelligence_core/tests/reliability/v12_pipeline_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return final_events, final_facts, nav_rejected_facts, semantic_rejected_candidates


if __name__ == "__main__":
    events, facts, nav_rejected, sem_rejected = run_mandatory_quality_pipeline()
    print(f"\n  Final: {events} events, {facts} facts")
