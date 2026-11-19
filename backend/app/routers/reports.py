from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.advance_tax.projector import project_advance_tax
from app.audit.hashing import hash_dataset
from app.audit.logger import record_audit_log
from app.db import get_db
from app.models.advance_tax import AdvanceTaxEstimate
from app.models.report import Report, ReportType
from app.models.tds_event import TDSEvent
from app.models.transaction import Transaction, TransactionSourceType
from app.models.user import User
from app.reports.excel_report import generate_excel_report
from app.reports.pdf_report import generate_pdf_report
from app.reports.report_data import ReportInput, TDSEventRow
from app.routers.deps import get_current_user
from app.rule_engine.section_393 import RULE_TABLE_VERSION
from app.schemas.reports import GenerateReportRequest, ReportSummary

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _build_report_input(db: Session, user: User, financial_year: str) -> ReportInput:
    rows = (
        db.query(TDSEvent, Transaction)
        .join(Transaction, TDSEvent.transaction_id == Transaction.id)
        .filter(
            TDSEvent.user_id == user.id,
            Transaction.financial_year == financial_year,
            Transaction.is_deleted.is_(False),
            Transaction.source_type.in_(
                [TransactionSourceType.MANUAL_ENTRY, TransactionSourceType.CSV_UPLOAD]
            ),
        )
        .order_by(Transaction.transaction_date.asc())
        .all()
    )

    tds_event_rows = [
        TDSEventRow(
            transaction_date=txn.transaction_date,
            vendor_name=txn.vendor.name if txn.vendor else "Unknown Payee",
            category=event.category.value,
            amount=txn.amount,
            decision_status=event.decision_status,
            review_reason=event.review_reason,
            tds_applicable=event.tds_applicable,
            pan_not_provided=event.pan_not_provided,
            tds_amount=event.tds_amount,
            rate_percent=event.rate_percent,
            explanation=event.explanation_text,
            filing_form_reference=event.filing_form_reference,
            filing_deadline=event.filing_deadline,
        )
        for event, txn in rows
    ]

    latest_estimate = (
        db.query(AdvanceTaxEstimate)
        .filter(AdvanceTaxEstimate.user_id == user.id, AdvanceTaxEstimate.financial_year == financial_year)
        .order_by(AdvanceTaxEstimate.created_at.desc())
        .first()
    )
    advance_tax_projection = None
    if latest_estimate is not None:
        advance_tax_projection = project_advance_tax(
            financial_year, latest_estimate.total_income_estimate, latest_estimate.regime
        )

    dataset_hash = hash_dataset(f"{user.id}:{financial_year}:{len(tds_event_rows)}")

    return ReportInput(
        user_full_name=user.full_name,
        user_email=user.email,
        financial_year=financial_year,
        generated_at=datetime.now(timezone.utc),
        rule_table_version=RULE_TABLE_VERSION,
        dataset_hash=dataset_hash,
        tds_events=tds_event_rows,
        advance_tax=advance_tax_projection,
    )


@router.post("/generate", response_model=ReportSummary, status_code=status.HTTP_201_CREATED)
def generate_report(
    payload: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report_input = _build_report_input(db, current_user, payload.financial_year)

    if payload.report_type == ReportType.PDF:
        file_bytes = generate_pdf_report(report_input)
        file_name = f"karai-tds-report-{payload.financial_year}.pdf"
    else:
        file_bytes = generate_excel_report(report_input)
        file_name = f"karai-tds-report-{payload.financial_year}.xlsx"

    report = Report(
        user_id=current_user.id,
        report_type=payload.report_type,
        financial_year=payload.financial_year,
        file_name=file_name,
        file_bytes=file_bytes,
        dataset_hash=report_input.dataset_hash,
        rule_table_version=report_input.rule_table_version,
    )
    db.add(report)
    db.flush()

    record_audit_log(
        db,
        user_id=current_user.id,
        action="report_generated",
        rule_table_version=report_input.rule_table_version,
        dataset_hash=report_input.dataset_hash,
        details={"report_type": payload.report_type.value, "financial_year": payload.financial_year},
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[ReportSummary])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Report)
        .filter(Report.user_id == current_user.id)
        .order_by(Report.generated_at.desc())
        .all()
    )


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id, Report.user_id == current_user.id).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    media_type = "application/pdf" if report.report_type == ReportType.PDF else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return Response(
        content=report.file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{report.file_name}"'},
    )
