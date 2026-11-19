"""Import every model module so SQLAlchemy's mapper registry (and Alembic's
autogenerate) sees the full schema and can resolve string-based relationship
forward references between them."""

from app.models.advance_tax import AdvanceTaxEstimate, TaxRegime
from app.models.ais_record import AISRecord, AISSourceType
from app.models.audit_log import AuditLog
from app.models.report import Report, ReportType
from app.models.revoked_token import RevokedToken
from app.models.tds_event import TDSEvent
from app.models.transaction import Transaction, TransactionSourceType
from app.models.transaction_search_term import TransactionSearchTerm
from app.models.user import User, UserRole
from app.models.vendor import Vendor

__all__ = [
    "AdvanceTaxEstimate",
    "TaxRegime",
    "AISRecord",
    "AISSourceType",
    "AuditLog",
    "Report",
    "ReportType",
    "RevokedToken",
    "TDSEvent",
    "Transaction",
    "TransactionSourceType",
    "TransactionSearchTerm",
    "User",
    "UserRole",
    "Vendor",
]
