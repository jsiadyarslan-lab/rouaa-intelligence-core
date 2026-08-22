# ROUAA CORE — PARALLEL QA EXECUTION
# Generated: 2026-08-22T03:52:47.793149+00:00
# TRACK A: Case 2 Forensic Trace | TRACK B: Frozen Benchmark | INVARIANT AUDIT

---

## TRACK A — CASE 2 FORENSIC TRACE

**IO**: `gold-fed-2024-07-25bp`
**Defect**: fact_value=-25 contradicts evidence "voted to maintain" (0bp)
**Question**: Where did fact_value=-25 originate?

### A.1: Gold Set V2 at remote main (6fcdcade)

**YAML block found in ROUAA_GOLD_SET_V2.md** (at 6fcdcade):
```yaml
io_id: gold-fed-2024-07-25bp
category: monetary
fact_metric: policy_rate_change
fact_value: -25
unit: basis_points
evidence_excerpt: "The Federal Open Market Committee voted to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent."
canonical_url: https://www.federalreserve.gov/newsevents/pressreleases/monetary20240731a.htm
snapshot_sha256: local:snapshots/gold_set_v2/fed-20240731a.html
temporal_data:
  publication_date: 2024-07-31
  reference_period: 2024-07-31
entity: Federal Open Market Committee (explicitly in excerpt)
verification_hash: pending
human_verification:
  step_1_value_in_excerpt: PASS — "5-1/4 to 5-1/2 percent" appears, -25bp derived from maintained status (no change = 0, but the decision itself is the event)
  step_2_metric_fit: PASS — policy_rate_
```

- **fact_value**: `-25`
- **fact_metric**: `policy_rate_change`
- **evidence_excerpt**: `The Federal Open Market Committee voted to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent.`

### A.2: Check golden_corpus_frozen.json for Fed July 2024 IO

golden_corpus_frozen.json: 51 IOs

IOs matching Fed/July/maintain keywords: 2
- `io-f3750c8c05f9b04c`: headline="imp-federal-reserve Statistical Release", event_type="statistical_release"
- `io-dd7f1db542d212a3`: headline="imp-bank-of-england Statistical Release", event_type="statistical_release"

gold-fed-2024-07-25bp is NOT in golden_corpus_frozen.json

**Forensic finding**: The Gold-V2 IO `gold-fed-2024-07-25bp` was NOT produced
by the extraction pipeline. It was **manually entered** in the Gold Set V2 YAML
(at commit 6fcdcade on main). There is no extraction/normalization code path
that generated fact_value=-25.

The fact_value=-25 was stored directly in the inline YAML block of
ROUAA_GOLD_SET_V2.md. No pipeline trace exists because no pipeline produced it.

### A.3: Provenance Chain Analysis

```
Source: Federal Reserve (federalreserve.gov)
  ↓
Document: monetary20240731a.htm (July 31, 2024 FOMC statement)
  ↓
Evidence excerpt: "The Federal Open Market Committee voted to maintain
                   the target range for the federal funds rate at
                   5-1/4 to 5-1/2 percent."
  ↓
  ╔═══════════════════════════════════════════════════════╗
  ║  DIVERGENCE POINT: Manual data entry                  ║
  ║  Evidence says "maintain" (0bp change)                ║
  ║  fact_value stored as -25 (25bp cut)                  ║
  ║  NO extraction pipeline produced this value            ║
  ║  Value was manually entered in Gold Set V2 YAML       ║
  ╚═══════════════════════════════════════════════════════╝
  ↓
Fact: fact_value=-25, fact_metric=policy_rate_change
  ↓
Event: (not separately stored in Gold-V2)
  ↓
IO: gold-fed-2024-07-25bp (final_status: VALID_GOLD — INCORRECT)
  ↓
Delivery: (not delivered — Gold-V2 is reference only)
```

### A.4: Divergence Classification

