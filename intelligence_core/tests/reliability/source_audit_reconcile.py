"""V2 §2-3 — Source Registry Audit + Health Reconciliation.

Audits all 98 source records for data quality:
  - No contradictory states (QUALIFIED while endpoint is 404/403)
  - All required fields present
  - Health states reconcile to total_sources with no overlap

Reconciliation:
  total_sources = HEALTHY + DEGRADED + STALE + BLOCKED + ENDPOINT_MOVED + NO_CONTENT + UNSUPPORTED
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.source_network.registry import SourceRegistry, HEALTH_STATES


def audit_source_records(registry_root: str = "source_registry") -> dict:
    """Audit every source record for data quality."""
    print(f"\n{'='*70}")
    print(f"V2 §2 — Source Registry Data Quality Audit")
    print(f"{'='*70}")

    registry = SourceRegistry(registry_root)
    all_sources = registry.all()
    print(f"\n  Total sources: {len(all_sources)}")

    # Required fields per directive §4
    required_fields = [
        "source_id", "institution_id", "institution_name", "country",
        "jurisdiction", "region", "source_class", "domain", "authority_level",
        "official_domain", "canonical_url", "acquisition_endpoint",
        "endpoint_type", "acquisition_method", "language", "coverage_topics",
        "frequency", "qualification_status", "health_status", "last_verified_at",
    ]

    # Audit each record
    issues = []
    for s in all_sources:
        # Check required fields
        for field in required_fields:
            val = getattr(s, field, None)
            if val is None or val == "":
                # coverage_topics is a list — check separately
                if field == "coverage_topics" and isinstance(val, list) and len(val) == 0:
                    issues.append({
                        "source_id": s.source_id,
                        "issue": f"empty required field: {field}",
                        "severity": "warning",
                    })
                elif field not in ("coverage_topics",):
                    issues.append({
                        "source_id": s.source_id,
                        "issue": f"empty required field: {field}",
                        "severity": "error",
                    })

        # Check for contradictory states
        qual = s.qualification_status
        health = s.health_status

        # QUALIFIED + (BLOCKED/ENDPOINT_MOVED/UNSUPPORTED) = contradiction
        if qual == "QUALIFIED" and health in ("BLOCKED", "ENDPOINT_MOVED", "UNSUPPORTED"):
            issues.append({
                "source_id": s.source_id,
                "issue": f"contradictory state: qualification={qual} + health={health}",
                "severity": "error",
            })

        # PRODUCTION_READY + (BLOCKED/ENDPOINT_MOVED/UNSUPPORTED/DEGRADED) = contradiction
        if qual == "PRODUCTION_READY" and health in ("BLOCKED", "ENDPOINT_MOVED", "UNSUPPORTED", "DEGRADED"):
            issues.append({
                "source_id": s.source_id,
                "issue": f"contradictory state: qualification={qual} + health={health}",
                "severity": "error",
            })

        # BLOCKED qualification + HEALTHY health = contradiction
        if qual == "BLOCKED" and health == "HEALTHY":
            issues.append({
                "source_id": s.source_id,
                "issue": f"contradictory state: qualification={qual} + health={health}",
                "severity": "error",
            })

        # REQUIRES_REMEDIATION + HEALTHY = check if endpoint was actually fixed
        if qual == "REQUIRES_REMEDIATION" and health == "HEALTHY":
            issues.append({
                "source_id": s.source_id,
                "issue": f"suspicious state: qualification={qual} + health={health} (endpoint may have recovered)",
                "severity": "warning",
            })

    # Summary
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    print(f"\n  Audit results:")
    print(f"    Errors:   {len(errors)}")
    print(f"    Warnings: {len(warnings)}")

    if errors:
        print(f"\n  Errors (first 10):")
        for e in errors[:10]:
            print(f"    {e['source_id']:<30} {e['issue']}")
    if warnings:
        print(f"\n  Warnings (first 5):")
        for w in warnings[:5]:
            print(f"    {w['source_id']:<30} {w['issue']}")

    return {
        "total_sources": len(all_sources),
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def reconcile_health_counts(registry_root: str = "source_registry") -> dict:
    """Reconcile health counts — total must equal sum of all health states."""
    print(f"\n{'='*70}")
    print(f"V2 §3 — Health Count Reconciliation")
    print(f"{'='*70}")

    registry = SourceRegistry(registry_root)
    stats = registry.stats()

    total = stats["total_sources"]
    by_health = stats["by_health"]

    print(f"\n  Total sources: {total}")
    print(f"\n  Health breakdown:")
    health_sum = 0
    for state in HEALTH_STATES:
        count = by_health.get(state, 0)
        health_sum += count
        pct = (count / total * 100) if total else 0
        print(f"    {state:<20} {count:>3}  ({pct:.1f}%)")

    # Check for overlap (sources with multiple health states — shouldn't be possible)
    # Each source has exactly one health_status field
    # But let's verify by counting all sources
    all_sources = registry.all()
    sources_with_health = sum(1 for s in all_sources if s.health_status)
    sources_without_health = sum(1 for s in all_sources if not s.health_status)

    print(f"\n  Reconciliation:")
    print(f"    Sum of health states: {health_sum}")
    print(f"    Total sources:       {total}")
    print(f"    Sources with health:  {sources_with_health}")
    print(f"    Sources without:      {sources_without_health}")

    if health_sum == total:
        print(f"    ✓ PASS: health counts reconcile (sum = total)")
        reconciled = True
    else:
        print(f"    ✗ FAIL: health counts do not reconcile (sum={health_sum} ≠ total={total})")
        reconciled = False

    # Check for unknown health states (not in HEALTH_STATES enum)
    unknown_states = [s for s in by_health if s not in HEALTH_STATES]
    if unknown_states:
        print(f"    ✗ FAIL: unknown health states: {unknown_states}")
        reconciled = False
    else:
        print(f"    ✓ PASS: all health states are in the canonical enum")

    return {
        "total_sources": total,
        "by_health": by_health,
        "health_sum": health_sum,
        "reconciled": reconciled,
        "unknown_states": unknown_states,
    }


def main():
    registry_root = sys.argv[1] if len(sys.argv) > 1 else "source_registry"

    audit = audit_source_records(registry_root)
    reconciliation = reconcile_health_counts(registry_root)

    # Save results
    out = {
        "schema_version": "1.0",
        "captured_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "audit": audit,
        "reconciliation": reconciliation,
    }
    out_path = Path("intelligence_core/tests/reliability/source_audit_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    overall = (audit["error_count"] == 0 and reconciliation["reconciled"])
    print(f"\n  Overall: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
