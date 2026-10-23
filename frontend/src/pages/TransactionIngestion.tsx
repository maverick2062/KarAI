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
    declared_category: "",
    party_pan: "",
    party_pan_provided: "unknown",
    party_is_non_resident: "",
    payer_is_specified_person: "",
    payer_is_designated_person: "",
    payee_is_individual_or_huf: "",
    service_kind: "",
    property_stamp_duty_value: "",
    property_consideration_total: "",
    property_payment_is_full_consideration: false,
    payee_is_individual_shareholder: "",
    dividend_payment_is_non_cash: "",
    lottery_winnings_kind: "",
    lottery_winnings_are_cash: "",
    vda_payer_is_individual_or_huf: "",
    vda_payer_turnover_within_limit: "",
    vda_payer_has_business_income: "",
    vda_consideration_is_cash: "",
  });

  useEffect(() => {
    if (!notification) return;
    const timeout = window.setTimeout(() => setNotification(null), 7000);
    return () => window.clearTimeout(timeout);
  }, [notification]);

  function showIngestionNotification(response: IngestionResponse) {
    setResult(response);
    const flagged = response.tds_events.filter((event) => event.tds_applicable);
    const reviews = response.tds_events.filter((event) => event.decision_status === "needs_review");
    setNotification(
      `${flagged.length} payment(s) flagged for TDS; ${reviews.length} need manual review.`,
    );
  }

  function optionalBoolean(value: string): boolean | null {
    return value === "" ? null : value === "yes";
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
      const rule_context = {
        payer_is_specified_person: optionalBoolean(manualEntry.payer_is_specified_person),
        payer_is_designated_person: optionalBoolean(manualEntry.payer_is_designated_person),
        payee_is_individual_or_huf: optionalBoolean(manualEntry.payee_is_individual_or_huf),
        service_kind: manualEntry.service_kind || null,
        property_stamp_duty_value: manualEntry.property_stamp_duty_value || null,
        property_consideration_total: manualEntry.property_consideration_total || null,
        property_payment_is_full_consideration: manualEntry.property_payment_is_full_consideration,
        payee_is_individual_shareholder: optionalBoolean(manualEntry.payee_is_individual_shareholder),
        dividend_payment_is_non_cash: optionalBoolean(manualEntry.dividend_payment_is_non_cash),
        lottery_winnings_kind: manualEntry.lottery_winnings_kind || null,
        lottery_winnings_are_cash: optionalBoolean(manualEntry.lottery_winnings_are_cash),
        vda_payer_is_individual_or_huf: optionalBoolean(manualEntry.vda_payer_is_individual_or_huf),
        vda_payer_turnover_within_limit: optionalBoolean(manualEntry.vda_payer_turnover_within_limit),
        vda_payer_has_business_income: optionalBoolean(manualEntry.vda_payer_has_business_income),
        vda_consideration_is_cash: optionalBoolean(manualEntry.vda_consideration_is_cash),
      };
      const response = await TransactionsApi.manualEntry([{
        ...manualEntry,
        amount: manualEntry.amount,
        declared_category: manualEntry.declared_category || null,
        rule_context,
        party_pan: manualEntry.party_pan || null,
        party_is_non_resident: manualEntry.party_is_non_resident === "yes",
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
        declared_category: "",
        party_pan: "",
        party_pan_provided: "unknown",
        party_is_non_resident: "",
        payer_is_specified_person: "",
        payer_is_designated_person: "",
        payee_is_individual_or_huf: "",
        service_kind: "",
        property_stamp_duty_value: "",
        property_consideration_total: "",
        property_payment_is_full_consideration: false,
        payee_is_individual_shareholder: "",
        dividend_payment_is_non_cash: "",
        lottery_winnings_kind: "",
        lottery_winnings_are_cash: "",
        vda_payer_is_individual_or_huf: "",
        vda_payer_turnover_within_limit: "",
        vda_payer_has_business_income: "",
        vda_consideration_is_cash: "",
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
            TDS category (confirm if known)
            <select
              value={manualEntry.declared_category}
              onChange={(e) => setManualEntry({ ...manualEntry, declared_category: e.target.value })}
            >
              <option value="">Infer from description</option>
              <option value="professional_fees">Professional / technical fees</option>
              <option value="rent">Rent</option>
              <option value="contractor_payments">Contractor payments</option>
              <option value="commission_brokerage">Commission / brokerage</option>
              <option value="interest_other_than_securities">Interest</option>
              <option value="dividend">Dividend</option>
              <option value="lottery_winnings">Lottery / game winnings</option>
              <option value="property_purchase">Property purchase</option>
              <option value="virtual_digital_assets">Virtual digital assets</option>
            </select>
          </label>
          {(manualEntry.declared_category === "professional_fees" ||
            manualEntry.declared_category === "commission_brokerage") && (
            <label>
              Is the payer a specified person?
              <select value={manualEntry.payer_is_specified_person} onChange={(e) =>
                setManualEntry({ ...manualEntry, payer_is_specified_person: e.target.value })
              }>
                <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
              </select>
            </label>
          )}
          {manualEntry.declared_category === "professional_fees" && (
            <label>
              Service type
              <select value={manualEntry.service_kind} onChange={(e) =>
                setManualEntry({ ...manualEntry, service_kind: e.target.value })
              }>
                <option value="">Unknown</option>
                <option value="professional">Professional service</option>
                <option value="technical">Technical service</option>
                <option value="call_centre">Call-centre operation</option>
                <option value="cinematographic_royalty">Cinematographic-film royalty</option>
              </select>
            </label>
          )}
          {manualEntry.declared_category === "contractor_payments" && (
            <>
              <label>
                Is the payer a designated person?
                <select value={manualEntry.payer_is_designated_person} onChange={(e) =>
                  setManualEntry({ ...manualEntry, payer_is_designated_person: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
              <label>
                Is the contractor an individual/HUF?
                <select value={manualEntry.payee_is_individual_or_huf} onChange={(e) =>
                  setManualEntry({ ...manualEntry, payee_is_individual_or_huf: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
            </>
          )}
          {manualEntry.declared_category === "property_purchase" && (
            <>
              <label>Stamp-duty value (₹)<input type="number" min="0.01" step="0.01" value={manualEntry.property_stamp_duty_value} onChange={(e) =>
                setManualEntry({ ...manualEntry, property_stamp_duty_value: e.target.value })
              } /></label>
              <label>Total property consideration (₹)<input type="number" min="0.01" step="0.01" value={manualEntry.property_consideration_total} onChange={(e) =>
                setManualEntry({ ...manualEntry, property_consideration_total: e.target.value })
              } /></label>
              <label>
                <input
                  type="checkbox"
                  checked={manualEntry.property_payment_is_full_consideration}
                  onChange={(e) =>
                    setManualEntry({ ...manualEntry, property_payment_is_full_consideration: e.target.checked })
                  }
                />
                This transaction is the full property consideration (not an installment)
              </label>
            </>
          )}
          {manualEntry.declared_category === "dividend" && (
            <>
              <label>
                Is the shareholder an individual?
                <select value={manualEntry.payee_is_individual_shareholder} onChange={(e) =>
                  setManualEntry({ ...manualEntry, payee_is_individual_shareholder: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
              <label>
                Is the payment non-cash?
                <select value={manualEntry.dividend_payment_is_non_cash} onChange={(e) =>
                  setManualEntry({ ...manualEntry, dividend_payment_is_non_cash: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
            </>
          )}
          {manualEntry.declared_category === "virtual_digital_assets" && (
            <>
              <label>
                Is VDA consideration paid in cash?
                <select value={manualEntry.vda_consideration_is_cash} onChange={(e) =>
                  setManualEntry({ ...manualEntry, vda_consideration_is_cash: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
              <label>
                Is the payer an individual/HUF?
                <select value={manualEntry.vda_payer_is_individual_or_huf} onChange={(e) =>
                  setManualEntry({ ...manualEntry, vda_payer_is_individual_or_huf: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
              {manualEntry.vda_payer_is_individual_or_huf === "yes" && (
                <>
                  <label>
                    Was the payer's preceding-year business/professional turnover within the statutory limit?
                    <select value={manualEntry.vda_payer_turnover_within_limit} onChange={(e) =>
                      setManualEntry({ ...manualEntry, vda_payer_turnover_within_limit: e.target.value })
                    }>
                      <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                    </select>
                  </label>
                  <label>
                    Did the payer have income under business/profession?
                    <select value={manualEntry.vda_payer_has_business_income} onChange={(e) =>
                      setManualEntry({ ...manualEntry, vda_payer_has_business_income: e.target.value })
                    }>
                      <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                    </select>
                  </label>
                </>
              )}
            </>
          )}
          {manualEntry.declared_category === "lottery_winnings" && (
            <>
              <label>
                Winnings type
                <select value={manualEntry.lottery_winnings_kind} onChange={(e) =>
                  setManualEntry({ ...manualEntry, lottery_winnings_kind: e.target.value })
                }>
                  <option value="">Unknown / other</option>
                  <option value="lottery">Lottery</option>
                  <option value="crossword">Crossword puzzle</option>
                  <option value="card_game">Card game</option>
                  <option value="game_show">Game show</option>
                  <option value="other_game">Other game</option>
                  <option value="gambling_betting">Gambling / betting</option>
                </select>
              </label>
              <label>
                Are the winnings paid in cash?
                <select value={manualEntry.lottery_winnings_are_cash} onChange={(e) =>
                  setManualEntry({ ...manualEntry, lottery_winnings_are_cash: e.target.value })
                }>
                  <option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
                </select>
              </label>
            </>
          )}
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
            Is the payee non-resident?
            <select
              value={manualEntry.party_is_non_resident}
              onChange={(e) => setManualEntry({ ...manualEntry, party_is_non_resident: e.target.value })}
            >
              <option value="">Unknown</option>
              <option value="no">No / resident</option>
              <option value="yes">Yes — manual treaty review required</option>
            </select>
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
                <strong>{event.category}</strong> — {event.decision_status === "needs_review"
                  ? "Needs manual review"
                  : event.tds_applicable ? "TDS due" : "No TDS due"}
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
