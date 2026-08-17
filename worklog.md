
---
Task ID: V2-RELIABILITY-CLOSURE
Agent: main
Task: Execute CORE ENGINE RELIABILITY & SCALE CLOSURE V2 directive — fix transport 100-reader 16% errors, optimize list endpoint, expand corpus to 100+, freeze 30 golden IOs, run 25/50/100 concurrent ingestion, 5x/10x reprocessing, golden regression, produce V2 evidence doc.

Work Log:
- Read existing transport (production_transport.py) and store (store.py)
- Identified root cause of 16% transport errors: every request does O(F×(R+D+S+E)) full file scans via store.latest_by_id() inside build_intelligence_object()
- Identified root cause of list endpoint slowness: full store scan + per-event rebuild on every request
- Next: build CachedStore wrapper + IO projection cache + list response cache

Stage Summary:
- Diagnosis: Transport errors are CORE/TRANSPORT reliability issues, NOT source-level gaps
- Architecture defects identified: (1) O(N) store scans per fact, (2) per-event rebuild on list, (3) O(N) io_id lookup, (4) no IO cache
- Plan: Phase 1 (transport fix) → Phase 2 (concurrency 25/50/100) → Phase 3 (reprocess 5x/10x) → Phase 4 (corpus) → Phase 5 (golden) → Phase 6 (regression) → Phase 7 (V2 doc)
