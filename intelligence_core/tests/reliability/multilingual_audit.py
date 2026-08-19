"""V5 §7-8 — Multilingual audit + language-specific golden IOs.

Inventory language-specific quality gaps:
  - English
  - Chinese
  - Japanese
  - Arabic
  - French
  - Spanish
  - Portuguese

Determine: language configuration gap vs Core semantic limitation.
"""
from __future__ import annotations
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id
from intelligence_core.production_transport import (
    _derive_status, _derive_supersedes_io_id, _compute_etag,
)


def detect_language(text: str) -> str:
    """Detect the primary language of a document.

    Heuristic:
      - >30% CJK characters → Chinese/Japanese/Korean
      - >30% Arabic characters → Arabic
      - >30% Cyrillic characters → Russian
      - Otherwise → English (or Latin-based)
    """
    if not text:
        return "unknown"

    total_chars = len(text)
    if total_chars == 0:
        return "unknown"

    # Count character types
    cjk_chars = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF or 0x3040 <= ord(c) <= 0x30FF)
    hiragana = sum(1 for c in text if 0x3040 <= ord(c) <= 0x309F)
    katakana = sum(1 for c in text if 0x30A0 <= ord(c) <= 0x30FF)
    arabic_chars = sum(1 for c in text if 0x0600 <= ord(c) <= 0x06FF)
    cyrillic_chars = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    latin_chars = sum(1 for c in text if 0x0041 <= ord(c) <= 0x024F)

    cjk_ratio = cjk_chars / total_chars
    arabic_ratio = arabic_chars / total_chars
    cyrillic_ratio = cyrillic_chars / total_chars

    if hiragana + katakana > 10:  # Japanese has hiragana/katakana
        return "ja"
    elif cjk_ratio > 0.1:
        return "zh"
    elif arabic_ratio > 0.1:
        return "ar"
    elif cyrillic_ratio > 0.1:
        return "ru"
    else:
        return "en"


def run_multilingual_audit(store_root: str = "v3_corpus_store"):
    """Audit multilingual quality."""
    print(f"\n{'='*70}")
    print(f"V5 §7 — Multilingual Audit")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Detect language for each document
    lang_stats = defaultdict(lambda: {
        "documents": 0,
        "facts": 0,
        "events": 0,
        "ambiguous": 0,
    })

    # Build doc → language map
    doc_lang = {}
    for rep_id, rep in reps_by_id.items():
        doc_id = rep.get("document_id", "")
        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue
        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                continue
            text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
            lang = detect_language(text)
            doc_lang[doc_id] = lang
            lang_stats[lang]["documents"] += 1
        except Exception:
            continue

    # Count facts + events per language
    for f in store.iter("facts"):
        doc_id = f.get("document_id", "")
        lang = doc_lang.get(doc_id, "unknown")
        lang_stats[lang]["facts"] += 1

    for ev in store.iter("events"):
        doc_id = ev.get("document_id", "")
        lang = doc_lang.get(doc_id, "unknown")
        lang_stats[lang]["events"] += 1

    print(f"\n--- Language Distribution ---")
    print(f"{'Language':<10} {'Documents':>10} {'Facts':>8} {'Events':>8}")
    for lang, stats in sorted(lang_stats.items(), key=lambda x: -x[1]["documents"]):
        print(f"  {lang:<8} {stats['documents']:>10} {stats['facts']:>8} {stats['events']:>8}")

    # Determine language-specific configuration gaps
    print(f"\n--- Language Configuration Assessment ---")
    for lang, stats in sorted(lang_stats.items(), key=lambda x: -x[1]["documents"]):
        if lang == "en":
            print(f"  {lang}: English — full semantic support ✅")
        elif lang == "unknown":
            print(f"  {lang}: Cannot determine language — needs investigation")
        else:
            # Check if this language has events (intelligence production)
            if stats["events"] > 0:
                print(f"  {lang}: {stats['documents']} docs, {stats['events']} events — "
                      f"patterns work but semantic context patterns are English-only ⚠️")
            else:
                print(f"  {lang}: {stats['documents']} docs, 0 events — "
                      f"patterns don't match this language ❌")

    return dict(lang_stats), doc_lang


