from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.audit.hashing import hash_dataset
from app.db import get_db
from app.models.transaction import Transaction, TransactionSourceType
from app.models.tds_event import TDSEvent
from app.models.user import User
from app.notifications import send_tds_event_email
from app.routers.deps import get_current_user
from app.schemas.transactions import (
    IngestionResponse,
    ManualIngestionRequest,
    SimulateFeedRequest,
    TransactionOut,
)
from app.sources.base import RawTransaction, TransactionSourceError
from app.sources.csv_source import CSVTransactionSource
from app.sources.synthetic_feed import SyntheticFeedGenerator
from app.tds_detector.detector import IngestionResult, ingest_transactions

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


def _queue_tds_notification(
    background_tasks: BackgroundTasks,
    user_email: str,
    events: list[TDSEvent],
) -> None:
    flagged_events = [event for event in events if event.tds_applicable]
    if not flagged_events:
        return

    notification_events = [
        {
            "vendor": event.transaction.vendor.name if event.transaction.vendor else "Payee",
            "category": event.category.value.replace("_", " "),
            "tds_amount": f"{event.tds_amount:,.2f}",
            "rate_percent": str(event.rate_percent),
            "pan_note": " (PAN not furnished)" if event.pan_not_provided else "",
        }
        for event in flagged_events
    ]
    background_tasks.add_task(send_tds_event_email, user_email, notification_events)


def _ingestion_response(result: IngestionResult) -> IngestionResponse:
    return IngestionResponse.model_validate(
        {
            "transactions_created": result.transactions_created,
            "tds_events_created": result.tds_events_created,
            "tds_events": result.tds_events,
        },
        from_attributes=True,
    )


@router.post("/upload-csv", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    try:
        raw_transactions = CSVTransactionSource(file_bytes).fetch()
    except TransactionSourceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    result = ingest_transactions(
        db,
        current_user.id,
        raw_transactions,
        TransactionSourceType.CSV_UPLOAD,
        dataset_hash=hash_dataset(file_bytes),
    )
    _queue_tds_notification(background_tasks, current_user.email, result.tds_events)
    return _ingestion_response(result)


@router.post("/manual", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
def manual_entry(
    payload: ManualIngestionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_transactions = [
        RawTransaction(
            transaction_date=entry.transaction_date,
            amount=entry.amount,
            party_name=entry.party_name,
            description=entry.description,
            declared_category=entry.declared_category,
            party_gstin=entry.party_gstin,
            party_pan=entry.party_pan,
            party_pan_provided=entry.party_pan_provided,
            party_is_non_resident=entry.party_is_non_resident,
            external_ref=entry.external_ref,
        )
        for entry in payload.entries
    ]
    dataset_hash = hash_dataset(payload.model_dump_json())

    try:
        result = ingest_transactions(
            db, current_user.id, raw_transactions, TransactionSourceType.MANUAL_ENTRY, dataset_hash
        )
    except TransactionSourceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    _queue_tds_notification(background_tasks, current_user.email, result.tds_events)
    return _ingestion_response(result)


@router.post("/simulate", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
def simulate_bank_feed(
    payload: SimulateFeedRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Demo-only endpoint: generates a synthetic bank/UPI feed so the product
    can be tried end-to-end without a real Account Aggregator connection."""
    raw_transactions = SyntheticFeedGenerator(seed=payload.seed).fetch()
    result = ingest_transactions(
        db,
        current_user.id,
        raw_transactions,
        TransactionSourceType.SYNTHETIC_FEED,
        dataset_hash=hash_dataset(f"synthetic:{payload.seed}"),
    )
    _queue_tds_notification(background_tasks, current_user.email, result.tds_events)
    return _ingestion_response(result)


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    financial_year: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)
    return (
        query.order_by(Transaction.transaction_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
