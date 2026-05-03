from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db import _ensure
from app.models import Bank, GenerationJob
from app.services import image_gen, llm
from app.sse import get_bus

logger = logging.getLogger("examcraft.generation")

# Bounded concurrency for figure generation. image_gen has its own semaphore
# inside; this is a soft cap on the asyncio.gather so we don't fan out 30+
# tasks at once and starve everything else.
FIGURE_CONCURRENCY = 4

SPEC_SYSTEM = """You are an expert exam writer producing a structured exam SPEC. The spec is the source of truth — the parent's app renders the questions as proper text in the browser, and only the per-problem figures are sent to an image model. Aim for content quality, balanced difficulty, and faithfulness to the bank's topic distribution and difficulty curve."""

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
          "type": "<problem-type name in the source language, e.g. 选择题 / 填空题 / 解答题 / 几何证明>",
          "content": "<the full problem statement, in the source language>",
          "choices": [<for multiple-choice only, otherwise omit>],
          "answer": "<the correct answer (letter for MC, value for fill-in, full solution for proof/computation)>",
          "knowledge_point": "<one of the bank's knowledge_points>",
          "difficulty": <0.0-1.0>,
          "points": <integer>,
          "figure": {{
            "needed": <true if the problem references a figure / diagram / coordinate system / function graph / statistical chart, false otherwise>,
            "description": "<if needed, an English description for an image-generation model. Always English regardless of the problem's language. Strict rules below>"
          }}
        }}
      ]
    }}
  ]
}}

CONTENT RULES
- Match the bank's knowledge_point_distribution and problem_type_distribution roughly. Don't over-concentrate.
- Difficulty curve should mirror the bank's profile (前易后难 if that's what the bank shows).
- Sum of section problem points should equal meta.total_points.
- Problems are NEW questions, not copies of any sample.
- Answers must be correct.

FIGURE RULES (very important — quality lives or dies here)
- Set "needed": true ONLY if the problem genuinely needs a figure. Geometry, coordinate systems, function graphs, statistical charts, and 3D-view problems are typical needs. Pure-text computation, fill-in-blank, simplification, word problems with no diagram do NOT need figures. Do NOT add decorative figures.
- If the problem text references a figure (using phrases like "如图" / "如图所示" / "如下图"), then "needed" MUST be true and "description" must reflect what was referenced.
- Figure descriptions are passed VERBATIM to gpt-image-2. They MUST be in English.
- Use this template for every figure description:
  "Clean black-and-white line drawing of a textbook math diagram on a white background, no shading, no extra decoration, no watermark.  <THE GEOMETRY / GRAPH HERE, with concrete labels in Latin characters>. Style: simple thin black lines, clear right-angle marks where applicable, sparse text, exam-textbook aesthetic."
- Concrete labels: only short Latin/numeric labels are reliable in the image. Use letters like A, B, C, P, O, x, y; numbers like 60°, 4cm; and arrows / dashed lines as needed. NEVER ask for Chinese text inside the figure — it won't render.
- One figure = one diagram. If a problem needs a graph and a separate table, prefer to inline the table in the problem text and use only the graph as the figure.
- If "needed" is false, set "description" to "" (empty string).

Reply with ONLY the JSON object."""

# Style preamble we prepend to every figure_description before sending to
# gpt-image-2 — the recipe in the memory says descriptive narration of an
# already-finished artifact works best.
FIGURE_STYLE_PREAMBLE = (
    "An editorial-quality math textbook figure, ready for print. "
    "Clean black ink line drawing on a pure white background. "
    "No shading, no color, no watermark, no decoration, no border. "
    "Sparse text, only short Latin / numeric labels. "
)


def _figure_prompt(description: str) -> str:
    return FIGURE_STYLE_PREAMBLE + description.strip()


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


def collect_figures(spec: dict[str, Any]) -> list[tuple[int, str]]:
    """Walk the spec and return [(problem_id, description)] for every problem
    that needs a figure. Skips problems with figure.needed=false or empty
    description."""
    out: list[tuple[int, str]] = []
    for section in spec.get("sections", []) or []:
        for problem in section.get("problems", []) or []:
            fig = problem.get("figure") or {}
            if not isinstance(fig, dict):
                continue
            if not fig.get("needed"):
                continue
            desc = (fig.get("description") or "").strip()
            if not desc:
                continue
            try:
                pid = int(problem.get("id"))
            except (TypeError, ValueError):
                continue
            out.append((pid, desc))
    return out


def _attach_figure_status(
    spec: dict[str, Any],
    job_id: str,
    figure_status: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Annotate each problem's figure object with status / image_url so the
    frontend can render it directly. Mutates a copy of spec; returns it."""
    for section in spec.get("sections", []) or []:
        for problem in section.get("problems", []) or []:
            fig = problem.get("figure")
            if not isinstance(fig, dict) or not fig.get("needed"):
                problem["figure"] = {"needed": False, "description": ""}
                continue
            try:
                pid = int(problem.get("id"))
            except (TypeError, ValueError):
                continue
            status = figure_status.get(pid, {})
            problem["figure"] = {
                "needed": True,
                "description": fig.get("description", ""),
                "status": status.get("status", "queued"),
                "error": status.get("error"),
                "image_url": (
                    f"/api/generations/{job_id}/problems/{pid}/figure"
                    if status.get("status") == "done"
                    else None
                ),
            }
    return spec


