"""add transaction workflow state

Revision ID: 7c9e2f4a1b6d
Revises: 42e91a6d8c20
Create Date: 2026-11-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c9e2f4a1b6d"
down_revision: Union[str, None] = "42e91a6d8c20"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "transactions",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("transactions", "is_deleted")
    op.drop_column("transactions", "is_completed")