| Layer | Status | Evidence |
|---|---|---|
| Source | ✓ CORRECT | federalreserve.gov is authoritative |
| Document | ✓ CORRECT | monetary20240731a.htm is the correct July 31, 2024 statement |
| Evidence excerpt | ✓ CORRECT | "voted to maintain" is verbatim from source |
| **Fact value** | **❌ WRONG** | **-25 stored instead of 0; "maintain" means 0bp** |
| Fact metric | ✓ CORRECT | policy_rate_change is the right metric |
| Event | N/A | not separately stored in Gold-V2 |
| IO identity | ⚠️ MISLEADING | io_id says "-25bp" but the decision was 0bp |

**Divergence type**: MANUAL_DATA_ENTRY_ERROR
**Exact point**: Between evidence_excerpt reading and fact_value storage
**No extraction/normalization pipeline involved** — value was hand-entered

---

## TRACK B — PHASE 6 FROZEN BENCHMARK

**Population**: golden_corpus_frozen.json (51 IOs)
**Test**: fact_value ↔ evidence_excerpt consistency for every IO

Loaded: 51 IOs

### B.1: Benchmark Summary

- Total fact/evidence pairs checked: 480
- fact_value ↔ evidence MATCH: 162
- fact_value ↔ evidence MISMATCH: 318
- No evidence text available: 0
- Consistency rate: 162/480 (33.8%)

### B.2: Fact/Evidence Mismatches (318 found)

| io_id | fact_value | fact_metric | evidence (first 100 chars) | match type |
|---|---|---|---|---|
| `io-9e2848265ad5928d` | `lower` | `rate_decision` | So MPC members need to consider what inflation and growth in the economy are likely to be in the nex | literal=False, norm=False, num=False |
| `io-e57db30de41a9d7e` | `0` | `policy_rate` | Interest on sight deposits The SNB applies interest to, or 'remunerates', sight deposits in Swiss fr | literal=False, norm=False, num=False |
| `io-e57db30de41a9d7e` | `110` | `policy_rate` | Open market operations include repo transactions, the issuance, purchase and sale of its own debt ce | literal=False, norm=False, num=False |
| `io-e57db30de41a9d7e` | `0` | `policy_rate` | The liquidity-shortage financing facility is granted in the form of a special-rate repo transaction. | literal=False, norm=False, num=False |
| `io-e57db30de41a9d7e` | `0` | `policy_rate` | Sight deposits which are held to meet minimum reserve requirements are not remunerated. Terms of Bus | literal=False, norm=False, num=False |
| `io-34acaea89e0d8ab2` | `31` | `policy_rate` | This weighed on risk sentiment in March, while in April and May markets recovered strongly. Over the | literal=False, norm=False, num=False |
| `io-3be348eb6518bd7f` | `raise` | `rate_decision` | It is the Monetary Policy Committee (MPC) that decides on Bank Rate and QE. When we need to reduce t | literal=False, norm=False, num=False |
| `io-3be348eb6518bd7f` | `lower` | `rate_decision` | That leads to less spending in the economy, which brings down the rate of inflation. When we need to | literal=False, norm=False, num=False |
| `io-3be348eb6518bd7f` | `raised` | `rate_decision` | The last time we announced an increase in the amount of QE was in November 2020. At the moment, infl | literal=False, norm=False, num=False |
| `io-3be348eb6518bd7f` | `lower` | `rate_decision` | Yields on government bonds act as a benchmark interest rate for all sorts of other financial product | literal=False, norm=False, num=False |
| `io-3be348eb6518bd7f` | `raise` | `rate_decision` | So, for example, lower government bond yields feed through to lower interest rates on household mort | literal=False, norm=False, num=False |
| `io-f252514d7487e66e` | `raise` | `rate_decision` | And none of those elements, for the moment, are giving us second-round effects indications. I heard  | literal=False, norm=False, num=False |
| `io-099e8da90a8a370d` | `cut` | `rate_decision` | Europe needs to further develop the infrastructure for making cross-border payments in euro with key | literal=False, norm=False, num=False |
| `io-be817f73577ff8e1` | `36` | `percentage_statistic` | Acceptance of card payments remained broadly stable at 88% between 2024 and 2026, while acceptance o | literal=False, norm=False, num=False |
| `io-be817f73577ff8e1` | `68` | `percentage_statistic` | Acceptance of card payments remained broadly stable at 88% between 2024 and 2026, while acceptance o | literal=False, norm=False, num=False |
| `io-be817f73577ff8e1` | `25` | `percentage_statistic` | erview of payments and financial stability Quick links Digital euro Payments news & events Market co | literal=False, norm=False, num=False |
| `io-be817f73577ff8e1` | `13` | `percentage_statistic` | l Statistical releases THE ECB BLOG - Improved data: how climate change impacts banks 18 April 2024  | literal=False, norm=False, num=False |
| `io-dcf76f5a97a74c3e` | `2` | `percentage_statistic` | Home Monetary policy Monetary policy We set monetary policy to keep inflation in the UK low and stab | literal=False, norm=False, num=False |
| `io-dcf76f5a97a74c3e` | `3.75` | `percentage_statistic` | Home Monetary policy Monetary policy We set monetary policy to keep inflation in the UK low and stab | literal=False, norm=False, num=False |
| `io-dcf76f5a97a74c3e` | `2.6` | `percentage_statistic` | Home Monetary policy Monetary policy We set monetary policy to keep inflation in the UK low and stab | literal=False, norm=False, num=False |

