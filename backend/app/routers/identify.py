from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active, rate_limit
from ..embedding import Embedder
from ..matching import Candidate, decide
from ..models import Speaker
from ..schemas import CandidateOut, IdentifyOut
from ..services import embed_upload, get_embedder

router = APIRouter(tags=["identify"])


@router.post("/identify", response_model=IdentifyOut, dependencies=[Depends(rate_limit)])
async def identify(
    session: Annotated[AsyncSession, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="The recording to identify.")],
) -> IdentifyOut:
    """Who is speaking? Returns the best match, or 'unknown' below the threshold."""
    clip = await embed_upload(file, embedder, settings)

    # pgvector does the nearest-neighbour search inside PostgreSQL.
    # `<=>` is cosine *distance* (1 - cosine similarity), so smaller is closer.
    distance = Speaker.embedding.cosine_distance(clip.vector.tolist()).label("distance")
    rows = await session.execute(
        select(Speaker.id, Speaker.name, distance).where(is_active()).order_by(distance).limit(settings.top_k)
    )
    candidates = [Candidate(sid, name, round(1.0 - float(d), 4)) for sid, name, d in rows.all()]

    decision = decide(candidates, settings.match_threshold, settings.min_margin)
    return IdentifyOut(
        label=decision.label,
        is_match=decision.is_match,
        speaker_id=decision.speaker_id,
        score=round(decision.score, 4),
        threshold=settings.match_threshold,
        reason=decision.reason,
        speech_seconds=clip.speech_seconds,
        candidates=[CandidateOut(speaker_id=c.speaker_id, name=c.name, score=c.score) for c in candidates],
    )
