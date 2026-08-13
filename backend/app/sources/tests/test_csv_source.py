from datetime import date
from decimal import Decimal

import pytest

from app.sources.account_aggregator_stub import AccountAggregatorSource
from app.sources.base import TransactionSourceError
from app.sources.csv_source import CSVTransactionSource
from app.sources.manual_source import ManualEntryTransactionSource
from app.sources.base import RawTransaction
from app.sources.synthetic_feed import SyntheticFeedGenerator


class TestCSVTransactionSource:
    def test_parses_standard_columns(self):
        csv_bytes = (
            b"transaction_date,amount,party_name,description\n"
            b"2026-05-10,35000,Acme Consulting,Professional fees Q1\n"
        )
        transactions = CSVTransactionSource(csv_bytes).fetch()
        assert len(transactions) == 1
        assert transactions[0].transaction_date == date(2026, 5, 10)
        assert transactions[0].amount == Decimal("35000")
        assert transactions[0].party_name == "Acme Consulting"

    def test_handles_comma_and_rupee_symbol_in_amount(self):
        csv_bytes = b"transaction_date,amount,party_name\n2026-06-01,\"1,20,000\",Landlord\n"
        transactions = CSVTransactionSource(csv_bytes).fetch()
        assert transactions[0].amount == Decimal("120000")

    def test_column_mapping_wizard_for_non_standard_headers(self):
        csv_bytes = b"Date,Amount (INR),Paid To\n2026-05-10,5000,Some Vendor\n"
        mapping = {"transaction_date": "Date", "amount": "Amount (INR)", "party_name": "Paid To"}
        transactions = CSVTransactionSource(csv_bytes, column_mapping=mapping).fetch()
        assert transactions[0].party_name == "Some Vendor"

    def test_missing_required_column_raises(self):
        csv_bytes = b"amount,party_name\n5000,Vendor\n"
        with pytest.raises(TransactionSourceError, match="Required column"):
            CSVTransactionSource(csv_bytes).fetch()

    def test_oversized_file_rejected(self):
        huge = b"x" * (51 * 1024 * 1024)
        with pytest.raises(TransactionSourceError, match="50 MB"):
            CSVTransactionSource(huge)

    def test_unparseable_amount_raises(self):
        csv_bytes = b"transaction_date,amount,party_name\n2026-05-10,not-a-number,Vendor\n"
        with pytest.raises(TransactionSourceError, match="Unrecognized amount"):
            CSVTransactionSource(csv_bytes).fetch()


class TestManualEntryTransactionSource:
    def test_returns_entries_as_given(self):
        entry = RawTransaction(transaction_date=date(2026, 4, 1), amount=Decimal("1000"), party_name="X")
        source = ManualEntryTransactionSource([entry])
        assert source.fetch() == [entry]


class TestSyntheticFeedGenerator:
    def test_generates_deterministic_output_for_same_seed(self):
        first = SyntheticFeedGenerator(seed=7).fetch()
        second = SyntheticFeedGenerator(seed=7).fetch()
        assert first == second

    def test_different_seeds_produce_different_output(self):
        first = SyntheticFeedGenerator(seed=1).fetch()
        second = SyntheticFeedGenerator(seed=2).fetch()
        assert first != second

    def test_generates_a_non_trivial_dataset(self):
        transactions = SyntheticFeedGenerator(seed=42).fetch()
        assert len(transactions) > 20
        assert all(t.amount > 0 for t in transactions)


class TestAccountAggregatorStub:
    def test_fetch_raises_not_implemented(self):
        source = AccountAggregatorSource(consent_handle="test-handle")
        with pytest.raises(NotImplementedError, match="AA partnership"):
            source.fetch()
