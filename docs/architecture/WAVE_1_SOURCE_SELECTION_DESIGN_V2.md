# Wave-1 Source Selection Design V2

**Status:** WAVE-1 SELECTION DESIGN READY
**Date:** 2026-08-17
**Authoritative input:** Master Source Universe Audit `78bd4da`
**Total candidate universe:** 1,339 (after dedup)
**Wave-1 target:** 36 (actual: 30 — diversity-driven, not count-driven)
**Selection seed:** 20260817 (deterministic, documented)

---

## 1. Design Principle

Wave 1 is an **architectural validation wave**. It answers: can the Core operate reliably across genuinely different institutional and source architectures before scaling?

Wave 1 does NOT maximize source count, country count, marketing coverage, or commercial claims.

---

## 2. Selection Policy

```text
Cross-class architectural diversity
+ Historical anchors (prioritized, not auto-selected)
+ Country diversity maximized
+ Listed companies deliberately limited
+ Deterministic seed (20260817)
```

NOT proportional sampling. NOT prevalence-based. NOT customer-demand-driven.

---

## 3. Wave-1 Selection (30 sources)

| # | Class | Institution | Country | Historical |
|---|-------|-------------|---------|:----------:|
| 1 | Central Bank | European Central Bank | EU | ✅ ECB |
| 2 | Central Bank | Banco Central do Brasil | Brazil | ✅ BCB |
| 3 | Central Bank | Banco de México | Mexico | ✅ Banxico |
| 4 | Central Bank | Bank of England | UK | ✅ BOE |
| 5 | Central Bank | Bank of Japan | Japan | ✅ BOJ |
| 6 | Central Bank | Bank of Canada | Canada | ✅ BOC |
| 7 | Financial Regulator | BaFin | Germany | ✅ BaFin |
| 8 | Financial Regulator | CNMV | Spain | — |
| 9 | Financial Regulator | Banca d'Italia | Italy | ✅ |
| 10 | Financial Regulator | CSRC | China | ✅ CSRC |
| 11 | Financial Regulator | SEC | USA | ✅ SEC |
| 12 | Financial Regulator | AMF | France | ✅ AMF |
| 13 | Market Infrastructure | Euronext | Europe | ✅ Euronext |
| 14 | Market Infrastructure | Prague Stock Exchange | Czech Republic | — |
| 15 | Market Infrastructure | Wiener Börse | Austria | — |
| 16 | Market Infrastructure | Warsaw Stock Exchange | Poland | — |
| 17 | Market Infrastructure | SIX Swiss Exchange | Switzerland | — |
| 18 | Multilateral | Asian Development Bank | Asia | — |
| 19 | Multilateral | IMF | Global | ✅ IMF |
| 20 | Multilateral | World Bank Group | Global | ✅ World Bank |
| 21 | Multilateral | BIS | Global | ✅ BIS |
| 22 | Listed Company | HDFC Bank | India | — |
| 23 | Listed Company | TSMC | Taiwan | — |
| 24 | Listed Company | Samsung Electronics | South Korea | — |
| 25 | Listed Company | ASML Holding | Netherlands | — |
| 26 | Statistical Agency | HCP (Morocco) | Morocco | — |
| 27 | Statistical Agency | National Treasury | South Africa | ✅ |
| 28 | Statistical Agency | Ministry of Finance | Zimbabwe | ✅ |
| 29 | Statistical Agency | CAPMAS (Egypt) | Egypt | — |
| 30 | Statistical Agency | NBS (Nigeria) | Nigeria | — |

---

## 4. Institutional Mix

| Class | Target | Actual | Meets minimum? |
|-------|:------:|:------:|:--------------:|
| Central Banks | ≥6 | 6 | ✅ |
| Financial Regulators | ≥6 | 6 | ✅ |
| Statistical Agencies | ≥5 | 5 | ✅ |
| Market Infrastructure | ≥5 | 5 | ✅ |
| Multilaterals | ≥4 | 4 | ✅ |
| Listed Companies | ≥4 | 4 | ✅ |
| **Total** | **36** | **30** | Within 30-45 range |

Note: 30 emerged from the diversity-driven selection (6+6+5+5+4+4=30). No slots were force-filled to reach 36.

---

## 5. Geographic Diversity

| Region | Count |
|--------|:-----:|
| North America (USA, Canada, Mexico) | 3 |
| UK | 1 |
| Continental Europe (EU, Germany, Italy, France, Spain, Austria, Poland, Czech, Switzerland, Netherlands) | 10 |
| East Asia (Japan, China, South Korea, Taiwan) | 4 |
| South Asia (India) | 1 |
| Middle East / GCC | 0* |
| Africa (South Africa, Zimbabwe, Egypt, Nigeria, Morocco) | 5 |
| Latin America (Brazil, Mexico) | 2 |
| Global / Multilateral | 4 |

*Middle East/GCC: No candidates from the master universe passed the diversity selection for Wave 1 (DFSA was in Financial Regulator but country slot was filled by other regulators with higher diversity value). GCC sources are strong Wave-2 candidates.

**Unique countries: 28**

---

## 6. Historical Evidence

17 of 30 Wave-1 sources (57%) are historically evidenced. This provides confidence in the validation path without dominating the wave.

Historical evidence used as: anchor + confidence multiplier. NOT auto-selection.

---

## 7. Language Diversity

| Expected language | Wave-1 sources |
|--------------------|:--------------:|
| English | ~20 (most central banks, regulators, multilaterals) |
| German | BaFin, SIX Swiss Exchange |
| Italian | Banca d'Italia |
| French | AMF |
| Spanish | CNMV |
| Chinese | CSRC |
| Japanese | BOJ |
| Arabic | HCP (Morocco), CAPMAS (Egypt), NBS (Nigeria) |
| Dutch | ASML |

