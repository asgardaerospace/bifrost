"""Daily Intelligence Brief generator.

Built up in slices. Implemented so far:

    1. Vault scanner   — streaming, never loads bodies.
    2. Frontmatter parser — lightweight, no PyYAML dep.
    3. CLI ``list`` command — JSON Lines metadata stream.
    4. CLI ``compose`` command — builds the BriefInput JSON document.
    5. Prompt builder + Claude API call — deterministic config.
    6. Atomic brief writer + ``--dry-run`` / ``--print-prompt`` flags
       on the ``generate`` command.

Usage:
    python -m app.scripts.daily_brief list
    python -m app.scripts.daily_brief compose  [--date YYYY-MM-DD]
    python -m app.scripts.daily_brief prompt   [--date YYYY-MM-DD]
    python -m app.scripts.daily_brief generate [--date YYYY-MM-DD]
                                               [--model opus|sonnet|haiku|<full-id>]
                                               [--dry-run]
                                               [--print-prompt]
                                               [--verbose]

The ``generate`` command runs the full pipeline by default:
scan → compose → prompt → Claude → atomic write to
``Bifrost/Briefs/{YYYY}/{MM}/{date}-brief.md``.

    --dry-run       skip Claude + write; print FACTS JSON to stdout.
    --print-prompt  skip Claude + write; print system + user prompt
                    to stdout.
    --verbose       on a successful run, print model/hash/usage above
                    the written-path line.

Environment:
    OBSIDIAN_VAULT_ROOT  vault path for the scanner (or --vault-root).
    ANTHROPIC_API_KEY    required for a non-dry-run ``generate``.

Reconciler caveat:
    Brief filenames (``2026-05-01-brief.md``) don't match the
    Bifrost-note regex ``^[a-z]+-\\d+\\.md$``, so the read-only
    reconciler will list them under ``invalid_files``. They're
    user-facing artifacts, not exporter-tracked notes — the
    reconciler will be taught to skip ``Briefs/`` in a follow-up.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# layout
# ----------------------------------------------------------------------

_BIFROST_DIR = "Bifrost"

# Top-level subtrees under Bifrost/ that the scanner skips entirely.
# ``_meta/`` is the manifest's territory; ``_archive/`` holds soft-deleted
# notes (we don't want them in the daily brief); ``Briefs/`` is our
# own output, which would create a feedback loop.
_SKIP_TOP_LEVEL: frozenset[str] = frozenset({"_meta", "_archive", "Briefs"})


# ----------------------------------------------------------------------
# parsed shape
# ----------------------------------------------------------------------


@dataclass(slots=True)
class NoteMeta:
    """Metadata for one Bifrost-tracked note. No body content.

    Attributes:
        path: vault-relative path with forward slashes
              (e.g. ``Bifrost/Programs/program-1.md``).
        frontmatter: parsed YAML frontmatter as native Python types
                     (str, int, float, bool, None, datetime, list).
    """

    path: str
    frontmatter: dict[str, Any]


# ----------------------------------------------------------------------
# vault scanner — streaming
# ----------------------------------------------------------------------


def scan_vault(vault_root: str | Path) -> Iterator[NoteMeta]:
    """Yield :class:`NoteMeta` for every Bifrost-emitted note under
    ``{vault_root}/Bifrost/``.

    Streaming: each file is opened, frontmatter is read, body is
    discarded. Memory stays bounded by the size of one frontmatter
    block — safe at 100k+ files.

    Skips ``_meta/``, ``_archive/``, ``Briefs/`` subtrees. Silently
    drops any .md file whose frontmatter is missing or whose
    ``bifrost_id`` isn't an integer (i.e. anything not produced by
    the exporter).
    """
    vault = Path(vault_root)
    bifrost = vault / _BIFROST_DIR
    if not bifrost.is_dir():
        return

    for path in bifrost.rglob("*.md"):
        try:
            rel_parts = path.relative_to(bifrost).parts
        except ValueError:
            continue
        if not rel_parts or rel_parts[0] in _SKIP_TOP_LEVEL:
            continue

        try:
            fm = parse_frontmatter(path)
        except OSError as exc:
            logger.warning("could not read %s: %s", path, exc)
            continue

        if fm is None:
            continue
        if not isinstance(fm.get("bifrost_id"), int):
            # Has frontmatter but isn't a Bifrost-tracked note.
            continue

        rel = path.relative_to(vault).as_posix()
        yield NoteMeta(path=rel, frontmatter=fm)


# ----------------------------------------------------------------------
# lightweight frontmatter parser
# ----------------------------------------------------------------------


def parse_frontmatter(path: Path) -> Optional[dict[str, Any]]:
    """Read and parse the YAML frontmatter block at ``path``.

    Returns ``None`` if the file does not begin with ``---`` or if the
    closing ``---`` is missing. Reads only as far as the closing
    delimiter — never loads the body. This is the streaming primitive
    that lets the scanner walk huge vaults without exploding memory.
    """
    lines: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        first = fh.readline()
        if first.rstrip("\r\n") != "---":
            return None
        for raw in fh:
            line = raw.rstrip("\r\n")
            if line == "---":
                return _parse_simple_yaml(lines)
            lines.append(line)
    # EOF without a closing fence — malformed file, skip.
    return None


# Keys we emit are ASCII identifiers; this regex is intentionally
# strict so an in-body ``Title:`` paragraph can't masquerade as
# frontmatter (the parser only ever sees frontmatter, but defensive).
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_LIST_ITEM_PREFIX = "  - "


def _parse_simple_yaml(lines: list[str]) -> dict[str, Any]:
    """Parse the YAML subset the Obsidian exporter emits.

    Supports:
        * ``key: scalar`` where scalar is one of:
              null, true, false, "double-quoted string",
              integer, float, ISO-8601 datetime, bare string
        * ``key: []``                          (empty list)
        * ``key:`` then ``  - scalar`` lines   (list)

    Anything more elaborate (anchors, multi-line strings, nested
    mappings) is intentionally not supported — the exporter never
    produces those shapes. Unrecognized lines are skipped, not raised
    on, so a single hand-edit can't take down the brief generator.
    """
    result: dict[str, Any] = {}
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        match = _KEY_RE.match(line)
        if match is None:
            i += 1
            continue

        key = match.group(1)
        rest = match.group(2).rstrip()

        if rest == "":
            # A multi-line list follows.
            items: list[Any] = []
            i += 1
            while i < n and lines[i].startswith(_LIST_ITEM_PREFIX):
                items.append(
                    _parse_scalar(lines[i][len(_LIST_ITEM_PREFIX):].strip())
                )
                i += 1
            result[key] = items
            continue

        if rest == "[]":
            result[key] = []
            i += 1
            continue

        result[key] = _parse_scalar(rest)
        i += 1
    return result


def _parse_scalar(raw: str) -> Any:
    if raw == "null":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False

    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return _unquote_yaml_string(raw[1:-1])

    dt = _try_iso_datetime(raw)
    if dt is not None:
        return dt

    if _INT_RE.match(raw):
        try:
            return int(raw)
        except ValueError:
            pass
    if _FLOAT_RE.match(raw):
        try:
            return float(raw)
        except ValueError:
            pass

    # Fall back to bare string — should be rare in exporter output
    # since the exporter quotes every string field on purpose.
    return raw


def _unquote_yaml_string(value: str) -> str:
    """Reverse the exporter's escaping: ``\\\\`` first, then ``\\"``."""
    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 1 < n:
            nxt = value[i + 1]
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            if nxt == '"':
                out.append('"')
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _try_iso_datetime(value: str) -> Optional[datetime]:
    # Cheap pre-check so we don't fromisoformat() every bare string.
    if len(value) < 10 or value[4] != "-" or value[7] != "-":
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ----------------------------------------------------------------------
# brief-input composition
# ----------------------------------------------------------------------


