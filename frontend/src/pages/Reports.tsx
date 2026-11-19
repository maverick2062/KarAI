import { useEffect, useState } from "react";
import { ReportsApi } from "../api/endpoints";
import type { ReportSummary, ReportType } from "../api/types";
import { ApiError } from "../api/client";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { currentFinancialYear } from "../utils/financialYear";

export function Reports() {
  const financialYear = currentFinancialYear();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadReports() {
    setIsLoading(true);
    ReportsApi.list()
      .then(setReports)
      .catch(() => setError("Could not load report history."))
      .finally(() => setIsLoading(false));
  }

  useEffect(loadReports, []);

  async function handleGenerate(reportType: ReportType) {
    setError(null);
    setIsGenerating(true);
    try {
      await ReportsApi.generate(financialYear, reportType);
      loadReports();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Report generation failed.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDownload(report: ReportSummary) {
    try {
      const blob = await ReportsApi.download(report.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = report.file_name;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download report.");
    }
  }

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>Reports</h1>

      {error && <div className="alert alert--error">{error}</div>}

      <div className="card" data-tour="reports-generate">
        <h2>Generate a compliance report — FY {financialYear}</h2>
        <div className="button-row">
          <button className="button button--primary" onClick={() => handleGenerate("pdf")} disabled={isGenerating}>
            Generate PDF
          </button>
          <button className="button button--secondary" onClick={() => handleGenerate("excel")} disabled={isGenerating}>
            Generate Excel
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Report history</h2>
        {isLoading && <p>Loading…</p>}
        {!isLoading && reports.length === 0 && <p className="empty-state">No reports generated yet.</p>}
        {!isLoading && reports.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Financial Year</th>
                <th>Generated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id}>
                  <td>{report.report_type.toUpperCase()}</td>
                  <td>{report.financial_year}</td>
                  <td>{new Date(report.generated_at).toLocaleString()}</td>
                  <td>
                    <button className="button button--ghost" onClick={() => handleDownload(report)}>
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