### B.3: Subject Attribution Check

For each IO, verify that the candidate/subject is supported by evidence (not just signal strength).

Subject attribution check: structural — frozen corpus does not store explicit subject fields.
Subject attribution validation requires the V48AB shadow evaluator (separate track).

---

## MANDATORY INVARIANT AUDIT

### Invariant 1: fact_value ↔ evidence_excerpt

For every IntelligenceObject:
- fact_value MUST be supported by evidence_excerpt/evidence_segment
- Support must be: (A) literal representation OR (B) documented deterministic versioned normalization
- NEVER: implicit inference, semantic guess, LLM reconstruction, contextual assumption

**Audit Results**:
- Total fact/evidence pairs: 480
- PASS (literal or normalized): 162
- FAIL (fact not in evidence): 318
- NO_EVIDENCE (no evidence text): 0

**FAIL details**:

- `io-9e2848265ad5928d`: fact_value="lower" — fact_value "lower" NOT found in evidence text
- `io-e57db30de41a9d7e`: fact_value="0" — fact_value "0" NOT found in evidence text
- `io-e57db30de41a9d7e`: fact_value="110" — fact_value "110" NOT found in evidence text
- `io-e57db30de41a9d7e`: fact_value="0" — fact_value "0" NOT found in evidence text
- `io-e57db30de41a9d7e`: fact_value="0" — fact_value "0" NOT found in evidence text
- `io-34acaea89e0d8ab2`: fact_value="31" — fact_value "31" NOT found in evidence text
- `io-3be348eb6518bd7f`: fact_value="raise" — fact_value "raise" NOT found in evidence text
- `io-3be348eb6518bd7f`: fact_value="lower" — fact_value "lower" NOT found in evidence text
- `io-3be348eb6518bd7f`: fact_value="raised" — fact_value "raised" NOT found in evidence text
- `io-3be348eb6518bd7f`: fact_value="lower" — fact_value "lower" NOT found in evidence text
- `io-3be348eb6518bd7f`: fact_value="raise" — fact_value "raise" NOT found in evidence text
- `io-f252514d7487e66e`: fact_value="raise" — fact_value "raise" NOT found in evidence text
- `io-099e8da90a8a370d`: fact_value="cut" — fact_value "cut" NOT found in evidence text
- `io-be817f73577ff8e1`: fact_value="36" — fact_value "36" NOT found in evidence text
- `io-be817f73577ff8e1`: fact_value="68" — fact_value "68" NOT found in evidence text
- `io-be817f73577ff8e1`: fact_value="25" — fact_value "25" NOT found in evidence text
- `io-be817f73577ff8e1`: fact_value="13" — fact_value "13" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dcf76f5a97a74c3e`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-a5963d0fb0a8b10d`: fact_value="0" — fact_value "0" NOT found in evidence text
- `io-a5963d0fb0a8b10d`: fact_value="0" — fact_value "0" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="54.9" — fact_value "54.9" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="48.3" — fact_value "48.3" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="65.2" — fact_value "65.2" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="70.0" — fact_value "70.0" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="646.1" — fact_value "646.1" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="5.8" — fact_value "5.8" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="226.8" — fact_value "226.8" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="21.27" — fact_value "21.27" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="43.37" — fact_value "43.37" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="64.64" — fact_value "64.64" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="21.87" — fact_value "21.87" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="102.1" — fact_value "102.1" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="28.8" — fact_value "28.8" NOT found in evidence text
- `io-abed2ad81fcd4f55`: fact_value="232.2" — fact_value "232.2" NOT found in evidence text
- `io-f3750c8c05f9b04c`: fact_value="3" — fact_value "3" NOT found in evidence text
- `io-42a1a68e297feffb`: fact_value="100" — fact_value "100" NOT found in evidence text
- `io-f92aa209b5d5c885`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-f92aa209b5d5c885`: fact_value="2.7" — fact_value "2.7" NOT found in evidence text
- `io-f92aa209b5d5c885`: fact_value="1.8" — fact_value "1.8" NOT found in evidence text
- `io-f92aa209b5d5c885`: fact_value="3.2" — fact_value "3.2" NOT found in evidence text
- `io-c6c8ac878a439394`: fact_value="72" — fact_value "72" NOT found in evidence text
- `io-43450fbfbd3f5f48`: fact_value="5" — fact_value "5" NOT found in evidence text
- `io-a27ee61aa6026a13`: fact_value="31" — fact_value "31" NOT found in evidence text
- `io-a27ee61aa6026a13`: fact_value="29" — fact_value "29" NOT found in evidence text
- `io-a27ee61aa6026a13`: fact_value="33" — fact_value "33" NOT found in evidence text
- `io-0f57ee23f994dd09`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-0f57ee23f994dd09`: fact_value="3" — fact_value "3" NOT found in evidence text
- `io-0f57ee23f994dd09`: fact_value="3" — fact_value "3" NOT found in evidence text
- `io-0f57ee23f994dd09`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-5374d45575bb9c06`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-5374d45575bb9c06`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-5374d45575bb9c06`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-5374d45575bb9c06`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-5374d45575bb9c06`: fact_value="4.2" — fact_value "4.2" NOT found in evidence text
- `io-5374d45575bb9c06`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-f803af6f431d9f8a`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-877cfaba4b9dc235`: fact_value="50" — fact_value "50" NOT found in evidence text
- `io-1ca8a75ee22968f7`: fact_value="disgorgement" — fact_value "disgorgement" NOT found in evidence text
- `io-1ca8a75ee22968f7`: fact_value="23" — fact_value "23" NOT found in evidence text
- `io-1ca8a75ee22968f7`: fact_value="4" — fact_value "4" NOT found in evidence text
- `io-86eb51402109b465`: fact_value="disgorgement" — fact_value "disgorgement" NOT found in evidence text
- `io-86eb51402109b465`: fact_value="injunction" — fact_value "injunction" NOT found in evidence text
- `io-86eb51402109b465`: fact_value="11" — fact_value "11" NOT found in evidence text
- `io-86eb51402109b465`: fact_value="850,000" — fact_value "850,000" NOT found in evidence text
- `io-86eb51402109b465`: fact_value="23" — fact_value "23" NOT found in evidence text
- `io-7fb679b134aeabb3`: fact_value="charged" — fact_value "charged" NOT found in evidence text
- `io-7fb679b134aeabb3`: fact_value="disgorgement" — fact_value "disgorgement" NOT found in evidence text
- `io-7fb679b134aeabb3`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-7fb679b134aeabb3`: fact_value="10" — fact_value "10" NOT found in evidence text
- `io-732c2593f8322d3e`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-732c2593f8322d3e`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-732c2593f8322d3e`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-3ba6bc20160d3cd7`: fact_value="settlement" — fact_value "settlement" NOT found in evidence text
- `io-1dad53e489db8113`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-1dad53e489db8113`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-1dad53e489db8113`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-1dad53e489db8113`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-e7f1ab14fa41db16`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-e7f1ab14fa41db16`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-478b3771245b3bd0`: fact_value="charged" — fact_value "charged" NOT found in evidence text
- `io-4d78210bf97ce3af`: fact_value="settlement" — fact_value "settlement" NOT found in evidence text
- `io-06e3082b313fcdc5`: fact_value="penalty" — fact_value "penalty" NOT found in evidence text
- `io-06e3082b313fcdc5`: fact_value="fine" — fact_value "fine" NOT found in evidence text
- `io-3d564cb820f793a1`: fact_value="settlement" — fact_value "settlement" NOT found in evidence text
- `io-03f54ef461c06001`: fact_value="20" — fact_value "20" NOT found in evidence text
- `io-03f54ef461c06001`: fact_value="5" — fact_value "5" NOT found in evidence text
- `io-03f54ef461c06001`: fact_value="5" — fact_value "5" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="4.4" — fact_value "4.4" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="77.6" — fact_value "77.6" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="314.7" — fact_value "314.7" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="388.0" — fact_value "388.0" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="7.3" — fact_value "7.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="102.1" — fact_value "102.1" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="28.8" — fact_value "28.8" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="189.3" — fact_value "189.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="198.3" — fact_value "198.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="5.6" — fact_value "5.6" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="68.5" — fact_value "68.5" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="1.3" — fact_value "1.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="320.2" — fact_value "320.2" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="6.6" — fact_value "6.6" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="35.6" — fact_value "35.6" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="206.9" — fact_value "206.9" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="1.1" — fact_value "1.1" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="107.8" — fact_value "107.8" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="5.3" — fact_value "5.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="94.5" — fact_value "94.5" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="153.6" — fact_value "153.6" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="248.1" — fact_value "248.1" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="0.3" — fact_value "0.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="4.5" — fact_value "4.5" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="6.5" — fact_value "6.5" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="0.7" — fact_value "0.7" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="14.9" — fact_value "14.9" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="19.5" — fact_value "19.5" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="3.0" — fact_value "3.0" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="7.4" — fact_value "7.4" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="14.3" — fact_value "14.3" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="0.7" — fact_value "0.7" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="0.1" — fact_value "0.1" NOT found in evidence text
- `io-0db41fde8c803040`: fact_value="4,667.7" — fact_value "4,667.7" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="48.3" — fact_value "48.3" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="65.2" — fact_value "65.2" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="70.0" — fact_value "70.0" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="646.1" — fact_value "646.1" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="65.2" — fact_value "65.2" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="58.2" — fact_value "58.2" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="7.0" — fact_value "7.0" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="68.0" — fact_value "68.0" NOT found in evidence text
- `io-8203734e329b78da`: fact_value="54.9" — fact_value "54.9" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="266.0" — fact_value "266.0" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="5.86" — fact_value "5.86" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="182.4" — fact_value "182.4" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="49.0" — fact_value "49.0" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="39.2" — fact_value "39.2" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="1,114.7" — fact_value "1,114.7" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="1,044.0" — fact_value "1,044.0" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="645.3" — fact_value "645.3" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="511.9" — fact_value "511.9" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="488.1" — fact_value "488.1" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="40.0" — fact_value "40.0" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="776.3" — fact_value "776.3" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="751.8" — fact_value "751.8" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="747.3" — fact_value "747.3" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="738.3" — fact_value "738.3" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="827.1" — fact_value "827.1" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="819.8" — fact_value "819.8" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="706.2" — fact_value "706.2" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="2.51" — fact_value "2.51" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="835.9" — fact_value "835.9" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="629.7" — fact_value "629.7" NOT found in evidence text
- `io-4b3549f2bfeabd43`: fact_value="534.0" — fact_value "534.0" NOT found in evidence text
- `io-0c647330a91d640c`: fact_value="328.0" — fact_value "328.0" NOT found in evidence text
- `io-0c647330a91d640c`: fact_value="95.5" — fact_value "95.5" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="181.6" — fact_value "181.6" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="164.9" — fact_value "164.9" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="156.1" — fact_value "156.1" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="159.9" — fact_value "159.9" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="704.2" — fact_value "704.2" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="156.1" — fact_value "156.1" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="94.3" — fact_value "94.3" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="61.8" — fact_value "61.8" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="43.8" — fact_value "43.8" NOT found in evidence text
- `io-09189d018d2081b4`: fact_value="181.6" — fact_value "181.6" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="14" — fact_value "14" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="18" — fact_value "18" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="49" — fact_value "49" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="24" — fact_value "24" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="4,609" — fact_value "4,609" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="332" — fact_value "332" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="2,172" — fact_value "2,172" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="1,253" — fact_value "1,253" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="309" — fact_value "309" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="1,094" — fact_value "1,094" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="1,815" — fact_value "1,815" NOT found in evidence text
- `io-6e897d602140277f`: fact_value="4,609" — fact_value "4,609" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="209.0" — fact_value "209.0" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="5.8" — fact_value "5.8" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="226.8" — fact_value "226.8" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="5.8" — fact_value "5.8" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="50.0" — fact_value "50.0" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="1.38" — fact_value "1.38" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="55.8" — fact_value "55.8" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="3.3" — fact_value "3.3" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="3.4" — fact_value "3.4" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="0.9" — fact_value "0.9" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="2.0" — fact_value "2.0" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="527.3" — fact_value "527.3" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="803.7" — fact_value "803.7" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="21.27" — fact_value "21.27" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="43.37" — fact_value "43.37" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="64.64" — fact_value "64.64" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="21.87" — fact_value "21.87" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="462.9" — fact_value "462.9" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="527.3" — fact_value "527.3" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="357.1" — fact_value "357.1" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="140.4" — fact_value "140.4" NOT found in evidence text
- `io-8fa184904578eae6`: fact_value="803.7" — fact_value "803.7" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="218.4" — fact_value "218.4" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="4.6" — fact_value "4.6" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="9.2" — fact_value "9.2" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="284.5" — fact_value "284.5" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="50.7" — fact_value "50.7" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="45.4" — fact_value "45.4" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="19.0" — fact_value "19.0" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="121.8" — fact_value "121.8" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="50.5" — fact_value "50.5" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="26.7" — fact_value "26.7" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="23.5" — fact_value "23.5" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="116.6" — fact_value "116.6" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="71.9" — fact_value "71.9" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="59.7" — fact_value "59.7" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="21.5" — fact_value "21.5" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="20.9" — fact_value "20.9" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="13.8" — fact_value "13.8" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="3.6" — fact_value "3.6" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="2.0" — fact_value "2.0" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="1.8" — fact_value "1.8" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="8.3" — fact_value "8.3" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="2.2" — fact_value "2.2" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="1.7" — fact_value "1.7" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="2.7" — fact_value "2.7" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="1.9" — fact_value "1.9" NOT found in evidence text
- `io-9304252516f5b4a0`: fact_value="66.1" — fact_value "66.1" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="19.9" — fact_value "19.9" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="111.1" — fact_value "111.1" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="114.0" — fact_value "114.0" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="611.7" — fact_value "611.7" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="111.1" — fact_value "111.1" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="67.2" — fact_value "67.2" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="44.0" — fact_value "44.0" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="18.1" — fact_value "18.1" NOT found in evidence text
- `io-0873c447e9b9733c`: fact_value="19" — fact_value "19" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="113.8" — fact_value "113.8" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="219.9" — fact_value "219.9" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="81.1" — fact_value "81.1" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="85.8" — fact_value "85.8" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="1.05" — fact_value "1.05" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="81.1" — fact_value "81.1" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="105.7" — fact_value "105.7" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="24.6" — fact_value "24.6" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="17.0" — fact_value "17.0" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="83.7" — fact_value "83.7" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="71.2" — fact_value "71.2" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="48.3" — fact_value "48.3" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="19.2" — fact_value "19.2" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="18.0" — fact_value "18.0" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="49.2" — fact_value "49.2" NOT found in evidence text
- `io-ca43d858fe433433`: fact_value="16.7" — fact_value "16.7" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="696.7" — fact_value "696.7" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="38.4" — fact_value "38.4" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="3.3" — fact_value "3.3" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="3.0" — fact_value "3.0" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="27.5" — fact_value "27.5" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="16.5" — fact_value "16.5" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="2.0" — fact_value "2.0" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="974.6" — fact_value "974.6" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="817.5" — fact_value "817.5" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="1.6" — fact_value "1.6" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="730.5" — fact_value "730.5" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="598.2" — fact_value "598.2" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="174.4" — fact_value "174.4" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="24.1" — fact_value "24.1" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="22.7" — fact_value "22.7" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="11.8" — fact_value "11.8" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="169.1" — fact_value "169.1" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="19.3" — fact_value "19.3" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="14.4" — fact_value "14.4" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="13.4" — fact_value "13.4" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="91.3" — fact_value "91.3" NOT found in evidence text
- `io-82bd93037aae3793`: fact_value="11.6" — fact_value "11.6" NOT found in evidence text
- `io-7e619d8c238339cc`: fact_value="3" — fact_value "3" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="86.2" — fact_value "86.2" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="91.0" — fact_value "91.0" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="90.2" — fact_value "90.2" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="830.8" — fact_value "830.8" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="91.0" — fact_value "91.0" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="98.5" — fact_value "98.5" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="7.5" — fact_value "7.5" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="11.5" — fact_value "11.5" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="38.4" — fact_value "38.4" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="23.0" — fact_value "23.0" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="15.4" — fact_value "15.4" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="19.0" — fact_value "19.0" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="20.2" — fact_value "20.2" NOT found in evidence text
- `io-d4c7af5cba135595`: fact_value="5.3" — fact_value "5.3" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="4" — fact_value "4" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2.6" — fact_value "2.6" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="4" — fact_value "4" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="4" — fact_value "4" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="3.75" — fact_value "3.75" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text
- `io-dd7f1db542d212a3`: fact_value="2" — fact_value "2" NOT found in evidence text

### Invariant 2: Subject Attribution (candidate ↔ event ↔ fact ↔ evidence)

Subject attribution validation requires running the V48AB shadow evaluator.
The frozen corpus does not store explicit subject fields per IO.
V48AB shadow evaluation at V48AD (ea6abd5) showed:
- Independent sample: 143/150 (95.3%)
- V48X TRUE retained: 13/19
- V48X FALSE rejected: 5/5 (preserved)
- 7 remaining failures (2 positive + 1 negative + 4 ambiguous)

---

## JOINT ADJUDICATION

### Combined Diagnosis

| Track | Question | Answer |
|---|---|---|
| TRACK A | How did fact_value=-25 get into gold-fed-2024-07-25bp? | Manual data entry in Gold Set V2 YAML — NO extraction pipeline involved |
| TRACK B | How many fact/evidence mismatches in frozen corpus (51 IOs)? | 318 mismatches, 162 matches, 0 no evidence |
| INVARIANT 1 | Is fact_value supported by evidence for all IOs? | {"YES" if fail_count == 0 else "NO — " + str(fail_count) + " failures"} |
| INVARIANT 2 | Is subject attribution validated? | V48AB: 143/150 (95.3%), 7 remaining failures |

### Classification

**SYSTEMIC** — Multiple fact/evidence mismatches found in frozen corpus.
May indicate a missing Core invariant (fact/evidence consistency check).
