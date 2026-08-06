"""Store provider telemetry on assistant chat messages."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("provider", sa.String(length=50), nullable=True))
    op.add_column("chat_messages", sa.Column("model", sa.String(length=120), nullable=True))
    op.add_column("chat_messages", sa.Column("api_key_id", sa.Integer(), nullable=True))
    op.add_column("chat_messages", sa.Column("api_key_source", sa.String(length=20), nullable=True))
    op.add_column("chat_messages", sa.Column("token_usage", sa.Integer(), nullable=True))
    op.add_column("chat_messages", sa.Column("estimated_cost", sa.String(length=32), nullable=True))
    op.add_column("chat_messages", sa.Column("latency_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    for name in ("latency_ms", "estimated_cost", "token_usage", "api_key_source", "api_key_id", "model", "provider"):
        op.drop_column("chat_messages", name)
