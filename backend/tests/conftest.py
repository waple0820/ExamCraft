from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest


@pytest.fixture
async def client(tmp_path, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    """Boot an isolated FastAPI app against a fresh tmp data dir + DB."""
    monkeypatch.setenv("EXAMCRAFT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EXAMCRAFT_SESSION_SECRET", "test-secret-not-for-prod")

    # Clear cached singletons so the test sees the patched env.
    from app import config, db

    config.reset_settings_cache()
    await db.reset_engine()

    from app.main import create_app

    app = create_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        async with app.router.lifespan_context(app):
            yield c

    await db.reset_engine()
    config.reset_settings_cache()
