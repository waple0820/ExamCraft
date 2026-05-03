from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

from pdf2image import convert_from_path

logger = logging.getLogger("examcraft.docrender")

# soffice is single-instance per UserInstallation profile — running it
# concurrently against the same profile leads to lockfile races. We serialize
# with this lock and pass a unique -env:UserInstallation per invocation as
# belt-and-suspenders.
_SOFFICE_LOCK = asyncio.Lock()

_SOFFICE_CANDIDATES = (
    "soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/opt/homebrew/bin/soffice",
    "/usr/local/bin/soffice",
)

DOCX_EXTENSIONS = {".doc", ".docx", ".odt", ".rtf"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = DOCX_EXTENSIONS | PDF_EXTENSIONS


def find_soffice() -> Path:
    for cand in _SOFFICE_CANDIDATES:
        resolved = shutil.which(cand) if "/" not in cand else (cand if Path(cand).exists() else None)
        if resolved:
            return Path(resolved)
    raise RuntimeError(
        "LibreOffice (soffice) not found. Install with: brew install libreoffice"
    )


def find_pdftoppm() -> Path:
    """Verify poppler is available — pdf2image shells out to pdftoppm."""
    found = shutil.which("pdftoppm")
    if not found:
        raise RuntimeError(
            "poppler (pdftoppm) not found. Install with: brew install poppler"
        )
    return Path(found)


async def docx_to_pdf(src: Path, out_dir: Path) -> Path:
    """Convert a .docx/.doc/.odt/.rtf to PDF via headless LibreOffice."""
    soffice = find_soffice()
    out_dir.mkdir(parents=True, exist_ok=True)

    async with _SOFFICE_LOCK:
        # Each invocation gets a unique LO user-profile dir to avoid the
        # lock-file collisions you get when reusing one.
        with tempfile.TemporaryDirectory(prefix="examcraft_lo_") as profile_dir:
            cmd = [
                str(soffice),
                f"-env:UserInstallation=file://{profile_dir}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(src),
            ]
            logger.info("soffice convert: %s -> %s", src.name, out_dir)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"soffice failed (exit {proc.returncode}): "
                    f"stdout={stdout.decode(errors='replace')[:500]} "
                    f"stderr={stderr.decode(errors='replace')[:500]}"
                )

    pdf_path = out_dir / (src.stem + ".pdf")
    if not pdf_path.exists():
        # Fallback: pick the only .pdf in out_dir (filename mangling can occur)
        pdfs = sorted(out_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError(f"soffice produced no PDF for {src}")
        pdf_path = pdfs[0]
    return pdf_path


def _pdf_to_pngs_sync(pdf_path: Path, out_dir: Path, dpi: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path), dpi=dpi)
    paths: list[Path] = []
    for i, img in enumerate(images, start=1):
        p = out_dir / f"page_{i:03d}.png"
        img.save(p, "PNG")
        paths.append(p)
    return paths


async def pdf_to_pngs(pdf_path: Path, out_dir: Path, *, dpi: int = 200) -> list[Path]:
    find_pdftoppm()
    return await asyncio.to_thread(_pdf_to_pngs_sync, pdf_path, out_dir, dpi)


async def render_to_pages(src: Path, out_dir: Path, *, dpi: int = 200) -> list[Path]:
    """Top-level entry: any supported file → list of per-page PNG paths."""
    suffix = src.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if suffix in PDF_EXTENSIONS:
        pdf = src
    else:
        with tempfile.TemporaryDirectory(prefix="examcraft_pdf_") as tmp:
            pdf = await docx_to_pdf(src, Path(tmp))
            # Copy the produced PDF inside out_dir so it survives the cleanup.
            persisted = out_dir / "source.pdf"
            out_dir.mkdir(parents=True, exist_ok=True)
            persisted.write_bytes(pdf.read_bytes())
            pdf = persisted

    return await pdf_to_pngs(pdf, out_dir, dpi=dpi)


def system_dependency_check() -> dict[str, str | None]:
    """Returns {"soffice": path-or-None, "pdftoppm": path-or-None} for diagnostics."""
    try:
        soffice = str(find_soffice())
    except RuntimeError:
        soffice = None
    pdftoppm = shutil.which("pdftoppm")
    return {"soffice": soffice, "pdftoppm": pdftoppm}


__all__ = [
    "DOCX_EXTENSIONS",
    "PDF_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "docx_to_pdf",
    "find_pdftoppm",
    "find_soffice",
    "pdf_to_pngs",
    "render_to_pages",
    "system_dependency_check",
]
