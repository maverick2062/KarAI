from app.audit.hashing import hash_dataset
from app.audit.logger import record_audit_log
from app.models.audit_log import AuditLog
from app.models.common import generate_uuid
from app.models.user import User, UserRole
from app.security import hash_password


class TestHashDataset:
    def test_same_content_produces_same_hash(self):
        assert hash_dataset("hello world") == hash_dataset("hello world")

    def test_different_content_produces_different_hash(self):
        assert hash_dataset("hello") != hash_dataset("world")

    def test_accepts_bytes_and_str_equivalently(self):
        assert hash_dataset("hello") == hash_dataset(b"hello")

    def test_returns_hex_sha256_length(self):
        assert len(hash_dataset("x")) == 64


class TestRecordAuditLog:
    def test_persists_expected_fields(self, db_session):
        user = User(
            id=generate_uuid(),
            email="audit-util@example.com",
            full_name="Audit User",
            hashed_password=hash_password("Passw0rd1"),
            role=UserRole.INDIVIDUAL,
        )
        db_session.add(user)
        db_session.flush()

        record_audit_log(
            db_session,
            user_id=user.id,
            action="report_generated",
            rule_table_version="ITA2025-S393-v1",
            dataset_hash="abc123",
            details={"report_type": "pdf"},
        )
        db_session.flush()

        entry = db_session.query(AuditLog).filter(AuditLog.user_id == user.id).one()
        assert entry.action == "report_generated"
        assert entry.dataset_hash == "abc123"
        assert '"report_type": "pdf"' in entry.details

    def test_allows_null_user_id_for_system_level_events(self, db_session):
        entry = record_audit_log(db_session, user_id=None, action="system_startup")
        assert entry.user_id is None
