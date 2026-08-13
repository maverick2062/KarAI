from decimal import Decimal

from pydantic import BaseModel

from app.ais_mock.diffing import AISDiscrepancyType


class SimulateAISRequest(BaseModel):
    financial_year: str
    seed: int = 42


class DiscrepancyOut(BaseModel):
    discrepancy_type: AISDiscrepancyType
    reporting_entity: str
    category: str
    ais_amount: Decimal | None
    reported_amount: Decimal | None
    message: str


class DiscrepancyResponse(BaseModel):
    financial_year: str
    discrepancies: list[DiscrepancyOut]
