"""Add canonical RBAC ownership fields to invitations.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("invited_by_user_id", sa.Integer(), nullable=True))
    op.add_column("invitations", sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_index("ix_invitations_invited_by_user_id", "invitations", ["invited_by_user_id"], unique=False)
    op.create_index("ix_invitations_company_id", "invitations", ["company_id"], unique=False)
    op.create_foreign_key(
        "fk_invitations_invited_by_user_id",
        "invitations",
        "employees",
        ["invited_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_invitations_company_id",
        "invitations",
        "companies",
        ["company_id"],
        ["id"],
    )

    # Backfill existing invitations before the application starts requiring
    # explicit company and manager ownership.
    op.execute(sa.text("""
        UPDATE invitations
        SET company_id = invited_by_id
        WHERE invited_by_type = 'company'
    """))
    op.execute(sa.text("""
        UPDATE invitations AS i
        SET invited_by_user_id = e.id,
            company_id = e.company_id
        FROM employees AS e
        WHERE i.invited_by_type = 'employee'
          AND e.id = i.invited_by_id
    """))


def downgrade() -> None:
    op.drop_constraint("fk_invitations_company_id", "invitations", type_="foreignkey")
    op.drop_constraint("fk_invitations_invited_by_user_id", "invitations", type_="foreignkey")
    op.drop_index("ix_invitations_company_id", table_name="invitations")
    op.drop_index("ix_invitations_invited_by_user_id", table_name="invitations")
    op.drop_column("invitations", "company_id")
    op.drop_column("invitations", "invited_by_user_id")
