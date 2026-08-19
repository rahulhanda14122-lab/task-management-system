"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_type=False: the enums are created explicitly below (once each, checkfirst=True).
    # Without this, op.create_table() would try to CREATE TYPE again for every column that
    # references the same enum (e.g. "department" is used on both users and task_rules).
    # Using the postgresql-dialect ENUM directly (rather than the generic sa.Enum) so that
    # create_type=False is reliably honored when the column is attached to a table.
    role_enum = PgEnum("admin", "manager", "user", name="role", create_type=False)
    department_enum = PgEnum("finance", "hr", "it", "operations", name="department", create_type=False)
    task_status_enum = PgEnum("todo", "in_progress", "done", name="task_status", create_type=False)
    task_priority_enum = PgEnum("low", "medium", "high", name="task_priority", create_type=False)
    assignment_status_enum = PgEnum(
        "pending", "assigned", "unassignable", name="assignment_status", create_type=False
    )

    bind = op.get_bind()
    role_enum.create(bind, checkfirst=True)
    department_enum.create(bind, checkfirst=True)
    task_status_enum.create(bind, checkfirst=True)
    task_priority_enum.create(bind, checkfirst=True)
    assignment_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", role_enum, nullable=False, server_default="user"),
        sa.Column("department", department_enum, nullable=False),
        sa.Column("experience_years", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("active_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index(
        "ix_users_dept_exp_active",
        "users",
        ["department", "experience_years", "active_task_count"],
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", task_status_enum, nullable=False, server_default="todo"),
        sa.Column("priority", task_priority_enum, nullable=False, server_default="medium"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assignment_status", assignment_status_enum, nullable=False, server_default="pending"),
        sa.Column("rules_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_assigned_to_status", "tasks", ["assigned_to", "status"])
    op.create_index(
        "ix_tasks_assignment_status_pending",
        "tasks",
        ["assignment_status"],
        postgresql_where=sa.text("assignment_status = 'pending'"),
    )
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])
    op.create_index("ix_tasks_priority", "tasks", ["priority"])
    op.create_index("ix_tasks_created_by", "tasks", ["created_by"])

    op.create_table(
        "task_rules",
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("department", department_enum, nullable=True),
        sa.Column("min_experience_years", sa.SmallInteger(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("max_active_tasks", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_task_rules_department_experience",
        "task_rules",
        ["department", "min_experience_years"],
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_index("ix_task_rules_department_experience", table_name="task_rules")
    op.drop_table("task_rules")
    op.drop_index("ix_tasks_created_by", table_name="tasks")
    op.drop_index("ix_tasks_priority", table_name="tasks")
    op.drop_index("ix_tasks_due_date", table_name="tasks")
    op.drop_index("ix_tasks_assignment_status_pending", table_name="tasks")
    op.drop_index("ix_tasks_assigned_to_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_users_dept_exp_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    sa.Enum(name="assignment_status").drop(bind, checkfirst=True)
    sa.Enum(name="task_priority").drop(bind, checkfirst=True)
    sa.Enum(name="task_status").drop(bind, checkfirst=True)
    sa.Enum(name="department").drop(bind, checkfirst=True)
    sa.Enum(name="role").drop(bind, checkfirst=True)
