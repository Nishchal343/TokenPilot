"""Add AI workspace tables.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "owner_type", "owner_id", "company_id"):
        op.create_index(f"ix_chat_sessions_{column}", "chat_sessions", [column], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "session_id"):
        op.create_index(f"ix_chat_messages_{column}", "chat_messages", [column], unique=False)

    op.create_table(
        "workspace_folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["workspace_folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "owner_type", "owner_id", "company_id"):
        op.create_index(f"ix_workspace_folders_{column}", "workspace_folders", [column], unique=False)

    op.create_table(
        "workspace_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["folder_id"], ["workspace_folders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "owner_type", "owner_id", "company_id", "folder_id"):
        op.create_index(f"ix_workspace_files_{column}", "workspace_files", [column], unique=False)

    op.create_table(
        "personal_api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "owner_type", "owner_id"):
        op.create_index(f"ix_personal_api_keys_{column}", "personal_api_keys", [column], unique=False)


def downgrade() -> None:
    for column in ("id", "owner_type", "owner_id"):
        op.drop_index(f"ix_personal_api_keys_{column}", table_name="personal_api_keys")
    op.drop_table("personal_api_keys")

    for column in ("folder_id", "company_id", "owner_id", "owner_type", "id"):
        op.drop_index(f"ix_workspace_files_{column}", table_name="workspace_files")
    op.drop_table("workspace_files")

    for column in ("company_id", "owner_id", "owner_type", "id"):
        op.drop_index(f"ix_workspace_folders_{column}", table_name="workspace_folders")
    op.drop_table("workspace_folders")

    for column in ("session_id", "id"):
        op.drop_index(f"ix_chat_messages_{column}", table_name="chat_messages")
    op.drop_table("chat_messages")

    for column in ("company_id", "owner_id", "owner_type", "id"):
        op.drop_index(f"ix_chat_sessions_{column}", table_name="chat_sessions")
    op.drop_table("chat_sessions")
