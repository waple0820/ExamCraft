# Container image for the ExamCraft backend.
#
# We need:
#   - Python 3.10+ for the FastAPI app
#   - LibreOffice (writer + impress + core) so soffice can convert .docx/.doc/
#     .odt/.rtf samples to PDF
#   - poppler-utils so pdf2image can rasterize PDFs to PNG via pdftoppm
#   - Noto CJK fonts so Chinese math papers render correctly during the
#     soffice → PDF step
#   - uv for dependency management (matches local dev)
#
# Image is roughly 1.0–1.2 GB compressed. If size becomes an issue, switch
# the LibreOffice install to libreoffice-core only and live without
# .doc/.odt/.rtf — the .docx path also works with the writer module.

FROM python:3.10-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXAMCRAFT_DATA_DIR=/data \
    EXAMCRAFT_HOST=0.0.0.0 \
    EXAMCRAFT_PORT=8000 \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-core \
        libreoffice-writer \
        libreoffice-impress \
        poppler-utils \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-noto-color-emoji \
        curl \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app/backend

# Cache deps separately from source so a code-only change doesn't bust the
# pip layer.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev

COPY backend/ ./

# /data is the persistent volume mount on Fly. Create it ahead of time so
# that the first request doesn't fail on a fresh machine.
RUN mkdir -p /data

EXPOSE 8000

# tini reaps zombies left over by soffice subprocesses, otherwise long-lived
# uvicorn workers slowly leak defunct PIDs.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
