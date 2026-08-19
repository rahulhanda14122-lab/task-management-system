from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, SmallInteger, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Department, Role, pg_enum


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[Role] = mapped_column(pg_enum(Role, "role"), nullable=False, default=Role.USER)
    department: Mapped[Department] = mapped_column(pg_enum(Department, "department"), nullable=False)
    experience_years: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    location: Mapped[str] = mapped_column(String(255), nullable=False)

    # Denormalized counter, updated atomically alongside assignment/completion so the
    # rule engine can filter/sort on it without a COUNT(*) join at request time.
    active_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Tie-break among equally loaded candidates: pick whoever was assigned least recently.
    # NULL means never assigned and sorts first (highest priority for the next assignment).
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to")

    __table_args__ = (
        # Core rule-engine index: filter by department/experience, sort by load, in one scan.
        Index(
            "ix_users_dept_exp_active_lra",
            "department",
            "experience_years",
            "active_task_count",
            "last_assigned_at",
            postgresql_where=text("is_active = true"),
        ),
    )
