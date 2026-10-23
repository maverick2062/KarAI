import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports.report_data import ReportInput
from app.rule_engine.section_393 import RULE_TABLE_DISCLAIMER


def generate_pdf_report(data: ReportInput) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("KarAI — TDS Compliance Audit Report", styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"<b>Taxpayer:</b> {data.user_full_name} ({data.user_email})", styles["Normal"]))
    story.append(Paragraph(f"<b>Financial Year:</b> {data.financial_year}", styles["Normal"]))
    story.append(Paragraph(f"<b>Generated:</b> {data.generated_at.isoformat()}", styles["Normal"]))
    story.append(Paragraph(f"<b>Rule table version:</b> {data.rule_table_version}", styles["Normal"]))
    story.append(Paragraph(f"<b>Dataset hash:</b> {data.dataset_hash}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Executive Summary", styles["Heading2"]))
    story.append(Paragraph(f"Transactions analyzed: {len(data.tds_events)}", styles["Normal"]))
    story.append(Paragraph(f"Transactions with a TDS obligation: {data.flagged_count}", styles["Normal"]))
    story.append(Paragraph(f"Total TDS due: ₹{data.total_tds_due:,.2f}", styles["Normal"]))

    if data.advance_tax is not None and data.advance_tax.advance_tax_required:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Advance Tax Summary", styles["Heading2"]))
        story.append(Paragraph(f"Regime: {data.advance_tax.regime.value}", styles["Normal"]))
        story.append(Paragraph(f"Estimated tax liability: ₹{data.advance_tax.tax_liability:,.2f}", styles["Normal"]))
        if data.advance_tax.interest_234b > 0:
            story.append(
                Paragraph(f"Estimated Section 234B interest: ₹{data.advance_tax.interest_234b:,.2f}", styles["Normal"])
            )

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Flagged Transactions", styles["Heading2"]))

    table_data = [["Date", "Vendor", "Category", "Amount", "TDS Due", "Rate", "PAN", "Form / Deadline"]]
    for event in data.tds_events:
        if not event.tds_applicable:
            continue
        table_data.append(
            [
                event.transaction_date.isoformat(),
                event.vendor_name,
                event.category,
                f"₹{event.amount:,.2f}",
                f"₹{event.tds_amount:,.2f}",
                f"{event.rate_percent}%",
                "Not furnished" if event.pan_not_provided else "Furnished/unknown",
                f"{event.filing_form_reference or '-'}\nby {event.filing_deadline or '-'}",
            ]
        )

    if len(table_data) == 1:
        story.append(Paragraph("No transactions currently have a TDS obligation.", styles["Normal"]))
    else:
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)

    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(RULE_TABLE_DISCLAIMER, styles["Italic"]))

    doc.build(story)
    return buffer.getvalue()
