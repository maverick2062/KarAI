from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.tds_event import TDSEvent
from app.models.vendor import Vendor
from app.rule_engine.section_393 import TDSCategory


def get_or_create_vendor(
    db: Session,
    user_id: str,
    name: str,
    gstin: str | None = None,
    is_non_resident: bool = False,
) -> Vendor:
    vendor = (
        db.query(Vendor)
        .filter(Vendor.user_id == user_id, Vendor.name == name)
        .first()
    )
    if vendor is not None:
        return vendor

    vendor = Vendor(user_id=user_id, name=name, gstin=gstin, is_non_resident=is_non_resident)
    db.add(vendor)
    db.flush()  # assign an id without committing the whole ingestion transaction
    return vendor


def get_cumulative_before(
    db: Session,
    user_id: str,
    vendor_id: str,
    category: TDSCategory,
    financial_year: str,
) -> Decimal:
    """The cumulative payment total for this payee/category/FY *before* the
    next transaction — simply the ``cumulative_after`` of the most recent
    prior TDSEvent for the same (vendor, category, FY), or 0 if none exists.
    Callers MUST process a batch of transactions in ``transaction_date`` order
    for this running total to be correct.
    """
    latest_event = (
        db.query(TDSEvent)
        .join(Transaction, TDSEvent.transaction_id == Transaction.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.vendor_id == vendor_id,
            Transaction.financial_year == financial_year,
            TDSEvent.category == category,
        )
        .order_by(Transaction.transaction_date.desc(), TDSEvent.created_at.desc())
        .first()
    )
    return latest_event.cumulative_after if latest_event else Decimal("0")
