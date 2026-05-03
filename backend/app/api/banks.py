from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import Bank, User

router = APIRouter(prefix="/api/banks", tags=["banks"])


class BankCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)


class BankOut(BaseModel):
    id: str
    name: str
    description: str | None
    analysis_status: str
    created_at: str

    @classmethod
    def from_model(cls, b: Bank) -> "BankOut":
        return cls(
            id=b.id,
            name=b.name,
            description=b.description,
            analysis_status=b.analysis_status,
            created_at=b.created_at.isoformat() if b.created_at else "",
        )


async def _load_owned_bank(
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


@router.get("", response_model=list[BankOut])
async def list_banks(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BankOut]:
    rows = (
        await session.execute(
            select(Bank).where(Bank.user_id == user.id).order_by(desc(Bank.created_at))
        )
    ).scalars().all()
    return [BankOut.from_model(b) for b in rows]


@router.post("", response_model=BankOut, status_code=status.HTTP_201_CREATED)
async def create_bank(
    body: BankCreateIn,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BankOut:
    bank = Bank(user_id=user.id, name=body.name, description=body.description)
    session.add(bank)
    await session.commit()
    await session.refresh(bank)
    return BankOut.from_model(bank)


@router.get("/{bank_id}", response_model=BankOut)
async def get_bank(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BankOut:
    bank = await _load_owned_bank(bank_id, user, session)
    return BankOut.from_model(bank)


@router.delete("/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank(
    bank_id: str,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    bank = await _load_owned_bank(bank_id, user, session)
    await session.delete(bank)
    await session.commit()
