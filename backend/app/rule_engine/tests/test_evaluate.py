from decimal import Decimal

import pytest

from app.explainability.renderer import render_explanation
from app.rule_engine.context import RuleContext
from app.rule_engine.evaluate import classify_category, compute_tds
from app.rule_engine.section_393 import TDSCategory, TDSDecisionStatus


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

    def test_nonresident_payee_overrides_resident_category(self):
        assert classify_category(
            "crypto asset transfer",
            declared_category="virtual_digital_assets",
            payee_is_non_resident=True,
        ) == TDSCategory.NON_RESIDENT_PAYMENT


class TestComputeTdsProfessionalFees:
    """Exercise professional-fee behavior against the configured advisory rule."""

    def test_below_threshold_no_tds(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("10000"),
            Decimal("5000"),
            context=RuleContext(payer_is_specified_person=True, service_kind="professional"),
        )
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")
        assert result.cumulative_after == Decimal("15000")

    def test_transaction_that_crosses_threshold_taxes_full_cumulative(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("10000"),
            Decimal("45000"),
            context=RuleContext(payer_is_specified_person=True, service_kind="professional"),
        )
        assert result.threshold_crossed_this_transaction is True
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("55000")
        assert result.tds_amount == Decimal("5500.00")

    def test_transaction_exactly_at_threshold_does_not_cross(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("5000"),
            Decimal("45000"),
            context=RuleContext(payer_is_specified_person=True, service_kind="professional"),
        )
        assert result.threshold_crossed_this_transaction is False
        assert result.tds_applicable is False

    def test_subsequent_payment_after_crossing_taxes_only_itself(self):
        # Already at 35,000 (past threshold) from prior payments; new payment of 5,000.
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("5000"),
            Decimal("55000"),
            context=RuleContext(payer_is_specified_person=True, service_kind="professional"),
        )
        assert result.threshold_crossed_this_transaction is False
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("5000")
        assert result.tds_amount == Decimal("500.00")


class TestComputeTdsRent:
    """Exercise rent behavior against the configured advisory rule."""

    def test_rent_requires_monthly_context_before_calculation(self):
        result = compute_tds(TDSCategory.RENT, Decimal("300000"), Decimal("0"))
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None


