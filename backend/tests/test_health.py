from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["model"]
