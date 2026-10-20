"""Glue between HTTP uploads, audio preprocessing and the embedding model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .audio import AudioError, ClipQuality, PreparedAudio, preprocess
from .config import Settings
from .demo import is_active
from .embedding import Embedder
from .liveness import ChallengeStore, Transcriber, phrase_match
from .matching import Candidate
from .models import Speaker
from .schemas import LivenessOut


@dataclass(frozen=True)
class ClipEmbedding:
    filename: str
    vector: np.ndarray
    speech_seconds: float
    transcript: str | None = None  # only when a transcriber was given
    quality: ClipQuality | None = None


def get_embedder(request: Request) -> Embedder:
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model is still loading, try again shortly.")
    return embedder


def get_transcriber(request: Request) -> Transcriber:
    transcriber = getattr(request.app.state, "transcriber", None)
    if transcriber is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Speech-to-text is still loading, try again shortly.")
    return transcriber


def get_challenges(request: Request) -> ChallengeStore:
    return request.app.state.challenges


async def read_upload(upload: UploadFile, settings: Settings) -> bytes:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"'{upload.filename}' is larger than {settings.max_upload_mb} MB.",
        )
    return data


async def prepare_upload(
    upload: UploadFile, settings: Settings, max_seconds: float | None = None, min_speech: float | None = None
) -> PreparedAudio:
    """Read one uploaded file and decode + clean it up (in a worker thread)."""
    data = await read_upload(upload, settings)
    try:
        # FFmpeg + the neural networks are CPU-bound, so they run in worker
        # threads and do not block the event loop for other requests.
        return await run_in_threadpool(
            preprocess,
            data,
            settings.min_speech_seconds if min_speech is None else min_speech,
            max_seconds or settings.max_clip_seconds,
        )
    except AudioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{upload.filename}: {exc}") from exc


async def embed_upload(
    upload: UploadFile, embedder: Embedder, settings: Settings, transcriber: Transcriber | None = None
) -> ClipEmbedding:
    """Read one uploaded file, clean it up and return its voiceprint (and transcript, if asked)."""
    prepared = await prepare_upload(upload, settings)
    vector = await run_in_threadpool(embedder.embed, prepared.samples)
    # Speech-to-text hears the whole clip, pauses included, not the trimmed speech.
    transcript = await run_in_threadpool(transcriber.transcribe, prepared.decoded) if transcriber else None
    return ClipEmbedding(upload.filename or "clip", vector, prepared.speech_seconds, transcript, prepared.quality)


async def live_clip(
    request: Request,
    file: UploadFile,
    challenge_id: str | None,
    embedder: Embedder,
    settings: Settings,
    challenges: ChallengeStore,
) -> tuple[ClipEmbedding, LivenessOut | None]:
    """Embed the clip and, if a phrase was handed out, check that the clip says it.

    With liveness on (the default) a phrase is required, so an old recording of
    someone can't be played back to pass as them.
    """
    phrase = None
    if challenge_id:
        # Used up right away, even if the audio turns out to be unusable: one phrase, one try.
        phrase = await challenges.take(challenge_id)
        if phrase is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "This phrase has expired or was already used. Get a new one and record again.",
            )
    elif settings.require_liveness:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Liveness check required: get a phrase from GET /challenge, say it in your clip "
            "and send its challenge_id.",
        )

    transcriber = get_transcriber(request) if phrase else None
    clip = await embed_upload(file, embedder, settings, transcriber)
    if phrase is None:
        return clip, None
    heard = clip.transcript or ""
    match = phrase_match(phrase, heard)
    return clip, LivenessOut(
        passed=match >= settings.liveness_min_match, phrase=phrase, heard=heard, match=round(match, 2)
    )


def failed_liveness_reason(liveness: LivenessOut) -> str:
    return f'Liveness check failed: the clip should say "{liveness.phrase}" but we heard "{liveness.heard}".'


async def nearest_speakers(session: AsyncSession, vector: np.ndarray, top_k: int) -> list[Candidate]:
    """The top_k enrolled speakers closest to a voiceprint, best first.

    pgvector does the nearest-neighbour search inside PostgreSQL. `<=>` is
    cosine *distance* (1 - cosine similarity), so smaller is closer.
    """
    distance = Speaker.embedding.cosine_distance(vector.tolist()).label("distance")
    rows = await session.exec(
        select(Speaker.id, Speaker.name, distance).where(is_active()).order_by(distance).limit(top_k)
    )
    return [Candidate(sid, name, round(1.0 - float(d), 4)) for sid, name, d in rows.all()]


async def embed_uploads(uploads: list[UploadFile], embedder: Embedder, settings: Settings) -> list[ClipEmbedding]:
    if not uploads:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Upload at least one voice sample.")
    if len(uploads) > settings.max_files_per_request:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"At most {settings.max_files_per_request} files per request.",
        )
    return [await embed_upload(u, embedder, settings) for u in uploads]
