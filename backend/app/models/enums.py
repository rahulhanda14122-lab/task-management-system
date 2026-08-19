import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """SQLAlchemy's Enum() stores the Python member *name* (e.g. "ADMIN") by default, not
    its `.value`. Our Postgres native enum types use lowercase values, so every enum column
    must be declared with this helper to serialize by `.value` instead.
    """
    return SAEnum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class Role(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


class Department(str, enum.Enum):
    FINANCE = "finance"
    HR = "hr"
    IT = "it"
    OPERATIONS = "operations"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AssignmentStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    UNASSIGNABLE = "unassignable"
