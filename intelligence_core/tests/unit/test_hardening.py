"""Pre-Simulation Hardening regression tests — L-EVT-PROP (Cases A–F),
L-REL (4 link forms), L-SRC (registration rules). Directive-mandated."""
import tempfile
import unittest
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Fact, ObjState, SupersessionReason
from intelligence_core.governance import (supersede_fact, supersede_fact_by_source,
                                          recompute_event, reproduce_event)
from intelligence_core.acquisition import resolve_index_link
from intelligence_core.identity import fact_id as make_fact_id
from intelligence_core.config import SourceConfig
from intelligence_core.entity_resolution import (InstitutionRegistry,
                                                 EntityResolutionError)
from intelligence_core.contracts import Institution


def seed(store, fid, metric="policy_rate", value="4.50", version=1,
         status=ObjState.ACTIVE, supersedes=None, superseded_by=None):
    row = Fact(fact_id=fid, fact_version=version, representation_id=f"rep-{fid}",
               document_id="doc-1", metric=metric, value=value,
               pattern_ref="rate_value", occurrence=1, status=status,
               supersedes=supersedes, superseded_by=superseded_by)
    store.append("facts", row.to_dict())
    return row.to_dict()


def seed_event(store, snapshot):
    store.append("events", {"event_id": "evt-1", "event_version": 1,
                            "document_id": "doc-1", "event_type": "monetary_policy_decision",
                            "fact_version_snapshot": snapshot, "occurrence": 0,
                            "status": "ACTIVE", "derived_at": ""})


class TestLEvtProp(unittest.TestCase):
    def _store(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return AppendOnlyStore(d.name)

    def test_case_a_single_superseded_fact_new_event_version(self):
        s = self._store()
        seed(s, "fact-a")
        seed_event(s, [{"fact_id": "fact-a", "fact_version": 1}])
        supersede_fact(s, "fact-a", "4.75", SupersessionReason.EXTRACTION_ERROR,
                       "err", "agent", "run")
        ev = recompute_event(s, "evt-1")
        self.assertEqual(ev["event_version"], 2)
        self.assertEqual(ev["status"], ObjState.ACTIVE.value)
        self.assertEqual(ev["fact_version_snapshot"],
                         [{"fact_id": "fact-a", "fact_version": 3}])

    def test_case_a_cross_representation_chain(self):
        s = self._store()
        seed(s, "fact-old", value="4.50")
        seed_event(s, [{"fact_id": "fact-old", "fact_version": 1}])
        seed(s, "fact-new", value="4.25")           # successor on NEW representation
        supersede_fact_by_source(s, "fact-old", s.current_fact("fact-new"),
                                  SupersessionReason.SOURCE_REVISION, "rev-doc",
                                  "agent", "run")
        ev = recompute_event(s, "evt-1")
        self.assertEqual(ev["fact_version_snapshot"],
                         [{"fact_id": "fact-new", "fact_version": 1}])   # followed the link
        self.assertEqual(ev["event_version"], 2)

    def test_case_b_mixed_facts(self):
        s = self._store()
        seed(s, "fact-stay", metric="policy_rate", value="1.0")
        seed(s, "fact-gone", metric="policy_rate", value="2.0")
        seed_event(s, [{"fact_id": "fact-stay", "fact_version": 1},
                       {"fact_id": "fact-gone", "fact_version": 1}])
        seed(s, "fact-repl", metric="policy_rate", value="2.2")
        supersede_fact_by_source(s, "fact-gone", s.current_fact("fact-repl"),
                                  SupersessionReason.SOURCE_REVISION, "rev", "a", "r")
        ev = recompute_event(s, "evt-1")
        ids = {x["fact_id"] for x in ev["fact_version_snapshot"]}
        self.assertEqual(ids, {"fact-stay", "fact-repl"})

    def test_case_c_all_superseded_event_survives(self):
        s = self._store()
        seed(s, "f1", value="1")
        seed(s, "f2", value="2")
        seed_event(s, [{"fact_id": "f1", "fact_version": 1},
                       {"fact_id": "f2", "fact_version": 1}])
        seed(s, "f1n", value="1x"); seed(s, "f2n", value="2x")
        supersede_fact_by_source(s, "f1", s.current_fact("f1n"),
                                  SupersessionReason.SOURCE_REVISION, "r", "a", "r")
        supersede_fact_by_source(s, "f2", s.current_fact("f2n"),
                                  SupersessionReason.SOURCE_REVISION, "r", "a", "r")
        ev = recompute_event(s, "evt-1")
        self.assertIsNotNone(ev)                       # does NOT disappear
        self.assertEqual(ev["event_version"], 2)
        self.assertEqual(ev["status"], ObjState.ACTIVE.value)

    def test_case_c2_all_invalidated_event_invalidated_not_deleted(self):
        s = self._store()
        seed(s, "fx", value="1")
        seed_event(s, [{"fact_id": "fx", "fact_version": 1}])
        cur = dict(s.current_fact("fx"))
        cur.update({"fact_version": cur["fact_version"] + 1,
                    "status": ObjState.INVALIDATED.value})
        s.append("facts", cur)
        ev = recompute_event(s, "evt-1")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["status"], ObjState.INVALIDATED.value)  # honest state, not silent death

    def test_case_d_historical_v1_reproducible_exactly(self):
        s = self._store()
        seed(s, "fact-h", value="4.50")
        seed_event(s, [{"fact_id": "fact-h", "fact_version": 1}])
        seed(s, "fact-h2", value="4.25")
        supersede_fact_by_source(s, "fact-h", s.current_fact("fact-h2"),
                                  SupersessionReason.SOURCE_REVISION, "r", "a", "r")
        recompute_event(s, "evt-1")
        old = reproduce_event(s, "evt-1", 1)
        self.assertEqual(old["facts"][0]["value"], "4.50")
        self.assertEqual(old["facts"][0]["fact_version"], 1)

    def test_case_e_deterministic_lineage(self):
        s1, s2 = self._store(), self._store()
        for s in (s1, s2):
            seed(s, "fact-e", value="3.0")
            seed_event(s, [{"fact_id": "fact-e", "fact_version": 1}])
            supersede_fact(s, "fact-e", "3.5", SupersessionReason.EXTRACTION_ERROR,
                           "err", "a", "r")
            recompute_event(s, "evt-1")
        self.assertEqual([ (r["event_version"], r["fact_version_snapshot"])
                           for r in s1.event_versions("evt-1") ],
                         [ (r["event_version"], r["fact_version_snapshot"])
                           for r in s2.event_versions("evt-1") ])

    def test_case_f_repeated_recompute_idempotent(self):
        s = self._store()
        seed(s, "fact-i", value="1")
        seed_event(s, [{"fact_id": "fact-i", "fact_version": 1}])
        supersede_fact(s, "fact-i", "2", SupersessionReason.EXTRACTION_ERROR,
                       "e", "a", "r")
        first = recompute_event(s, "evt-1")
        n_versions = len(s.event_versions("evt-1"))
        second = recompute_event(s, "evt-1")
        third = recompute_event(s, "evt-1")
        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(len(s.event_versions("evt-1")), n_versions)  # no extra rows


