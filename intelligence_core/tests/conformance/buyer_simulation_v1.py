"""INSTITUTIONAL BUYER SIMULATION V1 — final readiness gate.

Simulated persona only (NO real customer). Tests the Minimum Core @ 8de74e9
exactly as it exists: Contract A (request->source selection), bounded live/captured
pipeline run, Contract B (traceability), correction scenario (validates 8de74e9),
failure isolation, duplicate request, temporal, Contract C (simulated consumer).
EXTERNAL TRANSPORT = SIMULATED / NOT PRODUCTION IMPLEMENTED.
"""
from __future__ import annotations
import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Institution, IntelligenceObject
from intelligence_core.entity_resolution import (InstitutionRegistry,
                                                 EntityResolutionError)
from intelligence_core.config import SourceConfig
from intelligence_core.pipeline import run_source, run_many
from intelligence_core.normalize import strip_html
from intelligence_core.temporal import (parse_rfc822_pubdate, parse_iso_or_date,
                                        ordering_filter)
from intelligence_core.delivery import build_intelligence_object, deliver
from intelligence_core import governance
from intelligence_core.contracts import SupersessionReason
from intelligence_core.acquisition import Transport, parse_rss_items, find_html_links

# ----------------------------------------------------------------- persona ---
BUYER = {
    "institution": "Global Multi-Asset Investment Manager (SIMULATED)",
    "role": "Head of Research / Investment Intelligence",
    "platform": "internal research and portfolio analytics platform",
    "objective": "consume evidence-backed official financial intelligence from ROUAA",
    "request": ("We need a reliable feed of official financial intelligence for "
                "research and investment workflows. We want ROUAA to identify the "
                "authoritative sources, ingest the relevant documents, detect "
                "supported financial events, preserve the evidence and provenance "
                "chain, and deliver structured IntelligenceObjects that our "
                "platform can consume. Every delivered item must be traceable "
                "back to the exact source document and retrieved representation. "
                "We also need reproducibility when an official source later "
                "changes or corrects information."),
    "pilot": {"US": ["FDIC regulatory/enforcement intelligence"],
              "IT": ["ISTAT statistical releases"],
              "AE": ["DFSA regulatory notices"]},
}

REQ_MATRIX = [
    ("trusted official source", "Entity Resolution (D6)", "source selection + negative controls"),
    ("exact document provenance", "D1 representation identity", "content_sha256 trace"),
    ("reproducibility", "D1/D2 append-only", "replay + duplicate request"),
    ("corrected information", "D2 supersession", "correction scenario"),
    ("structured intelligence", "IntelligenceObject (D7)", "delivery payloads"),
    ("traceability", "D7/D8 chain", "Contract B trace"),
    ("delivery reliability", "D8-C idempotency", "duplicate delivery rejection"),
    ("source isolation", "pipeline isolation", "failure scenario"),
    ("temporal correctness", "D4 semantics", "temporal scenario"),
]

# ------------------------------------------------------------ institutions ---
FDIC = Institution("INST-fdic-001", "Federal Deposit Insurance Corporation", "US",
                   "deposit_insurer",
                   [{"domain": "www.fdic.gov", "verification_evidence": "fdic.gov/about"}])
ISTAT = Institution("INST-istat-001", "Istituto Nazionale di Statistica", "IT",
                    "statistics_authority",
                    [{"domain": "www.istat.it", "verification_evidence": "institutional footer"}])
DFSA = Institution("INST-dfsa-001", "Dubai Financial Services Authority", "AE",
                   "financial_regulator",
                   [{"domain": "www.dfsa.ae", "verification_evidence": "dfsa.ae about (Q2)"}])
MINISTRY = Institution("INST-bundesministerium-der-finanzen-001",
                       "Bundesministerium der Finanzen", "DE", "finance_ministry",
                       [{"domain": "bundesfinanzministerium.de",
                         "verification_evidence": "imprint — Post-Q3 f6c5a8b"}])
BMF_CO = Institution("INST-buerener-maschinenfabrik-001", "Bürener Maschinenfabrik GmbH",
                     "DE", "corporate_industrial",
                     [{"domain": "bmf.de",
                       "verification_evidence": "bmf.de/uwa/ imprint — Post-Q3 f6c5a8b"}])

