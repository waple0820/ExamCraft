from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.jobs import get_registry
from app.models import Bank, GenerationJob, User
from app.services import generation
from app.sse import encode_sse, get_bus

router = APIRouter(tags=["generations"])


class GenerationOut(BaseModel):
    id: str
    bank_id: str
    status: str
    progress_pct: float
    current_step: str | None
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    spec: dict[str, Any] | None


class GenerationSummary(BaseModel):
    id: str
    bank_id: str
    status: str
    progress_pct: float
    created_at: str
    finished_at: str | None


async def _ensure_bank_owned(
    bank_id: str, user: User, session: AsyncSession
) -> Bank:
    bank = (
        await session.execute(
            select(Bank).where(Bank.id == bank_id, Bank.user_id == user.id)
        )
    ).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bank not found")
    return bank


async def _load_owned_job(
    job_id: str, user: User, session: AsyncSession
) -> tuple[GenerationJob, Bank]:
    row = (
        await session.execute(
            select(GenerationJob, Bank)
            .join(Bank, Bank.id == GenerationJob.bank_id)
            .where(GenerationJob.id == job_id, Bank.user_id == user.id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "generation not found")
    return row[0], row[1]


def _serialize_job(job: GenerationJob) -> GenerationOut:
    spec = None
    if job.spec_json:
        try:
            spec = json.loads(job.spec_json)
        except json.JSONDecodeError:
            spec = {"_raw": job.spec_json}
    return GenerationOut(
        id=job.id,
        bank_id=job.bank_id,
        status=job.status,
        progress_pct=job.progress_pct,
        current_step=job.current_step,
        error=job.error,
        created_at=job.created_at.isoformat() if job.created_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        spec=spec,
    )


@router.post(
    "/api/banks/{bank_id}/generations",
    response_model=GenerationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def start_generation(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GenerationSummary:
    bank = await _ensure_bank_owned(bank_id, user, session)
    if not bank.analysis_json or bank.analysis_status != "done":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "bank profile is not ready — finish analyzing samples and aggregating first",
        )
    job = GenerationJob(bank_id=bank.id, status="queued", progress_pct=0.0)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    job_id = job.id
    get_registry().spawn(
        lambda: generation.run_generation(job_id),
        label=f"generate.{job_id[:8]}",
    )

    return GenerationSummary(
        id=job.id,
        bank_id=job.bank_id,
        status=job.status,
        progress_pct=job.progress_pct,
        created_at=job.created_at.isoformat() if job.created_at else "",
        finished_at=None,
    )


@router.get("/api/banks/{bank_id}/generations", response_model=list[GenerationSummary])
async def list_generations(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[GenerationSummary]:
    await _ensure_bank_owned(bank_id, user, session)
    rows = (
        await session.execute(
            select(GenerationJob)
            .where(GenerationJob.bank_id == bank_id)
            .order_by(desc(GenerationJob.created_at))
        )
    ).scalars().all()
    return [
        GenerationSummary(
            id=j.id,
            bank_id=j.bank_id,
            status=j.status,
            progress_pct=j.progress_pct,
            created_at=j.created_at.isoformat() if j.created_at else "",
            finished_at=j.finished_at.isoformat() if j.finished_at else None,
        )
        for j in rows
    ]


@router.get("/api/generations/{job_id}", response_model=GenerationOut)
async def get_generation(
    job_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GenerationOut:
    job, _ = await _load_owned_job(job_id, user, session)
    return _serialize_job(job)


@router.delete("/api/generations/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generation(
    job_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    job, _ = await _load_owned_job(job_id, user, session)
    await session.delete(job)
    await session.commit()


@router.get("/api/generations/{job_id}/problems/{problem_id}/figure")
async def get_generation_problem_figure(
    job_id: str,
    problem_id: int,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FileResponse:
    """Serve the rendered figure for a single problem."""
    job, _ = await _load_owned_job(job_id, user, session)
    path = generation.figure_path(job.id, problem_id)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "figure not found")
    return FileResponse(path, media_type="image/png")


@router.get("/api/generations/{job_id}/events")
async def stream_generation_events(
    job_id: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    job, _ = await _load_owned_job(job_id, user, session)
    bus = get_bus()
    job_id_local = job.id

    async def event_source() -> AsyncIterator[bytes]:
        # Heartbeat comment so proxies don't close the connection.
        yield b": connected\n\n"
        async for event in bus.subscribe(job_id_local):
            if await request.is_disconnected():
                return
            name = event.get("event", "message")
            yield encode_sse(name, event)
            if name in {"done", "error"}:
                return

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
