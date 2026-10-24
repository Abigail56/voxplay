"""Solo play: no friends online? Play against the built-in voices (LibriSpeech readers).

- Guess the voice: hear a short introduction of each reader, then a mystery clip,
  and pick who it was. The AI picks too, from the same introductions.
- Impersonate a reader, or disguise your own voice, with the same live check as a game turn.

Solo points count towards your level and badges, but not the weekly cup or
country vs country (those are for playing people).
"""

import json
import random
import secrets
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..audio import AudioError, preprocess
from ..auth import CurrentUser
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active, rate_limit, sample_clips, sample_folder
from ..embedding import Embedder
from ..liveness import ChallengeStore
from ..matching import cosine_similarity, decide
from ..models import GamePlay, Speaker, User
from ..rooms import failed_liveness, pct, score_disguise, score_impersonation
from ..schemas import SoloGuessIn, SoloGuessOut, SoloOut, SoloRoundOut, SoloTurnOut, SoloVoice
from ..services import get_challenges, get_embedder, live_clip, nearest_speakers
from .accounts import active_speaker

router = APIRouter(prefix="/solo", tags=["solo"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]

GUESS_POINTS = 30
OPTIONS = 4  # voices to choose from in a round
ROUND_SECONDS = 10 * 60
SOLO_MODES = ("solo_guess", "solo_impersonate", "solo_disguise")

# Voiceprints of the introduction clips, worked out once per API process.
_intros: dict[Path, np.ndarray] = {}


def display_name(name: str) -> str:
    """'LibriSpeech reader 1272' -> 'Reader 1272'. Players' names stay as they are."""
    return name.removeprefix("LibriSpeech ").capitalize() if name.startswith("LibriSpeech ") else name


def voice_out(speaker_id: int, name: str) -> SoloVoice:
    return SoloVoice(speaker_id=speaker_id, name=display_name(name))


async def sample_voices(session: AsyncSession, settings: Settings) -> list[tuple[int, str, list[Path]]]:
    """The built-in voices that have at least 2 recordings on disk (one to introduce them, one to guess)."""
    folder = sample_folder(settings)
    rows = (await session.exec(select(Speaker.id, Speaker.name).where(Speaker.is_sample, is_active()).order_by(Speaker.name))).all()
    voices = [(sid, name, sample_clips(folder, name)) for sid, name in rows]
    return [v for v in voices if len(v[2]) >= 2]


async def my_speaker_id(session: AsyncSession, user: User) -> int:
    speaker = await active_speaker(session, user)
    if speaker is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Enroll your voice first, so the game can recognise you.")
    return speaker.id


def audio_file(path: Path) -> Response:
    media = {".webm": "audio/webm", ".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac", ".m4a": "audio/mp4"}
    return Response(path.read_bytes(), media_type=media.get(path.suffix.lower(), "application/octet-stream"))


async def embed_file(embedder: Embedder, path: Path) -> np.ndarray:
    try:
        prepared = await run_in_threadpool(preprocess, path.read_bytes())
    except AudioError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"A built-in recording is broken: {exc}") from exc
    return await run_in_threadpool(embedder.embed, prepared.samples)


@router.get("", response_model=SoloOut)
async def solo(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> SoloOut:
    """The built-in voices you can play against, and how you've done so far."""
    voices = await sample_voices(session, settings)
    rounds, right, points = (
        await session.exec(
            select(
                func.count(),
                func.count().filter(GamePlay.mode == "solo_guess", GamePlay.points > 0),
                func.coalesce(func.sum(GamePlay.points), 0),
            ).where(GamePlay.user_id == user.id, GamePlay.mode.in_(SOLO_MODES))
        )
    ).one()
    return SoloOut(voices=[voice_out(sid, name) for sid, name, _ in voices], rounds=rounds, right=right, points=int(points))


@router.get("/voices/{speaker_id}/intro")
async def intro(speaker_id: int, user: CurrentUser, session: SessionDep, settings: SettingsDep) -> Response:
    """A built-in voice introducing itself: listen before you guess or impersonate. (Public LibriSpeech audio.)"""
    voice = next((v for v in await sample_voices(session, settings) if v[0] == speaker_id), None)
    if voice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No built-in voice with that id.")
    return audio_file(voice[2][0])


@router.post("/guess", response_model=SoloRoundOut, dependencies=[Depends(rate_limit)])
async def new_guess(request: Request, user: CurrentUser, session: SessionDep, settings: SettingsDep) -> SoloRoundOut:
    """A new 'guess the voice' round: some voices to choose from, and a mystery clip of one of them."""
    voices = await sample_voices(session, settings)
    if len(voices) < 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "There aren't enough built-in voices to play against yet.")
    rng = random.SystemRandom()
    options = rng.sample(voices, min(OPTIONS, len(voices)))
    answer = rng.choice(options)
    mystery = rng.choice(answer[2][1:])  # never the introduction you can listen to
    round_id = secrets.token_urlsafe(12)
    state = {"user": user.id, "answer": answer[0], "options": [v[0] for v in options], "clip": str(mystery)}
    await request.app.state.store.put(f"solo:{round_id}", json.dumps(state), ROUND_SECONDS)
    return SoloRoundOut(round_id=round_id, options=[voice_out(v[0], v[1]) for v in options], expires_in_seconds=ROUND_SECONDS)


