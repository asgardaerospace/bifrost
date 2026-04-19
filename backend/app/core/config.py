from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    project_name: str = "Bifrost"
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(...)

    jwt_secret_key: str = Field(...)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # NoDecode prevents pydantic-settings from JSON-parsing the env value
    # so our @field_validator can split a plain comma-separated string.
    cors_origins: Annotated[List[str], NoDecode] = Field(default_factory=list)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
