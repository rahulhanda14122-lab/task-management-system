from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "task_management",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.celery_tasks"],
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.workers.celery_tasks.evaluate_task_assignment": {"queue": "assignment"},
        "app.workers.celery_tasks.recompute_for_user_change": {"queue": "assignment"},
        "app.workers.celery_tasks.recompute_for_task_rule_change": {"queue": "assignment"},
        "app.workers.celery_tasks.sweep_pending_tasks": {"queue": "sweep"},
    },
    task_default_queue="assignment",
    task_acks_late=True,
    worker_prefetch_multiplier=4,
)

celery_app.conf.beat_schedule = {
    "sweep-pending-tasks-every-5-minutes": {
        "task": "app.workers.celery_tasks.sweep_pending_tasks",
        "schedule": 300.0,
        "options": {"queue": "sweep"},
    },
}
