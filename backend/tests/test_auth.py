from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_login_me_logout_roundtrip(client: httpx.AsyncClient) -> None:
    # No session → /me is 401.
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401

    # Login as Alice → 200, sets cookie.
    resp = await client.post("/api/auth/login", json={"username": "alice"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"] == "alice"
    user_id = body["id"]
    assert "examcraft_session" in resp.cookies

    # /me with that session.
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"id": user_id, "username": "alice"}

    # Logging in again as Alice returns the same user.
    resp = await client.post("/api/auth/login", json={"username": "alice"})
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id

    # Logout clears the cookie; /me 401 again.
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_bad_username(client: httpx.AsyncClient) -> None:
    for bad in ["", "   ", "hi there", "a" * 64]:
        resp = await client.post("/api/auth/login", json={"username": bad})
        assert resp.status_code in {400, 422}, (bad, resp.status_code, resp.text)


@pytest.mark.asyncio
async def test_unknown_session_cookie_is_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/auth/me", cookies={"examcraft_session": "garbage-not-a-real-token"}
    )
    assert resp.status_code == 401
