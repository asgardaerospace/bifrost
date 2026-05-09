"""Pre/post-deploy readiness check.

Runs:
  * env validation (delegates to validate_env)
  * database connectivity + migration head check (alembic)
  * basic schema sanity (key tables exist)
  * (optional) redis ping if REDIS_URL is set

Exits 0 only if everything is green. Intended to be called by CI before
flipping the load balancer or by an operator after a deploy.
"""

from __future__ import annotations

import os
import sys
from typing import List, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.scripts.validate_env import validate as validate_env

REQUIRED_TABLES = (
    "users",
    "missions",
    "execution_queue_items",
    "operational_events",
    "approvals",
)


def _check(name: str, ok: bool, hint: str = "") -> Tuple[str, bool, str]:
    return (name, ok, hint)


def run() -> List[Tuple[str, bool, str]]:
    results: List[Tuple[str, bool, str]] = list(validate_env())

    db_url = os.environ.get("DATABASE_URL", "")
    try:
        engine = create_engine(db_url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        results.append(_check("database connectivity", True))
        insp = inspect(engine)
        existing = set(insp.get_table_names())
        for tbl in REQUIRED_TABLES:
            results.append(_check(
                f"table:{tbl}",
                tbl in existing,
                f"run alembic upgrade head — table '{tbl}' missing",
            ))
        # Alembic head check.
        try:
            with engine.connect() as conn:
                row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
                results.append(_check("alembic_version", bool(row), "no alembic_version row — run alembic upgrade head"))
        except SQLAlchemyError as exc:
            results.append(_check("alembic_version", False, f"alembic_version table missing ({exc.__class__.__name__})"))
        engine.dispose()
    except SQLAlchemyError as exc:
        results.append(_check("database connectivity", False, str(exc).splitlines()[0]))

    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        try:
            import redis  # type: ignore[import-not-found]

            r = redis.from_url(redis_url, socket_timeout=3)
            r.ping()
            results.append(_check("redis connectivity", True))
        except Exception as exc:  # pragma: no cover -- network
            results.append(_check("redis connectivity", False, str(exc).splitlines()[0]))

    return results


def main() -> int:
    results = run()
    failed = [r for r in results if not r[1]]
    width = max((len(name) for name, _, _ in results), default=20)
    for name, ok, hint in results:
        flag = "OK " if ok else "FAIL"
        line = f"  [{flag}] {name.ljust(width)}"
        if not ok and hint:
            line = f"{line}  -> {hint}"
        print(line)
    if failed:
        print(f"\ndeploy check failed: {len(failed)} issue(s)", file=sys.stderr)
        return 1
    print("\ndeploy check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
