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
    PaginatedTasks,
    RecomputeRequest,
    TaskCreateRequest,
    TaskOut,
    TaskUpdateRequest,
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
from app.services.rule_engine import preview_eligible_users
from app.workers.celery_tasks import (
    evaluate_task_assignment,
    recompute_for_task_rule_change,
    recompute_for_user_change,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_task_or_404(db: AsyncSession, task_id: int) -> Task:
    stmt = select(Task).options(selectinload(Task.rule)).where(Task.id == task_id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("/", response_model=TaskOut, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    payload: TaskCreateRequest,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Creates the task + its rule set, then hands off assignment to the background worker.
    Returns immediately with assignment_status=PENDING -- the caller should poll the task or
    rely on GET /my-eligible-tasks / GET /tasks/{id}/eligible-users once it settles.
    """
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
    return task


@router.get("/", response_model=PaginatedTasks)
async def list_tasks(
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasks:
    stmt = select(Task).options(selectinload(Task.rule))
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    if cursor:
        stmt = stmt.where(Task.id > cursor)
    stmt = stmt.order_by(Task.id.asc()).limit(limit + 1)

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    return PaginatedTasks(items=[TaskOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/my-eligible-tasks", response_model=PaginatedTasks)
async def get_my_eligible_tasks(
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasks:
    """Highly optimised by design: index-backed query (tasks.assigned_to, status) plus a
    cache-aside layer keyed by a per-user version counter (see cache_service docstring)."""
    version = await get_my_tasks_version(current_user.id)
    cache_key = my_tasks_cache_key(current_user.id, version, cursor)

    cached = await get_cached_json(cache_key)
    if cached is not None:
        return PaginatedTasks.model_validate(cached)

    stmt = (
        select(Task)
        .options(selectinload(Task.rule))
        .where(Task.assigned_to == current_user.id)
    )
    if cursor:
        stmt = stmt.where(Task.id > cursor)
    stmt = stmt.order_by(Task.id.asc()).limit(limit + 1)

    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    payload = PaginatedTasks(items=[TaskOut.model_validate(r) for r in rows], next_cursor=next_cursor)

    await set_cached_json(cache_key, payload.model_dump(mode="json"), settings.MY_TASKS_CACHE_TTL_SECONDS)
    return payload


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    task = await _get_task_or_404(db, task_id)
    if current_user.role == Role.USER and task.assigned_to != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your task")
    return task


@router.get("/{task_id}/eligible-users", response_model=list[EligibleUserOut])
async def get_eligible_users(
    task_id: int,
    current_user: User = Depends(require_admin_or_manager),
    db: AsyncSession = Depends(get_db),
) -> list[EligibleUserOut]:
    """Admin/manager preview of current rule-matching candidates. Bounded by LIMIT and cached
    per rules_version so repeated calls while rules are unchanged hit Redis, not Postgres."""
    task = await _get_task_or_404(db, task_id)

    cached = await get_eligible_preview_cache(task_id, task.rules_version)
    if cached is not None:
        return cached

    users = await preview_eligible_users(db, task, settings.ELIGIBLE_USERS_PREVIEW_LIMIT)
    result = [EligibleUserOut.model_validate(u).model_dump(mode="json") for u in users]
    await set_eligible_preview_cache(task_id, task.rules_version, result)
    return result


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Admin/Manager can edit any field (including rules). A plain User may only transition
    the status of a task currently assigned to them (Todo -> In Progress -> Done)."""
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

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.due_date is not None:
        task.due_date = payload.due_date

    status_changed_to_done = False
    if payload.status is not None and payload.status != task.status:
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

    freed_user_id = None
    if status_changed_to_done:
        assignee = await db.get(User, task.assigned_to)
        if assignee is not None:
            assignee.active_task_count = max(0, assignee.active_task_count - 1)
            freed_user_id = assignee.id

    await db.commit()
    task = await _get_task_or_404(db, task.id)

    if freed_user_id is not None:
        await bump_my_tasks_version(freed_user_id)
    if rules_changed:
        recompute_for_task_rule_change.delay(task.id)

    return task


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
    """Manual/admin-triggered recompute -- enqueues the exact same Celery tasks used by the
    automatic triggers (idempotent, safe to call repeatedly)."""
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
