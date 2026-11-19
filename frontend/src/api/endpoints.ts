import { ApiError, api, getToken } from "./client";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
import type {
  AdvanceTaxProjectionResponse,
  DiscrepancyResponse,
  IngestionResponse,
  RegimeComparisonResponse,
  ReportSummary,
  ReportType,
  PageResponse,
  TaxRegime,
  TDSEventPage,
  TokenResponse,
  TransactionOut,
  User,
  UserRole,
} from "./types";

export const AuthApi = {
  register: (email: string, fullName: string, password: string, role: UserRole = "individual") =>
    api.post<User>("/api/v1/auth/register", { email, full_name: fullName, password, role }),
  login: (email: string, password: string) => api.post<TokenResponse>("/api/v1/auth/login", { email, password }),
  logout: () => api.post<void>("/api/v1/auth/logout"),
  me: () => api.get<User>("/api/v1/auth/me"),
};

export const TransactionsApi = {
  simulate: (seed = 42) => api.post<IngestionResponse>("/api/v1/transactions/simulate", { seed }),
  manualEntry: (entries: Record<string, unknown>[]) =>
    api.post<IngestionResponse>("/api/v1/transactions/manual", { entries }),
  uploadCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.postForm<IngestionResponse>("/api/v1/transactions/upload-csv", formData);
  },
  uploadCsvWithProgress: (file: File, onProgress: (percent: number) => void) =>
    new Promise<IngestionResponse>((resolve, reject) => {
      const formData = new FormData();
      formData.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE_URL}/api/v1/transactions/upload-csv`);
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as IngestionResponse);
          } catch {
            reject(new Error("The server returned an invalid response."));
          }
        } else {
          let detail = "Could not upload the CSV.";
          try {
            const body = JSON.parse(xhr.responseText) as { detail?: unknown };
            if (typeof body.detail === "string") detail = body.detail;
          } catch {
            // Keep the generic upload error.
          }
          reject(new ApiError(xhr.status, detail));
        }
      };
      xhr.onerror = () => reject(new Error("Could not connect to the server."));
      xhr.send(formData);
    }),
  list: (options: {
    financialYear?: string;
    search?: string;
    sourceType?: string;
    recentOnly?: boolean;
    includeSynthetic?: boolean;
    includeCompleted?: boolean;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  } = {}) =>
    api.get<PageResponse<TransactionOut>>(
      "/api/v1/transactions",
      {
        financial_year: options.financialYear,
        search: options.search,
        source_type: options.sourceType,
        recent_only: options.recentOnly,
        include_synthetic: options.includeSynthetic,
        include_completed: options.includeCompleted,
        limit: options.limit,
        offset: options.offset,
      },
      options.signal,
    ),
  complete: (transactionId: string) =>
    api.patch<TransactionOut>(`/api/v1/transactions/${transactionId}/complete`),
  reopen: (transactionId: string) =>
    api.patch<TransactionOut>(`/api/v1/transactions/${transactionId}/reopen`),
  delete: (transactionId: string) =>
    api.delete<void>(`/api/v1/transactions/${transactionId}`),
  restore: (transactionId: string) =>
    api.patch<TransactionOut>(`/api/v1/transactions/${transactionId}/restore`),
  removeSyntheticFeed: (financialYear?: string) =>
    api.delete<{ transactions_removed: number }>("/api/v1/transactions/synthetic-feed", {
      financial_year: financialYear,
    }),
};

export const TdsApi = {
  list: (params?: {
    financialYear?: string;
    category?: string;
    decisionStatus?: string;
    tdsApplicable?: boolean;
    transactionCompleted?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  }) =>
    api.get<TDSEventPage>("/api/v1/tds-events", {
      financial_year: params?.financialYear,
      category: params?.category,
      decision_status: params?.decisionStatus,
      tds_applicable: params?.tdsApplicable,
      transaction_completed: params?.transactionCompleted,
      search: params?.search,
      limit: params?.limit,
      offset: params?.offset,
    }, params?.signal),
};

export const AdvanceTaxApi = {
  compareRegimes: (totalIncome: number) =>
    api.get<RegimeComparisonResponse>("/api/v1/advance-tax/compare-regimes", { total_income: totalIncome }),
  estimate: (financialYear: string, totalIncome: number, regime: TaxRegime, paidSoFar = 0) =>
    api.post<AdvanceTaxProjectionResponse>("/api/v1/advance-tax/estimate", {
      financial_year: financialYear,
      total_income_estimate: totalIncome,
      regime,
      paid_so_far: paidSoFar,
    }),
};

export const AisApi = {
  simulate: (financialYear: string, seed = 42) =>
    api.post<DiscrepancyResponse>("/api/v1/ais/simulate", { financial_year: financialYear, seed }),
  discrepancies: (financialYear: string) =>
    api.get<DiscrepancyResponse>("/api/v1/ais/discrepancies", { financial_year: financialYear }),
};

export const ReportsApi = {
  generate: (financialYear: string, reportType: ReportType) =>
    api.post<ReportSummary>("/api/v1/reports/generate", { financial_year: financialYear, report_type: reportType }),
  list: () => api.get<ReportSummary[]>("/api/v1/reports"),
  download: (reportId: string) => api.downloadBlob(`/api/v1/reports/${reportId}/download`),
};

export const UsersApi = {
  deleteMyAccount: () => api.delete<void>("/api/v1/users/me"),
};
