from __future__ import annotations

import re
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User

# Cookie name is fixed (not env-configurable) so it can match the FastAPI
# `Cookie()` parameter name below.
SESSION_COOKIE_NAME = "examcraft_session"

# Allow letters, digits, CJK, dot/dash/underscore. 1-32 chars.
USERNAME_RE = re.compile(r"^[\w一-鿿][\w一-鿿\-\.]{0,31}$")


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="examcraft.session")


def issue_session_cookie(response: Response, user_id: str) -> None:
    settings = get_settings()
    token = _serializer().dumps({"uid": user_id})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_days * 86400,
        httponly=True,
        secure=False,  # localhost dev; flip when behind https
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    examcraft_session: Annotated[str | None, Cookie()] = None,
) -> User:
    if not examcraft_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no session")
    settings = get_settings()
    try:
        data = _serializer().loads(
            examcraft_session, max_age=settings.session_max_age_days * 86400
        )
    except SignatureExpired:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired") from None
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from None
    uid = data.get("uid") if isinstance(data, dict) else None
    if not uid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    user = (
        await session.execute(select(User).where(User.id == uid))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user
