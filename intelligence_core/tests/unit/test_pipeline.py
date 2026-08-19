"""§11 Pipeline — failure isolation, config-only remediation (FED_ENF), reproducibility."""
import tempfile
import unittest
from intelligence_core.store import AppendOnlyStore
from intelligence_core.contracts import Institution
from intelligence_core.entity_resolution import InstitutionRegistry
from intelligence_core.config import SourceConfig, config_from_dict, ConfigViolation

FDIC_INST = Institution(
    institution_id="INST-fdic-001", legal_entity="Federal Deposit Insurance Corporation",
    jurisdiction="US", institutional_class="deposit_insurer",
    verified_domains=[{"domain": "www.fdic.gov", "verification_evidence": "about page"}])
FED_INST = Institution(
    institution_id="INST-fed-enf-001", legal_entity="Board of Governors of the Federal Reserve System",
    jurisdiction="US", institutional_class="financial_regulator",
    verified_domains=[{"domain": "www.federalreserve.gov", "verification_evidence": "about page"}])

RSS_A = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Statistical release</title><link>https://www.fdic.gov/news/a1</link>
<pubDate>Mon, 10 Aug 2026 13:10:04 -0500</pubDate>
<description>In June 2026, GDP grew by 2.4 percent and the unemployment rate was 4.1 percent.</description></item>
</channel></rss>"""

RSS_B = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Enforcement</title><link>https://www.federalreserve.gov/enf/1</link>
<pubDate>Wed, 05 Aug 2026 09:03:31 -0500</pubDate>
<description>The Federal Reserve announced a Consent Order against First Test Bank for unsafe practices.</description></item>
</channel></rss>"""

ARTICLE_A = ("<html><body><p>In June 2026, GDP grew by 2.4 percent according to the "
             "advance estimate.</p></body></html>")
ARTICLE_B = ("<html><body><p>The Federal Reserve announced a Consent Order against "
             "First Test Bank for unsafe practices.</p></body></html>")

FED_PATTERNS_V1 = [(r"enforcement\s+action\s+against\s+([A-Z][A-Za-z0-9\s,&\.\-]{3,60}?)(?:[,\n\.])", "defendant_name")]
FED_PATTERNS_V2 = [(r"Consent\s+Order\s+against\s+([A-Z][A-Za-z0-9\s,&\.\-]{3,60}?)(?:[,\n\.])", "defendant_name")]


class FakeTransport:
    def __init__(self, routes: dict):
        self.routes = routes

    def get(self, url, timeout=30):
        for prefix, payload in self.routes.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return 200, url, payload.encode("utf-8"), "application/rss+xml"
        raise RuntimeError(f"no route for {url}")


def registry() -> InstitutionRegistry:
    r = InstitutionRegistry()
    r.add_institution(FDIC_INST)
    r.add_institution(FED_INST)
    return r


