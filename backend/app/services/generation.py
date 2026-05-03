from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db import _ensure
from app.models import Bank, GeneratedPage, GenerationJob
from app.services import image_gen, llm
from app.sse import get_bus

logger = logging.getLogger("examcraft.generation")

SPEC_SYSTEM = """You are an expert exam writer producing a structured exam SPEC. The spec is the source of truth (questions and answers will be displayed alongside a stylized image rendering). Aim for content quality, balanced difficulty, and faithfulness to the bank's topic distribution and difficulty curve."""

SPEC_PROMPT = """Build a brand-new practice exam spec for this bank. The bank's aggregated profile is below.

Bank profile (JSON):
{profile}

Return a JSON object with exactly this shape:

{{
  "title": "<exam title in the same language as the source samples>",
  "meta": {{
    "subject": "<subject name>",
    "grade": "<grade level>",
    "duration_minutes": <integer>,
    "total_points": <integer>
  }},
  "sections": [
    {{
      "name": "<section name>",
      "instructions": "<brief instructions>",
      "problems": [
        {{
          "id": <integer, unique across the whole exam>,
          "type": "<one of the bank's problem_types>",
          "content": "<the full problem statement, in the source language>",
          "choices": [<for multiple_choice only, otherwise omit>],
          "answer": "<the correct answer (letter for MC, value for fill-in, full solution for proof/computation)>",
          "knowledge_point": "<one of the bank's knowledge_points>",
          "difficulty": <0.0-1.0>,
          "points": <integer>
        }}
      ]
    }}
  ]
}}

Rules:
- Match the bank's knowledge_point_distribution and problem_type_distribution roughly. Don't over-concentrate on one topic.
- Difficulty curve should mirror the bank's profile.
- Total points across sections should equal meta.total_points.
- Problems are NEW questions, not copies of any sample.
- Answers must be correct.

Reply with ONLY the JSON object."""

PAGE_LAYOUT_SYSTEM = """You write image-generation prompts for gpt-image-2. Output prompts that DESCRIBE a finished printed exam page in editorial English narration, naming the bank's visual style as a noun. Do NOT pass long verbatim CJK strings or full problem statements to the image model — describe the content categorically (e.g. "five algebra problems on quadratic equations") because the model cannot render long Chinese math text accurately. The actual problem text is rendered separately from the spec; the image's job is the bank's visual feel."""

PAGE_LAYOUT_PROMPT = """The exam spec is below. Plan how to lay it out across pages, and write one descriptive image-generation prompt per page.

Bank style profile:
{style}

Exam spec (truncated to topic categories — full text lives in the spec, not the image):
{spec_summary}

Return JSON with this shape:

{{
  "pages": [
    {{
      "page_number": 1,
      "problem_ids": [<ids from the spec>],
      "prompt": "<English descriptive prompt for gpt-image-2 — magazine-quality, identifies the bank's visual style as a noun, mentions the page's content categorically without verbatim text, generous whitespace, premium documentation feel>"
    }}
  ]
}}

Rules:
- Prompts must be in English, even though the page content is Chinese.
- Each prompt frames the page as already-finished print artifact ("A premium documentation-style exam page showing…"), never as labeled instructions.
- Do not include long verbatim text from the spec — paraphrase content categorically.
- Cover the entire exam across pages.
- 4–8 pages typical.

Reply with ONLY the JSON object."""


async def _publish(channel: str, event_name: str, **data: Any) -> None:
    payload = {"event": event_name, "ts": datetime.utcnow().isoformat(), **data}
    await get_bus().publish(channel, payload)


