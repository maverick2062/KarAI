import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AisApi, TdsApi, TransactionsApi } from "../api/endpoints";
import type { DiscrepancyOut, TDSEventSummary, TransactionOut } from "../api/types";
import { ApiError } from "../api/client";
import { KpiCard } from "../components/KpiCard";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { currentFinancialYear, formatCurrency } from "../utils/financialYear";

export function Dashboard() {
  const financialYear = currentFinancialYear();
  const [transactions, setTransactions] = useState<TransactionOut[]>([]);
  const [tdsEvents, setTdsEvents] = useState<TDSEventSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [discrepancies, setDiscrepancies] = useState<DiscrepancyOut[] | null>(null);
  const [isCheckingAis, setIsCheckingAis] = useState(false);

  useEffect(() => {
    Promise.all([TransactionsApi.list(financialYear), TdsApi.list({ financialYear })])
      .then(([txns, events]) => {
        setTransactions(txns);
        setTdsEvents(events);
      })
      .catch(() => setError("Could not load dashboard data."))
      .finally(() => setIsLoading(false));
  }, [financialYear]);

  const flagged = tdsEvents.filter((e) => e.tds_applicable);
  const needsReview = tdsEvents.filter((e) => e.decision_status === "needs_review");
  const totalTdsDue = flagged.reduce((sum, e) => sum + Number(e.tds_amount ?? 0), 0);
  const upcomingDeadlines = [...new Set(flagged.map((e) => e.filing_deadline).filter(Boolean))]
    .sort()
    .slice(0, 5) as string[];

  let riskLevel: "default" | "success" | "warning" | "danger" = "success";
  if (flagged.length > 10) riskLevel = "danger";
  else if (flagged.length > 3) riskLevel = "warning";

  async function handleAisCheck() {
    setIsCheckingAis(true);
    try {
      const response = await AisApi.simulate(financialYear);
      setDiscrepancies(response.discrepancies);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not check AIS.");
    } finally {
      setIsCheckingAis(false);
    }
  }

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>Dashboard — FY {financialYear}</h1>

      {isLoading && <p>Loading…</p>}
      {error && <div className="alert alert--error">{error}</div>}

      {!isLoading && !error && (
        <>
          <div className="kpi-grid">
            <KpiCard label="Transactions processed" value={String(transactions.length)} />
            <KpiCard label="Flagged with TDS due" value={String(flagged.length)} tone={riskLevel} />
            <KpiCard label="Total TDS due" value={formatCurrency(totalTdsDue)} tone={flagged.length ? "warning" : "default"} />
            <KpiCard label="Needs manual review" value={String(needsReview.length)} tone={needsReview.length ? "danger" : "success"} />
            <KpiCard
              label="Overall risk level"
              value={riskLevel === "danger" ? "High" : riskLevel === "warning" ? "Medium" : "Low"}
              tone={riskLevel}
            />
          </div>

          {transactions.length === 0 ? (
            <div className="empty-state">
              <p>No transactions yet. Try a demo bank feed to see KarAI in action.</p>
              <Link className="button button--primary" to="/transactions">
                Ingest transactions
              </Link>
            </div>
          ) : (
            <div className="card">
              <h2>Upcoming TDS deposit deadlines</h2>
              {upcomingDeadlines.length === 0 ? (
                <p>No pending TDS deposits.</p>
              ) : (
                <ul className="deadline-list">
                  {upcomingDeadlines.map((deadline) => (
                    <li key={deadline}>{deadline}</li>
                  ))}
                </ul>
              )}
              <Link to="/tds-events">View all flagged transactions →</Link>
            </div>
          )}

          {transactions.length > 0 && (
            <div className="card">
              <h2>Check against your AIS</h2>
              <p>
                Compares your reported transactions against a (simulated) Annual Information Statement —
                the same pre-scrutiny check CBDT's own AI systems run, surfaced to you first.
              </p>
              <button className="button button--secondary" onClick={handleAisCheck} disabled={isCheckingAis}>
                {isCheckingAis ? "Checking…" : "Check against AIS"}
              </button>

              {discrepancies && (
                <ul className="result-list">
                  {discrepancies.length === 0 && <li>No discrepancies found.</li>}
                  {discrepancies.map((d, index) => (
                    <li key={index}>{d.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