class TestContextualTdsRules:
    def test_professional_fee_requires_payer_and_service_facts(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("60000"),
        )
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None
        assert "payer type" in result.review_reason

    def test_technical_service_uses_contextual_threshold_and_rate(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("60000"),
            context=RuleContext(payer_is_specified_person=True, service_kind="technical"),
        )
        assert result.decision_status == TDSDecisionStatus.APPLICABLE
        assert result.rate_percent == Decimal("2")
        assert result.tds_amount == Decimal("1200.00")

    def test_contractor_rate_depends_on_payee_classification(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("35000"),
            context=RuleContext(
                payer_is_designated_person=True,
                payee_is_individual_or_huf=True,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.APPLICABLE
        assert result.rate_percent == Decimal("1")
        assert result.tds_amount == Decimal("350.00")

    def test_commission_requires_specified_payer_fact(self):
        result = compute_tds(TDSCategory.COMMISSION_BROKERAGE, Decimal("25000"))
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_dividend_exception_requires_context_and_qualifying_facts(self):
        unresolved = compute_tds(TDSCategory.DIVIDEND, Decimal("5000"))
        assert unresolved.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert unresolved.tds_amount is None

        exempt = compute_tds(
            TDSCategory.DIVIDEND,
            Decimal("5000"),
            context=RuleContext(
                payee_is_individual_shareholder=True,
                dividend_payment_is_non_cash=True,
            ),
        )
        assert exempt.decision_status == TDSDecisionStatus.NOT_APPLICABLE
        assert exempt.tds_amount == Decimal("0")

    def test_property_requires_both_valuation_inputs(self):
        result = compute_tds(TDSCategory.PROPERTY_PURCHASE, Decimal("4000000"))
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_property_installment_remains_unresolved(self):
        result = compute_tds(
            TDSCategory.PROPERTY_PURCHASE,
            Decimal("2000000"),
            context=RuleContext(
                property_stamp_duty_value=Decimal("6000000"),
                property_consideration_total=Decimal("5500000"),
                property_payment_is_full_consideration=False,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_property_value_mismatch_remains_unresolved(self):
        result = compute_tds(
            TDSCategory.PROPERTY_PURCHASE,
            Decimal("5000000"),
            context=RuleContext(
                property_stamp_duty_value=Decimal("6000000"),
                property_consideration_total=Decimal("5500000"),
                property_payment_is_full_consideration=True,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_vda_requires_payer_classification(self):
        result = compute_tds(TDSCategory.VIRTUAL_DIGITAL_ASSETS, Decimal("20000"))
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_vda_qualifying_individual_payer_uses_50000_threshold(self):
        context = RuleContext(
            vda_consideration_is_cash=True,
            vda_payer_is_individual_or_huf=True,
            vda_payer_turnover_within_limit=True,
            vda_payer_has_business_income=False,
        )
        at_threshold = compute_tds(
            TDSCategory.VIRTUAL_DIGITAL_ASSETS,
            Decimal("50000"),
            context=context,
        )
        over_threshold = compute_tds(
            TDSCategory.VIRTUAL_DIGITAL_ASSETS,
            Decimal("50001"),
            context=context,
        )
        assert at_threshold.decision_status == TDSDecisionStatus.NOT_APPLICABLE
        assert at_threshold.tds_amount == Decimal("0")
        assert over_threshold.decision_status == TDSDecisionStatus.APPLICABLE
        assert over_threshold.tds_amount == Decimal("500.01")

    def test_vda_other_payers_use_10000_threshold(self):
        result = compute_tds(
            TDSCategory.VIRTUAL_DIGITAL_ASSETS,
            Decimal("10001"),
            context=RuleContext(
                vda_consideration_is_cash=True,
                vda_payer_is_individual_or_huf=False,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.APPLICABLE
        assert result.rate_percent == Decimal("1")
        assert result.tds_amount == Decimal("100.01")

    def test_vda_individual_payer_without_eligibility_uses_10000_threshold(self):
        result = compute_tds(
            TDSCategory.VIRTUAL_DIGITAL_ASSETS,
            Decimal("10001"),
            context=RuleContext(
                vda_consideration_is_cash=True,
                vda_payer_is_individual_or_huf=True,
                vda_payer_turnover_within_limit=False,
                vda_payer_has_business_income=False,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.APPLICABLE
        assert result.rule.threshold_amount == Decimal("10000")

    def test_vda_non_cash_consideration_requires_review(self):
        result = compute_tds(
            TDSCategory.VIRTUAL_DIGITAL_ASSETS,
            Decimal("10001"),
            context=RuleContext(
                vda_consideration_is_cash=False,
                vda_payer_is_individual_or_huf=False,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_vda_qualifying_threshold_crossing_catches_up_on_aggregate(self):
        result = compute_tds(
            TDSCategory.VIRTUAL_DIGITAL_ASSETS,
            Decimal("10000"),
            Decimal("45001"),
            context=RuleContext(
                vda_consideration_is_cash=True,
                vda_payer_is_individual_or_huf=True,
                vda_payer_turnover_within_limit=True,
                vda_payer_has_business_income=False,
            ),
        )
        assert result.threshold_crossed_this_transaction is True
        assert result.taxable_amount == Decimal("55001")
        assert result.tds_amount == Decimal("550.01")

    def test_lottery_winnings_use_per_transaction_threshold_and_rate(self):
        cash_winnings = RuleContext(
            lottery_winnings_kind="lottery",
            lottery_winnings_are_cash=True,
        )
        below = compute_tds(TDSCategory.LOTTERY_WINNINGS, Decimal("10000"), context=cash_winnings)
        above = compute_tds(TDSCategory.LOTTERY_WINNINGS, Decimal("10001"), context=cash_winnings)
        assert below.decision_status == TDSDecisionStatus.NOT_APPLICABLE
        assert below.tds_amount == Decimal("0")
        assert above.decision_status == TDSDecisionStatus.APPLICABLE
        assert above.rate_percent == Decimal("30")
        assert above.tds_amount == Decimal("3000.30")


class TestComputeTdsContractorPayments:
    """Exercise contractor threshold behavior against the configured advisory rule."""

    def test_single_payment_at_threshold_does_not_trigger_tds(self):
        result = compute_tds(TDSCategory.CONTRACTOR_PAYMENTS, Decimal("30000"))
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_annual_aggregate_at_threshold_does_not_trigger_tds(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("30000"),
            Decimal("70000"),
            context=RuleContext(payer_is_designated_person=True, payee_is_individual_or_huf=True),
        )
        assert result.tds_applicable is False
        assert result.tds_amount == Decimal("0")

    def test_single_payment_above_threshold_triggers_on_that_payment(self):
        result = compute_tds(
            TDSCategory.CONTRACTOR_PAYMENTS,
            Decimal("35000"),
            Decimal("20000"),
            context=RuleContext(payer_is_designated_person=True, payee_is_individual_or_huf=False),
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
            context=RuleContext(payer_is_designated_person=True, payee_is_individual_or_huf=False),
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
            context=RuleContext(payer_is_designated_person=True, payee_is_individual_or_huf=False),
        )
        assert result.threshold_crossed_this_transaction is False
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("5000")
        assert result.tds_amount == Decimal("100.00")


class TestComputeTdsPropertyPurchase:
    """Exercise property behavior against the configured advisory rule."""

    def test_below_per_transaction_threshold_no_tds(self):
        result = compute_tds(
            TDSCategory.PROPERTY_PURCHASE,
            Decimal("4000000"),
            context=RuleContext(
                property_stamp_duty_value=Decimal("4000000"),
                property_consideration_total=Decimal("4000000"),
                property_payment_is_full_consideration=True,
            ),
        )
        assert result.tds_applicable is False
        explanation = render_explanation(result, "Buyer")
        assert "₹40,00,000.00" in explanation
        assert "₹10,00,000.00 remaining" in explanation

    def test_above_per_transaction_threshold_taxes_whole_amount(self):
        result = compute_tds(
            TDSCategory.PROPERTY_PURCHASE,
            Decimal("6000000"),
            context=RuleContext(
                property_stamp_duty_value=Decimal("6000000"),
                property_consideration_total=Decimal("6000000"),
                property_payment_is_full_consideration=True,
            ),
        )
        assert result.tds_applicable is True
        assert result.taxable_amount == Decimal("6000000")
        assert result.tds_amount == Decimal("60000.00")

    def test_at_threshold_triggers_tds(self):
        result = compute_tds(
            TDSCategory.PROPERTY_PURCHASE,
            Decimal("5000000"),
            context=RuleContext(
                property_stamp_duty_value=Decimal("5000000"),
                property_consideration_total=Decimal("5000000"),
                property_payment_is_full_consideration=True,
            ),
        )
        assert result.tds_applicable is True
        assert result.tds_amount == Decimal("50000.00")

    def test_cumulative_history_is_irrelevant_for_per_transaction_basis(self):
        # Even with prior cumulative payments, per-transaction basis only looks at this payment.
        result = compute_tds(
            TDSCategory.PROPERTY_PURCHASE,
            Decimal("4000000"),
            Decimal("9000000"),
            context=RuleContext(
                property_stamp_duty_value=Decimal("4000000"),
                property_consideration_total=Decimal("4000000"),
                property_payment_is_full_consideration=True,
            ),
        )
        assert result.tds_applicable is False


class TestComputeTdsNonResident:
    """Section 393(2) — no threshold, TDS from the first rupee."""

    def test_tds_applies_from_first_rupee(self):
        result = compute_tds(TDSCategory.NON_RESIDENT_PAYMENT, Decimal("1"))
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW
        assert result.tds_amount is None

    def test_missing_pan_uses_higher_of_twenty_percent_or_rule_rate(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("55000"),
            pan_provided=False,
            context=RuleContext(payer_is_specified_person=True, service_kind="professional"),
        )
        assert result.tds_applicable is True
        assert result.pan_not_provided is True
        assert result.rate_percent == Decimal("20")
        assert result.tds_amount == Decimal("11000.00")
        assert "PAN was not furnished" in render_explanation(result, "Consultant")

    def test_missing_pan_does_not_reduce_rule_rate_above_twenty_percent(self):
        result = compute_tds(
            TDSCategory.LOTTERY_WINNINGS,
            Decimal("20000"),
            pan_provided=False,
            context=RuleContext(
                lottery_winnings_kind="lottery",
                lottery_winnings_are_cash=True,
            ),
        )
        assert result.decision_status == TDSDecisionStatus.APPLICABLE
        assert result.rate_percent == Decimal("30")
        assert result.tds_amount == Decimal("6000.00")
        explanation = render_explanation(result, "Winner")
        assert "PAN was not furnished" in explanation
        assert "30%" in explanation

    def test_unknown_pan_status_preserves_scheduled_rate(self):
        result = compute_tds(
            TDSCategory.PROFESSIONAL_FEES,
            Decimal("55000"),
            context=RuleContext(payer_is_specified_person=True, service_kind="professional"),
        )
        assert result.rate_percent == Decimal("10")
        assert result.pan_not_provided is False


class TestComputeTdsUnclassified:
    def test_unclassified_category_never_applies_tds(self):
        result = compute_tds(TDSCategory.UNCLASSIFIED, Decimal("1000000"))
        assert result.rule is None
        assert result.tds_applicable is False
        assert result.tds_amount is None
        assert result.decision_status == TDSDecisionStatus.NEEDS_REVIEW


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
