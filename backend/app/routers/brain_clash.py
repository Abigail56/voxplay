"""Brain Clash rooms: create, join, pick teams, play, answer by voice or text.

The same rooms run Beat Drop (mode "hum"), Story Forge (mode "story") and Word Bomb (mode "bomb");
a room keeps to the game it was opened for.

Rooms live in Redis like Who's Talking? rooms, and every change is published on `bc:<code>`,
which the /ws WebSocket passes on as {"type": "brain_clash"}. Browsers then fetch the room again.
Players need a VOXPLAY account, but not a recorded voice.
"""

import base64
import json
import random
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.concurrency import run_in_threadpool

from .. import brain_clash as bc
from .. import fairplay
from ..audio import AudioError, preprocess
from ..auth import CurrentUser
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import rate_limit
from ..models import BrainClashQuestion, BrainClashResult, User
from ..rooms import REACTIONS
from ..services import get_transcriber, prepare_upload, read_upload

router = APIRouter(prefix="/brain-clash", tags=["brain clash"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "data" / "brain_clash_questions.json"
HUM_CLIP_SECONDS = 600  # a Beat Drop hum is kept only while the round can still play it


def get_rooms(request: Request) -> bc.BrainClashStore:
    return request.app.state.bc_rooms


RoomsDep = Annotated[bc.BrainClashStore, Depends(get_rooms)]


async def seed_questions(sessionmaker: async_sessionmaker[AsyncSession], path: Path = QUESTIONS_FILE) -> int:
    """Copy the question bank file into the database (the file wins). Questions removed from the file are retired."""
    questions = json.loads(path.read_text(encoding="utf-8"))["questions"]
    async with sessionmaker() as session:
        for q in questions:
            await session.merge(BrainClashQuestion(**bc.Question(**q).model_dump(), active=q.get("active", True)))
        ids = {q["id"] for q in questions}
        for row in (await session.exec(select(BrainClashQuestion).where(BrainClashQuestion.active))).all():
            if row.id not in ids:
                row.active = False
                session.add(row)
        await session.commit()
    return len(questions)


async def question_pool(session: AsyncSession, settings: bc.RoomSettings) -> list[bc.Question]:
    query = select(BrainClashQuestion).where(BrainClashQuestion.active, BrainClashQuestion.kind == bc.KIND_FOR_MODE[settings.mode])
    if settings.categories:
        query = query.where(BrainClashQuestion.category.in_(settings.categories))
    rows = (await session.exec(query)).all()
    return [bc.Question.model_validate(r, from_attributes=True) for r in rows]


# ---------- what players see ----------


class QuestionOut(BaseModel):
    id: str
    kind: str
    category: str
    category_name: str
    difficulty: str
    prompt: str
    target: int | None = None
    points: int
    spark: str | None = None  # Story Forge: the word every line must use this round


class FlagOut(BaseModel):
    id: str
    round: int
    user_id: int
    player: str
    team: bc.TeamId
    kind: str
    said: str
    reasons: list[str]
    suspicion: float
    held: int  # points waiting for the decision
    status: str
    you_decide: bool  # this viewer can allow or void it


class RevealOut(BaseModel):
    answer: str
    explanation: str | None = None
    source: str | None = None
    as_of: str | None = None
    more: list[str] = []  # Name It Fast / Word Association: other answers that would have counted


class RoundOut(BaseModel):
    number: int
    phase: bc.Phase
    question: QuestionOut
    opened_at: datetime
    closes_at: datetime  # Word Bomb, while the fuse burns: the latest it can blow, not when it will
    fuse_from: datetime | None = None  # Word Bomb: the earliest it can blow, when screens start asking "boom yet?"
    turn_team: bc.TeamId | None
    attempts: dict[str, int]
    found: dict[str, list[str]]  # your team's items (both teams' once the round is over)
    found_count: dict[str, int]
    scored: dict[str, int]
    winner_team: bc.TeamId | None
    reveal_until: datetime | None
    tiebreak: bool
    you_tried: bool
    performer_id: int | None = None  # Beat Drop's hummer, Story Forge's writer
    has_clip: bool = False
    line: str | None = None
    fires: int = 0
    you_fired: bool = False
    flag_id: str | None = None
    reveal: RevealOut | None = None  # only once the round is over


class PlayerOut(bc.Player):
    online: bool = False


class RoomOut(BaseModel):
    code: str
    host_id: int
    status: bc.Status
    game_no: int
    settings: bc.RoomSettings
    players: list[PlayerOut]
    scores: dict[str, int]
    round: RoundOut | None
    rounds_total: int
    feed: list[bc.FeedItem]
    history: list[bc.RoundSummary]
    winner: str | None
    finish_reason: str | None
    notice: str | None
    game: str  # brain-clash | beat-drop | story-forge | word-bomb
    streaks: dict[str, int]
    flags: list[FlagOut]
    story: list[bc.StoryLine]
    opener: str | None
    server_time: datetime  # so screens can correct for a wrong clock
    you: int
    screen_key: str | None = None  # the host's key to open the party screen


class AnswerOut(BaseModel):
    room: RoomOut
    feedback: bc.FeedItem


def out(room: bc.BrainClashRoom, viewer: int, online: set[int] = frozenset()) -> RoomOut:
    me = room.player(viewer)
    r = room.round
    round_out = None
    if r is not None:
        q = r.question
        over = r.phase == "reveal"
        found = {t: [q.items[i][0] for i in r.found[t]] if over or (me and me.team == t) else [] for t in ("A", "B")}
        reveal = None
        if over:
            played = r.found["A"] + r.found["B"]
            more = [] if q.kind == "song" else [it[0] for i, it in enumerate(q.items) if i not in played and it[0] not in room.used_words][:12]
            reveal = RevealOut(answer=q.answer, explanation=q.explanation, source=q.source, as_of=q.as_of, more=more)
        # Beat Drop: only the hummer sees the song until the reveal.
        secret = q.kind == "song" and not over and viewer != r.performer_id
        prompt = "🤫 Only the hummer knows the song" if secret else q.prompt
        # Word Bomb: the real fuse stays on the server, so nobody can read it off the network.
        fuse_from, closes_at = bc.fuse_window(room) if room.settings.mode == "bomb" and r.phase == "open" else (None, r.closes_at)
        round_out = RoundOut(
            number=r.number,
            phase=r.phase,
            question=QuestionOut(
                id=q.id,
                kind=q.kind,
                category=q.category,
                category_name=bc.ALL_CATEGORIES.get(q.category, q.category),
                difficulty=q.difficulty,
                prompt=prompt,
                target=bc.list_target(q) if q.kind == "list" else None,
                points=(
                    room.settings.scoring.list_item if q.kind == "list"
                    else room.settings.scoring.spark if q.kind == "spark"
                    else room.settings.scoring.bomb_word if q.kind == "chunk"
                    else bc.question_points(room, q)
                ),
                spark=q.answer if q.kind == "spark" else None,
            ),
            opened_at=r.opened_at,
            closes_at=closes_at,
            fuse_from=fuse_from,
            turn_team=r.turn_team,
            attempts=r.attempts,
            found=found,
            found_count={t: len(r.found[t]) for t in ("A", "B")},
            scored=r.scored,
            winner_team=r.winner_team,
            reveal_until=r.reveal_until,
            tiebreak=r.tiebreak,
            you_tried=viewer in r.tried,
            performer_id=r.performer_id,
            has_clip=r.has_clip,
            line=r.line,
            fires=len(r.fired),
            you_fired=viewer in r.fired,
            flag_id=r.flag_id,
            reveal=reveal,
        )
    # Name It Fast: until the round is over, the other team's answers stay hidden (no copying).
    feed = []
    for f in room.feed:
        hidden = room.settings.mode == "namefast" and r and f.round == r.number and r.phase != "reveal" and (not me or f.team != me.team)
        feed.append(f.model_copy(update={"said": "…", "items": []}) if hidden else f)
    return RoomOut(
        code=room.code,
        host_id=room.host_id,
        status=room.status,
        game_no=room.game_no,
        settings=room.settings,
        players=[PlayerOut(**p.model_dump(), online=p.user_id in online) for p in room.players],
        scores=room.scores,
        round=round_out,
        rounds_total=room.rounds_total(),
        feed=feed,
        history=room.history,
        winner=room.winner,
        finish_reason=room.finish_reason,
        notice=room.notice,
        game=bc.GAME_FOR_MODE[room.settings.mode],
        streaks=room.streaks,
        flags=[flag_out(room, f, viewer) for f in room.flags],
        story=room.story,
        opener=room.opener,
        server_time=bc.now(),
        you=viewer,
        screen_key=room.screen_key if viewer == room.host_id else None,
    )


def can_decide(room: bc.BrainClashRoom, flag: bc.Flag, viewer: int) -> bool:
    """The host decides, unless the host is the one flagged: then the other team does."""
    judge = room.player(viewer)
    if flag.status != "pending" or judge is None:
        return False
    return judge.team != flag.team if flag.user_id == room.host_id else viewer == room.host_id


def flag_out(room: bc.BrainClashRoom, f: bc.Flag, viewer: int) -> FlagOut:
    return FlagOut(**f.model_dump(exclude={"held", "held_players"}), held=sum(f.held.values()), you_decide=can_decide(room, f, viewer))


async def online_ids(session: AsyncSession, room: bc.BrainClashRoom, settings: Settings) -> set[int]:
    since = datetime.now(timezone.utc) - timedelta(seconds=settings.online_seconds)
    ids = [p.user_id for p in room.players]
    rows = await session.exec(select(User.id).where(User.id.in_(ids), User.last_seen_at > since))
    return set(rows.all())


async def view(session: AsyncSession, settings: Settings, room: bc.BrainClashRoom, viewer: int) -> RoomOut:
    return out(room, viewer, await online_ids(session, room, settings))


async def get_or_404(rooms: bc.BrainClashStore, code: str) -> bc.BrainClashRoom:
    room = await rooms.get(code)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No Brain Clash room with the code {code.upper()}. Check the code and try again.")
    return room


def host_only(room: bc.BrainClashRoom, user: User) -> None:
    if room.host_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the host can do that.")


def member(room: bc.BrainClashRoom, user: User) -> bc.Player:
    player = room.player(user.id)
    if player is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Join this room first.")
    return player


def rules(action):
    """Run a game move, turning a broken rule into a friendly HTTP error."""
    try:
        return action()
    except bc.GameError as exc:
        raise HTTPException(exc.status, str(exc)) from None


async def save_change(session: AsyncSession, rooms: bc.BrainClashStore, room: bc.BrainClashRoom, was: str) -> None:
    """Save the room, and keep the result in the database the moment a match finishes."""
    await rooms.save(room)
    if was == "playing" and room.status == "finished":
        s = room.settings
        session.add(
            BrainClashResult(
                room_code=room.code,
                game_no=room.game_no,
                mode=s.mode,
                categories=s.categories,
                team_a=s.team_names["A"],
                team_b=s.team_names["B"],
                rounds_played=len(room.history),
                **outcome(room),
            )
        )
        await session.commit()


def outcome(room: bc.BrainClashRoom) -> dict:
    """The parts of a saved result that a flag decided after the final whistle can still change."""
    return {
        "score_a": room.scores["A"],
        "score_b": room.scores["B"],
        "winner": room.winner or "draw",
        "players": [{"user_id": p.user_id, "name": p.name, "team": p.team, "points": p.points} for p in room.players],
        "flags": [f.model_dump(include={"round", "user_id", "player", "kind", "reasons", "suspicion", "status"}) for f in room.flags],
    }


# ---------- requests ----------


class CreateIn(BaseModel):
    settings: bc.RoomSettings = Field(default_factory=bc.RoomSettings)
    name: str | None = Field(default=None, min_length=2, max_length=20)  # display name in this room


class JoinIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=20)
    team: bc.TeamId | None = None


class TeamIn(BaseModel):
    user_id: int
    team: bc.TeamId


def check_settings(settings: bc.RoomSettings) -> bc.RoomSettings:
    offered = bc.GAME_CATEGORIES[bc.GAME_FOR_MODE[settings.mode]]
    unknown = [c for c in settings.categories if c not in offered]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown categories: {', '.join(unknown)}")
    names = {t: (settings.team_names.get(t) or bc.DEFAULT_TEAM_NAMES[t]).strip()[:24] for t in ("A", "B")}
    return settings.model_copy(update={"team_names": names})


def display_name(name: str | None, user: User) -> str:
    return (name or user.nickname or user.username).strip()[:20] or user.username


# ---------- endpoints ----------


@router.get("/categories")
async def categories(session: SessionDep, game: str = "brain-clash") -> list[dict]:
    """A game's categories (brain-clash, beat-drop, story-forge or word-bomb) with how many active challenges each has for each mode."""
    if game not in bc.GAME_CATEGORIES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No game called {game}.")
    rows = (await session.exec(select(BrainClashQuestion.category, BrainClashQuestion.kind).where(BrainClashQuestion.active))).all()
    counts = Counter(rows)
    modes = {m: k for m, k in bc.KIND_FOR_MODE.items() if bc.GAME_FOR_MODE[m] == game}
    return [{"id": cid, "name": name, "counts": {mode: counts[(cid, kind)] for mode, kind in modes.items()}} for cid, name in bc.GAME_CATEGORIES[game].items()]


@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
async def create_room(body: CreateIn, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """Open a Brain Clash room. Share its code (e.g. NOVA-42) or link so friends can join."""
    host = bc.Player(user_id=user.id, name=display_name(body.name, user), team="A")
    room = await rooms.create(host, check_settings(body.settings))
    return await view(session, settings, room, user.id)


@router.get("/rooms/{code}", response_model=RoomOut)
async def get_room(code: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    return await view(session, settings, await get_or_404(rooms, code), user.id)


async def screen_room(rooms: bc.BrainClashStore, code: str, key: str) -> bc.BrainClashRoom:
    room = await get_or_404(rooms, code)
    if not room.screen_key_ok(key):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This party-screen link has expired. Ask the host for a new one.")
    return room


@router.get("/rooms/{code}/screen", response_model=RoomOut)
async def get_screen(code: str, key: str, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """The party screen: the room as a spectator sees it (no secrets: no hummer's song, no team's hidden list).
    Opened with the host's screen key instead of a sign-in, so a TV needs no account."""
    return await view(session, settings, await screen_room(rooms, code, key), 0)


@router.post("/rooms/{code}/join", response_model=RoomOut, dependencies=[Depends(rate_limit)])
async def join(code: str, body: JoinIn, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """Join a room (or come back to it after a disconnect: your team and points are kept)."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        player = room.player(user.id)
        if player is None:
            if room.status == "playing":
                raise HTTPException(status.HTTP_409_CONFLICT, "This match has already started. Join the next one!")
            if len(room.players) >= bc.MAX_PLAYERS:
                raise HTTPException(status.HTTP_409_CONFLICT, f"This room is full ({bc.MAX_PLAYERS} players).")
            room.players.append(bc.Player(user_id=user.id, name=display_name(body.name, user), team=body.team or bc.pick_team(room)))
            await rooms.save(room)
        elif body.name and room.status != "playing":
            player.name = display_name(body.name, user)
            await rooms.save(room)
    return await view(session, settings, room, user.id)


@router.post("/rooms/{code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave(code: str, user: CurrentUser, session: SessionDep, rooms: RoomsDep) -> None:
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        if room.player(user.id) is None:
            return
        was = room.status
        bc.remove_player(room, user.id)
        if room.players:
            await save_change(session, rooms, room, was)
        else:
            await rooms.delete(room.code)


@router.patch("/rooms/{code}/settings", response_model=RoomOut)
async def change_settings(
    code: str, body: bc.RoomSettings, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep
) -> RoomOut:
    """The host picks the mode, categories, rounds, timer, win score and team names."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        host_only(room, user)
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "The match is already running.")
        if bc.GAME_FOR_MODE[body.mode] != bc.GAME_FOR_MODE[room.settings.mode]:
            raise HTTPException(status.HTTP_409_CONFLICT, "This room plays a different game. Open a new room for that one.")
        room.settings = check_settings(body)
        await rooms.save(room)
    return await view(session, settings, room, user.id)


@router.post("/rooms/{code}/team", response_model=RoomOut)
async def set_team(code: str, body: TeamIn, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """Before the match: players switch their own team; the host can move anyone."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        member(room, user)
        if body.user_id != user.id:
            host_only(room, user)
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "Teams are locked while the match is running.")
        target = room.player(body.user_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That player isn't in this room.")
        target.team = body.team
        await rooms.save(room)
    return await view(session, settings, room, user.id)


@router.post("/rooms/{code}/shuffle", response_model=RoomOut)
async def shuffle_teams(code: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """The host deals everyone into two even teams at random."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        host_only(room, user)
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "Teams are locked while the match is running.")
        order = list(room.players)
        random.SystemRandom().shuffle(order)
        for i, p in enumerate(order):
            p.team = "A" if i % 2 == 0 else "B"
        await rooms.save(room)
    return await view(session, settings, room, user.id)


@router.post("/rooms/{code}/start", response_model=RoomOut)
async def start(code: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """The host starts the match (or a rematch with the same teams)."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        host_only(room, user)
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "The match is already running.")
        pool = await question_pool(session, room.settings)
        rules(lambda: bc.start_game(room, pool))
        await rooms.save(room)
    return await view(session, settings, room, user.id)


@router.post("/rooms/{code}/answer", response_model=AnswerOut, dependencies=[Depends(rate_limit)])
async def answer(
    code: str,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    rooms: RoomsDep,
    round_number: Annotated[int, Form(alias="round", description="The round on screen when you answered")],
    answer_id: Annotated[str, Form(pattern=r"^[A-Za-z0-9_-]{8,64}$", description="A fresh random id for every answer")],
    text: Annotated[str | None, Form(max_length=300, description="A typed answer (Story Forge: the line)")] = None,
    file: Annotated[UploadFile | None, File(description="A spoken answer (instead of text)")] = None,
    away_ms: Annotated[int, Form(ge=0, le=3_600_000, description="Fair play: ms the game was hidden since the question appeared")] = 0,
    pasted: Annotated[bool, Form(description="Fair play: the answer was pasted")] = False,
    typing_ms: Annotated[int | None, Form(ge=0, le=3_600_000, description="Fair play: first key press to Send")] = None,
) -> AnswerOut:
    """Answer the question on screen, by text or by voice. The server checks it and keeps the score.

    Voice answers are turned into text with Whisper and the recording is discarded straight away.
    A few facts about how the answer was given feed the fair-play detector (see fairplay.py).
    """
    received = datetime.now(timezone.utc)  # the clock stops when the answer arrives, not after speech-to-text
    store = request.app.state.store
    if await store.incr(f"bc:answer:{answer_id}", 3600) > 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "That answer was already sent.")
    if await store.incr(f"bc:rate:{user.id}:{int(time.time())}", 2) > 3:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down! One answer at a time.")
    room = await get_or_404(rooms, code)
    player = member(room, user)
    rules(lambda: bc.eligible(room, player))  # fail fast, before the slow speech-to-text

    if file is not None:
        prepared = await prepare_upload(file, settings, max_seconds=20, min_speech=0.2)
        q = room.round.question
        if q.kind == "spark":
            hint = f"A story about {q.answer}."  # so the spark word comes out spelled right
        else:
            same_category = (await session.exec(select(BrainClashQuestion).where(BrainClashQuestion.category == q.category))).all()
            hint = bc.vocabulary_hint(q, [bc.Question.model_validate(r, from_attributes=True) for r in same_category])
        said = await run_in_threadpool(get_transcriber(request).transcribe, prepared.decoded, hint)
    else:
        said = text or ""
    signals = fairplay.Signals(away_ms=away_ms, pasted=pasted, typing_ms=typing_ms, voice=file is not None)

    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        was = room.status
        feedback = rules(lambda: bc.submit_answer(room, user.id, said, round_number, received, signals))
        await save_change(session, rooms, room, was)
    return AnswerOut(room=await view(session, settings, room, user.id), feedback=feedback)


@router.post("/rooms/{code}/advance", response_model=RoomOut)
async def advance(code: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """Time's up, or on to the next question. Any player's screen calls this when its countdown ends; the
    server checks its own clock. Between rounds the host may skip ahead."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        member(room, user)
        was = room.status
        rules(lambda: bc.advance(room, bc.now(), by_host=room.host_id == user.id))
        await save_change(session, rooms, room, was)
    return await view(session, settings, room, user.id)


@router.post("/rooms/{code}/screen/advance", response_model=RoomOut)
async def screen_advance(code: str, key: str, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """The party screen's "time's up?", so the match moves on even when every phone is locked. Like a
    player's screen, it can only move a round on once the server's own clock says its time is over."""
    async with rooms.lock(code):
        room = await screen_room(rooms, code, key)
        was = room.status
        rules(lambda: bc.advance(room, bc.now(), by_host=False))
        await save_change(session, rooms, room, was)
    return await view(session, settings, room, 0)


@router.post("/rooms/{code}/end", response_model=RoomOut)
async def end(code: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """The host ends the match now. The team ahead wins (level scores: a draw)."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        host_only(room, user)
        if room.status != "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "The match isn't running.")
        bc.finish(room, "Ended by the host")
        await save_change(session, rooms, room, "playing")
    return await view(session, settings, room, user.id)


# ---------- Beat Drop, Story Forge, fair play and reactions ----------


def hum_key(room: bc.BrainClashRoom, round_number: int) -> str:
    return f"bchum:{room.code}:{room.game_no}:{round_number}"


@router.post("/rooms/{code}/hum", response_model=RoomOut, dependencies=[Depends(rate_limit)])
async def hum(
    code: str,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    rooms: RoomsDep,
    round_number: Annotated[int, Form(alias="round")],
    file: Annotated[UploadFile, File(description="The hum: up to 15 seconds")],
) -> RoomOut:
    """Beat Drop: the hummer sends their hum. It plays on every screen for this round only (kept 10
    minutes at most). Whisper listens to it too: a title said out loud instead of hummed is flagged."""
    received = datetime.now(timezone.utc)
    room = await get_or_404(rooms, code)
    member(room, user)
    r = room.round
    if room.settings.mode != "hum" or r is None or r.phase != "hum" or r.number != round_number or r.performer_id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "It's not your turn to hum.")
    data = await read_upload(file, settings)
    try:
        prepared = await run_in_threadpool(preprocess, data, 0.5, 15)
    except AudioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"We couldn't hear a hum: {exc}") from exc
    heard = await run_in_threadpool(get_transcriber(request).transcribe, prepared.decoded)
    await request.app.state.store.put(
        hum_key(room, round_number), json.dumps({"type": file.content_type or "audio/webm", "audio": base64.b64encode(data).decode()}), HUM_CLIP_SECONDS
    )
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        rules(lambda: bc.submit_hum(room, user.id, round_number, heard, received))
        await rooms.save(room)
    return await view(session, settings, room, user.id)


@router.get("/rooms/{code}/hum")
async def hum_clip(code: str, request: Request, user: CurrentUser, rooms: RoomsDep) -> Response:
    """Beat Drop: this round's hum, to play."""
    room = await get_or_404(rooms, code)
    member(room, user)
    return await hum_response(request, room)


@router.get("/rooms/{code}/screen/hum")
async def screen_hum_clip(code: str, key: str, request: Request, rooms: RoomsDep) -> Response:
    """Beat Drop: this round's hum, for the party screen's big speaker."""
    return await hum_response(request, await screen_room(rooms, code, key))


async def hum_response(request: Request, room: bc.BrainClashRoom) -> Response:
    raw = await request.app.state.store.get(hum_key(room, room.round.number)) if room.round and room.round.has_clip else None
    if raw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no hum to play right now.")
    clip = json.loads(raw)
    return Response(base64.b64decode(clip["audio"]), media_type=clip["type"], headers={"Cache-Control": "no-store"})


class RoundIn(BaseModel):
    round: int


@router.post("/rooms/{code}/fire", response_model=RoomOut)
async def fire(code: str, body: RoundIn, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """Story Forge: fire 🔥 at the line just written (other team only, once each)."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        rules(lambda: bc.fire(room, user.id, body.round))
        await rooms.save(room)
    return await view(session, settings, room, user.id)


class DecisionIn(BaseModel):
    allow: bool


@router.post("/rooms/{code}/flags/{flag_id}", response_model=RoomOut)
async def decide(code: str, flag_id: str, body: DecisionIn, user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> RoomOut:
    """Fair play: allow a flagged answer (its held points are added) or void it (they're dropped)."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        rules(lambda: bc.decide_flag(room, user.id, flag_id, body.allow))
        await rooms.save(room)
        if room.status == "finished":  # decided after the match: the saved result follows the new score
            saved = (
                await session.exec(select(BrainClashResult).where(BrainClashResult.room_code == room.code, BrainClashResult.game_no == room.game_no))
            ).first()
            if saved:
                for field, value in outcome(room).items():
                    setattr(saved, field, value)
                session.add(saved)
                await session.commit()
    return await view(session, settings, room, user.id)


class ReactIn(BaseModel):
    emoji: str


@router.post("/rooms/{code}/react", status_code=status.HTTP_204_NO_CONTENT)
async def react(code: str, body: ReactIn, request: Request, user: CurrentUser, rooms: RoomsDep) -> Response:
    """Send an emoji that floats across everyone's screen."""
    room = await get_or_404(rooms, code)
    player = member(room, user)
    if body.emoji not in REACTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Pick one of {' '.join(REACTIONS)}")
    store = request.app.state.store
    if await store.incr(f"react:{user.id}:{int(time.time() // 10)}", 10) > 8:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Easy there! Too many reactions.")
    await store.publish(f"bc:{room.code}", json.dumps({"reaction": body.emoji, "from": player.name}))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
