from __future__ import annotations

import httpx
import pytest


async def _login(client: httpx.AsyncClient, name: str) -> None:
    resp = await client.post("/api/auth/login", json={"username": name})
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_banks_require_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/banks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bank_crud_roundtrip(client: httpx.AsyncClient) -> None:
    await _login(client, "alice")

    # Empty initially.
    resp = await client.get("/api/banks")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create.
    resp = await client.post(
        "/api/banks",
        json={"name": "九年级数学", "description": "湖北中考真题样本"},
    )
    assert resp.status_code == 201, resp.text
    bank = resp.json()
    assert bank["name"] == "九年级数学"
    assert bank["analysis_status"] == "idle"
    bank_id = bank["id"]

    # List shows it.
    resp = await client.get("/api/banks")
    assert resp.status_code == 200
    listing = resp.json()
    assert len(listing) == 1
    assert listing[0]["id"] == bank_id

    # Get by id.
    resp = await client.get(f"/api/banks/{bank_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == bank_id

    # Delete.
    resp = await client.delete(f"/api/banks/{bank_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/banks/{bank_id}")
    assert resp.status_code == 404

    resp = await client.get("/api/banks")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_banks_isolated_between_users(client: httpx.AsyncClient) -> None:
    await _login(client, "alice")
    resp = await client.post("/api/banks", json={"name": "Alice bank"})
    assert resp.status_code == 201
    alice_bank_id = resp.json()["id"]

    # Switch to Bob.
    await client.post("/api/auth/logout")
    await _login(client, "bob")

    # Bob doesn't see Alice's banks.
    resp = await client.get("/api/banks")
    assert resp.json() == []

    # Bob can't fetch Alice's bank by id.
    resp = await client.get(f"/api/banks/{alice_bank_id}")
    assert resp.status_code == 404
