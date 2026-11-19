"""add private transaction search index

Revision ID: a31d02c6e947
Revises: 7c9e2f4a1b6d
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.security import decrypt_field
from app.transaction_search import searchable_tokens, search_term_hash


revision: str = "a31d02c6e947"
down_revision: Union[str, None] = "7c9e2f4a1b6d"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "transaction_search_terms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=36), nullable=False),
        sa.Column("term_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", "term_hash", name="uq_transaction_search_term"),
    )
    op.create_index(
        "ix_transaction_search_user_term",
        "transaction_search_terms",
        ["user_id", "term_hash"],
    )
    op.create_index(
        "ix_transaction_search_transaction",
        "transaction_search_terms",
        ["transaction_id"],
    )
    op.create_index(
        "ix_transactions_user_amount",
        "transactions",
        ["user_id", "amount"],
    )
    op.create_index(
        "ix_transactions_user_date_id",
        "transactions",
        ["user_id", "transaction_date", "id"],
    )

    bind = op.get_bind()
    transactions = sa.table(
        "transactions",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("vendor_id", sa.String()),
        sa.column("description", sa.String()),
    )
    vendors = sa.table(
        "vendors",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
    )
    rows = bind.execute(
        sa.select(transactions.c.id, transactions.c.user_id, transactions.c.description, vendors.c.name)
        .select_from(transactions.outerjoin(vendors, transactions.c.vendor_id == vendors.c.id))
    )
    search_terms = sa.table(
        "transaction_search_terms",
        sa.column("user_id", sa.String()),
        sa.column("transaction_id", sa.String()),
        sa.column("term_hash", sa.String()),
    )
    for row in rows:
        description = decrypt_field(row.description)
        terms = {
            search_term_hash(row.user_id, token)
            for value in (description, row.name)
            for token in searchable_tokens(value)
        }
        if terms:
            bind.execute(
                search_terms.insert(),
                [
                    {"user_id": row.user_id, "transaction_id": row.id, "term_hash": term_hash}
                    for term_hash in terms
                ],
            )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_date_id", table_name="transactions")
    op.drop_index("ix_transactions_user_amount", table_name="transactions")
    op.drop_index("ix_transaction_search_transaction", table_name="transaction_search_terms")
    op.drop_index("ix_transaction_search_user_term", table_name="transaction_search_terms")
    op.drop_table("transaction_search_terms")
