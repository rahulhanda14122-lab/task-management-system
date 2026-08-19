from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Department, Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    department: Department
    experience_years: int
    location: str
    active_task_count: int
    is_active: bool
    created_at: datetime


class UserUpdateRequest(BaseModel):
    """Fields an admin (or the user, for a subset) can change. Any change here can affect
    task eligibility, so the update endpoint triggers a recompute after commit."""

    full_name: str | None = None
    department: Department | None = None
    experience_years: int | None = Field(default=None, ge=0, le=60)
    location: str | None = None
    is_active: bool | None = None
