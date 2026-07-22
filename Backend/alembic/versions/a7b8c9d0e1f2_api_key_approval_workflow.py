"""Add AI API key approval workflow tables.

Revision ID: a7b8c9d0e1f2
Revises: f4b5c6d7e8f9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("budget_limit", sa.Integer(), nullable=False),
        sa.Column("remaining_budget", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"], unique=False)
    op.create_index("ix_api_keys_company_id", "api_keys", ["company_id"], unique=False)
    op.create_index("ix_api_keys_employee_id", "api_keys", ["employee_id"], unique=False)
    op.create_index("ix_api_keys_request_id", "api_keys", ["request_id"], unique=False)

    op.create_table(
        "api_key_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("team_leader_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("requested_tier", sa.String(length=20), nullable=False),
        sa.Column("requested_model", sa.String(length=120), nullable=False),
        sa.Column("requested_budget", sa.Integer(), nullable=False),
        sa.Column("leader_modified_budget", sa.Integer(), nullable=True),
        sa.Column("company_final_budget", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("api_key_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["team_leader_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "company_id", "team_leader_id", "employee_id", "status"):
        op.create_index(f"ix_api_key_requests_{column}", "api_key_requests", [column], unique=False)

    op.create_table(
        "api_key_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("old_budget", sa.Integer(), nullable=True),
        sa.Column("new_budget", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["request_id"], ["api_key_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_audit_logs_id", "api_key_audit_logs", ["id"], unique=False)
    op.create_index("ix_api_key_audit_logs_request_id", "api_key_audit_logs", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_key_audit_logs_request_id", table_name="api_key_audit_logs")
    op.drop_index("ix_api_key_audit_logs_id", table_name="api_key_audit_logs")
    op.drop_table("api_key_audit_logs")
    for column in ("status", "employee_id", "team_leader_id", "company_id", "id"):
        op.drop_index(f"ix_api_key_requests_{column}", table_name="api_key_requests")
    op.drop_table("api_key_requests")
    for column in ("request_id", "employee_id", "company_id", "id"):
        op.drop_index(f"ix_api_keys_{column}", table_name="api_keys")
    op.drop_table("api_keys")
