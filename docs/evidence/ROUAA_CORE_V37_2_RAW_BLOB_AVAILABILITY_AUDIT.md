# ROUAA Core V37.2 — Raw Blob Availability Audit

> **Status**: COMPLETE  
> **Date**: 2026-08-19  
> **Directive**: V37.2 IMPLEMENTATION PREFLIGHT §2  
> **Baseline**: 5a27473f5717c46f91e11637f289ee17cc450817  
> **Ledger**: `intelligence_core/tests/reliability/v37_1_evidence_selection_gap_ledger.json`

---

## Summary

| Metric | Value |
|--------|------:|
| total_cases | 158 |
| available_blobs (fact-level) | **158** |
| missing_blobs (fact-level) | **0** |
| unique_documents | 16 |
| available_unique_documents | **16** |
| missing_unique_documents | **0** |

**Result: 158/158 facts map to an available raw HTML blob. 16/16 unique documents have canonical blob files on disk.**

---

## Method

1. Loaded the 158-record V37.1 evidence selection gap ledger.
2. For each `document_id`, queried all store roots (`v3_corpus_store`, `real_corpus_store`, `real_corpus_store_new`, `real_corpus_store_new_waveb`, `scale_50_store`) via `CachedStore`.
3. Selected the latest `Representation` by `created_at` for each document.
4. Verified `raw_location` path exists on disk using `Path.exists()`.
5. No substitution or fallback was used — each fact maps to the canonical blob for its `document_id`.

---

## Blob Map (16 unique documents)

| document_id | store | size_bytes |
|-------------|-------|----------:|
| doc-3977e22b6168c0e8 | scale_50_store | 143,459 |
| doc-3c78c920fe89e689 | real_corpus_store_new_waveb | 187,975 |
| doc-49401aaf4cb8f90c | real_corpus_store_new_waveb | 147,044 |
| doc-5a0547ffcaa7a57e | real_corpus_store | 53,431 |
| doc-7c5cd3967c2f9f10 | scale_50_store | 69,765 |
| doc-7d5803d21c44a224 | scale_50_store | 128,147 |
| doc-7eafb0e5382d524a | scale_50_store | 273,293 |
| doc-8700a0859c829c44 | real_corpus_store | 93,163 |
| doc-9009073715abef71 | real_corpus_store_new | 187,395 |
| doc-93c89f0c3311c178 | real_corpus_store | 52,008 |
| doc-a72c0918e27dd12b | v3_corpus_store | 286,806 |
| doc-ab8dbef146c79b7d | scale_50_store | 241,367 |
| doc-bda337df91614348 | real_corpus_store_new | 77,338 |
| doc-cc10a6c194e5435b | v3_corpus_store | 272,240 |
| doc-da802c5165a71f32 | real_corpus_store_new_waveb | 1,280,571 |
| doc-e96dc7902ddcfa54 | real_corpus_store | 62,480 |

Blob paths are recorded in the companion JSON artifact.

---

## Notes

- `doc-da802c5165a71f32` is a large document (1.28 MB). Contains 10 GT facts with value collisions (`50` and `10` each appearing multiple times). EvidenceSegmentV1 selection must handle this via structural context, not value occurrence count.
- `doc-a72c0918e27dd12b` (Statistik Austria, 286 KB) contains 30 GT facts with `value=5`. The v32 adjudication ledger records `occurrences=717` for these facts. This is classified as a listing/index page — see Occurrence Identity Review for implications.
- All blobs are raw HTML (confirmed: no PDF magic bytes, no null bytes in first 1,000 bytes).

---

## Acceptance

- [x] Every one of the 158 facts maps to a canonical document ✓
- [x] All 16 canonical raw HTML blobs are available on disk ✓
- [x] No fabricated fallback used ✓

**Precondition §2 CLEARED.**
