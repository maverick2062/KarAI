from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.audit.hashing import hash_dataset
from app.db import get_db
from app.models.transaction import Transaction, TransactionSourceType
from app.models.transaction_search_term import TransactionSearchTerm
from app.models.tds_event import TDSEvent
from app.models.user import User
from app.notifications import send_tds_event_email
from app.routers.deps import get_current_user
from app.schemas.transactions import (
    IngestionResponse,
    ManualIngestionRequest,
    SimulateFeedRequest,
    TransactionPage,
    TransactionOut,
)
from app.sources.base import RawTransaction, TransactionSourceError
from app.sources.csv_source import CSVTransactionSource
from app.sources.synthetic_feed import SyntheticFeedGenerator
from app.tds_detector.detector import IngestionResult, ingest_transactions
from app.transaction_search import parse_amount_search, query_search_hashes

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
            rule_context=entry.rule_context,
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


@router.get("", response_model=TransactionPage)
def list_transactions(
    financial_year: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    source_type: TransactionSourceType | None = Query(default=None),
    recent_only: bool = Query(default=False),
    include_synthetic: bool = Query(default=True),
    include_completed: bool = Query(default=True),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Transaction)
        .options(joinedload(Transaction.vendor), joinedload(Transaction.tds_event))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.is_deleted.is_(False),
        )
    )
    if not include_synthetic:
        query = query.filter(Transaction.source_type != TransactionSourceType.SYNTHETIC_FEED)
    if source_type is not None:
        query = query.filter(Transaction.source_type == source_type)
    if recent_only:
        query = query.filter(
            Transaction.source_type.in_(
                [TransactionSourceType.MANUAL_ENTRY, TransactionSourceType.CSV_UPLOAD]
            )
        )
    if not include_completed:
        query = query.filter(Transaction.is_completed.is_(False))
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)

    normalized_search = (search or "").strip()
    if normalized_search:
        is_amount_search, amount_search = parse_amount_search(normalized_search)
        if is_amount_search:
            if amount_search is None:
                return TransactionPage(items=[], total=0, limit=limit, offset=offset)
            query = query.filter(Transaction.amount == amount_search)
        else:
            term_hashes = query_search_hashes(current_user.id, normalized_search)
            if not term_hashes:
                return TransactionPage(items=[], total=0, limit=limit, offset=offset)
            matching_ids = (
                db.query(TransactionSearchTerm.transaction_id)
                .filter(
                    TransactionSearchTerm.user_id == current_user.id,
                    TransactionSearchTerm.term_hash.in_(term_hashes),
                )
                .group_by(TransactionSearchTerm.transaction_id)
                .having(func.count(func.distinct(TransactionSearchTerm.term_hash)) == len(term_hashes))
                .subquery()
            )
            query = query.filter(Transaction.id.in_(matching_ids))

    total = query.count()
    items = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return TransactionPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/synthetic-feed")
def remove_synthetic_feed(
    financial_year: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.source_type == TransactionSourceType.SYNTHETIC_FEED,
        Transaction.is_deleted.is_(False),
    )
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)
    removed = query.update({Transaction.is_deleted: True}, synchronize_session=False)
    db.commit()
    return {"transactions_removed": removed}


@router.patch("/{transaction_id}/complete", response_model=TransactionOut)
def set_transaction_completed(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.is_deleted.is_(False),
            Transaction.source_type.in_(
                [TransactionSourceType.MANUAL_ENTRY, TransactionSourceType.CSV_UPLOAD]
            ),
        )
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.tds_event is None or not transaction.tds_event.tds_applicable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only transactions with TDS due can be marked as paid.",
        )
    transaction.is_completed = True
    db.commit()
    db.refresh(transaction)
    return transaction


@router.patch("/{transaction_id}/reopen", response_model=TransactionOut)
def reopen_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.is_deleted.is_(False),
            Transaction.source_type.in_(
                [TransactionSourceType.MANUAL_ENTRY, TransactionSourceType.CSV_UPLOAD]
            ),
        )
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    transaction.is_completed = False
    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .filter(
            Transaction.source_type.in_(
                [TransactionSourceType.MANUAL_ENTRY, TransactionSourceType.CSV_UPLOAD]
            ),
            Transaction.is_deleted.is_(False),
        )
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    transaction.is_deleted = True
    db.commit()
    return None


@router.patch("/{transaction_id}/restore", response_model=TransactionOut)
def restore_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .filter(
            Transaction.source_type.in_(
                [TransactionSourceType.MANUAL_ENTRY, TransactionSourceType.CSV_UPLOAD]
            )
        )
        .first()
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    transaction.is_deleted = False
    db.commit()
    db.refresh(transaction)
    return transaction