# Tunable thresholds. Kept as module constants so the brief is
# reproducible run-over-run; bumping a threshold is a single-line edit.
_RECENT_DAYS = 14
_INTEL_RELEVANCE_MIN = 70
_LOW_PROBABILITY_THRESHOLD = 30
_ACTIVE_STAGES: frozenset[str] = frozenset({"pursuing", "active"})
_HEALTHY_ONBOARDING: frozenset[str] = frozenset({"qualified", "onboarded"})


def build_brief_input(
    notes: list[NoteMeta],
    *,
    today: date,
) -> dict[str, Any]:
    """Assemble the deterministic BriefInput document.

    The output is a single JSON-serializable dict with six top-level
    keys mirroring the brief's six sections: ``programs``,
    ``investor_activity``, ``supplier_activity``, ``intel``,
    ``risks``, plus ``today``/``windows``/``counts`` metadata.

    All entity references use stable ``{prefix}-{id}`` strings so the
    downstream Claude call can cite them inline.
    """
    cutoff = datetime.combine(today, time.min, tzinfo=timezone.utc) - timedelta(
        days=_RECENT_DAYS
    )

    by_type = _group_by_type(notes)
    children_by_parent = _index_polymorphic_children(by_type, cutoff)

    programs = _build_programs(
        by_type.get("program", []), children_by_parent, cutoff
    )
    investor_activity = _build_investor_activity(
        by_type.get("investor_firm", []), children_by_parent
    )
    supplier_activity = _build_supplier_activity(
        by_type.get("supplier", []), children_by_parent, cutoff
    )
    intel = _build_intel(by_type.get("intel_item", []), cutoff)
    risks = _derive_risks(programs, supplier_activity)

    return {
        "today": today.isoformat(),
        "windows": {
            "recent_days": _RECENT_DAYS,
            "intel_relevance_min": _INTEL_RELEVANCE_MIN,
            "low_probability_threshold": _LOW_PROBABILITY_THRESHOLD,
        },
        "counts": {
            bt: len(items) for bt, items in sorted(by_type.items())
        },
        "programs": programs,
        "investor_activity": investor_activity,
        "supplier_activity": supplier_activity,
        "intel": intel,
        "risks": risks,
    }


