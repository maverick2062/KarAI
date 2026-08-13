import { api } from "./client";
import type {
  AdvanceTaxProjectionResponse,
  DiscrepancyResponse,
  IngestionResponse,
  RegimeComparisonResponse,
  ReportSummary,
  ReportType,
  TaxRegime,
  TDSEventSummary,
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
  list: (financialYear?: string) =>
    api.get<TransactionOut[]>("/api/v1/transactions", { financial_year: financialYear, limit: 500 }),
};

export const TdsApi = {
  list: (params?: { financialYear?: string; category?: string; tdsApplicable?: boolean }) =>
    api.get<TDSEventSummary[]>("/api/v1/tds-events", {
      financial_year: params?.financialYear,
      category: params?.category,
      tds_applicable: params?.tdsApplicable,
      limit: 500,
    }),
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
