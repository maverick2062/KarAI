import { useState, type FormEvent } from "react";
import { AdvanceTaxApi } from "../api/endpoints";
import type { AdvanceTaxProjectionResponse, RegimeComparisonResponse, TaxRegime } from "../api/types";
import { ApiError } from "../api/client";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { currentFinancialYear, formatCurrency } from "../utils/financialYear";

export function AdvanceTaxPlanner() {
  const financialYear = currentFinancialYear();
  const [income, setIncome] = useState("1500000");
  const [regime, setRegime] = useState<TaxRegime>("new");
  const [comparison, setComparison] = useState<RegimeComparisonResponse | null>(null);
  const [projection, setProjection] = useState<AdvanceTaxProjectionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  async function handleCompare(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsBusy(true);
    try {
      const totalIncome = parseFloat(income);
      const [comparisonResult, projectionResult] = await Promise.all([
        AdvanceTaxApi.compareRegimes(totalIncome),
        AdvanceTaxApi.estimate(financialYear, totalIncome, regime),
      ]);
      setComparison(comparisonResult);
      setProjection(projectionResult);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not compute advance tax.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>Advance Tax Planner — FY {financialYear}</h1>

      <div className="card">
        <form className="planner-form" onSubmit={handleCompare}>
          <label>
            Estimated total income this year (₹)
            <input
              type="number"
              min="0"
              step="1000"
              required
              value={income}
              onChange={(e) => setIncome(e.target.value)}
            />
          </label>
          <label>
            Regime to plan against
            <select value={regime} onChange={(e) => setRegime(e.target.value as TaxRegime)}>
              <option value="new">New regime</option>
              <option value="old">Old regime</option>
            </select>
          </label>
          <button className="button button--primary" type="submit" disabled={isBusy}>
            {isBusy ? "Calculating…" : "Calculate"}
          </button>
        </form>
        {error && <div className="alert alert--error">{error}</div>}
      </div>

      {comparison && (
        <div className="card">
          <h2>Old vs New regime</h2>
          <div className="regime-comparison">
            <div className={comparison.recommended_regime === "old" ? "regime-box regime-box--recommended" : "regime-box"}>
              <h3>Old regime</h3>
              <p className="regime-box__amount">{formatCurrency(comparison.old_regime_tax)}</p>
            </div>
            <div className={comparison.recommended_regime === "new" ? "regime-box regime-box--recommended" : "regime-box"}>
              <h3>New regime</h3>
              <p className="regime-box__amount">{formatCurrency(comparison.new_regime_tax)}</p>
            </div>
          </div>
          <p>
            Recommended: <strong>{comparison.recommended_regime} regime</strong>, saving{" "}
            {formatCurrency(comparison.savings_with_recommended)}.
          </p>
        </div>
      )}

      {projection && (
        <div className="card">
          <h2>Quarterly installment schedule</h2>
          {!projection.advance_tax_required ? (
            <p>Estimated liability is below ₹10,000 — advance tax isn't required.</p>
          ) : (
            <>
              <p>Estimated total tax liability: {formatCurrency(projection.tax_liability)}</p>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Installment</th>
                    <th>Due date</th>
                    <th>Cumulative required</th>
                    <th>Status</th>
                    <th>Est. 234C interest</th>
                  </tr>
                </thead>
                <tbody>
                  {projection.installments.map((installment) => (
                    <tr key={installment.label}>
                      <td>{installment.label}</td>
                      <td>{installment.due_date}</td>
                      <td>{formatCurrency(installment.cumulative_amount_required)}</td>
                      <td>
                        <span className={"badge " + (installment.is_short ? "badge--danger" : "badge--success")}>
                          {installment.is_short ? "Shortfall" : "On track"}
                        </span>
                      </td>
                      <td>{installment.is_short ? formatCurrency(installment.interest_234c) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {parseFloat(projection.interest_234b) > 0 && (
                <p className="alert alert--warning">
                  Estimated Section 234B interest for underpayment: {formatCurrency(projection.interest_234b)}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
