"""Shared data shape assembled from the DB and handed to both the PDF and
Excel report generators, so they never diverge on what a "report" contains."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.advance_tax.projector import AdvanceTaxProjection
from app.rule_engine.section_393 import TDSDecisionStatus


@dataclass(frozen=True)
class TDSEventRow:
    transaction_date: date
    vendor_name: str
    category: str
    amount: Decimal
    decision_status: TDSDecisionStatus
    review_reason: str | None
    tds_applicable: bool
    pan_not_provided: bool
    tds_amount: Decimal | None
    rate_percent: Decimal | None
    explanation: str
    filing_form_reference: str | None
    filing_deadline: str | None


@dataclass(frozen=True)
class ReportInput:
    user_full_name: str
    user_email: str
    financial_year: str
    generated_at: datetime
    rule_table_version: str
    dataset_hash: str
    tds_events: list[TDSEventRow] = field(default_factory=list)
    advance_tax: AdvanceTaxProjection | None = None

    @property
    def total_tds_due(self) -> Decimal:
        return sum(
            (e.tds_amount or Decimal("0") for e in self.tds_events if e.tds_applicable),
            Decimal("0"),
        )

    @property
    def flagged_count(self) -> int:
        return sum(1 for e in self.tds_events if e.tds_applicable)

    @property
    def needs_review_count(self) -> int:
        return sum(1 for e in self.tds_events if e.decision_status == TDSDecisionStatus.NEEDS_REVIEW)
