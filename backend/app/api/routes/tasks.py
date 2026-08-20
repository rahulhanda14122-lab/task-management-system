from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_admin_or_manager
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import AssignmentStatus, Role, TaskStatus
from app.models.task import Task
from app.models.task_rule import TaskRule
from app.models.user import User
from app.schemas.task import (
    EligibleUserOut,
    PaginatedPendingTasks,
    PaginatedTasks,
    PendingTaskOut,
    RecomputeRequest,
    TaskCreateRequest,
    TaskOut,
    TaskUpdateRequest,
    serialize_task,
)
from app.services.cache_service import (
    bump_my_tasks_version,
    get_cached_json,
    get_eligible_preview_cache,
    get_my_tasks_version,
    my_tasks_cache_key,
    set_cached_json,
    set_eligible_preview_cache,
)
from app.services.rule_engine import is_user_eligible_for_rule, preview_eligible_users
from app.workers.celery_tasks import (
    evaluate_task_assignment,
    recompute_for_task_rule_change,
    recompute_for_user_change,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_task_or_404(db: AsyncSession, task_id: int) -> Task:
    stmt = (
        select(Task)
        .options(selectinload(Task.rule), selectinload(Task.assignee))
        .where(Task.id == task_id)
    )
    task = (await db.execute(stmt)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _pending_matches_profile(user: User, rule: TaskRule | None) -> bool:
    """Soft match for listing (ignores max_active_tasks — claim checks that authoritatively)."""
    if rule is None:
        return True
    if rule.department is not None and user.department != rule.department:
        return False
    if rule.min_experience_years is not None and user.experience_years < rule.min_experience_years:
        return False
    if rule.location is not None and user.location != rule.location:
        return False
    return True


@router.post("/", response_model=TaskOut, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    payload: TaskCreateRequest,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    """Creates the task + its rule set, then hands off assignment to the background worker."""
    task = Task(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        created_by=current_user.id,
        assignment_status=AssignmentStatus.PENDING,
    )
    task.rule = TaskRule(
        department=payload.rules.department,
        min_experience_years=payload.rules.min_experience_years,
        location=payload.rules.location,
        max_active_tasks=payload.rules.max_active_tasks,
    )
    db.add(task)
    await db.commit()
    task = await _get_task_or_404(db, task.id)

    evaluate_task_assignment.delay(task.id)
    return serialize_task(task)


@router.get("/", response_model=PaginatedTasks)
async def list_tasks(
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasks:
    stmt = select(Task).options(selectinload(Task.rule), selectinload(Task.assignee))
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    if cursor:
        stmt = stmt.where(Task.id > cursor)
    stmt = stmt.order_by(Task.id.asc()).limit(limit + 1)

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    return PaginatedTasks(items=[serialize_task(r) for r in rows], next_cursor=next_cursor)


@router.get("/my-eligible-tasks", response_model=PaginatedTasks)
async def get_my_eligible_tasks(
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasks:
    """Assigned tasks for the current user — cache-aside + index-backed."""
    version = await get_my_tasks_version(current_user.id)
    cache_key = my_tasks_cache_key(current_user.id, version, cursor)

    cached = await get_cached_json(cache_key)
    if cached is not None:
        return PaginatedTasks.model_validate(cached)

    stmt = (
        select(Task)
        .options(selectinload(Task.rule), selectinload(Task.assignee))
        .where(Task.assigned_to == current_user.id)
    )
    if cursor:
        stmt = stmt.where(Task.id > cursor)
    stmt = stmt.order_by(Task.id.asc()).limit(limit + 1)

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    payload = PaginatedTasks(items=[serialize_task(r) for r in rows], next_cursor=next_cursor)

    await set_cached_json(cache_key, payload.model_dump(mode="json"), settings.MY_TASKS_CACHE_TTL_SECONDS)
    return payload


@router.get("/pending", response_model=PaginatedPendingTasks)
async def list_pending_tasks(
    cursor: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedPendingTasks:
    """List unassigned (pending) tasks.

    - Admin/Manager: all pending tasks.
    - User: only pending tasks whose department/experience/location rules match their profile.
    `can_claim` is true when the viewer fully matches rules (including max_active_tasks).
    """
    is_privileged = current_user.role in (Role.ADMIN, Role.MANAGER)

    stmt = (
        select(Task)
        .join(TaskRule, TaskRule.task_id == Task.id)
        .options(selectinload(Task.rule), selectinload(Task.assignee))
        .where(Task.assignment_status == AssignmentStatus.PENDING)
    )
    if not is_privileged:
        stmt = (
            stmt.where((TaskRule.department.is_(None)) | (TaskRule.department == current_user.department))
            .where(
                (TaskRule.min_experience_years.is_(None))
                | (TaskRule.min_experience_years <= current_user.experience_years)
            )
            .where((TaskRule.location.is_(None)) | (TaskRule.location == current_user.location))
        )
    if cursor:
        stmt = stmt.where(Task.id > cursor)
    stmt = stmt.order_by(Task.id.asc()).limit(limit + 1)

    rows = list((await db.execute(stmt)).scalars().unique().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None

    items: list[PendingTaskOut] = []
    for task in rows:
        rule = task.rule or TaskRule(task_id=task.id)
        can_claim = is_user_eligible_for_rule(current_user, rule)
        base = serialize_task(task)
        items.append(PendingTaskOut(**base.model_dump(), can_claim=can_claim))

    return PaginatedPendingTasks(items=items, next_cursor=next_cursor)


@router.post("/{task_id}/claim", response_model=TaskOut)
async def claim_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    """Self-assign a pending task if the current user matches its eligibility rules."""
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.rule), selectinload(Task.assignee))
        .where(Task.id == task_id)
        .with_for_update()
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.assignment_status != AssignmentStatus.PENDING or task.assigned_to is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not available to claim")

    user = await db.get(User, current_user.id, with_for_update=True)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    rule = task.rule or TaskRule(task_id=task.id)
    if not is_user_eligible_for_rule(user, rule):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not eligible to claim this task under its current rules",
        )

    user.active_task_count += 1
    user.last_assigned_at = datetime.now(timezone.utc)
    task.assigned_to = user.id
    task.assignment_status = AssignmentStatus.ASSIGNED
    await db.commit()

    task = await _get_task_or_404(db, task.id)
    await bump_my_tasks_version(user.id)
    return serialize_task(task)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    task = await _get_task_or_404(db, task_id)
    if current_user.role in (Role.ADMIN, Role.MANAGER):
        return serialize_task(task)
    if task.assigned_to == current_user.id:
        return serialize_task(task)
    # Users may view pending tasks they profile-match (for claim / detail).
    if task.assignment_status == AssignmentStatus.PENDING and _pending_matches_profile(
        current_user, task.rule
    ):
        return serialize_task(task)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your task")


@router.get("/{task_id}/eligible-users", response_model=list[EligibleUserOut])
async def get_eligible_users(
    task_id: int,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> list[EligibleUserOut]:
    """Admin/manager preview of current rule-matching candidates. Marks the current assignee."""
    task = await _get_task_or_404(db, task_id)

    users = await preview_eligible_users(db, task, settings.ELIGIBLE_USERS_PREVIEW_LIMIT)
    result = []
    for u in users:
        row = EligibleUserOut.model_validate(u).model_dump(mode="json")
        row["is_current_assignee"] = task.assigned_to is not None and u.id == task.assigned_to
        result.append(row)
    # Always include the current assignee even if they fall outside the preview LIMIT window
    # or no longer match rules (locked in_progress).
    if task.assigned_to is not None and not any(r["id"] == task.assigned_to for r in result):
        assignee = await db.get(User, task.assigned_to)
        if assignee is not None:
            row = EligibleUserOut.model_validate(assignee).model_dump(mode="json")
            row["is_current_assignee"] = True
            result.insert(0, row)
    return result


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    """Admin/Manager can edit any field (including rules). A plain User may only update
    the status of a task assigned to them (todo ↔ in_progress → done)."""
    task = await _get_task_or_404(db, task_id)
    is_privileged = current_user.role in (Role.ADMIN, Role.MANAGER)

    if not is_privileged:
        if task.assigned_to != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your task")
        if any(
            getattr(payload, field) is not None
            for field in ("title", "description", "priority", "due_date", "rules")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin/Manager can edit task details or rules; you may only update status",
            )

    editing_details = any(
        getattr(payload, field) is not None
        for field in ("title", "description", "priority", "due_date", "rules")
    )
    if task.status == TaskStatus.DONE and (editing_details or payload.status is not None):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed tasks cannot be edited",
        )

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.due_date is not None:
        task.due_date = payload.due_date

    status_changed = False
    status_changed_to_done = False
    previous_assignee = task.assigned_to
    if payload.status is not None and payload.status != task.status:
        status_changed = True
        if payload.status == TaskStatus.DONE and task.assigned_to is not None:
            status_changed_to_done = True
        task.status = payload.status

    rules_changed = False
    if payload.rules is not None:
        rule = task.rule or TaskRule(task_id=task.id)
        rule.department = payload.rules.department
        rule.min_experience_years = payload.rules.min_experience_years
        rule.location = payload.rules.location
        rule.max_active_tasks = payload.rules.max_active_tasks
        task.rule = rule
        task.rules_version += 1
        rules_changed = True

    privileged_resubmit = is_privileged and (
        rules_changed
        or payload.title is not None
        or payload.description is not None
        or payload.priority is not None
        or payload.due_date is not None
    )

    freed_user_id = None
    if status_changed_to_done:
        assignee = await db.get(User, task.assigned_to)
        if assignee is not None:
            assignee.active_task_count = max(0, assignee.active_task_count - 1)
            freed_user_id = assignee.id

    await db.commit()
    task = await _get_task_or_404(db, task.id)

    # Bust my-tasks cache on any status change so My Tasks UI refreshes immediately.
    if status_changed and previous_assignee is not None:
        await bump_my_tasks_version(previous_assignee)
    elif freed_user_id is not None:
        await bump_my_tasks_version(freed_user_id)

    if privileged_resubmit or rules_changed:
        recompute_for_task_rule_change.delay(task.id)

    return serialize_task(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> None:
    task = await _get_task_or_404(db, task_id)
    freed_user_id = task.assigned_to
    await db.delete(task)
    await db.commit()
    if freed_user_id is not None:
        await bump_my_tasks_version(freed_user_id)


@router.post("/recompute-eligibility", status_code=status.HTTP_202_ACCEPTED)
async def recompute_eligibility(
    payload: RecomputeRequest,
    current_user: User = Depends(require_admin_or_manager),
) -> dict:
    """Manual/admin-triggered recompute — same Celery paths as automatic triggers."""
    if payload.task_id is None and payload.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task_id or user_id is required")

    queued = []
    if payload.task_id is not None:
        recompute_for_task_rule_change.delay(payload.task_id)
        queued.append(f"task:{payload.task_id}")
    if payload.user_id is not None:
        recompute_for_user_change.delay(payload.user_id)
        queued.append(f"user:{payload.user_id}")

    return {"status": "queued", "jobs": queued}
