"""V2 §4 — Remediation Queue: Classify 52 failed sources.

For each source with qualification_status = REQUIRES_REMEDIATION or BLOCKED,
determine the specific failure class:
  - 403 Forbidden
  - 404 Not Found
  - wrong endpoint (RSS path guessed wrong)
  - moved endpoint (URL changed)
  - language barrier
  - JS-rendered (needs headless browser)
  - unsupported format
  - no content (feed empty)
  - other
"""
from __future__ import annotations
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.source_network.registry import SourceRegistry


def classify_failure(qualification_notes: str, health_status: str) -> str:
    """Classify a source failure based on its notes + health."""
    notes = (qualification_notes or "").lower()
    health = health_status or ""

    if health == "BLOCKED":
        if "403" in notes or "forbidden" in notes:
            return "403_FORBIDDEN"
        return "BLOCKED_OTHER"

    if health == "ENDPOINT_MOVED":
        if "404" in notes or "not found" in notes:
            return "404_NOT_FOUND"
        return "ENDPOINT_MOVED_OTHER"

    if health == "UNSUPPORTED":
        if "expected rss" in notes or "got html" in notes:
            return "WRONG_ENDPOINT_FORMAT"
        return "UNSUPPORTED_FORMAT"

    if health == "DEGRADED":
        if "timeout" in notes or "timed out" in notes:
            return "TIMEOUT"
        if "5xx" in notes or "server error" in notes:
            return "SERVER_ERROR"
        return "DEGRADED_OTHER"

    if "js" in notes or "javascript" in notes:
        return "JS_RENDERED"

    if "language" in notes:
        return "LANGUAGE_BARRIER"

    if "no content" in notes or "no items" in notes:
        return "NO_CONTENT"

    return "OTHER"


def process_remediation_queue(registry_root: str = "source_registry") -> dict:
    """Classify all sources in the remediation queue."""
    print(f"\n{'='*70}")
    print(f"V2 §4 — Remediation Queue Classification")
    print(f"{'='*70}")

    registry = SourceRegistry(registry_root)
    all_sources = registry.all()

    # Sources requiring remediation
    remediation_sources = [
        s for s in all_sources
        if s.qualification_status in ("REQUIRES_REMEDIATION", "BLOCKED")
    ]
    print(f"\n  Total sources in remediation queue: {len(remediation_sources)}")

    # Classify each
    classifications = []
    for s in remediation_sources:
        failure_class = classify_failure(s.qualification_notes, s.health_status)
        classifications.append({
            "source_id": s.source_id,
            "institution_name": s.institution_name,
            "country": s.country,
            "source_class": s.source_class,
            "acquisition_method": s.acquisition_method,
            "qualification_status": s.qualification_status,
            "health_status": s.health_status,
            "qualification_notes": s.qualification_notes,
            "failure_class": failure_class,
        })

    # Summary by failure class
    by_class = Counter(c["failure_class"] for c in classifications)
    print(f"\n  Failure class breakdown:")
    for cls, count in by_class.most_common():
        pct = (count / len(remediation_sources) * 100) if remediation_sources else 0
        print(f"    {cls:<25} {count:>3}  ({pct:.1f}%)")

    # By country
    by_country = Counter(c["country"] for c in classifications)
    print(f"\n  By country:")
    for country, count in by_country.most_common():
        print(f"    {country:<10} {count:>3}")

    # By source class
    by_source_class = Counter(c["source_class"] for c in classifications)
    print(f"\n  By source class:")
    for cls, count in by_source_class.most_common():
        print(f"    {cls:<30} {count:>3}")

    # By acquisition method
    by_method = Counter(c["acquisition_method"] for c in classifications)
    print(f"\n  By acquisition method:")
    for method, count in by_method.most_common():
        print(f"    {method:<10} {count:>3}")

    # Show first 10 examples per class
    print(f"\n  Examples by failure class:")
    for cls in by_class:
        examples = [c for c in classifications if c["failure_class"] == cls][:3]
        print(f"\n    {cls} ({by_class[cls]} total):")
        for e in examples:
            print(f"      {e['source_id']:<25} {e['institution_name'][:30]:<30} notes={e['qualification_notes'][:60]}")

    return {
        "total_remediation": len(remediation_sources),
        "by_class": dict(by_class),
        "by_country": dict(by_country),
        "by_source_class": dict(by_source_class),
        "by_acquisition_method": dict(by_method),
        "classifications": classifications,
    }


if __name__ == "__main__":
    result = process_remediation_queue()
    out_path = Path("intelligence_core/tests/reliability/remediation_queue_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
