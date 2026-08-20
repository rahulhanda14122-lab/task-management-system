from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssignmentStatus, Department, TaskPriority, TaskStatus


class TaskRuleIn(BaseModel):
    department: Department | None = None
    min_experience_years: int | None = Field(default=None, ge=0, le=60)
    location: str | None = None
    max_active_tasks: int | None = Field(default=None, ge=0)


class TaskRuleOut(TaskRuleIn):
    model_config = ConfigDict(from_attributes=True)


class TaskCreateRequest(BaseModel):
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    rules: TaskRuleIn


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    rules: TaskRuleIn | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    created_by: int
    assigned_to: int | None
    assigned_to_name: str | None = None
    assignment_status: AssignmentStatus
    rules_version: int
    created_at: datetime
    updated_at: datetime
    rule: TaskRuleOut | None = None


def serialize_task(task) -> TaskOut:
    """Map ORM Task → TaskOut, including assignee display name when loaded."""
    out = TaskOut.model_validate(task)
    assignee = getattr(task, "assignee", None)
    if assignee is not None:
        out = out.model_copy(update={"assigned_to_name": assignee.full_name})
    return out


class EligibleUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    department: Department
    experience_years: int
    location: str
    active_task_count: int
    last_assigned_at: datetime | None = None
    is_current_assignee: bool = False


class PendingTaskOut(TaskOut):
    """Pending task plus whether the current viewer may claim it."""

    can_claim: bool = False


class RecomputeRequest(BaseModel):
    task_id: int | None = None
    user_id: int | None = None


class PaginatedTasks(BaseModel):
    items: list[TaskOut]
    next_cursor: int | None = None


class PaginatedPendingTasks(BaseModel):
    items: list[PendingTaskOut]
    next_cursor: int | None = None
