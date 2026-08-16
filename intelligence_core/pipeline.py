"""Minimum Core orchestrator — failure isolation per source (directive §11: one source
failure never terminates others). Every step implements an approved D-decision."""
from __future__ import annotations
from .contracts import Document, Representation, Evidence, TemporalTuple
from .identity import evidence_id as make_evidence_id
from .acquisition import DirectHttpAdapter, parse_rss_items, find_html_links
from .normalize import strip_html
from .extract import extract_facts
from .detect import detect_event
from .delivery import build_intelligence_object, deliver
from .health import SourceHealth
from .temporal import parse_rfc822_pubdate, parse_iso_or_date


def ensure_source(store, cfg, institution) -> None:
    """L-SRC fix: the Core pipeline persists the resolved Source itself (D6/Core
    boundary). Idempotent: same source_id + same institution -> no duplicate row.
    Called ONLY after entity resolution succeeded (failed resolution -> no row)."""
    from .contracts import Source
    existing = store.latest_by_id("sources", "source_id").get(cfg.code)
    if existing is not None:
        if existing["institution_id"] != cfg.institution_id:
            raise RuntimeError(
                f"source '{cfg.code}' already registered to "
                f"{existing['institution_id']}, refusing rebind to "
                f"{cfg.institution_id} (D6; supersede explicitly)")
        return
    store.append("sources", Source(
        source_id=cfg.code, institution_id=cfg.institution_id,
        source_path=cfg.source_path, source_type="official",
        acquisition_method="direct_http",
        configuration_version=cfg.configuration_version).to_dict())


def _record_representation(store, fetch: dict, source_id: str) -> None:
    """D1: append-only; identical content re-fetch reuses the same representation id."""
    if fetch["representation_id"] not in store.latest_by_id("representations", "representation_id"):
        store.append("representations", Representation(
            representation_id=fetch["representation_id"],
            document_id=fetch["document_id"], content_sha256=fetch["content_sha256"],
            retrieved_at="", retrieval_event_id=fetch["retrieval_event"].retrieval_event_id,
            content_type=fetch.get("content_type", ""),
            raw_location=store.write_blob(fetch["content_sha256"], fetch["bytes"])).to_dict())
    store.append("retrieval_events", fetch["retrieval_event"].to_dict())


def _upsert_document(store, fetch: dict, source_id: str, tuples: list) -> None:
    if fetch["document_id"] not in store.latest_by_id("documents", "document_id"):
        store.append("documents", Document(
            document_id=fetch["document_id"], canonical_url=fetch["canonical_url"],
            aliases=fetch["aliases"], source_id=source_id,
            publication_tuples=[t.to_dict() for t in tuples]).to_dict())


def _process_item(store, adapter, cfg, item, source_id, run_id) -> dict:
    """One feed item -> document + representation + facts + event + IO."""
    url = item["link"]
    fetch = adapter.fetch(url, run_id=run_id)
    tuples = []
    if item.get("pubDate"):
        t = parse_rfc822_pubdate(item["pubDate"])
        tuples.append(t)
    if item.get("date_iso"):  # html-extracted iso date (configurable extraction not needed in min core)
        tuples.append(parse_iso_or_date(item["date_iso"],
                                        provenance=item.get("date_provenance", "html_time_attr")))
    _upsert_document(store, fetch, source_id, tuples)
    _record_representation(store, fetch, source_id)
    text = strip_html(fetch["bytes"].decode("utf-8", errors="replace"))
    if cfg.content_keywords:
        low = text.lower()
        if not any(k.lower() in low for k in cfg.content_keywords):
            return {"skipped": True, "document_id": fetch["document_id"]}
    facts = extract_facts(text, cfg.patterns, fetch["representation_id"],
                          fetch["document_id"])
    new_facts = []
    for f in facts:
        cur = store.current_fact(f.fact_id)
        if cur is None:
            store.append("facts", f.to_dict())
            store.append("evidence", Evidence(
                evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                event_or_fact_id=f.fact_id, representation_id=f.representation_id,
                location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                excerpt=f.excerpt,
                provenance_ref=f"representation:{f.representation_id}").to_dict())
            new_facts.append(f)
        else:
            new_facts.append(f)  # idempotent re-run: existing ACTIVE fact reused
    ev = detect_event(new_facts, fetch["document_id"], cfg.event_type)
    if ev is None:
        return {"document_id": fetch["document_id"], "facts": len(new_facts), "events": 0}
    existing = store.current_event(ev.event_id)
    if existing is None:
        store.append("events", ev.to_dict())
        existing = store.current_event(ev.event_id)
    io = build_intelligence_object(store, existing, source_name=cfg.name)
    if io.io_id not in store.latest_by_id("intelligence_objects", "io_id"):
        store.append("intelligence_objects", io.to_dict())
    deliver(store, io, destination=f"product:{cfg.code}")
    return {"document_id": fetch["document_id"], "facts": len(new_facts),
            "events": 1, "io_id": io.io_id}


def run_source(store, registry, cfg, transport=None, run_id: str = "run") -> dict:
    """One source end-to-end. NEVER raises: failures land in source-level states (isolation)."""
    health = SourceHealth(store, cfg.code)
    adapter = DirectHttpAdapter(transport)
    try:
        inst = registry.resolve(cfg.source_path)
        if inst is None:
            raise RuntimeError(
                f"source path host not entity-verified — REJECTED (D6; bmf.de precedent)")
        if inst.institution_id != cfg.institution_id:
            raise RuntimeError(f"entity mismatch: config binds {cfg.institution_id}, "
                               f"domain verified to {inst.institution_id}")
        ensure_source(store, cfg, inst)
        fetch = adapter.fetch(cfg.source_path, run_id=run_id)
        health.transition("ACCESSIBLE")
        xml_text = fetch["bytes"].decode("utf-8", errors="replace")
        results = []
        if cfg.feed_format == "rss":
            items = parse_rss_items(xml_text)
        else:
            from .acquisition import resolve_index_link
            links = find_html_links(xml_text, cfg.link_pattern, cfg.source_path)
            # L-REL fix: absolutize against the index page before Document fetch
            items = [{"link": resolve_index_link(l, cfg.source_path),
                      "title": "", "guid": "", "pubDate": ""} for l in links]
        for item in items:
            if not item.get("link"):
                continue
            r = _process_item(store, adapter, cfg, item, cfg.code, run_id)
            results.append(r)
        health.transition("DOCUMENTED")
        any_event = any(r.get("events") for r in results)
        if any_event:
            health.transition("EXTRACTED")
            health.transition("PUBLISHABLE")
        return {"source": cfg.code, "state": health.state, "items": len(results),
                "results": results}
    except Exception as e:  # source-scoped failure only (directive §11)
        health.transition("BLOCKED", reason=str(e)[:300])
        store.audit("SOURCE_FAILURE", {"source": cfg.code, "error": str(e)[:300]})
        return {"source": cfg.code, "state": health.state, "error": str(e)[:300]}


def run_many(store, registry, configs, transport=None, run_id: str = "run") -> list:
    return [run_source(store, registry, c, transport, run_id) for c in configs]
