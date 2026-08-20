from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_admin, require_admin_or_manager
from app.db.session import get_db
from app.models.task import Task
from app.models.user import User
from app.schemas.task import PaginatedTasks, serialize_task
from app.schemas.user import PaginatedUsers, ProfileUpdateRequest, UserOut, UserUpdateRequest
from app.workers.celery_tasks import recompute_for_user_change

router = APIRouter(prefix="/users", tags=["users"])

# Attributes that, if changed, can affect task eligibility and must trigger a recompute.
ELIGIBILITY_FIELDS = {"department", "experience_years", "location", "is_active"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Self-service profile edit. Eligibility field changes enqueue recompute_for_user_change."""
    user = await db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    eligibility_changed = any(field in ELIGIBILITY_FIELDS for field in update_data)

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    if eligibility_changed:
        recompute_for_user_change.delay(user.id)

    return user


@router.get("/", response_model=PaginatedUsers)
async def list_users(
    cursor: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> PaginatedUsers:
    stmt = select(User).order_by(User.id.asc())
    if cursor:
        stmt = stmt.where(User.id > cursor)
    stmt = stmt.limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    return PaginatedUsers(items=[UserOut.model_validate(u) for u in rows], next_cursor=next_cursor)


@router.get("/{user_id}/tasks", response_model=PaginatedTasks)
async def get_user_tasks(
    user_id: int,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasks:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    stmt = (
        select(Task)
        .options(selectinload(Task.rule), selectinload(Task.assignee))
        .where(Task.assigned_to == user_id)
        .order_by(Task.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return PaginatedTasks(items=[serialize_task(r) for r in rows], next_cursor=None)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Story 3: updating a user's profile can change which tasks they're eligible for. Any
    change to an eligibility-relevant field enqueues a bounded recompute after commit."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    eligibility_changed = any(field in update_data and field in ELIGIBILITY_FIELDS for field in update_data)

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    if eligibility_changed:
        recompute_for_user_change.delay(user.id)

    return user
