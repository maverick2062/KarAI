import { Fragment, useEffect, useState } from "react";
import { TdsApi } from "../api/endpoints";
import type { TDSEventPage } from "../api/types";
import { ApiError } from "../api/client";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { currentFinancialYear, formatCurrency } from "../utils/financialYear";

type Filter = "all" | "unpaid" | "not_applicable" | "needs_review" | "paid";
const PAGE_SIZE = 25;

export function TDSEvents() {
  const financialYear = currentFinancialYear();
  const [page, setPage] = useState<TDSEventPage | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setOffset(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    TdsApi.list({
      financialYear,
      search: search || undefined,
      tdsApplicable: filter === "unpaid" ? true : filter === "not_applicable" ? false : undefined,
      decisionStatus:
        filter === "needs_review"
          ? "needs_review"
          : filter === "not_applicable"
            ? "not_applicable"
            : undefined,
      transactionCompleted: filter === "paid" ? true : filter === "unpaid" ? false : undefined,
      limit: PAGE_SIZE,
      offset,
      signal: controller.signal,
    })
      .then(setPage)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof ApiError ? String(err.detail) : "Could not load TDS events.");
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, [financialYear, filter, offset, search]);

  function chooseFilter(nextFilter: Filter) {
    setFilter(nextFilter);
    setOffset(0);
    setExpandedId(null);
  }

  const events = page?.items ?? [];
  const from = page && page.total > 0 ? page.offset + 1 : 0;
  const to = page ? Math.min(page.offset + page.limit, page.total) : 0;

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>TDS Events — FY {financialYear}</h1>

      <label className="event-search">
        Search transactions
        <input
          type="search"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Description, payee, or exact amount"
          aria-describedby="event-search-hint"
        />
        <span id="event-search-hint" className="field-hint">
          Search terms match description or payee prefixes; a number searches the exact transaction amount.
        </span>
      </label>

      <div className="filter-bar" data-tour="tds-filters" aria-label="Filter TDS events">
        {([
          ["all", "All"],
          ["unpaid", "Unpaid TDS"],
          ["paid", "TDS paid"],
          ["not_applicable", "No TDS"],
          ["needs_review", "Needs review"],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            className={filter === value ? "chip chip--active" : "chip"}
            onClick={() => chooseFilter(value)}
            aria-pressed={filter === value}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="alert alert--error">{error}</div>}
      {isLoading && <p>Loading…</p>}
      {!isLoading && page?.total === 0 && <p className="empty-state">No transactions match this search and filter.</p>}

      <p className="field-hint" aria-live="polite">
        {page ? `Showing ${from}–${to} of ${page.total} events` : ""}
      </p>

      <table className="data-table data-table--responsive" data-tour="tds-table">
        <thead>
          <tr>
            <th>Transaction date</th>
            <th>Transaction</th>
            <th>Amount</th>
            <th>TDS due</th>
            <th>Rate</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <Fragment key={event.id}>
              <tr
                className="data-table__event-row data-table__row--clickable"
                onClick={() => setExpandedId(expandedId === event.id ? null : event.id)}
              >
                <td data-label="Transaction date">{event.transaction_date ?? "—"}</td>
                <td data-label="Transaction">
                  {event.transaction_description || event.transaction_party_name || event.category.replace(/_/g, " ")}
                </td>
                <td data-label="Amount">
                  {event.transaction_amount !== null ? formatCurrency(event.transaction_amount) : "—"}
                </td>
                <td data-label="TDS due">
                  {event.tds_amount !== null ? formatCurrency(event.tds_amount) : "Not calculated"}
                </td>
                <td data-label="Rate">{event.rate_percent !== null ? `${event.rate_percent}%` : "—"}</td>
                <td data-label="Status">
                  {event.transaction_is_completed ? (
                    <span className="badge badge--success">TDS paid</span>
                  ) : event.decision_status === "needs_review" ? (
                    <span className="badge badge--danger">Needs review</span>
                  ) : event.tds_applicable ? (
                    <span className="badge badge--warning">Unpaid TDS</span>
                  ) : (
                    <span className="badge badge--success">No TDS</span>
                  )}
                  {event.pan_not_provided && <span className="badge badge--danger">PAN missing</span>}
                </td>
                <td className="data-table__expand" aria-label="Show event details">
                  {expandedId === event.id ? "▲" : "▼"}
                </td>
              </tr>
              {expandedId === event.id && (
                <tr className="data-table__detail-row">
                  <td colSpan={7} className="explanation-row" data-label="Explanation">
                    <p>{event.explanation_text}</p>
                    {event.review_reason && <p><strong>Missing or unsupported fact:</strong> {event.review_reason}</p>}
                    {event.filing_form_reference && (
                      <p>
                        <strong>File:</strong> {event.filing_form_reference}
                        {event.filing_deadline && <> — by {event.filing_deadline}</>}
                      </p>
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>

      <div className="button-row pagination-controls">
        <button
          className="button button--secondary"
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={isLoading || offset === 0}
        >
          Previous
        </button>
        <button
          className="button button--secondary"
          onClick={() => setOffset(offset + PAGE_SIZE)}
          disabled={isLoading || !page || offset + page.limit >= page.total}
        >
          Next
        </button>
      </div>
    </div>
  );
}
