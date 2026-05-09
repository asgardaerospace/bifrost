#!/usr/bin/env bash
# Bifrost backend production entrypoint.
#
# Responsibilities (in order):
#   1. Validate environment via app.scripts.validate_env (fast-fail).
#   2. Wait for the database to be reachable (bounded loop).
#   3. Optionally run alembic migrations when BIFROST_RUN_MIGRATIONS=1.
#   4. Exec the supplied command (uvicorn by default).
#
# Designed to be deterministic, observable, and safe for restart loops.

set -euo pipefail

log() {
    printf '[entrypoint] %s\n' "$*" >&2
}

log "starting bifrost backend (env=${BIFROST_ENV:-unknown}, image=${BIFROST_IMAGE_TAG:-local})"

# Step 1 — environment sanity.
if ! python -m app.scripts.validate_env; then
    log "environment validation failed — refusing to boot"
    exit 78  # EX_CONFIG
fi

# Step 2 — database reachability (bounded retry, no infinite wait).
WAIT_DB="${BIFROST_WAIT_FOR_DB:-1}"
WAIT_DB_TIMEOUT="${BIFROST_WAIT_FOR_DB_TIMEOUT:-60}"
if [ "$WAIT_DB" = "1" ]; then
    log "waiting up to ${WAIT_DB_TIMEOUT}s for database"
    if ! python -m app.scripts.wait_for_db --timeout "$WAIT_DB_TIMEOUT"; then
        log "database not reachable after ${WAIT_DB_TIMEOUT}s — refusing to boot"
        exit 75  # EX_TEMPFAIL
    fi
fi

# Step 3 — migrations (opt-in; default off so a single migrator pod can own them).
if [ "${BIFROST_RUN_MIGRATIONS:-0}" = "1" ]; then
    log "running alembic upgrade head"
    alembic upgrade head
fi

# Step 4 — handoff.
log "starting application: $*"
exec "$@"
