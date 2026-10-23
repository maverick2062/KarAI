"""store PAN-furnished status on TDS events

Revision ID: 8b2f30a4c61d
Revises: baec03eb8abc
Create Date: 2026-10-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b2f30a4c61d"
down_revision: Union[str, None] = "baec03eb8abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tds_events",
        sa.Column("pan_not_provided", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tds_events", "pan_not_provided")
