"""Add metadata and selection state for personal API keys."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("personal_api_keys", sa.Column("label", sa.String(length=100), nullable=True))
    op.add_column("personal_api_keys", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("personal_api_keys", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("personal_api_keys", "last_used_at")
    op.drop_column("personal_api_keys", "is_default")
    op.drop_column("personal_api_keys", "label")
