import json

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit_log(
    db: Session,
    user_id: str | None,
    action: str,
    rule_table_version: str | None = None,
    dataset_hash: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        rule_table_version=rule_table_version,
        dataset_hash=dataset_hash,
        details=json.dumps(details) if details is not None else None,
    )
    db.add(entry)
    db.flush()
    return entry
