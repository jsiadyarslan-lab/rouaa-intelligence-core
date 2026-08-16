"""D1 — document identity + NR-v1 URL canonicalization. Deterministic, stdlib-only."""
from __future__ import annotations
import hashlib
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

# NR-v1: tracking/session parameters discarded (recorded as aliases by caller).
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "sid", "ref_")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _short(prefix: str, seed: str) -> str:
    return f"{prefix}-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def canonicalize_url(url: str, base: str | None = None, final_url: str | None = None) -> tuple[str, list[str]]:
    """NR-v1: absolutize, follow redirect target, normalize. Returns (canonical, aliases)."""
    aliases: list[str] = []
    if base:
        url = urljoin(base, url)
    if final_url and final_url != url:
        aliases.append(url)          # pre-redirect form preserved (D1 rule, BMF evidence)
        url = final_url
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower()
    port = p.port
    if port and _DEFAULT_PORTS.get(p.scheme) == port:
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")      # trailing slash stripped (root excepted)
    kept = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not any(k.lower().startswith(t) for t in _TRACKING_PREFIXES)]
    dropped = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
               if any(k.lower().startswith(t) for t in _TRACKING_PREFIXES)]
    if dropped:
        aliases.append(urlunsplit((p.scheme, netloc, path, urlencode(dropped), "")))
    canonical = urlunsplit((p.scheme.lower(), netloc, path, urlencode(kept), ""))  # fragment dropped
    return canonical, aliases


def document_id(canonical_url: str) -> str:
    return _short("doc", canonical_url)


def representation_id(doc_id: str, content_sha256: str) -> str:
    return _short("rep", f"{doc_id}:{content_sha256}")


def retrieval_event_id(run_id: str, requested_url: str, seq: int) -> str:
    return _short("ret", f"{run_id}:{requested_url}:{seq}")


def fact_id(representation_id_: str, metric: str, pattern_ref: str, occurrence: int) -> str:
    return _short("fact", f"{representation_id_}:{metric}:{pattern_ref}:{occurrence}")


def event_id(document_id_: str, event_type: str, occurrence: int) -> str:
    return _short("evt", f"{document_id_}:{event_type}:{occurrence}")


def evidence_id(fact_or_event_id: str, version: int) -> str:
    return _short("evi", f"{fact_or_event_id}:{version}")


def io_id(event_id_: str, event_version: int) -> str:
    return _short("io", f"{event_id_}:{event_version}")


def delivery_id(io_id_: str, version: int, destination: str) -> str:
    return _short("dlv", f"{io_id_}:{version}:{destination}")


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