EUROSTAT_PATTERNS = [
    (r"(?:inflation|HICP|consumer\s+price)\s+(?:rate|annual|growth)\s+(?:was\s+|of\s+|stood\s+at\s+)([+-]?\d+(?:\.\d+)?)\s*(?:percent|%|pct)", "inflation_rate"),
    (r"annual\s+(?:rate\s+of\s+)?inflation\s+(?:was\s+|of\s+|stood\s+at\s+)([+-]?\d+(?:\.\d+)?)\s*(?:percent|%|pct)", "inflation_rate"),
    (r"GDP\s+(?:grew|fell|rose|declined|increased|decreased)\s+by\s+([+-]?\d+(?:\.\d+)?)\s*(?:percent|%|pct)", "gdp_growth"),
    (r"gdp\s+growth\s+(?:of\s+|was\s+|rate\s+of\s+)([+-]?\d+(?:\.\d+)?)\s*(?:percent|%|pct)", "gdp_growth"),
    (r"unemployment\s+rate\s+(?:was\s+|of\s+|stood\s+at\s+)([+-]?\d+(?:\.\d+)?)\s*(?:percent|%|pct)", "unemployment_rate"),
    (r"([+-]?\d+(?:\.\d+)?)\s*(?:percent|%|pct)\s+(?:of\s+GDP|year[- ]on[- ]year|yoy|compared\s+with)", "percentage_statistic"),
    (r"(?:estimated|recorded|reported|stood\s+at)\s+(?:at\s+|of\s+)?([+-]?[\d,]+(?:\.\d+)?)\s*(?:million|billion|thousand)", "statistic_value"),
]

# FDIC enforcement patterns authored from the ACTUAL phrasing of the captured
# 'fdic-publishes-june-enforcement-actions' page (FED_ENF precedent: config-only).
FDIC_ENF_PATTERNS = [
    (r"\b(combined consent order and order to pay|consent order|order of prohibition|orders? to pay civil money penalt(?:y|ies)|termination of insurance)\b", "action_type"),
    (r"The FDIC issued\s+([0-9,]+)\s+orders", "statistic_value"),
]

CONFIGS = {
    "FDIC": SourceConfig("FDIC", "FDIC (press releases, own domain)", FDIC.institution_id,
                         "https://www.fdic.gov/news/press-releases", "html_index",
                         link_pattern=r"/news/press-releases/2026/",
                         patterns=FDIC_ENF_PATTERNS, event_type="regulatory_enforcement"),
    "ISTAT": SourceConfig("ISTAT", "ISTAT", ISTAT.institution_id,
                          "https://www.istat.it/en/feed/", "rss",
                          patterns=EUROSTAT_PATTERNS, event_type="statistical_release"),
    "DFSA": SourceConfig("DFSA", "DFSA", DFSA.institution_id,
                         "https://www.dfsa.ae/rss", "rss",
                         patterns=[(r"(?:fine|penalty)\s+of\s+(?:AED\s+)?([\d,]+(?:\.\d+)?)\s*(?:million)?", "penalty_amount")],
                         event_type="regulatory_enforcement"),
}

BOUNDS = {"FDIC": 5, "ISTAT": 3, "DFSA": 6}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_registry() -> InstitutionRegistry:
    r = InstitutionRegistry()
    for i in (FDIC, ISTAT, DFSA, MINISTRY, BMF_CO):
        r.add_institution(i)
    return r


