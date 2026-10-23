from dataclasses import dataclass
from datetime import datetime, time

from sqlalchemy.orm import Session

from app.audit.logger import record_audit_log
from app.explainability.renderer import render_explanation
from app.explainability.templates import FORM_REFERENCE_BY_CATEGORY, next_deposit_deadline
from app.models.common import current_financial_year
from app.models.tds_event import TDSEvent
from app.models.transaction import Transaction, TransactionSourceType
from app.rule_engine.evaluate import classify_category, compute_tds
from app.rule_engine.section_393 import RULE_TABLE_VERSION
from app.sources.base import RawTransaction
from app.tds_detector.tracker import get_cumulative_before, get_or_create_vendor


@dataclass
class IngestionResult:
    transactions_created: int
    tds_events_created: int
    tds_events: list[TDSEvent]


def ingest_transactions(
    db: Session,
    user_id: str,
    raw_transactions: list[RawTransaction],
    source_type: TransactionSourceType,
    dataset_hash: str,
) -> IngestionResult:
    """The core ingestion pipeline: resolve vendors, classify each transaction
    into a Section 393 category, run the rule engine against the payee's
    running FY total, generate a plain-language explanation, and persist
    Transaction + TDSEvent rows. Processes transactions in chronological
    order so cumulative-threshold tracking is correct regardless of upload
    order (e.g. an unsorted CSV).
    """
    ordered = sorted(raw_transactions, key=lambda t: t.transaction_date)

    created_events: list[TDSEvent] = []

    for raw in ordered:
        vendor = get_or_create_vendor(
            db,
            user_id=user_id,
            name=raw.party_name,
            gstin=raw.party_gstin,
            is_non_resident=raw.party_is_non_resident,
        )
        if raw.party_pan:
            vendor.pan = raw.party_pan
        pan_provided = raw.party_pan_provided
        if pan_provided is None:
            pan_provided = bool(vendor.pan)

        financial_year = current_financial_year(datetime.combine(raw.transaction_date, time()))

        transaction = Transaction(
            user_id=user_id,
            vendor_id=vendor.id,
            source_type=source_type,
            external_ref=raw.external_ref,
            transaction_date=raw.transaction_date,
            amount=raw.amount,
            description=raw.description,
            declared_category=raw.declared_category,
            financial_year=financial_year,
        )
        db.add(transaction)
        db.flush()

        category = classify_category(
            description=raw.description,
            declared_category=raw.declared_category,
            payee_is_non_resident=raw.party_is_non_resident,
        )
        cumulative_before = get_cumulative_before(db, user_id, vendor.id, category, financial_year)
        result = compute_tds(category, raw.amount, cumulative_before, pan_provided=pan_provided)

        explanation = render_explanation(result, vendor.name)

        tds_event = TDSEvent(
            user_id=user_id,
            transaction_id=transaction.id,
            category=category,
            rule_table_version=result.rule_table_version,
            threshold_crossed_this_transaction=result.threshold_crossed_this_transaction,
            tds_applicable=result.tds_applicable,
            pan_not_provided=result.pan_not_provided,
            cumulative_before=result.cumulative_before,
            cumulative_after=result.cumulative_after,
            taxable_amount=result.taxable_amount,
            tds_amount=result.tds_amount,
            rate_percent=result.rate_percent,
            explanation_text=explanation,
            filing_form_reference=FORM_REFERENCE_BY_CATEGORY.get(category) if result.tds_applicable else None,
            filing_deadline=next_deposit_deadline(raw.transaction_date) if result.tds_applicable else None,
        )
        db.add(tds_event)
        db.flush()
        created_events.append(tds_event)

    record_audit_log(
        db,
        user_id=user_id,
        action="tds_detection_run",
        rule_table_version=RULE_TABLE_VERSION,
        dataset_hash=dataset_hash,
        details={"source_type": source_type.value, "transaction_count": len(ordered)},
    )
    db.commit()

    return IngestionResult(
        transactions_created=len(ordered),
        tds_events_created=len(created_events),
        tds_events=created_events,
    )
