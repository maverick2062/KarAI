export type UserRole = "individual" | "tax_consultant" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_hours: number;
}

export interface TDSEventSummary {
  id: string;
  transaction_id: string;
  transaction_date: string | null;
  transaction_amount: string | null;
  transaction_description: string | null;
  transaction_party_name: string | null;
  transaction_is_completed: boolean;
  category: string;
  decision_status: "applicable" | "not_applicable" | "needs_review";
  review_reason: string | null;
  tds_applicable: boolean;
  threshold_crossed_this_transaction: boolean;
  pan_not_provided: boolean;
  cumulative_before: string;
  cumulative_after: string;
  taxable_amount: string | null;
  tds_amount: string | null;
  rate_percent: string | null;
  explanation_text: string;
  filing_form_reference: string | null;
  filing_deadline: string | null;
  created_at: string;
}

export interface TransactionOut {
  id: string;
  vendor_id: string | null;
  source_type: string;
  transaction_date: string;
  amount: string;
  description: string | null;
  declared_category: string | null;
  financial_year: string;
  created_at: string;
  is_completed: boolean;
  is_deleted: boolean;
  party_name: string | null;
  tds_applicable: boolean;
  tds_amount: string | null;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface TDSEventPage extends PageResponse<TDSEventSummary> {
  flagged_count: number;
  needs_review_count: number;
  total_tds_due: string;
  upcoming_deadlines: string[];
}

export interface IngestionResponse {
  transactions_created: number;
  tds_events_created: number;
  tds_events: TDSEventSummary[];
}

export type TaxRegime = "old" | "new";

export interface RegimeComparisonResponse {
  total_income: string;
  old_regime_tax: string;
  new_regime_tax: string;
  recommended_regime: TaxRegime;
  savings_with_recommended: string;
  slab_version: string;
}

export interface QuarterlyInstallmentOut {
  label: string;
  due_date: string;
  cumulative_percent_required: string;
  cumulative_amount_required: string;
  already_paid: string;
  installment_due: string;
  is_short: boolean;
  interest_234c: string;
}

export interface AdvanceTaxProjectionResponse {
  financial_year: string;
  total_income_estimate: string;
  regime: TaxRegime;
  tax_liability: string;
  advance_tax_required: boolean;
  installments: QuarterlyInstallmentOut[];
  interest_234b: string;
  slab_version: string;
}

export type AISDiscrepancyType = "amount_mismatch" | "missing_from_user_records" | "missing_from_ais";

export interface DiscrepancyOut {
  discrepancy_type: AISDiscrepancyType;
  reporting_entity: string;
  category: string;
  ais_amount: string | null;
  reported_amount: string | null;
  message: string;
}

export interface DiscrepancyResponse {
  financial_year: string;
  discrepancies: DiscrepancyOut[];
}

export type ReportType = "pdf" | "excel";

export interface ReportSummary {
  id: string;
  report_type: ReportType;
  financial_year: string;
  file_name: string;
  dataset_hash: string;
  rule_table_version: string;
  generated_at: string;
}
