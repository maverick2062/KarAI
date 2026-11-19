from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.advance_tax import TaxRegime


class EstimateRequest(BaseModel):
    financial_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    total_income_estimate: Decimal = Field(gt=0, allow_inf_nan=False)
    regime: TaxRegime
    paid_so_far: Decimal = Field(default=Decimal("0"), ge=0, allow_inf_nan=False)

    @field_validator("financial_year")
    @classmethod
    def validate_financial_year(cls, value: str) -> str:
        start_year, end_year = (int(part) for part in value.split("-"))
        if start_year < 1 or end_year != (start_year + 1) % 100:
            raise ValueError("Financial year must span consecutive calendar years.")
        return value


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
