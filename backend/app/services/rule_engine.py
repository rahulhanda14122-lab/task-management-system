"""Dynamic rule-based assignment engine.

Design notes (see /ARCHITECTURE.md for the full write-up):
- Rules are structured (department / min experience / location / max active tasks), so they
  compile directly into an indexed SQL predicate instead of an interpreter over arbitrary
  conditions.
- Multiple eligible users: tie-break is "least loaded" (lowest active_task_count), then
  least-recently-assigned (oldest last_assigned_at; NULL = never assigned, highest priority).
- In-progress / done tasks are locked to their current assignee ("lock once started").
- No eligible users: not an error. The task is left/returned to PENDING and retried later by
  the event-driven recompute hooks and the periodic sweep.
- Concurrency safety: candidate selection + assignment happen in one transaction using
  `FOR UPDATE SKIP LOCKED`, so two workers racing on overlapping eligible pools never
  double-assign or corrupt `active_task_count`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.enums import AssignmentStatus, TaskStatus
from app.models.task import Task
from app.models.task_rule import TaskRule
from app.models.user import User


def _base_candidate_query(rule: TaskRule) -> Select:
    stmt = select(User).where(User.is_active.is_(True))
    if rule.department is not None:
        stmt = stmt.where(User.department == rule.department)
    if rule.min_experience_years is not None:
        stmt = stmt.where(User.experience_years >= rule.min_experience_years)
    if rule.location is not None:
        stmt = stmt.where(User.location == rule.location)
    if rule.max_active_tasks is not None:
        stmt = stmt.where(User.active_task_count < rule.max_active_tasks)
    return stmt.order_by(
        User.active_task_count.asc(),
        User.last_assigned_at.asc().nullsfirst(),
        User.id.asc(),
    )


def is_user_eligible_for_rule(user: User, rule: TaskRule) -> bool:
    """Pure, side-effect-free check used when re-validating an already-assigned user."""
    if not user.is_active:
        return False
    if rule.department is not None and user.department != rule.department:
        return False
    if rule.min_experience_years is not None and user.experience_years < rule.min_experience_years:
        return False
    if rule.location is not None and user.location != rule.location:
        return False
    if rule.max_active_tasks is not None and user.active_task_count >= rule.max_active_tasks:
        return False
    return True


def is_assignment_locked(task: Task) -> bool:
    """Enterprise policy: once work has started (or finished), do not reassign."""
    return task.status in (TaskStatus.IN_PROGRESS, TaskStatus.DONE)


@dataclass
class AssignmentResult:
    task_id: int
    assigned_to: int | None
    assignment_status: AssignmentStatus


def assign_task(session: Session, task_id: int) -> AssignmentResult:
    """Atomically (re)evaluate and assign a single task. Safe to call repeatedly (idempotent):
    a task that is already validly ASSIGNED is left untouched; in_progress/done tasks stay
    locked to their current assignee regardless of eligibility changes.
    """
    task = session.get(Task, task_id, with_for_update=True)
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    rule = task.rule
    if rule is None:
        # No rules defined at all -> unconstrained, anyone active is eligible.
        rule = TaskRule(task_id=task_id)

    if task.assignment_status == AssignmentStatus.ASSIGNED and task.assigned_to is not None:
        if is_assignment_locked(task):
            return AssignmentResult(task.id, task.assigned_to, task.assignment_status)

        current = session.get(User, task.assigned_to)
        if current is not None and is_user_eligible_for_rule(current, rule):
            return AssignmentResult(task.id, task.assigned_to, task.assignment_status)
        # Currently assigned user no longer qualifies -> release capacity, fall through to reassign.
        if current is not None:
            current.active_task_count = max(0, current.active_task_count - 1)
        task.assigned_to = None
        task.assignment_status = AssignmentStatus.PENDING

    candidates_stmt = _base_candidate_query(rule).with_for_update(skip_locked=True).limit(1)
    candidate = session.execute(candidates_stmt).scalars().first()

    if candidate is None:
        task.assignment_status = AssignmentStatus.PENDING
        task.assigned_to = None
        session.commit()
        return AssignmentResult(task.id, None, task.assignment_status)

    candidate.active_task_count += 1
    candidate.last_assigned_at = datetime.now(timezone.utc)
    task.assigned_to = candidate.id
    task.assignment_status = AssignmentStatus.ASSIGNED
    session.commit()
    return AssignmentResult(task.id, candidate.id, task.assignment_status)


def release_task_capacity(session: Session, task: Task) -> None:
    """Call when a task moves to DONE: frees the assignee's capacity for future assignments."""
    if task.assigned_to is None:
        return
    user = session.get(User, task.assigned_to, with_for_update=True)
    if user is not None:
        user.active_task_count = max(0, user.active_task_count - 1)


def find_pending_task_ids_matching_user(session: Session, user: User) -> list[int]:
    """Bounded reverse lookup: which PENDING tasks might this (just-changed) user now match?

    Scoped to the small `pending` subset via the tasks.assignment_status index, then joined to
    task_rules on its primary key (task_id) -- a cheap PK lookup, not a table scan. The
    max_active_tasks constraint is intentionally not filtered here (it depends on the
    candidate's live active_task_count at assignment time) -- `assign_task` re-validates it
    authoritatively.
    """
    stmt = (
        select(Task.id)
        .join(TaskRule, TaskRule.task_id == Task.id)
        .where(Task.assignment_status == AssignmentStatus.PENDING)
        .where((TaskRule.department.is_(None)) | (TaskRule.department == user.department))
        .where(
            (TaskRule.min_experience_years.is_(None)) | (TaskRule.min_experience_years <= user.experience_years)
        )
        .where((TaskRule.location.is_(None)) | (TaskRule.location == user.location))
    )
    return list(session.execute(stmt).scalars().all())


async def preview_eligible_users(db: AsyncSession, task: Task, limit: int) -> list[User]:
    """Read-only candidate preview for GET /tasks/{id}/eligible-users. No locking -- this is a
    point-in-time snapshot for admins, not part of the assignment transaction itself.
    """
    rule = task.rule or TaskRule(task_id=task.id)
    stmt = _base_candidate_query(rule).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
