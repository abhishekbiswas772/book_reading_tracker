"""
Database connection/engine/session management.

Exposes a singleton DatabaseHandler that owns the async SQLAlchemy engine
and session factory, plus a FastAPI dependency (get_db_session) that other
routers (list/filter, etc.) can reuse to get an AsyncSession.
"""

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (app/db/models.py)."""

    pass


class DatabaseHandler:
    """
    Singleton owner of the async engine + session factory.

    Kept as a singleton so every part of the app (this module, service
    layer, and later list/filter endpoints built by other engineers)
    shares one engine/connection pool instead of each creating its own.
    """

    class DatabaseHandlerException(Exception):
        """Raised when the database engine/session cannot be created or initialized."""

        pass

    _instance: Optional["DatabaseHandler"] = None

    def __new__(cls) -> "DatabaseHandler":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        try:
            settings = get_settings()
            self._engine: AsyncEngine = create_async_engine(
                settings.database_url,
                echo=settings.db_echo,
            )
            self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
                bind=self._engine,
                expire_on_commit=False,
                class_=AsyncSession,
            )
            self._initialized = True
        except Exception as exc:
            raise DatabaseHandler.DatabaseHandlerException(
                f"Failed to initialize database engine: {exc}"
            ) from exc

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def init_models(self) -> None:
        """Create all tables that don't exist yet. Called once at app startup."""
        try:
            # Import models here so Base.metadata is populated before create_all runs.
            from app.db import models  # noqa: F401

            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            raise DatabaseHandler.DatabaseHandlerException(
                f"Failed to initialize database schema: {exc}"
            ) from exc

    async def dispose(self) -> None:
        """Cleanly close the engine's connection pool on app shutdown."""
        try:
            await self._engine.dispose()
        except Exception as exc:
            raise DatabaseHandler.DatabaseHandlerException(
                f"Failed to dispose database engine: {exc}"
            ) from exc


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an AsyncSession.

    Importable by other routers (e.g. a future GET /books list/filter
    endpoint) so everyone shares the same session-creation logic.
    """
    session_factory = DatabaseHandler().session_factory
    async with session_factory() as session:
        yield session
