"""Obsidian exporter configuration.

Loads from environment via pydantic-settings. Variables are prefixed
with ``OBSIDIAN_`` (e.g. ``OBSIDIAN_VAULT_ROOT``) so they don't collide
with the rest of Bifrost's settings.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObsidianExportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OBSIDIAN_",
        case_sensitive=False,
        extra="ignore",
    )

    vault_root: str = Field(...)
    export_enabled: bool = Field(default=False)
    batch_size: int = Field(default=500, ge=1, le=10_000)
    reconcile_enabled: bool = Field(default=False)


@lru_cache
def get_obsidian_settings() -> ObsidianExportSettings:
    return ObsidianExportSettings()