# ----------------------------------------------------------------------
# grouping + indexing
# ----------------------------------------------------------------------


def _group_by_type(
    notes: list[NoteMeta],
) -> dict[str, list[NoteMeta]]:
    out: dict[str, list[NoteMeta]] = defaultdict(list)
    for n in notes:
        bt = n.frontmatter.get("bifrost_type")
        if isinstance(bt, str):
            out[bt].append(n)
    # Stable per-type ordering by id keeps the brief deterministic.
    for items in out.values():
        items.sort(
            key=lambda meta: (
                meta.frontmatter.get("bifrost_id")
                if isinstance(meta.frontmatter.get("bifrost_id"), int)
                else -1
            )
        )
    return out


def _index_polymorphic_children(
    by_type: dict[str, list[NoteMeta]],
    cutoff: datetime,
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """Group polymorphic children (notes/meetings/comms) by their parent.

    Only includes children whose effective timestamp is at or after
    ``cutoff``. Effective timestamp is the most-recent contentful one:
    ``starts_at`` for meetings, ``sent_at`` for communications,
    ``created_at`` otherwise — falling back to ``created_at`` if the
    primary is null.
    """
    out: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)

    for child_type in ("note", "meeting", "communication"):
        for n in by_type.get(child_type, []):
            fm = n.frontmatter
            parent_type = fm.get("parent_type")
            parent_id = fm.get("parent_id")
            if not isinstance(parent_type, str) or not isinstance(parent_id, int):
                continue

            when = _child_timestamp(child_type, fm)
            if when is None or _ensure_aware(when) < cutoff:
                continue

            kind = "comm" if child_type == "communication" else child_type
            ref = f"{kind}-{fm.get('bifrost_id')}"
            out[(parent_type, parent_id)].append(
                {
                    "ref": ref,
                    "kind": kind,
                    "title": fm.get("title"),
                    "when": _to_iso(when),
                }
            )

    # Newest first within each parent, with kind+id as deterministic
    # tiebreaker (Python's sort is stable, so two passes give the
    # right ordering with mixed-type collections).
    for items in out.values():
        items.sort(key=lambda x: (x["kind"], x["ref"]))
        items.sort(key=lambda x: x["when"] or "", reverse=True)
    return out


def _child_timestamp(child_type: str, fm: dict[str, Any]) -> Optional[datetime]:
    candidates: tuple[str, ...]
    if child_type == "meeting":
        candidates = ("starts_at", "created_at")
    elif child_type == "communication":
        candidates = ("sent_at", "created_at")
    else:
        candidates = ("created_at",)
    for key in candidates:
        value = fm.get(key)
        if isinstance(value, datetime):
            return value
    return None


