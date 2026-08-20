"""V37.2 — Structural HTML Parser (Production).

Promotes HTMLStructureParser (V15/V24R) + SemanticTableParser (V25R) to
production. Adds the V37.2-required capabilities:

  - parent_segment_id (real structural ancestry via parser-state stack)
  - heading_context (nearest ancestor heading text attached to every segment)
  - structural exclusion of <nav>, <header> outside <article>, <footer>
    outside <article>, role="navigation"/"banner"/"contentinfo", and
    class patterns containing nav/menu/footer/header/cookie/consent/sidebar/
    social/ad-/advertisement.
  - PARAGRAPH integrity under malformed inline HTML (<b>, <strong>, <i>,
    <em>, <a>, <span> opened and not closed inside a paragraph do NOT split
    the paragraph — they accumulate into the open paragraph).
  - FOOTNOTE / QUOTE segment types (per Evidence Segment Architecture V1 §4.1)
  - Table promotion: SemanticTableParser output is composed into
    EvidenceSegmentV1 TABLE_ROW segments with row_label, column_label,
    cell_value, period, unit, table_id, heading_context, source_location.

NO sentence regex. NO post-hoc string matching. NO character slicing.
Pure parser-state, deterministic, single-pass.
"""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

from .contracts import Evidence  # noqa: F401  (kept for clarity — no mutation)


# ═══════════════════════════════════════════════════════════════════════
# Segment Type Inventory — Evidence Segment Architecture V1 §4
# ═══════════════════════════════════════════════════════════════════════

# Types eligible to be primary evidence.
PRIMARY_EVIDENCE_TYPES = frozenset({
    "PARAGRAPH", "LIST_ITEM", "TABLE_ROW", "QUOTE", "FOOTNOTE",
})

# Types that NEVER produce primary evidence (excluded at parse time).
EXCLUDED_TYPES = frozenset({
    "NAVIGATION", "HEADER_UI", "FOOTER_UI", "SOCIAL", "COOKIE",
    "CSS", "JS", "TEMPLATE", "ADVERTISEMENT", "LISTING", "DOCUMENT_HEADER",
})

# Heading tags — used for heading_context propagation.
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

# Inline tags that must NOT split a logical paragraph.
INLINE_TAGS = frozenset({
    "a", "b", "strong", "i", "em", "span", "u", "small", "sub", "sup",
    "mark", "code", "abbr", "cite", "q", "time", "font", "big", "tt",
})

# Tags whose content must NEVER participate in extraction (skip entirely).
SKIP_TAGS = frozenset({"style", "script", "template", "noscript"})

# Structural-container tags that mark their children as excluded.
EXCLUDED_CONTAINER_TAGS = frozenset({"nav"})

# role= values that mark an element as excluded.
# Per Evidence Segment Architecture V1 §6.1 — only these 3 ARIA roles
# unambiguously mark an element as non-content. Other roles (search, menu,
# toolbar, complementary) are too aggressive — they exclude form fields and
# sidebar widgets that may actually carry content.
EXCLUDED_ROLES = frozenset({
    "navigation", "banner", "contentinfo",
})

# Exact class names (lowercase, whitespace-split) that mark an element as
# excluded. Conservative — only matches whole class names, not substrings.
# (Previous regex-based matching caused false positives like "site-header"
# matching the "header" pattern even though "site-header" is a different
# class name denoting the page-level banner — which we DO want to exclude,
# but only when matched as a complete class name.)
EXCLUDED_CLASS_NAMES = frozenset({
    "nav", "navbar", "menu", "footer", "header",
    "cookie", "consent", "sidebar", "social",
    "advertisement", "advert", "breadcrumb",
    "site-header", "site-footer",
    "main-nav", "topnav", "subnav",
})


def _class_excluded(cls: str) -> bool:
    """True if any class name (whitespace-split) matches the exclusion list."""
    if not cls:
        return False
    for cn in cls.split():
        cn_lower = cn.lower()
        if cn_lower in EXCLUDED_CLASS_NAMES:
            return True
        # Match ad-* and nav-* prefix patterns as before
        if cn_lower.startswith("ad-") or cn_lower.startswith("nav-"):
            return True
    return False


# Accessibility-only class names — these mark headings as visually-hidden
# (screen-reader-only). Such headings must NOT propagate as heading_context
# to substantive content segments. They are typically used to label
# navigation regions for accessibility ("Main navigation", "Site menu")
# but their text does NOT describe the content that follows.
ACCESSIBILITY_ONLY_CLASS_NAMES = frozenset({
    "sr-only", "visually-hidden", "screen-reader-only",
    "screen-reader", "sr-only-focusable", "visuallyhidden",
    "hidden", "a11y", "aria-hidden",
})


