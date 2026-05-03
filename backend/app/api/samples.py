from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.config import get_settings
from app.db import get_session
from app.jobs import get_registry
from app.models import Bank, SampleExam, SampleExamPage, User
from app.services import docrender, ingestion

router = APIRouter(tags=["samples"])


class SamplePageOut(BaseModel):
    id: str
    page_number: int
    image_url: str
    has_analysis: bool


class SampleOut(BaseModel):
    id: str
    bank_id: str
    original_filename: str
    page_count: int
    status: str
    error: str | None
    created_at: str

    @classmethod
    def from_model(cls, s: SampleExam) -> "SampleOut":
        return cls(
            id=s.id,
            bank_id=s.bank_id,
            original_filename=s.original_filename,
            page_count=s.page_count,
            status=s.status,
            error=s.error,
            created_at=s.created_at.isoformat() if s.created_at else "",
        )


class SampleDetailOut(SampleOut):
    pages: list[SamplePageOut]


class BankAnalysisOut(BaseModel):
    status: str
    error: str | None
    analysis: dict[str, Any] | None
    sample_count: int
    samples_done: int


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


async def _ensure_sample_owned(
    sample_id: str, user: User, session: AsyncSession
) -> SampleExam:
    sample = (
        await session.execute(
            select(SampleExam)
            .join(Bank, Bank.id == SampleExam.bank_id)
            .where(SampleExam.id == sample_id, Bank.user_id == user.id)
        )
    ).scalar_one_or_none()
    if sample is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sample not found")
    return sample


@router.get("/api/banks/{bank_id}/samples", response_model=list[SampleOut])
async def list_samples(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[SampleOut]:
    await _ensure_bank_owned(bank_id, user, session)
    rows = (
        await session.execute(
            select(SampleExam)
            .where(SampleExam.bank_id == bank_id)
            .order_by(SampleExam.created_at.desc())
        )
    ).scalars().all()
    return [SampleOut.from_model(s) for s in rows]


@router.post(
    "/api/banks/{bank_id}/samples",
    response_model=SampleOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_sample(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> SampleOut:
    bank = await _ensure_bank_owned(bank_id, user, session)
    settings = get_settings()

    if file.filename is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file has no name")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in docrender.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unsupported file type {suffix!r}; supported: "
            f"{', '.join(sorted(docrender.SUPPORTED_EXTENSIONS))}",
        )

    bank_dir = settings.uploads_dir / bank.id
    bank_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    dest = bank_dir / stored_name

    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    await file.close()

    sample = SampleExam(
        bank_id=bank.id,
        original_filename=file.filename,
        file_path=str(dest),
        status="uploaded",
    )
    session.add(sample)
    await session.commit()
    await session.refresh(sample)

    sample_id = sample.id
    get_registry().spawn(
        lambda: ingestion.ingest_sample(sample_id),
        label=f"ingest.sample.{sample_id[:8]}",
    )

    return SampleOut.from_model(sample)


@router.get("/api/samples/{sample_id}", response_model=SampleDetailOut)
async def get_sample(
    sample_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SampleDetailOut:
    sample = await _ensure_sample_owned(sample_id, user, session)
    pages = (
        await session.execute(
            select(SampleExamPage)
            .where(SampleExamPage.sample_id == sample.id)
            .order_by(SampleExamPage.page_number)
        )
    ).scalars().all()
    base = SampleOut.from_model(sample).model_dump()
    return SampleDetailOut(
        **base,
        pages=[
            SamplePageOut(
                id=p.id,
                page_number=p.page_number,
                image_url=f"/api/samples/{sample.id}/pages/{p.page_number}/image",
                has_analysis=bool(p.vision_json),
            )
            for p in pages
        ],
    )


@router.get("/api/samples/{sample_id}/pages/{page_number}/image")
async def get_sample_page_image(
    sample_id: str,
    page_number: int,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FileResponse:
    sample = await _ensure_sample_owned(sample_id, user, session)
    page = (
        await session.execute(
            select(SampleExamPage).where(
                SampleExamPage.sample_id == sample.id,
                SampleExamPage.page_number == page_number,
            )
        )
    ).scalar_one_or_none()
    if page is None or not Path(page.image_path).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page image not found")
    return FileResponse(page.image_path, media_type="image/png")


@router.delete("/api/samples/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample(
    sample_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    sample = await _ensure_sample_owned(sample_id, user, session)

    # Best-effort filesystem cleanup; don't fail the API if files were moved.
    try:
        Path(sample.file_path).unlink(missing_ok=True)
    except OSError:
        pass
    settings = get_settings()
    pages_dir = settings.pages_dir / sample.id
    if pages_dir.exists():
        shutil.rmtree(pages_dir, ignore_errors=True)

    await session.delete(sample)
    await session.commit()


@router.get("/api/banks/{bank_id}/analysis", response_model=BankAnalysisOut)
async def get_bank_analysis(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BankAnalysisOut:
    bank = await _ensure_bank_owned(bank_id, user, session)
    samples = (
        await session.execute(select(SampleExam).where(SampleExam.bank_id == bank_id))
    ).scalars().all()

    parsed: dict[str, Any] | None = None
    if bank.analysis_json:
        try:
            parsed = json.loads(bank.analysis_json)
        except json.JSONDecodeError:
            parsed = {"_raw": bank.analysis_json}

    return BankAnalysisOut(
        status=bank.analysis_status,
        error=bank.analysis_error,
        analysis=parsed,
        sample_count=len(samples),
        samples_done=sum(1 for s in samples if s.status == "done"),
    )


@router.post("/api/banks/{bank_id}/analysis/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_bank_analysis(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    bank = await _ensure_bank_owned(bank_id, user, session)
    samples = (
        await session.execute(
            select(SampleExam).where(SampleExam.bank_id == bank.id)
        )
    ).scalars().all()
    if not any(s.status == "done" for s in samples):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "no analyzed samples yet — wait for ingestion to finish on at least one upload",
        )
    bank.analysis_status = "running"
    bank.analysis_error = None
    await session.commit()
    bank_id_local = bank.id
    get_registry().spawn(
        lambda: ingestion.aggregate_bank(bank_id_local),
        label=f"aggregate.bank.{bank_id_local[:8]}",
    )
    return {"status": "queued"}


@router.get("/api/system/check", tags=["system"])
async def system_check() -> dict[str, Any]:
    """Diagnostic endpoint: are external CLIs (soffice, pdftoppm) reachable?"""
    return {"deps": docrender.system_dependency_check()}
