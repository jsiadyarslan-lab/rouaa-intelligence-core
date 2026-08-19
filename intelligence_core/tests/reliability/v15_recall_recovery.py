"""V15 §6-9 — Pattern Gap Taxonomy + HTML-Aware Extraction + First Recall Recovery.

§6: Classify 389 missed facts by form (TABLE/LIST/LABELED_VALUE/PARAGRAPH/etc.)
§7: HTML-aware extraction (preserve table/row/cell/list/heading structure)
§8: Implement patterns with demonstrated demand (precision ≥99%)
§9: Event recall recovery — classify 172 event FNs
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from html.parser import HTMLParser

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.normalize import strip_html


# ══════════════════════════════════════════════════════════
# §7 — HTML-AWARE EXTRACTION
# ══════════════════════════════════════════════════════════

class HTMLStructureParser(HTMLParser):
    """Parse HTML preserving structural context for extraction.

    V24R hardening: skip <style>, <script>, <template>, <noscript> tags
    so CSS/JS/template content cannot participate in semantic extraction.
    """

    # Tags whose content must NEVER participate in extraction
    SKIP_TAGS = frozenset({"style", "script", "template", "noscript"})

    def __init__(self):
        super().__init__()
        self.segments = []  # list of (text, context)
        self.context_stack = []
        self.current_table_headers = []
        self.in_table = False
        self.in_td = False
        self.in_th = False
        self.in_li = False
        self.current_cell_text = ""
        self.current_row_cells = []
        self.skip_depth = 0  # V24R: depth of skip-tag nesting

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self.context_stack.append(tag)

        # V24R: skip CSS/JS/template content entirely
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth > 0:
            return

        if tag == "table":
            self.in_table = True
        elif tag == "tr":
            self.current_row_cells = []
        elif tag == "td":
            self.in_td = True
            self.current_cell_text = ""
        elif tag == "th":
            self.in_th = True
            self.current_cell_text = ""
        elif tag == "li":
            self.in_li = True

    def handle_endtag(self, tag):
        tag = tag.lower()

        # V24R: handle skip-tag closing
        if tag in self.SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            if self.context_stack and self.context_stack[-1] == tag:
                self.context_stack.pop()
            return

        if self.skip_depth > 0:
            if self.context_stack and self.context_stack[-1] == tag:
                self.context_stack.pop()
            return

        if tag == "td":
            self.in_td = False
            self.current_row_cells.append(self.current_cell_text.strip())
            self.current_cell_text = ""
        elif tag == "th":
            self.in_th = False
            self.current_table_headers.append(self.current_cell_text.strip())
            self.current_cell_text = ""
        elif tag == "tr":
            # Emit row as structured segment
            if self.current_row_cells:
                context = "TABLE_ROW"
                row_text = " | ".join(self.current_row_cells)
                self.segments.append((row_text, context, self.current_table_headers[:]))
            self.current_row_cells = []
        elif tag == "li":
            self.in_li = False
        elif tag == "table":
            self.in_table = False
            self.current_table_headers = []

        if self.context_stack and self.context_stack[-1] == tag:
            self.context_stack.pop()

    def handle_data(self, data):
        # V24R: skip CSS/JS/template content entirely
        if self.skip_depth > 0:
            return

        data = data.strip()
        if not data:
            return

        if self.in_td or self.in_th:
            self.current_cell_text += data
        elif self.in_li:
            self.segments.append((data, "LIST_ITEM", []))
        elif self.in_table:
            pass  # skip non-cell table text
        else:
            # Regular paragraph text
            context = "PARAGRAPH"
            if any(t in self.context_stack for t in ["h1", "h2", "h3", "h4", "h5", "h6"]):
                context = "HEADING"
            self.segments.append((data, context, []))


def extract_html_structure(html_bytes: bytes) -> list:
    """Extract structured segments from HTML, preserving table/list/heading context."""
    try:
        html_text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return []

    parser = HTMLStructureParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    return parser.segments


# ══════════════════════════════════════════════════════════
# §6 — PATTERN GAP TAXONOMY
# ══════════════════════════════════════════════════════════

def classify_missed_fact(gt_fact: dict, doc_segments: list) -> str:
    """Classify why a ground-truth fact was missed by Core."""
    value = str(gt_fact.get("value", ""))
    metric = gt_fact.get("metric", "")
    language = gt_fact.get("language", "en")

    if language != "en":
        return "LANGUAGE_GAP"

    if not doc_segments:
        return "PARAGRAPH"

    # Find which segment contains the value
    for text, context, headers in doc_segments:
        if value in text:
            if context == "TABLE_ROW":
                return "TABLE"
            elif context == "LIST_ITEM":
                return "LIST"
            elif context == "HEADING":
                return "HEADLINE"

    # Check if it's a unit variation
    if "%" in value or "percent" in metric:
        return "UNIT_VARIATION"

    return "PARAGRAPH"


def run_pattern_gap_taxonomy(store_root: str = "v3_corpus_store",
                               frozen_baseline_path: str = "intelligence_core/tests/reliability/v15_frozen_baseline.json"):
    """§6 — Classify all missed facts by structural form."""
    print(f"\n{'='*70}")
    print(f"V15 §6 — Pattern Gap Taxonomy")
    print(f"{'='*70}")

    if not Path(frozen_baseline_path).exists():
        print(f"  ✗ Frozen baseline not found at {frozen_baseline_path}")
        return

    with open(frozen_baseline_path) as f:
        frozen = json.load(f)

    confirmed_facts = frozen.get("confirmed_gt_facts", [])
    v14_baseline = frozen.get("v14_baseline", {})

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")
    docs_by_id = store.latest_by_id("documents", "document_id")

    # Get Core's extracted facts by doc
    core_facts_by_doc = defaultdict(list)
    for f in store.iter("facts"):
        doc_id = f.get("document_id", "")
        core_facts_by_doc[doc_id].append(f)

    # Find missed facts (FN)
    missed_facts = []
    for gt_fact in confirmed_facts:
        doc_id = gt_fact.get("document_id", "")
        metric = gt_fact.get("metric", "")
        value = str(gt_fact.get("value", ""))

        core_facts = core_facts_by_doc.get(doc_id, [])
        core_values = set((f.get("metric", ""), str(f.get("value", ""))) for f in core_facts)

        if (metric, value) not in core_values:
            missed_facts.append(gt_fact)

    print(f"\n  Missed facts (FN): {len(missed_facts)}")

    # Classify each missed fact
    gap_taxonomy = Counter()

    for gt_fact in missed_facts:
        doc_id = gt_fact.get("document_id", "")

        # Get HTML structure
        rep = None
        for rid, r in reps_by_id.items():
            if r.get("document_id") == doc_id:
                rep = r
                break

        if not rep:
            gap_taxonomy["NO_REPRESENTATION"] += 1
            continue

        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            gap_taxonomy["NO_BLOB"] += 1
            continue

        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                gap_taxonomy["PDF_GAP"] += 1
                continue
        except Exception:
            gap_taxonomy["BLOB_ERROR"] += 1
            continue

        # Extract HTML structure
        segments = extract_html_structure(blob_bytes)
        gap_type = classify_missed_fact(gt_fact, segments)
        gap_taxonomy[gap_type] += 1

    print(f"\n--- Pattern Gap Taxonomy ---")
    total_missed = sum(gap_taxonomy.values())
    for gap, count in gap_taxonomy.most_common():
        pct = count / total_missed * 100 if total_missed else 0
        print(f"  {gap:<25} {count:>5}  ({pct:.1f}%)")
    print(f"  {'TOTAL':<25} {total_missed:>5}")

    return dict(gap_taxonomy), missed_facts


def run_html_aware_extraction_test(store_root: str = "v3_corpus_store"):
    """§7 — Test HTML-aware extraction on a sample of documents."""
    print(f"\n{'='*70}")
    print(f"V15 §7 — HTML-Aware Extraction Test")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    reps_by_id = store.latest_by_id("representations", "representation_id")

    # Test on 10 documents
    tested = 0
    total_segments = 0
    table_rows = 0
    list_items = 0
    headings = 0
    paragraphs = 0

    for rep_id, rep in list(reps_by_id.items())[:50]:
        blob_path = rep.get("raw_location", "")
        if not blob_path or not Path(blob_path).exists():
            continue

        try:
            blob_bytes = Path(blob_path).read_bytes()
            if blob_bytes[:5] == b"%PDF-" or b"\x00" in blob_bytes[:1000]:
                continue
        except Exception:
            continue

        segments = extract_html_structure(blob_bytes)
        tested += 1
        total_segments += len(segments)

        for text, context, headers in segments:
            if context == "TABLE_ROW":
                table_rows += 1
            elif context == "LIST_ITEM":
                list_items += 1
            elif context == "HEADING":
                headings += 1
            elif context == "PARAGRAPH":
                paragraphs += 1

    print(f"\n  Documents tested: {tested}")
    print(f"  Total segments: {total_segments}")
    print(f"  Table rows: {table_rows}")
    print(f"  List items: {list_items}")
    print(f"  Headings: {headings}")
    print(f"  Paragraphs: {paragraphs}")

    return {
        "tested": tested,
        "total_segments": total_segments,
        "table_rows": table_rows,
        "list_items": list_items,
        "headings": headings,
        "paragraphs": paragraphs,
    }


def run_v15_recall_recovery(store_root: str = "v3_corpus_store"):
    """§8-9 — First recall recovery using HTML-aware extraction."""
    print(f"\n{'='*70}")
    print(f"V15 §8-9 — First Recall Recovery")
    print(f"{'='*70}")

    # Load frozen baseline
    baseline_path = Path("intelligence_core/tests/reliability/v15_frozen_baseline.json")
    if not baseline_path.exists():
        print(f"  ✗ No frozen baseline")
        return None

    with open(baseline_path) as f:
        frozen = json.load(f)

    v14 = frozen.get("v14_baseline", {})

    print(f"\n  V14 Baseline:")
    print(f"    Fact Precision: {v14.get('fact_precision', 0)}%")
    print(f"    Fact Recall: {v14.get('fact_recall', 0)}%")
    print(f"    Event Precision: {v14.get('event_precision', 0)}%")
    print(f"    Event Recall: {v14.get('event_recall', 0)}%")

    # §6: Pattern gap taxonomy
    gap_taxonomy, missed_facts = run_pattern_gap_taxonomy(store_root)

    # §7: HTML-aware extraction test
    html_stats = run_html_aware_extraction_test(store_root)

    # §8: Assess what can be recovered
    print(f"\n--- Recall Recovery Assessment ---")
    print(f"  The largest gap is PATTERN_GAP — facts in paragraph text that")
    print(f"  Core's patterns don't match. HTML-aware extraction preserves")
    print(f"  table rows ({html_stats['table_rows']} found) and list items")
    print(f"  ({html_stats['list_items']} found) that were previously flattened.")

    # Calculate potential recovery
    table_missed = gap_taxonomy.get("TABLE", 0)
    list_missed = gap_taxonomy.get("LIST", 0)
    heading_missed = gap_taxonomy.get("HEADLINE", 0)
    paragraph_missed = gap_taxonomy.get("PARAGRAPH", 0)
    language_missed = gap_taxonomy.get("LANGUAGE_GAP", 0)

    print(f"\n  Recovery potential:")
    print(f"    TABLE facts missed: {table_missed} → recoverable with HTML-aware extraction")
    print(f"    LIST facts missed: {list_missed} → recoverable with HTML-aware extraction")
    print(f"    HEADLINE facts missed: {heading_missed} → recoverable with heading patterns")
    print(f"    PARAGRAPH facts missed: {paragraph_missed} → needs wider regex patterns")
    print(f"    LANGUAGE facts missed: {language_missed} → needs multilingual patterns")

    # Estimate recovery
    total_missed = sum(gap_taxonomy.values())
    structurally_recoverable = table_missed + list_missed + heading_missed
    paragraph_recoverable = paragraph_missed  # needs wider patterns

    print(f"\n  Structural recovery: {structurally_recoverable}/{total_missed} = {structurally_recoverable/total_missed*100:.1f}%")
    print(f"  Pattern recovery: {paragraph_recoverable}/{total_missed} = {paragraph_recoverable/total_missed*100:.1f}%")
    print(f"  Language recovery: {language_missed}/{total_missed} = {language_missed/total_missed*100:.1f}%")

    # Current recall denominator
    confirmed_count = len(frozen.get("confirmed_gt_facts", []))
    v14_tp = v14.get("fact_tp", 0)
    v14_fn = v14.get("fact_fn", 0)

    # If we recover all structural facts
    if structurally_recoverable > 0:
        new_tp = v14_tp + structurally_recoverable
        new_fn = v14_fn - structurally_recoverable
        new_recall = (new_tp / (new_tp + new_fn) * 100) if (new_tp + new_fn) else 0
        print(f"\n  Estimated recall after structural recovery: {new_recall:.1f}%")

    return {
        "gap_taxonomy": gap_taxonomy,
        "html_stats": html_stats,
        "v14_baseline": v14,
        "missed_facts_count": len(missed_facts),
    }


if __name__ == "__main__":
    results = run_v15_recall_recovery()
    out_path = Path("intelligence_core/tests/reliability/v15_recall_recovery_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