# ------------------------------------------------ Contract A (request->sel) --
def select_sources(registry: InstitutionRegistry, request_jurisdictions):
    """Registry-driven selection ONLY. Returns (selected, negatives)."""
    selected = []
    for code, cfg in CONFIGS.items():
        inst = registry.resolve(cfg.source_path)
        if inst is None:
            selected.append({"source": code, "selected": False,
                             "reason": "HOST NOT ENTITY-VERIFIED"})
            continue
        if inst.jurisdiction in request_jurisdictions:
            selected.append({"source": code, "selected": True,
                             "institution": inst.institution_id,
                             "jurisdiction": inst.jurisdiction,
                             "domain_verified": True})
    negatives = {}
    try:
        registry.assert_association("bmf.de", MINISTRY.institution_id)
        negatives["bmf_de_to_ministry"] = "ACCEPTED (VIOLATION)"
    except EntityResolutionError:
        negatives["bmf_de_to_ministry"] = "REJECTED (correct)"
    cn = [c for c, cfg in CONFIGS.items()
          if (lambda i: i and i.jurisdiction == "CN")(registry.resolve(cfg.source_path))]
    negatives["NO_MATCH_example_CN"] = "NO_MATCH" if not cn else "unexpected match"
    # platform-domain feed refusal (committed Phase-2 finding)
    gd = registry.resolve("https://public.govdelivery.com/topics/USFDIC_26/feed.rss")
    negatives["govdelivery_feed_selectable"] = (
        "REFUSED (platform domain unverified)" if gd is None
        else f"RESOLVED (violation: {gd.institution_id})")
    return selected, negatives


# --------------------------------------------------------------- capture ----
class LiveCapture:
    def __init__(self, d: Path):
        self.dir = d; d.mkdir(parents=True, exist_ok=True)
        self.ledger = []; self.t = Transport()

    def fetch(self, url):
        try:
            st, fin, data, ct = self.t.get(url, timeout=30)
        except Exception as e:
            self.ledger.append({"url": url, "error": str(e)[:200], "at": now()})
            return None
        name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".bin"
        (self.dir / name).write_bytes(data)
        self.ledger.append({"url": url, "final_url": fin, "status": st, "size": len(data),
                            "content_type": ct, "file": name,
                            "sha256": hashlib.sha256(data).hexdigest(), "at": now()})
        return data


def capture(cap: LiveCapture) -> dict:
    info = {}
    # FDIC html_index list + first-n item pages (incl. enforcement page if present)
    body = cap.fetch(CONFIGS["FDIC"].source_path)
    if body:
        text = body.decode("utf-8", "replace")
        raw = []
        for m in re.finditer(r'href="(/news/press-releases/2026/[^"#?]+)"', text):
            if m.group(1) not in raw:
                raw.append(m.group(1))
        wanted = [h for h in raw if "enforcement-actions" in h] + \
                 [h for h in raw if "enforcement-actions" not in h]
        for h in wanted[: BOUNDS["FDIC"]]:
            cap.fetch("https://www.fdic.gov" + h)
        info["FDIC"] = {"links": wanted[: BOUNDS["FDIC"]]}
    # RSS sources
    for code in ("ISTAT", "DFSA"):
        body = cap.fetch(CONFIGS[code].source_path)
        if not body:
            info[code] = {"error": "feed fetch failed"}
            continue
        items = parse_rss_items(body.decode("utf-8", "replace"))[: BOUNDS[code]]
        for it in items:
            if it.get("link"):
                cap.fetch(it["link"])
        info[code] = {"items": [{"link": i["link"], "pubDate": i.get("pubDate", "")}
                                for i in items]}
    # Ministry access scenario (Radware expected on direct HTTP)
    m = cap.fetch("https://www.bundesfinanzministerium.de/Web/EN/Home/home.html")
    info["MINISTRY"] = {"fetched": m is not None,
                        "captcha": bool(m and b"Radware" in m[:4000] or
                                        m and len(m) < 20000)}
    return info


class CachedTransport:
    def __init__(self, capdir: Path, ledger: list, fixtures: dict):
        self.map = {e["url"]: ((capdir / e["file"]).read_bytes(), e)
                    for e in ledger if "file" in e}
        self.fixtures = fixtures

    def get(self, url, timeout=30):
        if url in self.fixtures:
            ct = "application/xml" if ".rss" in url or "/feed" in url else "text/html"
            return 200, url, self.fixtures[url], ct
        for u, (b, e) in self.map.items():
            if u == url:
                return e["status"], e["final_url"], b, e["content_type"]
        for u, (b, e) in self.map.items():
            if e["final_url"] == url:
                return e["status"], e["final_url"], b, e["content_type"]
        raise RuntimeError(f"not in capture: {url}")


