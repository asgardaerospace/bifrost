"""Wait until the configured database is reachable, or fail with a timeout.

Bounded retry so a misconfigured DB doesn't keep the container in an infinite
restart loop without an obvious failure mode. The entrypoint calls this before
handing off to uvicorn.
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for the Bifrost database.")
    parser.add_argument("--timeout", type=int, default=60, help="seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between probes")
    args = parser.parse_args()

    settings = get_settings()
    deadline = time.monotonic() + args.timeout
    last_error: str = ""
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        try:
            engine = create_engine(settings.database_url, pool_pre_ping=False, future=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            print(f"[wait_for_db] reachable on attempt {attempt}", file=sys.stderr)
            return 0
        except SQLAlchemyError as exc:
            last_error = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            print(f"[wait_for_db] attempt {attempt} not ready: {last_error}", file=sys.stderr)
        time.sleep(args.interval)

    print(f"[wait_for_db] timed out after {args.timeout}s ({last_error})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
