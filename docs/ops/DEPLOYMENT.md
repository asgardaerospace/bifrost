# Bifrost — Production Deployment Guide

> Sprint 8 baseline. Aerospace-grade operational infrastructure: deterministic
> startup, bounded retries, structured observability, governance-first autonomy.

## Surface

| Component | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | postgres:16-alpine | 5432 | persistent state |
| `redis`    | redis:7-alpine     | 6379 | websocket fanout (multi-worker) |
| `migrator` | bifrost-backend    |  —   | one-shot `alembic upgrade head` |
| `backend`  | bifrost-backend    | 8000 | FastAPI (uvicorn) |
| `frontend` | bifrost-frontend   | 3000 | Next.js standalone |

## First boot

1. Copy template and fill in real values:
   ```
   cp .env.production.example .env.production
   # generate JWT_SECRET_KEY, set POSTGRES_PASSWORD, set CORS_ORIGINS
   ```
2. Build and bring everything up:
   ```
   docker compose -f docker-compose.prod.yml --env-file .env.production build
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d
   ```
3. Verify readiness:
   ```
   curl http://localhost:8000/api/v1/health/ready
   docker compose -f docker-compose.prod.yml run --rm backend python -m app.scripts.deploy_check
   ```

The `migrator` service runs once with `BIFROST_RUN_MIGRATIONS=1` and exits. The
`backend` waits on `migrator` completion before starting (compose
`service_completed_successfully`).

## Boot semantics

`backend/docker/entrypoint.sh` runs in this order; it refuses to boot on any
failure rather than degrade silently:

1. `validate_env` — required vars present, prod secrets meet strength rules.
2. `wait_for_db` — bounded poll of `SELECT 1` (default 60s).
3. `alembic upgrade head` if `BIFROST_RUN_MIGRATIONS=1` (off by default on
   app pods so a single migrator owns schema changes).
4. `exec uvicorn ...`

Exit codes:
* `78` — config error (env validation)
* `75` — temporary failure (db not reachable in time)

## Required environment

See `.env.production.example` for the full list. The blocking-required keys
are `DATABASE_URL`, `JWT_SECRET_KEY`, `POSTGRES_*`. Production refuses to
boot with placeholder secrets or `JWT_SECRET_KEY` shorter than 32 chars.

## Rolling forward

* Build new image tag.
* Run `python -m app.scripts.deploy_check` against the target DB.
* Apply migrations from a single migrator pod (do NOT enable
  `BIFROST_RUN_MIGRATIONS=1` on app pods).
* Drain & redeploy app pods. Health probe: `GET /api/v1/health/ready`.

## Rollback

1. Stop new app pods.
2. Restore previous image tag.
3. If schema rollback is required, see `docs/ops/RECOVERY.md`.

## Scaling

* Multiple backend workers behind a load balancer require `REDIS_URL` for
  shared websocket fanout. Without redis, each worker has an isolated event
  ribbon.
* Connection pool tunables: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
  `DB_POOL_RECYCLE_S`, `DB_POOL_TIMEOUT_S`.
* Rate limits: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_RPM`, `RATE_LIMIT_BURST`.

## CORS

Production refuses `*` in `CORS_ORIGINS` (validate_env enforces). Set the
exact frontend origins you serve.

## Frontend

The Next.js image uses `output: "standalone"`. `NEXT_PUBLIC_API_BASE_URL`
must point to the public backend URL (CORS is handled by the backend in prod;
no rewrites are emitted).