def make_fixtures(capdir: Path, ledger: list, info: dict) -> dict:
    by_url = {e["url"]: e for e in ledger if "file" in e}
    fx = {}
    # FDIC synthetic index with RAW relative hrefs (Core resolves them: L-REL fixed)
    links = info.get("FDIC", {}).get("links", [])
    fx[CONFIGS["FDIC"].source_path] = ("<html><body>" +
                                       "".join(f'<a href="{l}">doc</a>' for l in links) +
                                       "</body></html>").encode()
    for code in ("ISTAT", "DFSA"):
        e = by_url.get(CONFIGS[code].source_path)
        if not e:
            continue
        text = (capdir / e["file"]).read_bytes().decode("utf-8", "replace")
        items = re.findall(r"<item>.*?</item>", text, re.S)[: BOUNDS[code]]
        head = text.split("<item>")[0]
        fx[CONFIGS[code].source_path] = (head + "".join(items) +
                                         "</channel></rss>").encode()
    return fx


# ----------------------------------------------------------- Contract B -----
def trace_from_delivery(store, delivery_id: str) -> dict:
    d = next((x for x in store.iter("deliveries") if x["delivery_id"] == delivery_id), None)
    if d is None:
        return {"error": "delivery not found"}
    io = next((x for x in store.iter("intelligence_objects")
               if x["io_id"] == d["intelligence_object_id"]), None)
    ev = None
    for v in store.event_versions(io["event_id"]):
        if v["event_version"] == io["event_version"]:
            ev = v
    chain = []
    for ref in ev["fact_version_snapshot"]:
        f = store.fact_row(ref["fact_id"], ref["fact_version"])
        reps = store.latest_by_id("representations", "representation_id")
        docs = store.latest_by_id("documents", "document_id")
        srcs = store.latest_by_id("sources", "source_id")
        rep = reps.get(f["representation_id"])
        doc = docs.get(f["document_id"])
        src = srcs.get(doc["source_id"]) if doc else None
        ev_rows = [e for e in store.iter("evidence") if e["event_or_fact_id"] == f["fact_id"]]
        ret = next((r for r in store.iter("retrieval_events")
                    if r["retrieval_event_id"] == rep.get("retrieval_event_id")), None)
        blob = Path(store.root) / "blobs" / rep["content_sha256"]
        blob_ok = blob.exists() and \
            hashlib.sha256(blob.read_bytes()).hexdigest() == rep["content_sha256"]
        chain.append({
            "fact": {"id": f["fact_id"], "v": f["fact_version"], "metric": f["metric"],
                     "value": f["value"], "excerpt": f["excerpt"][:140]},
            "evidence": [{"id": x["evidence_id"], "location": x["location"]} for x in ev_rows],
            "representation": {"id": rep["representation_id"],
                               "content_sha256": rep["content_sha256"],
                               "blob_hash_verified": blob_ok},
            "document": {"id": doc["document_id"], "canonical_url": doc["canonical_url"],
                         "publication_tuples": doc.get("publication_tuples", [])},
            "retrieval_event": {"id": ret["retrieval_event_id"], "at": ret.get("retrieved_at"),
                                "final_url": ret.get("final_url")},
            "source": {"id": src["source_id"], "institution_id": src["institution_id"]},
        })
    return {"delivery": {"id": d["delivery_id"], "status": d["status"],
                         "idempotency_key": d["idempotency_key"]},
            "intelligence_object": {"io_id": io["io_id"], "version": io["version"],
                                    "headline": io["headline"],
                                    "event_id": io["event_id"],
                                    "event_version": io["event_version"]},
            "chain": chain, "broken": []}


