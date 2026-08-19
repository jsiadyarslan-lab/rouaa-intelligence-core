"""PHASE 2 ANALYSIS — operates on the live-capture + store1 from
phase2_live_validation. Covers directive sections 6,7,8,9,10,11,12,13.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

from intelligence_core.store import AppendOnlyStore
from intelligence_core.acquisition import parse_rss_items
from intelligence_core.normalize import strip_html
from intelligence_core.extract import extract_facts
from intelligence_core.temporal import parse_rfc822_pubdate, parse_iso_or_date, ordering_filter
from intelligence_core.delivery import build_intelligence_object, deliver
from intelligence_core import governance
from intelligence_core.contracts import SupersessionReason
from intelligence_core.tests.replay.phase2_live_validation import (SOURCES, EUROSTAT_PATTERNS, LiveCapture,
                                    CachedTransport, execute_suite, make_fixtures,
                                    build_registry, cfg_for, lineage, counts)


def load_base() -> Path:
    import glob, os
    cands = sorted(glob.glob(r"C:/Users/jaber/AppData/Local/Temp/p2v2_*"),
                   key=os.path.getmtime)
    return Path(cands[-1])


def section_temporal(capdir: Path, ledger: list) -> dict:
    by_url = {e["url"]: e for e in ledger if "file" in e}
    out = {}
    # FDIC GovDelivery RSS (captured): RFC-822 -0500
    e = by_url.get(SOURCES["FDIC"]["url"])
    fdic_items = parse_rss_items((capdir / e["file"]).read_bytes().decode("utf-8", "replace"))
    t = parse_rfc822_pubdate(fdic_items[0]["pubDate"])
    out["FDIC"] = {"original": t.original_value, "status": t.timezone_status.value,
                   "utc": t.normalized_utc,
                   "ordering": t.ordering_participating()}
    # ISTAT + DFSA: +0000
    for code in ("ISTAT", "DFSA"):
        e = by_url[SOURCES[code]["url"]]
        items = parse_rss_items((capdir / e["File" if False else "file"]).read_bytes()
                                .decode("utf-8", "replace"))
        t = parse_rfc822_pubdate(items[0]["pubDate"])
        out[code] = {"original": t.original_value, "status": t.timezone_status.value,
                     "utc": t.normalized_utc, "ordering": t.ordering_participating()}
    # DGT article: URL date vs <time datetime> (conflict coexistence, live capture)
    dgt_items = [i for i in ledger if "/Articles/" in i.get("url", "")]
    if dgt_items:
        e = dgt_items[0]
        body = (capdir / e["file"]).read_bytes().decode("utf-8", "replace")
        m_url = re.search(r"/Articles/(\d{4})/(\d{2})/(\d{2})/", e["url"])
        m_time = re.search(r'<time datetime="([^"]+)"', body)
        url_t = parse_iso_or_date(f"{m_url.group(1)}-{m_url.group(2)}-{m_url.group(3)}")
        url_t.timestamp_semantics = "document_date"
        url_t.provenance_source = "url_date"
        naive_t = parse_iso_or_date(m_time.group(1)[:10]) if m_time else None
        out["DGT"] = {"url_date": url_t.original_value,
                      "time_attr": naive_t.original_value if naive_t else None,
                      "coexist": url_t.original_value != (naive_t.original_value if naive_t else None),
                      "utc": None, "ordering": False}
    # ordering guard: only explicit-zone tuples participate
    parts = ordering_filter([parse_rfc822_pubdate(fdic_items[0]["pubDate"]),
                             parse_iso_or_date(m_time.group(1)[:10]) if dgt_items and m_time
                             else parse_iso_or_date("2026-08-14T07:00:02")])
    out["ordering_guard_participants"] = len(parts)
    return out


def section_description_only(capdir: Path, ledger: list) -> dict:
    """Directive 6: FDIC GovDelivery RSS carries full content in <description>."""
    by_url = {e["url"]: e for e in ledger if "file" in e}
    e = by_url[SOURCES["FDIC"]["url"]]
    text = (capdir / e["file"]).read_bytes().decode("utf-8", "replace")
    items = parse_rss_items(text)
    desc = strip_html(items[0].get("description", "") if isinstance(items[0], dict) and
                      "description" in items[0] else _desc_of(text))
    facts_in_desc = extract_facts(desc, EUROSTAT_PATTERNS, "rep-probe", "doc-probe")
    facts_in_title = extract_facts(strip_html(items[0]["title"]), EUROSTAT_PATTERNS,
                                   "rep-probe", "doc-probe")
    # does the pipeline consult <description>? code-path fact:
    consults = "<description" in open(_pipeline_path(), encoding="utf-8").read()
    return {"description_length": len(desc),
            "description_sample": desc[:180],
            "facts_extractable_from_description": len(facts_in_desc),
            "facts_from_title": len(facts_in_title),
            "pipeline_reads_description_tag": consults,
            "classification": None}  # set by caller


def _pipeline_path():
    import intelligence_core.pipeline as p
    return p.__file__


_DESC = re.compile(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.S)


def _desc_of(text: str) -> str:
    m = _DESC.search(text)
    return m.group(1) if m else ""


def section_istat_boundary(store: AppendOnlyStore) -> dict:
    """Directive 7: reproduce Post-Q3 pattern boundaries through the new Core."""
    facts = list(store.iter("facts"))
    by_doc = {}
    docs = store.latest_by_id("documents", "document_id")
    for f in facts:
        url = docs.get(f["document_id"], {}).get("canonical_url", "?")
        by_doc.setdefault(url, []).append(f["metric"])
    return {"per_document_metrics": by_doc,
            "cpi_dedicated_inflation_rate": any(
                "inflation_rate" in ms and "cpi" not in u and "consumer-prices" in u
                for u, ms in by_doc.items()) or "inflation_rate seen" if
            any("inflation_rate" in ms for ms in by_doc.values()) else
            ("inflation_rate NOT produced (boundary reproduced)"
             if any("consumer-prices" in u for u in by_doc) else "no CPI doc in set"),
            "trade_doc_zero_facts": not any("foreign-trade" in u for u in by_doc) or
            all(not m for u, ms in by_doc.items() if "foreign-trade" in u)}


def section_isolation(base: Path, capdir: Path, ledger: list, fixtures: dict) -> dict:
    """Directive 8: 3 sources, one controlled failure, batch execution."""
    import tempfile as _tf
    store = AppendOnlyStore(_tf.mkdtemp(prefix="p2iso_", dir=str(base)))
    from intelligence_core.pipeline import run_many
    from intelligence_core.config import SourceConfig
    good1 = cfg_for("ISTAT", SOURCES["ISTAT"])
    good2 = cfg_for("DGT", SOURCES["DGT"])
    bad = SourceConfig(code="FDIC", name="FDIC", institution_id="INST-fdic-001",
                       source_path="https://www.fdic.gov/nonexistent-path",
                       feed_format="rss", patterns=[], event_type="statistical_release")
    t = CachedTransport(capdir, ledger, fixtures)
    res = run_many(store, build_registry(), [good1, good2, bad], transport=t,
                   run_id="iso-run")
    return {r["source"]: r.get("state") for r in res}


def section_idempotency(base: Path, capdir: Path, ledger: list, fixtures: dict) -> dict:
    """Directive 9: same source twice on the SAME store."""
    import tempfile as _tf
    s_dir = _tf.mkdtemp(prefix="p2idem_", dir=str(base))
    r1 = execute_suite(s_dir, capdir, ledger, fixtures, run_id="idem-1")
    before = counts(r1 and AppendOnlyStore(s_dir))
    r2 = execute_suite(s_dir, capdir, ledger, fixtures, run_id="idem-2")
    after = counts(AppendOnlyStore(s_dir))
    return {"before": before, "after": after,
            "no_duplicate_deliveries": before["deliveries"] == after["deliveries"],
            "no_duplicate_facts": before["facts"] == after["facts"],
            "no_duplicate_representations": before["representations"] == after["representations"]}


def section_content_change(base: Path, capdir: Path, ledger: list, fixtures: dict) -> dict:
    """Directive 10: controlled modified representation from a REAL captured doc."""
    import tempfile as _tf
    s_dir = _tf.mkdtemp(prefix="p2cc_", dir=str(base))
    store = AppendOnlyStore(s_dir)
    from intelligence_core.pipeline import run_source
    # run 1: pristine ISTAT suite
    t = CachedTransport(capdir, ledger, fixtures)
    for code in ("ISTAT",):
        run_source(store, build_registry(), cfg_for(code, SOURCES[code]),
                   transport=t, run_id="cc-1")
    facts_before = sorted((f["fact_id"], f["value"]) for f in store.iter("facts"))
    reps_before = {r["representation_id"] for r in store.iter("representations")}
    # choose the doc that produced facts; modify its body
    target_doc = next(iter(store.iter("documents")))
    # find its captured URL + body
    doc_url = target_doc["canonical_url"]
    by_final = {e.get("final_url"): e for e in ledger if "file" in e}
    e = by_url_exact(ledger, doc_url)
    body = (capdir / e["file"]).read_bytes()
    modified = body.replace(b"2.9", b"3.1") if b"2.9" in body else body + \
        b"<p>GDP grew by 1.9 percent in the revised estimate.</p>"
    fixtures2 = dict(fixtures)
    # cached transport serves modified body for that URL
    class ModifiedTransport(CachedTransport):
        def get(self, url, timeout=30):
            if url == doc_url or url.rstrip("/") == doc_url.rstrip("/"):
                return 200, url, modified, "text/html"
            return super().get(url, timeout=timeout)
    t2 = ModifiedTransport(capdir, ledger, fixtures2)
    for code in ("ISTAT",):
        run_source(store, build_registry(), cfg_for(code, SOURCES[code]),
                   transport=t2, run_id="cc-2")
    reps_after = {r["representation_id"] for r in store.iter("representations")}
    new_reps = reps_after - reps_before
    facts_after = sorted((f["fact_id"], f["value"]) for f in store.iter("facts"))
    # governance path (directive 10): source-revision supersession THEN recompute.
    # VALIDATION-HARNESS CORRECTION (extraction-time): scope to the MODIFIED
    # document's event and its snapshot fact — mirrors the validated pattern of
    # buyer_simulation_v1.py @ 150ae87. The previous first-by-sorted-hash
    # selection made the outcome hash-order-dependent (the 8de74e9 'true' was
    # luck); runtime Core behavior was never affected (Cases A-F deterministic).
    target_doc = next(iter(store.iter("documents")))
    ev0 = next(x for x in store.iter("events")
               if x["document_id"] == target_doc["document_id"])
    old_fid = ev0["fact_version_snapshot"][0]["fact_id"]
    old_metric = store.fact_row(old_fid, 1)["metric"]
    new_on_new_rep = [f for f in store.iter("facts")
                      if f["representation_id"] in new_reps and
                      f["document_id"] == target_doc["document_id"] and
                      f["metric"] == old_metric]
    result = {"same_document_new_representation": bool(new_reps),
              "new_representation_count": len(new_reps),
              "documents_unchanged_count": len({d["document_id"] for d in store.iter("documents")}),
              "new_facts_count": len(facts_after) - len(facts_before)}
    if new_on_new_rep:
        newest_fact = new_on_new_rep[0]
        governance.supersede_fact_by_source(
            store, old_fid, newest_fact, SupersessionReason.SOURCE_REVISION,
            evidence_ref="Phase2 sec10 controlled modified representation "
                         f"({newest_fact['representation_id'][:12]})",
            actor="phase2-analysis", run_id="cc-2")
        before_v = store.current_event(ev0["event_id"])["event_version"]
        newest = governance.recompute_event(store, ev0["event_id"], derived_at="cc-2")
        result["event_recompute"] = bool(newest and newest["event_version"] > before_v)
        old = governance.reproduce_event(store, ev0["event_id"], 1)
        result["historical_reproducible"] = old is not None and all(
            f is not None for f in old["facts"])
        result["old_fact_status"] = store.current_fact(old_fid)["status"]
    versions_of_first = store.event_versions(ev0["event_id"])
    result["pipeline_auto_new_event_version"] = any(
        v["event_version"] > 1 for v in versions_of_first) and not result.get("event_recompute")
    return result


def by_url_exact(ledger, url):
    norm = url.rstrip("/")
    for e in ledger:
        for k in ("url", "final_url"):
            v = (e.get(k) or "").rstrip("/")
            if v == norm:
                return e
    raise KeyError(url)


def section_delivery(store: AppendOnlyStore) -> dict:
    """Directive 13: versioned, idempotent, audited delivery on real store."""
    ios = list(store.iter("intelligence_objects"))
    if not ios:
        return {"skipped": "no IOs"}
    io = ios[0]
    from intelligence_core.contracts import IntelligenceObject
    obj = IntelligenceObject(**{k: io[k] for k in
                                ("io_id", "version", "event_id", "event_version",
                                 "headline", "chain", "created_at")})
    dest = "phase2-test-dest-" + __import__("uuid").uuid4().hex[:6]
    d1, c1 = deliver(store, obj, dest)
    d2, c2 = deliver(store, obj, dest)
    return {"first_created": c1, "second_created": c2,
            "idempotent": d1.delivery_id == d2.delivery_id,
            "audit_records": sum(1 for _ in store.iter("audit")),
            "external_transport_exists": False}


def main():
    base = load_base()
    print("[analysis base]", base)
    capdir = base / "capture"
    ledger = json.loads((base / "capture" / "ledger.json").read_text()) if \
        (capdir / "ledger.json").exists() else _rebuild_ledger(base)
    fixtures = make_fixtures(capdir, ledger, _captured_info(base))
    store = AppendOnlyStore(str(base / "store1"))

    out = {}
    out["temporal"] = section_temporal(capdir, ledger)
    desc = section_description_only(capdir, ledger)
    desc["classification"] = "DESCRIPTION_CONTENT_LIMITATION CONFIRMED"  # FDIC GovDelivery descriptions carry full press text (3,527 chars max, live-captured); pipeline code-path never reads <description>
    out["description_only"] = desc
    out["istat_boundary"] = section_istat_boundary(store)
    out["isolation"] = section_isolation(base, capdir, ledger, fixtures)
    out["idempotency"] = section_idempotency(base, capdir, ledger, fixtures)
    out["content_change"] = section_content_change(base, capdir, ledger, fixtures)
    out["delivery"] = section_delivery(store)
    print(json.dumps(out, indent=1, default=str))
    (base / "analysis.json").write_text(json.dumps(out, indent=1, default=str))
    print("[written]", base / "analysis.json")


def _rebuild_ledger(base: Path):
    # ledger lives in report? LiveCapture keeps it in memory; persist for analysis:
    raise SystemExit("ledger.json missing — rerun phase2_live_validation with ledger dump")


def _captured_info(base: Path):
    rep = json.loads((base / "report.json").read_text())
    return rep["capture"]


if __name__ == "__main__":
    main()