async def _set_status(
    job_id: str,
    *,
    status: str | None = None,
    progress_pct: float | None = None,
    current_step: str | None = None,
    error: str | None = None,
    spec_json: str | None = None,
) -> None:
    _, sm = _ensure()
    async with sm() as session:
        job = (
            await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            return
        if status is not None:
            job.status = status
            if status == "running" and job.started_at is None:
                job.started_at = datetime.utcnow()
            if status in {"done", "failed"}:
                job.finished_at = datetime.utcnow()
        if progress_pct is not None:
            job.progress_pct = progress_pct
        if current_step is not None:
            job.current_step = current_step
        if error is not None:
            job.error = error[:1000]
        if spec_json is not None:
            job.spec_json = spec_json
        await session.commit()


def _summarize_spec_for_layout(spec: dict[str, Any]) -> str:
    """A compact view of the spec — enough for layout planning, no verbatim CJK."""
    lines: list[str] = [f"Title: {spec.get('title', '')}"]
    meta = spec.get("meta", {}) or {}
    lines.append(
        f"Subject: {meta.get('subject', '')} | Grade: {meta.get('grade', '')}"
        f" | Duration: {meta.get('duration_minutes', '')}min"
        f" | Points: {meta.get('total_points', '')}"
    )
    for s in spec.get("sections", []):
        problems = s.get("problems", []) or []
        kps = sorted({p.get("knowledge_point", "") for p in problems if p.get("knowledge_point")})
        types = sorted({p.get("type", "") for p in problems if p.get("type")})
        lines.append(
            f"- Section '{s.get('name', '')}': {len(problems)} problems, "
            f"types={types}, topics={kps}"
        )
    return "\n".join(lines)


async def run_generation(job_id: str) -> None:
    """Top-level orchestrator: spec → page prompts → image fan-out."""
    settings = get_settings()
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    channel = job_id

    _, sm = _ensure()
    async with sm() as session:
        job = (
            await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            return
        bank = (
            await session.execute(select(Bank).where(Bank.id == job.bank_id))
        ).scalar_one_or_none()

    if bank is None:
        await _set_status(job_id, status="failed", error="bank not found")
        await _publish(channel, "error", message="bank not found")
        return
    if not bank.analysis_json:
        await _set_status(
            job_id,
            status="failed",
            error="bank profile not aggregated yet — analyze samples first",
        )
        await _publish(
            channel,
            "error",
            message="bank profile not aggregated yet — analyze samples first",
        )
        return

    bank_profile = json.loads(bank.analysis_json)

    try:
        await _set_status(
            job_id,
            status="running",
            progress_pct=0.05,
            current_step="building exam spec",
        )
        await _publish(channel, "step", step="spec", message="Building exam spec…")

        spec = await llm.chat_json(
            [
                {"role": "system", "content": SPEC_SYSTEM},
                {
                    "role": "user",
                    "content": SPEC_PROMPT.format(
                        profile=json.dumps(bank_profile, ensure_ascii=False, indent=2)
                    ),
                },
            ],
            tag="generate.spec",
        )
        spec_path = job_dir / "spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        await _set_status(
            job_id,
            spec_json=json.dumps(spec, ensure_ascii=False),
            progress_pct=0.2,
            current_step="planning page layout",
        )
        await _publish(channel, "spec_ready", spec=spec)
        await _publish(channel, "step", step="layout", message="Planning page layout…")

        # Step B — page prompts
        layout = await llm.chat_json(
            [
                {"role": "system", "content": PAGE_LAYOUT_SYSTEM},
                {
                    "role": "user",
                    "content": PAGE_LAYOUT_PROMPT.format(
                        style=json.dumps(
                            bank_profile.get("style_profile", {}), ensure_ascii=False, indent=2
                        ),
                        spec_summary=_summarize_spec_for_layout(spec),
                    ),
                },
            ],
            tag="generate.layout",
        )
        pages = layout.get("pages") or []
        if not pages:
            raise RuntimeError("layout planner produced no pages")
        prompts = [p.get("prompt", "") for p in pages]
        (job_dir / "prompts.json").write_text(
            json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        async with sm() as session:
            for i, p in enumerate(pages, start=1):
                gp = GeneratedPage(
                    job_id=job_id,
                    page_number=i,
                    prompt=p.get("prompt", ""),
                    status="queued",
                )
                session.add(gp)
            await session.commit()

        await _set_status(
            job_id,
            progress_pct=0.3,
            current_step=f"rendering {len(prompts)} page(s)",
        )
        await _publish(
            channel,
            "step",
            step="render",
            message=f"Rendering {len(prompts)} page(s)…",
            page_count=len(prompts),
        )

        completed_count = 0
        total = len(prompts)

        async def on_page(page_number: int, path: Path) -> None:
            nonlocal completed_count
            completed_count += 1
            async with sm() as s:
                row = (
                    await s.execute(
                        select(GeneratedPage).where(
                            GeneratedPage.job_id == job_id,
                            GeneratedPage.page_number == page_number,
                        )
                    )
                ).scalar_one_or_none()
                if row is not None:
                    row.image_path = str(path)
                    row.status = "done"
                    await s.commit()
            pct = 0.3 + 0.65 * (completed_count / max(total, 1))
            await _set_status(job_id, progress_pct=pct)
            await _publish(
                channel,
                "page_ready",
                page=page_number,
                image_url=f"/api/generations/{job_id}/pages/{page_number}/image",
                done=completed_count,
                total=total,
            )

        await image_gen.generate_many(prompts, job_dir, on_page=on_page)

        await _set_status(
            job_id,
            status="done",
            progress_pct=1.0,
            current_step="done",
        )
        await _publish(channel, "done", message="all pages ready")
    except Exception as exc:  # noqa: BLE001
        logger.exception("generation %s failed", job_id)
        await _set_status(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        await _publish(channel, "error", message=f"{type(exc).__name__}: {exc}")
    finally:
        await get_bus().close(channel)


async def revise_generation(
    job_id: str, user_message: str
) -> tuple[dict[str, Any], list[int], str]:
    """Stub for M5; returns (updated_spec, pages_to_rerender, reply_text)."""
    # M5 will fill this in.
    raise NotImplementedError