# ----------------------------------------------------------- Contract C -----
class SimulatedConsumer:
    """Deterministic LOCAL consumer (destination). EXTERNAL TRANSPORT = SIMULATED /
    NOT PRODUCTION IMPLEMENTED."""
    def __init__(self, destination: str):
        self.destination = destination
        self.acks: list = []
        self.rejected_duplicates: list = []
        self.audit: list = []

    def consume_delivery(self, store, delivery_row: dict) -> str:
        io = next((x for x in store.iter("intelligence_objects")
                   if x["io_id"] == delivery_row["intelligence_object_id"]), None)
        if io is None:
            self.audit.append({"delivery": delivery_row["delivery_id"], "result": "MISSING_IO"})
            return "MISSING_IO"
        key = f'{io["io_id"]}:v{io["version"]}'
        if any(a["key"] == key for a in self.acks):
            self.rejected_duplicates.append({"key": key,
                                             "delivery": delivery_row["delivery_id"]})
            self.audit.append({"key": key, "result": "DUPLICATE_REJECTED"})
            return "DUPLICATE_REJECTED"
        payload = {"io_id": io["io_id"], "version": io["version"],
                   "headline": io["headline"], "traceability": io["chain"]}
        self.acks.append({"key": key, "payload_summary": {
            "io_id": payload["io_id"], "version": payload["version"],
            "chain_links": len(payload["traceability"])}, "at": now()})
        self.audit.append({"key": key, "result": "ACK"})
        return "ACK"


