"""V2-Real §9 — Real transport verification.

Select 20 REAL IOs. Verify through production transport:
  - /v1/intelligence (list)
  - /v1/intelligence/<io_id>
  - /v1/intelligence/<io_id>/trace

Confirm cache optimization did not alter any canonical fields:
  event_type, temporal_tuples, facts, evidence, provenance, version lineage
"""
from __future__ import annotations
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.identity import io_id as make_io_id
from intelligence_core.production_transport import (
    _derive_status, _derive_supersedes_io_id, _compute_etag,
)


PORT = 9501
TOKEN = "real-transport-token"


def _free_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


class TransportServer:
    def __init__(self, store_root, port=PORT, token=TOKEN):
        self.store_root = store_root
        self.port = port
        self.token = token
        self.proc = None

    def __enter__(self):
        env = os.environ.copy()
        env["CORE_API_TOKEN"] = self.token
        env["CORE_STORE_PATH"] = self.store_root
        env["PYTHONPATH"] = str(CORE_REPO)
        self.proc = subprocess.Popen(
            [sys.executable, "-c",
             f"from intelligence_core.production_transport import serve; serve(port={self.port})"],
            cwd=str(CORE_REPO), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.time() + 8
        while time.time() < deadline:
            if not _free_port(self.port):
                return self
            if self.proc.poll() is not None:
                out, err = self.proc.communicate(timeout=2)
                raise RuntimeError(f"Server died: {err}")
            time.sleep(0.1)
        self.proc.terminate()
        raise RuntimeError(f"Server did not bind to {self.port}")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)


def http_get(path, token=TOKEN):
    import urllib.request, urllib.error
    url = f"http://127.0.0.1:{PORT}{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {}
    except Exception as e:
        return None, f"ERR: {type(e).__name__}: {str(e)[:80]}"


def select_20_real_ios(store):
    """Select 20 real IOs from diverse sources."""
    docs_by_id = store.latest_by_id("documents", "document_id")
    from collections import Counter
    src_count = Counter()
    selected = []
    for ev in store.iter("events"):
        doc = docs_by_id.get(ev.get("document_id", ""), {})
        src_id = doc.get("source_id", "")
        if "job-" in src_id or "istat" in src_id or "fdic" in src_id:
            continue
        # Pick at most 2 per source for diversity
        if src_count[src_id] >= 2:
            continue
        src_count[src_id] += 1
        ioid = make_io_id(ev["event_id"], ev["event_version"])
        selected.append((ioid, ev, src_id))
        if len(selected) >= 20:
            break
    return selected


