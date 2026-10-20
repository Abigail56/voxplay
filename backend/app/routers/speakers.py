from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import delete_expired, is_active, rate_limit
from ..embedding import Embedder
from ..matching import compute_centroid
from ..models import Speaker, User, VoiceSample
from ..schemas import SpeakerOut
from ..services import embed_uploads, get_embedder

router = APIRouter(prefix="/speakers", tags=["speakers"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def _sample_count(session: AsyncSession, speaker_id: int) -> int:
    return (await session.exec(select(func.count()).where(VoiceSample.speaker_id == speaker_id))).one()


def _out(speaker: Speaker, count: int) -> SpeakerOut:
    return SpeakerOut(
        id=speaker.id,
        name=speaker.name,
        sample_count=count,
        consent_given_at=speaker.consent_given_at,
        created_at=speaker.created_at,
        is_sample=speaker.is_sample,
        expires_at=speaker.expires_at,
    )


async def _get_or_404(session: AsyncSession, speaker_id: int) -> Speaker:
    speaker = (await session.exec(select(Speaker).where(Speaker.id == speaker_id, is_active()))).first()
    if speaker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Speaker not found.")
    return speaker


async def _forbid_protected(session: AsyncSession, speaker: Speaker) -> None:
    if speaker.is_sample:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Built-in sample voices can't be changed or deleted.")
    if (await session.exec(select(User.id).where(User.speaker_id == speaker.id))).first():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This voice belongs to a game account. Its owner can change or delete it there."
        )


@router.post(
    "", response_model=SpeakerOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)]
)
async def enroll_speaker(
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    name: Annotated[str, Form(min_length=1, max_length=100)],
    consent: Annotated[bool, Form(description="The person agreed to have their voiceprint stored.")],
    files: Annotated[list[UploadFile], File(description="One or more voice samples (3 x 5-10 s works well).")],
) -> SpeakerOut:
    """Enroll a new person from one or more voice samples."""
    if not consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Consent is required: voiceprints are biometric data, enroll only people who agree.",
        )
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name must not be blank.")

    if settings.demo_retention_hours > 0:
        # Free up names (and space) held by enrollments that have already expired.
        await delete_expired(session)
    if settings.max_active_enrollments > 0:
        visitors = (
            await session.exec(
                select(func.count()).select_from(Speaker).where(Speaker.is_sample.is_(False), is_active())
            )
        ).one()
        if visitors >= settings.max_active_enrollments:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The demo is full right now. Enrollments are deleted automatically, so please try again later.",
            )
    if (await session.exec(select(Speaker.id).where(func.lower(Speaker.name) == name.lower()))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"A speaker called '{name}' already exists.")
    if (await session.exec(select(User.id).where(User.username == name.lower()))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"'{name}' is a game player's name. Pick another one.")

    clips = await embed_uploads(files, embedder, settings)

    enrolled_at = datetime.now(timezone.utc)
    speaker = Speaker(
        name=name,
        embedding=compute_centroid([c.vector for c in clips]).tolist(),
        consent_given_at=enrolled_at,
        expires_at=(
            enrolled_at + timedelta(hours=settings.demo_retention_hours) if settings.demo_retention_hours > 0 else None
        ),
        samples=[VoiceSample(embedding=c.vector.tolist(), speech_seconds=c.speech_seconds) for c in clips],
    )
    session.add(speaker)
    await session.commit()
    await session.refresh(speaker)
    return _out(speaker, len(clips))


@router.post("/{speaker_id}/samples", response_model=SpeakerOut, dependencies=[Depends(rate_limit)])
async def add_samples(
    speaker_id: int,
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    files: Annotated[list[UploadFile], File()],
) -> SpeakerOut:
    """Add more samples to an existing speaker (improves accuracy)."""
    speaker = await _get_or_404(session, speaker_id)
    await _forbid_protected(session, speaker)
    clips = await embed_uploads(files, embedder, settings)

    for c in clips:
        session.add(VoiceSample(speaker_id=speaker.id, embedding=c.vector.tolist(), speech_seconds=c.speech_seconds))
    await session.flush()

    all_vectors = (await session.exec(select(VoiceSample.embedding).where(VoiceSample.speaker_id == speaker.id))).all()
    speaker.embedding = compute_centroid(all_vectors).tolist()
    await session.commit()
    return _out(speaker, len(all_vectors))


@router.get("", response_model=list[SpeakerOut])
async def list_speakers(session: SessionDep) -> list[SpeakerOut]:
    rows = await session.exec(
        select(Speaker, func.count(VoiceSample.id))
        .outerjoin(VoiceSample)
        .where(is_active())
        .group_by(Speaker.id)
        .order_by(Speaker.created_at.desc(), Speaker.id.desc())
    )
    return [_out(speaker, count) for speaker, count in rows.all()]


@router.get("/{speaker_id}", response_model=SpeakerOut)
async def get_speaker(speaker_id: int, session: SessionDep) -> SpeakerOut:
    speaker = await _get_or_404(session, speaker_id)
    return _out(speaker, await _sample_count(session, speaker.id))


@router.delete("/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker(speaker_id: int, session: SessionDep) -> Response:
    """Permanently delete a speaker and all their voiceprints (right to be forgotten)."""
    speaker = await _get_or_404(session, speaker_id)
    await _forbid_protected(session, speaker)
    await session.delete(speaker)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
