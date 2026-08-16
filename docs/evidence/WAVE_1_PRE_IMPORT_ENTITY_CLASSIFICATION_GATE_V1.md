# Wave-1 Pre-Import Entity Classification Gate V1

**Status:** WAVE-1 PRE-IMPORT GATE PASSED
**Date:** 2026-08-17
**Wave-1 selection:** `350bbbb`
**Scope:** 30 Wave-1 selected sources only (NOT the 1,339-source universe)

---

## 1. Objective

Validate and correct the 30 Wave-1 selections before any source is imported into ROUAA Intelligence Core.

---

## 2. Entity Verification Results

All 30 entities verified. Each domain corresponds to the actual institution (not a platform/distributor).

**BMF regression: PASS** — No platform/distributor has been mistaken for an institution. The `bmf.de` lesson (hostname ≠ institution) is preserved. All 30 domains were verified as belonging to the named institution.

---

## 3. Required Table

| # | Institution | Current Class | Verified Class | Entity Status | Content Path | Language | Historical Evidence | Result |
|---|-------------|---------------|----------------|---------------|--------------|----------|-------------------|--------|
| 1 | European Central Bank | Central Bank | Central Bank | IDENTITY_CONFIRMED | ecb.europa.eu (TBD) | English (EU) | ✅ ECB | SELECTED — CONFIRMED |
| 2 | Bank of England | Central Bank | Central Bank | IDENTITY_CONFIRMED | bankofengland.co.uk (TBD) | English | ✅ BOE | SELECTED — CONFIRMED |
| 3 | Bank of Japan | Central Bank | Central Bank | IDENTITY_CONFIRMED | boj.or.jp (TBD) | Japanese (+EN) | ✅ BOJ | SELECTED — CONFIRMED |
| 4 | Bank of Canada | Central Bank | Central Bank | IDENTITY_CONFIRMED | bankofcanada.ca (TBD) | English (+FR) | ✅ BOC | SELECTED — CONFIRMED |
| 5 | Banco Central do Brasil | Central Bank | Central Bank | IDENTITY_CONFIRMED | bcb.gov.br (TBD) | Portuguese (+EN) | ✅ BCB | SELECTED — CONFIRMED |
| 6 | Banco de México | Central Bank | Central Bank | IDENTITY_CONFIRMED | banxico.org.mx (TBD) | Spanish (+EN) | ✅ Banxico | SELECTED — CONFIRMED |
| 7 | SEC | Financial Regulator | Financial Regulator | IDENTITY_CONFIRMED | sec.gov (TBD) | English | ✅ SEC | SELECTED — CONFIRMED |
| 8 | AMF (France) | Financial Regulator | Financial Regulator | IDENTITY_CONFIRMED | amf-france.org (TBD) | French (+EN) | ✅ AMF | SELECTED — CONFIRMED |
| 9 | BaFin | Financial Regulator | Financial Regulator | IDENTITY_CONFIRMED | bafin.de (TBD) | German (+EN) | ✅ BaFin | SELECTED — CONFIRMED |
| 10 | Banca d'Italia | Financial Regulator | **Central Bank** | IDENTITY_CONFIRMED | bancaditalia.it (TBD) | Italian (+EN) | ✅ Banca d'Italia | **SELECTED — CORRECTED** |
| 11 | CNMV (Spain) | Financial Regulator | Financial Regulator | IDENTITY_CONFIRMED | cnmv.es (TBD) | Spanish (+EN) | NONE | SELECTED — CONFIRMED |
| 12 | CSRC (China) | Financial Regulator | Financial Regulator | IDENTITY_CONFIRMED | csrc.gov.cn (TBD) | Chinese (+EN) | ✅ CSRC | SELECTED — CONFIRMED |
| 13 | Euronext | Market Infrastructure | Market Infrastructure | IDENTITY_CONFIRMED | euronext.com (TBD) | Multilingual | ✅ Euronext | SELECTED — CONFIRMED |
| 14 | SIX Swiss Exchange | Market Infrastructure | Market Infrastructure | IDENTITY_CONFIRMED | six-group.com (TBD) | German/FR/IT/EN | NONE | SELECTED — CONFIRMED |
| 15 | Wiener Börse | Market Infrastructure | Market Infrastructure | IDENTITY_CONFIRMED | wienerborse.at (TBD) | German (+EN) | NONE | SELECTED — CONFIRMED |
| 16 | Warsaw Stock Exchange | Market Infrastructure | Market Infrastructure | IDENTITY_CONFIRMED | gpw.pl (TBD) | Polish (+EN) | NONE | SELECTED — CONFIRMED |
| 17 | Prague Stock Exchange | Market Infrastructure | Market Infrastructure | IDENTITY_CONFIRMED | pse.cz (TBD) | Czech (+EN) | NONE | SELECTED — CONFIRMED |
| 18 | NBS (Nigeria) | Statistical Agency | Statistical Agency | IDENTITY_CONFIRMED | nigerianstat.gov.ng (TBD) | English | NONE | SELECTED — CONFIRMED |
| 19 | CAPMAS (Egypt) | Statistical Agency | Statistical Agency | IDENTITY_CONFIRMED | capmas.gov.eg (TBD) | Arabic (+EN) | NONE | SELECTED — CONFIRMED |
| 20 | HCP (Morocco) | Statistical Agency | Statistical Agency | IDENTITY_CONFIRMED | hcp.ma (TBD) | Arabic/FR (+EN) | NONE | SELECTED — CONFIRMED |
| 21 | National Treasury (SA) | Statistical Agency | **Ministry / Treasury** | IDENTITY_CONFIRMED | treasury.gov.za (TBD) | English (+Afrikaans) | ~~US Treasury~~ → NONE | **SELECTED — CORRECTED** |
| 22 | Ministry of Finance (Zimbabwe) | Statistical Agency | **Ministry / Treasury** | IDENTITY_CONFIRMED | zimtreasury.gov.zw (TBD) | English | ~~US Treasury~~ → NONE | **SELECTED — CORRECTED** |
| 23 | IMF | Multilateral | Multilateral | IDENTITY_CONFIRMED | imf.org (TBD) | Multilingual | ✅ IMF | SELECTED — CONFIRMED |
| 24 | World Bank Group | Multilateral | Multilateral | IDENTITY_CONFIRMED | worldbank.org (TBD) | Multilingual | ✅ World Bank | SELECTED — CONFIRMED |
| 25 | BIS | Multilateral | Multilateral | IDENTITY_CONFIRMED | bis.org (TBD) | English | ✅ BIS | SELECTED — CONFIRMED |
| 26 | Asian Development Bank | Multilateral | Multilateral | IDENTITY_CONFIRMED | adb.org (TBD) | English | NONE | SELECTED — CONFIRMED |
| 27 | ASML Holding | Listed Company | Listed Company | IDENTITY_CONFIRMED | asml.com (TBD) | Dutch (+EN) | NONE | SELECTED — CONFIRMED |
| 28 | Samsung Electronics | Listed Company | Listed Company | IDENTITY_CONFIRMED | samsung.com (TBD) | Korean (+EN) | NONE | SELECTED — CONFIRMED |
| 29 | TSMC | Listed Company | Listed Company | IDENTITY_CONFIRMED | investor.tsmc.com (IR page) | Chinese (+EN) | NONE | SELECTED — CONFIRMED |
| 30 | HDFC Bank | Listed Company | Listed Company | IDENTITY_CONFIRMED | hdfcbank.com (TBD) | English (+Hindi) | NONE | SELECTED — CONFIRMED |