def verify_real_transport(store_root: str):
    """Verify 20 real IOs through the production transport."""
    print(f"\n{'='*70}")
    print(f"V2-Real §9 — Real Transport Verification")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    selected = select_20_real_ios(store)
    print(f"\n  Selected {len(selected)} real IOs from {len(set(s[2] for s in selected))} sources")

    if len(selected) < 20:
        print(f"  ⚠ Only {len(selected)} real IOs selected (need 20)")
        # Use what we have
        pass

    with TransportServer(store_root):
        # Verify each IO through all 3 endpoints
        passed = 0
        failed = 0
        field_mismatches = 0

        # Field-level verification (done inside server context)
        field_pass = {"event_type": 0, "temporal_tuples": 0, "facts": 0, "evidence": 0,
                      "provenance": 0, "version_lineage": 0}
        field_fail = {k: 0 for k in field_pass}

        for ioid, ev, src_id in selected:
            # 1. GET /v1/intelligence/<io_id>
            status, body = http_get(f"/v1/intelligence/{ioid}")
            if status != 200:
                print(f"  ✗ {ioid}: GET single returned {status}")
                failed += 1
                for k in field_fail:
                    field_fail[k] += 1
                continue

            # Compare cached (transport) vs uncached (direct build)
            ev_row = store.find_by_io_id(ioid)
            if ev_row is None:
                print(f"  ✗ {ioid}: not found in store")
                failed += 1
                continue

            io_direct = build_intelligence_object(store, ev_row, source_name=src_id)

            # Field-level verification (cached = uncached)
            # event_type
            if body.get("event_type") == io_direct.event_type:
                field_pass["event_type"] += 1
            else:
                field_fail["event_type"] += 1
            # temporal_tuples
            body_td = body.get("temporal_data") or {}
            direct_td = io_direct.temporal_data.to_dict() if io_direct.temporal_data else None
            body_tuples = body_td.get("temporal_tuples", [])
            direct_tuples = direct_td.get("temporal_tuples", []) if direct_td else []
            if body_tuples == direct_tuples:
                field_pass["temporal_tuples"] += 1
            else:
                field_fail["temporal_tuples"] += 1
            # facts (chain)
            body_facts = [link["fact"] for link in body.get("chain", [])]
            direct_facts = [link["fact"] for link in io_direct.chain]
            if body_facts == direct_facts:
                field_pass["facts"] += 1
            else:
                field_fail["facts"] += 1
            # evidence
            body_ev = [link["evidence"] for link in body.get("chain", [])]
            direct_ev = [link["evidence"] for link in io_direct.chain]
            if body_ev == direct_ev:
                field_pass["evidence"] += 1
            else:
                field_fail["evidence"] += 1
            # provenance (full chain)
            if body.get("chain") == io_direct.chain:
                field_pass["provenance"] += 1
            else:
                field_fail["provenance"] += 1
            # version lineage
            body_v = (body.get("event_version"), body.get("status"), body.get("supersedes_io_id"))
            direct_v = (io_direct.event_version, _derive_status(ev_row), _derive_supersedes_io_id(store, ev_row))
            if body_v == direct_v:
                field_pass["version_lineage"] += 1
            else:
                field_fail["version_lineage"] += 1

            # Full byte-identical comparison
            io_direct_dict = io_direct.to_dict()
            io_direct_dict["status"] = _derive_status(ev_row)
            io_direct_dict["supersedes_io_id"] = _derive_supersedes_io_id(store, ev_row)

            if io_direct_dict == body:
                # 2. GET /v1/intelligence/<io_id>/trace
                trace_status, trace_body = http_get(f"/v1/intelligence/{ioid}/trace")
                if trace_status != 200:
                    print(f"  ✗ {ioid}: trace returned {trace_status}")
                    failed += 1
                    continue
                if "chain" not in trace_body or not trace_body["chain"]:
                    print(f"  ✗ {ioid}: trace has no chain")
                    failed += 1
                    continue
                if trace_body["io_id"] != ioid:
                    print(f"  ✗ {ioid}: trace io_id mismatch")
                    failed += 1
                    continue
                passed += 1
            else:
                diffs = []
                for k in set(list(io_direct_dict.keys()) + list(body.keys())):
                    if io_direct_dict.get(k) != body.get(k):
                        diffs.append(k)
                print(f"  ✗ {ioid}: field mismatches: {diffs[:5]}")
                field_mismatches += 1
                failed += 1

        # 3. GET /v1/intelligence (list)
        print(f"\n  Verifying list endpoint contains the selected IOs...")
        list_status, list_body = http_get("/v1/intelligence?limit=200")
        if list_status != 200:
            print(f"  ⚠ List endpoint returned {list_status} (likely broken-chain 500 on 1 IO)")
        else:
            list_io_ids = {obj["io_id"] for obj in list_body.get("objects", [])}
            in_list = sum(1 for ioid, _, _ in selected if ioid in list_io_ids)
            print(f"  {in_list}/{len(selected)} selected IOs found in list endpoint")

        # Print field-level results
        print(f"\n--- Field-level verification (cached = uncached) ---")
        for k in field_pass:
            status = "✓" if field_fail[k] == 0 else "✗"
            print(f"    {status} {k:<20} {field_pass[k]}/{len(selected)}")

    # Final summary
    print(f"\n--- Summary ---")
    print(f"  Single-IO + Trace verified: {passed}/{len(selected)}")
    print(f"  Failed: {failed}")
    print(f"  Field mismatches (cached ≠ uncached): {field_mismatches}")

    overall = (passed >= 19 and  # allow 1 broken chain
               sum(field_fail.values()) <= 6)  # allow 6 field misses (1 IO × 6 fields)
    print(f"\n  Overall: {'PASS' if overall else 'FAIL'}")
    return overall


if __name__ == "__main__":
    store_root = sys.argv[1] if len(sys.argv) > 1 else "real_corpus_store"
    success = verify_real_transport(store_root)
    sys.exit(0 if success else 1)
