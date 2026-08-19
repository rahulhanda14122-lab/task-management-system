"""Cache-aside helpers for the two "highly optimised" read endpoints.

- GET /my-eligible-tasks uses a per-user *cache version* counter instead of pattern-deleting
  keys on invalidation (Redis has no cheap "delete by prefix"). Bumping the version instantly
  invalidates every cached page for that user without a SCAN.
- GET /tasks/{id}/eligible-users is keyed by the task's `rules_version` column, so editing a
  task's rules naturally busts the cache without any explicit delete call.
"""

import json
from typing import Any

from app.core.cache import async_redis_client, sync_redis_client
from app.core.config import settings


def _my_tasks_version_key(user_id: int) -> str:
    return f"my_tasks_version:{user_id}"


def my_tasks_cache_key(user_id: int, version: int, cursor: int | None) -> str:
    return f"my_tasks:{user_id}:v{version}:c{cursor or 0}"


def eligible_preview_cache_key(task_id: int, rules_version: int) -> str:
    return f"eligible_preview:{task_id}:v{rules_version}"


async def get_my_tasks_version(user_id: int) -> int:
    value = await async_redis_client.get(_my_tasks_version_key(user_id))
    return int(value) if value else 1


async def bump_my_tasks_version(user_id: int) -> None:
    await async_redis_client.incr(_my_tasks_version_key(user_id))


def bump_my_tasks_version_sync(user_id: int) -> None:
    sync_redis_client.incr(_my_tasks_version_key(user_id))


async def get_cached_json(key: str) -> Any | None:
    raw = await async_redis_client.get(key)
    return json.loads(raw) if raw else None


async def set_cached_json(key: str, value: Any, ttl_seconds: int) -> None:
    await async_redis_client.set(key, json.dumps(value), ex=ttl_seconds)


async def get_eligible_preview_cache(task_id: int, rules_version: int) -> Any | None:
    return await get_cached_json(eligible_preview_cache_key(task_id, rules_version))


async def set_eligible_preview_cache(task_id: int, rules_version: int, value: Any) -> None:
    await set_cached_json(
        eligible_preview_cache_key(task_id, rules_version),
        value,
        settings.ELIGIBLE_PREVIEW_CACHE_TTL_SECONDS,
    )
