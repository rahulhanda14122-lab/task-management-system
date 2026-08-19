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
    assignment_status: AssignmentStatus
    rules_version: int
    created_at: datetime
    updated_at: datetime
    rule: TaskRuleOut | None = None


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


class RecomputeRequest(BaseModel):
    task_id: int | None = None
    user_id: int | None = None


class PaginatedTasks(BaseModel):
    items: list[TaskOut]
    next_cursor: int | None = None
