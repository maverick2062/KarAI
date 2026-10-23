"""Advance tax liability projection: tax computation under both regimes, and
the quarterly installment schedule with Section 234B/234C interest estimates.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.advance_tax.slabs import (
    CESS_RATE,
    NEW_REGIME_87A_MAX_REBATE,
    NEW_REGIME_87A_REBATE_INCOME_LIMIT,
    NEW_REGIME_SLABS,
    OLD_REGIME_87A_MAX_REBATE,
    OLD_REGIME_87A_REBATE_INCOME_LIMIT,
    OLD_REGIME_SLABS,
    SLAB_VERSION,
    SlabBand,
)
from app.models.advance_tax import TaxRegime

ADVANCE_TAX_LIABILITY_THRESHOLD = Decimal("10000")  # Section 208 — no advance tax if liability below this
INTEREST_RATE_PER_MONTH = Decimal("0.01")  # 1%/month for both 234B and 234C

# (label, due_month, due_day, cumulative_percent_required, months_of_234c_interest_if_short)
INSTALLMENT_SCHEDULE: tuple[tuple[str, int, int, Decimal, int], ...] = (
    ("Q1", 6, 15, Decimal("0.15"), 3),
    ("Q2", 9, 15, Decimal("0.45"), 3),
    ("Q3", 12, 15, Decimal("0.75"), 3),
    ("Q4", 3, 15, Decimal("1.00"), 1),
)


def _round_currency(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _tax_from_slabs(total_income: Decimal, slabs: tuple[SlabBand, ...]) -> Decimal:
    tax = Decimal("0")
    for band in slabs:
        if total_income <= band.lower:
            continue
        band_top = band.upper if band.upper is not None else total_income
        taxable_in_band = min(total_income, band_top) - band.lower
        if taxable_in_band > 0:
            tax += taxable_in_band * band.rate
    return tax


def compute_tax_liability(total_income: Decimal, regime: TaxRegime) -> Decimal:
    """Total tax liability including cess, applying the Section 87A rebate.
    Surcharge is NOT modeled (see slabs.py docstring)."""
    if regime == TaxRegime.NEW:
        slabs, rebate_limit, max_rebate = NEW_REGIME_SLABS, NEW_REGIME_87A_REBATE_INCOME_LIMIT, NEW_REGIME_87A_MAX_REBATE
    else:
        slabs, rebate_limit, max_rebate = OLD_REGIME_SLABS, OLD_REGIME_87A_REBATE_INCOME_LIMIT, OLD_REGIME_87A_MAX_REBATE

    base_tax = _tax_from_slabs(total_income, slabs)

    if total_income <= rebate_limit:
        rebate = min(base_tax, max_rebate)
        base_tax -= rebate
    elif regime == TaxRegime.NEW:
        # Marginal relief: just above the rebate cliff, tax payable is capped
        # at (income - rebate_limit) under the new regime.
        marginal_cap = total_income - rebate_limit
        if base_tax > marginal_cap:
            base_tax = marginal_cap

    total_with_cess = base_tax * (Decimal("1") + CESS_RATE)
    return _round_currency(total_with_cess)


@dataclass(frozen=True)
class RegimeComparison:
    total_income: Decimal
    old_regime_tax: Decimal
    new_regime_tax: Decimal
    recommended_regime: TaxRegime
    savings_with_recommended: Decimal
    slab_version: str = SLAB_VERSION


def compare_regimes(total_income: Decimal) -> RegimeComparison:
    old_tax = compute_tax_liability(total_income, TaxRegime.OLD)
    new_tax = compute_tax_liability(total_income, TaxRegime.NEW)
    if new_tax <= old_tax:
        recommended, savings = TaxRegime.NEW, old_tax - new_tax
    else:
        recommended, savings = TaxRegime.OLD, new_tax - old_tax
    return RegimeComparison(total_income, old_tax, new_tax, recommended, savings)


@dataclass(frozen=True)
class QuarterlyInstallment:
    label: str
    due_date: str
    cumulative_percent_required: Decimal
    cumulative_amount_required: Decimal
    already_paid: Decimal
    installment_due: Decimal
    is_short: bool
    interest_234c: Decimal


@dataclass(frozen=True)
class AdvanceTaxProjection:
    financial_year: str
    total_income_estimate: Decimal
    regime: TaxRegime
    tax_liability: Decimal
    advance_tax_required: bool
    installments: list[QuarterlyInstallment] = field(default_factory=list)
    interest_234b: Decimal = Decimal("0")
    slab_version: str = SLAB_VERSION


def _fy_start_year(financial_year: str) -> int:
    return int(financial_year.split("-")[0])


def project_advance_tax(
    financial_year: str,
    total_income_estimate: Decimal,
    regime: TaxRegime,
    paid_so_far: Decimal = Decimal("0"),
    as_of: date | None = None,
) -> AdvanceTaxProjection:
    """Project the quarterly advance-tax installment schedule and estimate
    Section 234B/234C interest for underpayment, given a running total of
    what the user reports having already paid this FY.
    """
    tax_liability = compute_tax_liability(total_income_estimate, regime)

    if tax_liability < ADVANCE_TAX_LIABILITY_THRESHOLD:
        return AdvanceTaxProjection(
            financial_year=financial_year,
            total_income_estimate=total_income_estimate,
            regime=regime,
            tax_liability=tax_liability,
            advance_tax_required=False,
        )

    fy_start_year = _fy_start_year(financial_year)
    as_of = as_of or date.today()

    installments: list[QuarterlyInstallment] = []
    cumulative_paid_assumed = Decimal("0")

    for label, month, day, cumulative_pct, interest_months in INSTALLMENT_SCHEDULE:
        due_year = fy_start_year if month >= 4 else fy_start_year + 1
        due_date = date(due_year, month, day)

        cumulative_required = _round_currency(tax_liability * cumulative_pct)
        installment_due = max(Decimal("0"), cumulative_required - cumulative_paid_assumed)
        is_short = due_date <= as_of and paid_so_far < cumulative_required
        shortfall = max(Decimal("0"), cumulative_required - paid_so_far) if is_short else Decimal("0")
        interest = _round_currency(shortfall * INTEREST_RATE_PER_MONTH * interest_months) if is_short else Decimal("0")

        installments.append(
            QuarterlyInstallment(
                label=label,
                due_date=due_date.isoformat(),
                cumulative_percent_required=cumulative_pct,
                cumulative_amount_required=cumulative_required,
                already_paid=paid_so_far,
                installment_due=installment_due,
                is_short=is_short,
                interest_234c=interest,
            )
        )
        cumulative_paid_assumed = cumulative_required

    fy_end = date(fy_start_year + 1, 3, 31)
    interest_234b = Decimal("0")
    if as_of > fy_end and paid_so_far < tax_liability * Decimal("0.9"):
        months_overdue = (as_of.year - fy_end.year) * 12 + (as_of.month - fy_end.month) + 1
        shortfall = tax_liability - paid_so_far
        interest_234b = _round_currency(shortfall * INTEREST_RATE_PER_MONTH * max(months_overdue, 1))

    return AdvanceTaxProjection(
        financial_year=financial_year,
        total_income_estimate=total_income_estimate,
        regime=regime,
        tax_liability=tax_liability,
        advance_tax_required=True,
        installments=installments,
        interest_234b=interest_234b,
    )
