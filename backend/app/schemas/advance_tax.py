from decimal import Decimal

from pydantic import BaseModel

from app.models.advance_tax import TaxRegime


class EstimateRequest(BaseModel):
    financial_year: str
    total_income_estimate: Decimal
    regime: TaxRegime
    paid_so_far: Decimal = Decimal("0")


class RegimeComparisonResponse(BaseModel):
    total_income: Decimal
    old_regime_tax: Decimal
    new_regime_tax: Decimal
    recommended_regime: TaxRegime
    savings_with_recommended: Decimal
    slab_version: str


class QuarterlyInstallmentOut(BaseModel):
    label: str
    due_date: str
    cumulative_percent_required: Decimal
    cumulative_amount_required: Decimal
    already_paid: Decimal
    installment_due: Decimal
    is_short: bool
    interest_234c: Decimal


class AdvanceTaxProjectionResponse(BaseModel):
    financial_year: str
    total_income_estimate: Decimal
    regime: TaxRegime
    tax_liability: Decimal
    advance_tax_required: bool
    installments: list[QuarterlyInstallmentOut]
    interest_234b: Decimal
    slab_version: str
