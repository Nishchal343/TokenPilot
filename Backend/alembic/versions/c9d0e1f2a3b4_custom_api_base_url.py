"""Allow personal keys to target custom OpenAI-compatible APIs.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("personal_api_keys", sa.Column("api_base_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("personal_api_keys", "api_base_url")
