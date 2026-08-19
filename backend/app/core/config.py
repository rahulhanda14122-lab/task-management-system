from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://taskuser:taskpass@localhost:5432/taskdb"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://taskuser:taskpass@localhost:5432/taskdb"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production-please"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rule engine / caching tunables
    PENDING_TASK_ALERT_HOURS: int = 24
    ELIGIBLE_USERS_PREVIEW_LIMIT: int = 20
    MY_TASKS_CACHE_TTL_SECONDS: int = 45
    ELIGIBLE_PREVIEW_CACHE_TTL_SECONDS: int = 60

    PROJECT_NAME: str = "Task Management System"
    API_V1_PREFIX: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
