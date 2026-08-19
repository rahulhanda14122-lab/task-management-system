"""Background jobs backing the assignment/recompute strategy described in ARCHITECTURE.md.

Two queues (configured in app.core.celery_app):
- `assignment`: low-latency, triggered by task create / rule change / user attribute change.
- `sweep`: low-priority periodic safety net over the (small) PENDING subset.
"""

import logging

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.db.sync_session import SyncSessionLocal
from app.models.enums import AssignmentStatus, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.services.cache_service import bump_my_tasks_version_sync
from app.services.rule_engine import assign_task, find_pending_task_ids_matching_user

logger = logging.getLogger(__name__)


def _assign_and_invalidate(session, task_id: int) -> None:
    task = session.get(Task, task_id)
    old_assignee = task.assigned_to if task else None

    result = assign_task(session, task_id)

    if result.assigned_to != old_assignee:
        if old_assignee is not None:
            bump_my_tasks_version_sync(old_assignee)
        if result.assigned_to is not None:
            bump_my_tasks_version_sync(result.assigned_to)


@celery_app.task(name="app.workers.celery_tasks.evaluate_task_assignment", bind=True, max_retries=3, default_retry_delay=5)
def evaluate_task_assignment(self, task_id: int) -> None:
    """Triggered on task creation. Single-task, index-driven, cheap."""
    try:
        with SyncSessionLocal() as session:
            _assign_and_invalidate(session, task_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("evaluate_task_assignment failed for task_id=%s", task_id)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.celery_tasks.recompute_for_task_rule_change",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def recompute_for_task_rule_change(self, task_id: int) -> None:
    """Triggered when an admin edits a task's rules (Story 4). Same code path as initial
    assignment -- `assign_task` re-validates the current assignee and reassigns if needed.
    """
    try:
        with SyncSessionLocal() as session:
            _assign_and_invalidate(session, task_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("recompute_for_task_rule_change failed for task_id=%s", task_id)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.celery_tasks.recompute_for_user_change", bind=True, max_retries=3, default_retry_delay=5
)
def recompute_for_user_change(self, user_id: int) -> None:
    """Triggered when a user's department/experience/location changes (Story 3).

    Two bounded operations -- never a full-table scan:
      1. Forward check: tasks currently assigned to this user that they may no longer qualify for.
      2. Reverse check: PENDING tasks (small, indexed subset) that this user might now match.
    """
    try:
        with SyncSessionLocal() as session:
            user = session.get(User, user_id)
            if user is None:
                return

            # Only re-evaluate assigned tasks still in todo; in_progress/done are locked.
            assigned_task_ids = list(
                session.execute(
                    select(Task.id).where(
                        Task.assigned_to == user_id,
                        Task.assignment_status == AssignmentStatus.ASSIGNED,
                        Task.status == TaskStatus.TODO,
                    )
                ).scalars()
            )
            for task_id in assigned_task_ids:
                _assign_and_invalidate(session, task_id)

            pending_task_ids = find_pending_task_ids_matching_user(session, user)
            for task_id in pending_task_ids:
                _assign_and_invalidate(session, task_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("recompute_for_user_change failed for user_id=%s", user_id)
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.celery_tasks.sweep_pending_tasks")
def sweep_pending_tasks() -> None:
    """Periodic safety net (Celery Beat, every 5 min): re-attempts assignment for all PENDING
    tasks. Bounded by the partial index on assignment_status='pending', so cost stays low
    regardless of how large the overall tasks table grows.
    """
    with SyncSessionLocal() as session:
        pending_ids = list(
            session.execute(select(Task.id).where(Task.assignment_status == AssignmentStatus.PENDING)).scalars()
        )
        for task_id in pending_ids:
            try:
                _assign_and_invalidate(session, task_id)
            except Exception:  # noqa: BLE001
                logger.exception("sweep_pending_tasks failed for task_id=%s", task_id)
                session.rollback()
