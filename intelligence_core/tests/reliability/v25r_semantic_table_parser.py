"""V25R — Semantic Table Parser.

Parses HTML tables into SEMANTIC table objects that preserve:
  - table_id (stable hash)
  - caption (if present)
  - header_rows[] (multi-row header support)
  - body_rows[] (with row_label + cells)
  - column_label per cell (from headers)
  - row_label per cell (from first column or row header)
  - cell_value, cell_unit, cell_period (extracted from cell text)
  - source_location (for evidence)
"""
from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# UNIT DETECTION
# ═══════════════════════════════════════════════════════════════════════

UNIT_PATTERNS = [
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)(?!\w)", re.IGNORECASE), "percent", "Percentage"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:bps|bp|basis\s*points?)(?!\w)", re.IGNORECASE), "basis_points", "Basis points"),
    (re.compile(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|billion|thousand|trillion)?", re.IGNORECASE), "usd", "USD"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:USD|US\$)(?!\w)", re.IGNORECASE), "usd", "USD"),
    (re.compile(r"€\s*(\d+(?:,\d{3})*(?:\.\d+)?)", re.IGNORECASE), "eur", "EUR"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*€(?!\w)"), "eur", "EUR"),
    (re.compile(r"£\s*(\d+(?:,\d{3})*(?:\.\d+)?)", re.IGNORECASE), "gbp", "GBP"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)\s+(?:barrels|bbl)(?!\w)", re.IGNORECASE), "barrels", "Barrels (millions)"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:barrels|bbl)(?!\w)", re.IGNORECASE), "barrels", "Barrels"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)\s+(?:tons|tonnes)(?!\w)", re.IGNORECASE), "tons", "Tons (millions)"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:tons|tonnes)(?!\w)", re.IGNORECASE), "tons", "Tons"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)\s+(?:people|persons|employees)(?!\w)", re.IGNORECASE), "people_millions", "People (millions)"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:people|persons|employees)(?!\w)", re.IGNORECASE), "people", "People"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:index\s*points?|index)(?!\w)", re.IGNORECASE), "index_points", "Index Points"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)(?!\w)", re.IGNORECASE), "millions", "Millions"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:billion|B|bn)(?!\w)", re.IGNORECASE), "billions", "Billions"),
    (re.compile(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:thousand|k|K)(?!\w)", re.IGNORECASE), "thousands", "Thousands"),
]


