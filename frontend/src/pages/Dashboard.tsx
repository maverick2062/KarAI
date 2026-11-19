import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AisApi, TdsApi, TransactionsApi } from "../api/endpoints";
import type { DiscrepancyOut } from "../api/types";
import { ApiError } from "../api/client";
import { KpiCard } from "../components/KpiCard";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { currentFinancialYear, formatCurrency } from "../utils/financialYear";

export function Dashboard() {
  const financialYear = currentFinancialYear();
  const [openTransactionCount, setOpenTransactionCount] = useState(0);
  const [syntheticFeedCount, setSyntheticFeedCount] = useState(0);
  const [flaggedCount, setFlaggedCount] = useState(0);
  const [needsReviewCount, setNeedsReviewCount] = useState(0);
  const [totalTdsDue, setTotalTdsDue] = useState(0);
  const [upcomingDeadlines, setUpcomingDeadlines] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [discrepancies, setDiscrepancies] = useState<DiscrepancyOut[] | null>(null);
  const [isCheckingAis, setIsCheckingAis] = useState(false);
  const [isRemovingFeed, setIsRemovingFeed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      TransactionsApi.list({ financialYear, includeCompleted: false, limit: 1, signal: controller.signal }),
      TransactionsApi.list({ financialYear, sourceType: "synthetic_feed", limit: 1, signal: controller.signal }),
      TdsApi.list({ financialYear, transactionCompleted: false, limit: 100, signal: controller.signal }),
    ])
      .then(([activeTransactions, syntheticTransactions, events]) => {
        setOpenTransactionCount(activeTransactions.total);
        setSyntheticFeedCount(syntheticTransactions.total);
        setFlaggedCount(events.flagged_count);
        setNeedsReviewCount(events.needs_review_count);
        setTotalTdsDue(Number(events.total_tds_due));
        setUpcomingDeadlines(events.upcoming_deadlines);
      })
      .catch((err: unknown) => {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          setError("Could not load dashboard data.");
        }
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, [financialYear]);

  let riskLevel: "default" | "success" | "warning" | "danger" = "success";
  if (flaggedCount > 10) riskLevel = "danger";
  else if (flaggedCount > 3) riskLevel = "warning";

  async function handleRemoveSyntheticFeed() {
    if (!window.confirm("Remove the simulated bank feed from your dashboard? This does not affect uploaded or manually entered transactions.")) {
      return;
    }
    setIsRemovingFeed(true);
    setError(null);
    try {
      await TransactionsApi.removeSyntheticFeed(financialYear);
      const [activeTransactions, syntheticTransactions, events] = await Promise.all([
        TransactionsApi.list({ financialYear, includeCompleted: false, limit: 1 }),
        TransactionsApi.list({ financialYear, sourceType: "synthetic_feed", limit: 1 }),
        TdsApi.list({ financialYear, transactionCompleted: false, limit: 100 }),
      ]);
      setOpenTransactionCount(activeTransactions.total);
      setSyntheticFeedCount(syntheticTransactions.total);
      setFlaggedCount(events.flagged_count);
      setNeedsReviewCount(events.needs_review_count);
      setTotalTdsDue(Number(events.total_tds_due));
      setUpcomingDeadlines(events.upcoming_deadlines);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not remove the simulated feed.");
    } finally {
      setIsRemovingFeed(false);
    }
  }

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
          <div className="kpi-grid" data-tour="kpi-grid">
            <KpiCard label="Open transactions" value={String(openTransactionCount)} />
            <KpiCard label="Unpaid TDS events" value={String(flaggedCount)} tone={riskLevel} />
            <KpiCard label="TDS still due" value={formatCurrency(totalTdsDue)} tone={flaggedCount ? "warning" : "default"} />
            <KpiCard label="Needs manual review" value={String(needsReviewCount)} tone={needsReviewCount ? "danger" : "success"} />
            <KpiCard
              label="Overall risk level"
              value={riskLevel === "danger" ? "High" : riskLevel === "warning" ? "Medium" : "Low"}
              tone={riskLevel}
            />
          </div>

          {openTransactionCount === 0 ? (
            <div className="empty-state" data-tour="deadlines-card">
              <p>No open transactions. Add a transaction or try the simulated feed for reference.</p>
              <Link className="button button--primary" to="/transactions">
                Ingest transactions
              </Link>
            </div>
          ) : (
            <div className="card" data-tour="deadlines-card">
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

          {openTransactionCount > 0 && (
            <div className="card" data-tour="ais-card">
              <h2>Check against your AIS</h2>
              <p>
                Compares your reported transactions against simulated Annual Information Statement data.
                This is a prototype comparison, not a connection to the Income Tax Department.
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
          {syntheticFeedCount > 0 && (
            <div className="card">
              <h2>Simulated bank feed</h2>
              <p>{syntheticFeedCount} reference transaction(s); demo data is excluded from Recent Transactions and cannot be marked paid or deleted individually.</p>
              <button className="button button--danger" onClick={handleRemoveSyntheticFeed} disabled={isRemovingFeed}>
                {isRemovingFeed ? "Removing…" : "Remove simulated feed"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
