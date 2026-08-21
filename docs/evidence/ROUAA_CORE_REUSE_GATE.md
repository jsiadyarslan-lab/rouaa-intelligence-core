# REUSE GATE — Independent HTTP Consumer Test
**Starting commit:** 339c8ef
**Verdict:** PASS

## Test Matrix

| Test | Result |
|------|--------|
| Discovery | 6/6 |
| Retrieval | 6/6 |
| Trace | 6/6 |
| Canonical identity | 6/6 |
| Provenance reconstruction | 6/6 |
| Standalone reuse | 6/6 |
| Restart stability | 6/6 |

## Provenance Chain Structure

The HTTP response chain contains nested layers:
- fact (fact_id, metric, value)
- evidence (evidence_id, excerpt)
- representation (representation_id, content_sha256)
- document (document_id, canonical_url)
- source (source_id, source_url)
- event (event_id, event_type — in IO top-level)
- IntelligenceObject (io_id, headline — in IO top-level)

## What This Proves

An independent consumer using ONLY HTTP JSON can:
1. Discover IOs via list endpoint
2. Retrieve individual IOs
3. Retrieve provenance trace
4. Verify canonical identity
5. Reconstruct full provenance chain (Source→Document→Fact→Evidence→Event→IO)
6. Build standalone reusable payload
7. Survive server restart

## Production Files Changed

0

---
**PASS**. STOP.
