from sqlalchemy import ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Department, pg_enum


class TaskRule(Base):
    """1:1 eligibility rule set for a task. NULL on a column means 'unconstrained'.

    Kept as structured, nullable columns (not JSONB/EAV) because the assignable attribute
    set is fixed by the product spec, which is what allows composite indexing below.
    """

    __tablename__ = "task_rules"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)

    department: Mapped[Department | None] = mapped_column(pg_enum(Department, "department"), nullable=True)
    min_experience_years: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_active_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task = relationship("Task", back_populates="rule")

    __table_args__ = (
        # Combined with the tasks.assignment_status partial index (fast PK join on the
        # small "pending" subset), this supports the reverse "which pending tasks might a
        # just-changed user now match" lookup without ever scanning the full 1M tasks table.
        Index("ix_task_rules_department_experience", "department", "min_experience_years"),
    )
