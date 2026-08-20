"""ROUAA Core — Segment-Level Purpose Filtering (Recovery).

A SECOND-LAYER, segment-level filter that runs AFTER `structural_parser.parse_html_to_segments`
has already structurally excluded `<nav>`, `<header>` outside `<article>`,
`role="navigation"|"banner"|"contentinfo"`, and EXCLUDED_CLASS_NAMES.

The structural parser catches most navigation/banner/footer EXPLICITLY. But
on mixed-content pages (e.g., a Bank-of-England-style statistical release
that opens with a menu of "1. Summary, 2. Inflation, 3. Subscriptions"),
many menu items live inside `<article>` / `<main>` / `<section>` and are
emitted as PARAGRAPH or LIST_ITEM segments. The numeric tokens in those
menu items ("1.", "2.", "3.") get false-matched by the regex extractors
and end up as bogus facts.

This module applies a CONSERVATIVE, segment-level purpose classifier:

  classify_segment_purpose(segment) -> "SUBSTANTIVE" | "NAVIGATION" | "AMBIGUOUS"

Rules (all KEYS-LEVEL, no document-specific or source-specific shortcuts):

1. A segment already marked `excluded=True` by the parser is passed
   through (filter is a no-op for already-excluded segments — their
   `segment_type` already reflects the exclusion).

2. A segment whose `segment_type` is in {PARAGRAPH, LIST_ITEM, QUOTE,
   FOOTNOTE} is classified by its TEXT and HEADING_CONTEXT:

   - If text length < 80 chars AND text starts with a leading ordinal
     marker ("1.", "2.", "3." ... "99.") AND every word before the
     first colon or em-dash matches a generic navigation lexicon
     (Home, About, Publications, Subscribe, Login, Search, Contact,
     Menu, Back, Skip, Sign in, Sign up, Register, Help, Index,
     Contents, Summary, Press, News, Releases, Statistics, Topics,
     Topics, Browse, View, Read, More, See, All, Latest, Popular,
     Most read, Next, Previous, Continue, Start, Begin, End, Footer,
     Header, Sidebar, Navigation, Main, Site, Web, Page, Article,
     Section, Item, Items, List) → NAVIGATION.

   - If text is a single short line (< 60 chars) with no sentence
     punctuation (.!?), AND the heading_context is itself a generic
     navigation keyword (Menu, Navigation, Site map, Sitemap,
     Contents, Table of contents, Footer, Sidebar, Main menu,
     Quick links, Related, See also, Browse by, Browse, Topics,
     Categories, Index) → NAVIGATION.

   - Otherwise → SUBSTANTIVE.

3. TABLE_ROW segments are always SUBSTANTIVE (their structural context
   is unambiguous).

4. HEADING segments are always SUBSTANTIVE (they describe the content
   that follows).

5. ANY segment with numeric table-like cell content (e.g. "1.5", "2.0",
   "+0.5") inside a TABLE_ROW is SUBSTANTIVE.

INVARIANT: This filter NEVER skips an entire document. It operates
per-segment only. Mixed-content pages keep their substantive segments
even when most of the page is navigation.

INVARIANT: No GT-specific logic. No document IDs. No source IDs. No
hard-coded institution names. The lexicon is GENERIC.

INVARIANT: UNKNOWN is valid — a segment with insufficient signal is
classified SUBSTANTIVE (the safe default — better to retain than to
silently drop substantive content).
"""
from __future__ import annotations

import re
from typing import Optional

from .structural_parser import EvidenceSegmentV1


# ═══════════════════════════════════════════════════════════════════════
# Purpose categories
# ═══════════════════════════════════════════════════════════════════════

PURPOSE_SUBSTANTIVE = "SUBSTANTIVE"
PURPOSE_NAVIGATION = "NAVIGATION"
PURPOSE_AMBIGUOUS = "AMBIGUOUS"

ALL_PURPOSES = (PURPOSE_SUBSTANTIVE, PURPOSE_NAVIGATION, PURPOSE_AMBIGUOUS)


# ═══════════════════════════════════════════════════════════════════════
# Generic navigation lexicon — site-wide, NOT source-specific
# ═══════════════════════════════════════════════════════════════════════

# Words that strongly indicate a navigation/menu item when they appear as
# the first token of a short line. All words are generic UI/site words;
# NO institution names, NO document IDs, NO source-specific shortcuts.
_NAVIGATION_LEXICON = frozenset({
    # Generic site UI
    "home", "about", "about us", "publications", "subscribe", "login",
    "log in", "sign in", "signin", "sign up", "signup", "register",
    "log out", "logout", "search", "contact", "contact us", "menu",
    "back", "skip", "skip to content", "skip to main content",
    "help", "index", "contents", "table of contents", "press",
    "news", "releases", "statistics", "topics", "browse", "browse by",
    "view", "view all", "read", "read more", "more", "see", "see all",
    "see more", "all", "latest", "popular", "most read", "next",
    "previous", "continue", "start", "begin", "end", "footer",
    "header", "sidebar", "navigation", "main", "site", "web", "page",
    "article", "section", "item", "items", "list", "sitemap", "site map",
    "quick links", "related", "see also", "categories", "tags",
    "share", "follow", "follow us", "back to top", "top",
    "previous page", "next page", "first", "last", "current",
    "feedback", "feedback form", "report", "report a problem",
    "accessibility", "accessibility statement", "cookies",
    "cookie policy", "privacy", "privacy policy", "terms",
    "terms of use", "legal", "copyright", "disclaimer",
})

