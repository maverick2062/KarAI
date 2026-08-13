from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.transaction import TransactionSourceType


class ManualTransactionEntry(BaseModel):
    transaction_date: date
    amount: Decimal = Field(gt=0)
    party_name: str
    description: str = ""
    declared_category: str | None = None
    party_gstin: str | None = None
    party_is_non_resident: bool = False
    external_ref: str | None = None


class ManualIngestionRequest(BaseModel):
    entries: list[ManualTransactionEntry]


class SimulateFeedRequest(BaseModel):
    seed: int = 42


class TDSEventSummary(BaseModel):
    id: str
    transaction_id: str
    category: str
    tds_applicable: bool
    threshold_crossed_this_transaction: bool
    cumulative_before: Decimal
    cumulative_after: Decimal
    taxable_amount: Decimal
    tds_amount: Decimal
    rate_percent: Decimal
    explanation_text: str
    filing_form_reference: str | None
    filing_deadline: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionResponse(BaseModel):
    transactions_created: int
    tds_events_created: int
    tds_events: list[TDSEventSummary]


class TransactionOut(BaseModel):
    id: str
    vendor_id: str | None
    source_type: TransactionSourceType
    transaction_date: date
    amount: Decimal
    description: str | None
    declared_category: str | None
    financial_year: str
    created_at: datetime

    model_config = {"from_attributes": True}
