"""V2 §2 — Wave C Source Expansion: add 60+ NEW official sources.

Focus on coverage gaps identified in Wave B:
  - Insurance regulators (more)
  - Energy authorities (more)
  - Mining authorities
  - Agricultural agencies
  - Transport authorities
  - Competition authorities
  - Corporate registrars
  - Environmental/carbon markets authorities
  - More central banks + statistical agencies in undercovered regions

Target: ≥250 cumulative sources (192 Wave A+B + ~60 Wave C)
"""
from __future__ import annotations

WAVE_C_CATALOG = [

    # ════════════════════════════════════════════════════════
    # INSURANCE REGULATORS — ADDITIONAL (6)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-idda-ireland", "institution_id": "IDDA", "institution_name": "Insurance Development Authority Ireland",
     "country": "IE", "jurisdiction": "IE", "region": "EU", "source_class": "insurance_regulator",
     "domain": "insurance_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "centralbank.ie", "canonical_url": "https://www.centralbank.ie",
     "acquisition_endpoint": "https://www.centralbank.ie/news-media",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["insurance", "banking"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-dnb-netherlands", "institution_id": "DNB", "institution_name": "De Nederlandsche Bank",
     "country": "NL", "jurisdiction": "NL", "region": "EU", "source_class": "insurance_regulator",
     "domain": "financial_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "dnb.nl", "canonical_url": "https://www.dnb.nl",
     "acquisition_endpoint": "https://www.dnb.nl/en/news/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["banking", "insurance", "pensions"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-finansinspektionen-se", "institution_id": "FI", "institution_name": "Finansinspektionen (Sweden)",
     "country": "SE", "jurisdiction": "SE", "region": "NORDICS", "source_class": "financial_regulator",
     "domain": "financial_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "fi.se", "canonical_url": "https://www.fi.se",
     "acquisition_endpoint": "https://www.fi.se/en/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["banking", "insurance", "securities"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-fsa-jp", "institution_id": "FSAJP", "institution_name": "Financial Services Agency Japan",
     "country": "JP", "jurisdiction": "JP", "region": "JP", "source_class": "insurance_regulator",
     "domain": "financial_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "fsa.go.jp", "canonical_url": "https://www.fsa.go.jp",
     "acquisition_endpoint": "https://www.fsa.go.jp/en/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["banking", "insurance", "securities"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-iais-intl", "institution_id": "IAIS", "institution_name": "International Association of Insurance Supervisors",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "insurance_regulation", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "iaisweb.org", "canonical_url": "https://www.iaisweb.org",
     "acquisition_endpoint": "https://www.iaisweb.org/news/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["insurance"],
     "frequency": "monthly", "discovery_wave": "C"},

    {"source_id": "src-iroc-canada", "institution_id": "IROCC", "institution_name": "Insurance Companies Regulatory (Canada)",
     "country": "CA", "jurisdiction": "CA", "region": "CA", "source_class": "insurance_regulator",
     "domain": "insurance_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "osfi-bsif.gc.ca", "canonical_url": "https://www.osfi-bsif.gc.ca",
     "acquisition_endpoint": "https://www.osfi-bsif.gc.ca/Eng/wt-ow/Pages/default.aspx",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["insurance", "pensions"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # ENERGY AUTHORITIES — ADDITIONAL (8)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-irena", "institution_id": "IRENA", "institution_name": "International Renewable Energy Agency",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "energy_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "irena.org", "canonical_url": "https://www.irena.org",
     "acquisition_endpoint": "https://www.irena.org/News",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["renewables", "energy"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-nrcan", "institution_id": "NRCAN", "institution_name": "Natural Resources Canada",
     "country": "CA", "jurisdiction": "CA", "region": "CA", "source_class": "energy_ministry",
     "domain": "energy_statistics", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "nrcan.gc.ca", "canonical_url": "https://www.nrcan.gc.ca",
     "acquisition_endpoint": "https://www.nrcan.gc.ca",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["energy", "mining"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-beis-energy-uk", "institution_id": "BEISE", "institution_name": "BEIS Energy Statistics UK",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "energy_regulator",
     "domain": "energy_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "gov.uk", "canonical_url": "https://www.gov.uk/government/organisations/department-for-energy-security-and-net-zero",
     "acquisition_endpoint": "https://www.gov.uk/government/organisations/department-for-energy-security-and-net-zero.atom",
     "endpoint_type": "ATOM", "acquisition_method": "ATOM", "language": "en",
     "coverage_topics": ["energy", "renewables"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-cre-france", "institution_id": "CRE", "institution_name": "Commission de Régulation de l'Énergie (France)",
     "country": "FR", "jurisdiction": "FR", "region": "EU", "source_class": "energy_regulator",
     "domain": "energy_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "cre.fr", "canonical_url": "https://www.cre.fr",
     "acquisition_endpoint": "https://www.cre.fr/en",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["electricity", "gas"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-bnetza-de", "institution_id": "BNETZADE", "institution_name": "Bundesnetzagentor Energy (Germany)",
     "country": "DE", "jurisdiction": "DE", "region": "EU", "source_class": "energy_regulator",
     "domain": "energy_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "bundesnetzagentur.de", "canonical_url": "https://www.bundesnetzagentur.de",
     "acquisition_endpoint": "https://www.bundesnetzagentur.de/EN/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["electricity", "gas", "telecommunications"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-aer-canada", "institution_id": "AER", "institution_name": "Canada Energy Regulator",
     "country": "CA", "jurisdiction": "CA", "region": "CA", "source_class": "energy_regulator",
     "domain": "energy_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "cer-rec.gc.ca", "canonical_url": "https://www.cer-rec.gc.ca",
     "acquisition_endpoint": "https://www.cer-rec.gc.ca",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["oil", "gas", "electricity"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-acea-eu", "institution_id": "ACEA", "institution_name": "European Automobile Manufacturers (Energy)",
     "country": "EU", "jurisdiction": "EU", "region": "EU", "source_class": "industrial_ministry",
     "domain": "industrial_statistics", "authority_level": "SECONDARY_OFFICIAL",
     "official_domain": "acea.auto", "canonical_url": "https://www.acea.auto",
     "acquisition_endpoint": "https://www.acea.auto/news/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["manufacturing", "transport"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-entsog-eu", "institution_id": "ENTSOG", "institution_name": "European Network of Transmission System Operators for Gas",
     "country": "EU", "jurisdiction": "EU", "region": "EU", "source_class": "energy_regulator",
     "domain": "energy_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "entsog.eu", "canonical_url": "https://www.entsog.eu",
     "acquisition_endpoint": "https://www.entsog.eu/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["gas"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # MINING AUTHORITIES (4)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-icmm", "institution_id": "ICMM", "institution_name": "International Council on Mining and Metals",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "commodity_regulator",
     "domain": "mining_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "icmm.com", "canonical_url": "https://www.icmm.com",
     "acquisition_endpoint": "https://www.icmm.com/en-gb/news",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["mining"],
     "frequency": "monthly", "discovery_wave": "C"},

    {"source_id": "src-mcaus", "institution_id": "MCA", "institution_name": "Minerals Council of Australia",
     "country": "AU", "jurisdiction": "AU", "region": "AU", "source_class": "mining_authority",
     "domain": "mining_statistics", "authority_level": "SECONDARY_OFFICIAL",
     "official_domain": "minerals.org.au", "canonical_url": "https://www.minerals.org.au",
     "acquisition_endpoint": "https://www.minerals.org.au/news",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["mining"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-migme", "institution_id": "MIG", "institution_name": "Mining Inspectorate of Sweden",
     "country": "SE", "jurisdiction": "SE", "region": "NORDICS", "source_class": "mining_authority",
     "domain": "mining_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "sgu.se", "canonical_url": "https://www.sgu.se",
     "acquisition_endpoint": "https://www.sgu.se/en/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["mining"],
     "frequency": "monthly", "discovery_wave": "C"},

    {"source_id": "src-dmecs-za", "institution_id": "DMR", "institution_name": "Department of Mineral Resources (South Africa)",
     "country": "ZA", "jurisdiction": "ZA", "region": "SUB_SAHARAN_AFRICA", "source_class": "mining_authority",
     "domain": "mining_regulation", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "dmr.gov.za", "canonical_url": "https://www.dmr.gov.za",
     "acquisition_endpoint": "https://www.dmr.gov.za",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["mining"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # AGRICULTURAL AGENCIES (5)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-usda", "institution_id": "USDA", "institution_name": "US Department of Agriculture",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "agricultural_agency",
     "domain": "agricultural_statistics", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "usda.gov", "canonical_url": "https://www.usda.gov",
     "acquisition_endpoint": "https://www.usda.gov/newsroom/rss",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["agriculture"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-fao", "institution_id": "FAO", "institution_name": "Food and Agriculture Organization",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "agricultural_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "fao.org", "canonical_url": "https://www.fao.org",
     "acquisition_endpoint": "https://www.fao.org/newsroom/rss/en/",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["agriculture"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-ers-usda", "institution_id": "ERS", "institution_name": "Economic Research Service USDA",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "agricultural_agency",
     "domain": "agricultural_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "ers.usda.gov", "canonical_url": "https://www.ers.usda.gov",
     "acquisition_endpoint": "https://www.ers.usda.gov/rss/",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["agriculture", "trade"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-daff-au", "institution_id": "DAFF", "institution_name": "Department of Agriculture Fisheries and Forestry (Australia)",
     "country": "AU", "jurisdiction": "AU", "region": "AU", "source_class": "agricultural_agency",
     "domain": "agricultural_statistics", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "agriculture.gov.au", "canonical_url": "https://www.agriculture.gov.au",
     "acquisition_endpoint": "https://www.agriculture.gov.au/news",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["agriculture"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-defra-uk", "institution_id": "DEFRA", "institution_name": "DEFRA (UK)",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "agricultural_agency",
     "domain": "agricultural_statistics", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "gov.uk", "canonical_url": "https://www.gov.uk/government/organisations/department-for-environment-food-rural-affairs",
     "acquisition_endpoint": "https://www.gov.uk/government/organisations/department-for-environment-food-rural-affairs.atom",
     "endpoint_type": "ATOM", "acquisition_method": "ATOM", "language": "en",
     "coverage_topics": ["agriculture"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # TRANSPORT AUTHORITIES (5)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-dot-us", "institution_id": "DOT", "institution_name": "US Department of Transportation",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "transport_authority",
     "domain": "transport_statistics", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "transportation.gov", "canonical_url": "https://www.transportation.gov",
     "acquisition_endpoint": "https://www.transportation.gov/rss",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["transport"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-dft-uk", "institution_id": "DFT", "institution_name": "Department for Transport (UK)",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "transport_authority",
     "domain": "transport_statistics", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "gov.uk", "canonical_url": "https://www.gov.uk/government/organisations/department-for-transport",
     "acquisition_endpoint": "https://www.gov.uk/government/organisations/department-for-transport.atom",
     "endpoint_type": "ATOM", "acquisition_method": "ATOM", "language": "en",
     "coverage_topics": ["transport"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-bts-us", "institution_id": "BTS", "institution_name": "Bureau of Transportation Statistics",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "statistical_agency",
     "domain": "transport_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "bts.gov", "canonical_url": "https://www.bts.gov",
     "acquisition_endpoint": "https://www.bts.gov/rss",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["transport"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-imo-intl", "institution_id": "IMO", "institution_name": "International Maritime Organization",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "transport_regulation", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "imo.org", "canonical_url": "https://www.imo.org",
     "acquisition_endpoint": "https://www.imo.org/en/MediaCentre/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["transport", "trade"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-icao-intl", "institution_id": "ICAO", "institution_name": "International Civil Aviation Organization",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "transport_regulation", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "icao.int", "canonical_url": "https://www.icao.int",
     "acquisition_endpoint": "https://www.icao.int/Newsroom/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["transport"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # COMPETITION AUTHORITIES — ADDITIONAL (4)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-doj-atr", "institution_id": "DOJATR", "institution_name": "DOJ Antitrust Division (US)",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "competition_authority",
     "domain": "competition_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "justice.gov", "canonical_url": "https://www.justice.gov/atr",
     "acquisition_endpoint": "https://www.justice.gov/atr/rss.xml",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["competition"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-dgcomp-eu", "institution_id": "DGCOMP", "institution_name": "DG Competition (EU)",
     "country": "EU", "jurisdiction": "EU", "region": "EU", "source_class": "competition_authority",
     "domain": "competition_regulation", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "ec.europa.eu", "canonical_url": "https://competition-policy.ec.europa.eu",
     "acquisition_endpoint": "https://competition-policy.ec.europa.eu/news_en/rss.xml",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["competition"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-bundeskartellamt", "institution_id": "BKARTA", "institution_name": "Bundeskartellamt (Germany)",
     "country": "DE", "jurisdiction": "DE", "region": "EU", "source_class": "competition_authority",
     "domain": "competition_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "bundeskartellamt.de", "canonical_url": "https://www.bundeskartellamt.de",
     "acquisition_endpoint": "https://www.bundeskartellamt.de/EN/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["competition"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-adc-france", "institution_id": "ADC", "institution_name": "Autorité de la concurrence (France)",
     "country": "FR", "jurisdiction": "FR", "region": "EU", "source_class": "competition_authority",
     "domain": "competition_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "autoritedelaconcurrence.fr", "canonical_url": "https://www.autoritedelaconcurrence.fr",
     "acquisition_endpoint": "https://www.autoritedelaconcurrence.fr/en",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["competition"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # CORPORATE REGISTRARS / INSOLVENCY (4)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-companieshouse-uk", "institution_id": "CHUK", "institution_name": "Companies House (UK)",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "corporate_registrar",
     "domain": "corporate_registry", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "gov.uk", "canonical_url": "https://www.gov.uk/government/organisations/companies-house",
     "acquisition_endpoint": "https://www.gov.uk/government/organisations/companies-house.atom",
     "endpoint_type": "ATOM", "acquisition_method": "ATOM", "language": "en",
     "coverage_topics": ["corporate_regulation"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-sec-edgar", "institution_id": "EDGAR", "institution_name": "SEC EDGAR Filings",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "corporate_registrar",
     "domain": "corporate_registry", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "sec.gov", "canonical_url": "https://www.sec.gov/edgar",
     "acquisition_endpoint": "https://www.sec.gov/cgi-bin/browse-edgar",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["corporate_regulation", "securities"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-insolvency-uk", "institution_id": "INSUK", "institution_name": "Insolvency Service (UK)",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "insolvency_authority",
     "domain": "insolvency", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "gov.uk", "canonical_url": "https://www.gov.uk/government/organisations/insolvency-service",
     "acquisition_endpoint": "https://www.gov.uk/government/organisations/insolvency-service.atom",
     "endpoint_type": "ATOM", "acquisition_method": "ATOM", "language": "en",
     "coverage_topics": ["corporate_regulation"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-ustcc-us", "institution_id": "USTCC", "institution_name": "US Trustee Program",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "insolvency_authority",
     "domain": "insolvency", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "justice.gov", "canonical_url": "https://www.justice.gov/ust",
     "acquisition_endpoint": "https://www.justice.gov/ust",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["corporate_regulation"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # ENVIRONMENTAL / CARBON MARKETS (4)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-epa-us", "institution_id": "EPA", "institution_name": "Environmental Protection Agency (US)",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "environmental_carbon_authority",
     "domain": "environmental_regulation", "authority_level": "STATUTORY_REGULATOR",
     "official_domain": "epa.gov", "canonical_url": "https://www.epa.gov",
     "acquisition_endpoint": "https://www.epa.gov/newsreleases/search/rss",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["energy", "renewables"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-eea-eu", "institution_id": "EEA", "institution_name": "European Environment Agency",
     "country": "EU", "jurisdiction": "EU", "region": "EU", "source_class": "environmental_carbon_authority",
     "domain": "environmental_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "eea.europa.eu", "canonical_url": "https://www.eea.europa.eu",
     "acquisition_endpoint": "https://www.eea.europa.eu/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["energy", "renewables"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-ec-cm-eu", "institution_id": "ECCM", "institution_name": "EU Climate Action",
     "country": "EU", "jurisdiction": "EU", "region": "EU", "source_class": "environmental_carbon_authority",
     "domain": "carbon_markets", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "ec.europa.eu", "canonical_url": "https://climate.ec.europa.eu",
     "acquisition_endpoint": "https://climate.ec.europa.eu/news_en",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["renewables", "energy"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-defra-carbon-uk", "institution_id": "DEFCAR", "institution_name": "DEFRA Carbon (UK)",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "environmental_carbon_authority",
     "domain": "carbon_markets", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "gov.uk", "canonical_url": "https://www.gov.uk/government/organisations/department-for-environment-food-rural-affairs",
     "acquisition_endpoint": "https://www.gov.uk/government/policies?topics%5B%5D=climate-change",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["renewables"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # ADDITIONAL CENTRAL BANKS — UNDERCOVERED REGIONS (5)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-bceddo", "institution_id": "BCC", "institution_name": "Banque Centrale des États de l'Afrique de l'Ouest (BCEAO)",
     "country": "SN", "jurisdiction": "WAEMU", "region": "SUB_SAHARAN_AFRICA", "source_class": "central_bank",
     "domain": "monetary_policy", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "bceao.int", "canonical_url": "https://www.bceao.int",
     "acquisition_endpoint": "https://www.bceao.int/en",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["monetary_policy"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-beac", "institution_id": "BEAC", "institution_name": "Banque des États de l'Afrique Centrale (BEAC)",
     "country": "CM", "jurisdiction": "CEMAC", "region": "SUB_SAHARAN_AFRICA", "source_class": "central_bank",
     "domain": "monetary_policy", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "beac.int", "canonical_url": "https://www.beac.int",
     "acquisition_endpoint": "https://www.beac.int",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["monetary_policy"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-bcrd", "institution_id": "BCRD", "institution_name": "Central Bank of Dominican Republic",
     "country": "DO", "jurisdiction": "DO", "region": "LATAM", "source_class": "central_bank",
     "domain": "monetary_policy", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "bancentral.gov.do", "canonical_url": "https://www.bancentral.gov.do",
     "acquisition_endpoint": "https://www.bancentral.gov.do",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "es",
     "coverage_topics": ["monetary_policy"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-bcb-angola", "institution_id": "BCA", "institution_name": "Banco Central de Angola",
     "country": "AO", "jurisdiction": "AO", "region": "SUB_SAHARAN_AFRICA", "source_class": "central_bank",
     "domain": "monetary_policy", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "bna.ao", "canonical_url": "https://www.bna.ao",
     "acquisition_endpoint": "https://www.bna.ao",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "pt",
     "coverage_topics": ["monetary_policy"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-cbj-jordan", "institution_id": "CBJ", "institution_name": "Central Bank of Jordan",
     "country": "JO", "jurisdiction": "JO", "region": "MIDDLE_EAST", "source_class": "central_bank",
     "domain": "monetary_policy", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "cbj.gov.jo", "canonical_url": "https://www.cbj.gov.jo",
     "acquisition_endpoint": "https://www.cbj.gov.jo",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["monetary_policy"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # STATISTICAL AGENCIES — ADDITIONAL (5)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-stats-pl", "institution_id": "STATPL", "institution_name": "Statistics Poland",
     "country": "PL", "jurisdiction": "PL", "region": "EASTERN_EUROPE", "source_class": "statistical_agency",
     "domain": "economic_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "stat.gov.pl", "canonical_url": "https://stat.gov.pl",
     "acquisition_endpoint": "https://stat.gov.pl/en/news/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["gdp", "inflation", "employment"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-stat-nz", "institution_id": "STATSNZ", "institution_name": "Stats NZ",
     "country": "NZ", "jurisdiction": "NZ", "region": "NZ", "source_class": "statistical_agency",
     "domain": "economic_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "stats.govt.nz", "canonical_url": "https://www.stats.govt.nz",
     "acquisition_endpoint": "https://www.stats.govt.nz",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["gdp", "inflation", "employment"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-cso-ireland", "institution_id": "CSO", "institution_name": "Central Statistics Office (Ireland)",
     "country": "IE", "jurisdiction": "IE", "region": "EU", "source_class": "statistical_agency",
     "domain": "economic_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "cso.ie", "canonical_url": "https://www.cso.ie",
     "acquisition_endpoint": "https://www.cso.ie",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["gdp", "inflation", "employment"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-stat-austria", "institution_id": "STATAT", "institution_name": "Statistics Austria",
     "country": "AT", "jurisdiction": "AT", "region": "EU", "source_class": "statistical_agency",
     "domain": "economic_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "statistik.at", "canonical_url": "https://www.statistik.at",
     "acquisition_endpoint": "https://www.statistik.at",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["gdp", "inflation", "employment"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-stat-greece", "institution_id": "STATGR", "institution_name": "Hellenic Statistical Authority",
     "country": "GR", "jurisdiction": "GR", "region": "EU", "source_class": "statistical_agency",
     "domain": "economic_statistics", "authority_level": "OFFICIAL_STATISTICAL",
     "official_domain": "statistics.gr", "canonical_url": "https://www.statistics.gr",
     "acquisition_endpoint": "https://www.statistics.gr/en/home/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["gdp", "inflation", "employment"],
     "frequency": "daily", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # GOVERNMENT FINANCE / PUBLIC DEBT (3)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-dmo-uk", "institution_id": "DMOUK", "institution_name": "UK Debt Management Office",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "finance_ministry",
     "domain": "public_debt", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "dmo.gov.uk", "canonical_url": "https://www.dmo.gov.uk",
     "acquisition_endpoint": "https://www.dmo.gov.uk/news/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["public_debt", "government_finance"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-treasurydirect-us", "institution_id": "TDUS", "institution_name": "TreasuryDirect (US)",
     "country": "US", "jurisdiction": "US", "region": "US", "source_class": "finance_ministry",
     "domain": "public_debt", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "treasurydirect.gov", "canonical_url": "https://www.treasurydirect.gov",
     "acquisition_endpoint": "https://www.treasurydirect.gov",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["public_debt", "government_finance"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-igcp-portugal", "institution_id": "IGCP", "institution_name": "IGCP (Portugal Debt)",
     "country": "PT", "jurisdiction": "PT", "region": "EU", "source_class": "finance_ministry",
     "domain": "public_debt", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "igcp.pt", "canonical_url": "https://www.igcp.pt",
     "acquisition_endpoint": "https://www.igcp.pt",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["public_debt"],
     "frequency": "weekly", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # COMMODITY AUTHORITIES (3)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-lbma", "institution_id": "LBMA", "institution_name": "London Bullion Market Association",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "commodity_regulator",
     "domain": "commodity_market", "authority_level": "OFFICIAL_MARKET_OPERATOR",
     "official_domain": "lbma.org.uk", "canonical_url": "https://www.lbma.org.uk",
     "acquisition_endpoint": "https://www.lbma.org.uk/news",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["commodities"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-kcp-india", "institution_id": "KCP", "institution_name": "Coffee Board of India (Commodity)",
     "country": "IN", "jurisdiction": "IN", "region": "IN", "source_class": "commodity_regulator",
     "domain": "commodity_market", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "indiacoffee.org", "canonical_url": "https://www.indiacoffee.org",
     "acquisition_endpoint": "https://www.indiacoffee.org",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["commodities", "agriculture"],
     "frequency": "monthly", "discovery_wave": "C"},

    {"source_id": "src-lme-uk", "institution_id": "LME", "institution_name": "London Metal Exchange",
     "country": "UK", "jurisdiction": "UK", "region": "UK", "source_class": "commodity_regulator",
     "domain": "commodity_market", "authority_level": "OFFICIAL_MARKET_OPERATOR",
     "official_domain": "lme.com", "canonical_url": "https://www.lme.com",
     "acquisition_endpoint": "https://www.lme.com/News",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["commodities", "mining"],
     "frequency": "daily", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # INTERNATIONAL DEVELOPMENT (3)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-un-ecosoc", "institution_id": "ECOSOC", "institution_name": "UN Economic and Social Council",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "economic_policy", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "un.org", "canonical_url": "https://www.un.org/ecosoc",
     "acquisition_endpoint": "https://www.un.org/ecosoc/en/news",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["government_finance", "external_sector"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-unctad", "institution_id": "UNCTAD", "institution_name": "UNCTAD",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "trade_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "unctad.org", "canonical_url": "https://unctad.org",
     "acquisition_endpoint": "https://unctad.org/rss",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["trade", "external_sector"],
     "frequency": "daily", "discovery_wave": "C"},

    {"source_id": "src-ilo", "institution_id": "ILO", "institution_name": "International Labour Organization",
     "country": "INTL", "jurisdiction": "INTL", "region": "GLOBAL", "source_class": "international_economic_institution",
     "domain": "labor_statistics", "authority_level": "OFFICIAL_INTERNATIONAL",
     "official_domain": "ilo.org", "canonical_url": "https://www.ilo.org",
     "acquisition_endpoint": "https://www.ilo.org/news/rss",
     "endpoint_type": "RSS", "acquisition_method": "RSS", "language": "en",
     "coverage_topics": ["employment"],
     "frequency": "daily", "discovery_wave": "C"},

    # ════════════════════════════════════════════════════════
    # SOVEREIGN WEALTH FUNDS — ADDITIONAL (2)
    # ════════════════════════════════════════════════════════
    {"source_id": "src-gic-singapore", "institution_id": "GIC", "institution_name": "GIC (Singapore Sovereign Wealth)",
     "country": "SG", "jurisdiction": "SG", "region": "SOUTHEAST_ASIA", "source_class": "sovereign_wealth_institution",
     "domain": "sovereign_wealth", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "gic.com.sg", "canonical_url": "https://www.gic.com.sg",
     "acquisition_endpoint": "https://www.gic.com.sg/news/",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["capital_markets"],
     "frequency": "weekly", "discovery_wave": "C"},

    {"source_id": "src-adia-uae", "institution_id": "ADIA", "institution_name": "Abu Dhabi Investment Authority",
     "country": "AE", "jurisdiction": "AE", "region": "MIDDLE_EAST", "source_class": "sovereign_wealth_institution",
     "domain": "sovereign_wealth", "authority_level": "PRIMARY_OFFICIAL",
     "official_domain": "adia.ae", "canonical_url": "https://www.adia.ae",
     "acquisition_endpoint": "https://www.adia.ae",
     "endpoint_type": "HTML", "acquisition_method": "HTML", "language": "en",
     "coverage_topics": ["capital_markets"],
     "frequency": "monthly", "discovery_wave": "C"},
]


def get_wave_c_catalog():
    return WAVE_C_CATALOG


def wave_c_stats():
    from collections import Counter
    by_country = Counter(s["country"] for s in WAVE_C_CATALOG)
    by_region = Counter(s["region"] for s in WAVE_C_CATALOG)
    by_class = Counter(s["source_class"] for s in WAVE_C_CATALOG)
    by_method = Counter(s["acquisition_method"] for s in WAVE_C_CATALOG)
    return {
        "total": len(WAVE_C_CATALOG),
        "by_country": dict(by_country),
        "by_region": dict(by_region),
        "by_class": dict(by_class),
        "by_method": dict(by_method),
    }


if __name__ == "__main__":
    stats = wave_c_stats()
    print(f"Wave C catalog: {stats['total']} sources")
    print(f"\nBy region:")
    for k, v in sorted(stats["by_region"].items(), key=lambda x: -x[1]):
        print(f"  {k:<20} {v:>3}")
    print(f"\nBy class:")
    for k, v in sorted(stats["by_class"].items(), key=lambda x: -x[1]):
        print(f"  {k:<30} {v:>3}")
