from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AssignmentStatus, TaskPriority, TaskStatus, pg_enum


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        pg_enum(TaskStatus, "task_status"), nullable=False, default=TaskStatus.TODO
    )
    priority: Mapped[TaskPriority] = mapped_column(
        pg_enum(TaskPriority, "task_priority"), nullable=False, default=TaskPriority.MEDIUM
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    assignment_status: Mapped[AssignmentStatus] = mapped_column(
        pg_enum(AssignmentStatus, "assignment_status"),
        nullable=False,
        default=AssignmentStatus.PENDING,
    )
    # Bumped every time this task's rules are edited; used as a cache-busting key for the
    # "eligible users" preview endpoint (see docs/caching strategy).
    rules_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    rule = relationship("TaskRule", back_populates="task", uselist=False, cascade="all, delete-orphan")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to])

    __table_args__ = (
        # Powers GET /my-eligible-tasks: "this user's assigned tasks" without a table scan.
        Index("ix_tasks_assigned_to_status", "assigned_to", "status"),
        # Powers the periodic sweep job: only scans the (small) pending subset.
        Index(
            "ix_tasks_assignment_status_pending",
            "assignment_status",
            postgresql_where=text("assignment_status = 'pending'"),
        ),
        Index("ix_tasks_due_date", "due_date"),
        Index("ix_tasks_priority", "priority"),
        Index("ix_tasks_created_by", "created_by"),
    )
