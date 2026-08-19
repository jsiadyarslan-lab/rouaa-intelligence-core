"""ROUAA Global Official Source Network — Source Registry.

Per EXECUTION DIRECTIVE — GLOBAL OFFICIAL SOURCE EXPANSION V1 §4:
  The Source Registry becomes a first-class Core asset.

For every source record (§4 fields):
  source_id, institution_id, institution_name, country, jurisdiction, region,
  source_class, domain, official_domain, canonical_url, acquisition_endpoint,
  endpoint_type, acquisition_method, language, coverage_topics, frequency,
  authority_level, qualification_status, health_status, last_verified_at,
  last_success_at, last_document_at, last_event_at

Authority levels (§6):
  PRIMARY_OFFICIAL, STATUTORY_REGULATOR, OFFICIAL_STATISTICAL,
  OFFICIAL_MARKET_OPERATOR, OFFICIAL_INTERNATIONAL, SECONDARY_OFFICIAL

Qualification states (§5):
  DISCOVERED, DOMAIN_VERIFIED, ENDPOINT_VERIFIED, QUALIFIED,
  PRODUCTION_READY, BLOCKED, REQUIRES_REMEDIATION

Health states (§9):
  HEALTHY, DEGRADED, STALE, BLOCKED, ENDPOINT_MOVED, NO_CONTENT, UNSUPPORTED

Domain classes (§2): 40+ economic/financial domains
Geographic coverage (§3): 18+ regions

The registry is persisted as JSONL (append-only) + JSON index for queries.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ── Enums (as strings for JSON serialization) ──

AUTHORITY_LEVELS = [
    "PRIMARY_OFFICIAL",        # Central banks, finance ministries (highest authority)
    "STATUTORY_REGULATOR",     # SEC, CFTC, FCA, ESMA (statutory regulators)
    "OFFICIAL_STATISTICAL",    # BEA, Eurostat, ONS (official statistical agencies)
    "OFFICIAL_MARKET_OPERATOR", # Stock exchanges (NYSE, LSE, TSE)
    "OFFICIAL_INTERNATIONAL",  # IMF, BIS, World Bank, OECD, WTO
    "SECONDARY_OFFICIAL",      # Regional/state-level official bodies
]

QUALIFICATION_STATES = [
    "DISCOVERED",
    "DOMAIN_VERIFIED",
    "ENDPOINT_VERIFIED",
    "QUALIFIED",
    "PRODUCTION_READY",
    "BLOCKED",
    "REQUIRES_REMEDIATION",
]

HEALTH_STATES = [
    "HEALTHY",
    "DEGRADED",
    "STALE",
    "BLOCKED",
    "ENDPOINT_MOVED",
    "NO_CONTENT",
    "UNSUPPORTED",
]

ACQUISITION_METHODS = [
    "RSS", "ATOM", "HTML", "OFFICIAL_API", "CSV", "JSON", "PDF", "OTHER",
]

DOMAIN_CLASSES = [
    # Financial & Monetary
    "central_bank", "monetary_authority", "finance_ministry", "treasury",
    # Statistical
    "statistical_agency", "national_economic_agency", "industry_statistics_agency",
    # Regulators
    "securities_regulator", "financial_regulator", "banking_regulator",
    "insurance_regulator", "pension_regulator", "capital_markets_authority",
    "competition_authority", "consumer_protection_authority",
    # Markets
    "stock_exchange", "futures_derivatives_exchange", "market_supervisor",
    # Trade & Industry
    "trade_ministry", "customs_authority", "export_import_agency",
    "industrial_ministry", "corporate_registrar", "insolvency_authority",
    # Energy & Commodities
    "energy_ministry", "energy_regulator", "electricity_authority",
    "oil_gas_authority", "commodity_regulator", "mining_authority",
    "agricultural_agency",
    # Social & Infrastructure
    "labor_ministry", "employment_agency", "housing_agency",
    "real_estate_regulator", "infrastructure_agency", "transport_authority",
    "telecom_regulator", "technology_digital_authority",
    # Environmental
    "environmental_carbon_authority",
    # International
    "international_financial_institution", "international_economic_institution",
    "regional_economic_institution", "official_development_institution",
    "sovereign_wealth_institution",
]

GEOGRAPHIC_REGIONS = [
    "US", "CA", "LATAM", "EU", "UK", "NORDICS", "EASTERN_EUROPE",
    "MIDDLE_EAST", "NORTH_AFRICA", "SUB_SAHARAN_AFRICA", "CN", "JP",
    "KR", "IN", "SOUTHEAST_ASIA", "AU", "NZ", "CENTRAL_ASIA", "GLOBAL",
]

TOPIC_COVERAGE = [
    "monetary_policy", "inflation", "interest_rates", "employment", "gdp",
    "trade", "fiscal_policy", "taxes", "banking", "capital_markets",
    "securities", "insurance", "pensions", "corporate_regulation",
    "competition", "energy", "oil", "gas", "electricity", "renewables",
    "mining", "commodities", "agriculture", "housing", "construction",
    "manufacturing", "transport", "technology", "telecommunications",
    "consumer_finance", "external_sector", "public_debt", "government_finance",
]


@dataclass
class SourceRecord:
    """A single source in the Global Official Source Network."""
    # Identity
    source_id: str
    institution_id: str
    institution_name: str
    country: str
    jurisdiction: str
    region: str

    # Classification
    source_class: str          # one of DOMAIN_CLASSES
    domain: str                # economic/financial domain
    authority_level: str       # one of AUTHORITY_LEVELS

    # Acquisition
    official_domain: str
    canonical_url: str
    acquisition_endpoint: str
    endpoint_type: str          # RSS / ATOM / HTML / API / etc.
    acquisition_method: str     # one of ACQUISITION_METHODS
    language: str
    coverage_topics: list = field(default_factory=list)
    frequency: str = "unknown"  # daily / weekly / monthly / event_driven

    # Qualification + Health
    qualification_status: str = "DISCOVERED"
    health_status: str = "UNSUPPORTED"
    last_verified_at: str = ""
    last_success_at: str = ""
    last_document_at: str = ""
    last_event_at: str = ""

    # Discovery metadata
    discovered_at: str = ""
    discovery_wave: str = "A"
    qualification_notes: str = ""

    def to_dict(self) -> dict: return asdict(self)


class SourceRegistry:
    """Persistent Source Registry — JSONL store + in-memory index."""

    def __init__(self, root: str = "source_registry"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "sources.jsonl"
        # In-memory index (source_id → record)
        self._index: dict[str, SourceRecord] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = SourceRecord(**json.loads(line))
                    self._index[rec.source_id] = rec

    def _append(self, record: SourceRecord):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def register(self, record: SourceRecord) -> bool:
        """Register a new source. Returns True if new, False if duplicate."""
        if record.source_id in self._index:
            return False
        if not record.discovered_at:
            record.discovered_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._index[record.source_id] = record
        self._append(record)
        return True

    def update(self, source_id: str, **fields):
        """Update fields on an existing source (appends a new JSONL row)."""
        if source_id not in self._index:
            return False
        rec = self._index[source_id]
        for k, v in fields.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        self._append(rec)
        return True

    def get(self, source_id: str) -> SourceRecord | None:
        return self._index.get(source_id)

    def all(self) -> list[SourceRecord]:
        return list(self._index.values())

    def by_status(self, status: str) -> list[SourceRecord]:
        return [r for r in self._index.values() if r.qualification_status == status]

    def by_health(self, health: str) -> list[SourceRecord]:
        return [r for r in self._index.values() if r.health_status == health]

    def by_country(self, country: str) -> list[SourceRecord]:
        return [r for r in self._index.values() if r.country == country]

    def by_class(self, source_class: str) -> list[SourceRecord]:
        return [r for r in self._index.values() if r.source_class == source_class]

    def by_authority(self, authority: str) -> list[SourceRecord]:
        return [r for r in self._index.values() if r.authority_level == authority]

    def by_wave(self, wave: str) -> list[SourceRecord]:
        return [r for r in self._index.values() if r.discovery_wave == wave]

    def count_by(self, field: str) -> dict:
        """Count sources grouped by a field."""
        from collections import Counter
        return dict(Counter(getattr(r, field) for r in self._index.values()))

    def stats(self) -> dict:
        """Summary statistics."""
        from collections import Counter
        all_recs = list(self._index.values())
        return {
            "total_sources": len(all_recs),
            "by_qualification": dict(Counter(r.qualification_status for r in all_recs)),
            "by_health": dict(Counter(r.health_status for r in all_recs)),
            "by_authority": dict(Counter(r.authority_level for r in all_recs)),
            "by_country": dict(Counter(r.country for r in all_recs)),
            "by_region": dict(Counter(r.region for r in all_recs)),
            "by_source_class": dict(Counter(r.source_class for r in all_recs)),
            "by_acquisition_method": dict(Counter(r.acquisition_method for r in all_recs)),
            "by_language": dict(Counter(r.language for r in all_recs)),
            "by_wave": dict(Counter(r.discovery_wave for r in all_recs)),
        }
