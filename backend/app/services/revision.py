from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db import _ensure
from app.models import Bank, ChatMessage, GeneratedPage, GenerationJob
from app.services import image_gen, llm
from app.services.generation import (
    PAGE_LAYOUT_PROMPT,
    PAGE_LAYOUT_SYSTEM,
    _set_status,
    _summarize_spec_for_layout,
)
from app.sse import get_bus

logger = logging.getLogger("examcraft.revision")

REVISE_SYSTEM = """You are an editor revising a structured exam SPEC based on a parent's feedback. Apply the smallest reasonable change that satisfies the request, keep the same overall shape (sections, total points), keep all answers correct, and reply with the ENTIRE updated spec each time (no diffs)."""

REVISE_PROMPT = """Current exam spec (JSON):
{spec}

Recent chat history (oldest first):
{history}

Parent's latest message:
{user_message}

Return JSON with this shape:

{{
  "updated_spec": <the full revised spec, same shape as the input>,
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


async def _replan_layout(
    bank: Bank, spec: dict[str, Any]
) -> dict[str, Any]:
    bank_profile = json.loads(bank.analysis_json or "{}")
    return await llm.chat_json(
        [
            {"role": "system", "content": PAGE_LAYOUT_SYSTEM},
            {
                "role": "user",
                "content": PAGE_LAYOUT_PROMPT.format(
                    style=json.dumps(
                        bank_profile.get("style_profile", {}),
                        ensure_ascii=False,
                        indent=2,
                    ),
                    spec_summary=_summarize_spec_for_layout(spec),
                ),
            },
        ],
        tag="revise.layout",
    )


async def apply_revision(job_id: str, user_message_id: str) -> None:
    """Background worker: take the user's message, revise the spec, re-render affected pages."""
    settings = get_settings()
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
        await _publish(channel, "step", step="revise", message="Revising the spec…")

        spec = json.loads(job.spec_json)
        history_for_prompt = [m for m in history if m.id != user_msg.id]
        result = await llm.chat_json(
            [
                {"role": "system", "content": REVISE_SYSTEM},
                {
                    "role": "user",
                    "content": REVISE_PROMPT.format(
                        spec=json.dumps(spec, ensure_ascii=False, indent=2),
                        history=_format_history(history_for_prompt),
                        user_message=user_msg.content,
                    ),
                },
            ],
            tag="revise.spec",
        )

        updated_spec = result.get("updated_spec") or {}
        reply_text = result.get("reply_text") or "Updated."

        # Persist new spec + assistant reply.
        async with sm() as session:
            job_row = (
                await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
            ).scalar_one_or_none()
            if job_row is None:
                return
            job_row.spec_json = json.dumps(updated_spec, ensure_ascii=False)
            assistant = ChatMessage(
                job_id=job_id,
                role="assistant",
                content=reply_text,
                spec_diff_json=None,
            )
            session.add(assistant)
            await session.commit()

        spec_path = settings.jobs_dir / job_id / "spec.json"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(updated_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        await _publish(channel, "spec_ready", spec=updated_spec)
        await _publish(channel, "chat", role="assistant", message=reply_text)

        # Re-plan layout, then figure out which pages actually need re-rendering.
        # The layout planner produces slightly different prompt text each call
        # even when the underlying content is identical, so naively diffing
        # prompt strings would re-render everything. Instead diff the *set of
        # problem ids per page* — that's the real semantic change.
        new_layout = await _replan_layout(bank, updated_spec)
        new_pages = new_layout.get("pages") or []
        if not new_pages:
            await _set_status(job_id, status="done", current_step="done")
            await _publish(channel, "done", message="spec updated; no page changes")
            return

        previous_layout_path = settings.jobs_dir / job_id / "prompts.json"
        old_problem_ids_by_page: dict[int, frozenset[int]] = {}
        if previous_layout_path.exists():
            try:
                prev = json.loads(previous_layout_path.read_text(encoding="utf-8"))
                for entry in prev.get("pages") or []:
                    n = int(entry.get("page_number") or 0)
                    ids = entry.get("problem_ids") or []
                    if n > 0:
                        old_problem_ids_by_page[n] = frozenset(int(i) for i in ids)
            except (json.JSONDecodeError, ValueError, TypeError):
                old_problem_ids_by_page = {}

        old_prompts: dict[int, str] = {}
        async with sm() as session:
            old_rows = (
                await session.execute(
                    select(GeneratedPage)
                    .where(GeneratedPage.job_id == job_id)
                    .order_by(GeneratedPage.page_number)
                )
            ).scalars().all()
            for r in old_rows:
                old_prompts[r.page_number] = r.prompt or ""

        new_prompts: dict[int, str] = {}
        new_problem_ids_by_page: dict[int, frozenset[int]] = {}
        for entry in new_pages:
            n = int(entry.get("page_number") or 0)
            if n <= 0:
                continue
            new_prompts[n] = str(entry.get("prompt") or "")
            ids = entry.get("problem_ids") or []
            try:
                new_problem_ids_by_page[n] = frozenset(int(i) for i in ids)
            except (TypeError, ValueError):
                new_problem_ids_by_page[n] = frozenset()

        # Persist the new layout for the next revision's diff.
        previous_layout_path.parent.mkdir(parents=True, exist_ok=True)
        previous_layout_path.write_text(
            json.dumps(new_layout, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # A page needs re-rendering if it's new, missing from the old layout,
        # or its set of problem_ids changed. Pages with the same problem_ids
        # are kept as-is — the existing image still represents them.
        changed_pages: list[int] = []
        for n in sorted(new_prompts):
            old_ids = old_problem_ids_by_page.get(n)
            new_ids = new_problem_ids_by_page.get(n, frozenset())
            if old_ids is None or old_ids != new_ids or n not in old_prompts:
                changed_pages.append(n)
        removed_pages = [n for n in old_prompts if n not in new_prompts]

        if not changed_pages and not removed_pages:
            await _set_status(job_id, status="done", current_step="done")
            await _publish(channel, "done", message="spec tweaked; no visible page changes")
            return

        await _publish(
            channel,
            "step",
            step="render",
            message=f"Re-rendering {len(changed_pages)} page(s)…",
            pages=changed_pages,
        )

        async with sm() as session:
            # Drop removed pages.
            if removed_pages:
                rows = (
                    await session.execute(
                        select(GeneratedPage).where(
                            GeneratedPage.job_id == job_id,
                            GeneratedPage.page_number.in_(removed_pages),
                        )
                    )
                ).scalars().all()
                for r in rows:
                    await session.delete(r)
            # Upsert / mark queued for changed pages.
            for n in changed_pages:
                row = (
                    await session.execute(
                        select(GeneratedPage).where(
                            GeneratedPage.job_id == job_id,
                            GeneratedPage.page_number == n,
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    row = GeneratedPage(
                        job_id=job_id,
                        page_number=n,
                        prompt=new_prompts[n],
                        status="queued",
                    )
                    session.add(row)
                else:
                    row.prompt = new_prompts[n]
                    row.status = "queued"
                    row.error = None
                    row.image_path = None
            await session.commit()

        # Render the changed pages — concurrently, with the same shared
        # semaphore in image_gen, so wall-clock matches the generate path.
        job_dir = settings.jobs_dir / job_id
        completed = 0
        failed = 0

        async def _render_one(page_number: int) -> None:
            nonlocal completed, failed
            try:
                path = await image_gen.generate_one(
                    new_prompts[page_number], job_dir / f"page_{page_number:03d}.png"
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.exception("revise: page %d render failed", page_number)
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
                        row.status = "error"
                        row.error = f"{type(exc).__name__}: {exc}"[:500]
                        await s.commit()
                await _publish(
                    channel,
                    "page_error",
                    page=page_number,
                    message=f"{type(exc).__name__}: {exc}"[:200],
                    done=completed,
                    failed=failed,
                    total=len(changed_pages),
                )
                return
            completed += 1
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
                    row.error = None
                    await s.commit()
            await _publish(
                channel,
                "page_ready",
                page=page_number,
                image_url=f"/api/generations/{job_id}/pages/{page_number}/image",
                done=completed,
                total=len(changed_pages),
            )

        await asyncio.gather(*(_render_one(n) for n in changed_pages))

        if failed and not completed:
            raise RuntimeError(
                f"all {len(changed_pages)} re-renders failed — see per-page errors"
            )

        await _set_status(
            job_id,
            status="done",
            progress_pct=1.0,
            current_step=(
                "done"
                if not failed
                else f"done with {failed} failed page(s) — chat to retry"
            ),
        )
        await _publish(
            channel,
            "done",
            message=(
                f"revision complete · {completed}/{len(changed_pages)} re-rendered"
                + (f", {failed} failed" if failed else "")
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("revision %s failed", job_id)
        await _set_status(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        await _publish(channel, "error", message=f"{type(exc).__name__}: {exc}")
