"""PHASE 2 LIVE VALIDATION HARNESS v2 — Minimum Core @ 9af81b7.

Design: single LIVE capture pass (real network), then bounded DETERMINISTIC
executions from the capture cache. Discovered core limitations are RECORDED,
never remediated here (directive 19/21).
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Institution, Source
from intelligence_core.entity_resolution import InstitutionRegistry, EntityResolutionError
from intelligence_core.config import SourceConfig
from intelligence_core.pipeline import run_source, run_many
from intelligence_core.acquisition import Transport, parse_rss_items, find_html_links
from intelligence_core.normalize import strip_html
from intelligence_core.extract import extract_facts
from intelligence_core.temporal import parse_rfc822_pubdate, parse_iso_or_date, ordering_filter
from intelligence_core.delivery import build_intelligence_object, deliver
from intelligence_core import governance
from intelligence_core.detect import EVENT_TYPE_RULES

FDIC = Institution("INST-fdic-001", "Federal Deposit Insurance Corporation", "US",
                   "deposit_insurer",
                   [{"domain": "www.fdic.gov", "verification_evidence": "fdic.gov/about — US government agency"}])
ISTAT = Institution("INST-istat-001", "Istituto Nazionale di Statistica", "IT",
                    "statistics_authority",
                    [{"domain": "www.istat.it", "verification_evidence": "istat.it institutional footer"}])
DFSA = Institution("INST-dfsa-001", "Dubai Financial Services Authority", "AE",
                   "financial_regulator",
                   [{"domain": "www.dfsa.ae", "verification_evidence": "dfsa.ae about — DIFC regulator (Q2)"}])
MINISTRY = Institution("INST-bundesministerium-der-finanzen-001",
                       "Bundesministerium der Finanzen", "DE", "finance_ministry",
                       [{"domain": "bundesfinanzministerium.de",
                         "verification_evidence": "imprint — Post-Q3 f6c5a8b"}])
OBR = Institution("INST-obr-001", "Office for Budget Responsibility", "GB", "fiscal_watchdog",
                  [{"domain": "obr.uk", "verification_evidence": "obr.uk about — official statistics producer (Q2 S7)"}])
DGT = Institution("INST-dg-tresor-001", "Direction générale du Trésor", "FR",
                  "treasury_directorate",
                  [{"domain": "www.tresor.economie.gouv.fr",
                    "verification_evidence": "institutional footer"}])
BMF_COMPANY = Institution("INST-buerener-maschinenfabrik-001",
                          "Bürener Maschinenfabrik GmbH", "DE", "corporate_industrial",
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

SOURCES = {
    "FDIC": dict(inst=FDIC, url="https://public.govdelivery.com/topics/USFDIC_26/feed.rss",
                 fmt="rss", n=3, patterns=[
                     (r"Consent\s+Order\s+against\s+([A-Z][A-Za-z0-9\s,&\.\-]{3,80}?)(?:[,\n\.])", "defendant_name")],
                 event_type="regulatory_enforcement"),
    "ISTAT": dict(inst=ISTAT, url="https://www.istat.it/en/feed/", fmt="rss", n=3,
                  patterns=EUROSTAT_PATTERNS, event_type="statistical_release"),
    "DFSA": dict(inst=DFSA, url="https://www.dfsa.ae/rss", fmt="rss", n=2, patterns=[
        (r"(?:fine|penalty)\s+of\s+(?:AED\s+)?([\d,]+(?:\.\d+)?)\s*(?:million)?", "penalty_amount")],
        event_type="regulatory_enforcement"),
    "MINISTRY": dict(inst=MINISTRY,
                     url="https://www.bundesfinanzministerium.de/Web/EN/Home/home.html",
                     fmt="html_index", n=2, link_pattern=r"Pressemitteilungen",
                     base_override="https://www.bundesfinanzministerium.de/",
                     patterns=[], event_type="statistical_release"),
    "OBR": dict(inst=OBR, url="https://obr.uk/feed/", fmt="rss", n=3,
                patterns=EUROSTAT_PATTERNS, event_type="statistical_release"),
    "DGT": dict(inst=DGT, url="https://www.tresor.economie.gouv.fr/", fmt="html_index", n=2,
                link_pattern=r"/Articles/202[56]/", patterns=[], event_type="statistical_release"),
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LiveCapture:
    """Pass 1: real network; saves bodies + ledger."""
    def __init__(self, capdir: Path):
        self.dir = capdir; self.dir.mkdir(parents=True, exist_ok=True)
        self.ledger = []
        self.t = Transport()

    def fetch(self, url: str) -> bytes | None:
        try:
            status, final_url, data, ctype = self.t.get(url, timeout=30)
        except Exception as e:
            self.ledger.append({"url": url, "error": str(e)[:200], "at": now()})
            return None
        name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".bin"
        (self.dir / name).write_bytes(data)
        self.ledger.append({"url": url, "final_url": final_url, "status": status,
                            "size": len(data), "content_type": ctype, "file": name,
                            "sha256": hashlib.sha256(data).hexdigest(), "at": now()})
        return data


class CachedTransport:
    """Serves captured bodies by exact requested URL; fixtures override source URLs.

    FIXTURE PREPROCESSING (documented Phase-2 limitation L-REL / bounded-run
    discipline): (a) RSS bodies truncated to the first-n captured <item> blocks;
    (b) html_index list bodies replaced by a synthetic page whose hrefs are the
    captured links ABSOLUTIZED against the site base — the Core itself does not
    resolve relative html_index links (recorded as implementation limitation).
    """
    def __init__(self, capdir: Path, ledger: list, fixtures: dict):
        self.map = {e["url"]: (self._read(capdir, e), e) for e in ledger if "file" in e}
        self.fixtures = fixtures

    @staticmethod
    def _read(capdir, e):
        return (capdir / e["file"]).read_bytes()

    def get(self, url, timeout=30):
        if url in self.fixtures:
            ctype = "application/xml" if ".rss" in url or "/feed" in url else "text/html"
            return 200, url, self.fixtures[url], ctype
        for u, (body, e) in self.map.items():
            if u == url:
                return e["status"], e["final_url"], body, e["content_type"]
        for u, (body, e) in self.map.items():
            if e["final_url"] == url:
                return e["status"], e["final_url"], body, e["content_type"]
        raise RuntimeError(f"not in capture: {url}")


def capture_sources(cap: LiveCapture) -> dict:
    """Live-capture feeds/lists + first-n item pages. Returns per-source info."""
    out = {}
    for code, s in SOURCES.items():
        info = {"url": s["url"], "items": [], "feed_error": None}
        body = cap.fetch(s["url"])
        if body is None:
            info["feed_error"] = next((e.get("error") for e in cap.ledger
                                       if e["url"] == s["url"]), "unknown")
            out[code] = info
            continue
        text = body.decode("utf-8", errors="replace")
        if s["fmt"] == "rss":
            items = parse_rss_items(text)[: s["n"]]
            norm = [{"link": i["link"], "pubDate": i.get("pubDate", ""),
                     "guid": i.get("guid", ""), "title": i.get("title", "")} for i in items]
        else:
            # HARNESS FIXTURE PREPROCESSING (documented limitation L-REL):
            # absolutize relative hrefs against site base (base-tag / root),
            # because the Core does not resolve html_index relative links.
            base = s.get("base_override", s["url"])
            raw = find_html_links(text, s["link_pattern"], s["url"])
            links = [urljoin(base, h) for h in raw][: s["n"]]
            norm = [{"link": l, "pubDate": "", "guid": "", "title": ""} for l in links]
        for it in norm:
            page = cap.fetch(it["link"])
            it["captured"] = page is not None
        info["items"] = norm
        out[code] = info
    return out


def cfg_for(code: str, s: dict) -> SourceConfig:
    return SourceConfig(code=code, name=code, institution_id=s["inst"].institution_id,
                        source_path=s["url"], feed_format=s["fmt"],
                        link_pattern=s.get("link_pattern", ""), patterns=s["patterns"],
                        event_type=s["event_type"])


def register_sources(store: AppendOnlyStore, registry_):
    """LIMITATION L-SRC workaround (documented): pipeline does not auto-register
    Source rows; registration is an explicit pre-run step using Core contracts."""
    for code, s in SOURCES.items():
        store.append("sources", Source(source_id=code, institution_id=s["inst"].institution_id,
                                        source_path=s["url"], source_type="official",
                                        acquisition_method="direct_http").to_dict())


def counts(store) -> dict:
    return {c: sum(1 for _ in store.iter(c)) for c in
            ("sources", "documents", "representations", "retrieval_events", "facts",
             "events", "evidence", "intelligence_objects", "deliveries", "audit")}


def lineage(store) -> dict:
    return {"facts": sorted(r["fact_id"] for r in store.iter("facts")),
            "events": sorted((r["event_id"], r["event_version"]) for r in store.iter("events")),
            "ios": sorted(r["io_id"] for r in store.iter("intelligence_objects")),
            "reps": sorted(r["representation_id"] for r in store.iter("representations")),
            "deliveries": sorted(r["idempotency_key"] for r in store.iter("deliveries"))}


def verify_traceability(store) -> dict:
    reps = store.latest_by_id("representations", "representation_id")
    docs = store.latest_by_id("documents", "document_id")
    srcs = store.latest_by_id("sources", "source_id")
    insts = {i["institution_id"] for i in store.iter("institutions")} or None
    broken, checked = [], 0
    reg = build_registry()
    for io in store.iter("intelligence_objects"):
        for link in io["chain"]:
            checked += 1
            rid = link["representation"]["representation_id"]
            rep = reps.get(rid)
            if rep is None:
                broken.append(f"{io['io_id']}: rep {rid} missing"); continue
            blob = Path(store.root) / "blobs" / rep["content_sha256"]
            if not blob.exists():
                broken.append(f"{io['io_id']}: blob missing {rep['content_sha256'][:12]}")
            elif hashlib.sha256(blob.read_bytes()).hexdigest() != rep["content_sha256"]:
                broken.append(f"{io['io_id']}: blob hash mismatch")
            if link["document"]["document_id"] not in docs:
                broken.append(f"{io['io_id']}: document missing")
            sid = link["source"]["source_id"]
            if sid not in srcs:
                broken.append(f"{io['io_id']}: source missing")
            else:
                row = srcs[sid]
                if row["institution_id"] not in {i.institution_id for i in
                                                 [FDIC, ISTAT, DFSA, MINISTRY, OBR, DGT]}:
                    broken.append(f"{io['io_id']}: institution unverified")
    return {"links_checked": checked, "broken": broken}


def build_registry() -> InstitutionRegistry:
    r = InstitutionRegistry()
    for i in (FDIC, ISTAT, DFSA, MINISTRY, OBR, DGT, BMF_COMPANY):
        r.add_institution(i)
    return r


def entity_gate() -> dict:
    r = build_registry()
    pos = {}
    for code, s in SOURCES.items():
        inst = r.resolve(s["url"])
        pos[code] = {"resolved": inst.institution_id if inst else None,
                     "match": bool(inst and inst.institution_id == s["inst"].institution_id)}
    neg = {}
    try:
        r.assert_association("bmf.de", MINISTRY.institution_id)
        neg["bmf_de_to_ministry"] = "ACCEPTED (REGRESSION FAILURE)"
    except EntityResolutionError:
        neg["bmf_de_to_ministry"] = "REJECTED (correct)"
    try:
        r.resolve_by_brand("BMF")
        neg["brand_lookup"] = "ALLOWED (REGRESSION FAILURE)"
    except EntityResolutionError:
        neg["brand_lookup"] = "FORBIDDEN (correct)"
    try:
        r.assert_association("bmf.de", "INST-buerener-maschinenfabrik-001")
        neg["bmf_de_to_company"] = "ACCEPTED (correct)"
    except EntityResolutionError:
        neg["bmf_de_to_company"] = "REJECTED (WRONG)"
    return {"positive": pos, "negative": neg}


def make_fixtures(capdir: Path, ledger: list, captured: dict) -> dict:
    """Bounded-run fixtures from REAL captured bodies (see CachedTransport doc)."""
    by_url = {e["url"]: e for e in ledger if "file" in e}
    fixtures = {}
    for code, info in captured.items():
        s = SOURCES[code]
        e = by_url.get(s["url"])
        if not e:
            continue
        body = (capdir / e["file"]).read_bytes()
        text = body.decode("utf-8", errors="replace")
        if s["fmt"] == "rss":
            items = re.findall(r"<item>.*?</item>", text, re.S)[: s["n"]]
            head = text.split("<item>")[0]
            fixtures[s["url"]] = (head + "".join(items) + "</channel></rss>").encode("utf-8")
        else:
            # L-REL live proof: fixture carries the RAW relative hrefs from the real
            # body; the Core pipeline resolves them (resolve_index_link) itself.
            raw = find_html_links(text, s["link_pattern"], s["url"])[: s["n"]]
            page = "<html><body>" + "".join(
                f'<a href="{h}">doc</a>' for h in raw) + "</body></html>"
            fixtures[s["url"]] = page.encode("utf-8")
    return fixtures


def execute_suite(store_dir: str, capdir: Path, ledger: list, fixtures: dict,
                  run_id="phase2-run") -> dict:
    store = AppendOnlyStore(store_dir)
    # L-SRC fixed: the Core pipeline persists Source rows itself (ensure_source);
    # explicit harness registration removed.
    t = CachedTransport(capdir, ledger, fixtures)
    reg = build_registry()
    results = {}
    for code, s in SOURCES.items():
        cfg = cfg_for(code, s)
        r = run_source(store, reg, cfg, transport=t, run_id=run_id)
        results[code] = {k: v for k, v in r.items() if k != "results"}
    return {"sources": results, "counts": counts(store),
            "lineage": lineage(store), "traceability": verify_traceability(store),
            "store_dir": store_dir}


def main():
    base = Path(tempfile.mkdtemp(prefix="p2v2_"))
    print(f"[phase2-v2] base={base}")
    report = {"base": str(base)}

    report["entity_gate"] = entity_gate()
    print("[entity]", json.dumps(report["entity_gate"]["negative"]))

    cap = LiveCapture(base / "capture")
    captured = capture_sources(cap)
    (base / "capture" / "ledger.json").write_text(json.dumps(cap.ledger, indent=1))
    report["capture"] = {c: {"feed_error": v["feed_error"],
                             "items": [{"link": i["link"], "captured": i["captured"]}
                                       for i in v["items"]]} for c, v in captured.items()}
    for c, v in report["capture"].items():
        print(f"[capture] {c}: feed_error={v['feed_error']} items={len(v['items'])}")

    fixtures = make_fixtures(base / "capture", cap.ledger, captured)
    s1 = execute_suite(str(base / "store1"), base / "capture", cap.ledger, fixtures)
    s2 = execute_suite(str(base / "store2"), base / "capture", cap.ledger, fixtures)
    report["suite1"] = {k: s1[k] for k in ("sources", "counts", "traceability")}
    report["determinism_identical"] = s1["lineage"] == s2["lineage"]
    print("[counts]", json.dumps(s1["counts"]))
    print("[sources]", json.dumps(s1["sources"], indent=1))
    print("[traceability]", json.dumps(s1["traceability"]))
    print("[determinism]", report["determinism_identical"])

    (base / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print("[report]", base / "report.json")


if __name__ == "__main__":
    main()
