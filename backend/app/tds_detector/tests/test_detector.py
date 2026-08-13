from datetime import date
from decimal import Decimal

from app.models import AuditLog, User, UserRole
from app.models.common import generate_uuid
from app.models.transaction import TransactionSourceType
from app.rule_engine.section_393 import TDSCategory
from app.security import hash_password
from app.sources.base import RawTransaction
from app.tds_detector.detector import ingest_transactions


def _make_user(db_session, email="detector-user@example.com") -> User:
    user = User(
        id=generate_uuid(),
        email=email,
        full_name="Detector Test User",
        hashed_password=hash_password("Passw0rd1"),
        role=UserRole.INDIVIDUAL,
    )
    db_session.add(user)
    db_session.flush()
    return user


class TestIngestTransactions:
    def test_cumulative_threshold_crossing_across_a_batch(self, db_session):
        user = _make_user(db_session)

        raw = [
            RawTransaction(date(2026, 4, 10), Decimal("10000"), "Skyline Consulting", "Professional fees April"),
            RawTransaction(date(2026, 5, 10), Decimal("10000"), "Skyline Consulting", "Professional fees May"),
            RawTransaction(date(2026, 6, 10), Decimal("15000"), "Skyline Consulting", "Professional fees June"),
            RawTransaction(date(2026, 7, 10), Decimal("5000"), "Skyline Consulting", "Professional fees July"),
        ]

        result = ingest_transactions(
            db_session, user.id, raw, TransactionSourceType.MANUAL_ENTRY, dataset_hash="testhash1"
        )

        assert result.transactions_created == 4
        assert result.tds_events_created == 4

        events = sorted(result.tds_events, key=lambda e: e.cumulative_after)
        # April: 10,000 cumulative -> below 30,000, no TDS
        assert events[0].tds_applicable is False
        # May: 20,000 cumulative -> still below 30,000
        assert events[1].tds_applicable is False
        # June: 35,000 cumulative -> crosses 30,000 this transaction, catch-up TDS on full 35,000
        assert events[2].tds_applicable is True
        assert events[2].threshold_crossed_this_transaction is True
        assert events[2].taxable_amount == Decimal("35000.00")
        assert events[2].tds_amount == Decimal("3500.00")
        assert "crossing" in events[2].explanation_text
        # July: already past threshold, taxed only on its own 5,000
        assert events[3].tds_applicable is True
        assert events[3].threshold_crossed_this_transaction is False
        assert events[3].taxable_amount == Decimal("5000.00")
        assert events[3].tds_amount == Decimal("500.00")

    def test_unsorted_batch_is_processed_in_date_order(self, db_session):
        user = _make_user(db_session, "unsorted-batch@example.com")

        # Deliberately out of chronological order.
        raw = [
            RawTransaction(date(2026, 6, 10), Decimal("15000"), "Greenview Properties", "Rent June"),
            RawTransaction(date(2026, 4, 10), Decimal("200000"), "Greenview Properties", "Rent April"),
            RawTransaction(date(2026, 5, 10), Decimal("50000"), "Greenview Properties", "Rent May"),
        ]
        result = ingest_transactions(
            db_session, user.id, raw, TransactionSourceType.MANUAL_ENTRY, dataset_hash="testhash2"
        )

        by_date = {e.transaction.transaction_date: e for e in result.tds_events}
        assert by_date[date(2026, 4, 10)].cumulative_after == Decimal("200000.00")
        assert by_date[date(2026, 5, 10)].cumulative_after == Decimal("250000.00")
        # Rent threshold is 240,000 — May's cumulative of 250,000 crosses it.
        assert by_date[date(2026, 5, 10)].threshold_crossed_this_transaction is True
        assert by_date[date(2026, 6, 10)].threshold_crossed_this_transaction is False
        assert by_date[date(2026, 6, 10)].tds_applicable is True

    def test_different_users_have_independent_cumulative_tracking(self, db_session):
        user_a = _make_user(db_session, "vendor-isolation-a@example.com")
        user_b = _make_user(db_session, "vendor-isolation-b@example.com")

        same_vendor_txn = [
            RawTransaction(date(2026, 4, 1), Decimal("28000"), "Shared Name Consulting", "Professional fees")
        ]

        ingest_transactions(db_session, user_a.id, same_vendor_txn, TransactionSourceType.MANUAL_ENTRY, "h1")
        result_b = ingest_transactions(db_session, user_b.id, same_vendor_txn, TransactionSourceType.MANUAL_ENTRY, "h2")

        # User B's vendor is a distinct row scoped to user B, so cumulative starts fresh at 0,
        # not inheriting user A's 28,000 — this is the row-level isolation the rule engine relies on.
        assert result_b.tds_events[0].cumulative_before == Decimal("0")

    def test_audit_log_recorded_for_each_ingestion_run(self, db_session):
        user = _make_user(db_session, "audit-check@example.com")
        raw = [RawTransaction(date(2026, 4, 1), Decimal("1000"), "Some Vendor")]

        ingest_transactions(db_session, user.id, raw, TransactionSourceType.CSV_UPLOAD, dataset_hash="abc123")

        log = (
            db_session.query(AuditLog)
            .filter(AuditLog.user_id == user.id, AuditLog.action == "tds_detection_run")
            .first()
        )
        assert log is not None
        assert log.dataset_hash == "abc123"
        assert log.rule_table_version

    def test_non_resident_payment_taxed_from_first_rupee(self, db_session):
        user = _make_user(db_session, "non-resident@example.com")
        raw = [
            RawTransaction(
                date(2026, 4, 1),
                Decimal("50000"),
                "Overseas Vendor Ltd",
                "Royalty payment",
                party_is_non_resident=True,
            )
        ]
        result = ingest_transactions(db_session, user.id, raw, TransactionSourceType.MANUAL_ENTRY, "h3")
        event = result.tds_events[0]
        assert event.category == TDSCategory.NON_RESIDENT_PAYMENT
        assert event.tds_applicable is True
        assert event.cumulative_before == Decimal("0")