def figure_path(job_id: str, problem_id: int) -> Path:
    settings = get_settings()
    return settings.jobs_dir / job_id / "figures" / f"{problem_id}.png"


async def _persist_spec(job_id: str, spec: dict[str, Any]) -> None:
    settings = get_settings()
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    spec_path = job_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    await _set_status(job_id, spec_json=json.dumps(spec, ensure_ascii=False))


async def _render_figures(
    job_id: str,
    figures_to_gen: list[tuple[int, str]],
    spec: dict[str, Any],
    figure_status: dict[int, dict[str, Any]],
    channel: str,
) -> None:
    """Concurrently render each figure, updating figure_status + spec live."""
    sem = asyncio.Semaphore(FIGURE_CONCURRENCY)
    total = len(figures_to_gen)
    completed = 0
    failed = 0

    async def _one(problem_id: int, description: str) -> None:
        nonlocal completed, failed
        out_path = figure_path(job_id, problem_id)
        async with sem:
            try:
                await image_gen.generate_one(_figure_prompt(description), out_path)
                figure_status[problem_id] = {"status": "done"}
                completed += 1
                pct = 0.3 + 0.65 * ((completed + failed) / total)
                # Snapshot spec with current figure statuses so callers polling
                # the REST endpoint see live progress, not just SSE consumers.
                _attach_figure_status(spec, job_id, figure_status)
                await _persist_spec(job_id, spec)
                await _set_status(job_id, progress_pct=pct)
                await _publish(
                    channel,
                    "figure_ready",
                    problem_id=problem_id,
                    image_url=f"/api/generations/{job_id}/problems/{problem_id}/figure",
                    done=completed,
                    total=total,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("figure %d render failed", problem_id)
                figure_status[problem_id] = {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }
                failed += 1
                pct = 0.3 + 0.65 * ((completed + failed) / total)
                _attach_figure_status(spec, job_id, figure_status)
                await _persist_spec(job_id, spec)
                await _set_status(job_id, progress_pct=pct)
                await _publish(
                    channel,
                    "figure_error",
                    problem_id=problem_id,
                    message=f"{type(exc).__name__}: {exc}"[:200],
                    done=completed,
                    failed=failed,
                    total=total,
                )

    await asyncio.gather(*(_one(pid, desc) for pid, desc in figures_to_gen))


async def run_generation(job_id: str) -> None:
    """Top-level orchestrator: spec → per-problem figure rendering."""
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
            current_step="building exam content",
        )
        await _publish(channel, "step", step="spec", message="Building exam content…")

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

        # Collect figures to generate; initialize per-problem figure status.
        figures_to_gen = collect_figures(spec)
        figure_status: dict[int, dict[str, Any]] = {
            pid: {"status": "queued"} for pid, _ in figures_to_gen
        }
        _attach_figure_status(spec, job_id, figure_status)
        await _persist_spec(job_id, spec)

        await _set_status(
            job_id,
            progress_pct=0.3,
            current_step=(
                f"rendering {len(figures_to_gen)} figure(s)"
                if figures_to_gen
                else "no figures needed"
            ),
        )
        await _publish(channel, "spec_ready", spec=spec)

        if not figures_to_gen:
            await _set_status(
                job_id,
                status="done",
                progress_pct=1.0,
                current_step="done",
            )
            await _publish(channel, "done", message="exam ready · no figures needed")
            return

        await _publish(
            channel,
            "step",
            step="figures",
            message=f"Rendering {len(figures_to_gen)} figure(s)…",
            count=len(figures_to_gen),
        )

        await _render_figures(job_id, figures_to_gen, spec, figure_status, channel)

        completed = sum(1 for s in figure_status.values() if s.get("status") == "done")
        failed = sum(1 for s in figure_status.values() if s.get("status") == "error")
        total = len(figures_to_gen)

        if completed == 0:
            raise RuntimeError(
                f"all {total} figure render attempt(s) failed — see per-problem errors"
            )

        await _set_status(
            job_id,
            status="done",
            progress_pct=1.0,
            current_step=(
                "done"
                if not failed
                else f"done · {failed} figure(s) failed — chat to retry"
            ),
        )
        await _publish(
            channel,
            "done",
            message=(
                f"exam ready · {completed}/{total} figures rendered"
                + (f", {failed} failed" if failed else "")
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("generation %s failed", job_id)
        await _set_status(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        await _publish(channel, "error", message=f"{type(exc).__name__}: {exc}")
    finally:
        await get_bus().close(channel)


def index_figures_in_spec(spec: dict[str, Any]) -> dict[int, str]:
    """Reverse-map from problem_id to the figure_description currently in the
    spec. Used by revision to detect which figures changed."""
    out: dict[int, str] = {}
    for section in spec.get("sections", []) or []:
        for problem in section.get("problems", []) or []:
            fig = problem.get("figure") or {}
            if not isinstance(fig, dict) or not fig.get("needed"):
                continue
            try:
                pid = int(problem.get("id"))
            except (TypeError, ValueError):
                continue
            out[pid] = (fig.get("description") or "").strip()
    return out
