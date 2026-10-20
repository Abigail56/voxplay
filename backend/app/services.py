"""Glue between HTTP uploads, audio preprocessing and the embedding model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from .audio import AudioError, preprocess
from .config import Settings
from .embedding import Embedder


@dataclass(frozen=True)
class ClipEmbedding:
    filename: str
    vector: np.ndarray
    speech_seconds: float


def get_embedder(request: Request) -> Embedder:
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model is still loading, try again shortly.")
    return embedder


async def embed_upload(upload: UploadFile, embedder: Embedder, settings: Settings) -> ClipEmbedding:
    """Read one uploaded file, clean it up and return its voiceprint."""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"'{upload.filename}' is larger than {settings.max_upload_mb} MB.",
        )

    def work() -> ClipEmbedding:
        # FFmpeg + the neural network are CPU-bound, so they run in a worker
        # thread and do not block the event loop for other requests.
        prepared = preprocess(data, settings.min_speech_seconds, settings.max_clip_seconds)
        return ClipEmbedding(upload.filename or "clip", embedder.embed(prepared.samples), prepared.speech_seconds)

    try:
        return await run_in_threadpool(work)
    except AudioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{upload.filename}: {exc}") from exc


async def embed_uploads(uploads: list[UploadFile], embedder: Embedder, settings: Settings) -> list[ClipEmbedding]:
    if not uploads:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Upload at least one voice sample.")
    if len(uploads) > settings.max_files_per_request:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"At most {settings.max_files_per_request} files per request.",
        )
    return [await embed_upload(u, embedder, settings) for u in uploads]