def detect_unit(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    for pat, unit, desc in UNIT_PATTERNS:
        m = pat.search(text)
        if m:
            value = m.group(1).replace(",", "")
            return value, unit
    m = re.search(r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\b", text)
    if m:
        return m.group(1).replace(",", ""), ""
    return "", ""


# ═══════════════════════════════════════════════════════════════════════
# PERIOD DETECTION
# ═══════════════════════════════════════════════════════════════════════

MONTH_TO_NUM = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def detect_period(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"\b(20\d{2})\b", text)
    year = m.group(1) if m else None

    m = re.search(r"\bQ([1-4])\s*(20\d{2})?\b", text, re.IGNORECASE)
    if m:
        q = m.group(1)
        y = m.group(2) or year or ""
        return f"{y}Q{q}" if y else f"Q{q}"

    m = re.search(r"\b(H[12])\s*(20\d{2})?\b", text)
    if m:
        h = m.group(1)
        y = m.group(2) or year or ""
        return f"{y}{h}" if y else h

    m = re.search(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*(20\d{2})?\b", text, re.IGNORECASE)
    if m:
        mon = MONTH_TO_NUM.get(m.group(1)[:3].lower(), "")
        y = m.group(2) or year or ""
        return f"{y}-{mon}" if y else mon

    if year:
        return year

    if re.search(r"\bYoY\b", text, re.IGNORECASE):
        return "YOY"
    if re.search(r"\bMoM\b", text, re.IGNORECASE):
        return "MOM"
    if re.search(r"\bQoQ\b", text, re.IGNORECASE):
        return "QOQ"
    return None


# ═══════════════════════════════════════════════════════════════════════
# SEMANTIC TABLE MODEL
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TableCell:
    value: str = ""
    unit: str = ""
    numeric_value: str = ""
    column_label: str = ""
    column_index: int = 0
    period: Optional[str] = None


@dataclass
class TableRow:
    row_label: str = ""
    cells: list = field(default_factory=list)
    row_index: int = 0


@dataclass
class SemanticTable:
    table_id: str = ""
    caption: str = ""
    header_rows: list = field(default_factory=list)
    body_rows: list = field(default_factory=list)
    source_location: str = ""
    table_index: int = 0


# ═══════════════════════════════════════════════════════════════════════
# SEMANTIC TABLE PARSER
# ═══════════════════════════════════════════════════════════════════════

class SemanticTableParser(HTMLParser):
    SKIP_TAGS = frozenset({"style", "script", "template", "noscript"})

    def __init__(self, document_id: str = ""):
        super().__init__()
        self.document_id = document_id
        self.tables: list = []
        self.current_table = None
        self.current_row: list = []
        self.current_cell_text: str = ""
        self.in_thead = False
        self.in_tbody = False
        self.in_th = False
        self.in_td = False
        self.in_caption = False
        self.caption_text: str = ""
        self.is_header_row = False
        self.table_index = 0
        self.body_row_index = 0
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return
        if tag == "table":
            self.current_table = SemanticTable(
                table_id="",
                table_index=self.table_index,
                source_location=f"{self.document_id}#table{self.table_index}",
            )
            self.table_index += 1
            self.body_row_index = 0
        elif tag == "caption":
            self.in_caption = True
            self.caption_text = ""
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr":
            self.current_row = []
            self.is_header_row = self.in_thead
        elif tag == "th":
            self.in_th = True
            self.current_cell_text = ""
            self.is_header_row = True
        elif tag == "td":
            self.in_td = True
            self.current_cell_text = ""

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if self.skip_depth > 0:
            return
        if tag == "caption":
            self.in_caption = False
            if self.current_table:
                self.current_table.caption = self.caption_text.strip()
        elif tag == "th":
            self.in_th = False
            self.current_row.append(self.current_cell_text.strip())
            self.current_cell_text = ""
        elif tag == "td":
            self.in_td = False
            self.current_row.append(self.current_cell_text.strip())
            self.current_cell_text = ""
        elif tag == "tr":
            if self.current_table and self.current_row:
                if self.is_header_row:
                    self.current_table.header_rows.append(self.current_row[:])
                else:
                    row = TableRow(row_index=self.body_row_index)
                    if self.current_row:
                        row.row_label = self.current_row[0].strip()
                    for col_idx, cell_text in enumerate(self.current_row[1:], start=1):
                        value, unit = detect_unit(cell_text)
                        cell = TableCell(
                            value=cell_text,
                            unit=unit,
                            numeric_value=value,
                            column_index=col_idx,
                        )
                        cell.period = detect_period(cell_text) or detect_period(
                            self.current_table.header_rows[-1][col_idx] if self.current_table.header_rows
                            and col_idx < len(self.current_table.header_rows[-1]) else ""
                        )
                        row.cells.append(cell)
                    self.current_table.body_rows.append(row)
                    self.body_row_index += 1
            self.current_row = []
            self.is_header_row = False
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "table":
            if self.current_table:
                h = hashlib.sha1()
                h.update(self.current_table.source_location.encode("utf-8"))
                h.update(self.current_table.caption.encode("utf-8"))
                h.update(str(len(self.current_table.body_rows)).encode("utf-8"))
                self.current_table.table_id = "tbl-" + h.hexdigest()[:16]
                self.tables.append(self.current_table)
                self.current_table = None

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        if not data:
            return
        if self.in_caption:
            self.caption_text += data
        elif self.in_th or self.in_td:
            self.current_cell_text += data


def parse_semantic_tables(html_bytes: bytes, document_id: str = "") -> list:
    try:
        html_text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return []
    parser = SemanticTableParser(document_id=document_id)
    try:
        parser.feed(html_text)
    except Exception:
        pass
    real_tables = []
    for tbl in parser.tables:
        if not tbl.body_rows:
            continue
        if tbl.body_rows and all(len(r.cells) == 0 for r in tbl.body_rows):
            continue
        real_tables.append(tbl)
    return real_tables


# ═══════════════════════════════════════════════════════════════════════
# NEGATIVE TABLE FILTERS
# ═══════════════════════════════════════════════════════════════════════

NAV_KEYWORDS = {
    "skip to", "navigation", "main menu", "site menu", "breadcrumb",
    "search", "previous", "next", "page 1 of", "page 2 of",
    "facebook", "twitter", "linkedin", "youtube", "instagram",
    "copyright ©", "all rights reserved", "cookie consent",
    "privacy policy", "terms of use", "subscribe", "newsletter",
}

AD_KEYWORDS = {
    "advertisement", "sponsored", "advertisements", "sponsored content",
    "promoted", "advertise with us",
}


def is_navigation_table(table) -> bool:
    all_text = " ".join(c.value for r in table.body_rows for c in r.cells).lower()
    all_text += " " + table.caption.lower()
    nav_hits = sum(1 for kw in NAV_KEYWORDS if kw in all_text)
    return nav_hits >= 2


def is_ad_table(table) -> bool:
    all_text = " ".join(c.value for r in table.body_rows for c in r.cells).lower()
    all_text += " " + table.caption.lower()
    return any(kw in all_text for kw in AD_KEYWORDS)


def is_layout_table(table) -> bool:
    total_cells = 0
    numeric_cells = 0
    for r in table.body_rows:
        for c in r.cells:
            total_cells += 1
            if c.numeric_value:
                numeric_cells += 1
    if total_cells == 0:
        return True
    return numeric_cells == 0 and total_cells < 10


def filter_negative_tables(tables):
    stats = {"total": len(tables), "nav": 0, "ad": 0, "layout": 0, "kept": 0}
    kept = []
    for tbl in tables:
        if is_navigation_table(tbl):
            stats["nav"] += 1
            continue
        if is_ad_table(tbl):
            stats["ad"] += 1
            continue
        if is_layout_table(tbl):
            stats["layout"] += 1
            continue
        kept.append(tbl)
    stats["kept"] = len(kept)
    return kept, stats