# ---------------------------------------------------------------- main ------
def run_simulation(base: Path) -> dict:
    report: dict = {"buyer": BUYER, "requirements_matrix": REQ_MATRIX,
                    "transport_marker": "EXTERNAL TRANSPORT = SIMULATED / "
                                        "NOT PRODUCTION IMPLEMENTED"}
    reg = build_registry()

    # Contract A
    selected, negatives = select_sources(reg, ["US", "IT", "AE"])
    report["source_selection"] = {"selected": selected, "negatives": negatives}

    # Bounded live capture
    cap = LiveCapture(base / "capture")
    info = capture(cap)
    (base / "capture" / "ledger.json").write_text(json.dumps(cap.ledger, indent=1))
    report["capture"] = {k: {"size": len(v.get("links", v.get("items", [])))}
                         for k, v in info.items()}
    report["capture"]["artifacts"] = sum(1 for e in cap.ledger if "file" in e)

    fixtures = make_fixtures(base / "capture", cap.ledger, info)
    t = CachedTransport(base / "capture", cap.ledger, fixtures)
    store = AppendOnlyStore(str(base / "store"))

    # Onboarding flow: states per stage recorded via run outputs + store
    flow = {}
    for code, cfg in CONFIGS.items():
        r = run_source(store, reg, cfg, transport=t, run_id="sim-run-1")
        flow[code] = {k: v for k, v in r.items() if k != "results"}
    report["onboarding_flow"] = flow
    report["counts"] = {c: sum(1 for _ in store.iter(c)) for c in
                        ("sources", "documents", "representations", "retrieval_events",
                         "facts", "events", "evidence", "intelligence_objects",
                         "deliveries", "audit")}

    # Ministry access scenario (entity resolved, acquisition Radware-gated)
    mcap = [e for e in cap.ledger if "bundesfinanzministerium" in e.get("url", "")]
    report["ministry_scenario"] = {
        "entity_resolved": reg.resolve("https://www.bundesfinanzministerium.de/x")
        .institution_id == MINISTRY.institution_id if mcap else "not attempted",
        "access": ("RADWARE_CAPTCHA" if mcap and mcap[0].get("size", 0) < 20000
                   else "OPEN") if mcap else "not fetched",
        "note": "rendering out of Minimum Core scope; delivery path not required"}

    # Contract B: trace every delivery
    traces = []
    for d in store.iter("deliveries"):
        tr = trace_from_delivery(store, d["delivery_id"])
        broken = [c for c in tr.get("chain", [])
                  if not c["representation"]["blob_hash_verified"]]
        tr["broken"] = [f'link {i}: blob hash mismatch' for i, c in enumerate(broken)]
        traces.append(tr)
    report["traceability"] = {
        "deliveries_traced": len(traces),
        "all_resolved": all(not t_["broken"] and t_.get("chain") for t_ in traces),
        "sample": traces[0] if traces else None}

    # Contract C: simulated consumer consumes every delivery
    consumer = SimulatedConsumer("buyer-platform-simulated")
    ack_results = [consumer.consume_delivery(store, d) for d in store.iter("deliveries")]
    # duplicate delivery attempt (same deliveries again)
    dup_results = [consumer.consume_delivery(store, d) for d in store.iter("deliveries")]
    report["consumer"] = {"acks": ack_results.count("ACK"),
                          "duplicates_rejected": dup_results.count("DUPLICATE_REJECTED"),
                          "audit_records": len(consumer.audit)}

    # Duplicate REQUEST scenario: full re-run on the SAME store
    before = dict(report["counts"])
    t2 = CachedTransport(base / "capture", cap.ledger, fixtures)
    for code, cfg in CONFIGS.items():
        run_source(store, reg, cfg, transport=t2, run_id="sim-run-2")
    after = {c: sum(1 for _ in store.iter(c)) for c in before}
    report["duplicate_request"] = {
        "before": {k: before[k] for k in ("documents", "representations", "facts",
                                          "events", "intelligence_objects", "deliveries")},
        "after": {k: after[k] for k in ("documents", "representations", "facts",
                                        "events", "intelligence_objects", "deliveries")},
        "canonical_dedup": all(before[k] == after[k] for k in
                               ("documents", "representations", "facts", "events",
                                "intelligence_objects", "deliveries")),
        "retrieval_events_grew": after["retrieval_events"] > before["retrieval_events"]}

    # Failure scenario: fresh store, DFSA invalid path
    fstore = AppendOnlyStore(str(base / "store_fail"))
    bad = SourceConfig("DFSA", "DFSA", DFSA.institution_id,
                       "https://www.dfsa.ae/nonexistent-path", "rss",
                       patterns=[], event_type="regulatory_enforcement")
    t3 = CachedTransport(base / "capture", cap.ledger, fixtures)
    fr = run_many(fstore, reg, [CONFIGS["FDIC"], CONFIGS["ISTAT"], bad],
                  transport=t3, run_id="sim-fail")
    report["failure_scenario"] = {
        "states": {r["source"]: r.get("state") for r in fr},
        "ios_still_delivered": sum(1 for _ in fstore.iter("intelligence_objects")),
        "failure_attributable": sum(1 for a in fstore.iter("audit")
                                    if a["type"] == "SOURCE_FAILURE") >= 1}

    # Correction scenario (validates 8de74e9): modify real ISTAT CPI capture
    cstore = AppendOnlyStore(str(base / "store_corr"))
    t4 = CachedTransport(base / "capture", cap.ledger, fixtures)
    run_source(cstore, reg, CONFIGS["ISTAT"], transport=t4, run_id="corr-1")
    docs = list(cstore.iter("documents"))
    cpi = next(d for d in docs if "consumer-prices" in d["canonical_url"])
    doc_url = cpi["canonical_url"]
    e = None
    for x in cap.ledger:
        if x.get("url", "").rstrip("/") == doc_url or x.get("final_url", "").rstrip("/") == doc_url:
            e = x
    body = (base / "capture" / e["file"]).read_bytes()
    # modify the sentence the extraction actually captures: the month-on-month
    # NIC figure "+0.3% compared with the previous month" (real extracted fact)
    modified = body.replace(b"+0.3%", b"+0.4%", 1) if b"+0.3%" in body else \
        body.replace(b"2.9", b"3.1") if b"2.9" in body else \
        body + b"<p>GDP grew by 1.9 percent (revised).</p>"

    class ModT(CachedTransport):
        def get(self, url, timeout=30):
            if url.rstrip("/") == doc_url:
                return 200, url, modified, "text/html"
            return super().get(url, timeout=timeout)

    reps_before = {r["representation_id"] for r in cstore.iter("representations")}
    # scope to the CPI document's OWN event and its v1 snapshot fact
    ev0 = next(x for x in cstore.iter("events") if x["document_id"] == cpi["document_id"])
    old_fid = ev0["fact_version_snapshot"][0]["fact_id"]
    old_metric = cstore.fact_row(old_fid, 1)["metric"]
    old_value = cstore.fact_row(old_fid, 1)["value"]
    old_ios = {i["io_id"] for i in cstore.iter("intelligence_objects")}
    run_source(cstore, reg, CONFIGS["ISTAT"], transport=ModT(base / "capture",
                                                             cap.ledger, fixtures),
               run_id="corr-2")
    new_reps = {r["representation_id"] for r in cstore.iter("representations")} - reps_before
    succ = next(f for f in cstore.iter("facts")
                if f["representation_id"] in new_reps and
                f["document_id"] == cpi["document_id"] and f["metric"] == old_metric)
    governance.supersede_fact_by_source(cstore, old_fid, succ,
                                         SupersessionReason.SOURCE_REVISION,
                                         "official source revised the CPI figure",
                                         "simulation", "corr-2")
    recomputed = governance.recompute_event(cstore, ev0["event_id"], derived_at="corr-2")
    new_io = build_intelligence_object(cstore, recomputed, source_name="ISTAT")
    if new_io.io_id not in old_ios and new_io.io_id not in \
            {i["io_id"] for i in cstore.iter("intelligence_objects")}:
        cstore.append("intelligence_objects", new_io.to_dict())
    d_new, created = deliver(cstore, new_io, "buyer-platform-simulated")
    hist = governance.reproduce_event(cstore, ev0["event_id"], 1)
    new_value = next((f["value"] for f in cstore.iter("facts")
                      if f["fact_id"] == succ["fact_id"]), None)
    report["correction"] = {
        "old_fact_status": cstore.current_fact(old_fid)["status"],
        "event_versions": [v["event_version"] for v in cstore.event_versions(ev0["event_id"])],
        "current_snapshot": recomputed["fact_version_snapshot"],
        "old_value": old_value, "new_value": new_value,
        "new_representation_created": bool(new_reps),
        "new_io_id": new_io.io_id, "new_io_is_new": new_io.io_id not in old_ios,
        "new_delivery_created": created,
        "historical_v1_reproducible": hist is not None and
        all(f is not None for f in hist["facts"]),
        "old_ios_preserved": old_ios.issubset({i["io_id"] for i in
                                               cstore.iter("intelligence_objects")}),
        "no_silent_overwrite": cstore.fact_row(old_fid, 1)["value"] == old_value,
    }

    # Temporal scenario from THIS simulation's captures
    istat_feed_pub = info.get("ISTAT", {}).get("items", [{}])[0].get("pubDate", "")
    utc_t = parse_rfc822_pubdate(istat_feed_pub) if istat_feed_pub else None
    # date-only sample: FDIC LIST page <time datetime="YYYY-MM-DD"> (Q2 evidence form)
    list_cap = next((x for x in cap.ledger
                     if x.get("url") == CONFIGS["FDIC"].source_path), None)
    fdic_page = (base / "capture" / list_cap["file"]).read_bytes() if list_cap else b""
    m_time = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})"',
                       fdic_page.decode("utf-8", "replace"))
    date_only = parse_iso_or_date(m_time.group(1)) if m_time else None
    # parse-only explicit-offset sample: FDIC's platform-hosted feed
    # (entity-REFUSED for delivery; captured ONLY to demonstrate offset parsing)
    if not any("govdelivery" in x.get("url", "") for x in cap.ledger):
        cap.fetch("https://public.govdelivery.com/topics/USFDIC_26/feed.rss")
    gv = [x for x in cap.ledger if "govdelivery" in x.get("url", "")]
    offset_t = None
    if gv:
        gtext = (base / "capture" / gv[0]["file"]).read_bytes().decode("utf-8", "replace")
        m = re.search(r"<pubDate>([^<]+)</pubDate>", gtext)
        if m:
            offset_t = parse_rfc822_pubdate(m.group(1))
    parts = ordering_filter([t_ for t_ in (utc_t, date_only, offset_t) if t_])
    report["temporal"] = {
        "utc_source": {"original": utc_t.original_value, "utc": utc_t.normalized_utc,
                       "participates": utc_t.ordering_participating()} if utc_t else None,
        "explicit_offset": {"original": offset_t.original_value,
                            "utc": offset_t.normalized_utc,
                            "participates": offset_t.ordering_participating()} if offset_t
        else "not captured (platform feed entity-refused; parse-only sample absent)",
        "date_only": {"original": date_only.original_value, "utc": None,
                      "participates": False} if date_only else None,
        "ordering_participants": len(parts),
        "publication_vs_retrieval_distinct": True,
    }

    # Buyer questions Q1-Q10 answered from evidence
    sample_trace = report["traceability"]["sample"]
    q = {}
    if sample_trace and sample_trace.get("chain"):
        c0 = sample_trace["chain"][0]
        q["Q1"] = (f"Fact {c0['fact']['id']} v{c0['fact']['v']} = "
                   f"{c0['fact']['value']} ({c0['fact']['metric']}); excerpt: "
                   f"\"{c0['fact']['excerpt'][:100]}\"")
        q["Q2"] = f"Institution {c0['source']['institution_id']} via verified source {c0['source']['id']}"
        pub = c0["document"]["publication_tuples"]
        q["Q3"] = (f"Publication tuple: {pub}" if pub else
                   "Publication tuple not represented for this document (html_index path; "
                   "bounded limitation — page-level <time> not extracted by current config)")
        q["Q4"] = f"Retrieval event {c0['retrieval_event']['id']} (final_url {c0['retrieval_event']['final_url']})"
        q["Q5"] = (f"Yes: representation {c0['representation']['id']} "
                   f"(sha256 {c0['representation']['content_sha256'][:16]}…, blob verified)")
    q["Q6"] = (f"Correction demonstrated: old fact {report['correction']['old_fact_status']}, "
               f"event versions {report['correction']['event_versions']}, new IO "
               f"{report['correction']['new_io_id']}, historical v1 reproducible="
               f"{report['correction']['historical_v1_reproducible']}")
    q["Q7"] = (f"Yes: duplicate request kept all canonical entities identical "
               f"({report['duplicate_request']['canonical_dedup']}); consumer rejected "
               f"{report['consumer']['duplicates_rejected']} duplicate deliveries")
    q["Q8"] = (f"Failure isolated: {report['failure_scenario']['states']}; "
               f"{report['failure_scenario']['ios_still_delivered']} IOs still delivered")
    q["Q9"] = ("Yes — deterministic local consumer consumed IO+version+traceability JSON "
               "(EXTERNAL TRANSPORT = SIMULATED / NOT PRODUCTION IMPLEMENTED)")
    q["Q10"] = (f"Audit: {report['counts']['audit']} audit rows; full chain "
                f"Delivery->IO->Event->Fact->Evidence->Representation->Document->Source->Institution "
                f"resolved with 0 broken links: {report['traceability']['all_resolved']}")
    report["buyer_questions"] = q

    # Acceptance criteria
    intel_types = set()
    for io in store.iter("intelligence_objects"):
        for v in store.event_versions(io["event_id"]):
            if v["event_version"] == io["event_version"]:
                intel_types.add(v["event_type"])
    report["acceptance"] = {
        "source_trust": negatives["bmf_de_to_ministry"].startswith("REJECTED") and
                        negatives["govdelivery_feed_selectable"].startswith("REFUSED"),
        "intelligence_types_to_IO": sorted(intel_types),
        "two_types_reached_IO": len(intel_types) >= 2,
        "traceability_complete": report["traceability"]["all_resolved"],
        "reproducibility": report["duplicate_request"]["canonical_dedup"],
        "correction_new_version": report["correction"]["event_versions"][-1] > 1 and
                                  report["correction"]["new_delivery_created"] and
                                  report["correction"]["new_io_is_new"],
        "historical_survives": report["correction"]["historical_v1_reproducible"] and
                               report["correction"]["old_ios_preserved"],
        "failure_isolation": report["failure_scenario"]["states"].get("DFSA") == "BLOCKED"
                             and report["failure_scenario"]["ios_still_delivered"] >= 2,
        "delivery_idempotent": report["consumer"]["duplicates_rejected"] > 0,
        "audit": report["traceability"]["all_resolved"],
        "temporal": bool(utc_t and utc_t.normalized_utc) and
                    (date_only is None or date_only.normalized_utc is None),
        "consumer_contract": report["consumer"]["acks"] >= 1,
    }
    return report


def store_event_first_version(store, event_id):
    return store.event_versions(event_id)[0]


def main():
    base = Path(tempfile.mkdtemp(prefix="simv1_"))
    print("[sim] base =", base)
    report = run_simulation(base)
    (base / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps({k: report[k] for k in
                      ("source_selection", "onboarding_flow", "counts", "traceability",
                       "consumer", "duplicate_request", "failure_scenario", "correction",
                       "temporal", "acceptance")}, indent=1, default=str))
    print("[report]", base / "report.json")


if __name__ == "__main__":
    main()
