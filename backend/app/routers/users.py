from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.audit.logger import record_audit_log
from app.db import get_db
from app.models.user import User
from app.routers.deps import get_current_user

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account_and_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DPDP Act 2023 consent-revocation / right-to-erasure: permanently
    deletes the user and every row that references them (vendors,
    transactions, TDS events, advance-tax estimates, AIS records, reports)
    via ON DELETE CASCADE foreign keys. Logged as a user_id=None system-level
    audit entry, since the user row itself won't exist to reference afterward.
    """
    record_audit_log(
        db,
        user_id=None,
        action="account_deleted",
        details={"deleted_user_id": current_user.id, "deleted_user_email": current_user.email},
    )
    db.delete(current_user)
    db.commit()
