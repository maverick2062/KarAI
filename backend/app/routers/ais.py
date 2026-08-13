from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.ais_mock.diffing import ReportedAmount, find_discrepancies
from app.ais_mock.mock_upload import parse_ais_csv
from app.ais_mock.synthetic_ais import AISRecordInput, generate_synthetic_ais
from app.audit.logger import record_audit_log
from app.db import get_db
from app.models.ais_record import AISRecord, AISSourceType
from app.models.transaction import Transaction
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.ais import DiscrepancyOut, DiscrepancyResponse, SimulateAISRequest
from app.sources.base import TransactionSourceError

router = APIRouter(prefix="/api/v1/ais", tags=["ais"])


def _reported_amounts_for_fy(db: Session, user_id: str, financial_year: str) -> list[ReportedAmount]:
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.financial_year == financial_year)
        .all()
    )
    return [
        ReportedAmount(
            vendor_name=t.vendor.name if t.vendor else "Unknown Payee",
            category=t.declared_category or "unclassified",
            amount=t.amount,
        )
        for t in transactions
    ]


def _persist_and_diff(
    db: Session,
    user_id: str,
    financial_year: str,
    source_type: AISSourceType,
    records,
) -> DiscrepancyResponse:
    for record in records:
        db.add(
            AISRecord(
                user_id=user_id,
                source_type=source_type,
                financial_year=financial_year,
                reporting_entity=record.reporting_entity,
                amount=record.amount,
                category=record.category,
            )
        )

    reported = _reported_amounts_for_fy(db, user_id, financial_year)
    discrepancies = find_discrepancies(records, reported)

    record_audit_log(
        db,
        user_id=user_id,
        action="ais_discrepancy_check",
        details={"financial_year": financial_year, "source_type": source_type.value, "discrepancy_count": len(discrepancies)},
    )
    db.commit()

    return DiscrepancyResponse(
        financial_year=financial_year,
        discrepancies=[DiscrepancyOut(**d.__dict__) for d in discrepancies],
    )


@router.post("/simulate", response_model=DiscrepancyResponse)
def simulate_ais(
    payload: SimulateAISRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id, Transaction.financial_year == payload.financial_year)
        .all()
    )
    synthetic_records = generate_synthetic_ais(transactions, seed=payload.seed)
    return _persist_and_diff(db, current_user.id, payload.financial_year, AISSourceType.SYNTHETIC, synthetic_records)


@router.post("/upload", response_model=DiscrepancyResponse)
async def upload_ais(
    financial_year: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    try:
        records = parse_ais_csv(file_bytes)
    except TransactionSourceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _persist_and_diff(db, current_user.id, financial_year, AISSourceType.USER_UPLOAD, records)


@router.get("/discrepancies", response_model=DiscrepancyResponse)
def get_discrepancies(
    financial_year: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ais_records = (
        db.query(AISRecord)
        .filter(AISRecord.user_id == current_user.id, AISRecord.financial_year == financial_year)
        .all()
    )
    record_inputs = [AISRecordInput(r.reporting_entity, r.amount, r.category) for r in ais_records]
    reported = _reported_amounts_for_fy(db, current_user.id, financial_year)
    discrepancies = find_discrepancies(record_inputs, reported)

    return DiscrepancyResponse(
        financial_year=financial_year,
        discrepancies=[DiscrepancyOut(**d.__dict__) for d in discrepancies],
    )
