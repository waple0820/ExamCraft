from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import litellm

from app.config import get_settings

logger = logging.getLogger("examcraft.llm")


def _common_kwargs() -> dict[str, Any]:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is empty — copy .env.example to .env and set it "
            "(same value as ~/Desktop/projects/browseruse-bench/.env)."
        )
    return {
        "model": s.examcraft_model,
        "api_base": s.openai_base_url,
        "api_key": s.openai_api_key,
    }


async def chat(
    messages: list[dict[str, Any]],
    *,
    json_mode: bool = False,
    tag: str | None = None,
    temperature: float | None = None,
) -> str:
    """Plain text or JSON chat completion through the LiteLLM gateway."""
    kwargs: dict[str, Any] = {**_common_kwargs(), "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if tag:
        kwargs["metadata"] = {"tag": tag}
    logger.info("llm.chat tag=%s json=%s msgs=%d", tag, json_mode, len(messages))
    resp = await litellm.acompletion(**kwargs)
    return resp.choices[0].message.content or ""


async def chat_json(
    messages: list[dict[str, Any]], *, tag: str | None = None
) -> dict[str, Any]:
    """Chat that returns parsed JSON. Falls back to a single retry on parse failure."""
    text = await chat(messages, json_mode=True, tag=tag)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("llm.chat_json parse failed for tag=%s; retrying once", tag)
        text = await chat(
            [
                *messages,
                {
                    "role": "user",
                    "content": "Your last reply wasn't valid JSON. Reply with ONLY the JSON object, no prose.",
                },
            ],
            json_mode=True,
            tag=f"{tag}.retry" if tag else "retry",
        )
        return json.loads(text)


def _image_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{b64}"


async def vision_json(
    image_path: Path,
    prompt: str,
    *,
    tag: str | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    """One-shot vision call against a single PNG/JPG, returning parsed JSON."""
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}},
    ]
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})
    return await chat_json(messages, tag=tag)
