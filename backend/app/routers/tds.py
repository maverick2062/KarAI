from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.tds_event import TDSEvent
from app.models.transaction import Transaction
from app.models.transaction_search_term import TransactionSearchTerm
from app.models.user import User
from app.routers.deps import get_current_user
from app.rule_engine.section_393 import TDSCategory, TDSDecisionStatus
from app.schemas.transactions import TDSEventPage, TDSEventSummary
from app.transaction_search import parse_amount_search, query_search_hashes

router = APIRouter(prefix="/api/v1/tds-events", tags=["tds-events"])


@router.get("", response_model=TDSEventPage)
def list_tds_events(
    financial_year: str | None = Query(default=None),
    category: TDSCategory | None = Query(default=None),
    decision_status: TDSDecisionStatus | None = Query(default=None),
    tds_applicable: bool | None = Query(default=None),
    transaction_completed: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(TDSEvent)
        .join(Transaction, TDSEvent.transaction_id == Transaction.id)
        .filter(
            TDSEvent.user_id == current_user.id,
            Transaction.is_deleted.is_(False),
        )
    )
    if category is not None:
        query = query.filter(TDSEvent.category == category)
    if decision_status is not None:
        query = query.filter(TDSEvent.decision_status == decision_status)
    if tds_applicable is not None:
        query = query.filter(TDSEvent.tds_applicable == tds_applicable)
    if transaction_completed is not None:
        query = query.filter(Transaction.is_completed.is_(transaction_completed))
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)

    normalized_search = (search or "").strip()
    if normalized_search:
        is_amount_search, amount_search = parse_amount_search(normalized_search)
        if is_amount_search:
            if amount_search is None:
                return TDSEventPage(items=[], total=0, limit=limit, offset=offset)
            query = query.filter(Transaction.amount == amount_search)
        else:
            term_hashes = query_search_hashes(current_user.id, normalized_search)
            if not term_hashes:
                return TDSEventPage(items=[], total=0, limit=limit, offset=offset)
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

    total, flagged_count, needs_review_count, total_tds_due = query.with_entities(
        func.count(TDSEvent.id),
        func.coalesce(func.sum(case((TDSEvent.tds_applicable.is_(True), 1), else_=0)), 0),
        func.coalesce(
            func.sum(case((TDSEvent.decision_status == TDSDecisionStatus.NEEDS_REVIEW, 1), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((TDSEvent.tds_applicable.is_(True), TDSEvent.tds_amount), else_=0)),
            0,
        ),
    ).first()
    upcoming_deadlines = [
        deadline
        for (deadline,) in (
            query.filter(
                TDSEvent.tds_applicable.is_(True),
                TDSEvent.filing_deadline.is_not(None),
            )
            .with_entities(TDSEvent.filing_deadline)
            .distinct()
            .order_by(TDSEvent.filing_deadline)
            .limit(5)
            .all()
        )
    ]
    events = (
        query.options(joinedload(TDSEvent.transaction).joinedload(Transaction.vendor))
        .order_by(Transaction.transaction_date.desc(), TDSEvent.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_serialize_event(event) for event in events]
    return TDSEventPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        flagged_count=flagged_count,
        needs_review_count=needs_review_count,
        total_tds_due=total_tds_due,
        upcoming_deadlines=upcoming_deadlines,
    )


def _serialize_event(event: TDSEvent) -> dict:
    transaction = event.transaction
    return {
        **TDSEventSummary.model_validate(event, from_attributes=True).model_dump(),
        "transaction_date": transaction.transaction_date,
        "transaction_amount": transaction.amount,
        "transaction_description": transaction.description,
        "transaction_party_name": transaction.vendor.name if transaction.vendor else None,
        "transaction_is_completed": transaction.is_completed,
    }


@router.get("/{event_id}", response_model=TDSEventSummary)
def get_tds_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = (
        db.query(TDSEvent)
        .options(joinedload(TDSEvent.transaction).joinedload(Transaction.vendor))
        .join(Transaction, TDSEvent.transaction_id == Transaction.id)
        .filter(
            TDSEvent.id == event_id,
            TDSEvent.user_id == current_user.id,
            Transaction.is_deleted.is_(False),
        )
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TDS event not found")
    return _serialize_event(event)
