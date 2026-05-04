from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.jobs import get_registry
from app.models import Bank, ChatMessage, GenerationJob, User
from app.serialize import iso_z
from app.services import revision

router = APIRouter(tags=["chat"])


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatPostIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


async def _load_owned_job(
    job_id: str, user: User, session: AsyncSession
) -> GenerationJob:
    row = (
        await session.execute(
            select(GenerationJob)
            .join(Bank, Bank.id == GenerationJob.bank_id)
            .where(GenerationJob.id == job_id, Bank.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "generation not found")
    return row


@router.get("/api/generations/{job_id}/chat", response_model=list[ChatMessageOut])
async def list_messages(
    job_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ChatMessageOut]:
    await _load_owned_job(job_id, user, session)
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.job_id == job_id)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()
    return [
        ChatMessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=iso_z(m.created_at),
        )
        for m in rows
    ]


@router.post(
    "/api/generations/{job_id}/chat",
    response_model=ChatMessageOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_message(
    job_id: str,
    body: ChatPostIn,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatMessageOut:
    job = await _load_owned_job(job_id, user, session)
    if job.status != "done":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "wait for the current generation to finish before sending a revision message",
        )
    msg = ChatMessage(job_id=job.id, role="user", content=body.content.strip())
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    # Mark the job as running again so the watch UI shows progress.
    job.status = "running"
    job.error = None
    await session.commit()

    job_id_local = job.id
    msg_id = msg.id
    get_registry().spawn(
        lambda: revision.apply_revision(job_id_local, msg_id),
        label=f"revise.{job_id_local[:8]}",
    )

    return ChatMessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        created_at=iso_z(msg.created_at),
    )
