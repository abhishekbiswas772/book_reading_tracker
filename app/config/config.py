"""
Application-wide settings, loaded from environment variables / .env file.

ASSUMPTION: other engineers on this project will reuse this same Settings
object (via get_settings()) for their own modules (list/filter endpoints,
etc.), so values that are likely to be shared (DB URL, app name, port) live
here rather than being duplicated per-module.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration. Values can be overridden via env vars or a .env file."""

    app_name: str = "Reading List Tracker"
    app_version: str = "0.1.0"
    port: int = 8000
    host: str = "0.0.0.0"

    # ASSUMPTION: SQLite file lives at the project root as reading_list.db.
    # aiosqlite driver is required for the async SQLAlchemy engine.
    database_url: str = "sqlite+aiosqlite:///./reading_list.db"

    # Echo raw SQL statements to stdout — handy for local debugging.
    db_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Settings are cheap to build but we still cache a single instance per process."""
    return Settings()
