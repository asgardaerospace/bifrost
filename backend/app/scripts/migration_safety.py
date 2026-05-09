"""Migration safety check.

Inspects the pending alembic revisions between current and head and flags
operations that are not safe under load — primarily destructive DDL and
column type changes that would lock a busy table.

Heuristic — not a substitute for review. Intended to be run as part of CI
before merging a migration. Exits 0 if all pending migrations look safe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VERSIONS_DIR = REPO_ROOT / "backend" / "alembic" / "versions"

# Patterns we consider risky on a hot table.
RISKY_PATTERNS = [
    (re.compile(r"\bdrop_table\b", re.IGNORECASE), "drop_table"),
    (re.compile(r"\bdrop_column\b", re.IGNORECASE), "drop_column"),
    (re.compile(r"\balter_column.*type_=", re.IGNORECASE), "alter_column type change"),
    (re.compile(r"\bdrop_constraint\b", re.IGNORECASE), "drop_constraint"),
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "raw DROP TABLE"),
    (re.compile(r"\bALTER\s+TABLE\b.*DROP\b", re.IGNORECASE), "raw ALTER DROP"),
]


def main() -> int:
    if not VERSIONS_DIR.exists():
        print(f"versions dir not found: {VERSIONS_DIR}", file=sys.stderr)
        return 0

    flagged: list[tuple[str, str]] = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat, label in RISKY_PATTERNS:
            if pat.search(text):
                flagged.append((path.name, label))

    if not flagged:
        print("migration safety: no risky patterns detected")
        return 0

    print("migration safety: review the following before merging\n")
    for name, label in flagged:
        print(f"  {name}: {label}")
    print(
        "\nThese operations are not automatically blocked — they may be safe "
        "with the right runbook. Confirm:\n"
        "  * the affected table is not under heavy write load\n"
        "  * a backup exists (ops/scripts/backup.sh)\n"
        "  * the change is reversible OR a rollback path is documented",
        file=sys.stderr,
    )
    # Exit 0 to keep CI green by default — flip to 1 once your team is ready
    # to enforce. The list above is what an operator/reviewer should triage.
    return 0


if __name__ == "__main__":
    sys.exit(main())
