"""§11 Identity — BMF entity misattribution regression (directive §7)."""
import unittest
from intelligence_core.contracts import Institution
from intelligence_core.entity_resolution import InstitutionRegistry, EntityResolutionError

MINISTRY = Institution(
    institution_id="INST-bundesministerium-der-finanzen-001",
    legal_entity="Bundesministerium der Finanzen",
    jurisdiction="DE", institutional_class="finance_ministry",
    verified_domains=[{"domain": "bundesfinanzministerium.de",
                       "verification_evidence": "imprint: bundesfinanzministerium.de/Impressum"}],
    brands=["BMF"])
COMPANY = Institution(
    institution_id="INST-buerener-maschinenfabrik-001",
    legal_entity="Bürener Maschinenfabrik GmbH",
    jurisdiction="DE", institutional_class="corporate_industrial",
    verified_domains=[{"domain": "bmf.de",
                       "verification_evidence": "imprint: bmf.de/uwa/ — 'Bürener Maschinenfabrik GmbH' (Post-Q3 f6c5a8b)"}],
    brands=["BMF"])


def registry() -> InstitutionRegistry:
    r = InstitutionRegistry()
    r.add_institution(MINISTRY)
    r.add_institution(COMPANY)
    return r


class TestEntityResolution(unittest.TestCase):
    def test_bmf_de_is_not_the_ministry(self):
        r = registry()
        self.assertEqual(r.resolve("bmf.de").institution_id,
                         COMPANY.institution_id)
        self.assertNotEqual(r.resolve("bmf.de").institution_id, MINISTRY.institution_id)

    def test_false_association_rejected(self):
        r = registry()
        with self.assertRaises(EntityResolutionError):
            r.assert_association("bmf.de", MINISTRY.institution_id)  # the original misattribution

    def test_brand_lookup_forbidden(self):
        r = registry()
        with self.assertRaises(EntityResolutionError):
            r.resolve_by_brand("BMF")  # collides across both institutions

    def test_long_domain_is_the_ministry(self):
        r = registry()
        self.assertEqual(r.resolve("https://www.bundesfinanzministerium.de/Web/EN/Home/home.html")
                         .institution_id, MINISTRY.institution_id)

    def test_unverified_domain_rejected(self):
        r = registry()
        with self.assertRaises(EntityResolutionError):
            r.assert_association("unknown-domain.example", MINISTRY.institution_id)

    def test_superseding_correction_preserves_history(self):
        r = registry()
        r.supersede_entity_correction("bmf.de", COMPANY.institution_id,
                                      COMPANY.institution_id, "test", "evidence-x")
        self.assertTrue(any(h["type"] == "ENTITY_CORRECTION"
                            for h in r._by_id[COMPANY.institution_id].history))


if __name__ == "__main__":
    unittest.main()