class TestPipeline(unittest.TestCase):
    def test_one_source_failure_does_not_terminate_others(self):
        from intelligence_core.pipeline import run_many
        with tempfile.TemporaryDirectory() as d:
            s = AppendOnlyStore(d)
            ok = SourceConfig(code="FDIC", name="FDIC", institution_id=FDIC_INST.institution_id,
                              source_path="https://www.fdic.gov/news/press-releases",
                              feed_format="rss",
                              patterns=[(r"GDP\s+grew\s+by\s+([+-]?\d+(?:\.\d+)?)\s*(?:percent|%)", "gdp_growth")],
                              event_type="statistical_release")
            bad = SourceConfig(code="DEAD", name="Dead", institution_id=FDIC_INST.institution_id,
                               source_path="https://www.fdic.gov/nonexistent",
                               feed_format="rss",
                               patterns=[(r"x", "gdp_growth")], event_type="statistical_release")
            t = FakeTransport({"https://www.fdic.gov/news/press-releases": RSS_A,
                               "https://www.fdic.gov/news/a1": ARTICLE_A,
                               "https://www.fdic.gov/nonexistent": ConnectionError("refused")})
            results = run_many(s, registry(), [bad, ok], transport=t, run_id="r1")
            self.assertEqual(results[0]["state"], "BLOCKED")      # failed source isolated
            self.assertEqual(results[1]["state"], "PUBLISHABLE")  # other source completed
            self.assertEqual(results[1]["results"][0]["events"], 1)
            self.assertEqual(results[1]["results"][0]["facts"], 1)

    def test_fed_enf_config_only_remediation(self):
        """FED_ENF precedent (f16bc00): changing PATTERNS ONLY (config) changes the result.
        No core code changes involved — same Core, two configuration versions."""
        from intelligence_core.pipeline import run_source
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            s1, s2 = AppendOnlyStore(d1), AppendOnlyStore(d2)
            v1 = SourceConfig(code="FED_ENF", name="Fed Enforcement",
                              institution_id=FED_INST.institution_id,
                              source_path="https://www.federalreserve.gov/feeds/enf.xml",
                              feed_format="rss", patterns=FED_PATTERNS_V1,
                              event_type="regulatory_enforcement")
            v2 = SourceConfig(code="FED_ENF", name="Fed Enforcement",
                              institution_id=FED_INST.institution_id,
                              source_path="https://www.federalreserve.gov/feeds/enf.xml",
                              feed_format="rss", patterns=FED_PATTERNS_V2,
                              event_type="regulatory_enforcement",
                              configuration_version="2")
            t = FakeTransport({"https://www.federalreserve.gov/feeds/enf.xml": RSS_B,
                               "https://www.federalreserve.gov/enf/1": ARTICLE_B})
            r1 = run_source(s1, registry(), v1, transport=t, run_id="a")
            r2 = run_source(s2, registry(), v2, transport=t, run_id="b")
            self.assertEqual(r1["results"][0]["facts"], 0)   # original patterns miss Fed phrasing
            self.assertEqual(r2["results"][0]["facts"], 1)   # remediated config-only patterns hit

    def test_reproducibility_same_inputs_same_lineage(self):
        from intelligence_core.pipeline import run_source
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            s1, s2 = AppendOnlyStore(d1), AppendOnlyStore(d2)
            cfg = SourceConfig(code="FDIC", name="FDIC", institution_id=FDIC_INST.institution_id,
                               source_path="https://www.fdic.gov/news/press-releases",
                               feed_format="rss",
                               patterns=[(r"GDP\s+grew\s+by\s+([+-]?\d+(?:\.\d+)?)\s*(?:percent|%)", "gdp_growth")],
                               event_type="statistical_release")
            t = FakeTransport({"https://www.fdic.gov/news/press-releases": RSS_A,
                               "https://www.fdic.gov/news/a1": ARTICLE_A})
            r1 = run_source(s1, registry(), cfg, transport=t, run_id="same-run")
            r2 = run_source(s2, registry(), cfg, transport=t, run_id="same-run")
            io1 = list(s1.iter("intelligence_objects"))
            io2 = list(s2.iter("intelligence_objects"))
            self.assertEqual([x["io_id"] for x in io1], [x["io_id"] for x in io2])
            f1 = [x["fact_id"] for x in s1.iter("facts")]
            f2 = [x["fact_id"] for x in s2.iter("facts")]
            self.assertEqual(f1, f2)
            self.assertEqual(r1["results"], r2["results"])

    def test_config_forbidden_domains_rejected(self):
        with self.assertRaises(ConfigViolation):
            config_from_dict({"code": "X", "source_path": "https://x/", "feed_format": "rss",
                              "patterns": [], "event_type": "statistical_release",
                              "captcha": "solve-it"})            # forbidden domain in dict
        with self.assertRaises(ConfigViolation):
            config_from_dict({"code": "Y", "source_path": "https://y/", "feed_format": "rss",
                              "patterns": [], "event_type": "fiscal_policy"})  # 7th type
        with self.assertRaises(ConfigViolation):
            SourceConfig(code="Z", name="Z", institution_id="", source_path="https://z/",
                         patterns=[], event_type="statistical_release")  # no entity binding


if __name__ == "__main__":
    unittest.main()
