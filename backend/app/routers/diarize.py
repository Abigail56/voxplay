from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active, rate_limit
from ..diarization import diarize
from ..embedding import Embedder, embed_all
from ..models import Speaker
from ..schemas import DiarizeOut, SegmentOut, TalkTimeOut
from ..services import get_embedder, prepare_upload

router = APIRouter(tags=["diarize"])


@router.post("/diarize", response_model=DiarizeOut, dependencies=[Depends(rate_limit)])
async def who_spoke_when(
    session: Annotated[AsyncSession, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="A recording with one or more people talking.")],
) -> DiarizeOut:
    """Who spoke when? Splits a recording into segments, each labelled with a speaker.

    People who aren't enrolled come back as "Unknown 1", "Unknown 2", ... This labels
    whose voice a recording *sounds like*; it can't prove anyone was there live.
    """
    prepared = await prepare_upload(file, settings, max_seconds=settings.max_diarize_seconds)

    # Every enrolled voiceprint is compared with every window, so load them once.
    # (Fine for a demo-sized database; thousands of speakers would query pgvector per window.)
    speakers = (await session.exec(select(Speaker.id, Speaker.name, Speaker.embedding).where(is_active()))).all()

    segments = await run_in_threadpool(
        diarize,
        prepared.decoded,
        lambda clips: embed_all(embedder, clips),
        speakers,
        settings.diarize_threshold,
        settings.diarize_window_seconds,
        settings.diarize_window_seconds / 2,
    )

    seconds: dict[str, float] = defaultdict(float)
    for s in segments:
        seconds[s.label] += s.end - s.start
    total = sum(seconds.values()) or 1.0
    first = {s.label: s for s in reversed(segments)}  # any segment of each label, for id/is_match
    talk_time = [
        TalkTimeOut(
            label=label,
            speaker_id=first[label].speaker_id,
            is_match=first[label].is_match,
            seconds=round(secs, 1),
            share=round(secs / total, 3),
        )
        for label, secs in sorted(seconds.items(), key=lambda kv: -kv[1])
    ]
    return DiarizeOut(
        duration_seconds=prepared.original_seconds,
        threshold=settings.diarize_threshold,
        segments=[SegmentOut(**vars(s)) for s in segments],
        talk_time=talk_time,
    )
