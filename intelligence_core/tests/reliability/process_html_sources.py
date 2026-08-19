"""V2-Expansion §18b — Process HTML-qualified sources by extracting document links.

HTML sources don't have RSS feeds, but they have list pages with links to
press releases, news, and publications. This script:
  1. Fetches the HTML listing page
  2. Extracts links to documents (press releases, news articles)
  3. Fetches each document
  4. Extracts facts, detects events, builds IOs
"""
from __future__ import annotations
import json
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlsplit

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.acquisition import DirectHttpAdapter, Transport
from intelligence_core.contracts import (
    Institution, Evidence, Source, Document, Representation, RetrievalEvent,
)
from intelligence_core.cached_store import CachedStore
from intelligence_core.store import AppendOnlyStore
from intelligence_core.detect import detect_event
from intelligence_core.delivery import build_intelligence_object
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.extract import extract_facts
from intelligence_core.identity import (
    evidence_id as make_evidence_id,
    document_id as make_doc_id,
    representation_id as make_rep_id,
    retrieval_event_id as make_retrieval_id,
    content_sha256,
)
from intelligence_core.normalize import strip_html
from intelligence_core.source_network.registry import SourceRegistry
from intelligence_core.tests.reliability.topup_expanded_patterns import EXPANDED_PATTERNS
from intelligence_core.tests.reliability.process_new_sources import (
    CLASS_TO_PATTERN, ORIGINAL_SOURCES, SOURCE_ID_MAP,
    _WRITE_LOCK, safe_append, safe_latest_by_id, safe_current_fact, safe_current_event,
)


# Patterns for finding news/press release links in HTML
NEWS_LINK_PATTERNS = [
    r'href=["\']([^"\']*(?:press|news|release|announcement|publication)[^"\']*)["\']',
    r'href=["\']([^"\']*(?:comunicato|press-release|news-release)[^"\']*)["\']',
]


def extract_document_links(html: str, base_url: str) -> list:
    """Extract document links from an HTML listing page."""
    links = set()
    for pattern in NEWS_LINK_PATTERNS:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = match.group(1)
            # Make absolute
            if url.startswith("/"):
                url = urljoin(base_url, url)
            elif not url.startswith("http"):
                url = urljoin(base_url, url)
            # Filter out non-document URLs
            if any(ext in url.lower() for ext in [".pdf", ".jpg", ".png", ".css", ".js", ".ico"]):
                continue
            if any(skip in url.lower() for skip in ["mailto:", "tel:", "#", "javascript:"]):
                continue
            links.add(url)
    return list(links)[:20]  # cap at 20


