"""add contextual TDS decisions

Revision ID: 42e91a6d8c20
Revises: 8b2f30a4c61d
Create Date: 2026-10-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "42e91a6d8c20"
down_revision: Union[str, None] = "8b2f30a4c61d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


decision_status = sa.Enum(
    "APPLICABLE",
    "NOT_APPLICABLE",
    "NEEDS_REVIEW",
    name="tdsdecisionstatus",
)


def upgrade() -> None:
    decision_status.create(op.get_bind(), checkfirst=True)
    op.add_column("transactions", sa.Column("rule_context", sa.JSON(), nullable=True))
    op.add_column("tds_events", sa.Column("decision_status", decision_status, nullable=True))
    op.add_column("tds_events", sa.Column("review_reason", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE tds_events
        SET decision_status = CASE
            WHEN tds_applicable THEN CAST('APPLICABLE' AS tdsdecisionstatus)
            ELSE CAST('NOT_APPLICABLE' AS tdsdecisionstatus)
        END
        """
    )
    op.alter_column("tds_events", "decision_status", nullable=False)
    op.alter_column("tds_events", "taxable_amount", nullable=True)
    op.alter_column("tds_events", "tds_amount", nullable=True)
    op.alter_column("tds_events", "rate_percent", nullable=True)


def downgrade() -> None:
    op.execute(
        """
        UPDATE tds_events
        SET taxable_amount = COALESCE(taxable_amount, 0),
            tds_amount = COALESCE(tds_amount, 0),
            rate_percent = COALESCE(rate_percent, 0)
        """
    )
    op.alter_column("tds_events", "taxable_amount", nullable=False)
    op.alter_column("tds_events", "tds_amount", nullable=False)
    op.alter_column("tds_events", "rate_percent", nullable=False)
    op.drop_column("tds_events", "review_reason")
    op.drop_column("tds_events", "decision_status")
    decision_status.drop(op.get_bind(), checkfirst=True)
    op.drop_column("transactions", "rule_context")
