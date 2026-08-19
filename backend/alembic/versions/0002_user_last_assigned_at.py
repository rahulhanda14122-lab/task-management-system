"""add users.last_assigned_at for least-recently-assigned tie-break

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_index("ix_users_dept_exp_active", table_name="users")
    op.create_index(
        "ix_users_dept_exp_active_lra",
        "users",
        ["department", "experience_years", "active_task_count", "last_assigned_at"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_dept_exp_active_lra", table_name="users")
    op.create_index(
        "ix_users_dept_exp_active",
        "users",
        ["department", "experience_years", "active_task_count"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.drop_column("users", "last_assigned_at")
