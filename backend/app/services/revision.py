from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db import _ensure
from app.models import Bank, ChatMessage, GenerationJob
from app.services import image_gen, llm
from app.services.generation import (
    _attach_figure_status,
    _figure_prompt,
    _persist_spec,
    _set_status,
    figure_path,
    index_figures_in_spec,
)
from app.sse import get_bus

logger = logging.getLogger("examcraft.revision")

REVISE_SYSTEM = """You are an editor revising a structured exam SPEC based on a parent's feedback. Apply the smallest reasonable change that satisfies the request, keep the same overall shape (sections, total points), keep all answers correct, and reply with the ENTIRE updated spec each time (no diffs).

The spec format is unchanged from the original generation: each problem has id / type / content / choices / answer / knowledge_point / difficulty / points / figure {needed, description}. When you change a problem that has or needs a figure, also update its figure object accordingly:
- If the new problem still needs a figure of the same shape, keep the description as close as possible.
- If the figure changes, write a new English description following the same rules (clean line drawing, white background, short Latin labels only).
- If the new problem no longer needs a figure, set "figure": {"needed": false, "description": ""}."""

REVISE_PROMPT = """Current exam spec (JSON):
{spec}

Recent chat history (oldest first):
{history}

Parent's latest message:
{user_message}

Return JSON with this shape:

{{
  "updated_spec": <the full revised spec, same shape as the input — including the figure objects on each problem>,
  "reply_text": "<one or two sentences in the parent's language explaining what you changed>"
}}

Reply with ONLY the JSON object."""


async def _publish(channel: str, event_name: str, **data: Any) -> None:
    payload = {"event": event_name, "ts": datetime.utcnow().isoformat(), **data}
    await get_bus().publish(channel, payload)


def _format_history(messages: list[ChatMessage]) -> str:
    if not messages:
        return "(no previous turns)"
    lines: list[str] = []
    for m in messages[-10:]:
        prefix = "Parent" if m.role == "user" else "Editor"
        lines.append(f"{prefix}: {m.content}")
    return "\n".join(lines)


async def apply_revision(job_id: str, user_message_id: str) -> None:
    """Background worker: rewrite the spec from the user's message, then
    re-render only the figures whose description actually changed."""
    _, sm = _ensure()
    channel = job_id

    async with sm() as session:
        job = (
            await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            return
        bank = (
            await session.execute(select(Bank).where(Bank.id == job.bank_id))
        ).scalar_one_or_none()
        history = (
            await session.execute(
                select(ChatMessage)
                .where(ChatMessage.job_id == job_id)
                .order_by(ChatMessage.created_at)
            )
        ).scalars().all()
        user_msg = next((m for m in history if m.id == user_message_id), None)

    if not job or not bank or not user_msg or not job.spec_json:
        await _publish(channel, "error", message="cannot revise: missing job/spec/message")
        await _set_status(job_id, status="failed", error="missing job/spec/message")
        return

    try:
        await _publish(channel, "step", step="revise", message="Revising the exam…")

        old_spec = json.loads(job.spec_json)
        old_figures = index_figures_in_spec(old_spec)

        history_for_prompt = [m for m in history if m.id != user_msg.id]
        result = await llm.chat_json(
            [
                {"role": "system", "content": REVISE_SYSTEM},
                {
                    "role": "user",
                    "content": REVISE_PROMPT.format(
                        spec=json.dumps(old_spec, ensure_ascii=False, indent=2),
                        history=_format_history(history_for_prompt),
                        user_message=user_msg.content,
                    ),
                },
            ],
            tag="revise.spec",
        )

        updated_spec = result.get("updated_spec") or {}
        reply_text = result.get("reply_text") or "Updated."

        async with sm() as session:
            job_row = (
                await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
            ).scalar_one_or_none()
            if job_row is None:
                return
            assistant = ChatMessage(
                job_id=job_id,
                role="assistant",
                content=reply_text,
                spec_diff_json=None,
            )
            session.add(assistant)
            await session.commit()

        # Diff figures by description string. Three cases:
        #   - changed: same problem id, description text differs -> regenerate
        #   - new: problem id only in new spec -> generate
        #   - removed: problem id only in old spec -> delete on disk
        new_figures = index_figures_in_spec(updated_spec)
        to_render: list[tuple[int, str]] = []
        for pid, desc in new_figures.items():
            if old_figures.get(pid) != desc:
                to_render.append((pid, desc))
        removed = [pid for pid in old_figures if pid not in new_figures]

        # Carry over the existing figure files for unchanged problems by
        # initializing figure_status from disk.
        figure_status: dict[int, dict[str, Any]] = {}
        for pid in new_figures:
            if (pid, new_figures[pid]) in to_render:
                figure_status[pid] = {"status": "queued"}
            elif figure_path(job_id, pid).exists():
                figure_status[pid] = {"status": "done"}
            else:
                # Existed in spec but file is missing — re-render to be safe.
                figure_status[pid] = {"status": "queued"}
                if (pid, new_figures[pid]) not in to_render:
                    to_render.append((pid, new_figures[pid]))

        _attach_figure_status(updated_spec, job_id, figure_status)
        await _persist_spec(job_id, updated_spec)
        await _publish(channel, "spec_ready", spec=updated_spec)
        await _publish(channel, "chat", role="assistant", message=reply_text)

        # Clean up removed figures' files.
        for pid in removed:
            try:
                figure_path(job_id, pid).unlink(missing_ok=True)
            except OSError:
                pass

        if not to_render:
            await _set_status(job_id, status="done", progress_pct=1.0, current_step="done")
            await _publish(channel, "done", message="exam updated · no figures changed")
            return

        total = len(to_render)
        await _publish(
            channel,
            "step",
            step="figures",
            message=f"Re-rendering {total} figure(s)…",
            count=total,
        )

        sem = asyncio.Semaphore(4)
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
                    _attach_figure_status(updated_spec, job_id, figure_status)
                    await _persist_spec(job_id, updated_spec)
                    await _publish(
                        channel,
                        "figure_ready",
                        problem_id=problem_id,
                        image_url=f"/api/generations/{job_id}/problems/{problem_id}/figure",
                        done=completed,
                        total=total,
                    )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    logger.exception(
                        "revise: figure %d render failed", problem_id
                    )
                    figure_status[problem_id] = {
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}"[:500],
                    }
                    _attach_figure_status(updated_spec, job_id, figure_status)
                    await _persist_spec(job_id, updated_spec)
                    await _publish(
                        channel,
                        "figure_error",
                        problem_id=problem_id,
                        message=f"{type(exc).__name__}: {exc}"[:200],
                        done=completed,
                        failed=failed,
                        total=total,
                    )

        await asyncio.gather(*(_one(pid, desc) for pid, desc in to_render))

        if failed and not completed:
            raise RuntimeError(
                f"all {total} re-renders failed — see per-figure errors"
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
                f"revision complete · {completed}/{total} re-rendered"
                + (f", {failed} failed" if failed else "")
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("revision %s failed", job_id)
        await _set_status(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        await _publish(channel, "error", message=f"{type(exc).__name__}: {exc}")
