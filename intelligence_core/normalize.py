"""Normalization — text pipeline carried over from scripts/pipeline/normalizer.py."""
from __future__ import annotations
import re

_SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)
_STYLE = re.compile(r"<style\b.*?</style>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_ENTITIES = {"&nbsp;": " ", "&#160;": " ", "&amp;": "&", "&#8211;": "-",
             "&#8212;": "-", "&lt;": "<", "&gt;": ">", "&quot;": '"'}


def strip_html(html: str) -> str:
    x = _SCRIPT.sub(" ", html)
    x = _STYLE.sub(" ", x)
    for k, v in _ENTITIES.items():
        x = x.replace(k, v)
    x = _TAGS.sub(" ", x)
    return re.sub(r"\s+", " ", x).strip()


def split_into_paragraphs(text: str) -> list:
    return [p.strip() for p in text.split(" . ") if p.strip()]
