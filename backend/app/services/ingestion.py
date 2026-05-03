from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import _ensure
from app.models import Bank, SampleExam, SampleExamPage
from app.services import docrender, llm

logger = logging.getLogger("examcraft.ingestion")

PAGE_ANALYSIS_CONCURRENCY = 5

PAGE_VISION_PROMPT = """You are analyzing one page of a sample exam paper.
Return a JSON object with these keys:

  "page_role": "cover" | "content" | "answer_key" | "blank" | "other"
  "header_style": short string describing the school header / banner
  "layout": short string (e.g. "two-column with boxed problems", "single column")
  "typography_notes": short string about fonts, weight, problem numbering style
  "problem_types": array of strings (e.g. ["multiple_choice", "fill_in_blank", "computation", "proof"])
  "knowledge_points": array of short Chinese phrases naming the topics covered (e.g. ["二次函数", "相似三角形"])
  "difficulty_signals": array of short strings (e.g. ["mostly easy", "one challenge problem near end"])
  "notes": one short sentence of anything else worth remembering

Reply with ONLY the JSON object."""

BANK_AGGREGATION_SYSTEM = """You are aggregating per-page analyses of multiple sample exam papers into a single bank-level profile that downstream code will use to GENERATE new exams in the same style and topic distribution. Be specific and practical, not vague."""

BANK_AGGREGATION_PROMPT = """Below is a list of per-page analyses, grouped by source file. Produce a single JSON object with these keys:

  "style_profile": {{
      "header_template": short description of the header style to reproduce,
      "layout_pattern": short description of overall page layout,
      "typography": short description of typography conventions,
      "tone": one short sentence on overall feel ("formal regional mock-exam", "friendly school worksheet", etc)
  }},
  "knowledge_point_distribution": object mapping Chinese topic name -> rough weight (number summing to 1.0),
  "problem_type_distribution": object mapping type -> rough weight (sum to 1.0),
  "difficulty_curve": short string describing difficulty progression across the exam,
  "typical_page_count": integer (median across samples),
  "summary": one paragraph summarizing what a generated exam in this bank should look like.

Source analyses:
{analyses}

Reply with ONLY the JSON object."""


async def _refresh_bank(session: AsyncSession, bank_id: str) -> Bank | None:
    return (
        await session.execute(select(Bank).where(Bank.id == bank_id))
    ).scalar_one_or_none()


async def _refresh_sample(session: AsyncSession, sample_id: str) -> SampleExam | None:
    return (
        await session.execute(select(SampleExam).where(SampleExam.id == sample_id))
    ).scalar_one_or_none()


async def ingest_sample(sample_id: str, *, then_aggregate_bank: bool = True) -> None:
    """End-to-end ingestion of a single uploaded sample.

    Flow: extract pages → vision-analyze each page → trigger bank aggregation.
    Updates the SampleExam.status field on each transition.
    """
    _, sm = _ensure()

    async with sm() as session:
        sample = await _refresh_sample(session, sample_id)
        if sample is None:
            logger.warning("ingest_sample: sample %s vanished", sample_id)
            return
        bank_id = sample.bank_id
        sample.status = "extracting"
        sample.error = None
        await session.commit()

    try:
        await _extract_pages(sample_id)
        await _analyze_pages(sample_id)
        async with sm() as session:
            sample = await _refresh_sample(session, sample_id)
            if sample is None:
                return
            sample.status = "done"
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest_sample %s failed", sample_id)
        async with sm() as session:
            sample = await _refresh_sample(session, sample_id)
            if sample is not None:
                sample.status = "error"
                sample.error = f"{type(exc).__name__}: {exc}"[:500]
                await session.commit()
        return

    if then_aggregate_bank:
        try:
            await aggregate_bank(bank_id)
        except Exception:  # noqa: BLE001
            logger.exception("aggregate_bank %s failed after ingest", bank_id)


