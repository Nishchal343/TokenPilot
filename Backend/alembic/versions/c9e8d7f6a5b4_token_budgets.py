"""Add token budgets and AI usage counters.

Revision ID: c9e8d7f6a5b4
Revises: b7f2c9a1d4e6
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c9e8d7f6a5b4"
down_revision: Union[str, Sequence[str], None] = "b7f2c9a1d4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "token_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("monthly_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remaining_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpt_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gemini_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claude_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("other_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employee_id", name="uq_token_budget_company_employee"),
    )
    op.create_index("ix_token_budgets_id", "token_budgets", ["id"], unique=False)
    op.create_index("ix_token_budgets_company_id", "token_budgets", ["company_id"], unique=False)
    op.create_index("ix_token_budgets_employee_id", "token_budgets", ["employee_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_token_budgets_employee_id", table_name="token_budgets")
    op.drop_index("ix_token_budgets_company_id", table_name="token_budgets")
    op.drop_index("ix_token_budgets_id", table_name="token_budgets")
    op.drop_table("token_budgets")
