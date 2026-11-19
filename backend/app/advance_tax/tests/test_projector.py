from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.advance_tax.projector import compare_regimes, compute_tax_liability, project_advance_tax
from app.models.advance_tax import TaxRegime
from app.schemas.advance_tax import EstimateRequest


class TestComputeTaxLiability:
    def test_new_regime_fully_rebated_below_12_lakh(self):
        assert compute_tax_liability(Decimal("1000000"), TaxRegime.NEW) == Decimal("0")

    def test_new_regime_exactly_at_rebate_limit_is_nil(self):
        assert compute_tax_liability(Decimal("1200000"), TaxRegime.NEW) == Decimal("0")

    def test_new_regime_above_rebate_limit_taxed_normally(self):
        # 15L: 0-4:0, 4-8:20000 (5%), 8-12:40000 (10%), 12-15:45000 (15%) = 105000 base, *1.04 cess
        assert compute_tax_liability(Decimal("1500000"), TaxRegime.NEW) == Decimal("109200.00")

    def test_new_regime_marginal_relief_near_cliff(self):
        # 12.1L: base tax would be 21,500 but income-over-limit is only 10,000 -> capped there
        assert compute_tax_liability(Decimal("1210000"), TaxRegime.NEW) == Decimal("10400.00")

    def test_old_regime_no_rebate_above_5_lakh(self):
        # 10L: 0-2.5:0, 2.5-5:12500, 5-10:100000 = 112500 base, *1.04 cess
        assert compute_tax_liability(Decimal("1000000"), TaxRegime.OLD) == Decimal("117000.00")

    def test_old_regime_fully_rebated_at_5_lakh(self):
        assert compute_tax_liability(Decimal("500000"), TaxRegime.OLD) == Decimal("0")

    def test_old_regime_does_not_receive_marginal_relief_above_rebate_limit(self):
        assert compute_tax_liability(Decimal("500001"), TaxRegime.OLD) == Decimal("13000.21")

    def test_zero_income_has_zero_tax_under_both_regimes(self):
        assert compute_tax_liability(Decimal("0"), TaxRegime.NEW) == Decimal("0")
        assert compute_tax_liability(Decimal("0"), TaxRegime.OLD) == Decimal("0")


class TestCompareRegimes:
    def test_recommends_new_regime_when_cheaper(self):
        comparison = compare_regimes(Decimal("1000000"))
        assert comparison.recommended_regime == TaxRegime.NEW
        assert comparison.new_regime_tax == Decimal("0")
        assert comparison.old_regime_tax == Decimal("117000.00")
        assert comparison.savings_with_recommended == Decimal("117000.00")


class TestProjectAdvanceTax:
    @pytest.mark.parametrize("financial_year", ["FY26", "2026", "2026-7", "2026-28", "0000-01"])
    def test_estimate_request_rejects_malformed_financial_year(self, financial_year):
        with pytest.raises(ValidationError):
            EstimateRequest(
                financial_year=financial_year,
                total_income_estimate=Decimal("100000"),
                regime=TaxRegime.NEW,
            )

    @pytest.mark.parametrize(
        ("total_income_estimate", "paid_so_far"),
        [
            (Decimal("-1"), Decimal("0")),
            (Decimal("NaN"), Decimal("0")),
            (Decimal("1000"), Decimal("-1")),
            (Decimal("1000"), Decimal("Infinity")),
        ],
    )
    def test_estimate_request_rejects_invalid_money_values(self, total_income_estimate, paid_so_far):
        with pytest.raises(ValidationError):
            EstimateRequest(
                financial_year="2026-27",
                total_income_estimate=total_income_estimate,
                regime=TaxRegime.NEW,
                paid_so_far=paid_so_far,
            )

    def test_projector_rejects_malformed_financial_year_even_when_liability_is_below_threshold(self):
        with pytest.raises(ValueError, match="Financial year"):
            project_advance_tax("FY26", Decimal("100"), TaxRegime.NEW)

    def test_below_liability_threshold_does_not_require_advance_tax(self):
        projection = project_advance_tax("2026-27", Decimal("800000"), TaxRegime.NEW)
        assert projection.advance_tax_required is False
        assert projection.installments == []

    def test_quarterly_schedule_percentages_for_liable_taxpayer(self):
        projection = project_advance_tax(
            "2026-27", Decimal("1500000"), TaxRegime.NEW, paid_so_far=Decimal("0"), as_of=date(2026, 5, 1)
        )
        assert projection.advance_tax_required is True
        assert [i.label for i in projection.installments] == ["Q1", "Q2", "Q3", "Q4"]
        assert projection.installments[0].cumulative_percent_required == Decimal("0.15")
        assert projection.installments[0].cumulative_amount_required == projection.tax_liability * Decimal("0.15")
        assert projection.installments[3].cumulative_percent_required == Decimal("1.00")

        # As of May 1 (before Q1's June 15 due date), nothing is short yet.
        assert all(i.is_short is False for i in projection.installments)

    def test_missed_q1_installment_accrues_234c_interest(self):
        projection = project_advance_tax(
            "2026-27", Decimal("1500000"), TaxRegime.NEW, paid_so_far=Decimal("0"), as_of=date(2026, 7, 1)
        )
        q1 = projection.installments[0]
        assert q1.is_short is True
        assert q1.interest_234c > Decimal("0")
        # Q2, due Sept 15, hasn't passed yet as of July 1.
        assert projection.installments[1].is_short is False

    def test_234b_interest_applies_after_fy_end_if_underpaid(self):
        liability = compute_tax_liability(Decimal("1500000"), TaxRegime.NEW)
        projection = project_advance_tax(
            "2026-27",
            Decimal("1500000"),
            TaxRegime.NEW,
            paid_so_far=Decimal("0"),
            as_of=date(2026, 6, 15),  # after FY2026-27 ends (31 Mar 2027)... wait, use post-FY date below
        )
        # Re-run with a date genuinely after FY end (31 Mar 2027) to check 234B.
        projection_after_fy = project_advance_tax(
            "2026-27", Decimal("1500000"), TaxRegime.NEW, paid_so_far=Decimal("0"), as_of=date(2027, 5, 1)
        )
        assert projection_after_fy.interest_234b > Decimal("0")
        assert liability == projection_after_fy.tax_liability

    def test_no_234b_interest_if_paid_over_90_percent(self):
        liability = compute_tax_liability(Decimal("1500000"), TaxRegime.NEW)
        projection = project_advance_tax(
            "2026-27",
            Decimal("1500000"),
            TaxRegime.NEW,
            paid_so_far=liability,  # fully paid
            as_of=date(2027, 5, 1),
        )
        assert projection.interest_234b == Decimal("0")
