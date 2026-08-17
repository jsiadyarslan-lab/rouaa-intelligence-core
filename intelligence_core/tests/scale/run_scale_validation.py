"""ROUAA Core Scale → Product Consumption Validation V1.

Runs the existing Core acquisition + extraction + delivery pipeline
against 50 qualified official sources from the existing source universe.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from intelligence_core.acquisition import DirectHttpAdapter, parse_rss_items
from intelligence_core.contracts import (
    Institution, Evidence, Source, Document, Representation,
)
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts
from intelligence_core.identity import evidence_id as make_evidence_id
from intelligence_core.normalize import strip_html
from intelligence_core.store import AppendOnlyStore
from intelligence_core.temporal import parse_rfc822_pubdate

RATE_PATTERNS = [
    (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", "rate_value"),
    (r"\b(maintain(?:ed)?|raise(?:d)?|cut|lower(?:ed)?)\s+(?:the\s+)?(?:key\s+|policy\s+|interest\s+)?rate", "rate_action"),
]
STATISTICAL_PATTERNS = [
    (r"(?:évolution\s+de|variation\s+de|hausse\s+de|baisse\s+de|augmentation\s+de)\s+([+-]?\d+(?:[.,]\d+)?)\s*%", "percentage_statistic"),
    (r"\b(\d+(?:[.,]\d+)?)\s*%", "percentage_statistic"),
]
ENFORCEMENT_PATTERNS = [
    (r"\b(consent\s+order|cease(?:-|\s+)and(?:-|\s+)desist|injunction|penalty|disgorgement|settlement|fine|charged|sued)\b", "action_type"),
    (r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:million|billion|thousand)?", "penalty_amount"),
]
MARKET_STAT_PATTERNS = [
    (r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\b", "percentage_statistic"),
]

EVENT_TYPE_BY_SOURCE_TYPE = {
    "central_bank": ("monetary_policy_decision", RATE_PATTERNS),
    "statistics": ("statistical_release", STATISTICAL_PATTERNS),
    "regulator": ("regulatory_enforcement", ENFORCEMENT_PATTERNS),
    "exchange": ("regulatory_enforcement", ENFORCEMENT_PATTERNS),
    "ministry": ("regulatory_enforcement", ENFORCEMENT_PATTERNS),
    "intl_org": ("statistical_release", STATISTICAL_PATTERNS),
    "energy": ("regulatory_enforcement", ENFORCEMENT_PATTERNS),
    "rating": ("regulatory_enforcement", ENFORCEMENT_PATTERNS),
    "commodity": ("market_statistic_release", MARKET_STAT_PATTERNS),
    "other": ("statistical_release", STATISTICAL_PATTERNS),
}

RSS_PATHS = [
    "/rss", "/rss/news.xml", "/news/rss", "/feed", "/rss/press.html",
    "/news/pressreleases.rss", "/xml/syndication.rss", "/rss/press-releases.xml",
    "/en/rss", "/feed.xml", "/atom.xml", "/rss.xml", "/newsroom/rss",
    "/press/rss", "/rss/news", "/news/feed", "/feeds/news", "/en/news/rss",
    "/newsroom/feed", "/rss/press-releases.rss", "/en/press/rss",
    "/rss.xml", "/news.xml", "/feed/news", "/en/feed",
    "/rss/press-releases", "/press-releases/rss", "/news/rss.xml",
    "/rss/press.html", "/en/rss/press.html",
]


def load_selected_sources():
    with open("/tmp/selected_sources.json") as f:
        return json.load(f)


def build_institution_registry(sources):
    reg = InstitutionRegistry()
    for i, s in enumerate(sources):
        website = s.get("website", "")
        if not website:
            continue
        parts = urlsplit(website)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain:
            continue
        inst_id = f"INST-{s.get('source_id', f'src-{i:03d}')}"
        inst = Institution(
            institution_id=inst_id, legal_entity=s.get("name", ""),
            jurisdiction=s.get("country_code", ""),
            institutional_class=s.get("class", ""),
            verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
            status="ACTIVE",
        )
        try:
            reg.add_institution(inst)
        except Exception:
            pass
    return reg


def try_acquire_rss(adapter, website):
    base_url = website.rstrip("/")
    for path in RSS_PATHS:
        url = base_url + path
        try:
            fetch = adapter.fetch(url, run_id="scale-val")
            if fetch["retrieval_event"].http_status == 200:
                body = fetch["bytes"].decode("utf-8", errors="replace")
                if "<?xml" in body[:200] or "<rss" in body[:200] or "<feed" in body[:200] or "<channel" in body[:500]:
                    return fetch
        except Exception:
            continue
    return None


def process_one_source(store, registry, adapter, src, run_id):
    website = src.get("website", "")
    source_id = src.get("source_id", src.get("name", "unknown"))
    source_name = src.get("name", source_id)
    source_type = src.get("type", "")
    result = {
        "source_id": source_id, "name": source_name, "class": src.get("class",""),
        "country": src.get("country",""), "website": website,
        "acquisition": None, "documents_acquired": 0, "documents_processed": 0,
        "documents_with_facts": 0, "facts_extracted": 0,
        "documents_with_events": 0, "events_detected": 0,
        "intelligence_objects": [], "errors": [],
        "failure_stage": None, "failure_reason": None,
    }
    try:
        inst = registry.resolve(website)
        if inst is None:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = "entity_not_resolved"
            return result
        event_type, patterns = EVENT_TYPE_BY_SOURCE_TYPE.get(source_type, ("statistical_release", STATISTICAL_PATTERNS))
        rss_fetch = try_acquire_rss(adapter, website)
        if rss_fetch is None:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = "no_rss_feed"
            return result
        result["acquisition"] = {"http_status": rss_fetch["retrieval_event"].http_status,
                                  "bytes": len(rss_fetch["bytes"]), "feed_url": rss_fetch["canonical_url"]}
        existing_sources = store.latest_by_id("sources", "source_id")
        if source_id not in existing_sources:
            store.append("sources", Source(
                source_id=source_id, institution_id=inst.institution_id,
                source_path=rss_fetch["canonical_url"], source_type="official",
                acquisition_method="direct_http", status="ACTIVE",
            ).to_dict())
        xml_text = rss_fetch["bytes"].decode("utf-8", errors="replace")
        items = parse_rss_items(xml_text)
        result["documents_acquired"] = len(items) if items else 0
        if not items:
            result["failure_stage"] = "DOCUMENT"
            result["failure_reason"] = "no_rss_items"
            return result
        max_items = min(3, len(items))
        for item in items[:max_items]:
            if not item.get("link"):
                continue
            doc_result = process_one_document(store, adapter, source_id, source_name,
                                               inst.institution_id, event_type, patterns, item, run_id)
            result["documents_processed"] += 1
            result["facts_extracted"] += doc_result.get("facts_count", 0)
            if doc_result.get("facts_count", 0) > 0:
                result["documents_with_facts"] += 1
            if doc_result.get("event"):
                result["documents_with_events"] += 1
                result["events_detected"] += 1
            if doc_result.get("io_id"):
                result["intelligence_objects"].append(doc_result["io_id"])
            if doc_result.get("error"):
                result["errors"].append(doc_result["error"])
    except Exception as e:
        result["errors"].append({"stage": "PIPELINE", "message": str(e)[:200]})
        if not result["failure_stage"]:
            result["failure_stage"] = "PIPELINE"
            result["failure_reason"] = str(e)[:100]
    return result


def process_one_document(store, adapter, source_id, source_name, inst_id,
                          event_type, patterns, item, run_id):
    url = item["link"]
    pubdate = item.get("pubDate", "")
    result = {"item_url": url, "item_title": item.get("title","")[:100],
              "facts_count": 0, "event": None, "io_id": None, "error": None}
    if url.lower().endswith(".pdf"):
        result["error"] = {"stage": "DOCUMENT", "message": "PDF skipped (D10)"}
        return result
    fetch = None
    for attempt in range(2):
        try:
            fetch = adapter.fetch(url, run_id=run_id)
            break
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
                continue
            result["error"] = {"stage": "DOCUMENT", "message": f"fetch failed: {str(e)[:100]}"}
            return result
    if fetch is None:
        result["error"] = {"stage": "DOCUMENT", "message": "fetch failed after retries"}
        return result
    if fetch["retrieval_event"].http_status != 200:
        result["error"] = {"stage": "DOCUMENT", "message": f"HTTP {fetch['retrieval_event'].http_status}"}
        return result
    try:
        tuples = []
        if pubdate:
            try:
                tuples.append(parse_rfc822_pubdate(pubdate))
            except Exception:
                pass
        doc_id = fetch["document_id"]
        existing_docs = store.latest_by_id("documents", "document_id")
        if doc_id not in existing_docs:
            store.append("documents", Document(
                document_id=doc_id, canonical_url=fetch["canonical_url"],
                aliases=fetch.get("aliases", []), source_id=source_id,
                publication_tuples=[t.to_dict() for t in tuples],
                created_at="", status="ACTIVE",
            ).to_dict())
        existing_reps = store.latest_by_id("representations", "representation_id")
        if fetch["representation_id"] not in existing_reps:
            store.append("representations", Representation(
                representation_id=fetch["representation_id"], document_id=doc_id,
                content_sha256=fetch["content_sha256"], retrieved_at="",
                retrieval_event_id=fetch["retrieval_event"].retrieval_event_id,
                content_type=fetch.get("content_type", ""),
                raw_location=store.write_blob(fetch["content_sha256"], fetch["bytes"]),
            ).to_dict())
        store.append("retrieval_events", fetch["retrieval_event"].to_dict())
        text = strip_html(fetch["bytes"].decode("utf-8", errors="replace"))
        facts = extract_facts(text, patterns, fetch["representation_id"], doc_id)
        result["facts_count"] = len(facts)
        new_facts = []
        for f in facts:
            cur = store.current_fact(f.fact_id)
            if cur is None:
                store.append("facts", f.to_dict())
                store.append("evidence", Evidence(
                    evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                    event_or_fact_id=f.fact_id, representation_id=f.representation_id,
                    location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                    excerpt=f.excerpt, provenance_ref=f"representation:{f.representation_id}",
                ).to_dict())
                new_facts.append(f)
            else:
                new_facts.append(f)
        ev = detect_event(new_facts, doc_id, event_type)
        if ev is None:
            return result
        existing = store.current_event(ev.event_id)
        if existing is None:
            store.append("events", ev.to_dict())
            existing = store.current_event(ev.event_id)
        io = build_intelligence_object(store, existing, source_name=source_name)
        result["event"] = {"event_id": ev.event_id, "event_type": ev.event_type}
        result["io_id"] = io.io_id
    except Exception as e:
        result["error"] = {"stage": "PROCESS", "message": str(e)[:200]}
    return result


def calculate_metrics(results):
    total = len(results)
    sources_with_ios = sum(1 for r in results if r["intelligence_objects"])
    sources_acquired = sum(1 for r in results if r.get("acquisition"))
    total_docs = sum(r["documents_processed"] for r in results)
    total_docs_facts = sum(r["documents_with_facts"] for r in results)
    total_facts = sum(r["facts_extracted"] for r in results)
    total_events = sum(r["events_detected"] for r in results)
    total_ios = sum(len(r["intelligence_objects"]) for r in results)
    by_class = defaultdict(lambda: {"attempted":0,"acquired":0,"docs":0,"facts":0,"events":0,"ios":0,"with_ios":0})
    for r in results:
        c = r["class"]; by_class[c]["attempted"] += 1
        if r.get("acquisition"): by_class[c]["acquired"] += 1
        by_class[c]["docs"] += r["documents_processed"]
        by_class[c]["facts"] += r["facts_extracted"]
        by_class[c]["events"] += r["events_detected"]
        by_class[c]["ios"] += len(r["intelligence_objects"])
        if r["intelligence_objects"]: by_class[c]["with_ios"] += 1
    failures = defaultdict(int)
    for r in results:
        if r["failure_stage"]: failures[r["failure_stage"]] += 1
    return {
        "sources_attempted": total, "sources_acquired": sources_acquired,
        "sources_with_ios": sources_with_ios,
        "total_documents_processed": total_docs,
        "total_documents_with_facts": total_docs_facts,
        "total_facts_extracted": total_facts,
        "total_events_detected": total_events,
        "total_intelligence_objects": total_ios,
        "source_intelligence_yield": f"{sources_with_ios}/{total}",
        "document_fact_yield": f"{total_docs_facts}/{total_docs}" if total_docs else "0/0",
        "event_yield": f"{total_events}/{total_docs_facts}" if total_docs_facts else "0/0",
        "io_yield": f"{total_ios}/{total_events}" if total_events else "0/0",
        "by_class": dict(by_class),
        "failures_by_stage": dict(failures),
    }


def run_scale_validation(store_root="scale_validation_store"):
    if Path(store_root).exists(): shutil.rmtree(store_root)
    store = AppendOnlyStore(store_root)
    sources = load_selected_sources()
    registry = build_institution_registry(sources)
    adapter = DirectHttpAdapter()
    run_id = f"scale-val-{int(time.time())}"
    results = []
    for src in sources:
        result = process_one_source(store, registry, adapter, src, run_id)
        results.append(result)
        time.sleep(0.3)
    metrics = calculate_metrics(results)
    return {
        "schema_version":"1.0","run_id":run_id,
        "captured_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "store_root":str(store_root),
        "sources_attempted":len(results),"results":results,"metrics":metrics,
    }


if __name__ == "__main__":
    store_root = sys.argv[1] if len(sys.argv) > 1 else "scale_validation_store"
    manifest = run_scale_validation(store_root)
    print(json.dumps(manifest, indent=2, default=str))
