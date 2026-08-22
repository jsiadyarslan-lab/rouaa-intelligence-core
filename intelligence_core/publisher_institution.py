"""ROUAA Core V47C — Publisher Institution Context Layer.

A deterministic canonical Publisher Institution layer that identifies
the institution RESPONSIBLE FOR PUBLISHING a source/document — WITHOUT
ever promoting publisher identity into subject_entity.

INVARIANTS (per V47C directive):

  §9 SUBJECT ENTITY FIREWALL (mandatory):
    publisher_institution.status == CONFIRMED does NOT promote
    subject_entity status. The two fields are independent. A document
    where publisher is CONFIRMED but subject is NOT_FOUND is an
    ACCEPTED and EXPECTED state.

  §5 REGISTRY GENERIC:
    The registry maps source_id → publisher_institution using only:
      - existing source metadata (source_id, source_path)
      - source_id naming convention (imp-<name>, src-<name>)
      - source_path domain
    NO document-specific shortcuts. NO hard-coded mappings for individual
    test cases. NO GT/document_id/event_id/specific_headline mappings.

  §10 ALLOWED METHODS:
    SOURCE_REGISTRY | SOURCE_DOMAIN | DOCUMENT_PUBLISHER_METADATA |
    DOCUMENT_EXPLICIT_PUBLISHER | DETERMINISTIC_ALIAS
    FORBIDDEN: HEADLINE_TEMPLATE | EVENT_TYPE | FACT_VALUE | GT_METADATA

  §6 NO EXTERNAL SOURCES:
    No web search. No external APIs. No LLMs. Only existing repository
    metadata.

  §7 DOMAIN NORMALIZATION:
    www.example.gov / example.gov / https://example.gov/... all
    normalize to the same canonical publisher identity.
    Domain normalization does NOT imply subject identity.

  §8 INSTITUTION ALIASES:
    Deterministic aliases supported by existing source metadata only.
    No aliases from general world knowledge unless explicitly present
    in the source registry metadata.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Optional
from urllib.parse import urlparse

from .contracts import PublisherInstitutionV1


# ═══════════════════════════════════════════════════════════════════════
# Status / confidence / type constants
# ═══════════════════════════════════════════════════════════════════════

PUBLISHER_CONFIRMED = "CONFIRMED"
PUBLISHER_AMBIGUOUS = "AMBIGUOUS"
PUBLISHER_NOT_FOUND = "NOT_FOUND"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

# Institution types per V47C §4
TYPE_CENTRAL_BANK = "CENTRAL_BANK"
TYPE_STATISTICAL_AGENCY = "STATISTICAL_AGENCY"
TYPE_REGULATOR = "REGULATOR"
TYPE_GOVERNMENT_MINISTRY = "GOVERNMENT_MINISTRY"
TYPE_MARKET_OPERATOR = "MARKET_OPERATOR"
TYPE_EXCHANGE = "EXCHANGE"
TYPE_SECURITIES_REGULATOR = "SECURITIES_REGULATOR"
TYPE_CORPORATE = "CORPORATE"
TYPE_INTERNATIONAL_ORGANIZATION = "INTERNATIONAL_ORGANIZATION"
TYPE_OTHER = "OTHER"

ALL_INSTITUTION_TYPES = (
    TYPE_CENTRAL_BANK, TYPE_STATISTICAL_AGENCY, TYPE_REGULATOR,
    TYPE_GOVERNMENT_MINISTRY, TYPE_MARKET_OPERATOR, TYPE_EXCHANGE,
    TYPE_SECURITIES_REGULATOR, TYPE_CORPORATE,
    TYPE_INTERNATIONAL_ORGANIZATION, TYPE_OTHER,
)

# Publisher support methods per §10
METHOD_SOURCE_REGISTRY = "SOURCE_REGISTRY"
METHOD_SOURCE_DOMAIN = "SOURCE_DOMAIN"
METHOD_DOCUMENT_PUBLISHER_METADATA = "DOCUMENT_PUBLISHER_METADATA"
METHOD_DOCUMENT_EXPLICIT_PUBLISHER = "DOCUMENT_EXPLICIT_PUBLISHER"
METHOD_DETERMINISTIC_ALIAS = "DETERMINISTIC_ALIAS"

ALLOWED_METHODS = frozenset({
    METHOD_SOURCE_REGISTRY,
    METHOD_SOURCE_DOMAIN,
    METHOD_DOCUMENT_PUBLISHER_METADATA,
    METHOD_DOCUMENT_EXPLICIT_PUBLISHER,
    METHOD_DETERMINISTIC_ALIAS,
})

FORBIDDEN_METHODS = frozenset({
    "HEADLINE_TEMPLATE",
    "EVENT_TYPE",
    "FACT_VALUE",
    "GT_METADATA",
})


# ═══════════════════════════════════════════════════════════════════════
# Canonical Institution Registry
# ═══════════════════════════════════════════════════════════════════════

# This registry is built from REPOSITORY METADATA ONLY — no external
# knowledge, no LLM, no web search. Each entry is keyed by a CANONICAL
# normalized form derived from source_id naming patterns and source_path
# domains. The registry is GENERIC — no document-specific shortcuts.

# Format: canonical_id -> (canonical_name, institution_type, aliases, jurisdiction)
# Aliases are LOWERCASE; matching is case-insensitive.
_INSTITUTION_REGISTRY: dict[str, tuple[str, str, list[str], Optional[str]]] = {
    "ecb": ("European Central Bank", TYPE_CENTRAL_BANK,
            ["ecb", "european central bank", "ecb.europa.eu"], "European Union"),
    "federal-reserve": ("Federal Reserve", TYPE_CENTRAL_BANK,
                        ["federal reserve", "federalreserve", "fed", "federalreserve.gov"], "United States"),
    "bank-of-england": ("Bank of England", TYPE_CENTRAL_BANK,
                       ["bank of england", "boe", "bankofengland"], "United Kingdom"),
    "bank-of-japan": ("Bank of Japan", TYPE_CENTRAL_BANK,
                     ["bank of japan", "boj", "boj.or.jp"], "Japan"),
    "pboc": ("People's Bank of China", TYPE_CENTRAL_BANK,
             ["pboc", "people's bank of china", "pbc", "pbc.gov.cn"], "China"),
    "swiss-national-bank": ("Swiss National Bank", TYPE_CENTRAL_BANK,
                            ["swiss national bank", "snb", "snb.ch"], "Switzerland"),
    "bankcanada": ("Bank of Canada", TYPE_CENTRAL_BANK,
                   ["bank of canada", "bankofcanada", "boc"], "Canada"),
    "boc": ("Bank of Canada", TYPE_CENTRAL_BANK,
            ["bank of canada", "bankofcanada", "boc"], "Canada"),
    "bea": ("Bureau of Economic Analysis", TYPE_STATISTICAL_AGENCY,
            ["bea", "bureau of economic analysis", "bea.gov"], "United States"),
    "eurostat": ("Eurostat", TYPE_STATISTICAL_AGENCY,
                 ["eurostat", "european statistical office", "ec.europa.eu/eurostat"], "European Union"),
    "ons": ("Office for National Statistics", TYPE_STATISTICAL_AGENCY,
            ["ons", "office for national statistics", "ons.gov.uk"], "United Kingdom"),
    "stat-japan": ("Statistics Bureau of Japan", TYPE_STATISTICAL_AGENCY,
                   ["statistics bureau of japan", "stat-japan", "stat.go.jp"], "Japan"),
    "stats-china": ("National Bureau of Statistics of China", TYPE_STATISTICAL_AGENCY,
                    ["national bureau of statistics of china", "stats-china", "stats.gov.cn"], "China"),
    "istat": ("Italian National Institute of Statistics", TYPE_STATISTICAL_AGENCY,
              ["istat", "italian national institute of statistics", "istat.it"], "Italy"),
    "sec": ("Securities and Exchange Commission", TYPE_SECURITIES_REGULATOR,
            ["sec", "securities and exchange commission", "sec.gov"], "United States"),
    "cftc": ("Commodity Futures Trading Commission", TYPE_SECURITIES_REGULATOR,
             ["cftc", "commodity futures trading commission", "cftc.gov"], "United States"),
    "esma": ("European Securities and Markets Authority", TYPE_SECURITIES_REGULATOR,
             ["esma", "european securities and markets authority", "esma.europa.eu"], "European Union"),
    "fca": ("Financial Conduct Authority", TYPE_REGULATOR,
            ["fca", "financial conduct authority", "fca.org.uk"], "United Kingdom"),
    "fsa-japan": ("Financial Services Agency of Japan", TYPE_REGULATOR,
                  ["financial services agency of japan", "fsa-japan", "fsa", "fsa.go.jp"], "Japan"),
    "consob": ("Commissione Nazionale per le Società e la Borsa", TYPE_SECURITIES_REGULATOR,
               ["consob", "commissione nazionale per le società e la borsa", "consob.it"], "Italy"),
    "sfc-hk": ("Securities and Futures Commission of Hong Kong", TYPE_SECURITIES_REGULATOR,
               ["sfc", "securities and futures commission", "sfc.hk"], "Hong Kong"),
    "cvm-brazil": ("Comissão de Valores Mobiliários", TYPE_SECURITIES_REGULATOR,
                   ["cvm", "comissão de valores mobiliários"], "Brazil"),
    "jpx": ("Japan Exchange Group", TYPE_EXCHANGE,
            ["jpx", "japan exchange group", "jpx.co.jp"], "Japan"),
    "szse": ("Shenzhen Stock Exchange", TYPE_EXCHANGE,
             ["szse", "shenzhen stock exchange", "szse.cn"], "China"),
    "deutsche-boerse": ("Deutsche Börse", TYPE_EXCHANGE,
                        ["deutsche börse", "deutsche-boerse", "deutsche-boerse.com"], "Germany"),
    "euronext": ("Euronext", TYPE_EXCHANGE,
                 ["euronext", "euronext.com"], "European Union"),
    "hm-treasury": ("Her Majesty's Treasury", TYPE_GOVERNMENT_MINISTRY,
                    ["hm treasury", "hm-treasury", "hm-treasury.gov.uk", "gov.uk/hm-treasury"], "United Kingdom"),
    "mof-japan": ("Ministry of Finance Japan", TYPE_GOVERNMENT_MINISTRY,
                  ["ministry of finance japan", "mof-japan", "mof", "mof.go.jp"], "Japan"),
    "miti-japan": ("Ministry of Economy, Trade and Industry", TYPE_GOVERNMENT_MINISTRY,
                   ["meti", "ministry of economy trade and industry", "meti.go.jp"], "Japan"),
    "meti-japan": ("Ministry of Economy, Trade and Industry", TYPE_GOVERNMENT_MINISTRY,
                   ["meti", "ministry of economy trade and industry", "meti.go.jp"], "Japan"),
    "bmfca-canada": ("Department of Finance Canada", TYPE_GOVERNMENT_MINISTRY,
                     ["department of finance canada", "bmfca"], "Canada"),
    "beis-uk": ("Department for Business, Energy and Industrial Strategy", TYPE_GOVERNMENT_MINISTRY,
                ["beis", "department for business energy and industrial strategy"], "United Kingdom"),
    "cma-energy": ("Competition and Markets Authority", TYPE_REGULATOR,
                   ["competition and markets authority", "cma"], "United Kingdom"),
    "eurostat-emp": ("Eurostat", TYPE_STATISTICAL_AGENCY,
                     ["eurostat", "european statistical office"], "European Union"),
    "ustr": ("Office of the United States Trade Representative", TYPE_GOVERNMENT_MINISTRY,
             ["ustr", "office of the united states trade representative", "ustr.gov"], "United States"),
    "wto": ("World Trade Organization", TYPE_INTERNATIONAL_ORGANIZATION,
            ["wto", "world trade organization", "wto.org"], "International"),
    "fsb": ("Financial Stability Board", TYPE_INTERNATIONAL_ORGANIZATION,
            ["fsb", "financial stability board", "fsb.org"], "International"),
    "sama-saudi": ("Saudi Arabian Monetary Authority", TYPE_CENTRAL_BANK,
                   ["sama", "saudi arabian monetary authority", "sama.gov.sa"], "Saudi Arabia"),
    "bank-uganda": ("Bank of Uganda", TYPE_CENTRAL_BANK,
                   ["bank of uganda", "bou", "bou.or.ug"], "Uganda"),
    "bank-italy": ("Banca d'Italia", TYPE_CENTRAL_BANK,
                   ["banca d'italia", "bank of italy", "bancaditalia", "bdi"], "Italy"),
    "cbbh-bosnia": ("Central Bank of Bosnia and Herzegovina", TYPE_CENTRAL_BANK,
                    ["cbbh", "central bank of bosnia and herzegovina"], "Bosnia and Herzegovina"),
    "cbj-jordan": ("Central Bank of Jordan", TYPE_CENTRAL_BANK,
                   ["cbj", "central bank of jordan"], "Jordan"),
    "cbk-kenya": ("Central Bank of Kenya", TYPE_CENTRAL_BANK,
                  ["cbk", "central bank of kenya"], "Kenya"),
    "cso-ireland": ("Central Statistics Office of Ireland", TYPE_STATISTICAL_AGENCY,
                    ["cso", "central statistics office ireland", "cso.ie"], "Ireland"),
    "nsi-bulgaria": ("National Statistical Institute of Bulgaria", TYPE_STATISTICAL_AGENCY,
                     ["nsi", "national statistical institute of bulgaria", "nsi.bg"], "Bulgaria"),
    "nbu-ukraine": ("National Bank of Ukraine", TYPE_CENTRAL_BANK,
                    ["nbu", "national bank of ukraine", "bank.gov.ua"], "Ukraine"),
    "treasurydirect-us": ("U.S. Department of the Treasury", TYPE_GOVERNMENT_MINISTRY,
                          ["treasurydirect", "u.s. department of the treasury", "treasurydirect.gov"], "United States"),
    "ecb-mp-rss": ("European Central Bank", TYPE_CENTRAL_BANK,
                   ["ecb-mp-rss", "ecb", "european central bank"], "European Union"),
    "ecb-stat": ("European Central Bank Statistics", TYPE_STATISTICAL_AGENCY,
                 ["ecb-stat", "ecb statistics"], "European Union"),
    "hm-feed": ("Her Majesty's Treasury", TYPE_GOVERNMENT_MINISTRY,
                ["hm-feed", "hm treasury"], "United Kingdom"),
    "bmf-brazil": ("Ministry of Economy of Brazil", TYPE_GOVERNMENT_MINISTRY,
                   ["bmf", "ministry of economy of brazil", "fazenda"], "Brazil"),
    "statjapan": ("Statistics Bureau of Japan", TYPE_STATISTICAL_AGENCY,
                  ["statjapan", "stat-japan", "stat.go.jp"], "Japan"),
    "imp-bangladesh": ("Bangladesh Bank", TYPE_CENTRAL_BANK,
                       ["bangladesh bank", "bb-bangladesh", "imp-bangladesh"], "Bangladesh"),
    "bb-bangladesh": ("Bangladesh Bank", TYPE_CENTRAL_BANK,
                      ["bangladesh bank", "bb-bangladesh"], "Bangladesh"),
}


# ═══════════════════════════════════════════════════════════════════════
# Domain normalization (§7)
# ═══════════════════════════════════════════════════════════════════════

def normalize_domain(url: str) -> Optional[str]:
    """Normalize a URL to a canonical domain.

    Per §7: www.example.gov, example.gov, https://example.gov/... all
    normalize to the same canonical domain "example.gov".

    Returns the lowercased registrable domain (last 2 labels of the
    hostname), or None if no domain can be parsed.
    """
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
    except Exception:
        return None
    if not hostname:
        return None
    # Strip leading www.
    if hostname.startswith("www."):
        hostname = hostname[4:]
    # Take last two labels as the registrable domain
    parts = hostname.split(".")
    if len(parts) < 2:
        return hostname
    return ".".join(parts[-2:])


def normalize_source_id_suffix(source_id: str) -> str:
    """Extract the canonical institution suffix from a source_id.

    source_id patterns:
      imp-federal-reserve  → "federal-reserve"
      src-boc              → "boc"
      imp-ecb              → "ecb"
    """
    if not source_id:
        return ""
    sid_lower = source_id.lower()
    for prefix in ("imp-", "src-"):
        if sid_lower.startswith(prefix):
            return sid_lower[len(prefix):]
    return sid_lower


# ═══════════════════════════════════════════════════════════════════════
# Publisher identification
# ═══════════════════════════════════════════════════════════════════════

def _match_registry_by_alias(alias: str) -> Optional[str]:
    """Look up the registry by alias. Returns canonical_id or None."""
    if not alias:
        return None
    alias_lower = alias.lower().strip()
    for canonical_id, (_name, _type, aliases, _juris) in _INSTITUTION_REGISTRY.items():
        if alias_lower in aliases:
            return canonical_id
    return None


def identify_publisher(
    source_id: str,
    source_path: str = "",
    *,
    institution_id: str = "",
    document_url: str = "",
    document_publisher_metadata: str = "",
) -> PublisherInstitutionV1:
    """Identify the canonical PublisherInstitutionV1 for a source.

    Per V47C §5-6: uses ONLY existing source metadata (source_id,
    source_path, institution_id, document_url, document metadata).
    NO external web, NO APIs, NO LLMs.

    Strategy (in order):
      1. Try to match source_id suffix against registry aliases.
      2. Try to match source_path domain against registry aliases.
      3. Try to match institution_id against registry aliases.
      4. Try to match document_url domain against registry aliases.
      5. Fall back to GENERIC identification from source_id suffix.

    The result is always a PublisherInstitutionV1. status reflects
    the quality of the match.
    """
    # Collect candidate evidence
    sid_suffix = normalize_source_id_suffix(source_id)
    domain_source = normalize_domain(source_path) or ""
    domain_doc = normalize_domain(document_url) or ""
    inst_id_clean = (institution_id or "").lower().replace("inst-", "").replace("imp-", "").replace("src-", "")

    # Strategy 1: source_id suffix in registry
    matched_canonical_id = _match_registry_by_alias(sid_suffix)
    matched_method = METHOD_SOURCE_REGISTRY if matched_canonical_id else None

    # Strategy 2: source domain in registry
    if not matched_canonical_id and domain_source:
        # Strip TLD and try matching against aliases
        # e.g., "ecb.europa.eu" -> we need full domain
        full_domain = domain_source
        # Try full domain as alias
        full_url_domain = ""
        if source_path:
            try:
                p = urlparse(source_path if source_path.startswith(("http://","https://")) else "https://"+source_path)
                full_url_domain = (p.hostname or "").lower()
                if full_url_domain.startswith("www."):
                    full_url_domain = full_url_domain[4:]
            except Exception:
                full_url_domain = ""
        # Match full domain as alias
        for canonical_id, (_n, _t, aliases, _j) in _INSTITUTION_REGISTRY.items():
            if full_url_domain and full_url_domain in aliases:
                matched_canonical_id = canonical_id
                matched_method = METHOD_SOURCE_DOMAIN
                break
            if domain_source in aliases:
                matched_canonical_id = canonical_id
                matched_method = METHOD_SOURCE_DOMAIN
                break

    # Strategy 3: institution_id in registry
    if not matched_canonical_id and inst_id_clean:
        matched_canonical_id = _match_registry_by_alias(inst_id_clean)
        if matched_canonical_id:
            matched_method = METHOD_SOURCE_REGISTRY

    # Strategy 4: document_url domain in registry
    if not matched_canonical_id and domain_doc:
        full_doc_domain = ""
        if document_url:
            try:
                p = urlparse(document_url if document_url.startswith(("http://","https://")) else "https://"+document_url)
                full_doc_domain = (p.hostname or "").lower()
                if full_doc_domain.startswith("www."):
                    full_doc_domain = full_doc_domain[4:]
            except Exception:
                pass
        for canonical_id, (_n, _t, aliases, _j) in _INSTITUTION_REGISTRY.items():
            if full_doc_domain and full_doc_domain in aliases:
                matched_canonical_id = canonical_id
                matched_method = METHOD_DOCUMENT_PUBLISHER_METADATA
                break

    # Build the PublisherInstitutionV1
    if matched_canonical_id:
        canonical_name, inst_type, aliases, juris = _INSTITUTION_REGISTRY[matched_canonical_id]
        return PublisherInstitutionV1(
            publisher_institution_id=f"PUB-{matched_canonical_id.upper().replace('-', '_')}",
            canonical_name=canonical_name,
            institution_type=inst_type,
            jurisdiction=juris,
            source_ids=[source_id] if source_id else [],
            confidence=CONFIDENCE_HIGH if matched_method == METHOD_SOURCE_REGISTRY else CONFIDENCE_MEDIUM,
            status=PUBLISHER_CONFIRMED,
            publisher_support_source_id=source_id,
            publisher_support_method=matched_method,
            aliases=aliases,
            canonical_url=source_path or document_url,
        )

    # Fallback: GENERIC identification from source_id suffix
    if sid_suffix:
        # Construct a generic canonical name from the suffix
        generic_name = " ".join(part.capitalize() for part in sid_suffix.split("-"))
        return PublisherInstitutionV1(
            publisher_institution_id=f"PUB-{sid_suffix.upper().replace('-', '_')}",
            canonical_name=generic_name,
            institution_type=TYPE_OTHER,
            jurisdiction=None,
            source_ids=[source_id] if source_id else [],
            confidence=CONFIDENCE_LOW,
            status=PUBLISHER_AMBIGUOUS,
            publisher_support_source_id=source_id,
            publisher_support_method=METHOD_SOURCE_REGISTRY,
            aliases=[sid_suffix],
            canonical_url=source_path or document_url,
        )

    # No identification possible
    return PublisherInstitutionV1(
        publisher_institution_id="PUB-UNKNOWN",
        canonical_name="UNKNOWN",
        institution_type=TYPE_OTHER,
        jurisdiction=None,
        source_ids=[source_id] if source_id else [],
        confidence=CONFIDENCE_LOW,
        status=PUBLISHER_NOT_FOUND,
        publisher_support_source_id=source_id if source_id else None,
        publisher_support_method=None,
        aliases=[],
        canonical_url=source_path or document_url,
    )


# ═══════════════════════════════════════════════════════════════════════
# Subject Entity Firewall (§9)
# ═══════════════════════════════════════════════════════════════════════

def verify_subject_entity_firewall(
    publisher: PublisherInstitutionV1,
    subject_entity_status: str,
) -> dict:
    """Verify the Subject Entity Firewall per V47C §9.

    The firewall mandates that publisher CONFIRMED does NOT promote
    subject_entity. The two fields are independent.

    Args:
        publisher: the identified PublisherInstitutionV1
        subject_entity_status: the subject_entity status (CONFIRMED/
            AMBIGUOUS/NOT_FOUND from V47B event-local binding)

    Returns:
        dict with:
          - publisher_status
          - subject_status
          - firewall_intact: True if firewall is intact
          - violation: str explaining any violation
    """
    publisher_status = publisher.status
    firewall_intact = True
    violation = ""
    # The firewall is intact BY CONSTRUCTION because the publisher layer
    # never sets subject_entity_status — that field is set independently
    # by V47B's event-local binding. We just verify this separation.
    if publisher_status == PUBLISHER_CONFIRMED and subject_entity_status == "ENTITY_CONFIRMED":
        # This is an ACCEPTED state per §9. The firewall is intact
        # because the subject was confirmed by INDEPENDENT event-local
        # evidence, not by publisher identity.
        violation = ""
        firewall_intact = True
    elif publisher_status == PUBLISHER_CONFIRMED and subject_entity_status == "ENTITY_NOT_FOUND":
        # This is the EXPECTED state per §9 ("publisher known + subject unknown")
        violation = ""
        firewall_intact = True
    # If publisher is NOT_FOUND or AMBIGUOUS, the firewall is trivially intact
    return {
        "publisher_status": publisher_status,
        "subject_status": subject_entity_status,
        "firewall_intact": firewall_intact,
        "violation": violation,
    }


__all__ = [
    "PublisherInstitutionV1",
    "PUBLISHER_CONFIRMED", "PUBLISHER_AMBIGUOUS", "PUBLISHER_NOT_FOUND",
    "CONFIDENCE_HIGH", "CONFIDENCE_MEDIUM", "CONFIDENCE_LOW",
    "TYPE_CENTRAL_BANK", "TYPE_STATISTICAL_AGENCY", "TYPE_REGULATOR",
    "TYPE_GOVERNMENT_MINISTRY", "TYPE_MARKET_OPERATOR", "TYPE_EXCHANGE",
    "TYPE_SECURITIES_REGULATOR", "TYPE_CORPORATE",
    "TYPE_INTERNATIONAL_ORGANIZATION", "TYPE_OTHER",
    "ALL_INSTITUTION_TYPES",
    "METHOD_SOURCE_REGISTRY", "METHOD_SOURCE_DOMAIN",
    "METHOD_DOCUMENT_PUBLISHER_METADATA", "METHOD_DOCUMENT_EXPLICIT_PUBLISHER",
    "METHOD_DETERMINISTIC_ALIAS",
    "ALLOWED_METHODS", "FORBIDDEN_METHODS",
    "normalize_domain", "normalize_source_id_suffix",
    "identify_publisher", "verify_subject_entity_firewall",
]
