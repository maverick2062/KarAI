export interface TourStep {
  target: string;
  route: string;
  title: string;
  content: string;
  placement?: "top" | "bottom";
}

export const TOUR_STEPS: TourStep[] = [
  {
    target: '[data-tour="nav-links"]',
    route: "/dashboard",
    title: "Explore KarAI",
    content:
      "Use these links to move between the dashboard, transaction intake, TDS events, advance-tax estimates, reports, and settings.",
    placement: "bottom",
  },
  {
    target: '[data-tour="kpi-grid"]',
    route: "/dashboard",
    title: "Dashboard overview",
    content:
      "These cards summarize the transactions and TDS events in your account, including items that need manual review. Risk labels are prototype indicators, not tax conclusions.",
    placement: "bottom",
  },
  {
    target: '[data-tour="deadlines-card"]',
    route: "/dashboard",
    title: "Upcoming dates",
    content:
      "Once transactions are available, this area lists dates associated with flagged events. Confirm applicable payment and filing deadlines with a qualified tax professional.",
    placement: "top",
  },
  {
    target: '[data-tour="ingest-demo"]',
    route: "/transactions",
    title: "Try the demo feed",
    content:
      "Generate synthetic transactions to see how the current configured rules evaluate payment records. This is demo data, not a live bank feed.",
    placement: "bottom",
  },
  {
    target: '[data-tour="ingest-csv"]',
    route: "/transactions",
    title: "Upload transactions",
    content:
      "Upload a CSV with the required columns or drop it into this area. Check the required columns and review the returned explanations after processing.",
    placement: "top",
  },
  {
    target: '[data-tour="ingest-manual"]',
    route: "/transactions",
    title: "Enter a transaction",
    content:
      "Record a payment and provide any relevant payer, payee, and payment details. Missing facts may cause an event to be marked for manual review.",
    placement: "top",
  },
  {
    target: '[data-tour="tds-filters"]',
    route: "/tds-events",
    title: "Filter TDS events",
    content:
      "Use these buttons to filter recorded events and find transactions that were flagged or need more information.",
    placement: "bottom",
  },
  {
    target: '[data-tour="tds-table"]',
    route: "/tds-events",
    title: "Review explanations",
    content:
      "Open an event to review its inputs and rule-based explanation. The rule table is advisory and does not replace professional review.",
    placement: "top",
  },
  {
    target: '[data-tour="planner-form"]',
    route: "/advance-tax",
    title: "Advance-tax estimate",
    content:
      "Enter an income estimate to compare the configured old- and new-regime calculations and view an installment projection. Verify the current law and your facts before acting.",
    placement: "bottom",
  },
  {
    target: '[data-tour="reports-generate"]',
    route: "/reports",
    title: "Generate a report",
    content:
      "Create a report from the records available in this prototype. A generated report is not a filed return or a certification of tax compliance.",
    placement: "bottom",
  },
];
