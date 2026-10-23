import io

from openpyxl import Workbook
from openpyxl.styles import Font

from app.reports.report_data import ReportInput
from app.rule_engine.section_393 import RULE_TABLE_DISCLAIMER


def generate_excel_report(data: ReportInput) -> bytes:
    workbook = Workbook()

    summary = workbook.active
    summary.title = "Summary"
    summary.append(["KarAI — TDS Compliance Audit Report"])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append(["Taxpayer", f"{data.user_full_name} ({data.user_email})"])
    summary.append(["Financial Year", data.financial_year])
    summary.append(["Generated", data.generated_at.isoformat()])
    summary.append(["Rule table version", data.rule_table_version])
    summary.append(["Dataset hash", data.dataset_hash])
    summary.append([])
    summary.append(["Transactions analyzed", len(data.tds_events)])
    summary.append(["Transactions with a TDS obligation", data.flagged_count])
    summary.append(["Total TDS due", float(data.total_tds_due)])

    if data.advance_tax is not None and data.advance_tax.advance_tax_required:
        summary.append([])
        summary.append(["Advance Tax — Regime", data.advance_tax.regime.value])
        summary.append(["Advance Tax — Estimated liability", float(data.advance_tax.tax_liability)])
        summary.append(["Advance Tax — Section 234B interest", float(data.advance_tax.interest_234b)])

    summary.append([])
    summary.append([RULE_TABLE_DISCLAIMER])

    flagged = workbook.create_sheet("Flagged Transactions")
    headers = [
        "Date",
        "Vendor",
        "Category",
        "Amount",
        "TDS Applicable",
        "TDS Amount",
        "Rate (%)",
        "PAN Status",
        "Explanation",
        "Filing Form",
        "Filing Deadline",
    ]
    flagged.append(headers)
    for cell in flagged[1]:
        cell.font = Font(bold=True)

    for event in data.tds_events:
        flagged.append(
            [
                event.transaction_date.isoformat(),
                event.vendor_name,
                event.category,
                float(event.amount),
                "Yes" if event.tds_applicable else "No",
                float(event.tds_amount),
                float(event.rate_percent),
                "Not furnished" if event.pan_not_provided else "Furnished/unknown",
                event.explanation,
                event.filing_form_reference or "",
                event.filing_deadline or "",
            ]
        )

    for column_cells in flagged.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=10)
        flagged.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 60)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
