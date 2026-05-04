"""Export a generation's spec + figures to a Word .docx via pandoc.

Why pandoc: the spec carries math expressions in LaTeX form
(`\\(-3\\)`, `\\[\\frac{1}{3}\\]`, etc.) and we want them to land in
Word as real OMML equations, not images or raw text. python-docx can't
do that conversion; pandoc does it natively when we feed it markdown
with the tex_math_double_backslash + tex_math_dollars extensions on.

Pictures are inlined right under the problem they belong to via standard
markdown image syntax with absolute paths to the per-problem PNGs the
generation pipeline already produced under jobs/<id>/figures/<pid>.png.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.generation import figure_path

logger = logging.getLogger("examcraft.docx_export")

# tex_math_single_backslash → "\(x\)" / "\[x\]" (one backslash before paren),
# which is what the LLM emits. Pandoc's `tex_math_double_backslash` is for
# the escaped form "\\(x\\)" with two backslashes — we don't want that.
# tex_math_dollars → "$x$" / "$$x$$" inline + display, default in pandoc but
# explicit here for clarity.
PANDOC_FROM = "markdown+tex_math_single_backslash+tex_math_dollars+raw_tex"
PANDOC_TO = "docx"


def _find_pandoc() -> Path:
    found = shutil.which("pandoc")
    if not found:
        raise RuntimeError(
            "pandoc not found. Install with: brew install pandoc (mac) / apt-get install -y pandoc (ubuntu)"
        )
    return Path(found)


def _safe_filename(title: str, fallback: str = "exam") -> str:
    """Make a filename-safe slug that keeps Chinese characters readable."""
    if not title:
        return fallback
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", title).strip(" ._")
    return cleaned or fallback


def build_markdown(
    spec: dict[str, Any],
    job_id: str,
    *,
    include_answers: bool = False,
) -> str:
    """Render the spec as pandoc-flavored markdown."""
    lines: list[str] = []

    title = spec.get("title") or "试卷"
    lines.append(f"# {title}")
    lines.append("")

    meta = spec.get("meta", {}) or {}
    bits: list[str] = []
    if meta.get("subject"):
        bits.append(f"学科: {meta['subject']}")
    if meta.get("grade"):
        bits.append(f"年级: {meta['grade']}")
    if meta.get("duration_minutes"):
        bits.append(f"时长: {meta['duration_minutes']} 分钟")
    if meta.get("total_points"):
        bits.append(f"满分: {meta['total_points']} 分")
    if bits:
        lines.append("  ·  ".join(bits))
        lines.append("")

    answers: list[tuple[int, str]] = []

    for section in spec.get("sections", []) or []:
        section_name = section.get("name") or ""
        if section_name:
            lines.append(f"## {section_name}")
            lines.append("")
        if section.get("instructions"):
            lines.append(f"*{section['instructions']}*")
            lines.append("")

        for problem in section.get("problems", []) or []:
            pid = problem.get("id")
            if pid is None:
                continue
            content = problem.get("content", "") or ""
            choices = problem.get("choices") or []
            answer = problem.get("answer", "")
            points = problem.get("points")

            head = f"**{pid}.** {content}"
            if isinstance(points, int):
                head += f"  ({points} 分)"
            lines.append(head)
            lines.append("")

            if choices:
                # Two-column-ish: just list each choice on its own line.
                # Pandoc renders these as paragraphs in Word, which is
                # how teachers usually format A./B./C./D. options.
                for c in choices:
                    lines.append(str(c))
                    lines.append("")

            fig = problem.get("figure") or {}
            fig_status = fig.get("status") if isinstance(fig, dict) else None
            if fig.get("needed") and fig_status == "done":
                fig_p = figure_path(job_id, int(pid))
                if fig_p.exists():
                    # Absolute path so we don't need --resource-path acrobatics.
                    # `width=6cm` keeps figures roughly the size they show on
                    # screen — sized to fit in a Word column without being huge.
                    lines.append(f"![]({fig_p.as_posix()}){{ width=6cm }}")
                    lines.append("")

            if isinstance(answer, str) and answer.strip():
                answers.append((int(pid), answer.strip()))
            else:
                answers.append((int(pid), str(answer)))

        lines.append("")

    if include_answers and answers:
        lines.append("\\newpage")
        lines.append("")
        lines.append("## 参考答案")
        lines.append("")
        for pid, a in answers:
            lines.append(f"**{pid}.** {a}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


async def export_docx(
    spec: dict[str, Any],
    job_id: str,
    *,
    include_answers: bool = False,
) -> Path:
    """Render the spec to a .docx file. Returns the on-disk path.

    The output goes under jobs/<id>/exam(_with_answers).docx and is
    overwritten on every call, so re-downloading after a chat revision
    yields a fresh document."""
    settings = get_settings()
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    md = build_markdown(spec, job_id, include_answers=include_answers)
    md_path = job_dir / (
        "exam_with_answers.md" if include_answers else "exam.md"
    )
    md_path.write_text(md, encoding="utf-8")

    out_path = job_dir / (
        "exam_with_answers.docx" if include_answers else "exam.docx"
    )

    pandoc = _find_pandoc()
    cmd = [
        str(pandoc),
        "--from",
        PANDOC_FROM,
        "--to",
        PANDOC_TO,
        "--output",
        str(out_path),
        str(md_path),
    ]
    logger.info("docx export: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"pandoc failed (exit {proc.returncode}): "
            f"stderr={stderr.decode(errors='replace')[:500]} "
            f"stdout={stdout.decode(errors='replace')[:500]}"
        )

    if not out_path.exists():
        raise RuntimeError("pandoc did not produce a .docx file")

    return out_path


__all__ = ["build_markdown", "export_docx", "_safe_filename"]
