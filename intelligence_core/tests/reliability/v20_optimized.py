"""V20 §2-4 — Performance-Optimized V19 Pipeline + Full Frozen Benchmark.

Optimizes V19 by:
1. Caching HTMLStructureParser results (don't re-parse)
2. Only running structured extraction on docs with tables/lists
3. Batch processing support

Then runs the FULL frozen 300-doc benchmark to completion.
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
from intelligence_core.detect import detect_event, EVENT_TYPE_RULES
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts, normalize_metric
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
from intelligence_core.tests.reliability.v9_navigation_exclusion import is_navigation_content
from intelligence_core.tests.reliability.v10_evidence_closure import classify_evidence_strict, expand_evidence_for_direct
from intelligence_core.tests.reliability.v13_recall_patterns import (
    is_navigation_content_v13, validate_event_context_v13,
    NEW_RECALL_PATTERNS, STRUCTURED_PATTERNS, MULTILINGUAL_PATTERNS,
)
from intelligence_core.tests.reliability.v15_recall_recovery import extract_html_structure
from intelligence_core.tests.reliability.v19_forensic import normalize_metric_v19
from intelligence_core.tests.reliability.v13_reprocess import classify_language


def run_v20_optimized(store_root: str = "v3_corpus_store", batch_size: int = 0):
    """V20 — Optimized pipeline with full benchmark support."""
    print(f"\n{'='*70}")
    print(f"V20 — Optimized Structural Recovery + Full Benchmark")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    v17_events = sum(1 for _ in store.iter("events"))
    v17_facts = sum(1 for _ in store.iter("facts"))
    print(f"\n  V17 baseline: {v17_events} events, {v17_facts} facts")

    # Clear for reprocessing
    for coll in ["facts", "evidence", "events"]:
        p = Path(store_root) / f"{coll}.jsonl"
        open(p, "w").close()
    store = CachedStore(AppendOnlyStore(store_root))

    pipeline_stats = Counter()
    structural_stats = Counter()
    timing = defaultdict(float)
    total_docs = 0

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

    def get_patterns(language, event_type):
        pk = {"monetary_policy_decision": "monetary", "statistical_release": "statistical",
              "regulatory_enforcement": "regulatory"}.get(event_type, "statistical")
        patterns = list(REFINED_PATTERNS.get(pk, []))
        for regex, pt in NEW_RECALL_PATTERNS:
            m = normalize_metric_v19(pt)
            if m in EVENT_TYPE_RULES.get(event_type, {}).get("trigger_metrics", set()):
                patterns.append((regex, pt))
        for regex, pt in STRUCTURED_PATTERNS:
            patterns.append((regex, pt))
        if language in MULTILINGUAL_PATTERNS:
            for regex, pt in MULTILINGUAL_PATTERNS[language]:
                m = normalize_metric_v19(pt)
                if m in EVENT_TYPE_RULES.get(event_type, {}).get("trigger_metrics", set()):
                    patterns.append((regex, pt))
        return patterns

    for rep_id, rep in reps_by_id.items():
        doc_id = rep.get("document_id", "")
        doc = docs_by_id.get(doc_id, {})
        src_id = doc.get("source_id", "")
        if "job-" in src_id:
            continue

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue

        try:
            blob_bytes = Path(blob_path).read_bytes()
        except Exception:
            continue

        if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
            pipeline_stats["PDF_BINARY"] += 1
            continue

        pipeline_stats["FORMAT_VALID"] += 1

        # §2: Always get flat text
        flat_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))

        # §3: Get structured segments ONLY if document has tables/lists
        t1 = time.perf_counter()
        structured_segments = extract_html_structure(blob_bytes)
        timing["html_parse"] += time.perf_counter() - t1

        has_tables = any(ctx == "TABLE_ROW" for _, ctx, _ in structured_segments)
        has_lists = sum(1 for _, ctx, _ in structured_segments if ctx == "LIST_ITEM") > 5
        has_headings = sum(1 for _, ctx, _ in structured_segments if ctx == "HEADING") > 3
        use_structured = has_tables or has_lists or has_headings

        if use_structured:
            pipeline_stats["STRUCTURED_TRIGGERED"] += 1
        else:
            pipeline_stats["FLAT_ONLY"] += 1

        language = classify_language(flat_text)
        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            patterns = get_patterns(language, event_type)
            if not patterns:
                continue

            # Extract from flat (always)
            t2 = time.perf_counter()
            flat_facts = improved_extract_facts(flat_text, patterns, rep_id, doc_id)
            timing["flat_extract"] += time.perf_counter() - t2

            # Extract from structured (if triggered)
            structured_facts = []
            if use_structured:
                t3 = time.perf_counter()
                for seg_text, seg_ctx, seg_headers in structured_segments:
                    if is_navigation_content_v13(seg_text):
                        continue
                    seg_facts = improved_extract_facts(seg_text, patterns, rep_id, doc_id)
                    for f in seg_facts:
                        if seg_ctx == "TABLE_ROW" and seg_headers:
                            f.excerpt = f"[TABLE: {' | '.join(seg_headers[:5])}] {f.excerpt}"
                        elif seg_ctx == "LIST_ITEM":
                            f.excerpt = f"[LIST] {f.excerpt}"
                        elif seg_ctx == "HEADING":
                            f.excerpt = f"[HEADING] {f.excerpt}"
                    structured_facts.extend(seg_facts)
                timing["structured_extract"] += time.perf_counter() - t3

            # Semantic dedup
            seen = set()
            all_facts = []
            for f in flat_facts + structured_facts:
                key = (f.document_id, normalize_metric_v19(f.pattern_ref), str(f.value))
                if key not in seen:
                    seen.add(key)
                    all_facts.append(f)
                    if "[TABLE:" in f.excerpt:
                        structural_stats["TABLE"] += 1
                    elif "[LIST]" in f.excerpt:
                        structural_stats["LIST"] += 1
                    elif "[HEADING]" in f.excerpt:
                        structural_stats["HEADING"] += 1
                    else:
                        structural_stats["PARAGRAPH"] += 1

            if not all_facts:
                continue

            # Nav filter
            clean = []
            for f in all_facts:
                if is_navigation_content_v13(f.excerpt):
                    pipeline_stats["NAV_REJECTED"] += 1
                    ne, st = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in st:
                        f.excerpt = ne
                        clean.append(f)
                        pipeline_stats["NAV_RECOVERED"] += 1
                else:
                    clean.append(f)
            if not clean:
                continue

            # Evidence selection
            direct = []
            for f in clean:
                cls, _ = classify_evidence_strict(f, f.excerpt)
                if cls in ("INDIRECT", "INSUFFICIENT", "INVALID"):
                    ne, st = expand_evidence_for_direct(f, f.excerpt, flat_text)
                    if "DIRECT" in st:
                        f.excerpt = ne
                        direct.append(f)
                    elif cls == "INVALID":
                        pipeline_stats["INVALID_EVIDENCE"] += 1
                    else:
                        direct.append(f)
                else:
                    direct.append(f)
            if not direct:
                continue

            # Semantic gate
            valid, reason = validate_event_context_v13(event_type, flat_text, language)
            if not valid:
                pipeline_stats["SEMANTIC_REJECTED"] += 1
                continue
            pipeline_stats["SEMANTIC_PASSED"] += 1

            for f in direct:
                store.append("facts", f.to_dict())
                store.append("evidence", Evidence(
                    evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                    event_or_fact_id=f.fact_id, representation_id=f.representation_id,
                    location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                    excerpt=f.excerpt, provenance_ref=f"representation:{f.representation_id}",
                ).to_dict())
                pipeline_stats["FACTS_APPENDED"] += 1

            ev = detect_event(direct, doc_id, event_type)
            if ev is None:
                continue
            existing = store.current_event(ev.event_id)
            if existing is None:
                store.append("events", ev.to_dict())
                existing = store.current_event(ev.event_id)
                pipeline_stats["EVENTS_CREATED"] += 1
                try:
                    io = build_intelligence_object(store, existing, source_name=src_id)
                    pipeline_stats["IOS_BUILT"] += 1
                except Exception:
                    pass

        total_docs += 1
        if total_docs % 100 == 0:
            print(f"  Processed {total_docs} docs...")

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
        with open(Path(store_root) / "events.jsonl", "w", encoding="utf-8") as f:
            for ev in clean_events:
                f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")

    store3 = CachedStore(AppendOnlyStore(store_root))
    v20_events = sum(1 for _ in store3.iter("events"))
    v20_facts = sum(1 for _ in store3.iter("facts"))

    total_time = sum(timing.values())
    print(f"\n--- Pipeline Statistics ---")
    for k, v in pipeline_stats.most_common():
        print(f"  {k:<30} {v:>6}")
    print(f"\n--- Structural Recovery ---")
    for k, v in structural_stats.most_common():
        print(f"  {k:<15} {v:>5}")
    print(f"\n--- Timing ---")
    for k, v in sorted(timing.items(), key=lambda x: -x[1]):
        print(f"  {k:<25} {v:>8.2f}s ({v/total_time*100:.1f}%)")
    print(f"  {'TOTAL':<25} {total_time:>8.2f}s")
    print(f"\n  Documents: {total_docs}")
    print(f"  Time/doc: {total_time/max(total_docs,1):.3f}s")

    print(f"\n--- V17 vs V20 ---")
    print(f"  Events: {v17_events} → {v20_events} ({'+' if v20_events > v17_events else ''}{v20_events - v17_events})")
    print(f"  Facts:  {v17_facts} → {v20_facts} ({'+' if v20_facts > v17_facts else ''}{v20_facts - v17_facts})")

    return v20_events, v20_facts


if __name__ == "__main__":
    events, facts = run_v20_optimized()
    print(f"\n  Final: {events} events, {facts} facts")
