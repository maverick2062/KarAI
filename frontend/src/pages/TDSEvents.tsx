import { Fragment, useEffect, useMemo, useState } from "react";
import { TdsApi } from "../api/endpoints";
import type { TDSEventSummary } from "../api/types";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { currentFinancialYear, formatCurrency } from "../utils/financialYear";

type Filter = "all" | "flagged" | "not_flagged";

export function TDSEvents() {
  const financialYear = currentFinancialYear();
  const [events, setEvents] = useState<TDSEventSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    TdsApi.list({ financialYear })
      .then(setEvents)
      .finally(() => setIsLoading(false));
  }, [financialYear]);

  const filteredEvents = useMemo(() => {
    if (filter === "flagged") return events.filter((e) => e.tds_applicable);
    if (filter === "not_flagged") return events.filter((e) => !e.tds_applicable);
    return events;
  }, [events, filter]);

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>TDS Events — FY {financialYear}</h1>

      <div className="filter-bar">
        <button className={filter === "all" ? "chip chip--active" : "chip"} onClick={() => setFilter("all")}>
          All ({events.length})
        </button>
        <button
          className={filter === "flagged" ? "chip chip--active" : "chip"}
          onClick={() => setFilter("flagged")}
        >
          TDS due ({events.filter((e) => e.tds_applicable).length})
        </button>
        <button
          className={filter === "not_flagged" ? "chip chip--active" : "chip"}
          onClick={() => setFilter("not_flagged")}
        >
          No TDS due
        </button>
      </div>

      {isLoading && <p>Loading…</p>}

      {!isLoading && filteredEvents.length === 0 && <p className="empty-state">No transactions match this filter.</p>}

      <table className="data-table data-table--responsive">
        <thead>
          <tr>
            <th>Category</th>
            <th>Amount</th>
            <th>TDS Due</th>
            <th>Rate</th>
            <th>Risk</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {filteredEvents.map((event) => (
            <Fragment key={event.id}>
              <tr
                className="data-table__event-row data-table__row--clickable"
                onClick={() => setExpandedId(expandedId === event.id ? null : event.id)}
              >
                <td data-label="Category">{event.category.replace(/_/g, " ")}</td>
                <td data-label="Payment total">{formatCurrency(event.cumulative_after)}</td>
                <td data-label="TDS amount">{event.tds_applicable ? formatCurrency(event.tds_amount) : "—"}</td>
                <td data-label="Rate">{event.rate_percent}%</td>
                <td data-label="Flags">
                  {event.pan_not_provided && (
                    <span className="badge badge--danger">PAN missing</span>
                  )}
                  <span className={"badge " + (event.tds_applicable ? "badge--warning" : "badge--success")}>
                    {event.tds_applicable ? "TDS due" : "Clear"}
                  </span>
                </td>
                <td className="data-table__expand" aria-label="Show event details">
                  {expandedId === event.id ? "▲" : "▼"}
                </td>
              </tr>
              {expandedId === event.id && (
                <tr className="data-table__detail-row">
                  <td colSpan={6} className="explanation-row" data-label="Explanation">
                    <p>{event.explanation_text}</p>
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
    </div>
  );
}