def process_html_source(store, registry, src_record, run_id, max_docs=10):
    """Process an HTML source: fetch listing, extract links, fetch documents."""
    if src_record.source_id in SOURCE_ID_MAP and SOURCE_ID_MAP[src_record.source_id] in ORIGINAL_SOURCES:
        return {"source_id": src_record.source_id, "skipped": "original_source",
                "intelligence_objects": []}

    website = src_record.canonical_url
    source_id = src_record.source_id
    source_name = src_record.institution_name

    result = {
        "source_id": source_id, "name": source_name,
        "country": src_record.country, "class": src_record.source_class,
        "acquisition_method": "HTML",
        "documents_acquired": 0, "documents_processed": 0,
        "facts_extracted": 0, "events_detected": 0,
        "intelligence_objects": [], "errors": [],
        "failure_stage": None, "failure_reason": None,
    }

    try:
        # Resolve/create institution
        inst = registry.resolve(website)
        if inst is None:
            parts = urlsplit(website)
            domain = parts.hostname or ""
            if domain.startswith("www."):
                domain = domain[4:]
            inst_id = src_record.institution_id
            inst = Institution(
                institution_id=inst_id, legal_entity=source_name,
                jurisdiction=src_record.country, institutional_class=src_record.source_class,
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                registry.add_institution(inst)
            except Exception:
                pass

        transport = Transport()
        original_get = transport.get
        def fast_get(url, timeout=8):
            return original_get(url, timeout=timeout)
        transport.get = fast_get
        adapter = DirectHttpAdapter(transport=transport)

        # Fetch the listing page
        try:
            listing_fetch = adapter.fetch(website, run_id=run_id)
        except Exception as e:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = f"fetch_failed: {str(e)[:60]}"
            return result

        if listing_fetch["retrieval_event"].http_status != 200:
            result["failure_stage"] = "ACQUISITION"
            result["failure_reason"] = f"http_{listing_fetch['retrieval_event'].http_status}"
            return result

        listing_html = listing_fetch["bytes"].decode("utf-8", errors="replace")
        result["acquisition"] = {
            "http_status": 200,
            "bytes": len(listing_fetch["bytes"]),
            "feed_url": website,
        }

        # Extract document links
        doc_urls = extract_document_links(listing_html, website)
        result["documents_acquired"] = len(doc_urls)
        if not doc_urls:
            result["failure_stage"] = "DOCUMENT"
            result["failure_reason"] = "no_document_links_found"
            return result

        # Register source
        existing_sources = safe_latest_by_id(store, "sources", "source_id")
        if source_id not in existing_sources:
            safe_append(store, "sources", Source(
                source_id=source_id, institution_id=inst.institution_id,
                source_path=website, source_type="official",
                acquisition_method="direct_http", status="ACTIVE",
            ).to_dict())

        # Get expanded patterns for this source class
        event_type, pattern_key = CLASS_TO_PATTERN.get(
            src_record.source_class, ("statistical_release", "statistical"))
        patterns = EXPANDED_PATTERNS.get(pattern_key, EXPANDED_PATTERNS["statistical"])

        # Process each document
        for doc_url in doc_urls[:max_docs]:
            try:
                # Fetch document
                doc_fetch = adapter.fetch(doc_url, run_id=run_id)
                if doc_fetch["retrieval_event"].http_status != 200:
                    continue

                doc_id = doc_fetch["document_id"]
                rep_id = doc_fetch["representation_id"]
                content_sha = doc_fetch["content_sha256"]

                # Register document (idempotent)
                existing_docs = safe_latest_by_id(store, "documents", "document_id")
                if doc_id not in existing_docs:
                    safe_append(store, "documents", Document(
                        document_id=doc_id, canonical_url=doc_fetch["canonical_url"],
                        aliases=[], source_id=source_id,
                        publication_tuples=[],  # HTML docs may not have pubdate
                        created_at="", status="ACTIVE",
                    ).to_dict())

                # Register representation (idempotent)
                existing_reps = safe_latest_by_id(store, "representations", "representation_id")
                if rep_id not in existing_reps:
                    safe_append(store, "representations", Representation(
                        representation_id=rep_id, document_id=doc_id,
                        content_sha256=content_sha, retrieved_at="",
                        retrieval_event_id=doc_fetch["retrieval_event"].retrieval_event_id,
                        content_type=doc_fetch.get("content_type", ""),
                        raw_location=str(store.root / "blobs" / content_sha),
                    ).to_dict())
                    # Write blob
                    store.write_blob(content_sha, doc_fetch["bytes"])
                    # Register retrieval event
                    safe_append(store, "retrieval_events", doc_fetch["retrieval_event"].to_dict())

                result["documents_processed"] += 1

                # Extract facts
                text = strip_html(doc_fetch["bytes"].decode("utf-8", errors="replace"))
                facts = extract_facts(text, patterns, rep_id, doc_id)
                if not facts:
                    continue
                result["facts_extracted"] += len(facts)

                # Append facts + evidence (idempotent)
                for f in facts:
                    cur = safe_current_fact(store, f.fact_id)
                    if cur is None:
                        safe_append(store, "facts", f.to_dict())
                        safe_append(store, "evidence", Evidence(
                            evidence_id=make_evidence_id(f.fact_id, f.fact_version),
                            event_or_fact_id=f.fact_id,
                            representation_id=f.representation_id,
                            location=f"pattern:{f.pattern_ref}#occ{f.occurrence}",
                            excerpt=f.excerpt,
                            provenance_ref=f"representation:{f.representation_id}",
                        ).to_dict())

                # Detect event (idempotent)
                ev = detect_event(facts, doc_id, event_type)
                if ev is None:
                    continue
                existing_ev = safe_current_event(store, ev.event_id)
                if existing_ev is None:
                    safe_append(store, "events", ev.to_dict())
                    existing_ev = safe_current_event(store, ev.event_id)
                    result["events_detected"] += 1

                # Build IO
                with _WRITE_LOCK:
                    io = build_intelligence_object(store, existing_ev, source_name=source_id)
                result["intelligence_objects"].append(io.io_id)

            except Exception as e:
                result["errors"].append({"stage": "DOC", "message": str(e)[:80]})
                continue

    except Exception as e:
        result["errors"].append({"stage": "PIPELINE", "message": str(e)[:200]})
        if not result["failure_stage"]:
            result["failure_stage"] = "PIPELINE"
            result["failure_reason"] = str(e)[:100]
    return result


def run_html_sources_processing(store_root: str = "real_corpus_store_new",
                                  registry_root: str = "source_registry",
                                  max_workers: int = 6):
    """Process HTML-qualified sources."""
    print(f"\n{'='*70}")
    print(f"V2-Expansion §18b — Process HTML-qualified sources through Core")
    print(f"{'='*70}")

    store = CachedStore(AppendOnlyStore(store_root))
    existing_events = sum(1 for _ in store.iter("events"))
    print(f"  Starting events: {existing_events}")

    src_registry = SourceRegistry(registry_root)
    # Get HTML + ATOM sources that are QUALIFIED or PRODUCTION_READY
    html_sources = [
        r for r in src_registry.all()
        if r.qualification_status in ("QUALIFIED", "PRODUCTION_READY")
        and r.acquisition_method in ("HTML", "ATOM")
    ]
    # Filter to NEW sources only
    new_html = []
    for r in html_sources:
        original_id = SOURCE_ID_MAP.get(r.source_id)
        if original_id and original_id in ORIGINAL_SOURCES:
            continue
        new_html.append(r)
    print(f"  NEW HTML/ATOM sources to process: {len(new_html)}")

    institution_registry = InstitutionRegistry()
    for r in src_registry.all():
        website = r.canonical_url
        parts = urlsplit(website)
        domain = parts.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            inst = Institution(
                institution_id=r.institution_id, legal_entity=r.institution_name,
                jurisdiction=r.country, institutional_class=r.source_class,
                verified_domains=[{"domain": domain, "verification_evidence": "official_source_domain"}],
                status="ACTIVE",
            )
            try:
                institution_registry.add_institution(inst)
            except Exception:
                pass

    run_id = f"html-sources-{int(time.time())}"
    t_start = time.perf_counter()

    results = [None] * len(new_html)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_html_source, store, institution_registry, r, run_id): i
            for i, r in enumerate(new_html)
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                result = future.result(timeout=60)
                results[i] = result
                n_ios = len(result.get("intelligence_objects", []))
                src_id = result["source_id"]
                docs = result.get("documents_processed", 0)
                facts = result.get("facts_extracted", 0)
                err = result.get("failure_reason") or "-"
                print(f"  [{i+1:2d}/{len(new_html)}] {src_id:<30} docs={docs:2d} facts={facts:3d} ios={n_ios:3d} err={err}")
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {str(e)[:80]}")
                results[i] = {"source_id": new_html[i].source_id,
                              "intelligence_objects": [],
                              "failure_reason": str(e)[:100]}

    elapsed = time.perf_counter() - t_start
    total_new_ios = sum(len(r.get("intelligence_objects", [])) for r in results if r)
    final_events = sum(1 for _ in store.iter("events"))
    new_events_count = final_events - existing_events

    print(f"\n--- Results ---")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Sources processed: {len([r for r in results if r and not r.get('skipped')])}")
    print(f"  New IOs produced: {total_new_ios}")
    print(f"  Final total events: {final_events}")
    print(f"  New events added: {new_events_count}")

    # Save results
    out = {
        "schema_version": "1.0",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store_root": store_root,
        "starting_events": existing_events,
        "final_events": final_events,
        "new_events": new_events_count,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    out_path = Path("intelligence_core/tests/reliability/html_sources_processing_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return final_events, new_events_count


if __name__ == "__main__":
    final, new = run_html_sources_processing()
    if new >= 25:
        print(f"\n  ✓ PASS: {new} new real IOs (≥25 target)")
    else:
        print(f"\n  ⚠ {new} new real IOs (< 25 target)")
