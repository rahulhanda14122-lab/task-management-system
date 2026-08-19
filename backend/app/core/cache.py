import redis.asyncio as aioredis
import redis as sync_redis

from app.core.config import settings

# Async client for FastAPI request handlers.
async_redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# Sync client for Celery workers (which invalidate cache entries after assignment/recompute).
sync_redis_client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