async def _extract_pages(sample_id: str) -> None:
    from app.config import get_settings

    settings = get_settings()
    _, sm = _ensure()

    async with sm() as session:
        sample = await _refresh_sample(session, sample_id)
        if sample is None:
            return
        src = Path(sample.file_path)
        out_dir = settings.pages_dir / sample.id
        out_dir.mkdir(parents=True, exist_ok=True)

    paths = await docrender.render_to_pages(src, out_dir)

    async with sm() as session:
        sample = await _refresh_sample(session, sample_id)
        if sample is None:
            return
        sample.page_count = len(paths)
        sample.status = "analyzing"
        for i, p in enumerate(paths, start=1):
            page = SampleExamPage(
                sample_id=sample.id,
                page_number=i,
                image_path=str(p),
            )
            session.add(page)
        await session.commit()
        logger.info("sample %s extracted %d page(s)", sample_id, len(paths))


async def _analyze_pages(sample_id: str) -> None:
    _, sm = _ensure()

    async with sm() as session:
        rows = (
            await session.execute(
                select(SampleExamPage)
                .where(SampleExamPage.sample_id == sample_id)
                .order_by(SampleExamPage.page_number)
            )
        ).scalars().all()
        page_jobs = [(p.id, Path(p.image_path), p.page_number) for p in rows]

    sem = asyncio.Semaphore(PAGE_ANALYSIS_CONCURRENCY)

    async def _one(page_id: str, image: Path, n: int) -> tuple[str, dict[str, Any] | str]:
        async with sem:
            try:
                data = await llm.vision_json(
                    image,
                    PAGE_VISION_PROMPT,
                    tag=f"ingest.page.{n}",
                )
                return page_id, data
            except Exception as exc:  # noqa: BLE001
                logger.exception("page analysis failed for sample %s page %d", sample_id, n)
                return page_id, f"error: {type(exc).__name__}: {exc}"

    results = await asyncio.gather(*(_one(pid, img, n) for pid, img, n in page_jobs))

    async with sm() as session:
        rows = (
            await session.execute(
                select(SampleExamPage).where(SampleExamPage.sample_id == sample_id)
            )
        ).scalars().all()
        by_id = {r.id: r for r in rows}
        for pid, payload in results:
            row = by_id.get(pid)
            if row is None:
                continue
            if isinstance(payload, dict):
                row.vision_json = json.dumps(payload, ensure_ascii=False)
            else:
                row.vision_json = json.dumps({"_error": payload}, ensure_ascii=False)
        await session.commit()


async def aggregate_bank(bank_id: str) -> None:
    """Aggregate all per-page analyses into the bank's analysis_json."""
    _, sm = _ensure()

    async with sm() as session:
        bank = await _refresh_bank(session, bank_id)
        if bank is None:
            return
        bank.analysis_status = "running"
        bank.analysis_error = None
        await session.commit()

    try:
        async with sm() as session:
            samples = (
                await session.execute(
                    select(SampleExam).where(SampleExam.bank_id == bank_id)
                )
            ).scalars().all()
            sample_ids = [s.id for s in samples]

            grouped: list[dict[str, Any]] = []
            for s in samples:
                pages = (
                    await session.execute(
                        select(SampleExamPage)
                        .where(SampleExamPage.sample_id == s.id)
                        .order_by(SampleExamPage.page_number)
                    )
                ).scalars().all()
                page_payloads = []
                for p in pages:
                    if p.vision_json:
                        try:
                            page_payloads.append(json.loads(p.vision_json))
                        except json.JSONDecodeError:
                            continue
                if page_payloads:
                    grouped.append({"file": s.original_filename, "pages": page_payloads})

        if not grouped:
            raise RuntimeError("No analyzed pages available for aggregation")

        rendered = json.dumps(grouped, ensure_ascii=False, indent=2)
        prompt = BANK_AGGREGATION_PROMPT.format(analyses=rendered)
        result = await llm.chat_json(
            [
                {"role": "system", "content": BANK_AGGREGATION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tag="ingest.aggregate",
        )

        async with sm() as session:
            bank = await _refresh_bank(session, bank_id)
            if bank is None:
                return
            bank.analysis_json = json.dumps(result, ensure_ascii=False)
            bank.analysis_status = "done"
            bank.analysis_error = None
            await session.commit()
            logger.info("bank %s aggregated over %d sample(s)", bank_id, len(sample_ids))
    except Exception as exc:  # noqa: BLE001
        logger.exception("aggregate_bank %s failed", bank_id)
        async with sm() as session:
            bank = await _refresh_bank(session, bank_id)
            if bank is not None:
                bank.analysis_status = "error"
                bank.analysis_error = f"{type(exc).__name__}: {exc}"[:500]
                await session.commit()
