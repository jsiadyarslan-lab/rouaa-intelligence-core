"""Deterministic test runner — Minimum Core Phase 1 (directive §11 families)."""
import sys
import unittest

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([
        loader.loadTestsFromName("intelligence_core.tests.unit.test_entity"),
        loader.loadTestsFromName("intelligence_core.tests.unit.test_document_identity"),
        loader.loadTestsFromName("intelligence_core.tests.unit.test_temporal"),
        loader.loadTestsFromName("intelligence_core.tests.unit.test_governance"),
        loader.loadTestsFromName("intelligence_core.tests.unit.test_pipeline"),
        loader.loadTestsFromName("intelligence_core.tests.unit.test_hardening"),
    ])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