async def round_state(request: Request, round_id: str, user: User, take: bool = False) -> dict:
    key = f"solo:{round_id}"
    store = request.app.state.store
    raw = await (store.take(key) if take else store.get(key))
    state = json.loads(raw) if raw else None
    if state is None or state["user"] != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That round is over. Start a new one!")
    return state


@router.get("/guess/{round_id}/clip")
async def guess_clip(round_id: str, request: Request, user: CurrentUser) -> Response:
    """The mystery clip of a 'guess the voice' round."""
    state = await round_state(request, round_id, user)
    return audio_file(Path(state["clip"]))


@router.post("/guess/{round_id}", response_model=SoloGuessOut, dependencies=[Depends(rate_limit)])
async def answer_guess(
    round_id: str, body: SoloGuessIn, request: Request, user: CurrentUser, session: SessionDep, settings: SettingsDep, embedder: EmbedderDep
) -> SoloGuessOut:
    """Your pick. One answer per round."""
    speaker_id = await my_speaker_id(session, user)
    state = await round_state(request, round_id, user, take=True)
    voices = {v[0]: v for v in await sample_voices(session, settings)}
    options = [voices[sid] for sid in state["options"] if sid in voices]
    answer = voices.get(state["answer"])
    if answer is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That voice isn't available any more. Start a new round!")

    # The AI only gets what you got: the introductions, and the mystery clip.
    mystery = await embed_file(embedder, Path(state["clip"]))
    sims = []
    for sid, name, clips in options:
        if clips[0] not in _intros:
            _intros[clips[0]] = await embed_file(embedder, clips[0])
        sims.append((cosine_similarity(mystery, _intros[clips[0]]), sid, name))
    _, ai_id, ai_name = max(sims)

    right = body.speaker_id == answer[0]
    ai_right = ai_id == answer[0]
    points = GUESS_POINTS if right else 0
    who = display_name(answer[1])
    if right:
        message = f"Yes, it was {who}! {points} points." + (" The AI got it too." if ai_right else " The AI didn't. You beat the machine!")
    else:
        message = f"No, it was {who}." + (" The AI got it right." if ai_right else f" The AI was fooled too: it said {display_name(ai_name)}.")
    session.add(GamePlay(speaker_id=speaker_id, user_id=user.id, mode="solo_guess", points=points))
    await session.commit()
    return SoloGuessOut(right=right, answer=voice_out(answer[0], answer[1]), ai_guess=voice_out(ai_id, ai_name), points=points, message=message)


@router.post("/turn", response_model=SoloTurnOut, dependencies=[Depends(rate_limit)])
async def solo_turn(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    embedder: EmbedderDep,
    challenges: Annotated[ChallengeStore, Depends(get_challenges)],
    mode: Annotated[Literal["impersonate", "disguise"], Form()],
    file: Annotated[UploadFile, File(description="You, saying the line from GET /challenge?kind=line.")],
    challenge_id: Annotated[str, Form()],
    speaker_id: Annotated[int | None, Form(description="impersonate: the built-in voice to sound like")] = None,
) -> SoloTurnOut:
    """Impersonate a built-in voice, or disguise your own. Scored like a game turn."""
    own_id = await my_speaker_id(session, user)
    target = None
    if mode == "impersonate":
        target = next((v for v in await sample_voices(session, settings) if v[0] == speaker_id), None)
        if target is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick one of the built-in voices to impersonate.")
    clip, liveness = await live_clip(request, file, challenge_id, embedder, settings, challenges)
    failed = liveness is not None and not liveness.passed

    score, sounded_like = None, {}
    if failed:
        points, message = failed_liveness(user.username)
    else:
        candidates = await nearest_speakers(session, clip.vector, settings.top_k)
        sounded_like = {display_name(c.name): pct(c.score) for c in candidates}
        if mode == "impersonate":
            voice = (await session.exec(select(Speaker.embedding).where(Speaker.id == target[0]))).first()
            score = cosine_similarity(clip.vector, voice)
            points, message = score_impersonation(user.username, display_name(target[1]), score, score >= settings.match_threshold)
        else:
            voice = (await session.exec(select(Speaker.embedding).where(Speaker.id == own_id))).first()
            score = cosine_similarity(clip.vector, voice)
            decision = decide(candidates, settings.match_threshold, settings.min_margin)
            framed = display_name(decision.label) if decision.is_match and decision.speaker_id != own_id else None
            points, message = score_disguise(user.username, score, framed)
    session.add(
        GamePlay(
            speaker_id=own_id,
            user_id=user.id,
            mode=f"solo_{mode}",
            points=points,
            live_passed=liveness.passed if liveness else None,
            score=round(score, 4) if score is not None else None,
        )
    )
    await session.commit()
    return SoloTurnOut(points=points, message=message, score=score, liveness=liveness, sounded_like=sounded_like)
