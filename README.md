# Task Management System with Dynamic Rule-Based Task Assignment

A scalable task management system where tasks are never manually assigned. Each task declares
eligibility rules (department, experience, location, current workload) and a background rule
engine automatically finds and assigns the best-matching user — with automatic re-evaluation
whenever a user's profile or a task's rules change.

> **Full technical documentation** (architecture, API reference with request/response bodies,
> scenario tables, sequence diagrams, caching examples, scaling guide):
> **[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)**

## Stack

| Layer | Technology |
|---|---|
| Backend API | Python, FastAPI (async), SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL 16 |
| Cache & Message Broker | Redis 7 |
| Background Processing | Celery (+ Celery Beat for scheduled sweeps) |
| Auth | JWT access tokens + rotating refresh tokens |
| Frontend | React 18 (Vite) |
| Infra | Docker & Docker Compose |

## Quick Start

```bash
docker compose up --build
docker compose exec backend python -m app.seed.seed_data   # run once
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

**Demo accounts:** `admin@example.com` / `admin123` · `manager@example.com` / `manager123` · `user1@example.com` / `password123`

---

## Architecture Decisions

| Decision | Choice | Why |
|---|---|---|
| Rule storage | Structured columns on `task_rules` | Fixed attribute set → composite/partial indexes; rule engine compiles to indexed SQL (not a generic interpreter) |
| Assignment execution | Async via Celery | `POST /tasks/` returns immediately; matching happens off the request path |
| Tie-break | Least-recently-assigned (`last_assigned_at`) | Fair rotation among equally loaded users; never-assigned users preferred |
| No eligible users | `assignment_status = pending` | Normal state, not an error; auto-retried on data changes + periodic sweep |
| In-progress tasks | Lock once started | `in_progress` / `done` tasks are never reassigned due to profile or rule changes |
| Recompute scope | Event-driven, bounded | Per-task or per-user indexed lookups — never a full 1M-row scan |
| Cache invalidation | Version counter (`INCR`) | O(1) bust of all cached pages without Redis pattern deletes |
| Message broker | Redis via Celery | Simpler ops for this workload; broker upgrade path to RabbitMQ available |
| Concurrency | `FOR UPDATE SKIP LOCKED` | Safe parallel assignment without double-allocating user capacity |

See [TECHNICAL_DOCUMENTATION.md §3](TECHNICAL_DOCUMENTATION.md#3-architecture-decisions) for full rationale and diagrams.

---

## Indexing Strategy

Indexes match the exact query shapes of the rule engine and hot read APIs.

| Index | Purpose |
|---|---|
| `users(department, experience_years, active_task_count, last_assigned_at) WHERE is_active` | Core assignment query — filter + sort in one index scan |
| `users(email)` UNIQUE | Login |
| `tasks(assigned_to, status)` | `GET /my-eligible-tasks` |
| `tasks(assignment_status) WHERE = 'pending'` (partial) | Sweep + reverse recompute — bounded to small pending subset |
| `task_rules(department, min_experience_years)` | Join filter for "which pending tasks might this user now match" |
| `tasks(due_date, priority, created_by)` | Admin listing/filtering |

At 1M tasks, partial indexes on `assignment_status = 'pending'` keep recompute and sweep costs
flat regardless of how large the assigned/done history grows.

See [TECHNICAL_DOCUMENTATION.md §10](TECHNICAL_DOCUMENTATION.md#10-indexing-strategy).

---

## Caching Strategy

**Pattern:** cache-aside via Redis (logical DB 0).

| Endpoint | Cache key | Invalidation |
|---|---|---|
| `GET /my-eligible-tasks` | `my_tasks:{user_id}:v{version}:c{cursor}` | Bump `my_tasks_version:{user_id}` on assignment/status change |
| `GET /tasks/{id}/eligible-users` | `eligible_preview:{task_id}:v{rules_version}` | Auto via `rules_version++` on rule edit |

**Version invalidation example:** when user 3 gets a new assignment, `INCR my_tasks_version:3`
(from 1 → 2). All cached pages under `v1` become stale instantly; next read uses `v2` keys
and hits the database. No wildcard key deletion needed.

**Cursor pagination:** `cursor` is the last task `id` from the previous page (`?cursor=20` →
`WHERE id > 20`). Each page is a separate cache entry.

See [TECHNICAL_DOCUMENTATION.md §11](TECHNICAL_DOCUMENTATION.md#11-caching-strategy) for a
step-by-step worked example.

---

## Rule Engine Design

Each task defines eligibility rules as nullable structured columns (`department`,
`min_experience_years`, `location`, `max_active_tasks`). NULL = unconstrained.

**Assignment query** (inside a transaction):

```sql
SELECT id FROM users
WHERE is_active = true
  AND (department = :dept OR :dept IS NULL)
  AND (experience_years >= :min_exp OR :min_exp IS NULL)
  AND (location = :loc OR :loc IS NULL)
  AND (active_task_count < :max_active OR :max_active IS NULL)
