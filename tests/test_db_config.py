"""
Exercises DatabaseHandler / get_db_session directly, since every other test
bypasses them entirely via the FastAPI dependency override (per design —
DatabaseHandler is a process-lifetime __new__ singleton that can't just be
re-pointed at a test DB).

This test forces the singleton's *first* (and only, for the process)
initialization to bind to an in-memory SQLite DB by monkeypatching the
settings it reads at construction time — so it, and main.py's lifespan
(exercised here too), never touch the real reading_list.db. No other test
in this suite ever constructs DatabaseHandler, so this ordering is safe
regardless of test execution order.
"""

import pytest

from app.config.config import Settings
from app.db.config import DatabaseHandler, get_db_session
from main import app, lifespan

pytestmark = pytest.mark.asyncio


async def test_database_handler_singleton_lifecycle(monkeypatch):
    memory_settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr("app.db.config.get_settings", lambda: memory_settings)

    handler_a = DatabaseHandler()
    handler_b = DatabaseHandler()
    assert handler_a is handler_b

    assert handler_a.engine is not None
    assert handler_a.session_factory is not None

    await handler_a.init_models()

    session_gen = get_db_session()
    session = await session_gen.__anext__()
    assert session is not None
    await session_gen.aclose()

    # Exercises main.py's lifespan context manager. DatabaseHandler is
    # already the memory-backed singleton above, so this stays off the
    # real DB file regardless of main.py's own default settings.
    async with lifespan(app):
        pass
