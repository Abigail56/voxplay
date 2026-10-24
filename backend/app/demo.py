"""Rules that make the API safe to leave open as a public demo.

- Visitors' enrollments expire (DEMO_RETENTION_HOURS) and are deleted by a background job.
- Built-in sample voices (LibriSpeech readers) are always there to match against.
- A simple per-IP rate limit (RATE_LIMIT_PER_MINUTE, counted in Redis) stops one visitor
  hammering the model.

Everything here is switched off by default, so local development behaves as before.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.concurrency import run_in_threadpool

from .audio import AudioError, preprocess
from .config import Settings
from .embedding import Embedder
from .matching import compute_centroid
from .models import Speaker, VoiceSample
from .store import Store

log = logging.getLogger("voiceid.demo")

AUDIO_EXT = {".wav", ".flac", ".mp3", ".webm", ".ogg", ".m4a"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def is_active():
    """SQL condition: the speaker hasn't expired yet (or never expires)."""
    return or_(Speaker.expires_at.is_(None), Speaker.expires_at > now())


async def delete_expired(session: AsyncSession) -> int:
    """Delete every expired enrollment (their voice samples go with them). Returns how many."""
    result = await session.exec(
        delete(Speaker).where(Speaker.expires_at.is_not(None), Speaker.expires_at <= now())
    )
    await session.commit()
    return result.rowcount or 0


async def cleanup_loop(sessionmaker: async_sessionmaker[AsyncSession], every_seconds: int = 300) -> None:
    """Background task: delete expired enrollments every few minutes."""
    while True:
        try:
            async with sessionmaker() as session:
                removed = await delete_expired(session)
            if removed:
                log.info("Deleted %d expired enrollment(s).", removed)
        except Exception:  # never let the loop die; try again next round
            log.exception("Cleanup of expired enrollments failed")
        await asyncio.sleep(every_seconds)


class RateLimiter:
    """Allow at most `limit` requests per client IP per minute.

    The counters live in the shared store (Redis when configured), so the limit
    holds across all API instances. It counts per clock minute, which is
    simple and good enough to stop one visitor hammering the model.
    """

    def __init__(self, store: Store, limit: int, window_seconds: int = 60) -> None:
        self.store = store
        self.limit = limit
        self.window = window_seconds

    async def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        bucket = int(time.time() // self.window)
        return await self.store.incr(f"rate:{key}:{bucket}", self.window) <= self.limit


def client_ip(request: Request, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request) -> None:
    """FastAPI dependency for the expensive endpoints (enroll, add samples, identify)."""
    settings: Settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    if not await limiter.allow(client_ip(request, settings.trust_proxy_headers)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests from you in the last minute. Please wait a moment and try again.",
        )


def sample_folder(settings: Settings) -> Path:
    """Where the built-in voices' recordings are (SAMPLE_VOICES_DIR, relative to the backend folder)."""
    folder = Path(settings.sample_voices_dir)
    return folder if folder.is_absolute() else Path(__file__).resolve().parents[1] / folder


def sample_clips(folder: Path, name: str) -> list[Path]:
    """One built-in voice's recordings, in order (the first is the one to introduce them with)."""
    person = folder / name
    if not person.is_dir() or person.parent != folder:
        return []
    return sorted(f for f in person.iterdir() if f.suffix.lower() in AUDIO_EXT)


async def seed_sample_voices(
    sessionmaker: async_sessionmaker[AsyncSession], embedder: Embedder, folder: Path
) -> int:
    """Enroll each sub-folder of `folder` as a permanent sample speaker (once).

    folder/<Speaker name>/*.webm  ->  speaker "<Speaker name>" with one sample per file.
    """
    if not folder.is_dir():
        log.warning("Sample voices folder %s not found; skipping.", folder)
        return 0

    added = 0
    async with sessionmaker() as session:
        for person in sorted(p for p in folder.iterdir() if p.is_dir()):
            if (await session.exec(select(Speaker.id).where(Speaker.name == person.name))).first():
                continue
            vectors, seconds = [], []
            for clip in sample_clips(folder, person.name):
                try:
                    prepared = await run_in_threadpool(preprocess, clip.read_bytes())
                except AudioError as exc:
                    log.warning("Skipping sample %s: %s", clip, exc)
                    continue
                vectors.append(await run_in_threadpool(embedder.embed, prepared.samples))
                seconds.append(prepared.speech_seconds)
            if not vectors:
                continue
            session.add(
                Speaker(
                    name=person.name,
                    embedding=compute_centroid(vectors).tolist(),
                    consent_given_at=now(),  # public research recordings (LibriSpeech, CC BY 4.0)
                    is_sample=True,
                    expires_at=None,
                    samples=[VoiceSample(embedding=v.tolist(), speech_seconds=s) for v, s in zip(vectors, seconds)],
                )
            )
            added += 1
        await session.commit()
    if added:
        log.info("Enrolled %d sample voice(s) from %s.", added, folder)
    return added
