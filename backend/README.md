# ExamCraft backend

FastAPI + SQLAlchemy (aiosqlite) + litellm + pdf2image, uv-managed.

```sh
uv sync
uv run examcraft-server
```

The server reads `../.env` (one directory up — single env file shared with
the web side).

## Layout

```
app/
├── main.py        FastAPI app factory + lifespan
├── cli.py         `examcraft-server` entry point
├── config.py      pydantic-settings, loads ../.env
├── db.py          async engine + session, WAL mode
├── models.py      SQLAlchemy ORM
├── auth.py        passwordless cookie session (HMAC via itsdangerous)
├── api/           routers (auth, banks, samples, generations, chat)
├── services/      llm.py, image_gen.py, docrender.py, ingestion.py, generation.py, revision.py
├── jobs.py        in-process JobRegistry + asyncio.create_task
└── sse.py         per-job pub/sub for progress events
```

## Tests

```sh
uv run pytest -q
```
