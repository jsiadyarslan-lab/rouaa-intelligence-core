"""V5 §4 — Sentence-aware evidence extraction.

The current evidence extraction uses a fixed character window (110 chars before,
40 chars after the match). This is insufficient because:
  - It may cut sentences in half
  - It doesn't capture the full context (entity, unit, direction)
  - It produces INDIRECT_EVIDENCE instead of DIRECT_EVIDENCE

This module implements sentence-aware extraction:
  - Find the sentence containing the match
  - Extend to include the previous + next sentence if they provide context
  - Preserve the full sentence as the evidence excerpt
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))


# Sentence boundary patterns
SENTENCE_BOUNDARIES = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

# Also split on common list/paragraph boundaries
PARAGRAPH_BOUNDARIES = re.compile(r'\n\s*\n')


def extract_sentence_around_match(text: str, match_start: int, match_end: int,
                                    context_sentences: int = 1) -> str:
    """Extract the sentence containing the match, plus context sentences.

    Args:
        text: The full document text
        match_start: Start position of the match
        match_end: End position of the match
        context_sentences: Number of sentences before/after to include

    Returns:
        The evidence excerpt (sentence-aware)
    """
    # Find all sentence boundaries
    sentences = []
    last_end = 0
    for m in SENTENCE_BOUNDARIES.finditer(text):
        sentences.append((last_end, m.start()))
        last_end = m.end()
    sentences.append((last_end, len(text)))

    # Find which sentence contains the match
    match_sentence_idx = None
    for i, (start, end) in enumerate(sentences):
        if start <= match_start < end:
            match_sentence_idx = i
            break

    if match_sentence_idx is None:
        # Fallback to character window
        start = max(0, match_start - 110)
        end = min(len(text), match_end + 40)
        return text[start:end].strip()

    # Extract the match sentence + context sentences
    start_idx = max(0, match_sentence_idx - context_sentences)
    end_idx = min(len(sentences), match_sentence_idx + context_sentences + 1)

    excerpt_start = sentences[start_idx][0]
    excerpt_end = sentences[end_idx - 1][1]

    # Also check if the match spans multiple sentences
    if match_end > sentences[match_sentence_idx][1]:
        # Match spans multiple sentences — extend to include all
        for i in range(match_sentence_idx, len(sentences)):
            if sentences[i][1] >= match_end:
                end_idx = min(len(sentences), i + 1 + context_sentences)
                excerpt_end = sentences[end_idx - 1][1]
                break

    return text[excerpt_start:excerpt_end].strip()


def extract_paragraph_around_match(text: str, match_start: int, match_end: int) -> str:
    """Extract the paragraph containing the match."""
    # Find paragraph boundaries
    paragraphs = []
    last_end = 0
    for m in PARAGRAPH_BOUNDARIES.finditer(text):
        paragraphs.append((last_end, m.start()))
        last_end = m.end()
    paragraphs.append((last_end, len(text)))

    # Find which paragraph contains the match
    for start, end in paragraphs:
        if start <= match_start < end:
            return text[start:end].strip()

    # Fallback
    start = max(0, match_start - 200)
    end = min(len(text), match_end + 100)
    return text[start:end].strip()


def improved_extract_facts(text: str, patterns: list, representation_id: str,
                            document_id: str, created_at: str = "") -> list:
    """Extract facts with sentence-aware evidence.

    This is a drop-in replacement for intelligence_core.extract.extract_facts
    that produces better evidence excerpts.
    """
    from intelligence_core.contracts import Fact, ObjState
    from intelligence_core.identity import fact_id as make_fact_id
    from intelligence_core.extract import normalize_metric

    facts = []
    occurrences = {}
    for regex_src, pattern_type in patterns:
        metric, _ = normalize_metric(pattern_type)
        rx = re.compile(regex_src)
        for m in rx.finditer(text):
            key = (pattern_type, metric)
            occurrences[key] = occurrences.get(key, 0) + 1
            occ = occurrences[key]

            # Sentence-aware evidence extraction (V5 §4)
            excerpt = extract_sentence_around_match(text, m.start(), m.end(),
                                                     context_sentences=1)

            fid = make_fact_id(representation_id, metric, pattern_type, occ)
            facts.append(Fact(
                fact_id=fid, fact_version=1,
                representation_id=representation_id, document_id=document_id,
                metric=metric, value=m.group(1) if m.groups() else "",
                raw_value=m.group(0), pattern_ref=pattern_type, occurrence=occ,
                excerpt=excerpt, status=ObjState.ACTIVE, created_at=created_at))
    return facts


def test_sentence_extraction():
    """Test the sentence-aware extraction."""
    text = """
    The Federal Reserve Board on Tuesday announced a consent order against XYZ Bank.
    The bank was fined $5 million for violations of banking regulations.
    This enforcement action follows an investigation that began in 2024.
    The penalty includes a $3 million fine and $2 million in disgorgement.
    """

    # Find "consent order" and extract evidence
    pattern = r'\b(consent\s+order)\b'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        excerpt = extract_sentence_around_match(text, m.start(), m.end())
        print(f"Match: '{m.group(0)}' at {m.start()}")
        print(f"Sentence-aware excerpt:")
        print(f"  {excerpt}")
        print()

    # Find "$5 million" and extract evidence
    pattern2 = r'\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+million'
    m2 = re.search(pattern2, text)
    if m2:
        excerpt2 = extract_sentence_around_match(text, m2.start(), m2.end())
        print(f"Match: '{m2.group(0)}' at {m2.start()}")
        print(f"Sentence-aware excerpt:")
        print(f"  {excerpt2}")


if __name__ == "__main__":
    test_sentence_extraction()
