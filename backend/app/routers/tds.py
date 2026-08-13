from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tds_event import TDSEvent
from app.models.transaction import Transaction
from app.models.user import User
from app.routers.deps import get_current_user
from app.rule_engine.section_393 import TDSCategory
from app.schemas.transactions import TDSEventSummary

router = APIRouter(prefix="/api/v1/tds-events", tags=["tds-events"])


@router.get("", response_model=list[TDSEventSummary])
def list_tds_events(
    financial_year: str | None = Query(default=None),
    category: TDSCategory | None = Query(default=None),
    tds_applicable: bool | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(TDSEvent).filter(TDSEvent.user_id == current_user.id)
    if category is not None:
        query = query.filter(TDSEvent.category == category)
    if tds_applicable is not None:
        query = query.filter(TDSEvent.tds_applicable == tds_applicable)
    if financial_year:
        query = query.join(Transaction, TDSEvent.transaction_id == Transaction.id).filter(
            Transaction.financial_year == financial_year
        )

    return (
        query.order_by(TDSEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{event_id}", response_model=TDSEventSummary)
def get_tds_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = (
        db.query(TDSEvent)
        .filter(TDSEvent.id == event_id, TDSEvent.user_id == current_user.id)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TDS event not found")
    return event
