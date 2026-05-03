"""Convenience seeding: create a starter bank and queue ingestion of DOCX/PDF
samples from ~/Desktop/personal/试卷/ (or another directory passed on the CLI).

Run with:

    cd backend
    uv run examcraft-seed                                  # default user "papa", default bank "九年级数学"
    uv run examcraft-seed --user mom --bank 高中物理 --src ~/Documents/物理/
    uv run examcraft-seed --limit 2                        # only first 2 files
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import _ensure, init_db
from app.jobs import get_registry, mark_in_flight_jobs_failed_on_startup
from app.models import Bank, SampleExam, User
from app.services import docrender, ingestion

DEFAULT_SRC = Path.home() / "Desktop" / "personal" / "试卷"
DEFAULT_USER = "papa"
DEFAULT_BANK = "九年级数学"
DEFAULT_DESCRIPTION = "湖北中考真题 + 模拟题样本（自动 seed）"


async def seed(
    *,
    user_name: str,
    bank_name: str,
    description: str,
    src_dir: Path,
    limit: int | None,
    auto_aggregate: bool,
) -> None:
    settings = get_settings()
    await init_db()
    await mark_in_flight_jobs_failed_on_startup()

    if not src_dir.exists():
        raise SystemExit(f"source dir does not exist: {src_dir}")

    candidates = sorted(
        p
        for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in docrender.SUPPORTED_EXTENSIONS
    )
    if not candidates:
        raise SystemExit(
            f"no .pdf/.docx files in {src_dir} — supported: {sorted(docrender.SUPPORTED_EXTENSIONS)}"
        )
    if limit is not None:
        candidates = candidates[:limit]

    print(f"src: {src_dir}")
    print(f"user: {user_name}, bank: {bank_name}")
    print(f"will ingest {len(candidates)} file(s):")
    for p in candidates:
        print(f"  - {p.name}")

    _, sm = _ensure()

    async with sm() as session:
        user = (
            await session.execute(select(User).where(User.username == user_name))
        ).scalar_one_or_none()
        if user is None:
            user = User(username=user_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"created user '{user_name}'")
        else:
            print(f"using existing user '{user_name}'")

        bank = (
            await session.execute(
                select(Bank).where(Bank.user_id == user.id, Bank.name == bank_name)
            )
        ).scalar_one_or_none()
        if bank is None:
            bank = Bank(user_id=user.id, name=bank_name, description=description)
            session.add(bank)
            await session.commit()
            await session.refresh(bank)
            print(f"created bank '{bank_name}' ({bank.id})")
        else:
            print(f"using existing bank '{bank_name}' ({bank.id})")

    bank_dir = settings.uploads_dir / bank.id
    bank_dir.mkdir(parents=True, exist_ok=True)

    sample_ids: list[str] = []
    async with sm() as session:
        for src in candidates:
            stored = bank_dir / f"{uuid.uuid4().hex}{src.suffix.lower()}"
            shutil.copy2(src, stored)
            sample = SampleExam(
                bank_id=bank.id,
                original_filename=src.name,
                file_path=str(stored),
                status="uploaded",
            )
            session.add(sample)
            await session.commit()
            await session.refresh(sample)
            sample_ids.append(sample.id)
            print(f"queued {src.name} -> sample {sample.id}")

    print("\nstarting ingestion (the same coroutine the API uses)…")
    # Run inline so the script doesn't exit before background tasks complete.
    for sid in sample_ids[:-1]:
        get_registry().spawn(
            lambda sid=sid: ingestion.ingest_sample(sid, then_aggregate_bank=False),
            label=f"seed.ingest.{sid[:8]}",
        )
    if sample_ids:
        await ingestion.ingest_sample(sample_ids[-1], then_aggregate_bank=False)

    # Wait for the spawned tasks to finish.
    while get_registry().in_flight():
        await asyncio.sleep(2)
        print(f"…still running {get_registry().in_flight()} ingestion task(s)")

    if auto_aggregate:
        print("\naggregating bank profile…")
        await ingestion.aggregate_bank(bank.id)

    print("\ndone.")
    print(f"open the app and sign in as '{user_name}' — bank '{bank_name}' should be ready.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="examcraft-seed", description=__doc__)
    parser.add_argument("--user", default=DEFAULT_USER, help=f"username (default: {DEFAULT_USER})")
    parser.add_argument("--bank", default=DEFAULT_BANK, help=f"bank name (default: {DEFAULT_BANK})")
    parser.add_argument(
        "--description",
        default=DEFAULT_DESCRIPTION,
        help="bank description if creating a new one",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SRC,
        help=f"directory of .pdf/.docx samples (default: {DEFAULT_SRC})",
    )
    parser.add_argument("--limit", type=int, default=None, help="ingest only first N files")
    parser.add_argument(
        "--no-aggregate",
        action="store_true",
        help="skip the bank-level aggregation step (you can trigger it later from the UI)",
    )
    args = parser.parse_args()

    asyncio.run(
        seed(
            user_name=args.user,
            bank_name=args.bank,
            description=args.description,
            src_dir=args.src.expanduser(),
            limit=args.limit,
            auto_aggregate=not args.no_aggregate,
        )
    )


if __name__ == "__main__":
    main()
