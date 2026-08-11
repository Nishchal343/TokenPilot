"""Add V1 optimization settings, reports, and cache entries."""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_messages", sa.Column("optimization_report", sa.JSON(), nullable=True))
    op.create_table("optimization_settings",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("owner_type", sa.String(20), nullable=False), sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("prompt_enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("document_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("code_enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("context_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smart_cache_enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("similarity_threshold", sa.String(16), nullable=False, server_default="0.9"),
        sa.Column("optimization_level", sa.String(20), nullable=False, server_default="balanced"))
    op.create_index("ix_optimization_settings_owner", "optimization_settings", ["owner_type", "owner_id"])
    op.create_table("optimization_requests",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("owner_type", sa.String(20), nullable=False), sa.Column("owner_id", sa.Integer(), nullable=False), sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(20), nullable=False), sa.Column("provider", sa.String(50)), sa.Column("model", sa.String(120)), sa.Column("original_prompt", sa.Text(), nullable=False), sa.Column("optimized_prompt", sa.Text(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False), sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("api_call_avoided", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_optimization_requests_owner", "optimization_requests", ["owner_type", "owner_id"])
    op.create_table("optimization_cache_entries",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("owner_type", sa.String(20), nullable=False), sa.Column("owner_id", sa.Integer(), nullable=False), sa.Column("module", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False), sa.Column("model", sa.String(120), nullable=False), sa.Column("original_prompt", sa.Text(), nullable=False), sa.Column("optimized_prompt", sa.Text(), nullable=False), sa.Column("response", sa.Text(), nullable=False), sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("estimated_cost", sa.String(32), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_optimization_cache_owner", "optimization_cache_entries", ["owner_type", "owner_id"])


def downgrade():
    op.drop_column("chat_messages", "optimization_report"); op.drop_table("optimization_cache_entries"); op.drop_table("optimization_requests"); op.drop_table("optimization_settings")
