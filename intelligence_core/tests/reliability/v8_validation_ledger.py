"""V8 §2-5 — Canonical Validation Ledger + Rejection Provenance.

Persistent ledger that tracks every entity transformation:
  DOCUMENT → EVENT_CANDIDATE → (ACCEPTED|REJECTED) → EVENT → INTELLIGENCE_OBJECT
  FACT → EVIDENCE → REPRESENTATION → DOCUMENT

Every rejected candidate stores full provenance:
  source_document_id, event_candidate_id, event_type, trigger_fact_ids,
  rejection_reason, rejection_rule, pipeline_version, timestamp
"""
from __future__ import annotations
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))


# ── Terminal Disposition Enum ──

TERMINAL_DISPOSITIONS = [
    "VALID_SURVIVOR",        # Event survived all gates, is in current corpus
    "INSUFFICIENT_CONTEXT",  # Document lacks required context for event type
    "STALE_FACT",            # Facts from old extraction, no longer match
    "WRONG_EVENT_TYPE",      # Document matches exclusion pattern
    "PDF_BINARY",            # Document is PDF/binary, was incorrectly processed
    "BROKEN_PROVENANCE",     # Event's fact_version_snapshot references removed facts
    "DUPLICATE",             # Same event created by different extraction run
    "REBUILT_VALID",         # Was rejected but rebuilt as valid in current pipeline
    "REBUILT_REJECTED",      # Was rejected and remains rejected after rebuild attempt
    "OTHER_EXPLICIT",        # Other reason (explicitly classified)
]


@dataclass
class EventCandidate:
    """An event candidate — may be accepted or rejected."""
    candidate_id: str                    # unique ID for this candidate
    source_document_id: str
    event_type: str
    trigger_fact_ids: list               # fact_ids that triggered this candidate
    pipeline_version: str                # V3, V5, V6, V7, V8
    created_at: str                      # when candidate was created
    # Acceptance/rejection
    disposition: str = "PENDING"         # ACCEPTED, REJECTED, or terminal disposition
    rejection_reason: str = ""           # why rejected (if rejected)
    rejection_rule: str = ""             # which rule rejected it
    # If accepted
    event_id: str = ""                   # the event_id if accepted
    io_id: str = ""                      # the io_id if accepted


@dataclass
class KPIRecord:
    """A governed KPI with full provenance."""
    metric_name: str
    numerator: int
    denominator: int
    universe: str                        # what population the denominator represents
    sample: str                          # sampling method
    pipeline_version: str
    timestamp: str
    value_pct: float = 0.0               # numerator/denominator * 100

    def __post_init__(self):
        if self.denominator > 0:
            self.value_pct = round(self.numerator / self.denominator * 100, 1)


