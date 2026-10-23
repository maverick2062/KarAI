from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.transaction import TransactionSourceType
from app.rule_engine.context import RuleContext
from app.rule_engine.section_393 import TDSDecisionStatus
from app.sources.base import normalize_pan


class ManualTransactionEntry(BaseModel):
    transaction_date: date
    amount: Decimal = Field(gt=0)
    party_name: str
    description: str = ""
    declared_category: str | None = None
    party_gstin: str | None = None
    party_pan: str | None = None
    party_pan_provided: bool | None = None
    party_is_non_resident: bool = False
    external_ref: str | None = None
    rule_context: RuleContext | None = None

    @field_validator("party_pan")
    @classmethod
    def validate_party_pan(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        try:
            return normalize_pan(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def infer_pan_provided(self):
        if self.party_pan:
            if self.party_pan_provided is False:
                raise ValueError("A PAN cannot be supplied when party_pan_provided is false.")
            self.party_pan_provided = True
        return self


class ManualIngestionRequest(BaseModel):
    entries: list[ManualTransactionEntry]


class SimulateFeedRequest(BaseModel):
    seed: int = 42


class TDSEventSummary(BaseModel):
    id: str
    transaction_id: str
    category: str
    decision_status: TDSDecisionStatus
    review_reason: str | None
    tds_applicable: bool
    threshold_crossed_this_transaction: bool
    pan_not_provided: bool
    cumulative_before: Decimal
    cumulative_after: Decimal
    taxable_amount: Decimal | None
    tds_amount: Decimal | None
    rate_percent: Decimal | None
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
