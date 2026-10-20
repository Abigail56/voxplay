"""Rules that make the API safe to leave open as a public demo.

- Visitors' enrollments expire (DEMO_RETENTION_HOURS) and are deleted by a background job.
- Built-in sample voices (LibriSpeech readers) are always there to match against.
- A simple per-IP rate limit (RATE_LIMIT_PER_MINUTE) stops one visitor hammering the model.

Everything here is switched off by default, so local development behaves as before.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from .audio import AudioError, preprocess
from .config import Settings
from .embedding import Embedder
from .matching import compute_centroid
from .models import Speaker, VoiceSample

log = logging.getLogger("voiceid.demo")

AUDIO_EXT = {".wav", ".flac", ".mp3", ".webm", ".ogg", ".m4a"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def is_active():
    """SQL condition: the speaker hasn't expired yet (or never expires)."""
    return or_(Speaker.expires_at.is_(None), Speaker.expires_at > now())


async def delete_expired(session: AsyncSession) -> int:
    """Delete every expired enrollment (their voice samples go with them). Returns how many."""
    result = await session.execute(
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
    """Allow at most `limit` requests per client IP in any 60-second window (in memory).

    Good enough for a single-instance demo. Several instances would share the count
    in Redis instead, like the portfolio API's contact form does.
    """

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        cutoff = time.monotonic() - self.window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(time.monotonic())
            return True


def client_ip(request: Request, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """FastAPI dependency for the expensive endpoints (enroll, add samples, identify)."""
    settings: Settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    if not limiter.allow(client_ip(request, settings.trust_proxy_headers)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests from you in the last minute. Please wait a moment and try again.",
        )


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
            if await session.scalar(select(Speaker.id).where(Speaker.name == person.name)):
                continue
            vectors, seconds = [], []
            for clip in sorted(f for f in person.iterdir() if f.suffix.lower() in AUDIO_EXT):
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