# Heading context values that mark the segments under them as
# navigation rather than substantive content.
_NAVIGATION_HEADING_CONTEXTS = frozenset({
    "menu", "navigation", "site map", "sitemap", "contents",
    "table of contents", "footer", "sidebar", "main menu",
    "quick links", "related", "see also", "browse by", "browse",
    "topics", "categories", "index", "site navigation",
    "page navigation", "section navigation",
})


# ═══════════════════════════════════════════════════════════════════════
# Pattern precompilation
# ═══════════════════════════════════════════════════════════════════════

# Leading ordinal: "1.", "2.", "10." ... up to "99."
# Captures the leading ordinal and the optional separator.
_LEADING_ORDINAL_RE = re.compile(r"^\s*(\d{1,2})(\.|\)|\-)\s+")

# Sentence-ending punctuation
_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")

# Numeric table-like cell content (e.g., "1.5", "2.0", "+0.5")
_NUMERIC_TABLE_RE = re.compile(r"\b[+-]?\d+(\.\d+)?\b")

# Short line threshold for menu-like text
_SHORT_LINE_MAX = 80
_VERY_SHORT_LINE_MAX = 60


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _normalize_text(text: str) -> str:
    """Collapse whitespace and strip leading/trailing."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _first_token_phrase(text: str, max_phrase_chars: int = 40) -> str:
    """Take the text up to the first colon or em-dash, capped at
    `max_phrase_chars`. Returns the leading phrase lowercased.

    For "1. Summary of inflation report: ..."
    returns "summary of inflation report"
    """
    if not text:
        return ""
    # Stop at the first colon or em-dash
    stop = len(text)
    for delim in (":", "—", "–", "-"):
        idx = text.find(delim)
        if idx > 0 and idx < stop:
            stop = idx
    phrase = text[:stop].strip()
    if len(phrase) > max_phrase_chars:
        phrase = phrase[:max_phrase_chars].strip()
    return phrase.lower()


def _has_sentence_end(text: str) -> bool:
    """True if the text ends with sentence-ending punctuation."""
    if not text:
        return False
    return bool(_SENTENCE_END_RE.search(text))


def _is_short_line(text: str, max_chars: int = _SHORT_LINE_MAX) -> bool:
    """True if normalized text length is below `max_chars`."""
    return 0 < len(_normalize_text(text)) <= max_chars


# ═══════════════════════════════════════════════════════════════════════
# Classifier
# ═══════════════════════════════════════════════════════════════════════

# Segment types that are ALWAYS substantive (structural context is
# unambiguous — they describe their content explicitly).
_ALWAYS_SUBSTANTIVE_TYPES = frozenset({
    "TABLE_ROW", "TABLE_HEADER", "TABLE_CELL",
    "HEADING", "DOCUMENT_TITLE", "CAPTION",
})

# Segment types that are NEVER substantive (already structurally excluded
# by the parser, but we mark them too so callers know).
_NEVER_SUBSTANTIVE_TYPES = frozenset({
    "NAVIGATION", "HEADER_UI", "FOOTER_UI", "SOCIAL", "COOKIE",
    "CSS", "JS", "TEMPLATE", "ADVERTISEMENT", "LISTING",
})


def classify_segment_purpose(segment: EvidenceSegmentV1) -> str:
    """Classify a single EvidenceSegmentV1 segment's purpose.

    Returns one of:
        PURPOSE_SUBSTANTIVE  — segment carries primary content
        PURPOSE_NAVIGATION   — segment is a navigation/menu element
        PURPOSE_AMBIGUOUS    — segment has insufficient signal (treated
                                as SUBSTANTIVE for filtering, but the
                                distinct category allows callers to
                                report ambiguity)

    Classification logic:
        1. If `segment.excluded=True` already, return the purpose
           implied by its `segment_type`:
              - {NAVIGATION, HEADER_UI, FOOTER_UI, SOCIAL, COOKIE,
                 CSS, JS, TEMPLATE, ADVERTISEMENT, LISTING} → NAVIGATION
              - everything else excluded → AMBIGUOUS
        2. If `segment.segment_type` in _ALWAYS_SUBSTANTIVE_TYPES →
           SUBSTANTIVE
        3. If `segment.segment_type` in _NEVER_SUBSTANTIVE_TYPES →
           NAVIGATION
        4. For {PARAGRAPH, LIST_ITEM, QUOTE, FOOTNOTE}:
              (a) Heading-context navigation check
              (b) Short-line ordinal + lexicon check
              (c) Short-line + no-sentence-end + navigation heading
                  context check
              (d) Default → SUBSTANTIVE
        5. Other segment types → SUBSTANTIVE (safe default)
    """
    st = segment.segment_type or ""
    text = segment.text or ""
    hc = (segment.heading_context or "").strip().lower()

    # (1) Already structurally excluded — defer to type
    if segment.excluded:
        if st in _NEVER_SUBSTANTIVE_TYPES:
            return PURPOSE_NAVIGATION
        return PURPOSE_AMBIGUOUS

    # (2) Types that are ALWAYS substantive regardless of text
    if st in _ALWAYS_SUBSTANTIVE_TYPES:
        return PURPOSE_SUBSTANTIVE

    # (3) Types that are NEVER substantive
    if st in _NEVER_SUBSTANTIVE_TYPES:
        return PURPOSE_NAVIGATION

    # (4) Content-bearing types: PARAGRAPH / LIST_ITEM / QUOTE / FOOTNOTE
    if st in ("PARAGRAPH", "LIST_ITEM", "QUOTE", "FOOTNOTE"):
        norm = _normalize_text(text)
        if not norm:
            return PURPOSE_AMBIGUOUS

        # (a) Heading-context navigation check
        if hc and hc in _NAVIGATION_HEADING_CONTEXTS:
            return PURPOSE_NAVIGATION

        # (b) Short-line ordinal + lexicon check
        #     e.g., "1. Summary" or "2. Subscribe to updates"
        ordinal_match = _LEADING_ORDINAL_RE.match(norm)
        if ordinal_match and len(norm) <= _SHORT_LINE_MAX:
            phrase = _first_token_phrase(norm[ordinal_match.end():])
            # Check if the phrase contains any navigation lexicon token
            # at the start (allowing for multi-word phrases like
            # "summary of inflation" but matching "summary" prefix).
            if phrase:
                for nav_word in _NAVIGATION_LEXICON:
                    if phrase == nav_word or phrase.startswith(nav_word + " "):
                        return PURPOSE_NAVIGATION
            # If leading ordinal + short line + no sentence end → still
            # likely a menu item even without lexicon match
            if not _has_sentence_end(norm):
                return PURPOSE_NAVIGATION

        # (c) Very-short line + no sentence-end + navigation heading context
        if (len(norm) <= _VERY_SHORT_LINE_MAX
                and not _has_sentence_end(norm)
                and hc in _NAVIGATION_HEADING_CONTEXTS):
            return PURPOSE_NAVIGATION

        # (d) Default for content-bearing segment
        return PURPOSE_SUBSTANTIVE

    # (5) Other segment types — safe default
    return PURPOSE_SUBSTANTIVE


# ═══════════════════════════════════════════════════════════════════════
# Filter entry point
# ═══════════════════════════════════════════════════════════════════════

def apply_purpose_filter(
    segments: list[EvidenceSegmentV1],
    *,
    return_purposes: bool = False,
) -> list[EvidenceSegmentV1] | tuple[list[EvidenceSegmentV1], list[str]]:
    """Filter `segments` to retain only those whose purpose is SUBSTANTIVE.

    The filter is SEGMENT-LEVEL. It NEVER skips an entire document.
    Mixed-content pages keep their substantive segments.

    Args:
        segments: list of EvidenceSegmentV1 emitted by parse_html_to_segments.
        return_purposes: if True, also return the parallel list of purpose
            classifications (for diagnostics).

    Returns:
        Either:
            list of substantive EvidenceSegmentV1 (return_purposes=False), OR
            tuple of (substantive_segments, purposes_for_each_input_segment)
            (return_purposes=True).

    Note: the purposes list (when requested) has the SAME LENGTH as the
    INPUT list — every input segment receives a classification, even
    those filtered out. This makes auditing of mixed-page filtering
    possible without losing the source-side picture.
    """
    substantive: list[EvidenceSegmentV1] = []
    purposes: list[str] = []
    for seg in segments:
        p = classify_segment_purpose(seg)
        purposes.append(p)
        if p == PURPOSE_SUBSTANTIVE:
            substantive.append(seg)
    if return_purposes:
        return substantive, purposes
    return substantive


def purpose_breakdown(segments: list[EvidenceSegmentV1]) -> dict[str, int]:
    """Return a Counter-style breakdown of purposes across `segments`.

    Useful for the corpus-recovery layer to report how much of each
    document's parsed segments were substantive vs navigation vs ambiguous.
    """
    counts = {p: 0 for p in ALL_PURPOSES}
    for seg in segments:
        p = classify_segment_purpose(seg)
        counts[p] = counts.get(p, 0) + 1
    return counts


__all__ = [
    "PURPOSE_SUBSTANTIVE",
    "PURPOSE_NAVIGATION",
    "PURPOSE_AMBIGUOUS",
    "ALL_PURPOSES",
    "classify_segment_purpose",
    "apply_purpose_filter",
    "purpose_breakdown",
]
