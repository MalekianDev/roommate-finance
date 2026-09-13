"""Widen payment and split amount precision

Revision ID: a8f3c1d9e4b2
Revises: 64cbaa4b7c90
Create Date: 2026-08-22 11:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8f3c1d9e4b2"
down_revision: str | Sequence[str] | None = "64cbaa4b7c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "payments",
        "amount",
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=15, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        "splits",
        "amount",
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=15, scale=2),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "splits",
        "amount",
        existing_type=sa.Numeric(precision=15, scale=2),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        "payments",
        "amount",
        existing_type=sa.Numeric(precision=15, scale=2),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
