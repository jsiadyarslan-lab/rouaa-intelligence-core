# ROUAA INTELLIGENCE CORE — PRODUCTIONIZATION PLAN V1

**Status:** PRODUCTIONIZATION PLAN (planning only — no deployment, no product connections)
**Date:** 2026-08-16
**Directive:** EXECUTION DIRECTIVE — MAKE REPOSITORY 4 PUBLIC + PRODUCTIONIZATION REVIEW V1 (user-issued verbatim)
**Object under plan:** `jsiadyarslan-lab/rouaa-intelligence-core` @ `743c3bf` (PUBLIC since this task; visibility verified)
**Companion:** `ROUAA_INTELLIGENCE_CORE_PRODUCTION_READINESS_REVIEW_V1.md` (same commit)

---

## 1. Staging Scope (what Gate-G execution builds — the ONLY authorized build list)

| # | Item | Why (gap reference) | Boundary |
|---|---|---|---|
| S1 | **Service entry point** `intelligence_core/service.py`: minimal process exposing `/healthz` + a run-once/loop runner invoking `pipeline.run_many` over registered configs | G-RUN | stdlib `http.server`-class ONLY; no framework |
| S2 | **Environment contract**: `ROUAA_CORE_STORAGE_ROOT` (required), `ROUAA_CORE_RUN_INTERVAL` (optional), `ROUAA_LOG_LEVEL` | G-CFG | no credentials in env at staging (no external transport) |
| S3 | **Storage hardening**: single-writer lock file + optional fsync-on-append + blob write-to-temp-then-rename | G-STO | JSONL/blob model UNCHANGED (SQL remains a separate decision) |
| S4 | **Acquisition operations**: per-source timeout from env, simple retry (2×, exponential backoff) for transport errors only, per-source politeness interval | G-ACQ | no new acquisition mechanisms; no anti-bot bypass; no CAPTCHA |
| S5 | **Telemetry minimum**: structured run summary (counts per collection + source states + errors) emitted to stdout/log; storage-size gauge | G-OBS | no external metrics service at staging |
| S6 | **Backup/restore procedure**: volume snapshot + verify script (re-hash blobs vs index) | G-STO | documented procedure, not automation |
| S7 | **Railway staging deployment** (Gate H): single service, volume mount at `ROUAA_CORE_STORAGE_ROOT` | L-section | staging only; no domain, no public API |

## 2. Railway Topology (design — NOTHING created)

- **Service:** one Python 3.12-slim worker (Nixpacks/requirements-empty → stdlib only).
- **Start command:** `python -m intelligence_core.service` (S1; falls back to run-once + sleep loop per `ROUAA_CORE_RUN_INTERVAL`).
- **Health:** `/healthz` (liveness: process up; readiness: storage writable). Railway healthcheck TCP/HTTP.
- **Persistence:** Railway Volume mounted at `/data`; `ROUAA_CORE_STORAGE_ROOT=/data/store`. Blobs + JSONL co-located (content-addressed; snapshot-friendly).
- **Restart policy:** always (Railway default); crash of a run must not lose partial evidence (append-only guarantees).
- **Env vars at staging:** ONLY S2 list. **Secrets:** none required at staging (no auth, no external transport). Production secrets enter only with the FUTURE EXTERNAL API decision.
- **Logging:** stdout JSON lines (S5); Railway log drain optional.
- **Deployment strategy/rollback:** deploys are immutable builds; rollback = reactivate previous build; volume untouched by deploys (state survives rollbacks by design).
- **Config file:** source configurations staged as a versioned `configs/` file read at start (Core config contract; no DB).

## 3. Storage Operations (baseline UNCHANGED — JSONL + content-addressed blobs)

- **Durability:** filesystem-backed; S3 adds fsync option + atomic blob writes; backup = volume snapshot + verification script (S6).
- **Concurrency:** single-writer model — enforced by lock file (S3). Readers (future API) read append-only files safely (last-row-wins view).
- **Corruption:** detectable (sha-256 mismatch on blob verify; JSONL line parse failure) → quarantine file + replay from snapshot; **never auto-mutate evidence**.
- **Growth:** bounded by acquisition rate (§6); retention policy remains an open decision (per D9 principles).

## 4. API Boundary (conceptual — not implemented)

| Endpoint class | Level | Notes |
|---|---|---|
| `/healthz`, run summaries | CORE API (staging) | S1/S5 |
| sources/documents/IO read + trace (Contract B) | CORE API (post-staging) | IO-first; chain-preserving |
| delivery status/ack, external destinations | FUTURE EXTERNAL API | auth + TLS + rate limits required first |
| store internals, governance ops | INTERNAL | never exposed |

Cross-cutting contract for any API: authentication (staged token at minimum), versioning (URI `/v1`), pagination (cursor by id), idempotent reads, error model (`{code, message, trace_ref}`), rate limits per token.

## 5. External Delivery (FUTURE — requirements recorded, NOT built)

Destination identity registry · mutual TLS or signed tokens · ACK protocol with retry/backoff · idempotency by (io_id, version, destination) — **already ledger-enforced** · replay window from delivery ledger · delivery audit immutable. Authorization: separate decision.

## 6. Scaling Envelope (evidence-bounded)

Current reality: ≤10 onboarded sources, hourly-or-slower fetch cadence, documents/day in the tens, single writer, storage growth ≈ fetched bytes (deduplicated by content hash). **Smallest sufficient topology = ONE small service + ONE volume.** Kubernetes / Redis / Kafka / microservices: **explicitly rejected** — no evidence of necessity (directive §11); revisit only with measured load evidence.

## 7. Recovery Matrix (all preserve evidence + auditability)

| Failure | Recovery |
|---|---|
| Process crash mid-run | append-only ⇒ partial run is valid state; restart continues; retrieval events record each act |
| Storage/volume failure | restore last snapshot; verify (S6); gap = re-fetch window (representations dedupe) |
| Network failure | S4 retry (transport-class only) → source BLOCKED; others isolated (proven) |
| Malformed document | document-scoped failure; state machine holds DOCUMENTED/partial; audit row |
| Source outage | BLOCKED state + health record; no cross-source impact (proven) |
| Partial pipeline failure | per-source scope; store remains consistent (append-only) |
| Delivery failure | ledger keeps PENDING/FAILED; replay by idempotency key |
| Corrupted representation | detected by hash; quarantine + re-fetch as NEW representation (never overwrite) |
| Configuration rollback | configs are versioned files; redeploy previous config; all historical evidence stands |

## 8. Product Integration Boundary (unchanged sequence)

Gate G (production architecture approved — this plan + review) → Gate H (Railway staging + smoke/persistence/health validation) → Gate I (first controlled product integration: read-only IO consumption) → Gate J (remaining products). **No product becomes a canonical source of Core intelligence; no product mutations.**

## 9. Open Decisions (NOT auto-resolved)

SQL migration timing · LICENSE · public API authentication model · external transport authorization · retention periods · platform-distribution entity rule (D6 extension) · Railway production domain/DNS.
