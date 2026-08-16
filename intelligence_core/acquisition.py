"""D10 acquisition: direct-HTTP only (RSS/Atom + static/server HTML).

All methods produce the SAME canonical Representation contract (directive §8).
No browser rendering, no CAPTCHA workarounds, no XLS/PDF parsing (deferred).
"""
from __future__ import annotations
import re
import urllib.request
import xml.etree.ElementTree as ET
from .contracts import RetrievalEvent
from .identity import (canonicalize_url, content_sha256, document_id,
                       representation_id, retrieval_event_id)


class Transport:
    """Minimal transport seam. Deterministic tests inject FakeTransport."""
    def get(self, url: str, timeout: int = 30) -> tuple[int, str, bytes, str]:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ROUAA-Core/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return resp.status, resp.geturl(), data, resp.headers.get("Content-Type", "")


class DirectHttpAdapter:
    adapter_class = "direct_http"

    def __init__(self, transport: Transport | None = None):
        self.transport = transport or Transport()
        self._seq = 0

    def fetch(self, url: str, base: str | None = None, run_id: str = "run") -> dict:
        """Returns {retrieval_event, document_id, representation_id, sha256, bytes,
        canonical_url, aliases}. Raises on network/HTTP failure (caller isolates)."""
        self._seq += 1
        rid_evt = retrieval_event_id(run_id, url, self._seq)
        status, final_url, data, ctype = self.transport.get(url)
        canonical, aliases = canonicalize_url(url, base=base, final_url=final_url)
        sha = content_sha256(data)
        doc_id = document_id(canonical)
        rep_id = representation_id(doc_id, sha)
        evt = RetrievalEvent(retrieval_event_id=rid_evt, method="GET",
                             adapter_class=self.adapter_class, requested_url=url,
                             final_url=final_url, http_status=status,
                             retrieved_at="", run_id=run_id)
        return {"retrieval_event": evt, "document_id": doc_id,
                "representation_id": rep_id, "content_sha256": sha, "bytes": data,
                "canonical_url": canonical, "aliases": aliases, "content_type": ctype}


_RSS_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_LINK = re.compile(r"<link>([^<]+)</link>")
_GUID = re.compile(r"<guid[^>]*>([^<]+)</guid>")
_TITLE = re.compile(r"<title>(?:<!\[CDATA\[)?([^<\]]+)", re.S)
_PUBDATE = re.compile(r"<pubDate>([^<]+)</pubDate>")


def parse_rss_items(xml_text: str) -> list:
    """RSS 2.0 items -> [{title, link, guid, pubDate}]. Tolerant regex parse
    (matches the evidence-layer approach; ET used when well-formed)."""
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for it in root.iter("item"):
            items.append({
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip(),
                "guid": (it.findtext("guid") or "").strip(),
                "pubDate": (it.findtext("pubDate") or "").strip()})
        if items:
            return items
        for it in root.iter("{http://www.w3.org/2005/Atom}entry"):  # Atom
            link = ""
            for l in it.findall("{http://www.w3.org/2005/Atom}link"):
                if l.get("href"):
                    link = l.get("href"); break
            items.append({"title": (it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip(),
                          "link": link, "guid": (it.findtext("{http://www.w3.org/2005/Atom}id") or "").strip(),
                          "pubDate": (it.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()})
        return items
    except ET.ParseError:
        for m in _RSS_ITEM.finditer(xml_text):
            it = m.group(1)
            items.append({"title": (_TITLE.search(it) or [None, ""])[1].strip() if _TITLE.search(it) else "",
                          "link": (_LINK.search(it) or [None, ""])[1].strip() if _LINK.search(it) else "",
                          "guid": (_GUID.search(it) or [None, ""])[1].strip() if _GUID.search(it) else "",
                          "pubDate": (_PUBDATE.search(it) or [None, ""])[1].strip() if _PUBDATE.search(it) else ""})
        return items


def resolve_index_link(href: str, index_url: str) -> str:
    """L-REL fix: normalize an html_index href against the index page URL before
    fetching. Supports absolute, root-relative (/path), path-relative (path),
    and ../ forms. Canonicalization still passes through NR-v1 at fetch time."""
    from urllib.parse import urljoin
    return urljoin(index_url, href.strip())


def find_html_links(html: str, link_pattern: str, base: str) -> list:
    """OFAC-style html_index discovery: anchors matching a configured pattern."""
    out = []
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1)
        if re.search(link_pattern, href):
            out.append(href)
    return out