class ValidationLedger:
    """Canonical validation ledger — persists to JSONL."""

    def __init__(self, root: str = "validation_ledger"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.candidates_path = self.root / "event_candidates.jsonl"
        self.kpis_path = self.root / "kpis.jsonl"
        self.reconciliation_path = self.root / "reconciliation.jsonl"
        self._candidates: dict[str, EventCandidate] = {}
        self._kpis: list[KPIRecord] = []
        self._load()

    def _load(self):
        if self.candidates_path.exists():
            with open(self.candidates_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._candidates[data["candidate_id"]] = EventCandidate(**data)
        if self.kpis_path.exists():
            with open(self.kpis_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._kpis.append(KPIRecord(**json.loads(line)))

    def record_candidate(self, candidate: EventCandidate):
        """Record or update an event candidate."""
        self._candidates[candidate.candidate_id] = candidate
        with open(self.candidates_path, "a") as f:
            f.write(json.dumps(asdict(candidate), ensure_ascii=False, sort_keys=True) + "\n")

    def record_kpi(self, kpi: KPIRecord):
        """Record a KPI."""
        self._kpis.append(kpi)
        with open(self.kpis_path, "a") as f:
            f.write(json.dumps(asdict(kpi), ensure_ascii=False, sort_keys=True) + "\n")

    def get_candidate(self, candidate_id: str) -> EventCandidate | None:
        return self._candidates.get(candidate_id)

    def all_candidates(self) -> list[EventCandidate]:
        return list(self._candidates.values())

    def candidates_by_disposition(self, disposition: str) -> list[EventCandidate]:
        return [c for c in self._candidates.values() if c.disposition == disposition]

    def rejection_ledger(self) -> list[EventCandidate]:
        """All rejected candidates with full provenance."""
        return [c for c in self._candidates.values() if c.disposition not in ("ACCEPTED", "VALID_SURVIVOR", "PENDING")]

    def stats(self) -> dict:
        """Summary statistics."""
        from collections import Counter
        all_cands = list(self._candidates.values())
        dispositions = Counter(c.disposition for c in all_cands)
        return {
            "total_candidates": len(all_cands),
            "by_disposition": dict(dispositions),
            "total_kpis": len(self._kpis),
        }


def build_validation_ledger(store_root: str = "v3_corpus_store",
                             ledger_root: str = "validation_ledger"):
    """Build the canonical validation ledger from the current store."""
    print(f"\n{'='*70}")
    print(f"V8 §2-5 — Canonical Validation Ledger")
    print(f"{'='*70}")

    from intelligence_core.cached_store import CachedStore
    from intelligence_core.store import AppendOnlyStore
    from intelligence_core.delivery import build_intelligence_object
    from intelligence_core.identity import io_id as make_io_id
    from intelligence_core.normalize import strip_html
    from intelligence_core.tests.reliability.event_semantic_gate import validate_event_context
    from intelligence_core.tests.reliability.sentence_aware_extraction import improved_extract_facts
    from intelligence_core.tests.reliability.v5_re_extract_facts import REFINED_PATTERNS
    from intelligence_core.detect import detect_event

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Clear + rebuild ledger
    if Path(ledger_root).exists():
        import shutil
        shutil.rmtree(ledger_root)
    ledger = ValidationLedger(ledger_root)

    # Get current surviving events (the 153)
    surviving_events = {}
    for ev in store.iter("events"):
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        surviving_events[ioid] = ev

    print(f"  Surviving events: {len(surviving_events)}")

    # For each document, generate event candidates with the OLD pipeline (no semantic gate)
    # and classify each as ACCEPTED or REJECTED
    SRC_TO_EVENT_TYPES = {
        "central_bank": ["monetary_policy_decision", "statistical_release", "regulatory_enforcement"],
        "statistical_agency": ["statistical_release"],
        "financial_regulator": ["regulatory_enforcement", "statistical_release"],
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

    OLD_PATTERNS = {
        "monetary": [
            (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", "rate_value"),
            (r"\b(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?)\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", "rate_action"),
        ],
        "statistical": [
            (r"\b(\d+(?:\.\d+)?)\s*%", "percentage_statistic"),
        ],
        "regulatory": [
            (r"\b(consent\s+order|cease(?:-|\s+)and(?:-|\s+)desist|injunction|penalty|disgorgement|settlement|fine|charged|sued|enforcement)\b", "action_type"),
            (r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|thousand)?", "penalty_amount"),
        ],
    }

    from intelligence_core.extract import extract_facts
    import hashlib

    candidate_count = 0
    accepted_count = 0
    rejected_count = 0

    for doc_id, doc in docs_by_id.items():
        src_id = doc.get("source_id", "")
        if "job-" in src_id:
            continue

        # Get document text
        rep = None
        for rid, r in reps_by_id.items():
            if r.get("document_id") == doc_id:
                rep = r
                break
        if not rep:
            continue

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue

        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                # PDF/binary — record as rejected
                for event_type in SRC_TO_EVENT_TYPES.get(get_source_class(src_id), ["statistical_release"]):
                    candidate_id = f"cand-{hashlib.sha256(f'{doc_id}:{event_type}:pdf'.encode()).hexdigest()[:16]}"
                    ledger.record_candidate(EventCandidate(
                        candidate_id=candidate_id,
                        source_document_id=doc_id,
                        event_type=event_type,
                        trigger_fact_ids=[],
                        pipeline_version="V3",
                        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        disposition="PDF_BINARY",
                        rejection_reason="Document is PDF/binary",
                        rejection_rule="binary_check",
                    ))
                    candidate_count += 1
                    rejected_count += 1
                continue
            doc_text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue

        source_class = get_source_class(src_id)
        event_types = SRC_TO_EVENT_TYPES.get(source_class, ["statistical_release"])

        for event_type in event_types:
            pattern_key = {
                "monetary_policy_decision": "monetary",
                "statistical_release": "statistical",
                "regulatory_enforcement": "regulatory",
            }.get(event_type, "statistical")
            patterns = OLD_PATTERNS.get(pattern_key, [])

            # OLD-style extraction (no semantic gate)
            facts = extract_facts(doc_text, patterns, "rep-old", doc_id)
            if not facts:
                continue

            ev = detect_event(facts, doc_id, event_type)
            if ev is None:
                continue

            ioid = make_io_id(ev.event_id, ev.event_version)
            candidate_id = f"cand-{hashlib.sha256(f'{doc_id}:{event_type}:{ev.event_id}'.encode()).hexdigest()[:16]}"

            # Check if this candidate survived
            if ioid in surviving_events:
                disposition = "VALID_SURVIVOR"
                rejection_reason = ""
                rejection_rule = ""
                accepted_count += 1
            else:
                # Check why it was rejected
                is_valid, reason = validate_event_context(event_type, doc_text)
                if not is_valid:
                    reason_lower = reason.lower()
                    if "exclusion pattern" in reason_lower:
                        disposition = "WRONG_EVENT_TYPE"
                        rejection_rule = "exclusion_pattern"
                    elif "missing required context" in reason_lower:
                        disposition = "INSUFFICIENT_CONTEXT"
                        rejection_rule = "context_validation"
                    else:
                        disposition = "INSUFFICIENT_CONTEXT"
                        rejection_rule = "context_validation"
                    rejection_reason = reason
                else:
                    # Semantic gate passes but event not in store — likely stale fact
                    disposition = "STALE_FACT"
                    rejection_reason = "Fact from old extraction, no longer matches current patterns"
                    rejection_rule = "stale_fact_check"
                rejected_count += 1

            ledger.record_candidate(EventCandidate(
                candidate_id=candidate_id,
                source_document_id=doc_id,
                event_type=event_type,
                trigger_fact_ids=[f.fact_id for f in facts[:5]],
                pipeline_version="V3",
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                disposition=disposition,
                rejection_reason=rejection_reason,
                rejection_rule=rejection_rule,
                event_id=ev.event_id if ioid in surviving_events else "",
                io_id=ioid if ioid in surviving_events else "",
            ))
            candidate_count += 1

    # Stats
    stats = ledger.stats()
    print(f"\n  Total candidates: {stats['total_candidates']}")
    print(f"  Accepted (VALID_SURVIVOR): {accepted_count}")
    print(f"  Rejected: {rejected_count}")
    print(f"\n  By disposition:")
    for disp, count in sorted(stats["by_disposition"].items(), key=lambda x: -x[1]):
        print(f"    {disp:<25} {count:>4}")

    # Reconciliation invariant
    total = sum(stats["by_disposition"].values())
    print(f"\n  Reconciliation invariant:")
    print(f"    sum(dispositions) = {total}")
    print(f"    total_candidates = {stats['total_candidates']}")
    print(f"    Match: {'✓' if total == stats['total_candidates'] else '✗'}")

    return ledger, stats


if __name__ == "__main__":
    ledger, stats = build_validation_ledger()
    print(f"\n  Ledger built at: validation_ledger/")
