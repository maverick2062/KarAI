import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { TransactionsApi } from "../api/endpoints";
import type { IngestionResponse } from "../api/types";
import { ApiError } from "../api/client";
import { DisclaimerBanner } from "../components/DisclaimerBanner";

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return typeof err.detail === "string" ? err.detail : "Request failed.";
  return "Something went wrong. Please try again.";
}

export function TransactionIngestion() {
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [manualEntry, setManualEntry] = useState({
    transaction_date: new Date().toISOString().slice(0, 10),
    amount: "",
    party_name: "",
    description: "",
    party_pan: "",
    party_pan_provided: "unknown",
  });

  useEffect(() => {
    if (!notification) return;
    const timeout = window.setTimeout(() => setNotification(null), 7000);
    return () => window.clearTimeout(timeout);
  }, [notification]);

  function showIngestionNotification(response: IngestionResponse) {
    setResult(response);
    const flagged = response.tds_events.filter((event) => event.tds_applicable);
    setNotification(
      flagged.length
        ? `${flagged.length} payment(s) flagged for TDS. Review the TDS event details below.`
        : "Transactions processed. No TDS was triggered.",
    );
  }

  async function handleFile(file: File) {
    setError(null);
    setIsBusy(true);
    try {
      const response = await TransactionsApi.uploadCsv(file);
      showIngestionNotification(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsBusy(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  async function handleSimulate() {
    setError(null);
    setIsBusy(true);
    try {
      const response = await TransactionsApi.simulate(42);
      showIngestionNotification(response);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleManualSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsBusy(true);
    try {
      const response = await TransactionsApi.manualEntry([{
        ...manualEntry,
        amount: manualEntry.amount,
        party_pan: manualEntry.party_pan || null,
        party_pan_provided:
          manualEntry.party_pan_provided === "unknown"
            ? null
            : manualEntry.party_pan_provided === "yes",
      }]);
      showIngestionNotification(response);
      setManualEntry({
        ...manualEntry,
        amount: "",
        party_name: "",
        description: "",
        party_pan: "",
        party_pan_provided: "unknown",
      });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>Ingest transactions</h1>
      {notification && (
        <div className="toast" role="status" aria-live="polite">
          <span>{notification}</span>
          <button className="toast__close" onClick={() => setNotification(null)} aria-label="Dismiss notification">
            ×
          </button>
        </div>
      )}
      <p className="page__subtitle">
        No live bank connection exists yet in this prototype (that needs an RBI Account Aggregator
        partnership) — use a CSV upload, manual entry, or the demo feed below.
      </p>

      {error && <div className="alert alert--error">{error}</div>}

      <div className="card">
        <h2>Try a demo bank feed</h2>
        <p>Generates a year of realistic recurring payments so you can see TDS detection immediately.</p>
        <button className="button button--primary" onClick={handleSimulate} disabled={isBusy}>
          {isBusy ? "Working…" : "Simulate bank feed"}
        </button>
      </div>

      <div className="card">
        <h2>Upload CSV</h2>
        <div
          className={"drop-zone" + (isDragActive ? " drop-zone--active" : "")}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragActive(true);
          }}
          onDragLeave={() => setIsDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <p>Drag & drop a CSV here, or click to browse</p>
          <p className="field-hint">Required columns: transaction_date, amount, party_name (up to 50 MB)</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </div>

      <div className="card">
        <h2>Manual entry</h2>
        <form className="manual-entry-form" onSubmit={handleManualSubmit}>
          <label>
            Date
            <input
              type="date"
              required
              value={manualEntry.transaction_date}
              onChange={(e) => setManualEntry({ ...manualEntry, transaction_date: e.target.value })}
            />
          </label>
          <label>
            Amount (₹)
            <input
              type="number"
              required
              min="0.01"
              step="0.01"
              value={manualEntry.amount}
              onChange={(e) => setManualEntry({ ...manualEntry, amount: e.target.value })}
            />
          </label>
          <label>
            Paid to
            <input
              required
              value={manualEntry.party_name}
              onChange={(e) => setManualEntry({ ...manualEntry, party_name: e.target.value })}
            />
          </label>
          <label>
            Description
            <input
              placeholder="e.g. Professional consulting fee"
              value={manualEntry.description}
              onChange={(e) => setManualEntry({ ...manualEntry, description: e.target.value })}
            />
          </label>
          <label>
            Payee PAN (optional)
            <input
              autoComplete="off"
              maxLength={10}
              placeholder="ABCDE1234F"
              value={manualEntry.party_pan}
              onChange={(e) =>
                setManualEntry({
                  ...manualEntry,
                  party_pan: e.target.value.toUpperCase(),
                  party_pan_provided: e.target.value ? "yes" : manualEntry.party_pan_provided,
                })
              }
            />
            <span className="field-hint">PAN is encrypted at rest. A supplied PAN is format-checked only.</span>
          </label>
          <label>
            PAN furnished?
            <select
              value={manualEntry.party_pan_provided}
              onChange={(e) =>
                setManualEntry({
                  ...manualEntry,
                  party_pan_provided: e.target.value,
                  party_pan: e.target.value === "no" ? "" : manualEntry.party_pan,
                })
              }
            >
              <option value="unknown">Not known</option>
              <option value="yes">Yes</option>
              <option value="no">No — apply higher rate</option>
            </select>
          </label>
          <button className="button button--primary" type="submit" disabled={isBusy}>
            Add transaction
          </button>
        </form>
      </div>

      {result && (
        <div className="card">
          <h2>Ingestion result</h2>
          <p>
            {result.transactions_created} transaction(s) processed, {result.tds_events_created} evaluated for TDS.
          </p>
          <ul className="result-list">
            {result.tds_events.map((event) => (
              <li key={event.id} className={event.tds_applicable ? "result-list__item--flagged" : ""}>
                <strong>{event.category}</strong> — {event.tds_applicable ? "TDS due" : "No TDS due"}
                  {event.pan_not_provided && <span className="badge badge--danger"> PAN missing · 20%+ rate</span>}
                  <p>{event.explanation_text}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
