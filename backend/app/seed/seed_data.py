"""Seed data for local development / demoing the assignment engine.

Run inside the backend container (after migrations):
    python -m app.seed.seed_data

Creates:
- 1 admin account, 1 manager account
- ~40 regular users spread across all departments/experience/locations
- ~15 sample tasks with varied rules, immediately evaluated through the same rule engine
  the Celery workers use, so the seed produces a realistic mix of ASSIGNED and PENDING tasks.
"""

import itertools
import random

from app.core.security import hash_password
from app.db.sync_session import SyncSessionLocal
from app.models.enums import Department, Role, TaskPriority
from app.models.task import Task
from app.models.task_rule import TaskRule
from app.models.user import User
from app.services.rule_engine import assign_task

LOCATIONS = ["Bengaluru", "Mumbai", "Delhi", "Pune", "Hyderabad", "Remote"]

DEPARTMENTS = list(Department)


def _make_users(n: int) -> list[User]:
    users = []
    dept_cycle = itertools.cycle(DEPARTMENTS)
    loc_cycle = itertools.cycle(LOCATIONS)
    for i in range(n):
        dept = next(dept_cycle)
        loc = next(loc_cycle)
        users.append(
            User(
                email=f"user{i+1}@example.com",
                password_hash=hash_password("password123"),
                full_name=f"Demo User {i+1}",
                role=Role.USER,
                department=dept,
                experience_years=random.randint(0, 15),
                location=loc,
                active_task_count=0,
            )
        )
    return users


SAMPLE_TASKS = [
    {
        "title": "Reconcile Q3 finance ledger",
        "description": "Cross-check Q3 transactions against the general ledger.",
        "priority": TaskPriority.HIGH,
        "rules": {"department": Department.FINANCE, "min_experience_years": 4, "max_active_tasks": 5},
    },
    {
        "title": "Onboard new hires",
        "description": "Run onboarding paperwork and orientation for the new HR batch.",
        "priority": TaskPriority.MEDIUM,
        "rules": {"department": Department.HR, "min_experience_years": 2, "max_active_tasks": 8},
    },
    {
        "title": "Patch production servers",
        "description": "Apply the latest security patches across the IT fleet.",
        "priority": TaskPriority.HIGH,
        "rules": {"department": Department.IT, "min_experience_years": 5, "max_active_tasks": 3},
    },
    {
        "title": "Audit warehouse inventory",
        "description": "Physical inventory count reconciliation for the Pune warehouse.",
        "priority": TaskPriority.MEDIUM,
        "rules": {"department": Department.OPERATIONS, "location": "Pune", "max_active_tasks": 6},
    },
    {
        "title": "Prepare annual budget forecast",
        "description": "Draft next fiscal year's departmental budget forecast.",
        "priority": TaskPriority.HIGH,
        "rules": {"department": Department.FINANCE, "min_experience_years": 8, "max_active_tasks": 4},
    },
    {
        "title": "Design new performance review template",
        "description": "Revamp the HR performance review form for next cycle.",
        "priority": TaskPriority.LOW,
        "rules": {"department": Department.HR, "min_experience_years": 3},
    },
    {
        "title": "Migrate database to new cluster",
        "description": "Zero-downtime migration of the primary Postgres cluster.",
        "priority": TaskPriority.HIGH,
        "rules": {"department": Department.IT, "min_experience_years": 6, "location": "Bengaluru", "max_active_tasks": 3},
    },
    {
        "title": "Optimise delivery routes",
        "description": "Re-plan logistics delivery routes for the western region.",
        "priority": TaskPriority.MEDIUM,
        "rules": {"department": Department.OPERATIONS, "min_experience_years": 4, "max_active_tasks": 5},
    },
    {
        "title": "Impossible finance task (demo: no eligible users)",
        "description": "Deliberately unreachable rule to demonstrate the PENDING flow.",
        "priority": TaskPriority.LOW,
        "rules": {"department": Department.FINANCE, "min_experience_years": 25},
    },
]


def run() -> None:
    with SyncSessionLocal() as session:
        if session.query(User).count() > 0:
            print("Seed data already present, skipping.")
            return

        admin = User(
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            full_name="Alice Admin",
            role=Role.ADMIN,
            department=Department.IT,
            experience_years=10,
            location="Bengaluru",
        )
        manager = User(
            email="manager@example.com",
            password_hash=hash_password("manager123"),
            full_name="Mark Manager",
            role=Role.MANAGER,
            department=Department.OPERATIONS,
            experience_years=8,
            location="Mumbai",
        )
        demo_users = _make_users(40)

        session.add_all([admin, manager, *demo_users])
        session.commit()
        print(f"Created {2 + len(demo_users)} users (admin@example.com / admin123, manager@example.com / manager123)")

        creator = admin
        task_ids = []
        for spec in SAMPLE_TASKS:
            task = Task(
                title=spec["title"],
                description=spec["description"],
                priority=spec["priority"],
                created_by=creator.id,
            )
            rule_spec = spec["rules"]
            task.rule = TaskRule(
                department=rule_spec.get("department"),
                min_experience_years=rule_spec.get("min_experience_years"),
                location=rule_spec.get("location"),
                max_active_tasks=rule_spec.get("max_active_tasks"),
            )
            session.add(task)
            session.commit()
            task_ids.append(task.id)

        for task_id in task_ids:
            result = assign_task(session, task_id)
            print(f"Task {task_id}: assignment_status={result.assignment_status.value}, assigned_to={result.assigned_to}")

        print("Seed complete.")


if __name__ == "__main__":
    run()
