from datetime import datetime

from pydantic import BaseModel

from app.models.report import ReportType


class GenerateReportRequest(BaseModel):
    financial_year: str
    report_type: ReportType


class ReportSummary(BaseModel):
    id: str
    report_type: ReportType
    financial_year: str
    file_name: str
    dataset_hash: str
    rule_table_version: str
    generated_at: datetime

    model_config = {"from_attributes": True}
