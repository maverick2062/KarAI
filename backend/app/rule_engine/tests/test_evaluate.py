from decimal import Decimal

import pytest

from app.explainability.renderer import render_explanation
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

    @pytest.mark.parametrize(
        "description",
        ["Payment to parent", "Current account charges"],
    )
    def test_keyword_match_does_not_match_inside_other_words(self, description):
        assert classify_category(description) == TDSCategory.UNCLASSIFIED

    def test_overlapping_keyword_matches_require_explicit_category(self):
        assert classify_category("interest on rent deposit") == TDSCategory.UNCLASSIFIED

    def test_explicit_category_resolves_ambiguous_description(self):
        assert (
            classify_category(
                "interest on rent deposit",
                declared_category="interest_other_than_securities",
            )
            == TDSCategory.INTEREST_OTHER_THAN_SECURITIES
        )


class TestComputeTdsProfessionalFees:
    """Exercise professional-fee behavior against the configured advisory rule."""

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
    """Exercise rent behavior against the configured advisory rule."""

    def test_large_single_payment_crossing_threshold(self):
        result = compute_tds(TDSCategory.RENT, Decimal("300000"), Decimal("0"))
        assert result.threshold_crossed_this_transaction is True
        assert result.taxable_amount == Decimal("300000")
        assert result.tds_amount == Decimal("30000.00")


class TestComputeTdsContractorPayments:
    """Exercise contractor threshold behavior against the configured advisory rule."""

    def test_single_payment_at_threshold_does_not_trigger_tds(self):
        result = compute_tds(TDSCategory.CONTRACTOR_PAYMENTS, Decimal("30000"))
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")

    def test_annual_aggregate_at_threshold_does_not_trigger_tds(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("30000"),
            Decimal("70000"),
        )
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")

    def test_single_payment_above_threshold_triggers_on_that_payment(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("35000"),
            Decimal("20000"),
        )
        assert result.threshold_crossed_this_transaction is True
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("35000")
        assert result.tds_amount == Decimal("700.00")
        assert result.single_payment_threshold_triggered is True

        explanation = render_explanation(result, "Acme Contractors")
        assert "₹30,000.00 single-payment threshold" in explanation
        assert "₹700.00" in explanation

    def test_annual_threshold_crossing_catches_up_on_full_cumulative_amount(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("10000"),
            Decimal("95000"),
        )
        assert result.threshold_crossed_this_transaction is True
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("105000")
        assert result.tds_amount == Decimal("2100.00")
        assert result.single_payment_threshold_triggered is False

    def test_payment_after_annual_threshold_is_taxed_even_when_below_single_threshold(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("5000"),
            Decimal("105000"),
        )
        assert result.threshold_crossed_this_transaction is False
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("5000")
        assert result.tds_amount == Decimal("100.00")


class TestComputeTdsPropertyPurchase:
    """Exercise property behavior against the configured advisory rule."""

    def test_below_per_transaction_threshold_no_tds(self):
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("4000000"))
        assert result.tds_applicable is False

    def test_above_per_transaction_threshold_taxes_whole_amount(self):
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("6000000"))
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("6000000")
        assert result.tds_amount == Decimal("60000.00")

    def test_at_threshold_triggers_tds(self):
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("5000000"))
        assert result.tds_applicable is True
        assert result.tds_amount == Decimal("50000.00")

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

    def test_missing_pan_uses_higher_of_twenty_percent_or_rule_rate(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("40000"),
            pan_provided=False,
        )
        assert result.tds_applicable is True
        assert result.pan_not_provided is True
        assert result.rate_percent == Decimal("20")
        assert result.tds_amount == Decimal("8000.00")
        assert "PAN was not furnished" in render_explanation(result, "Consultant")

    def test_missing_pan_does_not_reduce_rule_rate_above_twenty_percent(self):
        result = compute_tds(
            TDSCategory.LOTTERY_WINNINGS,
            Decimal("20000"),
            pan_provided=False,
        )
        assert result.rate_percent == Decimal("30")

    def test_unknown_pan_status_preserves_scheduled_rate(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("40000"),
        )
        assert result.rate_percent == Decimal("10")
        assert result.pan_not_provided is False


class TestComputeTdsUnclassified:
    def test_unclassified_category_never_applies_tds(self):
        result = compute_tds(TDSCategory.UNCLASSIFIED, Decimal("1000000"))
        assert result.rule is None
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
def test_compute_tds_rejects_non_positive_or_non_finite_transaction_amounts(amount):
    with pytest.raises(ValueError, match="finite and greater than zero"):
        compute_tds(TDSCategory.RENT, amount)


@pytest.mark.parametrize("cumulative", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
def test_compute_tds_rejects_invalid_cumulative_amount(cumulative):
    with pytest.raises(ValueError, match="finite and non-negative"):
        compute_tds(TDSCategory.RENT, Decimal("1"), cumulative)


def test_compute_tds_rejects_float_amounts():
    with pytest.raises(TypeError, match="must be Decimal"):
        compute_tds(TDSCategory.RENT, 1.0)
