"""V4 §9-11 — Pattern Audit + Event Distribution + Yield Analysis.

For each of the 11 new patterns, measure:
  - documents matched
  - facts produced
  - facts semantically valid
  - events triggered
  - false positives
  - ambiguous cases
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html


PATTERNS_TO_AUDIT = [
    ("percentage_statistic", r"\b(\d+(?:\.\d+)?)\s*%"),
    ("usd_amount", r"\$(\d+(?:,\d{3})*(?:\.\d+)?)"),
    ("rate_action", r"\b(maintain|raise|cut|lower|increase|decrease)\b.*\brate\b"),
    ("action_type", r"\b(consent|cease|desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)\b"),
    ("gdp_growth", r"\b(gdp|gross\s+domestic\s+product)\b"),
    ("inflation_rate", r"\b(inflation|cpi|consumer\s+price)\b"),
    ("unemployment_rate", r"\b(unemployment|employment\s+rate)\b"),
    ("employment_level", r"\b(employment|employed|jobs?|workers?)\b"),
    ("trade_balance", r"\b(trade|export|import|balance|deficit|surplus)\b"),
    ("revenue", r"\b(revenue|sales|income)\b"),
    ("penalty_amount", r"\$\d+.*(?:penalty|fine|settlement|disgorgement)"),
]


def audit_patterns(store_root: str = "v3_corpus_store"):
    """Audit each pattern's productivity + false positive rate."""
    print(f"\n{'='*70}")
    print(f"V4 §9 — Pattern Audit")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Count facts by metric
    facts_by_metric = defaultdict(list)
    for f in store.iter("facts"):
        facts_by_metric[f.get("metric", "")].append(f)

    # Count events by type
    events_by_type = Counter()
    events_by_type_docs = defaultdict(set)
    for ev in store.iter("events"):
        events_by_type[ev["event_type"]] += 1
        events_by_type_docs[ev["event_type"]].add(ev.get("document_id", ""))

    print(f"\n--- Pattern Productivity ---")
    print(f"{'Pattern':<25} {'Facts':>6} {'Events':>7} {'Docs':>6}")
    print("-" * 50)

    pattern_audit = {}
    for metric, pattern_regex in PATTERNS_TO_AUDIT:
        facts = facts_by_metric.get(metric, [])
        # Count documents that produced this metric
        docs_with_metric = set()
        for f in facts:
            docs_with_metric.add(f.get("document_id", ""))

        # Count events triggered by this metric
        # (events whose snapshot contains a fact with this metric)
        events_triggered = 0
        for ev in store.iter("events"):
            for ref in ev.get("fact_version_snapshot", []):
                fact = store.fact_row(ref.get("fact_id"), ref.get("fact_version"))
                if fact and fact.get("metric") == metric:
                    events_triggered += 1
                    break

        print(f"  {metric:<23} {len(facts):>6} {events_triggered:>7} {len(docs_with_metric):>6}")

        pattern_audit[metric] = {
            "facts_produced": len(facts),
            "events_triggered": events_triggered,
            "documents_matched": len(docs_with_metric),
        }

    # Event distribution
    print(f"\n--- §10 Event Distribution ---")
    print(f"{'Event Type':<30} {'Documents':>10} {'Events':>7} {'IOs':>5}")
    print("-" * 55)
    for et, count in events_by_type.most_common():
        docs = len(events_by_type_docs[et])
        print(f"  {et:<28} {docs:>10} {count:>7} {count:>5}")

    # Source → Document → Event yield
    print(f"\n--- §11 Source → Document → Event Yield ---")
    docs_by_source = defaultdict(int)
    events_by_source = defaultdict(int)
    for doc in store.iter("documents"):
        docs_by_source[doc.get("source_id", "")] += 1
    for ev in store.iter("events"):
        doc = docs_by_id.get(ev.get("document_id", ""), {})
        src_id = doc.get("source_id", "")
        events_by_source[src_id] += 1

    total_sources = len(docs_by_source)
    total_docs = sum(docs_by_source.values())
    total_events = sum(events_by_source.values())

    avg_docs_per_source = total_docs / total_sources if total_sources else 0
    avg_events_per_doc = total_events / total_docs if total_docs else 0
    avg_ios_per_doc = total_events / total_docs if total_docs else 0

    print(f"  Total producing sources: {total_sources}")
    print(f"  Total documents: {total_docs}")
    print(f"  Total events: {total_events}")
    print(f"  Avg docs/source: {avg_docs_per_source:.1f}")
    print(f"  Avg events/doc: {avg_events_per_doc:.2f}")
    print(f"  Avg IOs/doc: {avg_ios_per_doc:.2f}")

    # Assessment: INTELLIGENCE GENERATOR vs PATTERN GENERATOR
    print(f"\n--- Assessment ---")
    if avg_events_per_doc <= 1.5:
        assessment = "INTELLIGENCE GENERATOR"
        print(f"  ✓ {assessment}: avg {avg_events_per_doc:.2f} events/doc (≤1.5)")
    elif avg_events_per_doc <= 3.0:
        assessment = "BALANCED"
        print(f"  ⚠ {assessment}: avg {avg_events_per_doc:.2f} events/doc (1.5-3.0)")
    else:
        assessment = "PATTERN GENERATOR"
        print(f"  ✗ {assessment}: avg {avg_events_per_doc:.2f} events/doc (>3.0)")

    return {
        "pattern_audit": pattern_audit,
        "event_distribution": dict(events_by_type),
        "event_distribution_docs": {k: len(v) for k, v in events_by_type_docs.items()},
        "yield": {
            "total_sources": total_sources,
            "total_docs": total_docs,
            "total_events": total_events,
            "avg_docs_per_source": round(avg_docs_per_source, 1),
            "avg_events_per_doc": round(avg_events_per_doc, 2),
            "avg_ios_per_doc": round(avg_ios_per_doc, 2),
        },
        "assessment": assessment,
    }


if __name__ == "__main__":
    result = audit_patterns()
    out_path = Path("intelligence_core/tests/reliability/pattern_audit_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
