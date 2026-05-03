from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import auth as auth_routes
from app.api import banks as bank_routes
from app.api import samples as sample_routes
from app.config import get_settings
from app.db import init_db
from app.jobs import mark_in_flight_jobs_failed_on_startup

logger = logging.getLogger("examcraft")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("ExamCraft starting; data dir: %s", settings.data_dir)
    await init_db()
    await mark_in_flight_jobs_failed_on_startup()
    yield
    logger.info("ExamCraft shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ExamCraft", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "model": settings.examcraft_model,
                "image_model": settings.image_model,
            }
        )

    app.include_router(auth_routes.router)
    app.include_router(bank_routes.router)
    app.include_router(sample_routes.router)

    return app


app = create_app()