ORDER BY active_task_count ASC,
         last_assigned_at ASC NULLS FIRST,
         id ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

| Scenario | Outcome |
|---|---|
| Multiple eligible users | Least-loaded → least-recently-assigned |
| No eligible users | Task stays `pending`; retried automatically |
| Task is `in_progress` or `done` | Locked to current assignee |
| Concurrent workers | Row lock prevents double-assignment |

Implementation: [`backend/app/services/rule_engine.py`](backend/app/services/rule_engine.py)

See [TECHNICAL_DOCUMENTATION.md §8](TECHNICAL_DOCUMENTATION.md#8-rule-engine-design) for
scenario tables and sequence diagrams.

---

## Recompute Strategy

Recompute is **event-driven and bounded** — never a full-table scan.

| Trigger | Celery job | Scope |
|---|---|---|
| Task created | `evaluate_task_assignment(task_id)` | Single task |
| Rules edited | `recompute_for_task_rule_change(task_id)` | Single task |
| User profile changed | `recompute_for_user_change(user_id)` | User's todo tasks + matching pending tasks |
| Manual admin call | Same jobs via `POST /tasks/recompute-eligibility` | Specified task or user |
| Safety net (every 5 min) | `sweep_pending_tasks()` | All `pending` tasks only |

**User-change recompute** performs two bounded lookups:
1. **Forward:** re-evaluate assigned `todo` tasks (in_progress/done are locked)
2. **Reverse:** find `pending` tasks whose rules now match the user's new profile

**Task completion:** marking a task `done` decrements the assignee's `active_task_count`,
freeing capacity for future assignments.

See [TECHNICAL_DOCUMENTATION.md §9](TECHNICAL_DOCUMENTATION.md#9-recompute-strategy).

---

## API Reference (summary)

Base path: `/api/v1` · Full docs with request/response bodies:
[TECHNICAL_DOCUMENTATION.md §13](TECHNICAL_DOCUMENTATION.md#13-api-documentation)

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/auth/signup` | Public | Create account |
| POST | `/auth/login` | Public | Returns access + refresh tokens |
| POST | `/auth/refresh` | Public | Rotates refresh token |
| GET | `/users/me` | Any | Current user profile |
| PATCH | `/users/{id}` | Admin | Triggers recompute on eligibility fields |
| POST | `/tasks/` | Admin/Manager | Creates task; enqueues assignment (202) |
| GET | `/tasks/my-eligible-tasks` | Any | Cached, cursor-paginated |
| GET | `/tasks/{id}/eligible-users` | Admin/Manager | Cached preview, capped at 20 |
| PATCH | `/tasks/{id}` | Admin/Manager or assignee | Admin edits all; User advances status only |
| POST | `/tasks/recompute-eligibility` | Admin/Manager | Manual recompute trigger |

---

## Project Layout

```
.
├── TECHNICAL_DOCUMENTATION.md   # Shareable technical doc (this is the main reference)
├── ARCHITECTURE.md              # Original architecture design
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── core/                    # config, security, redis, celery
│   │   ├── api/routes/              # auth, users, tasks
│   │   ├── services/                # rule_engine, cache_service
│   │   ├── workers/                 # celery_tasks
│   │   ├── models/                  # SQLAlchemy ORM
│   │   └── schemas/                 # Pydantic DTOs
│   └── alembic/                     # DB migrations
└── frontend/
    └── src/                         # React app
```

---

## Performance Targets

Designed for **100k users / 1M tasks / <200ms** on hot read paths:

- Async FastAPI + connection pooling (PgBouncer at scale)
- Index-backed queries for assignment and my-tasks
- Redis cache-aside on two performance-critical endpoints
- All assignment/recompute work offloaded to Celery workers
- Partial indexes keep pending-task operations cheap at any table size

---

## Migrations

```bash
docker compose exec backend alembic upgrade head
```

Current head: `0002` (adds `users.last_assigned_at` for least-recently-assigned tie-break).
