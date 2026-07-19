"""Add employee hierarchy and notifications.

Revision ID: b7f2c9a1d4e6
Revises: 08cea5baf40f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f2c9a1d4e6"
down_revision: Union[str, Sequence[str], None] = "08cea5baf40f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("manager_id", sa.Integer(), nullable=True))
    op.create_index("ix_employees_manager_id", "employees", ["manager_id"], unique=False)
    op.create_foreign_key("fk_employees_manager_id", "employees", "employees", ["manager_id"], ["id"])

    op.add_column("invitations", sa.Column("manager_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_invitations_manager_id", "invitations", "employees", ["manager_id"], ["id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_employee_id", "notifications", ["employee_id"], unique=False)
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=False)
    op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_id", table_name="notifications")
    op.drop_index("ix_notifications_employee_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_constraint("fk_invitations_manager_id", "invitations", type_="foreignkey")
    op.drop_column("invitations", "manager_id")
    op.drop_constraint("fk_employees_manager_id", "employees", type_="foreignkey")
    op.drop_index("ix_employees_manager_id", table_name="employees")
    op.drop_column("employees", "manager_id")