---

## 4. Corrections Applied

### Correction 1: Banca d'Italia

| Field | Old | New |
|-------|-----|-----|
| Institutional class | Financial Regulator (B2) | **Central Bank (B1)** |
| Historical evidence | Banca d'Italia | Banca d'Italia (retained — accurate) |

**Rationale:** Banca d'Italia (bancaditalia.it) is the central bank of Italy. It has supervisory/regulatory roles but its primary institutional class is Central Bank (B1). The dual role (central bank + banking supervisor) is common in European central banks (ECB, Bundesbank, Banque de France all have similar dual roles). The canonical class is determined by the **primary institutional function**, which is central banking.

No hybrid class was invented. The existing taxonomy (B1 Central Bank) is used.

### Correction 2: National Treasury (South Africa)

| Field | Old | New |
|-------|-----|-----|
| Institutional class | Statistical Agency (B3) | **Ministry / Treasury (B4)** |
| Historical evidence | ~~US Treasury~~ (false keyword match) | **NONE** (corrected) |

**Rationale:** National Treasury of South Africa (treasury.gov.za) is the government ministry responsible for fiscal policy and public finance. It is NOT a statistical agency. The "Statistical Agency" classification was inherited from the batch header in the source file, which incorrectly grouped treasury/ministry sources with statistical agencies.

**Historical evidence correction:** The historical_sources mapping matched "treasury" in `treasury.gov.za` to "US Treasury". This is a **false keyword match** — the South African National Treasury is a different institution. Historical evidence corrected to NONE.

### Correction 3: Ministry of Finance (Zimbabwe)

| Field | Old | New |
|-------|-----|-----|
| Institutional class | Statistical Agency (B3) | **Ministry / Treasury (B4)** |
| Historical evidence | ~~US Treasury~~ (false keyword match) | **NONE** (corrected) |

**Rationale:** Ministry of Finance Zimbabwe (zimtreasury.gov.zw) is the government treasury ministry. It is NOT a statistical agency. Same false keyword match as Correction 2 — "treasury" matched "US Treasury" in the historical_sources mapping.

---

