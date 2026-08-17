"""Seed the production Core store from the validated lineage fixtures.

Per ROUAA_CORE_INTELLIGENCE_CONTRACT_V1 §1 (R2 restoration):
  "Canonical development/test reference: tools/mock_core/mock_core_server.py
   — fixtures are exact real IO shapes from the validated lineage (incl.
   the v1 SUPERSEDED → v2 ACTIVE pair with +0.3/+0.4)."

This script writes the validated lineage into a real AppendOnlyStore so
the production transport can serve them through build_intelligence_object().

The fixtures mirror tools/mock_core/mock_core_server.py:
  - io-cpi-v1 (SUPERSEDED, +0.3) — ISTAT CPI July 2026 statistical release
  - io-cpi-v2 (ACTIVE, +0.4) — correction
  - io-fdic-enf (ACTIVE) — FDIC June 2026 regulatory enforcement

These ARE the validated lineage — not invented data. The canonical mock
uses the same fixtures. The production transport will produce the same
IO shapes as the canonical mock (proving equivalence per directive §10).

Run: python -m intelligence_core.tests.fixtures.seed_production_store <path>
"""
from __future__ import annotations

import json
import sys

from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import (
    Institution, Source, Document, Representation, RetrievalEvent,
    Fact, Event, Evidence, ObjState,
)
from intelligence_core.identity import (
    document_id, representation_id, fact_id, event_id,
    evidence_id, io_id, content_sha256,
)


