# Bifrost — Backup & Recovery

> Doctrine: documented recovery flows, tested rollback paths, replay-safe
> operational continuity.

## Backups

`ops/scripts/backup.sh` writes a gzipped pg_dump tagged with timestamp +
alembic head:

```
DATABASE_URL=...  BIFROST_BACKUP_DIR=/var/backups/bifrost  ops/scripts/backup.sh
```

* Default retention: 14 days (`BIFROST_BACKUP_RETENTION_DAYS`).
* Production: schedule via cron / k8s CronJob. Recommended cadence: hourly
  for active operations periods, daily otherwise.
* Off-site copy is the operator's responsibility — script does not push to
  remote storage by design (no embedded credentials).

## Restore

`ops/scripts/restore.sh <dump.sql.gz>` restores into the configured DB:

```
DATABASE_URL=postgresql+psycopg://...  ops/scripts/restore.sh ./var/backups/bifrost-XXXX.sql.gz
```

Safety:
* Refuses to overwrite a non-empty DB unless `BIFROST_RESTORE_FORCE=1`.
* Wraps the SQL replay in a single transaction.
* Runs `alembic upgrade head` afterwards.
* Runs `python -m app.scripts.deploy_check` to verify schema sanity.

## Schema rollback

Bifrost migrations are forward-only by convention. To revert a schema change:

1. `alembic downgrade -1` against a *staging* DB to validate the down() path.
2. If clean, take a fresh production backup.
3. `alembic downgrade -1` in production (preferably from a maintenance pod
   with no app traffic).
4. Redeploy the app pods on the previous image tag.

## Event replay recovery

Operational events are append-only and indexed by `id ASC`. To rebuild
derived state after an incident:

* Subscribers can resync via `GET /api/v1/events/replay?since=<cursor>`.
* The frontend already does this on every websocket reconnect — no operator
  action needed for in-flight clients.
* Server-side derived state (pressure history, recommendations) recomputes
  on the next event for the affected mission. To force a recompute:
  `POST /api/v1/missions/<id>/pressure/recompute`.

## Workflow recovery

Autonomy operations and proposed actions are persisted at every state
transition. A failed agent run leaves an `autonomy_operations` row in
`status='failed'` with a stack trace in `payload`. To re-run:

1. Fetch the operation: `GET /api/v1/agents/operations/<id>`.
2. Re-trigger the workflow via the originating endpoint. The idempotency
   layer protects against duplicate side effects when the same logical
   trigger fires twice in a short window.

## Disaster recovery (full DB loss)

1. Provision a fresh postgres instance.
2. Run the latest tested backup through `restore.sh`.
3. Bring backend up with `BIFROST_RUN_MIGRATIONS=1` on a single pod (the
   `migrator` service in `docker-compose.prod.yml` does this).
4. Verify with `deploy_check`.
5. Resume normal traffic.

Acceptable RTO/RPO depends on backup cadence — Bifrost is durable but is
not a hot-standby system. For zero-RPO operation, layer in WAL streaming
to a replica.
