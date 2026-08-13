from decimal import Decimal

from app.models import Transaction, TransactionSourceType, User, UserRole, Vendor
from app.models.common import generate_uuid
from app.security import hash_password


def test_user_password_is_hashed_not_plaintext(db_session):
    user = User(
        id=generate_uuid(),
        email="alice@example.com",
        full_name="Alice",
        hashed_password=hash_password("s3cret-Passw0rd"),
        role=UserRole.INDIVIDUAL,
    )
    db_session.add(user)
    db_session.flush()

    assert user.hashed_password != "s3cret-Passw0rd"
    assert user.hashed_password.startswith("$2b$")


def test_vendor_pan_is_encrypted_at_rest(db_session):
    user = User(
        id=generate_uuid(),
        email="bob@example.com",
        full_name="Bob",
        hashed_password=hash_password("s3cret-Passw0rd"),
    )
    db_session.add(user)
    db_session.flush()

    vendor = Vendor(user_id=user.id, name="Acme Consulting", pan="ABCDE1234F")
    db_session.add(vendor)
    db_session.flush()
    db_session.expire(vendor)  # force a re-read from the DB via the TypeDecorator

    # Reading through the ORM decrypts transparently.
    assert vendor.pan == "ABCDE1234F"

    # The raw stored bytes must NOT contain the plaintext PAN.
    raw = db_session.execute(
        __import__("sqlalchemy").text("SELECT pan FROM vendors WHERE id = :id"),
        {"id": vendor.id},
    ).scalar_one()
    assert "ABCDE1234F" not in raw


def test_transaction_requires_user_and_belongs_to_owner(db_session):
    user = User(
        id=generate_uuid(),
        email="carol@example.com",
        full_name="Carol",
        hashed_password=hash_password("s3cret-Passw0rd"),
    )
    db_session.add(user)
    db_session.flush()

    txn = Transaction(
        user_id=user.id,
        source_type=TransactionSourceType.MANUAL_ENTRY,
        transaction_date="2026-06-15",
        amount=Decimal("35000.00"),
        description="Professional consulting fee",
    )
    db_session.add(txn)
    db_session.flush()

    assert txn.user_id == user.id
    assert txn.financial_year == "2026-27"