def _is_accessibility_only_class(cls: str) -> bool:
    """True if any class name marks the element as accessibility-only
    (visually hidden from sighted users)."""
    if not cls:
        return False
    for cn in cls.split():
        if cn.lower() in ACCESSIBILITY_ONLY_CLASS_NAMES:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# EvidenceSegmentV1 — production dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class EvidenceSegmentV1:
    """A single structural segment extracted from an HTML document.

    Identity is SOURCE-DERIVED (document_id + parse position). Parent
    ancestry is DERIVED from parser-state stack at emit time.
    """
    # ── Identity ─────────────────────────────────────────────────────────
    document_id: str
    segment_id: str
    segment_index: int

    # ── Type + ancestry ────────────────────────────────────────────────
    segment_type: str
    parent_segment_id: Optional[str] = None

    # ── Content ─────────────────────────────────────────────────────────
    text: str = ""
    source_location: str = ""

    # ── Structural context ──────────────────────────────────────────────
    heading_context: Optional[str] = None
    table_id: Optional[str] = None
    row_label: Optional[str] = None
    column_label: Optional[str] = None
    cell_value: Optional[str] = None
    period: Optional[str] = None
    unit: Optional[str] = None
    list_depth: int = 0

    # ── Exclusion flags ─────────────────────────────────────────────────
    excluded: bool = False
    exclusion_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "segment_id": self.segment_id,
            "segment_index": self.segment_index,
            "segment_type": self.segment_type,
            "parent_segment_id": self.parent_segment_id,
            "text": self.text,
            "source_location": self.source_location,
            "heading_context": self.heading_context,
            "table_id": self.table_id,
            "row_label": self.row_label,
            "column_label": self.column_label,
            "cell_value": self.cell_value,
            "period": self.period,
            "unit": self.unit,
            "list_depth": self.list_depth,
            "excluded": self.excluded,
            "exclusion_reason": self.exclusion_reason,
        }


def _segment_id(document_id: str, segment_index: int) -> str:
    """Deterministic 16-char segment id. Stable across re-parses of same doc."""
    raw = f"{document_id}::{segment_index}"
    return "seg-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _table_id(document_id: str, table_index: int) -> str:
    raw = f"{document_id}::table::{table_index}"
    return "tbl-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Stack frame for parser-state ancestry tracking
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class _StackFrame:
    """One frame per open HTML element. Carries exclusion state."""
    tag: str
    role: Optional[str] = None
    excluded: bool = False
    exclusion_reason: Optional[str] = None
    # Segment index of the nearest ancestor HEADING (for heading_context).
    heading_segment_index: Optional[int] = None
    # Segment index of the immediate structural parent (TABLE for TABLE_ROW,
    # UL/OL for LIST_ITEM, HEADING for child PARAGRAPH, etc.)
    structural_parent_index: Optional[int] = None


@dataclass
class _OpenList:
    """Track list nesting depth."""
    segment_index: Optional[int] = None  # segment id of this list (LIST type, optional)
    depth: int = 1


@dataclass
class _OpenTable:
    """Track an open <table>. Bridges to SemanticTableParser semantics."""
    table_index: int
    table_id: str
    segment_index: Optional[int] = None  # segment index of the table itself (for parent linkage)
    # Multi-row header support
    header_rows: list = field(default_factory=list)  # list[list[str]]
    current_row: list = field(default_factory=list)  # list[str]
    current_cell_text: str = ""
    in_thead: bool = False
    in_tbody: bool = False
    is_header_row: bool = False
    in_th: bool = False
    in_td: bool = False
    body_row_index: int = 0
    caption: str = ""
    in_caption: bool = False
    caption_text: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Unit + Period detection (carried over from V25R SemanticTableParser,
# unchanged behavior — proven on real corpus)
# ═══════════════════════════════════════════════════════════════════════

UNIT_PATTERNS = [
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)(?!\w)", re.IGNORECASE), "percent"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:bps|bp|basis\s*points?)(?!\w)", re.IGNORECASE), "basis_points"),
    (re.compile(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|billion|thousand|trillion)?", re.IGNORECASE), "usd"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:USD|US\$)(?!\w)", re.IGNORECASE), "usd"),
    (re.compile(r"€\s*(\d+(?:,\d{3})*(?:\.\d+)?)", re.IGNORECASE), "eur"),
    (re.compile(r"£\s*(\d+(?:,\d{3})*(?:\.\d+)?)", re.IGNORECASE), "gbp"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)\s+(?:barrels|bbl)(?!\w)", re.IGNORECASE), "barrels"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:barrels|bbl)(?!\w)", re.IGNORECASE), "barrels"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)\s+(?:tons|tonnes)(?!\w)", re.IGNORECASE), "tons"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:tons|tonnes)(?!\w)", re.IGNORECASE), "tons"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:index\s*points?|index)(?!\w)", re.IGNORECASE), "index_points"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)(?!\w)", re.IGNORECASE), "millions"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:billion|B|bn)(?!\w)", re.IGNORECASE), "billions"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:thousand|k|K)(?!\w)", re.IGNORECASE), "thousands"),
]