IDX = "https://www.example.gov/sections/2026/index.html"


class TestLRel(unittest.TestCase):
    def test_absolute(self):
        self.assertEqual(resolve_index_link("https://other.example/a?x=1", IDX),
                         "https://other.example/a?x=1")

    def test_root_relative(self):
        self.assertEqual(resolve_index_link("/Articles/2026/07/16/slug", IDX),
                         "https://www.example.gov/Articles/2026/07/16/slug")

    def test_path_relative(self):
        self.assertEqual(resolve_index_link("news/item-9.html", IDX),
                         "https://www.example.gov/sections/2026/news/item-9.html")

    def test_dotdot(self):
        self.assertEqual(resolve_index_link("../2027/report.html", IDX),
                         "https://www.example.gov/sections/2027/report.html")

    def test_query_preserved(self):
        self.assertEqual(resolve_index_link("/a?utm_source=x&id=7", IDX),
                         "https://www.example.gov/a?utm_source=x&id=7")


INST = Institution("INST-x-001", "Example Regulator", "US", "financial_regulator",
                   [{"domain": "www.example.gov", "verification_evidence": "about"}])


class TestLSrc(unittest.TestCase):
    def _run(self, code="X", institution_id=INST.institution_id,
             path="https://www.example.gov/feed"):
        import tempfile
        from intelligence_core.pipeline import run_source
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        store = AppendOnlyStore(d.name)
        cfg = SourceConfig(code=code, name=code, institution_id=institution_id,
                           source_path=path, feed_format="rss",
                           patterns=[(r"never", "policy_rate")],
                           event_type="statistical_release")

        class EmptyFeed:
            def get(self, url, timeout=30):
                return 200, url, b"<rss version='2.0'><channel></channel></rss>", \
                    "application/xml"
        reg = InstitutionRegistry(); reg.add_institution(INST)
        r = run_source(store, reg, cfg, transport=EmptyFeed(), run_id="t")
        return store, r

    def test_source_persisted_once_idempotent(self):
        store, r1 = self._run()
        self.assertEqual(sum(1 for _ in store.iter("sources")), 1)
        from intelligence_core.pipeline import run_source
        cfg = SourceConfig(code="X", name="X", institution_id=INST.institution_id,
                           source_path="https://www.example.gov/feed",
                           feed_format="rss", patterns=[],
                           event_type="statistical_release")

        class EmptyFeed:
            def get(self, url, timeout=30):
                return 200, url, b"<rss version='2.0'><channel></channel></rss>", \
                    "application/xml"
        reg = InstitutionRegistry(); reg.add_institution(INST)
        run_source(store, reg, cfg, transport=EmptyFeed(), run_id="t2")
        self.assertEqual(sum(1 for _ in store.iter("sources")), 1)   # no duplicate

    def test_failed_entity_resolution_no_source_row(self):
        store, r = self._run(path="https://unverified.example/feed")
        self.assertEqual(r["state"], "BLOCKED")
        self.assertEqual(sum(1 for _ in store.iter("sources")), 0)   # no row

    def test_mismatched_entity_rejected_no_row(self):
        store, r = self._run(path="https://www.example.gov/feed",
                             institution_id="INST-other-999")
        self.assertEqual(r["state"], "BLOCKED")
        self.assertEqual(sum(1 for _ in store.iter("sources")), 0)

    def test_banned_domain_rejected(self):
        # bmf.de regression interplay: unverified domain -> BLOCKED before Source row
        store, r = self._run(path="https://bmf.de/feed")
        self.assertEqual(r["state"], "BLOCKED")
        self.assertEqual(sum(1 for _ in store.iter("sources")), 0)


if __name__ == "__main__":
    unittest.main()