# ----------------------------------------------------------------------
# section builders
# ----------------------------------------------------------------------


def _build_programs(
    program_notes: list[NoteMeta],
    children_by_parent: dict[tuple[str, int], list[dict[str, Any]]],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in program_notes:
        fm = n.frontmatter
        program_id = fm.get("bifrost_id")
        if not isinstance(program_id, int):
            continue
        updated_at = fm.get("updated_at")
        stage = fm.get("stage")
        recent = children_by_parent.get(("program", program_id), [])
        out.append(
            {
                "ref": f"program-{program_id}",
                "title": fm.get("title"),
                "stage": stage,
                "owner": fm.get("owner"),
                "next_step": fm.get("next_step"),
                "probability_score": fm.get("probability_score"),
                "strategic_value_score": fm.get("strategic_value_score"),
                "estimated_value": fm.get("estimated_value"),
                "account": fm.get("account"),
                "account_id": fm.get("account_id"),
                "accounts_count": fm.get("accounts_count"),
                "investors_count": fm.get("investors_count"),
                "suppliers_count": fm.get("suppliers_count"),
                "updated_at": _to_iso(updated_at),
                "stale": _is_stale(updated_at, stage, cutoff),
                "recent_activity_count": len(recent),
                "recent_activity": recent,
            }
        )
    out.sort(key=lambda p: p["updated_at"] or "", reverse=True)
    return out


def _build_investor_activity(
    firm_notes: list[NoteMeta],
    children_by_parent: dict[tuple[str, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Firms with at least one direct child (note/meeting/comm) inside
    the recent window.

    Note: in the current vault, polymorphic notes are typically
    attached at ``entity_type='investor_opportunity'`` rather than
    directly to firms. Without an opportunity-level transformer to
    bridge them, those don't surface here. This is correct: the brief
    is sourced from vault data alone, so the gap is honest.
    """
    out: list[dict[str, Any]] = []
    for n in firm_notes:
        fm = n.frontmatter
        firm_id = fm.get("bifrost_id")
        if not isinstance(firm_id, int):
            continue
        recent = children_by_parent.get(("investor_firm", firm_id), [])
        if not recent:
            continue
        out.append(
            {
                "ref": f"firm-{firm_id}",
                "name": fm.get("title"),
                "stage_focus": fm.get("stage_focus"),
                "location": fm.get("location"),
                "contacts_count": fm.get("contacts_count"),
                "opportunities_count": fm.get("opportunities_count"),
                "recent_activity": recent,
            }
        )
    out.sort(key=_recent_activity_sort_key, reverse=True)
    return out


def _build_supplier_activity(
    supplier_notes: list[NoteMeta],
    children_by_parent: dict[tuple[str, int], list[dict[str, Any]]],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    """Suppliers updated in the recent window OR with direct child
    activity OR engaged in at least one program.

    The "engaged in a program" branch is the loosest of the three —
    a supplier with no recent updates but tied to an active program
    is still relevant context for the brief.
    """
    out: list[dict[str, Any]] = []
    for n in supplier_notes:
        fm = n.frontmatter
        supplier_id = fm.get("bifrost_id")
        if not isinstance(supplier_id, int):
            continue
        updated_at = fm.get("updated_at")
        recent_updated = (
            isinstance(updated_at, datetime)
            and _ensure_aware(updated_at) >= cutoff
        )
        recent = children_by_parent.get(("supplier", supplier_id), [])
        engaged = isinstance(fm.get("programs_count"), int) and fm["programs_count"] > 0
        if not (recent_updated or recent or engaged):
            continue
        out.append(
            {
                "ref": f"supplier-{supplier_id}",
                "name": fm.get("title"),
                "supplier_type": fm.get("supplier_type"),
                "region": fm.get("region"),
                "country": fm.get("country"),
                "onboarding_status": fm.get("onboarding_status"),
                "preferred_partner_score": fm.get("preferred_partner_score"),
                "capabilities_count": fm.get("capabilities_count"),
                "certifications_count": fm.get("certifications_count"),
                "programs_count": fm.get("programs_count"),
                "updated_at": _to_iso(updated_at),
                "recent_activity": recent,
            }
        )
    out.sort(key=_recent_activity_sort_key, reverse=True)
    return out


def _build_intel(
    intel_notes: list[NoteMeta],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    """Intel items with relevance ≥ threshold AND published in window."""
    out: list[dict[str, Any]] = []
    for n in intel_notes:
        fm = n.frontmatter
        intel_id = fm.get("bifrost_id")
        if not isinstance(intel_id, int):
            continue
        relevance = fm.get("relevance_score")
        if not isinstance(relevance, (int, float)) or relevance < _INTEL_RELEVANCE_MIN:
            continue
        published_at = fm.get("published_at")
        if not isinstance(published_at, datetime):
            continue
        if _ensure_aware(published_at) < cutoff:
            continue
        out.append(
            {
                "ref": f"intel-{intel_id}",
                "title": fm.get("title"),
                "source_name": fm.get("source_name"),
                "category": fm.get("category"),
                "relevance_score": relevance,
                "published_at": _to_iso(published_at),
                "url": fm.get("source_url_external"),
                "intel_status": fm.get("intel_status"),
                "entities_count": fm.get("entities_count"),
                "actions_count": fm.get("actions_count"),
            }
        )
    # Highest relevance first; tie-break by most recent.
    out.sort(
        key=lambda i: (
            -(i["relevance_score"] or 0),
            -(_iso_sort_key(i["published_at"])),
        )
    )
    return out


# ----------------------------------------------------------------------
# risk derivation
# ----------------------------------------------------------------------


def _derive_risks(
    programs: list[dict[str, Any]],
    supplier_activity: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """All four risk categories are pure derivations from the section
    output, so the brief can audit which entity drove which flag.
    """
    stalled = [p["ref"] for p in programs if p.get("stale")]

    missing_next_step = [
        p["ref"]
        for p in programs
        if not _is_truthy_string(p.get("next_step"))
        and p.get("stage") in _ACTIVE_STAGES
    ]

    low_probability = [
        p["ref"]
        for p in programs
        if isinstance(p.get("probability_score"), (int, float))
        and p["probability_score"] < _LOW_PROBABILITY_THRESHOLD
        and p.get("stage") in _ACTIVE_STAGES
    ]

    supplier_risks = [
        s["ref"]
        for s in supplier_activity
        if (s.get("onboarding_status") or "")
        not in _HEALTHY_ONBOARDING
        and (s.get("programs_count") or 0) > 0
    ]

    return {
        "stalled_programs": sorted(stalled),
        "missing_next_step": sorted(missing_next_step),
        "low_probability_deals": sorted(low_probability),
        "supplier_risks": sorted(supplier_risks),
    }


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _is_stale(updated_at: Any, stage: Any, cutoff: datetime) -> bool:
    """Stale = active-stage program whose updated_at is older than
    the recency cutoff (or has no timestamp at all)."""
    if not isinstance(stage, str) or stage not in _ACTIVE_STAGES:
        return False
    if not isinstance(updated_at, datetime):
        return True
    return _ensure_aware(updated_at) < cutoff


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_truthy_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        s = _ensure_aware(value).isoformat()
        return s[:-6] + "Z" if s.endswith("+00:00") else s
    if isinstance(value, str):
        return value
    return None


def _iso_sort_key(value: Optional[str]) -> float:
    """Numeric sort key for ISO timestamps — used so we can sort
    descending via negation in tuple keys."""
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _recent_activity_sort_key(item: dict[str, Any]) -> str:
    activity = item.get("recent_activity") or []
    if not activity:
        return ""
    # Items already sorted newest-first within the index, so the
    # head is the most recent.
    return activity[0].get("when") or ""


# ----------------------------------------------------------------------
# deterministic config — single source of truth for the API call
# ----------------------------------------------------------------------


# Bump when the system prompt or any output-shaping rule changes.
# Embedded in the brief frontmatter (slice 4) so old briefs can be
# distinguished from new ones at audit time.
SYSTEM_PROMPT_VERSION = 1

# Default model. Operator can override per-run with --model. The
# aliases below are convenience shorthands; full model ids also work.
DEFAULT_MODEL = "claude-opus-4-7"

_MODEL_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# Generation parameters. ``temperature=0`` is what makes the brief
# deterministic for a given input — same FACTS in, same markdown out.
MAX_TOKENS = 4096
TEMPERATURE = 0


SYSTEM_PROMPT = """You write daily intelligence briefs for an aerospace executive at Asgard Aerospace.

# Rules
1. Use ONLY facts present in the FACTS block. Do not invent names, numbers, dates, or relationships. If a fact isn't in FACTS, you don't know it.
2. Every bullet ends with one or more entity citations in square brackets, e.g. "[program-1]" or "[firm-3, intel-2]". Place the citation at the END of the bullet, not inline within prose.
3. If a section has no qualifying facts, output exactly "_(no items)_" as a single line beneath the heading. Do not invent filler bullets.
4. Bullets are at most 2 sentences each. Each section has at most 6 bullets.
5. The "Recommended Actions" section contains 3-7 bullets. Each must (a) cite at least one fact and (b) propose a concrete next step (e.g. "Send updated SOW to [account-1] by Friday"). Do not produce vague advice ("monitor the situation", "consider follow-up").
6. Output ONLY the markdown brief — start with the H1, end with the last bullet of section 6. No preamble, no postamble, no code fences.

# Template (substitute {today} verbatim)
# Asgard Daily Brief – {today}

## 1. Program Updates

## 2. Investor Activity

## 3. Supplier Activity

## 4. External Intelligence

## 5. Risks & Flags

## 6. Recommended Actions
"""


# ----------------------------------------------------------------------
# prompt builder
# ----------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class PromptPair:
    """The two messages the API call needs, plus a content hash that
    identifies the input deterministically (independent of when it
    was generated)."""

    system: str
    user: str
    input_hash: str


def build_prompt(brief_input: dict[str, Any]) -> PromptPair:
    """Render the BriefInput dict into a system+user prompt pair.

    The user message is structured as: a one-line ``Today:`` header,
    a compact JSON dump of FACTS, and a single instruction to write
    the brief. Compact JSON (no whitespace) keeps token usage tight
    and removes a source of cosmetic non-determinism.

    ``input_hash`` is sha256 over the canonical FACTS JSON. Same
    facts → same hash → same brief, regardless of when run.
    """
    facts_json = json.dumps(
        brief_input,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )
    digest = hashlib.sha256(facts_json.encode("utf-8")).hexdigest()
    input_hash = f"sha256:{digest}"

    today = brief_input.get("today", "")
    user_message = (
        f"Today: {today}\n\n"
        f"FACTS (JSON):\n{facts_json}\n\n"
        "Write the brief now."
    )
    return PromptPair(
        system=SYSTEM_PROMPT,
        user=user_message,
        input_hash=input_hash,
    )


# ----------------------------------------------------------------------
# Claude API call
# ----------------------------------------------------------------------


@dataclass(slots=True)
class BriefResult:
    """Outcome of a successful Claude call."""

    markdown: str
    model: str
    input_hash: str
    system_prompt_version: int
    usage: dict[str, int] = field(default_factory=dict)


def call_claude(
    prompt_pair: PromptPair,
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> BriefResult:
    """Call the Anthropic API once, return the brief markdown.

    Failure modes — each raises a clear ``RuntimeError`` so the CLI
    can map to exit code 2:
        * ``anthropic`` SDK not installed
        * ``ANTHROPIC_API_KEY`` neither passed nor in env
        * API call returns a non-text response

    Prompt caching: ``cache_control: ephemeral`` is set on the system
    block. The current SYSTEM_PROMPT is below the cacheable token
    threshold so the header is effectively a no-op today, but it's
    free to include and will activate automatically once the prompt
    grows past the threshold.
    """
    resolved_model = _MODEL_ALIASES.get(model, model)

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it or pass --api-key."
        )

    try:
        # Lazy import — keeps the rest of the script usable in
        # environments that don't have anthropic installed.
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK not installed. Run: pip install anthropic"
        ) from exc

    client = Anthropic(api_key=key)
    response = client.messages.create(
        model=resolved_model,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=[
            {
                "type": "text",
                "text": prompt_pair.system,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[
            {"role": "user", "content": prompt_pair.user},
        ],
    )

    markdown = _extract_text(response)
    if not markdown.strip():
        raise RuntimeError(
            "Anthropic returned an empty response — refusing to proceed."
        )

    return BriefResult(
        markdown=markdown,
        model=resolved_model,
        input_hash=prompt_pair.input_hash,
        system_prompt_version=SYSTEM_PROMPT_VERSION,
        usage=_extract_usage(response),
    )


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", None) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    fields = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    out: dict[str, int] = {}
    for f in fields:
        value = getattr(usage, f, None)
        if isinstance(value, int):
            out[f] = value
    return out


# ----------------------------------------------------------------------
# atomic writer
# ----------------------------------------------------------------------


_BRIEFS_FOLDER = "Briefs"


def write_brief(
    vault_root: str | Path,
    *,
    brief_date: date,
    result: BriefResult,
    brief_input: dict[str, Any],
) -> Path:
    """Atomically write the brief markdown to the dated path under
    ``{vault_root}/Bifrost/Briefs/{YYYY}/{MM}/{date}-brief.md``.

    Atomicity: write to ``.tmp`` in the destination directory, fsync
    the file, ``os.replace`` it over the target. A crash mid-write
    leaves either the old file or the new one — never a partial.

    Re-running on the same date overwrites cleanly. With
    ``temperature=0`` and a stable input the FACTS hash + Claude
    output are identical across runs, so overwrites are byte-for-byte
    no-ops in practice.

    Returns the absolute path of the written file.
    """
    vault = Path(vault_root)
    folder = (
        vault
        / "Bifrost"
        / _BRIEFS_FOLDER
        / f"{brief_date.year:04d}"
        / f"{brief_date.month:02d}"
    )
    target = folder / f"{brief_date.isoformat()}-brief.md"

    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"failed to create brief directory {folder}: {exc}"
        ) from exc

    text = _format_brief_file(
        brief_date=brief_date, result=result, brief_input=brief_input
    )
    payload = text.encode("utf-8")

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(folder),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)
    except OSError as exc:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise RuntimeError(f"failed to write brief: {exc}") from exc

    return target


def _format_brief_file(
    *,
    brief_date: date,
    result: BriefResult,
    brief_input: dict[str, Any],
) -> str:
    counts = {
        "programs": len(brief_input.get("programs") or []),
        "investor_activity": len(brief_input.get("investor_activity") or []),
        "supplier_activity": len(brief_input.get("supplier_activity") or []),
        "intel": len(brief_input.get("intel") or []),
        "risks": sum(
            len(v) for v in (brief_input.get("risks") or {}).values()
        ),
    }

    fm_lines: list[str] = ["---"]
    fm_lines.append(f'type: "asgard_brief"')
    fm_lines.append(f"brief_date: {brief_date.isoformat()}")
    fm_lines.append(f"generated_at: {_to_iso(datetime.now(timezone.utc))}")
    fm_lines.append(f"model: {_yaml_quote(result.model)}")
    fm_lines.append(f"system_prompt_version: {result.system_prompt_version}")
    fm_lines.append(f"input_hash: {_yaml_quote(result.input_hash)}")
    fm_lines.append("input_counts:")
    for key in (
        "programs",
        "investor_activity",
        "supplier_activity",
        "intel",
        "risks",
    ):
        fm_lines.append(f"  {key}: {counts[key]}")
    if result.usage:
        fm_lines.append("usage:")
        for key in sorted(result.usage):
            fm_lines.append(f"  {key}: {result.usage[key]}")
    fm_lines.append("---")

    body = (result.markdown or "").rstrip() + "\n"
    return "\n".join(fm_lines) + "\n\n" + body


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily_brief",
        description="Daily Intelligence Brief generator.",
    )
    parser.add_argument(
        "--vault-root",
        type=str,
        default=None,
        help="Vault path; defaults to OBSIDIAN_VAULT_ROOT from settings.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "list",
        help="Stream Bifrost-tracked note metadata as JSON Lines.",
    )

    compose = sub.add_parser(
        "compose",
        help="Build the BriefInput JSON document.",
    )
    compose.add_argument(
        "--date",
        type=str,
        default=None,
        help="Brief date YYYY-MM-DD (default: today UTC).",
    )

    prompt_cmd = sub.add_parser(
        "prompt",
        help="Print the system + user prompt without calling the API.",
    )
    prompt_cmd.add_argument("--date", type=str, default=None)

    generate = sub.add_parser(
        "generate",
        help=(
            "Full pipeline: scan + compose + prompt + Claude + atomic write."
        ),
    )
    generate.add_argument("--date", type=str, default=None)
    generate.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=(
            "Model id or alias. Aliases: opus, sonnet, haiku. "
            f"Default: {DEFAULT_MODEL}."
        ),
    )
    generate.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Claude and write; print the FACTS JSON and exit 0.",
    )
    generate.add_argument(
        "--print-prompt",
        action="store_true",
        help="Skip Claude and write; print system + user prompt and exit 0.",
    )
    generate.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "On a successful run, print model/hash/usage above the "
            "written-path line."
        ),
    )
    return parser


def _parse_brief_date(value: Optional[str]) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"invalid --date {value!r}: {exc}")


def _resolve_vault_root(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    # Lazy import — keeps the module usable in environments that
    # don't have the exporter's pydantic settings configured.
    from app.exporters.obsidian.config import get_obsidian_settings
    return get_obsidian_settings().vault_root


def _serialize(meta: NoteMeta) -> dict[str, Any]:
    return {"path": meta.path, "frontmatter": meta.frontmatter}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        s = value.isoformat()
        return s[:-6] + "Z" if s.endswith("+00:00") else s
    raise TypeError(f"unserializable type: {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        vault_root = _resolve_vault_root(args.vault_root)
    except Exception as exc:  # noqa: BLE001
        print(f"aborted: cannot resolve vault root: {exc}", file=sys.stderr)
        return 2

    if args.command == "list":
        count = 0
        for meta in scan_vault(vault_root):
            print(
                json.dumps(
                    _serialize(meta),
                    default=_json_default,
                    sort_keys=True,
                )
            )
            count += 1
        logger.info("scanned %d note(s)", count)
        return 0

    if args.command == "compose":
        today = _parse_brief_date(args.date)
        notes = list(scan_vault(vault_root))
        payload = build_brief_input(notes, today=today)
        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                default=_json_default,
            )
        )
        logger.info(
            "composed brief input for %s (programs=%d, intel=%d, risks=%d)",
            today.isoformat(),
            len(payload["programs"]),
            len(payload["intel"]),
            sum(len(v) for v in payload["risks"].values()),
        )
        return 0

    if args.command == "prompt":
        today = _parse_brief_date(args.date)
        notes = list(scan_vault(vault_root))
        payload = build_brief_input(notes, today=today)
        prompt_pair = build_prompt(payload)
        print("=== input_hash ===")
        print(prompt_pair.input_hash)
        print("=== system ===")
        print(prompt_pair.system)
        print("=== user ===")
        print(prompt_pair.user)
        return 0

    if args.command == "generate":
        today = _parse_brief_date(args.date)
        notes = list(scan_vault(vault_root))
        payload = build_brief_input(notes, today=today)

        # ``--dry-run`` short-circuits before the API call AND before
        # any write. Useful for verifying filter rules / FACTS shape
        # without burning Anthropic credits or touching the vault.
        if args.dry_run and not args.print_prompt:
            print(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                    default=_json_default,
                )
            )
            return 0

        prompt_pair = build_prompt(payload)

        # ``--print-prompt`` short-circuits with the resolved
        # system+user pair. Use this when iterating on prompt rules.
        if args.print_prompt:
            print("=== input_hash ===")
            print(prompt_pair.input_hash)
            print("=== system ===")
            print(prompt_pair.system)
            print("=== user ===")
            print(prompt_pair.user)
            return 0

        try:
            result = call_claude(prompt_pair, model=args.model)
        except RuntimeError as exc:
            print(f"aborted: {exc}", file=sys.stderr)
            return 2

        try:
            written = write_brief(
                vault_root,
                brief_date=today,
                result=result,
                brief_input=payload,
            )
        except RuntimeError as exc:
            print(f"aborted: {exc}", file=sys.stderr)
            return 2

        if args.verbose:
            print(f"=== model: {result.model}")
            print(f"=== input_hash: {result.input_hash}")
            print(
                f"=== system_prompt_version: {result.system_prompt_version}"
            )
            print(f"=== usage: {json.dumps(result.usage, sort_keys=True)}")
        print(f"wrote {written}")
        return 0

    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
