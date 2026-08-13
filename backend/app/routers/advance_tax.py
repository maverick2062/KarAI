from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.advance_tax.projector import compare_regimes, project_advance_tax
from app.audit.logger import record_audit_log
from app.db import get_db
from app.models.advance_tax import AdvanceTaxEstimate
from app.models.user import User
from app.routers.deps import get_current_user
from app.rule_engine.section_393 import RULE_TABLE_VERSION
from app.schemas.advance_tax import (
    AdvanceTaxProjectionResponse,
    EstimateRequest,
    QuarterlyInstallmentOut,
    RegimeComparisonResponse,
)

router = APIRouter(prefix="/api/v1/advance-tax", tags=["advance-tax"])


@router.get("/compare-regimes", response_model=RegimeComparisonResponse)
def compare_regimes_endpoint(
    total_income: Decimal = Query(gt=0),
    current_user: User = Depends(get_current_user),
):
    comparison = compare_regimes(total_income)
    return RegimeComparisonResponse(**comparison.__dict__)


@router.post("/estimate", response_model=AdvanceTaxProjectionResponse)
def estimate_advance_tax(
    payload: EstimateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    projection = project_advance_tax(
        financial_year=payload.financial_year,
        total_income_estimate=payload.total_income_estimate,
        regime=payload.regime,
        paid_so_far=payload.paid_so_far,
    )

    for installment in projection.installments:
        db.add(
            AdvanceTaxEstimate(
                user_id=current_user.id,
                financial_year=projection.financial_year,
                quarter=int(installment.label[1]),
                regime=projection.regime,
                total_income_estimate=projection.total_income_estimate,
                tax_liability=projection.tax_liability,
                installment_due=installment.installment_due,
                interest_234b=projection.interest_234b if installment.label == "Q4" else Decimal("0"),
                interest_234c=installment.interest_234c,
                slab_version=projection.slab_version,
            )
        )

    record_audit_log(
        db,
        user_id=current_user.id,
        action="advance_tax_estimate_computed",
        rule_table_version=RULE_TABLE_VERSION,
        details={"financial_year": payload.financial_year, "regime": payload.regime.value},
    )
    db.commit()

    return AdvanceTaxProjectionResponse(
        financial_year=projection.financial_year,
        total_income_estimate=projection.total_income_estimate,
        regime=projection.regime,
        tax_liability=projection.tax_liability,
        advance_tax_required=projection.advance_tax_required,
        installments=[QuarterlyInstallmentOut(**i.__dict__) for i in projection.installments],
        interest_234b=projection.interest_234b,
        slab_version=projection.slab_version,
    )
