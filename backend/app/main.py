"""FastAPI entry point: `uvicorn app.main:app`."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import func, select
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .db import create_engine, init_db
from .demo import RateLimiter, cleanup_loop, is_active, sample_folder, seed_sample_voices
from .embedding import EcapaEmbedder, Embedder
from .geocode import Geocoder, NominatimGeocoder
from .liveness import ChallengeStore, Transcriber, WhisperTranscriber
from .models import Speaker
from .routers import accounts, admin, daily, game, identify, rooms, solo, speakers
from .schemas import HealthOut
from .rooms import RoomStore
from .store import make_store

log = logging.getLogger("voiceid")


def create_app(
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    transcriber: Transcriber | None = None,
    geocoder: Geocoder | None = None,
) -> FastAPI:
    """Build the app. Tests pass fakes (embedder, transcriber, geocoder): no ML models, no network."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessionmaker = create_engine(settings.database_url)
        await init_db(engine)
        app.state.sessionmaker = sessionmaker
        app.state.settings = settings
        store = make_store(settings.redis_url)
        app.state.store = store
        app.state.rooms = RoomStore(store, settings.room_ttl_hours)
        app.state.geocoder = geocoder or NominatimGeocoder(store, settings.geocoder_user_agent)
        app.state.jwt_secret = settings.jwt_secret
        if not app.state.jwt_secret:
            log.warning("JWT_SECRET is not set: using a random one, so everyone is signed out on restart.")
            app.state.jwt_secret = secrets.token_urlsafe(32)
        app.state.rate_limiter = RateLimiter(store, settings.rate_limit_per_minute)
        app.state.challenges = ChallengeStore(store, settings.challenge_ttl_seconds)
        app.state.embedder = embedder
        app.state.transcriber = transcriber
        if embedder is None:
            log.info("Loading speaker-embedding model %s ...", settings.model_source)
            app.state.embedder = await run_in_threadpool(
                EcapaEmbedder, settings.model_source, settings.model_dir, settings.torch_threads
            )
            log.info("Model ready.")
        if transcriber is None:
            log.info("Loading speech-to-text model %s ...", settings.asr_model)
            app.state.transcriber = await run_in_threadpool(
                WhisperTranscriber, settings.asr_model, settings.asr_dir, settings.torch_threads
            )
            log.info("Speech-to-text ready.")

        if settings.seed_sample_voices:
            await seed_sample_voices(sessionmaker, app.state.embedder, sample_folder(settings))

        cleanup = None
        if settings.demo_retention_hours > 0:
            cleanup = asyncio.create_task(cleanup_loop(sessionmaker))
        yield
        if cleanup:
            cleanup.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup
        if geocoder is None:
            await app.state.geocoder.close()
        await store.close()
        await engine.dispose()

    app = FastAPI(
        title="Voice ID - speaker recognition API",
        description="Enroll people by voice, identify who is speaking (with a liveness check) "
        "and find out who spoke when in a longer recording.",
        version="2.0.0",
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
    app.include_router(accounts.router)
    app.include_router(rooms.router)
    app.include_router(game.router)
    app.include_router(daily.router)
    app.include_router(solo.router)
    app.include_router(admin.router)

    @app.get("/health", response_model=HealthOut, tags=["health"])
    async def health(request: Request) -> HealthOut:
        async with request.app.state.sessionmaker() as session:
            count = (await session.exec(select(func.count()).select_from(Speaker).where(is_active()))).one()
        return HealthOut(
            status="ok",
            model_loaded=request.app.state.embedder is not None,
            threshold=settings.match_threshold,
            speakers=count,
            demo_retention_hours=settings.demo_retention_hours,
            liveness_required=settings.require_liveness,
        )

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