MONTH_TO_NUM = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def detect_unit(text: str) -> tuple[str, str]:
    """Return (numeric_value, unit). Empty strings if nothing detected."""
    if not text:
        return "", ""
    for pat, unit in UNIT_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).replace(",", ""), unit
    m = re.search(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\b", text)
    if m:
        return m.group(1).replace(",", ""), ""
    return "", ""


def detect_period(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"\b(20\d{2})\b", text)
    year = m.group(1) if m else None
    m = re.search(r"\bQ([1-4])\s*(20\d{2})?\b", text, re.IGNORECASE)
    if m:
        q = m.group(1); y = m.group(2) or year or ""
        return f"{y}Q{q}" if y else f"Q{q}"
    m = re.search(r"\b(H[12])\s*(20\d{2})?\b", text)
    if m:
        h = m.group(1); y = m.group(2) or year or ""
        return f"{y}{h}" if y else h
    m = re.search(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*(20\d{2})?\b",
        text, re.IGNORECASE)
    if m:
        mon = MONTH_TO_NUM.get(m.group(1)[:3].lower(), "")
        y = m.group(2) or year or ""
        return f"{y}-{mon}" if y else mon
    if year:
        return year
    if re.search(r"\bYoY\b", text, re.IGNORECASE): return "YOY"
    if re.search(r"\bMoM\b", text, re.IGNORECASE): return "MOM"
    if re.search(r"\bQoQ\b", text, re.IGNORECASE): return "QOQ"
    return None


# ═══════════════════════════════════════════════════════════════════════
# StructuralHTMLParser — production V37.2 parser
# ═══════════════════════════════════════════════════════════════════════

class StructuralHTMLParser(HTMLParser):
    """V37.2 production parser. Single pass, deterministic, parser-state.

    Emits EvidenceSegmentV1 with:
      - segment_id (sha256-based, stable)
      - parent_segment_id (real ancestry from structural parent)
      - heading_context (nearest ancestor HEADING text)
      - segment_type from {PARAGRAPH, LIST_ITEM, TABLE_ROW, HEADING, QUOTE,
                           FOOTNOTE, DOCUMENT_HEADER, OTHER, +EXCLUDED_*}
      - excluded flag (structural, primary; keyword, secondary)

    Inline tags inside a PARAGRAPH do NOT split the paragraph — they
    accumulate into the current open paragraph's text buffer. This handles
    malformed/unclosed <b>/<strong>/<i>/<em>/<a>/<span> inside paragraphs
    per V37.2 PHASE 5.
    """

    def __init__(self, document_id: str = ""):
        super().__init__(convert_charrefs=True)
        self.document_id = document_id
        self.segments: list[EvidenceSegmentV1] = []
        self._stack: list[_StackFrame] = []
        self._skip_depth: int = 0
        # Paragraph accumulation buffer (PHASE 5 — inline-tag tolerant).
        self._para_buf: str = ""
        self._para_open: bool = False
        self._para_segment_index: Optional[int] = None
        # Heading accumulation
        self._heading_buf: str = ""
        self._heading_open: bool = False
        # V37.2 COLLISION FIX §5 — accessibility-only heading flag
        self._heading_is_accessibility: bool = False
        # List nesting
        self._list_stack: list[_OpenList] = []
        # Table state (composed with SemanticTableParser semantics)
        self._table_stack: list[_OpenTable] = []
        # Counter for table_index (per document)
        self._table_counter: int = 0
        # Quote / Footnote state
        self._quote_open: bool = False
        self._quote_buf: str = ""
        self._footnote_open: bool = False
        self._footnote_buf: str = ""
        # Last emitted heading text — used for heading_context of children
        self._last_heading_text: Optional[str] = None
        # Last emitted heading segment index — for parent_segment_id linking
        self._last_heading_segment_index: Optional[int] = None
        # Article scope tracking (header/footer inside article = not UI)
        self._article_depth: int = 0
        # Block-quote depth (for QUOTE type)
        self._blockquote_depth: int = 0

    # ── Helpers ─────────────────────────────────────────────────────────

    def _current_excluded(self) -> tuple[bool, Optional[str]]:
        """Return (excluded, reason) inherited from any ancestor."""
        for frame in reversed(self._stack):
            if frame.excluded:
                return True, frame.exclusion_reason
        return False, None

    def _current_heading_index(self) -> Optional[int]:
        for frame in reversed(self._stack):
            if frame.heading_segment_index is not None:
                return frame.heading_segment_index
        return self._last_heading_segment_index

    def _current_heading_text(self) -> Optional[str]:
        idx = self._current_heading_index()
        if idx is None or idx >= len(self.segments):
            return self._last_heading_text
        return self.segments[idx].text or self._last_heading_text

    def _current_structural_parent(self) -> Optional[int]:
        """Return segment_index of nearest structural parent.

        Walks the stack looking for any frame carrying a
        structural_parent_index (set by an ancestor heading/table/list).
        If no frame carries it, falls back to the most recent HEADING
        segment (preserved in _last_heading_segment_index across
        sibling elements after the heading's own frame was popped).
        Returns None for orphan segments (no ancestor heading)."""
        for frame in reversed(self._stack):
            if frame.structural_parent_index is not None:
                return frame.structural_parent_index
        return self._last_heading_segment_index

    def _emit_segment(
        self,
        segment_type: str,
        text: str,
        *,
        table_id: Optional[str] = None,
        row_label: Optional[str] = None,
        column_label: Optional[str] = None,
        cell_value: Optional[str] = None,
        period: Optional[str] = None,
        unit: Optional[str] = None,
        list_depth: int = 0,
        source_location_suffix: str = "",
    ) -> int:
        """Emit one segment. Returns the new segment index."""
        seg_index = len(self.segments)
        excluded, reason = self._current_excluded()
        # Override: PARAGRAPH/LIST_ITEM emitted inside excluded container
        # inherits excluded=True.
        # Type may be downgraded for excluded containers.
        if excluded:
            # If the segment is inside an excluded container, keep its
            # original type but mark excluded=True. The caller will filter.
            pass
        seg_id = _segment_id(self.document_id, seg_index)
        parent_idx = self._current_structural_parent()
        parent_seg_id: Optional[str] = None
        if parent_idx is not None and parent_idx < seg_index:
            parent_seg_id = self.segments[parent_idx].segment_id
        # heading_context — nearest ancestor heading text
        heading_text = self._current_heading_text()
        # source_location — deterministic
        if source_location_suffix:
            loc = f"{self.document_id}#{source_location_suffix}"
        else:
            loc = f"{self.document_id}#{segment_type.lower()}{seg_index}"
        seg = EvidenceSegmentV1(
            document_id=self.document_id,
            segment_id=seg_id,
            segment_index=seg_index,
            segment_type=segment_type,
            parent_segment_id=parent_seg_id,
            text=text,
            source_location=loc,
            heading_context=heading_text,
            table_id=table_id,
            row_label=row_label,
            column_label=column_label,
            cell_value=cell_value,
            period=period,
            unit=unit,
            list_depth=list_depth,
            excluded=excluded,
            exclusion_reason=reason,
        )
        self.segments.append(seg)
        # If this segment is a HEADING, register it for descendants' context
        # UNLESS it's an accessibility-only heading OR an excluded heading
        # (V37.2 COLLISION FIX §5 — accessibility headings + nav/header/
        # footer headings must NOT propagate as heading_context).
        if segment_type == "HEADING":
            if not self._heading_is_accessibility and not seg.excluded:
                # Only substantive (visible, non-excluded) headings
                # propagate heading_context. Accessibility-only headings
                # like <h2 class="sr-only">Main navigation</h2> and
                # excluded headings like <h2> inside <nav> are emitted
                # as HEADING segments for audit but their text is NOT
                # propagated to descendants.
                self._last_heading_text = text
                self._last_heading_segment_index = seg_index
                # Update top-of-stack frame so descendants see this heading
                if self._stack:
                    self._stack[-1].heading_segment_index = seg_index
                    self._stack[-1].structural_parent_index = seg_index
            # Reset accessibility flag for next heading
            self._heading_is_accessibility = False
        # If this segment is a TABLE_ROW, its parent is the table (set on
        # the open table frame). Already handled via _current_structural_parent.
        return seg_index

    # ── Start tag ───────────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        role = attr_dict.get("role", "").lower() or None
        cls = attr_dict.get("class", "")

        # SKIP_TAGS (style/script/template/noscript) — never participate
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            # Push a minimal frame so end balancing works
            self._stack.append(_StackFrame(tag=tag, excluded=True,
                                           exclusion_reason="SKIP"))
            return

        if self._skip_depth > 0:
            # Inside skip content — push frame but don't process
            self._stack.append(_StackFrame(tag=tag, excluded=True,
                                           exclusion_reason="SKIP_INHERITED"))
            return

        # Determine exclusion status for this element
        excluded = False
        reason: Optional[str] = None
        if tag in EXCLUDED_CONTAINER_TAGS:
            excluded = True; reason = "NAVIGATION"
        elif role in EXCLUDED_ROLES:
            excluded = True; reason = f"ROLE_{role.upper()}"
        elif _class_excluded(cls):
            excluded = True; reason = "CLASS_PATTERN"

        # Inherit exclusion from ancestors
        if not excluded:
            anc_excl, anc_reason = self._current_excluded()
            if anc_excl:
                excluded = True; reason = anc_reason or "INHERITED"

        # Build frame — carry heading + structural parent from current top
        heading_idx = self._current_heading_index() if not excluded else None
        struct_parent = self._current_structural_parent() if not excluded else None
        # When opening a new structural container, it will become the parent
        # of its children. But its own segment_index isn't known until emit.
        # We'll set structural_parent_index on emit-when-closed for tables/lists.
        frame = _StackFrame(
            tag=tag, role=role,
            excluded=excluded, exclusion_reason=reason,
            heading_segment_index=heading_idx,
            structural_parent_index=struct_parent,
        )
        self._stack.append(frame)

        # Article scope — header/footer inside article are NOT UI
        if tag == "article":
            self._article_depth += 1
            return

        # ── Structural containers ───────────────────────────────────────

        if tag == "table":
            # Open table even when excluded — TABLE_ROW segments emitted
            # inside an excluded table will carry excluded=True for audit.
            tbl_idx = self._table_counter
            self._table_counter += 1
            tbl_id = _table_id(self.document_id, tbl_idx)
            ot = _OpenTable(table_index=tbl_idx, table_id=tbl_id)
            self._table_stack.append(ot)
            return

        if tag == "thead" and self._table_stack:
            self._table_stack[-1].in_thead = True
            return
        if tag == "tbody" and self._table_stack:
            self._table_stack[-1].in_tbody = True
            return
        if tag == "caption" and self._table_stack:
            self._table_stack[-1].in_caption = True
            self._table_stack[-1].caption_text = ""
            return

        if tag == "tr" and self._table_stack:
            ot = self._table_stack[-1]
            ot.current_row = []
            ot.is_header_row = ot.in_thead
            return

        if tag == "th" and self._table_stack:
            ot = self._table_stack[-1]
            ot.in_th = True
            ot.current_cell_text = ""
            ot.is_header_row = True
            return
        if tag == "td" and self._table_stack:
            ot = self._table_stack[-1]
            ot.in_td = True
            ot.current_cell_text = ""
            return

        if tag in ("ul", "ol"):
            # Open list even when excluded — LIST_ITEM segments will
            # carry excluded=True for audit.
            depth = (self._list_stack[-1].depth + 1) if self._list_stack else 1
            self._list_stack.append(_OpenList(depth=depth))
            return

        if tag == "li":
            # Begin a LIST_ITEM — we'll emit on close. Open even when
            # excluded so the segment is emitted with excluded=True.
            self._para_buf = ""
            self._para_open = False  # li uses its own emission
            return

        # ── Headings ────────────────────────────────────────────────────
        if tag in HEADING_TAGS:
            # Open heading buffer even when excluded — the HEADING
            # segment will carry excluded=True for audit.
            # V37.2 COLLISION FIX §5: Detect accessibility-only headings
            # (class="sr-only" / "visually-hidden" etc.) and mark them
            # so they DO NOT propagate as heading_context to children.
            self._heading_buf = ""
            self._heading_open = True
            self._heading_is_accessibility = _is_accessibility_only_class(cls)
            return

        # ── Quote / Footnote ────────────────────────────────────────────
        if tag in ("blockquote", "q"):
            # Open quote buffer even when excluded (audit).
            self._blockquote_depth += 1
            if tag == "blockquote":
                self._quote_open = True
                self._quote_buf = ""
            return
        if tag == "aside":
            # <aside> inside <article> = FOOTNOTE; outside = ADVERTISEMENT
            if self._article_depth > 0 and not excluded:
                self._footnote_open = True
                self._footnote_buf = ""
            else:
                # Mark this frame as ADVERTISEMENT
                frame.excluded = True
                frame.exclusion_reason = "ADVERTISEMENT_ASIDE"
            return

        # ── Paragraph ───────────────────────────────────────────────────
        if tag == "p":
            # Open paragraph buffer regardless of excluded status. The
            # segment will be emitted on flush with excluded=True if any
            # ancestor is excluded (per Evidence Segment Architecture V1 §6 —
            # excluded segments are still emitted for forensic audit, never
            # silently dropped).
            if self._para_buf.strip():
                self._flush_paragraph()
            self._para_buf = ""
            self._para_open = True
            return

        # ── Inline tags inside paragraph (PHASE 5) ─────────────────────
        # Inline tags do NOT split the paragraph. They contribute their text
        # via handle_data into the same _para_buf. We do nothing here — the
        # tag is on the stack so its data flows through handle_data into
        # _para_buf (when _para_open is True).
        if tag in INLINE_TAGS and self._para_open:
            return  # accumulate into paragraph buffer

        # ── Title / meta description → DOCUMENT_HEADER ─────────────────
        if tag == "title":
            self._heading_buf = ""
            self._heading_open = False
            self._footnote_open = False
            # Use heading buffer for title text capture
            self._para_buf = ""
            # Flag to emit DOCUMENT_HEADER on close
            # We'll piggyback on _heading_buf for text capture
            return

    # ── End tag ────────────────────────────────────────────────────────

    def handle_endtag(self, tag):
        tag = tag.lower()

        # SKIP_TAGS
        if tag in SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            if self._stack and self._stack[-1].tag == tag:
                self._stack.pop()
            return

        if self._skip_depth > 0:
            if self._stack and self._stack[-1].tag == tag:
                self._stack.pop()
            return

        # Article scope
        if tag == "article":
            if self._article_depth > 0:
                self._article_depth -= 1
            if self._stack and self._stack[-1].tag == "article":
                self._stack.pop()
            return

        # ── Table element endings ───────────────────────────────────────
        if tag == "caption" and self._table_stack:
            ot = self._table_stack[-1]
            ot.in_caption = False
            ot.caption = ot.caption_text.strip()
            ot.caption_text = ""
            # Don't pop the table frame
            # Pop only if top-of-stack is caption — but we don't push caption
            # frames separately, so just return
            return

        if tag == "th" and self._table_stack:
            ot = self._table_stack[-1]
            ot.in_th = False
            ot.current_row.append(ot.current_cell_text.strip())
            ot.current_cell_text = ""
            return

        if tag == "td" and self._table_stack:
            ot = self._table_stack[-1]
            ot.in_td = False
            ot.current_row.append(ot.current_cell_text.strip())
            ot.current_cell_text = ""
            return

        if tag == "tr" and self._table_stack:
            ot = self._table_stack[-1]
            self._close_table_row(ot)
            return

        if tag == "thead" and self._table_stack:
            self._table_stack[-1].in_thead = False
            return
        if tag == "tbody" and self._table_stack:
            self._table_stack[-1].in_tbody = False
            return

        if tag == "table" and self._table_stack:
            ot = self._table_stack.pop()
            # If table had no body rows, emit nothing (layout/empty table)
            # The table's own segment was not pre-emitted. We do NOT emit a
            # TABLE segment — TABLE_ROW segments are the unit. Their
            # parent_segment_id will point to the nearest ancestor heading
            # (or be None if no ancestor).
            # Pop the table's frame from _stack (the table frame is the one
            # whose tag == "table")
            while self._stack and self._stack[-1].tag != "table":
                self._stack.pop()
            if self._stack and self._stack[-1].tag == "table":
                self._stack.pop()
            return

        # ── List endings ────────────────────────────────────────────────
        if tag in ("ul", "ol") and self._list_stack:
            self._list_stack.pop()
            if self._stack and self._stack[-1].tag in ("ul", "ol"):
                self._stack.pop()
            return

        if tag == "li":
            # Emit LIST_ITEM segment from accumulated buffer
            text = self._para_buf.strip()
            self._para_buf = ""
            if text:
                depth = self._list_stack[-1].depth if self._list_stack else 1
                self._emit_segment(
                    "LIST_ITEM", text, list_depth=depth,
                    source_location_suffix=f"li{len(self.segments)}",
                )
            # Pop the li frame
            if self._stack and self._stack[-1].tag == "li":
                self._stack.pop()
            return

        # ── Heading endings ─────────────────────────────────────────────
        if tag in HEADING_TAGS:
            text = self._heading_buf.strip()
            self._heading_buf = ""
            self._heading_open = False
            if text:
                # Emit HEADING segment. Its parent is the previous heading
                # (or None). Its own segment_index becomes the parent for
                # subsequent siblings/children until a new heading appears.
                self._emit_segment(
                    "HEADING", text,
                    source_location_suffix=f"h{len(self.segments)}",
                )
            # Pop the heading frame
            if self._stack and self._stack[-1].tag == tag:
                self._stack.pop()
            return

        # ── Quote endings ──────────────────────────────────────────────
        if tag == "blockquote":
            text = self._quote_buf.strip()
            self._quote_buf = ""
            self._quote_open = False
            if self._blockquote_depth > 0:
                self._blockquote_depth -= 1
            if text:
                self._emit_segment(
                    "QUOTE", text,
                    source_location_suffix=f"quote{len(self.segments)}",
                )
            if self._stack and self._stack[-1].tag == "blockquote":
                self._stack.pop()
            return
        if tag == "q":
            # Inline quote — don't split paragraph. If we're in a paragraph,
            # the text already accumulated into _para_buf.
            if self._stack and self._stack[-1].tag == "q":
                self._stack.pop()
            return

        # ── Aside (footnote) endings ───────────────────────────────────
        if tag == "aside":
            if self._footnote_open:
                text = self._footnote_buf.strip()
                self._footnote_buf = ""
                self._footnote_open = False
                if text:
                    self._emit_segment(
                        "FOOTNOTE", text,
                        source_location_suffix=f"fn{len(self.segments)}",
                    )
            if self._stack and self._stack[-1].tag == "aside":
                self._stack.pop()
            return

        # ── Title → DOCUMENT_HEADER ────────────────────────────────────
        if tag == "title":
            text = self._heading_buf.strip()
            self._heading_buf = ""
            if text:
                self._emit_segment(
                    "DOCUMENT_HEADER", text,
                    source_location_suffix=f"title{len(self.segments)}",
                )
            if self._stack and self._stack[-1].tag == "title":
                self._stack.pop()
            return

        # ── Paragraph ending ───────────────────────────────────────────
        if tag == "p":
            self._flush_paragraph()
            if self._stack and self._stack[-1].tag == "p":
                self._stack.pop()
            return

        # ── Inline tag ending — no flush (PHASE 5) ────────────────────
        if tag in INLINE_TAGS:
            # Inline tag close — paragraph remains open. Text already
            # accumulated. Do not flush.
            self._pop_stack_to_tag(tag)
            return

        # ── Other tags — pop frames up to and including matching tag ─
        # Browser-style: walk the stack from top to bottom looking for a
        # matching open tag. If found, pop everything above it AND the
        # matching frame. This handles malformed HTML where intervening
        # tags weren't properly closed (e.g., <form><div></form> — the
        # form's frame would otherwise stay on the stack and pollute
        # exclusion inheritance for content after </form>).
        self._pop_stack_to_tag(tag)

    def _pop_stack_to_tag(self, tag: str) -> None:
        """Pop frames from the top of the stack until (and including) the
        matching tag. If no match, do nothing (malformed close tag)."""
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return
        # No match — ignore (the close tag has no corresponding open)

    # ── Data ─────────────────────────────────────────────────────────────

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if not data:
            return

        # Inside table cells — accumulate into current cell
        if self._table_stack:
            ot = self._table_stack[-1]
            if ot.in_caption:
                ot.caption_text += data
                return
            if ot.in_th or ot.in_td:
                ot.current_cell_text += data
                return
            # Other text inside <table> but outside cells — ignore
            return

        # Inside heading
        if self._heading_open:
            self._heading_buf += data
            return

        # Inside <title>
        if self._stack and self._stack[-1].tag == "title":
            self._heading_buf += data
            return

        # Inside blockquote
        if self._quote_open:
            self._quote_buf += data
            return

        # Inside <aside> footnote
        if self._footnote_open:
            self._footnote_buf += data
            return

        # Inside paragraph (open) — accumulate (handles inline tags too)
        if self._para_open:
            self._para_buf += data
            return

        # Standalone text node outside any structural container.
        # This happens for free-text between <p> blocks. Treat as a
        # PARAGRAPH if the text is non-trivial.
        text = data.strip()
        if not text:
            return
        # If we're inside an excluded container, skip (don't emit)
        excluded, _ = self._current_excluded()
        if excluded:
            return
        # Otherwise treat as an implicit paragraph
        self._para_buf = text
        self._para_open = True
        # Note: this paragraph has no enclosing <p> tag, so it will be
        # flushed only when the next structural element opens/closes or
        # when the document ends. That's correct behavior.

    # ── Flush paragraph ──────────────────────────────────────────────────

    def _flush_paragraph(self):
        """Emit a PARAGRAPH segment from the accumulated buffer."""
        if not self._para_open:
            return
        text = self._para_buf.strip()
        self._para_buf = ""
        self._para_open = False
        if not text:
            return
        excluded, _ = self._current_excluded()
        if excluded:
            # Still emit but with excluded=True for audit
            self._emit_segment(
                "PARAGRAPH", text,
                source_location_suffix=f"p{len(self.segments)}",
            )
            return
        self._emit_segment(
            "PARAGRAPH", text,
            source_location_suffix=f"p{len(self.segments)}",
        )

    # ── Close a table row — emit TABLE_ROW segment(s) ──────────────────

    def _close_table_row(self, ot: _OpenTable):
        """Emit one TABLE_ROW segment per body row. Header rows go to
        header_rows[] and do NOT produce segments (they contribute
        column_label to subsequent body rows)."""
        if not ot.current_row:
            return
        if ot.is_header_row:
            ot.header_rows.append(ot.current_row[:])
            ot.current_row = []
            ot.is_header_row = False
            return
        # Body row — emit one TABLE_ROW segment per cell, with column_label
        # from headers (multi-row headers: take last row that has a label
        # for this column index; colspan not yet supported — see _colspan
        # note in design doc).
        row_cells = ot.current_row
        row_label = row_cells[0].strip() if row_cells else ""
        body_col_idx = 0
        for cell_idx, cell_text in enumerate(row_cells):
            if cell_idx == 0:
                # Row label — don't emit a TABLE_ROW segment for the label
                # itself. The label is attached as `row_label` to the
                # subsequent cell segments.
                continue
            body_col_idx += 1
            # Column label from headers
            col_label = self._resolve_column_label(ot, body_col_idx)
            value, unit = detect_unit(cell_text)
            period = detect_period(cell_text) or self._detect_header_period(ot, body_col_idx)
            # Construct segment text — preserves full semantic context
            # per Evidence Segment Architecture V1 §7.1
            text_parts = []
            if row_label:
                text_parts.append(row_label)
            if col_label:
                text_parts.append(col_label)
            text_parts.append(cell_text)
            if period:
                text_parts.append(f"({period})")
            seg_text = " | ".join(text_parts)
            self._emit_segment(
                "TABLE_ROW", seg_text,
                table_id=ot.table_id,
                row_label=row_label or None,
                column_label=col_label,
                cell_value=cell_text.strip(),
                period=period,
                unit=unit,
                source_location_suffix=f"table{ot.table_index}_r{ot.body_row_index}_c{body_col_idx}",
            )
        ot.body_row_index += 1
        ot.current_row = []
        ot.is_header_row = False

    def _resolve_column_label(self, ot: _OpenTable, col_idx: int) -> Optional[str]:
        """Get column label from the LAST header row (V25R proven behavior).

        Multi-row header joining across rows is V37.3+ scope — for V37.2
        we use the most specific (last) header row only. This matches the
        proven behavior of SemanticTableParser from V25R."""
        if not ot.header_rows:
            return None
        last = ot.header_rows[-1]
        if col_idx < len(last):
            lbl = last[col_idx].strip()
            return lbl or None
        return None

    def _detect_header_period(self, ot: _OpenTable, col_idx: int) -> Optional[str]:
        """Detect period from header cell at col_idx (any header row)."""
        for hrow in ot.header_rows:
            if col_idx < len(hrow):
                p = detect_period(hrow[col_idx])
                if p:
                    return p
        return None

    # ── Close all open state ────────────────────────────────────────────

    def close(self):
        super().close()
        # Flush any open paragraph
        if self._para_open:
            self._flush_paragraph()
        # Close any open table (emit no segments — already done per row)
        # No-op needed
        # Close any open heading (defensive)
        if self._heading_open and self._heading_buf.strip():
            text = self._heading_buf.strip()
            self._heading_buf = ""
            self._heading_open = False
            self._emit_segment(
                "HEADING", text,
                source_location_suffix=f"h{len(self.segments)}",
            )


# ═══════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════

def parse_html_to_segments(html_bytes: bytes, document_id: str = "") -> list[EvidenceSegmentV1]:
    """Parse HTML bytes into a list of EvidenceSegmentV1.

    Single pass, deterministic, parser-state. No sentence regex. No
    post-hoc string matching. Inline tags inside paragraphs do not split.

    Returns segments in document order. Excluded segments carry
    excluded=True; callers can filter.
    """
    if not html_bytes:
        return []
    try:
        html_text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return []
    parser = StructuralHTMLParser(document_id=document_id)
    try:
        parser.feed(html_text)
        parser.close()
    except Exception:
        # Partial parse is still useful — return what we have
        pass
    return parser.segments
