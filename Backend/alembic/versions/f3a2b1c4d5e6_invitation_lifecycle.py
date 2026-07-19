"""Add invitation lifecycle columns and enum values

Revision ID: f3a2b1c4d5e6
Revises: 4e7710e71050
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a2b1c4d5e6"
down_revision: Union[str, None] = "4e7710e71050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values to invitationstatus
    op.execute("ALTER TYPE invitationstatus ADD VALUE IF NOT EXISTS 'expired'")
    op.execute("ALTER TYPE invitationstatus ADD VALUE IF NOT EXISTS 'cancelled'")

    # Add new columns to invitations table
    op.add_column("invitations", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("invitations", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invitations", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invitations", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("invitations", "cancelled_at")
    op.drop_column("invitations", "rejected_at")
    op.drop_column("invitations", "accepted_at")
    op.drop_column("invitations", "name")
    # Note: PostgreSQL does not support removing enum values in a simple ALTER TYPE