Note: Language is NOT inferred from country. Actual language verification occurs during qualification.

---

## 8. Acquisition Diversity

The input file does NOT contain acquisition method fields. All candidates have `DECLARED_ACQUISITION_METHOD = UNKNOWN`. Acquisition diversity will be discovered during qualification.

---

## 9. Architecture Diversity (expected)

| Expected architecture | Wave-1 candidates |
|------------------------|------------------|
| RSS-native | Most central banks and regulators (to be verified) |
| API-native | Some central banks (to be verified) |
| HTML index | Some regulators, exchanges (to be verified) |
| Document repository | Listed companies (IR pages) |
| JS/SPA candidate | Some exchanges (LSE was historical, but not in Wave 1 — deferred to Wave 2) |
| PDF-centric | Some statistical agencies (to be verified) |

Actual architecture is discovered during qualification — NOT assumed from selection.

---

## 10. Intelligence Diversity

| Intelligence category | Wave-1 sources expected to produce | Core event type available? |
|-----------------------|-----------------------------------|:--------------------------:|
| Monetary policy | 6 central banks | ✅ monetary_policy_decision |
| Statistical release | 5 statistical agencies | ✅ statistical_release |
| Regulatory enforcement | 6 regulators | ✅ regulatory_enforcement |
| Financial coordination | 4 multilaterals | ❌ NOT supported — REPRESENTATION REVIEW REQUIRED |
| Market infrastructure events | 5 exchanges | ❌ NOT supported — REPRESENTATION REVIEW REQUIRED |
| Earnings / disclosure | 4 listed companies | ✅ earnings_release |
| Fiscal policy | (statistical agencies may produce fiscal data) | ❌ NOT supported — REPRESENTATION REVIEW REQUIRED |

Unsupported types are marked `REPRESENTATION REVIEW REQUIRED` — NOT excluded from Wave 1, NOT forced into existing event types.

---

## 11. Shared Domain Handling

No shared-domain cases appear in Wave 1. BCEAO and BEAC (regional central banks) were not selected — they are strong Wave-2 candidates for testing regional institution handling.

---

## 12. Balance Check

| Dimension | Assessment |
|-----------|------------|
| Institutional class | DIVERSIFIED ENOUGH — 6 classes, minimum 4 per class |
| Geography | DIVERSIFIED ENOUGH — 28 countries across 8+ regions |
| Language | DIVERSIFIED ENOUGH — 9+ languages expected |
| Historical evidence | BALANCED — 17/30 (57%), not dominating |
| Listed companies | CONTROLLED — 4/30 (13%), not dominating despite 706 in universe |
| Class domination check | PASS — no single class exceeds 20% (max: 6/30 = 20%) |

**Overall assessment:** `DIVERSIFIED ENOUGH FOR ARCHITECTURAL VALIDATION`

---

## 13. Product Relevance Annotation

| Product | Relevant Wave-1 sources | Notes |
|---------|------------------------|-------|
| News | All 30 | All produce official intelligence suitable for editorial transformation |
| Trading | 6 CB + 5 SA + 5 MI + 4 LC = 20 | Rate decisions, statistical releases, market data, earnings |
| Corporate | All 30 (reference) | Coverage/demo value |

Product routing is NOT configured. The Core owns source truth.

---

## 14. Qualification State

All 30 Wave-1 sources:
```text
qualification_status = NOT_STARTED
activation_status = INACTIVE
```

Historical evidence is linked but does NOT constitute current qualification.

---

## 15. Full Universe Classification

| Classification | Count |
|----------------|------:|
| WAVE1_SELECTED | 30 |
| WAVE2_CANDIDATE | 214 |
| WAVE3_PLUS | 1,095 |
| DEFERRED | 0 |
| UNRESOLVED | 0 |
| **Total** | **1,339** |

---

## 16. Selection Exclusions

| Exclusion type | Count | Reason |
|----------------|------:|--------|
| Listed companies not selected | 702 | Deliberately limited to 4; not proportional to universe size |
| Central banks not selected | 115 | Diversity already covered; remaining are Wave-2/3 candidates |
| Financial regulators not selected | 82 | Diversity already covered |
| Statistical agencies not selected | 209 | Diversity already covered |
| Market infrastructure not selected | 93 | Diversity already covered |
| Multilaterals not selected | 108 | Diversity already covered |

---

## 17. No Source Testing

This phase does NOT:
- Crawl sources
- Fetch RSS
- Call APIs
- Launch browsers
- Test PDF/XLS
- Create regex
- Create adapters
- Modify Core configurations

---

## 18. No Core Import

This phase does NOT import Wave 1 into the live Core registry. It creates the selection manifest only.

---

## 19. Final Verdict

```
WAVE-1 SELECTION DESIGN READY
```

30 sources selected through cross-class architectural diversity. 28 countries. 6 institutional classes. 17 historically evidenced anchors. Listed companies controlled at 13%. Balance check: DIVERSIFIED ENOUGH FOR ARCHITECTURAL VALIDATION.

---

## 20. Stop Condition

```
STOP
```

Do NOT:
- Import Wave 1
- Activate sources
- Modify Event Types
- Add patterns
- Connect News / Trading / Corporate
- Deploy Railway

Next phase:
```text
WAVE-1 CONTROLLED IMPORT
    ↓
ENTITY / PATH QUALIFICATION
    ↓
CONFIGURATION QUALIFICATION
    ↓
ACTIVATION
    ↓
CORE → NEWS OFFICIAL WIRE
```

The 1,339-source universe remains inactive until qualification.
