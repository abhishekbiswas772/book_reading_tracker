"""
Shared fixtures: a fresh in-memory SQLite DB per test, wired into the real
FastAPI app via a get_db_session dependency override, so tests never touch
the real reading_list.db (which is a process-lifetime singleton and can't
just be re-pointed at a test DB by re-instantiating DatabaseHandler).
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401  (registers Book on Base.metadata)
from app.db.config import Base, get_db_session
from main import app


@pytest_asyncio.fixture
async def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session_factory):
    async def override_get_db_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def raw_session(db_session_factory):
    """Direct DB session for tests that bypass the API to seed rows."""
    async with db_session_factory() as session:
        yield session
