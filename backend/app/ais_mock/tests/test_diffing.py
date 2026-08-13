from decimal import Decimal

import pytest

from app.ais_mock.diffing import AISDiscrepancyType, ReportedAmount, find_discrepancies
from app.ais_mock.mock_upload import parse_ais_csv
from app.ais_mock.oauth_stub import fetch_ais_via_oauth
from app.ais_mock.synthetic_ais import AISRecordInput
from app.sources.base import TransactionSourceError


class TestFindDiscrepancies:
    def test_matching_amounts_produce_no_discrepancy(self):
        ais = [AISRecordInput("Acme Bank", Decimal("5000"), "interest")]
        reported = [ReportedAmount("Acme Bank", "interest", Decimal("5000"))]
        assert find_discrepancies(ais, reported) == []

    def test_matching_within_tolerance_produces_no_discrepancy(self):
        ais = [AISRecordInput("Acme Bank", Decimal("5050"), "interest")]
        reported = [ReportedAmount("Acme Bank", "interest", Decimal("5000"))]
        assert find_discrepancies(ais, reported) == []

    def test_amount_mismatch_beyond_tolerance_is_flagged(self):
        ais = [AISRecordInput("Acme Bank", Decimal("8000"), "interest")]
        reported = [ReportedAmount("Acme Bank", "interest", Decimal("5000"))]
        discrepancies = find_discrepancies(ais, reported)
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == AISDiscrepancyType.AMOUNT_MISMATCH
        assert discrepancies[0].ais_amount == Decimal("8000")
        assert discrepancies[0].reported_amount == Decimal("5000")

    def test_ais_entry_not_reported_by_user_is_flagged(self):
        ais = [AISRecordInput("Unreported Bank", Decimal("3000"), "interest")]
        discrepancies = find_discrepancies(ais, [])
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == AISDiscrepancyType.MISSING_FROM_USER_RECORDS

    def test_user_reported_entry_missing_from_ais_is_flagged(self):
        reported = [ReportedAmount("Freelance Client", "professional_fees", Decimal("40000"))]
        discrepancies = find_discrepancies([], reported)
        assert len(discrepancies) == 1
        assert discrepancies[0].discrepancy_type == AISDiscrepancyType.MISSING_FROM_AIS
        assert discrepancies[0].reported_amount == Decimal("40000")

    def test_matching_is_case_and_whitespace_insensitive(self):
        ais = [AISRecordInput("  ACME bank  ", Decimal("5000"), "Interest")]
        reported = [ReportedAmount("Acme Bank", "interest", Decimal("5000"))]
        assert find_discrepancies(ais, reported) == []

    def test_multiple_transactions_to_same_vendor_are_summed_before_comparison(self):
        ais = [AISRecordInput("Acme Bank", Decimal("9000"), "interest")]
        reported = [
            ReportedAmount("Acme Bank", "interest", Decimal("4000")),
            ReportedAmount("Acme Bank", "interest", Decimal("5000")),
        ]
        assert find_discrepancies(ais, reported) == []

    def test_multiple_ais_lines_for_same_vendor_are_summed_before_comparison(self):
        # Regression test: a real (or synthetic) AIS often reports several line
        # items per payee across the year. Comparing each raw line against the
        # payee's full-year reported total (instead of summing AIS lines first)
        # previously manufactured a false mismatch for every single line item.
        ais = [
            AISRecordInput("Acme Bank", Decimal("4000"), "interest"),
            AISRecordInput("Acme Bank", Decimal("5000"), "interest"),
        ]
        reported = [ReportedAmount("Acme Bank", "interest", Decimal("9000"))]
        assert find_discrepancies(ais, reported) == []

    def test_many_small_ais_lines_summing_close_to_reported_total_is_not_flagged(self):
        ais = [AISRecordInput("Acme Bank", Decimal(amount), "interest") for amount in (1000, 2000, 3000, 2950)]
        reported = [ReportedAmount("Acme Bank", "interest", Decimal("8950"))]
        assert find_discrepancies(ais, reported) == []


class TestParseAisCsv:
    def test_parses_valid_csv(self):
        csv_bytes = b"reporting_entity,amount,category\nAcme Bank,5000,interest\n"
        records = parse_ais_csv(csv_bytes)
        assert records == [AISRecordInput("Acme Bank", Decimal("5000"), "interest")]

    def test_missing_column_raises(self):
        csv_bytes = b"amount,category\n5000,interest\n"
        with pytest.raises(TransactionSourceError, match="reporting_entity"):
            parse_ais_csv(csv_bytes)


class TestOAuthStub:
    def test_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="OAuth"):
            fetch_ais_via_oauth("fake-token")
