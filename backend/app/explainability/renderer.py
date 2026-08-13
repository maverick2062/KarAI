"""Template-based plain-language explanation generator.

Deliberately NOT a black-box ML explainer (no SHAP/LIME here): every number
in a TDS computation comes from a deterministic rule lookup, so the
"explanation" is a matter of clearly narrating that lookup, not approximating
a model's behaviour. This is what the research materials call the XAI-for-tax
layer — "This deduction is under Section 393 (Table Item 3) at 10% because
your total payments crossed ₹30,000" rather than just a bare number.
"""

from app.rule_engine.evaluate import TDSComputationResult
from app.rule_engine.section_393 import RULE_TABLE_DISCLAIMER


def render_explanation(result: TDSComputationResult, vendor_name: str) -> str:
    if result.rule is None:
        return (
            "This transaction wasn't classified under any Section 393 TDS category, "
            "so no deduction is suggested. If this looks wrong, set a category explicitly. "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    rule = result.rule

    if not result.tds_applicable:
        remaining = rule.threshold_amount - result.cumulative_after
        return (
            f"No TDS due yet under {rule.table_item}. Your total payments to {vendor_name} "
            f"this financial year are ₹{result.cumulative_after:,.2f}, below the "
            f"₹{rule.threshold_amount:,.2f} threshold (₹{remaining:,.2f} remaining before TDS applies). "
            f"{RULE_TABLE_DISCLAIMER}"
        )

    if result.threshold_crossed_this_transaction:
        return (
            f"This payment took your total payments to {vendor_name} this financial year to "
            f"₹{result.cumulative_after:,.2f}, crossing the ₹{rule.threshold_amount:,.2f} threshold under "
            f"{rule.table_item}. TDS of {rule.rate_percent}% now applies on the full "
            f"₹{result.taxable_amount:,.2f} paid so far this year (₹{result.tds_amount:,.2f}), including "
            f"catch-up on earlier payments to the same payee. {rule.rate_notes} {RULE_TABLE_DISCLAIMER}"
        )

    return (
        f"TDS applies under {rule.table_item} because your payments to {vendor_name} already "
        f"crossed the ₹{rule.threshold_amount:,.2f} threshold earlier this financial year. "
        f"Deduct {rule.rate_percent}% (₹{result.tds_amount:,.2f}) on this ₹{result.taxable_amount:,.2f} "
        f"payment. {rule.rate_notes} {RULE_TABLE_DISCLAIMER}"
    )
