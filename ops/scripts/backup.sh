#!/usr/bin/env bash
# Bifrost — production backup script.
#
# Creates a compressed pg_dump of the configured database into BIFROST_BACKUP_DIR
# (default: ./var/backups). Tags the dump with timestamp + alembic head so the
# restore script can verify schema compatibility.
#
# Intended to run from cron / a backup pod. Uses DATABASE_URL from the
# environment so no secrets are baked into the script.

set -euo pipefail

BACKUP_DIR="${BIFROST_BACKUP_DIR:-./var/backups}"
RETENTION_DAYS="${BIFROST_BACKUP_RETENTION_DAYS:-14}"

if [ -z "${DATABASE_URL:-}" ]; then
    echo "[backup] DATABASE_URL not set" >&2
    exit 78
fi

mkdir -p "$BACKUP_DIR"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
head="$(python -c "
import os, sys
from sqlalchemy import create_engine, text
try:
    e = create_engine(os.environ['DATABASE_URL'])
    with e.connect() as c:
        r = c.execute(text('SELECT version_num FROM alembic_version')).first()
        sys.stdout.write(r[0] if r else 'unknown')
except Exception as exc:
    sys.stdout.write('unknown')
" 2>/dev/null)"

out="${BACKUP_DIR}/bifrost-${ts}-${head}.sql.gz"

echo "[backup] writing $out"
pg_dump "$DATABASE_URL" --no-owner --no-privileges --quote-all-identifiers \
    | gzip -9 > "$out"

bytes="$(wc -c <"$out")"
echo "[backup] wrote $bytes bytes"

# Retention sweep — keep the last RETENTION_DAYS.
find "$BACKUP_DIR" -maxdepth 1 -name 'bifrost-*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete \
    || true

echo "[backup] done"
