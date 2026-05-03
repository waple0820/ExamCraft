from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    USERNAME_RE,
    clear_session_cookie,
    current_user,
    issue_session_cookie,
)
from app.db import get_session
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)


class UserOut(BaseModel):
    id: str
    username: str


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserOut:
    if not USERNAME_RE.match(body.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid username")
    user = (
        await session.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if user is None:
        user = User(username=body.username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    issue_session_cookie(response, user.id)
    return UserOut(id=user.id, username=user.username)


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(current_user)]) -> UserOut:
    return UserOut(id=user.id, username=user.username)
