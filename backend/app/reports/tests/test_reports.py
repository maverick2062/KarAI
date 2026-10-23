import io
from datetime import date, datetime, timezone
from decimal import Decimal

from openpyxl import load_workbook

from app.advance_tax.projector import project_advance_tax
from app.models.advance_tax import TaxRegime
from app.reports.excel_report import generate_excel_report
from app.reports.pdf_report import generate_pdf_report
from app.reports.report_data import ReportInput, TDSEventRow


def _sample_report_input() -> ReportInput:
    events = [
        TDSEventRow(
            transaction_date=date(2026, 6, 10),
            vendor_name="Skyline Consulting",
            category="professional_fees",
            amount=Decimal("35000"),
            tds_applicable=True,
            pan_not_provided=False,
            tds_amount=Decimal("3500.00"),
            rate_percent=Decimal("10"),
            explanation="Crossed the ₹30,000 threshold.",
            filing_form_reference="Form 26Q",
            filing_deadline="2026-07-07",
        ),
        TDSEventRow(
            transaction_date=date(2026, 4, 1),
            vendor_name="Small Vendor",
            category="commission_brokerage",
            amount=Decimal("5000"),
            tds_applicable=False,
            pan_not_provided=False,
            tds_amount=Decimal("0"),
            rate_percent=Decimal("2"),
            explanation="Below threshold.",
            filing_form_reference=None,
            filing_deadline=None,
        ),
    ]
    advance_tax = project_advance_tax("2026-27", Decimal("1500000"), TaxRegime.NEW, as_of=date(2026, 5, 1))

    return ReportInput(
        user_full_name="Alice Freelancer",
        user_email="alice@example.com",
        financial_year="2026-27",
        generated_at=datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc),
        rule_table_version="ITA2025-S393-v1",
        dataset_hash="deadbeef",
        tds_events=events,
        advance_tax=advance_tax,
    )


class TestReportInputAggregates:
    def test_total_tds_due_only_sums_applicable_events(self):
        data = _sample_report_input()
        assert data.total_tds_due == Decimal("3500.00")
        assert data.flagged_count == 1


class TestPdfReport:
    def test_generates_valid_pdf_bytes(self):
        pdf_bytes = generate_pdf_report(_sample_report_input())
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 500

    def test_handles_no_flagged_transactions(self):
        data = _sample_report_input()
        no_flags = data.__class__(
            **{**data.__dict__, "tds_events": [e for e in data.tds_events if not e.tds_applicable]}
        )
        pdf_bytes = generate_pdf_report(no_flags)
        assert pdf_bytes.startswith(b"%PDF")


class TestExcelReport:
    def test_generates_readable_workbook_with_expected_sheets(self):
        excel_bytes = generate_excel_report(_sample_report_input())
        workbook = load_workbook(io.BytesIO(excel_bytes))
        assert workbook.sheetnames == ["Summary", "Flagged Transactions"]

        flagged_sheet = workbook["Flagged Transactions"]
        header_row = [cell.value for cell in flagged_sheet[1]]
        assert "Vendor" in header_row
        assert "TDS Amount" in header_row
        assert "PAN Status" in header_row

        first_data_row = [cell.value for cell in flagged_sheet[2]]
        assert first_data_row[1] == "Skyline Consulting"

    def test_summary_sheet_contains_key_metadata(self):
        excel_bytes = generate_excel_report(_sample_report_input())
        workbook = load_workbook(io.BytesIO(excel_bytes))
        summary_values = [cell.value for row in workbook["Summary"].iter_rows() for cell in row if cell.value]
        assert any("alice@example.com" in str(v) for v in summary_values)
        assert any("deadbeef" in str(v) for v in summary_values)
