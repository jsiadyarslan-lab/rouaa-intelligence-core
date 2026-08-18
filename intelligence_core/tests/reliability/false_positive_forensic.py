"""V6 §2 — Forensic analysis of 3 remaining false positives.

For each false positive, determine:
  - document content
  - matched pattern
  - fact value
  - event_type
  - evidence excerpt
  - triggering context

Classify root cause:
  - KEYWORD_ONLY: pattern matched but document isn't about this event
  - INSUFFICIENT_CONTEXT: document has some context but not enough
  - WRONG_CONTEXT: document is about a different topic
  - WRONG_EVENT_BINDING: event type doesn't match document's primary intent
  - STALE_RULE: pattern is too broad/narrow
  - SOURCE-SPECIFIC: this source type produces documents that don't fit
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html
from intelligence_core.identity import io_id as make_io_id


FALSE_POSITIVE_IO_IDS = [
    "io-935ab64f33806484",  # monetary_policy_decision, imp-bea
    "io-39cfc3b482bba190",  # regulatory_enforcement, imp-cftc
    "io-f405b7c878fbec26",  # regulatory_enforcement, imp-bea
]


def forensic_analysis(store_root: str = "v3_corpus_store"):
    """Forensic analysis of each false positive."""
    print(f"\n{'='*70}")
    print(f"V6 §2 — False-Positive Forensic Analysis")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")
    reps_by_id = store.latest_by_id("representations", "representation_id")

    results = []

    for target_ioid in FALSE_POSITIVE_IO_IDS:
        # Find the event
        for ev in store.iter("events"):
            ioid = make_io_id(ev["event_id"], ev["event_version"])
            if ioid == target_ioid:
                doc_id = ev.get("document_id", "")
                doc = docs_by_id.get(doc_id, {})
                src_id = doc.get("source_id", "")

                # Get document content
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
                else:
                    rep = {}

                # Get facts
                facts = []
                for ref in ev.get("fact_version_snapshot", []):
                    f = store.fact_row(ref.get("fact_id"), ref.get("fact_version"))
                    if f:
                        facts.append(f)

                # Analyze
                print(f"\n--- {target_ioid} ---")
                print(f"  Event type: {ev['event_type']}")
                print(f"  Source: {src_id}")
                print(f"  Document: {doc_id}")

                if facts:
                    print(f"  Facts:")
                    for f in facts[:3]:
                        print(f"    metric={f.get('metric', '')} value={f.get('value', '')[:30]}")
                        print(f"    excerpt: {f.get('excerpt', '')[:120]}")

                print(f"\n  Document content (first 400 chars):")
                print(f"  {doc_text[:400]}")

                # Classify root cause
                root_cause = classify_root_cause(ev, doc_text, src_id)
                print(f"\n  Root cause: {root_cause['classification']}")
                print(f"  Reason: {root_cause['reason']}")

                results.append({
                    "io_id": target_ioid,
                    "event_type": ev["event_type"],
                    "source_id": src_id,
                    "document_id": doc_id,
                    "root_cause": root_cause["classification"],
                    "reason": root_cause["reason"],
                    "fix": root_cause["fix"],
                    "document_text_preview": doc_text[:500],
                    "facts": [{"metric": f.get("metric", ""), "value": str(f.get("value", ""))[:50],
                               "excerpt": f.get("excerpt", "")[:150]}
                              for f in facts[:3]],
                })
                break

    return results


def classify_root_cause(ev: dict, doc_text: str, src_id: str) -> dict:
    """Classify the root cause of a false positive."""
    event_type = ev["event_type"]
    text_lower = doc_text.lower()

    if event_type == "monetary_policy_decision":
        # Check if this is actually a monetary policy document
        has_monetary_context = bool(re.search(
            r"\b(monetary\s+policy|policy\s+rate|interest\s+rate\s+(?:decision|announcement)|"
            r"key\s+rate|base\s+rate|benchmark\s+rate|central\s+bank\s+(?:decision|statement))\b",
            text_lower
        ))
        has_decision_language = bool(re.search(
            r"\b(decid(?:e|ed|ion)|announc(?:e|ed|ement)|statement|press\s+release)\b",
            text_lower
        ))

        if not has_monetary_context and not has_decision_language:
            return {
                "classification": "KEYWORD_ONLY",
                "reason": "Document contains 'rate' keyword but has no monetary policy decision context — "
                         "it's a statistical release that happens to mention rates",
                "fix": "Require BOTH monetary policy context AND decision language before creating monetary_policy_decision event",
            }
        elif has_monetary_context and not has_decision_language:
            return {
                "classification": "INSUFFICIENT_CONTEXT",
                "reason": "Document mentions monetary policy but doesn't announce a decision",
                "fix": "Require decision/announcement language in addition to monetary policy context",
            }
        else:
            return {
                "classification": "WRONG_CONTEXT",
                "reason": "Document is about statistics, not monetary policy decisions",
                "fix": "Check document's primary intent — if it's a statistical release, don't create monetary event",
            }

    elif event_type == "regulatory_enforcement":
        # Check if this is actually an enforcement action
        has_enforcement_action = bool(re.search(
            r"\b(consent\s+order|cease\s+and\s+desist|injunction|penalty\s+(?:of|imposed)|"
            r"disgorgement|settlement|fine\s+(?:of|imposed)|charged\s+with|sued|"
            r"enforcement\s+action|enforcement\s+proceeding)\b",
            text_lower
        ))
        has_regulatory_authority = bool(re.search(
            r"\b(sec|cftc|fca|esma|consob|regulator|regulatory|commission|authority|"
            r"supervisory|enforcement\s+division)\b",
            text_lower
        ))

        if not has_enforcement_action:
            return {
                "classification": "KEYWORD_ONLY",
                "reason": "Document contains 'enforcement' keyword but doesn't describe an actual enforcement action "
                         "(no consent order, penalty, injunction, etc.)",
                "fix": "Require actual enforcement action language (consent order, penalty imposed, charged with, etc.) "
                       "not just the word 'enforcement'",
            }
        elif not has_regulatory_authority:
            return {
                "classification": "WRONG_CONTEXT",
                "reason": "Enforcement language found but no regulatory authority context",
                "fix": "Require regulatory authority context in addition to enforcement action language",
            }
        else:
            return {
                "classification": "INSUFFICIENT_CONTEXT",
                "reason": "Has some enforcement language but not enough to constitute an enforcement event",
                "fix": "Strengthen enforcement action requirements",
            }

    return {
        "classification": "UNKNOWN",
        "reason": "Could not classify root cause",
        "fix": "Manual investigation needed",
    }


if __name__ == "__main__":
    results = forensic_analysis()
    out_path = Path("intelligence_core/tests/reliability/false_positive_forensic_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
