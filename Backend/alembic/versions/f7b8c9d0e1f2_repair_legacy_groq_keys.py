"""Repair connections created by the old provider/model mismatch flow."""

from alembic import op


revision = "f7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE api_keys SET provider = 'Groq', model = 'llama-3.3-70b-versatile' "
        "WHERE lower(provider) = 'openai' AND lower(model) = 'groq'"
    )


def downgrade():
    op.execute(
        "UPDATE api_keys SET provider = 'OpenAI', model = 'groq' "
        "WHERE lower(provider) = 'groq' AND lower(model) = 'llama-3.3-70b-versatile'"
    )
