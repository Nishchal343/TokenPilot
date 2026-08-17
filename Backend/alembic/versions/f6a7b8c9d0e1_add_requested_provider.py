"""Store the provider selected for API-key requests."""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = ("e1f2a3b4c5d6", "c3d4e5f6a7b8")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_key_requests", sa.Column("requested_provider", sa.String(length=50), nullable=True))
    op.execute("UPDATE api_key_requests SET requested_provider = 'OpenAI' WHERE requested_provider IS NULL")
    op.alter_column("api_key_requests", "requested_provider", nullable=False)


def downgrade():
    op.drop_column("api_key_requests", "requested_provider")
