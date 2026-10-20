"""FastAPI entry point: `uvicorn app.main:app`."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .db import create_engine, init_db
from .demo import RateLimiter, cleanup_loop, is_active, seed_sample_voices
from .embedding import EcapaEmbedder, Embedder
from .models import Speaker
from .routers import identify, speakers
from .schemas import HealthOut

log = logging.getLogger("voiceid")


def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    """Build the app. Tests pass a fake `embedder` so no ML model is loaded."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessionmaker = create_engine(settings.database_url)
        await init_db(engine)
        app.state.sessionmaker = sessionmaker
        app.state.settings = settings
        app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
        app.state.embedder = embedder
        if embedder is None:
            log.info("Loading speaker-embedding model %s ...", settings.model_source)
            app.state.embedder = await run_in_threadpool(
                EcapaEmbedder, settings.model_source, settings.model_dir, settings.torch_threads
            )
            log.info("Model ready.")

        if settings.seed_sample_voices:
            folder = Path(settings.sample_voices_dir)
            if not folder.is_absolute():
                folder = Path(__file__).resolve().parents[1] / folder
            await seed_sample_voices(sessionmaker, app.state.embedder, folder)

        cleanup = None
        if settings.demo_retention_hours > 0:
            cleanup = asyncio.create_task(cleanup_loop(sessionmaker))
        yield
        if cleanup:
            cleanup.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup
        await engine.dispose()

    app = FastAPI(
        title="Voice ID - speaker recognition API",
        description="Enroll people by voice and identify who is speaking.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Routes read settings via Depends(get_settings); make them see *these* settings.
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(speakers.router)
    app.include_router(identify.router)

    @app.get("/health", response_model=HealthOut, tags=["health"])
    async def health(request: Request) -> HealthOut:
        async with request.app.state.sessionmaker() as session:
            count = await session.scalar(select(func.count()).select_from(Speaker).where(is_active())) or 0
        return HealthOut(
            status="ok",
            model_loaded=request.app.state.embedder is not None,
            threshold=settings.match_threshold,
            speakers=count,
            demo_retention_hours=settings.demo_retention_hours,
        )

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
