# V48 Human Adjudication Packet v1

## Metadata
- Population: 480
- Source: RECON v2 (8407a21e34a0)
- Agent role: IMPLEMENTATION_WORKER — NOT CLASSIFICATION AUTHORITY
- All human_support_class: PENDING_HUMAN
- N1-N5: FROZEN
- 10% threshold: FROZEN (pre-registered, immutable)

## Contextual Support Distribution (TOOL observation — NOT human adjudication)

| Class | Count | Meaning |
|---|---|---|
| DIRECT_CONTEXTUAL_SUPPORT | 103 | fact_value in structural segment excerpt |
| DOCUMENT_PRESENCE_ONLY | 318 | fact_value in full document but NOT in segment |
| AMBIGUOUS_CONTEXT | 59 | multiple occurrences — context unclear |
| INSUFFICIENT_EVIDENCE | 0 | no canonical evidence or fact not found |

## §5 Critical Distinction

- fact_value_present = TRUE: 480/480
- fact_context_supported = TRUE: 103/480
- Present but NOT contextually supported: 377/480

## Per-Case Summary (first 20 cases)

| case_id | fact_value | contextual_class | segment_available | occurrence_count |
|---|---|---|---|---|
| case-0001 | lower | DOCUMENT_PRESENCE_ONLY | YES | 1 |
| case-0002 | 0 | DOCUMENT_PRESENCE_ONLY | YES | 1083 |
| case-0003 | 110 | DOCUMENT_PRESENCE_ONLY | YES | 1 |
| case-0004 | 0 | DOCUMENT_PRESENCE_ONLY | YES | 1083 |
| case-0005 | 0 | AMBIGUOUS_CONTEXT | YES | 1083 |
| case-0006 | 0 | DOCUMENT_PRESENCE_ONLY | YES | 1083 |
| case-0007 | 31 | DOCUMENT_PRESENCE_ONLY | YES | 5 |
| case-0008 | raise | DOCUMENT_PRESENCE_ONLY | YES | 3 |
| case-0009 | lower | DOCUMENT_PRESENCE_ONLY | YES | 13 |
| case-0010 | lower | AMBIGUOUS_CONTEXT | YES | 13 |
| case-0011 | lower | AMBIGUOUS_CONTEXT | YES | 13 |
| case-0012 | raised | DOCUMENT_PRESENCE_ONLY | YES | 1 |
| case-0013 | lower | DOCUMENT_PRESENCE_ONLY | YES | 13 |
| case-0014 | lower | AMBIGUOUS_CONTEXT | YES | 13 |
| case-0015 | raise | DOCUMENT_PRESENCE_ONLY | YES | 3 |
| case-0016 | 1 | AMBIGUOUS_CONTEXT | YES | 142 |
| case-0017 | raise | DOCUMENT_PRESENCE_ONLY | YES | 2 |
| case-0018 | cut | DOCUMENT_PRESENCE_ONLY | YES | 34 |
| case-0019 | 2 | AMBIGUOUS_CONTEXT | YES | 7095 |
| case-0020 | 2.25 | AMBIGUOUS_CONTEXT | YES | 28 |

## §10 Forbidden Conclusion

This packet does NOT claim:
- '480/480 facts are correct'
- '480/480 facts are contextually supported'

The only permitted conclusion: CANONICAL_SOURCE_RECOVERED_AND_HUMAN_ADJUDICATION_PACKET_PREPARED
