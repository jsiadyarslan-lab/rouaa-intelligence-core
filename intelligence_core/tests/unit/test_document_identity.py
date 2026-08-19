"""§11 Document identity — D1 three-level contract."""
import unittest
from intelligence_core.identity import (canonicalize_url, document_id,
                                        representation_id, content_sha256)


class TestCanonicalization(unittest.TestCase):
    def test_relative_absolutized(self):
        c, _ = canonicalize_url("news-article/AV./x/17738541",
                                base="https://www.londonstockexchange.com/news")
        # urljoin semantics: sibling-relative href replaces the last path segment (Q1 evidence form)
        self.assertEqual(c, "https://www.londonstockexchange.com/news-article/AV./x/17738541")

    def test_redirect_alias_recorded(self):
        c, aliases = canonicalize_url("https://bmf.de/feed/", final_url="https://bmf.de/feed")
        self.assertEqual(c, "https://bmf.de/feed")
        self.assertIn("https://bmf.de/feed/", aliases)

    def test_tracking_params_stripped_and_aliased(self):
        c, aliases = canonicalize_url("https://x.example/a?utm_source=r&id=7")
        self.assertEqual(c, "https://x.example/a?id=7")
        self.assertTrue(aliases)

    def test_host_case_and_trailing_slash(self):
        c, _ = canonicalize_url("HTTPS://X.Example/A/")
        self.assertEqual(c, "https://x.example/A")


class TestThreeLevelIdentity(unittest.TestCase):
    def test_same_content_same_representation(self):
        doc = document_id("https://s.example/doc1")
        sha = content_sha256(b"same bytes")
        self.assertEqual(representation_id(doc, sha), representation_id(doc, sha))

    def test_changed_content_new_representation_same_document(self):
        doc = document_id("https://s.example/doc1")
        r1 = representation_id(doc, content_sha256(b"v1"))
        r2 = representation_id(doc, content_sha256(b"v2"))
        self.assertNotEqual(r1, r2)

    def test_deterministic_across_runs(self):
        self.assertEqual(document_id("https://s.example/doc1"),
                         document_id("https://s.example/doc1"))


if __name__ == "__main__":
    unittest.main()
