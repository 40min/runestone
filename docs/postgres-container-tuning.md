# Postgres Container Tuning

Runestone's Docker Compose setup uses a modest Postgres profile intended to reduce resource consumption while keeping enough database concurrency for the backend and recall worker.

## Decision

The Compose deployment configures Postgres and the application connection pools with conservative defaults:

- `POSTGRES_MAX_CONNECTIONS=50`
- `POSTGRES_SHARED_BUFFERS=128MB`
- `POSTGRES_EFFECTIVE_CACHE_SIZE=384MB`
- `POSTGRES_MAINTENANCE_WORK_MEM=32MB`
- `POSTGRES_CHECKPOINT_TIMEOUT=15min`
- `POSTGRES_MAX_WAL_SIZE=512MB`
- `DATABASE_POOL_SIZE=8`
- `DATABASE_MAX_OVERFLOW=8`

The backend container also sets `STARTUP_DB_CHECK=false`. Container startup already runs `alembic upgrade head` before Uvicorn starts, so the extra application-level table introspection is redundant in Compose and can delay readiness on constrained hosts.

## Rationale

The previous backend pool allowed up to 30 database connections per backend process. That is useful on larger hosts, but it can over-allocate memory and connection slots for smaller container deployments.

The current defaults reduce idle resource pressure while preserving burst capacity:

- One backend process can use up to 16 database connections.
- The recall worker can use up to 16 database connections.
- Postgres keeps spare connection capacity for migrations, manual sessions, and maintenance.

This keeps the system resilient when multiple backend code paths or agent tools use the database in parallel, without making Postgres reserve capacity for a much larger workload than the default deployment needs.

## Connection Budget

When changing worker counts or pool sizes, keep Postgres capacity above the possible application connection demand:

```text
(backend_processes + recall_processes) * (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW) + maintenance_margin
```

Use at least `5` for `maintenance_margin` so Alembic, shell access, and operational tools have room to connect.

For example, with one backend process and one recall process:

```text
(1 + 1) * (8 + 8) + 5 = 37
```

The default `POSTGRES_MAX_CONNECTIONS=50` leaves comfortable headroom for that deployment shape.

## Durability

The tuning intentionally does not disable core durability settings such as `fsync` or `full_page_writes`. The goal is lower resource use and faster readiness, not trading away database safety.

## When To Tune Up

Increase `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, and `POSTGRES_MAX_CONNECTIONS` together if the deployment adds more backend worker processes or starts returning SQLAlchemy pool timeout errors under expected load.

Increase memory-related Postgres settings only when the container has enough available RAM after accounting for the backend, frontend, recall worker, filesystem cache, and the host OS.
