from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import rate_limit
from ..embedding import Embedder
from ..liveness import ChallengeStore
from ..matching import UNKNOWN_LABEL, decide
from ..schemas import CandidateOut, ChallengeOut, IdentifyOut
from ..services import failed_liveness_reason, get_challenges, get_embedder, live_clip, nearest_speakers

router = APIRouter(tags=["identify"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ChallengesDep = Annotated[ChallengeStore, Depends(get_challenges)]
ChallengeIdForm = Annotated[str | None, Form(description="From GET /challenge. The clip must say its phrase.")]


@router.get("/challenge", response_model=ChallengeOut)
async def new_challenge(
    challenges: ChallengesDep,
    kind: Annotated[Literal["digits", "line"], Query(description="digits for /identify; a silly line for game turns")] = "digits",
) -> ChallengeOut:
    """A fresh phrase to say in the next /identify clip or game turn. It works once, for a short time."""
    c = await challenges.issue(kind)
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