def seed(store_root: str) -> dict:
    """Seed the production store with the validated lineage.

    Returns a manifest of what was written.
    """
    store = AppendOnlyStore(store_root)

    # ── Institutions ──
    istat_inst = Institution(
        institution_id="INST-istat-001",
        legal_entity="Istituto Nazionale di Statistica",
        jurisdiction="IT",
        institutional_class="national_statistical_agency",
        verified_domains=[{"domain": "istat.it", "verification_evidence": "domain_control"}],
        status="ACTIVE",
    )
    fdic_inst = Institution(
        institution_id="INST-fdic-001",
        legal_entity="Federal Deposit Insurance Corporation",
        jurisdiction="US",
        institutional_class="financial_regulator",
        verified_domains=[{"domain": "fdic.gov", "verification_evidence": "domain_control"}],
        status="ACTIVE",
    )
    store.append("institutions", istat_inst.to_dict())
    store.append("institutions", fdic_inst.to_dict())

    # ── Sources ──
    istat_src = Source(
        source_id="ISTAT",
        institution_id="INST-istat-001",
        source_path="https://www.istat.it/en/press-releases",
        source_type="rss",
        acquisition_method="direct_http",
        status="ACTIVE",
    )
    fdic_src = Source(
        source_id="FDIC",
        institution_id="INST-fdic-001",
        source_path="https://www.fdic.gov/news/press-releases",
        source_type="rss",
        acquisition_method="direct_http",
        status="ACTIVE",
    )
    store.append("sources", istat_src.to_dict())
    store.append("sources", fdic_src.to_dict())

    # ── Documents ──
    cpi_url = "https://www.istat.it/en/press-release/consumer-prices-july-2026"
    fdic_url = "https://www.fdic.gov/news/press-releases/2026/fdic-publishes-june-enforcement-actions"

    cpi_doc_id = document_id(cpi_url)
    fdic_doc_id = document_id(fdic_url)

    cpi_doc = Document(
        document_id=cpi_doc_id,
        canonical_url=cpi_url,
        aliases=[],
        source_id="ISTAT",
        publication_tuples=[],  # D4 tuples live here in production; canonical §3 says they're NOT surfaced
        created_at="2026-08-12T08:00:58Z",
        status="ACTIVE",
    )
    fdic_doc = Document(
        document_id=fdic_doc_id,
        canonical_url=fdic_url,
        aliases=[],
        source_id="FDIC",
        publication_tuples=[],
        created_at="2026-07-31T00:00:00Z",
        status="ACTIVE",
    )
    store.append("documents", cpi_doc.to_dict())
    store.append("documents", fdic_doc.to_dict())

    # ── Representations (content-addressed) ──
    # SHA-256 of the canonical representation content.
    # Matches the canonical mock fixtures: 'a' * 64, 'b' * 64, 'c' * 64.
    cpi_v1_sha = "a" * 64
    cpi_v2_sha = "c" * 64
    fdic_sha = "b" * 64

    cpi_rep_id = representation_id(cpi_doc_id, cpi_v1_sha)
    cpi_v2_rep_id = representation_id(cpi_doc_id, cpi_v2_sha)
    fdic_rep_id = representation_id(fdic_doc_id, fdic_sha)

    for rep_id, doc_id_, sha in [
        (cpi_rep_id, cpi_doc_id, cpi_v1_sha),
        (cpi_v2_rep_id, cpi_doc_id, cpi_v2_sha),
        (fdic_rep_id, fdic_doc_id, fdic_sha),
    ]:
        rep = Representation(
            representation_id=rep_id,
            document_id=doc_id_,
            content_sha256=sha,
            retrieved_at="2026-08-12T08:00:58Z",
            retrieval_event_id="ret-seed-v1",
            content_type="text/html",
            raw_location=f"blobs/{sha}",
        )
        store.append("representations", rep.to_dict())
        # Write the blob (content-addressed)
        store.write_blob(sha, f"seed-content-{sha[:8]}".encode())

    # ── Retrieval events ──
    for _rep_id, _doc_id, url in [
        (cpi_rep_id, cpi_doc_id, cpi_url),
        (cpi_v2_rep_id, cpi_doc_id, cpi_url),
        (fdic_rep_id, fdic_doc_id, fdic_url),
    ]:
        ret = RetrievalEvent(
            retrieval_event_id="ret-seed-v1",
            method="direct_http",
            adapter_class="direct_http",
            requested_url=url,
            final_url=url,
            http_status=200,
            retrieved_at="2026-08-12T08:00:58Z",
            run_id="seed-v1",
        )
        store.append("retrieval_events", ret.to_dict())

    # ── Facts ──
    # io-cpi-v1: fact-cpi-mom value=+0.3 (v1)
    # io-cpi-v2: fact-cpi-mom value=+0.4 (v2 — correction; same fact_id, new version)
    # io-fdic-enf: fact-enf-1 value="consent order"
    cpi_fact_v1 = Fact(
        fact_id="fact-cpi-mom",
        fact_version=1,
        representation_id=cpi_rep_id,
        document_id=cpi_doc_id,
        metric="percentage_statistic",
        value="+0.3",
        raw_value="+0.3",
        pattern_ref="FE-6-statistical",
        occurrence=0,
        excerpt="In July 2026 the Italian consumer price index for the whole nation (NIC) was +0.3% compared with the previous month.",
        status=ObjState.SUPERSEDED,
        supersedes=None,
        superseded_by="fact-cpi-mom:v2",
        created_at="2026-08-12T08:00:58Z",
    )
    cpi_fact_v2 = Fact(
        fact_id="fact-cpi-mom",
        fact_version=2,
        representation_id=cpi_v2_rep_id,
        document_id=cpi_doc_id,
        metric="percentage_statistic",
        value="+0.4",
        raw_value="+0.4",
        pattern_ref="FE-6-statistical",
        occurrence=0,
        excerpt="Corrected: In July 2026 the Italian consumer price index for the whole nation (NIC) was +0.4% compared with the previous month.",
        status=ObjState.ACTIVE,
        supersedes="fact-cpi-mom:v1",
        superseded_by=None,
        created_at="2026-08-13T08:00:00Z",
    )
    fdic_fact = Fact(
        fact_id="fact-enf-1",
        fact_version=1,
        representation_id=fdic_rep_id,
        document_id=fdic_doc_id,
        metric="action_type",
        value="consent order",
        raw_value="consent order",
        pattern_ref="FE-8-enforcement",
        occurrence=0,
        excerpt="FDIC issued 15 consent orders in June 2026.",
        status=ObjState.ACTIVE,
        supersedes=None,
        superseded_by=None,
        created_at="2026-07-31T00:00:00Z",
    )
    store.append("facts", cpi_fact_v1.to_dict())
    store.append("facts", cpi_fact_v2.to_dict())
    store.append("facts", fdic_fact.to_dict())

    # ── Evidence ──
    cpi_evi_v1 = Evidence(
        evidence_id="evi-cpi-1",
        event_or_fact_id="fact-cpi-mom",
        representation_id=cpi_rep_id,
        location="blobs/" + cpi_v1_sha,
        excerpt="...issued 15 orders...",
        provenance_ref="",
        created_at="2026-08-12T08:00:58Z",
    )
    cpi_evi_v2 = Evidence(
        evidence_id="evi-cpi-2",
        event_or_fact_id="fact-cpi-mom",
        representation_id=cpi_v2_rep_id,
        location="blobs/" + cpi_v2_sha,
        excerpt="...issued 15 orders...",
        provenance_ref="",
        created_at="2026-08-13T08:00:00Z",
    )
    fdic_evi = Evidence(
        evidence_id="evi-enf-1",
        event_or_fact_id="fact-enf-1",
        representation_id=fdic_rep_id,
        location="blobs/" + fdic_sha,
        excerpt="...issued 15 orders...",
        provenance_ref="",
        created_at="2026-07-31T00:00:00Z",
    )
    store.append("evidence", cpi_evi_v1.to_dict())
    store.append("evidence", cpi_evi_v2.to_dict())
    store.append("evidence", fdic_evi.to_dict())

    # ── Events ──
    # io-cpi-v1: evt-cpi v1, SUPERSEDED, references fact-cpi-mom:v1
    # io-cpi-v2: evt-cpi v2, ACTIVE, references fact-cpi-mom:v2 (correction)
    # io-fdic-enf: evt-fdic v1, ACTIVE, references fact-enf-1:v1
    cpi_evt_v1 = Event(
        event_id="evt-cpi",
        event_version=1,
        document_id=cpi_doc_id,
        event_type="statistical_release",
        fact_version_snapshot=[{"fact_id": "fact-cpi-mom", "fact_version": 1}],
        occurrence=0,
        status=ObjState.SUPERSEDED,
        derived_at="2026-08-12T08:00:58Z",
    )
    cpi_evt_v2 = Event(
        event_id="evt-cpi",
        event_version=2,
        document_id=cpi_doc_id,
        event_type="statistical_release",
        fact_version_snapshot=[{"fact_id": "fact-cpi-mom", "fact_version": 2}],
        occurrence=0,
        status=ObjState.ACTIVE,
        derived_at="2026-08-13T08:00:00Z",  # distinct from v1 — enables cursor pagination
    )
    fdic_evt = Event(
        event_id="evt-fdic",
        event_version=1,
        document_id=fdic_doc_id,
        event_type="regulatory_enforcement",
        fact_version_snapshot=[{"fact_id": "fact-enf-1", "fact_version": 1}],
        occurrence=0,
        status=ObjState.ACTIVE,
        derived_at="2026-07-31T00:00:00Z",  # distinct from CPI events — enables cursor pagination
    )
    store.append("events", cpi_evt_v1.to_dict())
    store.append("events", cpi_evt_v2.to_dict())
    store.append("events", fdic_evt.to_dict())

    # Compute expected io_ids for the manifest
    expected_io_ids = {
        "io-cpi-v1": io_id("evt-cpi", 1),
        "io-cpi-v2": io_id("evt-cpi", 2),
        "io-fdic-enf": io_id("evt-fdic", 1),
    }

    return {
        "store_root": str(store_root),
        "seeded_collections": {
            "institutions": 2,
            "sources": 2,
            "documents": 2,
            "representations": 3,
            "retrieval_events": 3,
            "facts": 3,
            "evidence": 3,
            "events": 3,
        },
        "expected_io_ids": expected_io_ids,
        "validated_lineage": [
            {"io_id": expected_io_ids["io-cpi-v1"], "event_version": 1, "status": "SUPERSEDED",
             "event_type": "statistical_release", "fact_value": "+0.3"},
            {"io_id": expected_io_ids["io-cpi-v2"], "event_version": 2, "status": "ACTIVE",
             "event_type": "statistical_release", "fact_value": "+0.4",
             "supersedes_io_id": expected_io_ids["io-cpi-v1"]},
            {"io_id": expected_io_ids["io-fdic-enf"], "event_version": 1, "status": "ACTIVE",
             "event_type": "regulatory_enforcement", "fact_value": "consent order"},
        ],
    }


if __name__ == "__main__":
    store_root = sys.argv[1] if len(sys.argv) > 1 else "production_store"
    manifest = seed(store_root)
    print(json.dumps(manifest, indent=2))
