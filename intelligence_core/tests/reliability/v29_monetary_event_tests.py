"""V29 §6-7 — Monetary Event Semantic Gate Regression Tests.

Negative fixtures: 3 V28 FP cases (Canadian securities market notices)
Positive fixtures: synthetic valid monetary_policy_decision documents
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

CORE_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CORE_REPO))

from intelligence_core.tests.reliability.v13_recall_patterns import validate_event_context_v13


class TestMonetaryEventNegativeFixtures(unittest.TestCase):
    """V29 §6 — The 3 V28 FP cases must be REJECTED by the new gate."""

    def setUp(self):
        # Simulated document text based on the actual Bank of Canada
        # securities market notice that was misclassified as monetary_policy_decision
        self.securities_notice_text = """
        Bank of Canada Core functions Monetary policy Financial system Currency
        Funds management Publications Market notices August 13, 2026
        CIMPA and CDS announce the start of the trial period for the fail fee
        framework for Government of Canada securities transactions August 12, 2026
        New GoC General Collateral Reopening and Operations
        Government securities auctions Schedules and results
        """

    def test_cimpa_cds_securities_notice_rejected(self):
        """The CIMPA/CDS fail fee notice must NOT pass monetary_policy_decision gate."""
        valid, reason = validate_event_context_v13("monetary_policy_decision", self.securities_notice_text, "en")
        self.assertFalse(valid, f"CIMPA/CDS securities notice should be rejected, but got: {reason}")

    def test_government_securities_transactions_rejected(self):
        """CIMPA/CDS fail-fee framework notices must NOT pass monetary gate (V29.1 narrow)."""
        text = """
        Market notice: CIMPA and CDS announce the start of the trial period
        for the fail fee framework for Government of Canada securities transactions.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertFalse(valid, f"CIMPA/CDS fail-fee notice should be rejected: {reason}")

    def test_bond_auction_notice_accepted(self):
        """V29.1: Bond auction notices that DON'T contain CIMPA/CDS must PASS (no broad exclusion)."""
        text = """
        The central bank announced its policy rate decision.
        Bond auction schedule updated. Interest rate maintained at 4.5%.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Monetary doc mentioning bond auction should pass (V29.1 narrow): {reason}")

    def test_fail_fee_framework_rejected(self):
        """Fail fee framework notices must NOT pass monetary gate (V29.1 narrow)."""
        text = """
        CIMPA announces fail fee framework trial period.
        CDS to implement settlement framework for Government of Canada securities.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertFalse(valid, f"Fail fee notice should be rejected: {reason}")


class TestMonetaryEventPositiveFixtures(unittest.TestCase):
    """V29 §7 — Valid monetary_policy_decision documents must still PASS."""

    def test_rate_hike_accepted(self):
        """A rate hike decision must pass the monetary gate."""
        text = """
        The Bank announced today that it has raised its policy rate to 4.5%.
        The monetary policy committee decided to increase the benchmark rate
        by 25 basis points. This decision reflects the central bank's assessment
        of inflation pressures.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Valid rate hike should pass: {reason}")

    def test_rate_cut_accepted(self):
        """A rate cut decision must pass the monetary gate."""
        text = """
        The central bank cut its key rate to 0.5% in today's decision.
        The monetary policy statement announced a 50 basis point reduction.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Valid rate cut should pass: {reason}")

    def test_rate_hold_accepted(self):
        """A rate hold/maintain decision must pass the monetary gate."""
        text = """
        The Bank maintained its policy rate at 5.0%.
        The monetary policy committee decided to keep the benchmark rate unchanged.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Valid rate hold should pass: {reason}")

    def test_press_release_monetary_accepted(self):
        """A monetary policy press release must pass the gate."""
        text = """
        Press release: The Bank of England's monetary policy committee
        announced its interest rate decision today. The policy rate
        was maintained at 5.25%.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Valid monetary press release should pass: {reason}")

    def test_policy_statement_accepted(self):
        """A monetary policy statement must pass the gate."""
        text = """
        Statement on monetary policy: The Federal Reserve's Federal Open
        Market Committee decided to raise the federal funds rate to 5.5%.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Valid policy statement should pass: {reason}")

    def test_announced_rate_change_accepted(self):
        """An announced rate change must pass the gate."""
        text = """
        The ECB announced a rate change today. The European Central Bank
        raised its main refinancing rate to 4.5%. The decision was made
        by the monetary policy committee.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Valid announced rate change should pass: {reason}")


class TestNoFalseNegativeMonetary(unittest.TestCase):
    """V29 §10 — The new gate must not create false negatives for valid monetary events."""

    def test_comprehensive_monetary_policy_doc(self):
        """A comprehensive monetary policy document must pass."""
        text = """
        Monetary Policy Decision — January 2026

        The Bank of Canada today announced its decision on the target for
        the overnight rate. The policy rate was maintained at 4.25%.

        Press release: The Bank's monetary policy committee reviewed
        economic indicators and decided to hold the key rate steady.

        Statement on monetary policy: The Bank's governing council
        believes that the current interest rate stance is appropriate.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Comprehensive monetary policy doc should pass: {reason}")

    def test_simple_rate_decision(self):
        """A simple rate decision must pass."""
        text = """
        The Bank decided to raise the policy rate to 3.5%.
        """
        valid, reason = validate_event_context_v13("monetary_policy_decision", text, "en")
        self.assertTrue(valid, f"Simple rate decision should pass: {reason}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
