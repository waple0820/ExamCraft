# ExamCraft

A personal local web app that turns teachers' sample exam papers into freshly
generated practice exams in the same style. Upload `.docx` / `.pdf` samples
into a question bank, the app analyzes their knowledge points and visual
style, and one click produces a brand-new exam — both as a printable spec
(questions + answers) and a stylized PNG rendered by `gpt-image-2`. Includes
a chat loop for fixing problems on the fly.

Built for one user, one Mac, one browser. Passwordless, single-tenant.

## Quick start

### 1. System dependencies (one time)

```sh
brew install poppler libreoffice
```

- `poppler` provides `pdftoppm`, used by `pdf2image` to rasterize PDFs.
- `libreoffice` provides `soffice`, used to convert `.docx` → PDF.

### 2. Environment

```sh
cp .env.example .env
# Edit .env: paste OPENAI_API_KEY (same key as browseruse-bench/.env) and
# rotate EXAMCRAFT_SESSION_SECRET.
```

### 3. Backend

```sh
cd backend
uv sync
uv run examcraft-server          # http://127.0.0.1:8000
```

### 4. Frontend

```sh
cd web
npm install
npm run dev                      # http://localhost:3000
```

Or use the convenience target from the repo root:

```sh
make dev                         # backend + frontend in parallel
```

## Project layout

```
ExamCraft/
├── backend/      Python 3.10+, uv-managed (FastAPI + SQLAlchemy + litellm + pdf2image)
├── web/          Next.js 15 + TypeScript + Tailwind + shadcn/ui
├── Makefile      dev / setup / test
└── .env.example  shared env template (backend reads this; web has its own)
```

Generated artifacts (uploads, page images, SQLite DB, job step files) live
under `backend/data/` and are git-ignored.

## Architecture in one paragraph

Backend pipelines: ingestion converts each uploaded paper to per-page PNGs
(via `soffice` + `pdf2image`), then `gpt-5.4` (through litellm) extracts
knowledge points and style per page; an aggregation pass produces a
bank-level style-and-topic profile. Generation builds a structured exam
**spec** (the source of truth — questions, answers, knowledge points), then
descriptive English page-prompts, then fans out to `gpt-image-2` with
bounded concurrency and retry. Chat revision edits the spec and re-renders
just the affected pages. Progress streams to the frontend over SSE.

The spec JSON, not the PNG, is canonical. The PNG is a stylized companion.

## Plan & memory

The full implementation plan lives at
`~/.claude/plans/buzzing-sparking-raven.md`.

Project memory (Claude Code) lives at
`~/.claude/projects/-Users-avatar-Desktop-projects-ExamCraft/memory/`.
