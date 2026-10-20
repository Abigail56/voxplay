from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active, rate_limit
from ..embedding import Embedder
from ..liveness import ChallengeStore
from ..matching import UNKNOWN_LABEL, cosine_similarity, decide
from ..models import Speaker
from ..schemas import CandidateOut, ChallengeOut, IdentifyOut, VerifyOut
from ..services import failed_liveness_reason, get_challenges, get_embedder, live_clip, nearest_speakers

router = APIRouter(tags=["identify"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ChallengesDep = Annotated[ChallengeStore, Depends(get_challenges)]
ChallengeIdForm = Annotated[str | None, Form(description="From GET /challenge. The clip must say its phrase.")]


@router.get("/challenge", response_model=ChallengeOut)
async def new_challenge(challenges: ChallengesDep) -> ChallengeOut:
    """A fresh phrase to say in the next /identify or /verify clip. It works once, for a short time."""
    c = await challenges.issue()
    return ChallengeOut(challenge_id=c.id, phrase=c.phrase, expires_in_seconds=c.expires_in_seconds)


@router.post("/identify", response_model=IdentifyOut, dependencies=[Depends(rate_limit)])
async def identify(
    request: Request,
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    challenges: ChallengesDep,
    file: Annotated[UploadFile, File(description="The recording to identify.")],
    challenge_id: ChallengeIdForm = None,
) -> IdentifyOut:
    """Who is speaking? Returns the best match, or 'unknown' below the threshold.

    With liveness on (the default), the clip must also say the phrase from GET /challenge.
    """
    clip, liveness = await live_clip(request, file, challenge_id, embedder, settings, challenges)
    if liveness and not liveness.passed:
        # Give a possible replay or voice clone nothing to tune itself against: no names, no scores.
        return IdentifyOut(
            label=UNKNOWN_LABEL,
            is_match=False,
            speaker_id=None,
            score=0.0,
            threshold=settings.match_threshold,
            reason=failed_liveness_reason(liveness),
            speech_seconds=clip.speech_seconds,
            candidates=[],
            liveness=liveness,
        )

    candidates = await nearest_speakers(session, clip.vector, settings.top_k)
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
        liveness=liveness,
    )


@router.post("/speakers/{speaker_id}/verify", response_model=VerifyOut, dependencies=[Depends(rate_limit)])
async def verify(
    speaker_id: int,
    request: Request,
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    challenges: ChallengesDep,
    file: Annotated[UploadFile, File(description="The recording to compare with this speaker.")],
    challenge_id: ChallengeIdForm = None,
) -> VerifyOut:
    """How much does this clip sound like one particular person? ("Is this Ada?")

    Used by the voice game, both for "be yourself" turns and for impersonation turns.
    """
    speaker = (await session.exec(select(Speaker).where(Speaker.id == speaker_id, is_active()))).first()
    if speaker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Speaker not found.")

    clip, liveness = await live_clip(request, file, challenge_id, embedder, settings, challenges)
    if liveness and not liveness.passed:
        return VerifyOut(
            speaker_id=speaker.id,
            name=speaker.name,
            score=0.0,
            threshold=settings.match_threshold,
            is_match=False,
            reason=failed_liveness_reason(liveness),
            liveness=liveness,
        )

    score = round(cosine_similarity(clip.vector, speaker.embedding), 4)
    is_match = score >= settings.match_threshold
    return VerifyOut(
        speaker_id=speaker.id,
        name=speaker.name,
        score=score,
        threshold=settings.match_threshold,
        is_match=is_match,
        reason=(
            f"Sounds like {speaker.name}: {score:.3f} is above the threshold {settings.match_threshold:.2f}."
            if is_match
            else f"Doesn't sound enough like {speaker.name}: {score:.3f} is below {settings.match_threshold:.2f}."
        ),
        liveness=liveness,
    )
