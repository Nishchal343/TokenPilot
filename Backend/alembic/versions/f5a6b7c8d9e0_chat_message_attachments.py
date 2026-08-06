"""Store image attachments with chat messages."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("attachments", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "attachments")
