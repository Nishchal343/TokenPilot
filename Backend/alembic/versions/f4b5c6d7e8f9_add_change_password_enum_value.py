"""add change_password to the OTP purpose enum

Revision ID: f4b5c6d7e8f9
Revises: f3a2b1c4d5e6
"""

from alembic import op


revision = "f4b5c6d7e8f9"
down_revision = "f3a2b1c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE otppurpose ADD VALUE IF NOT EXISTS 'change_password'")


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value in place.
    pass
