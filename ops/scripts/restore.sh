#!/usr/bin/env bash
# Bifrost — production restore script.
#
# Restores a pg_dump produced by backup.sh into the configured DATABASE_URL.
# REFUSES to run against a non-empty database unless BIFROST_RESTORE_FORCE=1.
#
# Usage:
#   DATABASE_URL=... ops/scripts/restore.sh ./var/backups/bifrost-XYZ.sql.gz
#
# After restore:
#   * runs alembic upgrade head (no-op if dump matches current head).
#   * runs deploy_check.py to verify table presence + alembic head.

set -euo pipefail

DUMP="${1:-}"
if [ -z "$DUMP" ]; then
    echo "usage: $0 <dump.sql.gz>" >&2
    exit 2
fi
if [ ! -f "$DUMP" ]; then
    echo "[restore] file not found: $DUMP" >&2
    exit 2
fi
if [ -z "${DATABASE_URL:-}" ]; then
    echo "[restore] DATABASE_URL not set" >&2
    exit 78
fi

# Safety — refuse to overwrite a non-empty DB without an explicit force.
if [ "${BIFROST_RESTORE_FORCE:-0}" != "1" ]; then
    nonempty="$(python -c "
import os, sys
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    n = c.execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\")).scalar()
print('1' if n and n > 0 else '0')
" 2>/dev/null || echo 0)"
    if [ "$nonempty" = "1" ]; then
        echo "[restore] target DB is non-empty; set BIFROST_RESTORE_FORCE=1 to proceed" >&2
        exit 1
    fi
fi

echo "[restore] applying $DUMP"
gunzip -c "$DUMP" | psql "$DATABASE_URL" --single-transaction --set ON_ERROR_STOP=on

echo "[restore] running alembic upgrade head"
alembic upgrade head || {
    echo "[restore] alembic upgrade failed — investigate before serving traffic" >&2
    exit 1
}

echo "[restore] running deploy_check"
python -m app.scripts.deploy_check

echo "[restore] done"