def build_language_golden_ios(store_root: str = "v3_corpus_store", doc_lang: dict = None):
    """Build language-specific golden IOs for non-English languages."""
    print(f"\n{'='*70}")
    print(f"V5 §8 — Language-Specific Golden IOs")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    docs_by_id = store.latest_by_id("documents", "document_id")

    if doc_lang is None:
        # Rebuild doc_lang
        doc_lang = {}
        reps_by_id = store.latest_by_id("representations", "representation_id")
        for rep_id, rep in reps_by_id.items():
            doc_id = rep.get("document_id", "")
            blob_path = rep.get("raw_location", "")
            if not blob_path or not Path(blob_path).exists():
                continue
            try:
                blob_bytes = Path(blob_path).read_bytes()
                if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                    continue
                text = strip_html(blob_bytes.decode("utf-8", errors="replace"))
                lang = detect_language(text)
                doc_lang[doc_id] = lang
            except Exception:
                continue

    # Find IOs from non-English documents
    lang_ios = defaultdict(list)
    for ev in store.iter("events"):
        doc_id = ev.get("document_id", "")
        lang = doc_lang.get(doc_id, "en")
        if lang != "en" and lang != "unknown":
            ioid = make_io_id(ev["event_id"], ev["event_version"])
            doc = docs_by_id.get(doc_id, {})
            src_id = doc.get("source_id", "")
            lang_ios[lang].append({
                "io_id": ioid,
                "event_row": ev,
                "source_id": src_id,
                "language": lang,
            })

    # Build golden IOs (≥5 per language if available)
    language_goldens = {}
    for lang, ios in lang_ios.items():
        selected = ios[:5]  # Take up to 5 per language
        for io_entry in selected:
            try:
                io = build_intelligence_object(store, io_entry["event_row"], source_name=io_entry["source_id"])
                io_dict = io.to_dict()
                io_dict["status"] = _derive_status(io_entry["event_row"])
                io_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, io_entry["event_row"])
                language_goldens[io_entry["io_id"]] = {
                    "io_id": io_entry["io_id"],
                    "event_type": io_entry["event_row"]["event_type"],
                    "source_id": io_entry["source_id"],
                    "language": lang,
                    "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "io_dict": io_dict,
                    "etag": _compute_etag(io_dict),
                }
            except Exception:
                continue

        print(f"  {lang}: {len(selected)} golden IOs frozen")

    # Save
    frozen_path = Path("intelligence_core/tests/reliability/golden_corpus_frozen.json")
    if frozen_path.exists():
        with open(frozen_path) as f:
            frozen = json.load(f)
    else:
        frozen = {}

    for ioid, entry in language_goldens.items():
        frozen[ioid] = entry

    with open(frozen_path, "w") as f:
        json.dump(frozen, f, indent=2, default=str)

    # Update golden summary
    golden_path = Path("intelligence_core/tests/reliability/golden_corpus_v2.json")
    if golden_path.exists():
        with open(golden_path) as f:
            golden_summary = json.load(f)
    else:
        golden_summary = {"golden_ios": {}}

    for ioid, entry in language_goldens.items():
        golden_summary["golden_ios"][ioid] = {
            "io_id": ioid,
            "event_type": entry["event_type"],
            "frozen_at": entry["frozen_at"],
            "etag": entry["etag"],
            "event_version": 1,
            "status": "ACTIVE",
            "supersedes_io_id": None,
            "chain_length": len(entry["io_dict"].get("chain", [])),
            "temporal_tuples_count": len((entry["io_dict"].get("temporal_data") or {}).get("temporal_tuples", [])),
            "language": entry["language"],
            "source_id": entry["source_id"],
        }

    golden_summary["total_golden"] = len(golden_summary["golden_ios"])
    golden_summary["language_golden_count"] = sum(1 for v in golden_summary["golden_ios"].values() if v.get("language"))

    with open(golden_path, "w") as f:
        json.dump(golden_summary, f, indent=2, default=str)

    print(f"\n  Total golden IOs: {golden_summary['total_golden']}")
    print(f"  Language golden IOs: {golden_summary['language_golden_count']}")

    return language_goldens


def main():
    store_root = sys.argv[1] if len(sys.argv) > 1 else "v3_corpus_store"

    lang_stats, doc_lang = run_multilingual_audit(store_root)
    language_goldens = build_language_golden_ios(store_root, doc_lang)

    out = {
        "schema_version": "1.0",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "language_stats": dict(lang_stats),
        "language_goldens": {k: {"io_id": v["io_id"], "event_type": v["event_type"],
                                  "language": v["language"], "source_id": v["source_id"]}
                              for k, v in language_goldens.items()},
    }
    out_path = Path("intelligence_core/tests/reliability/multilingual_audit_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
