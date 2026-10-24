"""Tests for the public-demo rules: expiry, sample voices, rate limit, database URLs."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, update
from sqlmodel import select

from app.config import Settings, normalize_database_url
from app.demo import RateLimiter, delete_expired, seed_sample_voices
from app.main import create_app
from app.models import Speaker, VoiceSample
from app.store import MemoryStore

from .helpers import FakeEmbedder, FakeGeocoder, FakeTranscriber, tone_wav

TEST_DB = os.getenv("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")


# ---------- pure functions (no database) ----------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # What Neon gives you
        (
            "postgresql://u:p@ep-x.neon.tech/voiceid?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/voiceid?ssl=require",
        ),
        ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        # Already correct: unchanged
        ("postgresql+asyncpg://u:p@db:5432/voiceid", "postgresql+asyncpg://u:p@db:5432/voiceid"),
        ("postgresql://u:p@h/db?sslmode=disable", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_normalize_database_url(given, expected):
    assert normalize_database_url(given) == expected
    assert Settings(database_url=given).database_url == expected


async def test_rate_limiter_allows_up_to_limit_per_key():
    limiter = RateLimiter(MemoryStore(), limit=2)
    assert await limiter.allow("a") and await limiter.allow("a")
    assert not await limiter.allow("a")
    assert await limiter.allow("b")  # other visitors are not affected


async def test_rate_limiter_zero_means_off():
    limiter = RateLimiter(MemoryStore(), limit=0)
    assert all([await limiter.allow("a") for _ in range(100)])


# ---------- API with a real database ----------


def make_client(**overrides):
    # redis_url="": never share rate-limit counters with a running API through the real Redis.
    base = {"require_liveness": False, "redis_url": "", "seed_sample_voices": False}
    settings = Settings(database_url=TEST_DB, match_threshold=0.5, **{**base, **overrides})
    return create_app(settings, embedder=FakeEmbedder(), transcriber=FakeTranscriber(), geocoder=FakeGeocoder())


async def started(app):
    ctx = app.router.lifespan_context(app)
    await ctx.__aenter__()
    async with app.state.sessionmaker() as s:
        await s.exec(text("TRUNCATE speakers, voice_samples, game_plays, users RESTART IDENTITY CASCADE"))
        await s.commit()
    return ctx


def wav(freq):
    return ("files", ("v.wav", tone_wav(freq), "audio/wav"))


@needs_db
async def test_enrollment_expires_and_is_cleaned_up():
    app = make_client(demo_retention_hours=24)
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            ada = (await c.post("/speakers", data={"name": "Ada", "consent": "true"}, files=[wav(200)])).json()
            expires = datetime.fromisoformat(ada["expires_at"])
            assert timedelta(hours=23.9) < expires - datetime.now(timezone.utc) <= timedelta(hours=24)
            assert ada["is_sample"] is False

            # Pretend 24 hours have passed.
            async with app.state.sessionmaker() as s:
                await s.exec(
                    update(Speaker).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
                )
                await s.commit()

            # Expired speakers vanish at once from every endpoint...
            assert (await c.get("/speakers")).json() == []
            assert (await c.get(f"/speakers/{ada['id']}")).status_code == 404
            r = await c.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
            assert r.json()["label"] == "unknown"
            assert (await c.get("/health")).json()["demo_retention_hours"] == 24

            # ...and the name is free again, because enrolling clears expired rows first.
            again = await c.post("/speakers", data={"name": "Ada", "consent": "true"}, files=[wav(200)])
            assert again.status_code == 201

        # The cleanup job deletes expired rows and their voice samples for good.
        async with app.state.sessionmaker() as s:
            await s.exec(update(Speaker).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
            await s.commit()
            assert await delete_expired(s) == 1
            assert (await s.exec(select(VoiceSample.id))).all() == []
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_no_expiry_by_default():
    app = make_client()
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            ada = (await c.post("/speakers", data={"name": "Ada", "consent": "true"}, files=[wav(200)])).json()
            assert ada["expires_at"] is None
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_sample_voices_are_seeded_once_and_protected(tmp_path: Path):
    for name, freq in [("Reader A", 300), ("Reader B", 700)]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "1.wav").write_bytes(tone_wav(freq))

    app = make_client(demo_retention_hours=24)
    ctx = await started(app)
    try:
        assert await seed_sample_voices(app.state.sessionmaker, app.state.embedder, tmp_path) == 2
        assert await seed_sample_voices(app.state.sessionmaker, app.state.embedder, tmp_path) == 0  # idempotent

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            speakers = (await c.get("/speakers")).json()
            assert {s["name"] for s in speakers} == {"Reader A", "Reader B"}
            assert all(s["is_sample"] and s["expires_at"] is None for s in speakers)

            r = await c.post("/identify", files={"file": ("q.wav", tone_wav(700), "audio/wav")})
            assert r.json()["label"] == "Reader B"

            sample_id = speakers[0]["id"]
            assert (await c.delete(f"/speakers/{sample_id}")).status_code == 403
            assert (await c.post(f"/speakers/{sample_id}/samples", files=[wav(300)])).status_code == 403
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_demo_full_limit():
    app = make_client(max_active_enrollments=1)
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            assert (await c.post("/speakers", data={"name": "A", "consent": "true"}, files=[wav(200)])).status_code == 201
            r = await c.post("/speakers", data={"name": "B", "consent": "true"}, files=[wav(600)])
            assert r.status_code == 503
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_rate_limit_returns_429():
    app = make_client(rate_limit_per_minute=2)
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            clip = {"file": ("q.wav", tone_wav(200), "audio/wav")}
            assert (await c.post("/identify", files=clip)).status_code == 200
            assert (await c.post("/identify", files=clip)).status_code == 200
            r = await c.post("/identify", files=clip)
            assert r.status_code == 429
            assert "Too many requests" in r.json()["detail"]
            assert (await c.get("/speakers")).status_code == 200  # reading is never limited
    finally:
        await ctx.__aexit__(None, None, None)
