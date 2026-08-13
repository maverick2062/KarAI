"""Static, auditable mappings used to enrich a TDS explanation — which form
to file and by when. These are plain-English conventions (deposit by the 7th
of the following month is the general TDS rule) rather than data the rule
engine computes, so they live separately from ``rule_engine``."""

from datetime import date

from app.rule_engine.section_393 import TDSCategory

FORM_REFERENCE_BY_CATEGORY: dict[TDSCategory, str] = {
    TDSCategory.PROFESSIONAL_FEES: "Form 26Q (non-salary TDS return) — verify current form number under ITA 2025",
    TDSCategory.RENT: "Form 26QC (TDS on rent by individuals/HUF) — verify applicability to your case",
    TDSCategory.CONTRACTOR_PAYMENTS: "Form 26Q (non-salary TDS return)",
    TDSCategory.COMMISSION_BROKERAGE: "Form 26Q (non-salary TDS return)",
    TDSCategory.INTEREST_OTHER_THAN_SECURITIES: "Form 26Q (non-salary TDS return)",
    TDSCategory.DIVIDEND: "Form 26Q (non-salary TDS return)",
    TDSCategory.LOTTERY_WINNINGS: "Form 26Q (non-salary TDS return)",
    TDSCategory.PROPERTY_PURCHASE: "Form 26QB (TDS on property purchase)",
    TDSCategory.VIRTUAL_DIGITAL_ASSETS: "Form 26QE (TDS on virtual digital assets)",
    TDSCategory.NON_RESIDENT_PAYMENT: "Form 27Q (TDS on payments to non-residents) — consult a CA",
}


def next_deposit_deadline(transaction_date: date) -> str:
    """The general Indian TDS convention: deposit by the 7th of the month
    following the month of deduction (special-cased for March deductions,
    which get until 30 April). This is a convention, not a category-specific
    rule, so it's computed once here rather than per rule."""
    if transaction_date.month == 3:
        deadline = date(transaction_date.year, 4, 30)
    elif transaction_date.month == 12:
        deadline = date(transaction_date.year + 1, 1, 7)
    else:
        deadline = date(transaction_date.year, transaction_date.month + 1, 7)
    return deadline.isoformat()
