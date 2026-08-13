from decimal import Decimal

import pytest

from app.rule_engine.evaluate import classify_category, compute_tds
from app.rule_engine.section_393 import TDSCategory


class TestClassifyCategory:
    def test_declared_category_takes_precedence(self):
        assert classify_category("some random text", declared_category="Rent") == TDSCategory.RENT

    def test_declared_category_normalizes_spacing_and_case(self):
        assert (
            classify_category("x", declared_category="Commission Brokerage")
            == TDSCategory.COMMISSION_BROKERAGE
        )

    def test_unknown_declared_category_falls_back_to_keywords(self):
        result = classify_category("Paid monthly rent for office", declared_category="not-a-real-category")
        assert result == TDSCategory.RENT

    @pytest.mark.parametrize(
        "description,expected",
        [
            ("Professional consulting fee for Q1", TDSCategory.PROFESSIONAL_FEES),
            ("Office rent for March", TDSCategory.RENT),
            ("Payment to construction contractor", TDSCategory.CONTRACTOR_PAYMENTS),
            ("Sales commission payout", TDSCategory.COMMISSION_BROKERAGE),
            ("Fixed deposit interest credited", TDSCategory.INTEREST_OTHER_THAN_SECURITIES),
            ("Dividend payout Q2", TDSCategory.DIVIDEND),
            ("Game show winnings", TDSCategory.LOTTERY_WINNINGS),
            ("Immovable property purchase", TDSCategory.PROPERTY_PURCHASE),
            ("Crypto asset transfer", TDSCategory.VIRTUAL_DIGITAL_ASSETS),
        ],
    )
    def test_keyword_classification(self, description, expected):
        assert classify_category(description) == expected

    def test_non_resident_flag_overrides_keyword_match(self):
        result = classify_category("consulting fee", payee_is_non_resident=True)
        assert result == TDSCategory.NON_RESIDENT_PAYMENT

    def test_no_match_returns_unclassified(self):
        assert classify_category("miscellaneous grocery purchase") == TDSCategory.UNCLASSIFIED


class TestComputeTdsProfessionalFees:
    """Section 393 Table Item 3 — threshold ₹30,000/payee/FY, rate 10%."""

    def test_below_threshold_no_tds(self):
        result = compute_tds(TDSCategory.PROFESSIONAL_FEES, Decimal("10000"), Decimal("5000"))
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")
        assert result.cumulative_after == Decimal("15000")

    def test_transaction_that_crosses_threshold_taxes_full_cumulative(self):
        # 25,000 already paid, this payment of 10,000 takes it to 35,000 — crosses 30,000.
        result = compute_tds(TDSCategory.PROFESSIONAL_FEES, Decimal("10000"), Decimal("25000"))
        assert result.threshold_crossed_this_transaction is True
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("35000")
        assert result.tds_amount == Decimal("3500.00")  # 10% of 35,000

    def test_transaction_exactly_at_threshold_does_not_cross(self):
        # Cumulative becomes exactly 30,000 — spec is "exceeding", so this must NOT trigger.
        result = compute_tds(TDSCategory.PROFESSIONAL_FEES, Decimal("5000"), Decimal("25000"))
        assert result.threshold_crossed_this_transaction is False
        assert result.tds_applicable is False

    def test_subsequent_payment_after_crossing_taxes_only_itself(self):
        # Already at 35,000 (past threshold) from prior payments; new payment of 5,000.
        result = compute_tds(TDSCategory.PROFESSIONAL_FEES, Decimal("5000"), Decimal("35000"))
        assert result.threshold_crossed_this_transaction is False
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("5000")
        assert result.tds_amount == Decimal("500.00")


class TestComputeTdsRent:
    """Section 393 Table Item 5 — threshold ₹2,40,000/payee/FY, rate 10%."""

    def test_large_single_payment_crossing_threshold(self):
        result = compute_tds(TDSCategory.RENT, Decimal("300000"), Decimal("0"))
        assert result.threshold_crossed_this_transaction is True
        assert result.taxable_amount == Decimal("300000")
        assert result.tds_amount == Decimal("30000.00")


class TestComputeTdsPropertyPurchase:
    """Section 393 Table Item 8 — per-transaction threshold ₹50,00,000, rate 1%."""

    def test_below_per_transaction_threshold_no_tds(self):
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("4000000"))
        assert result.tds_applicable is False

    def test_above_per_transaction_threshold_taxes_whole_amount(self):
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("6000000"))
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("6000000")
        assert result.tds_amount == Decimal("60000.00")

    def test_cumulative_history_is_irrelevant_for_per_transaction_basis(self):
        # Even with prior cumulative payments, per-transaction basis only looks at this payment.
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("4000000"), Decimal("9000000"))
        assert result.tds_applicable is False


class TestComputeTdsNonResident:
    """Section 393(2) — no threshold, TDS from the first rupee."""

    def test_tds_applies_from_first_rupee(self):
        result = compute_tds(TDSCategory.NON_RESIDENT_PAYMENT, Decimal("1"))
        assert result.tds_applicable is True
        assert result.threshold_crossed_this_transaction is True
        assert result.taxable_amount == Decimal("1")


class TestComputeTdsUnclassified:
    def test_unclassified_category_never_applies_tds(self):
        result = compute_tds(TDSCategory.UNCLASSIFIED, Decimal("1000000"))
        assert result.rule is None
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")