## 5. False Historical Evidence Corrections

Two records had false historical evidence from a keyword-matching bug in the audit script:

| Record | Old evidence | Corrected evidence | Reason |
|--------|-------------|-------------------|--------|
| National Treasury (South Africa) | US Treasury | NONE | False keyword match on "treasury" |
| Ministry of Finance (Zimbabwe) | US Treasury | NONE | False keyword match on "treasury" |

These are NOT the US Treasury. They are national treasury ministries of their respective countries. The historical_sources mapping has been corrected in the manifest.

---

## 6. BMF Regression Check

**PASS** — All 30 entities verified. No platform/distributor has been mistaken for the institution.

Special notes:
- **bafin.de** is BaFin's correct official domain. This is NOT the `bmf.de` confusion from the Core Architecture (where `bmf.de` was initially assumed to be the German Ministry of Finance but was actually Bürener Maschinenfabrik GmbH). `bafin.de` and `bmf.de` are different domains for different institutions.
- **investor.tsmc.com** is TSMC's investor relations page. The institution is TSMC; the IR page is the candidate content path, not the institutional identity.
- **six-group.com** is SIX Group's corporate domain. SIX Group operates the SIX Swiss Exchange. The institution is SIX Group (correct for Market Infrastructure).

---

## 7. Verified Class Distribution (after corrections)

| Class | Count | B-class |
|-------|:-----:|:-------:|
| Central Bank | 7 | B1 |
| Financial Regulator | 5 | B2 |
| Statistical Agency | 3 | B3 |
| Ministry / Treasury | 2 | B4 |
| Market Infrastructure | 5 | B5 |
| Multilateral | 4 | B7 |
| Listed Company | 4 | B9 |
| **Total** | **30** | |

---

## 8. Intelligence Scope Check

| Class | Likely intelligence | Core event type available? |
|-------|-------------------|:--------------------------:|
| Central Bank (7) | monetary_policy, statistical_release | ✅ Supported |
| Financial Regulator (5) | regulatory_enforcement | ✅ Supported |
| Statistical Agency (3) | statistical_release | ✅ Supported |
| Ministry / Treasury (2) | fiscal_policy | ❌ REPRESENTATION REVIEW REQUIRED |
| Market Infrastructure (5) | market_infrastructure | ❌ REPRESENTATION REVIEW REQUIRED |
| Multilateral (4) | financial_coordination | ❌ REPRESENTATION REVIEW REQUIRED |
| Listed Company (4) | earnings/disclosure | ✅ earnings_release supported |

3 intelligence types are NOT supported by the current Core Event Model. These are marked `REPRESENTATION REVIEW REQUIRED` — NOT excluded from Wave 1, NOT forced into existing event types.

---

## 9. Historical Evidence (corrected)

| Count | Status |
|-------|--------|
| 15 | Historically evidenced (accurate) |
| 15 | No historical evidence |
| 2 | False historical evidence corrected to NONE |
| **30** | **Total** |

The 2 corrections (National Treasury SA, Ministry of Finance Zimbabwe) reduced the historical count from 17 to 15.

---

## 10. Acceptance Criteria

| # | Criterion | Status |
|---|-----------|:------:|
| 1 | All 30 entities correctly attributable | ✅ PASS |
| 2 | All 30 have defensible institutional class | ✅ PASS (3 corrected) |
| 3 | No platform/distributor mistaken for institution | ✅ PASS |
| 4 | Candidate content paths identified or marked TBD | ✅ PASS (all TBD — qualification stage) |
| 5 | Historical evidence references accurate | ✅ PASS (2 false matches corrected) |
| 6 | No frozen artifacts modified | ✅ PASS |
| 7 | No source activated | ✅ PASS |

---

## 11. Manifest Updated

`docs/evidence/WAVE_1_SELECTION_MANIFEST_V2.json` updated with:
- 3 classification corrections (Banca d'Italia, National Treasury SA, Ministry of Finance Zimbabwe)
- 2 false historical evidence corrections (removed "US Treasury" from SA and Zimbabwe)
- All 30 records marked `IDENTITY_CONFIRMED`
- Pre-import gate metadata added to manifest

---

## 12. Final Verdict

```
WAVE-1 PRE-IMPORT GATE PASSED
```

27 confirmed + 3 corrected + 0 blocked = 30 sources ready for controlled import.

---

## 13. Stop Condition

```
STOP
```

Do NOT:
- Import sources
- Activate sources
- Create configurations
- Add Event Types
- Add patterns
- Connect News / Trading / Corporate
- Deploy Railway

Next phase (only after PASS):
```text
WAVE-1 CONTROLLED IMPORT
    ↓
LIVE ENTITY VERIFICATION
    ↓
CONTENT-PATH QUALIFICATION
    ↓
CONFIGURATION QUALIFICATION
    ↓
ACTIVATION
```

No activation occurs in this task.
