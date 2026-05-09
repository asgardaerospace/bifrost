"""Environment validation — runs at boot, before the app touches the network.

Exits 0 if the configured environment is internally consistent; exits non-zero
with a human-readable report otherwise. Intended to be called from the
container entrypoint so a misconfigured deployment fails fast with a clear
message instead of running half-broken.

Doctrine: deterministic startup. We refuse to boot rather than degrade
silently in production.
"""

from __future__ import annotations

import os
import sys
from typing import List, Tuple


PROD_ENVS = {"production", "prod"}


def _check(name: str, ok: bool, hint: str) -> Tuple[str, bool, str]:
    return (name, ok, hint)


def validate() -> List[Tuple[str, bool, str]]:
    results: List[Tuple[str, bool, str]] = []

    env = os.environ.get("ENVIRONMENT", "development").lower()
    is_prod = env in PROD_ENVS

    db_url = os.environ.get("DATABASE_URL", "")
    results.append(_check(
        "DATABASE_URL",
        bool(db_url),
        "set DATABASE_URL to a SQLAlchemy URL (postgresql+psycopg://...)",
    ))
    if db_url:
        results.append(_check(
            "DATABASE_URL scheme",
            db_url.startswith(("postgresql", "postgres", "sqlite")),
            "must start with postgresql/postgres or sqlite",
        ))
        if is_prod:
            results.append(_check(
                "DATABASE_URL not sqlite (prod)",
                not db_url.startswith("sqlite"),
                "sqlite is not allowed in production",
            ))

    secret = os.environ.get("JWT_SECRET_KEY", "")
    results.append(_check(
        "JWT_SECRET_KEY present",
        bool(secret),
        "set JWT_SECRET_KEY to a long random value (>=32 chars)",
    ))
    if is_prod:
        results.append(_check(
            "JWT_SECRET_KEY strength (prod)",
            len(secret) >= 32 and secret not in {"change-me", "smoke-test-secret"},
            "JWT_SECRET_KEY must be >=32 chars and not a placeholder",
        ))

    cors = os.environ.get("CORS_ORIGINS", "")
    if is_prod:
        # In prod we want explicit origins, not wildcards.
        results.append(_check(
            "CORS_ORIGINS scope (prod)",
            "*" not in cors,
            "do not use '*' in CORS_ORIGINS in production",
        ))

    redis = os.environ.get("REDIS_URL", "")
    if redis:
        results.append(_check(
            "REDIS_URL scheme",
            redis.startswith(("redis://", "rediss://")),
            "REDIS_URL must start with redis:// or rediss://",
        ))

    enforce = os.environ.get("AUTH_ENFORCEMENT_ENABLED", "false").lower()
    results.append(_check(
        "AUTH_ENFORCEMENT_ENABLED valid",
        enforce in {"true", "false", "1", "0"},
        "must be true|false|1|0",
    ))

    return results


def main() -> int:
    results = validate()
    failed = [r for r in results if not r[1]]
    width = max((len(name) for name, _, _ in results), default=20)
    for name, ok, hint in results:
        flag = "OK " if ok else "FAIL"
        line = f"  [{flag}] {name.ljust(width)}"
        if not ok:
            line = f"{line}  -> {hint}"
        print(line)
    if failed:
        print(f"\nenvironment validation failed: {len(failed)} issue(s)", file=sys.stderr)
        return 1
    print("\nenvironment validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
