from __future__ import annotations

import asyncio
import base64
import logging
import random
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("examcraft.image_gen")

# Per the reference recipe in
# ~/.claude/projects/-Users-avatar-Desktop-projects-browseruse-bench/memory/reference_image_gen_api.md
# the endpoint silently nulls ~10% of calls. Retry with backoff.
DEFAULT_RETRIES = 4
DEFAULT_TIMEOUT_S = 240.0
DEFAULT_SIZE = "1024x1024"

# Cap concurrent image generations to keep wall-clock predictable.
_GEN_SEMAPHORE = asyncio.Semaphore(3)


class ImageGenError(RuntimeError):
    """Final failure after all retries."""


def _decode_response(payload: dict[str, Any]) -> bytes:
    """Returns PNG bytes from any of the response shapes the gateway has emitted."""
    data = payload.get("data") or []
    if not data:
        raise ImageGenError(f"empty data in image-gen response: keys={list(payload.keys())}")
    item = data[0]
    url = item.get("url") or ""
    if isinstance(url, str) and url.startswith("data:image/"):
        return base64.b64decode(url.split(",", 1)[1])
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        # Defer fetch to caller via httpx.
        raise ImageGenError(f"unexpected http(s) url in response: {url}")
    raise ImageGenError(
        f"image-gen response had no decodable image; item keys: {list(item.keys())}"
    )


async def generate_one(
    prompt: str,
    out_path: Path,
    *,
    size: str = DEFAULT_SIZE,
    retries: int = DEFAULT_RETRIES,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Path:
    """Render a single image to out_path. Returns out_path on success."""
    settings = get_settings()
    if not settings.image_api_key:
        raise ImageGenError("IMAGE_API_KEY is empty; cannot call gpt-image-2")

    url = settings.image_api_base.rstrip("/") + "/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {settings.image_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.image_model,
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
    }

    last_err: Exception | None = None
    async with _GEN_SEMAPHORE:
        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    resp = await client.post(url, json=body, headers=headers)
                if resp.status_code >= 400:
                    raise ImageGenError(
                        f"HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                payload = resp.json()
                png = _decode_response(payload)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(png)
                logger.info(
                    "image_gen ok attempt=%d bytes=%d -> %s",
                    attempt,
                    len(png),
                    out_path.name,
                )
                return out_path
            except (httpx.HTTPError, ImageGenError, ValueError) as exc:  # noqa: BLE001
                last_err = exc
                if attempt >= retries:
                    break
                # Backoff with jitter; first retry around 2s.
                delay = (2 ** (attempt - 1)) + random.uniform(0, 1.5)
                logger.warning(
                    "image_gen attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt,
                    retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    raise ImageGenError(
        f"image_gen failed after {retries} attempts: {last_err!r}"
    ) from last_err


async def generate_many(
    prompts: list[str],
    out_dir: Path,
    *,
    size: str = DEFAULT_SIZE,
    on_page: Callable[[int, Path], Awaitable[None]] | None = None,  # noqa: F821
    on_page_error: Callable[[int, Exception], Awaitable[None]] | None = None,  # noqa: F821
) -> list[Path | Exception]:
    """Render N pages with bounded concurrency.

    Returns a list of length len(prompts); each element is either a Path on
    success or the Exception that caused the page to fail after all retries.
    Partial failure does NOT raise — the caller decides whether to fail the
    overall job.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    async def _one(idx: int, prompt: str) -> tuple[int, Path | Exception]:
        path = out_dir / f"page_{idx + 1:03d}.png"
        try:
            await generate_one(prompt, path, size=size)
        except Exception as exc:  # noqa: BLE001
            logger.error("page %d: failed after retries: %s", idx + 1, exc)
            if on_page_error is not None:
                try:
                    await on_page_error(idx + 1, exc)
                except Exception:  # noqa: BLE001
                    logger.exception("on_page_error callback failed for page %d", idx + 1)
            return idx, exc
        if on_page is not None:
            try:
                await on_page(idx + 1, path)
            except Exception:  # noqa: BLE001
                logger.exception("on_page callback failed for page %d", idx + 1)
        return idx, path

    tasks = [_one(i, p) for i, p in enumerate(prompts)]
    results: list[Path | Exception] = [RuntimeError("not started")] * len(prompts)
    for fut in asyncio.as_completed(tasks):
        idx, outcome = await fut
        results[idx] = outcome
    return results
