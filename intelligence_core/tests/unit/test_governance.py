"""§11 Corrections — D2 supersession, event snapshots, historical reproducibility,
evidence hash traceability, IO chain, delivery idempotency, event-model boundary."""
import unittest
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Fact, ObjState, SupersessionReason
from intelligence_core.governance import (supersede_fact, recompute_event,
                                           reproduce_event)
from intelligence_core.delivery import build_intelligence_object, deliver


def make_store(tmpdir) -> AppendOnlyStore:
    return AppendOnlyStore(str(tmpdir))


def seed_fact(store, fid="fact-x", metric="policy_rate", value="4.50") -> dict:
    row = Fact(fact_id=fid, fact_version=1, representation_id="rep-1",
               document_id="doc-1", metric=metric, value=value,
               pattern_ref="rate_value", occurrence=1, excerpt="policy rate was 4.50 percent")
    store.append("facts", row.to_dict())
    store.append("events", {"event_id": "evt-1", "event_version": 1,
                            "document_id": "doc-1", "event_type": "monetary_policy_decision",
                            "fact_version_snapshot": [{"fact_id": fid, "fact_version": 1}],
                            "occurrence": 0, "status": "ACTIVE", "derived_at": ""})
    store.append("representations", {"representation_id": "rep-1", "document_id": "doc-1",
                                     "content_sha256": "a" * 64, "retrieved_at": "",
                                     "retrieval_event_id": "ret-1", "content_type": "",
                                     "raw_location": ""})
    store.append("documents", {"document_id": "doc-1", "canonical_url": "https://s.example/d",
                                "aliases": [], "source_id": "SRC-1",
                                "publication_tuples": [], "created_at": "", "status": "ACTIVE"})
    return row.to_dict()


class TestCorrections(unittest.TestCase):
    def test_fact_supersession_appends_not_overwrites(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            s = make_store(d)
            seed_fact(s)
            nxt = supersede_fact(s, "fact-x", "4.75", SupersessionReason.EXTRACTION_ERROR,
                                 "re-extraction of rep-1 found decimal error", "agent", "run-2")
            self.assertEqual(nxt["fact_version"], 3)          # closing row v2 + active v3
            self.assertEqual(nxt["status"], ObjState.ACTIVE.value)
            v1 = s.fact_row("fact-x", 1)
            self.assertIsNotNone(v1)                            # history retained
            self.assertEqual(v1["value"], "4.50")              # immutable
            versions = s.fact_versions("fact-x")
            self.assertEqual(len(versions), 3)

    def test_event_recompute_snapshot_and_reproducibility(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = make_store(d)
            seed_fact(s)
            supersede_fact(s, "fact-x", "4.75", SupersessionReason.EXTRACTION_ERROR,
                           "err", "agent", "run-2")
            new_evt = recompute_event(s, "evt-1")
            self.assertEqual(new_evt["event_version"], 2)
            snap = new_evt["fact_version_snapshot"]
            self.assertEqual(snap[0]["fact_version"], 3)        # current ACTIVE version
            old = reproduce_event(s, "evt-1", 1)                # historical reproducibility
            self.assertIsNotNone(old)
            self.assertEqual(old["facts"][0]["value"], "4.50") # old truth reproducible
            self.assertEqual(old["event"]["event_version"], 1)

    def test_evidence_hash_traceability(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = make_store(d)
            seed_fact(s)                                        # rep-1 anchored to sha256
            s.append("evidence", {"evidence_id": "evi-1", "event_or_fact_id": "fact-x",
                                  "representation_id": "rep-1", "location": "p:1",
                                  "excerpt": "x", "provenance_ref": "representation:rep-1",
                                  "created_at": ""})
            reps = s.latest_by_id("representations", "representation_id")
            self.assertIn("rep-1", reps)
            self.assertEqual(reps["rep-1"]["content_sha256"], "a" * 64)  # exact-bytes anchor

    def test_io_chain_and_delivery_idempotency(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = make_store(d)
            seed_fact(s)
            s.append("evidence", {"evidence_id": "evi-1", "event_or_fact_id": "fact-x",
                                  "representation_id": "rep-1", "location": "p:1",
                                  "excerpt": "rate was", "provenance_ref": "r:rep-1",
                                  "created_at": ""})
            evt = s.current_event("evt-1")
            io = build_intelligence_object(s, evt, source_name="Test Source")
            self.assertEqual(len(io.chain), 1)
            link = io.chain[0]
            self.assertEqual(link["representation"]["content_sha256"], "a" * 64)
            self.assertEqual(link["document"]["canonical_url"], "https://s.example/d")
            d1, created1 = deliver(s, io, "product:TEST")
            d2, created2 = deliver(s, io, "product:TEST")
            self.assertTrue(created1)
            self.assertFalse(created2)                          # idempotent per version
            self.assertEqual(d1.delivery_id, d2.delivery_id)

    def test_six_event_types_only(self):
        from intelligence_core.detect import SUPPORTED_EVENT_TYPES, detect_event
        self.assertEqual(len(SUPPORTED_EVENT_TYPES), 6)
        with self.assertRaises(ValueError):
            detect_event([], "doc", "fiscal_policy")            # forbidden new type


if __name__ == "__main__":
    unittest.main()
