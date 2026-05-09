# Bifrost — Operational Runbook

> What to do when something looks wrong. Sprint 8 baseline.

## First-look checks

```
curl -s https://<host>/api/v1/health
curl -s https://<host>/api/v1/health/ready    # full check
curl -s https://<host>/api/v1/observability/metrics | jq .
```

Look at counters: `http.status.5xx`, `reliability.retry.exhausted.*`,
`reliability.breaker.opened.*`, `policy.deny.*`, `events.published.*`,
`http.rate_limited`.

## Symptom → triage

### Operators see "REALTIME · RECONNECTING"

1. Check websocket layer — `pubsub.connections` gauge in `/observability/metrics`.
2. If 0 across the fleet: backend is up but not accepting ws upgrades. Check
   `redis` health (`docker compose -f docker-compose.prod.yml ps redis`) and
   the `pubsub.attach_redis` log line at startup.
3. If gauge >0 but specific operators are stuck: instruct them to refresh.
   The client reconnects with exponential backoff (1s → 30s) and replays
   missed events from `/events/replay?since=<lastId>` automatically.

### Operators see "REALTIME · QUIET"

The connection is open but no frames have arrived in >60s. This usually
means events are flowing into the DB but pubsub fanout has stalled. Check:
* `pubsub.connections` gauge (the surface itself is connected).
* `events.published.*` counters (are events being persisted at all?).
* Redis subscriber task — restart the backend pod if redis is configured
  but the subscriber log line `pubsub: redis fanout attached` is missing.

### 5xx spike

1. `/observability/metrics` — `http.status.5xx` counter.
2. Recent structured logs (JSON to stdout). Filter on `level=ERROR`.
3. Correlate: pull an offending response's `x-request-id` header and grep
   logs for that id. Trace metadata (`trace_id`, `mission_id`, `workflow_id`)
   flows through every record.

### Rate-limit pressure

* Counter: `http.rate_limited`.
* Tune `RATE_LIMIT_RPM` / `RATE_LIMIT_BURST` and bounce backend.

### Approval/governance regression

1. Read recent `/governance/audit?limit=50`.
2. Check `policy.deny.*` counters for unexpected denies.
3. Inspect autonomy ledger: `GET /agents/operations?limit=50`.
4. If a policy is blocking legitimate work, an admin can record an override
   via `POST /governance/policies/{action_type}/override`. The override
   itself is audited.

### Database under pressure

* `db.pool_*` SQLAlchemy stats (visible in /observability/metrics if engine
  events are wired in your env).
* Tune `DB_POOL_SIZE` upward; consider running a read replica if reporting
  workloads grow.

## Escalation

* Critical (data corruption, security incident): pause autonomous workflow
  execution by setting `GOVERNANCE_AUTONOMY_CONFIDENCE_FLOOR=1.0` (rejects
  all proposals via the policy floor) and bouncing backend pods. Then follow
  RECOVERY.md.

## Common admin operations

```
# rotate JWT secret (forces all sessions to re-login)
JWT_SECRET_KEY=<new>  # update .env.production
docker compose -f docker-compose.prod.yml up -d backend

# trigger a manual backup
DATABASE_URL=... ops/scripts/backup.sh

# verify a backup is restorable (against scratch DB)
DATABASE_URL=postgresql://.../scratch ops/scripts/restore.sh ./var/backups/<file>.sql.gz
```
