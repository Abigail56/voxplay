import base64
import json
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..adaptation import learn
from ..auth import CurrentUser
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import rate_limit
from ..embedding import Embedder
from ..liveness import ChallengeStore
from ..matching import cosine_similarity, decide
from ..models import GamePlay, GameResult, Speaker, User
from ..rooms import (
    CHAIN_START_POINTS,
    MAX_PLAYERS,
    RATE_SECONDS,
    REACTIONS,
    SPEED_SECONDS,
    VOTE_SECONDS,
    Pending,
    Room,
    RoomPlayer,
    RoomStore,
    Turn,
    apply_turn,
    chain_origin_name,
    crowd_verdict,
    everyone_voted,
    failed_liveness,
    min_players,
    open_rating,
    open_voting,
    pct,
    ranks,
    reveal,
    score_copy,
    score_disguise,
    score_impersonation,
    score_yourself,
    speed_bonus,
    start_game,
    timed_out,
    voters,
    winners,
)
from ..schemas import RateIn, ReactIn, RoomCreateIn, VoteIn
from ..services import get_challenges, get_embedder, live_clip, nearest_speakers
from .accounts import active_speaker, on_map

router = APIRouter(prefix="/rooms", tags=["rooms"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
# Turn clips (Guess Who's mystery clip, the impression being rated, the voice to copy in
# telephone, and the replay) are deleted when no longer needed, or after this at the latest.
CLIP_SECONDS = 60 * 60


def get_rooms(request: Request) -> RoomStore:
    return request.app.state.rooms


RoomsDep = Annotated[RoomStore, Depends(get_rooms)]


class RoomOut(Room):
    # Never sent: the turn order, Guess Who's secrets, ratings before the reveal and voiceprints.
    plan: list[Turn] = Field(default=[], exclude=True)
    votes: dict[int, int] = Field(default={}, exclude=True)
    clip_key: str | None = Field(default=None, exclude=True)
    pending: Pending | None = Field(default=None, exclude=True)
    chain_origin: list[float] | None = Field(default=None, exclude=True)
    chain_last: list[float] | None = Field(default=None, exclude=True)

    current_turn: Turn | None = None  # hidden from everyone but the speaker in Guess Who
    turns_total: int = 0
    you_speak: bool = False  # Guess Who: you're the secret speaker this turn
    voted: list[int] = []  # who has voted or rated (not what)
    my_vote: int | None = None  # your suspect (Guess Who) or your stars (rating)
    has_clip: bool = False  # there's a clip to listen to right now
    deadline: str | None = None  # ISO time the turn runs out (speed rounds, voting, rating)
    deadline_seconds: int | None = None  # how long that phase lasts in total
    winner_ids: list[int] = []


PHASE_SECONDS = {"speak": SPEED_SECONDS, "vote": VOTE_SECONDS, "rate": RATE_SECONDS}


def out(room: Room, viewer_id: int) -> RoomOut:
    """The room as one player may see it. In Guess Who the speaker stays secret until the reveal."""
    turn = room.active_turn()
    secret = room.mode == "guess" and turn is not None
    deadline = room.turn_deadline()
    data = room.model_dump(exclude={"plan", "votes", "clip_key", "pending", "chain_origin", "chain_last"})
    return RoomOut(
        **data,
        current_turn=None if secret and turn.player_id != viewer_id else turn,
        turns_total=len(room.plan),
        you_speak=bool(secret and turn.player_id == viewer_id),
        voted=list(room.votes),
        my_vote=room.votes.get(viewer_id),
        has_clip=room.clip_key is not None,
        deadline=deadline.isoformat() if deadline else None,
        deadline_seconds=PHASE_SECONDS[room.phase] if deadline else None,
        winner_ids=[w.user_id for w in winners(room)] if room.status == "finished" else [],
    )


async def as_player(session: AsyncSession, user: User) -> RoomPlayer:
    speaker = await active_speaker(session, user)
    if speaker is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Enroll your voice first, so the game can recognise you.")
    return RoomPlayer(user_id=user.id, username=user.username, speaker_id=speaker.id, country=user.country)


async def get_or_404(rooms: RoomStore, code: str) -> Room:
    room = await rooms.get(code)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No game with the code {code.upper()}. Check the code and try again.")
    return room


def member(room: Room, user: User) -> None:
    if room.player(user.id) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Join this game first.")


async def leave_other_rooms(rooms: RoomStore, user_id: int, keep: str | None = None) -> None:
    """You can be in one game at a time: joining a new one leaves the old one."""
    other = await rooms.room_of(user_id)
    if other and other.code != keep:
        await rooms.leave(other.code, user_id)


async def improve_voice(session: AsyncSession, settings: Settings, speaker_id: int, clip, candidates) -> None:
    """A real turn (live check passed): learn from it if it was clearly you."""
    own = (await session.exec(select(Speaker.embedding).where(Speaker.id == speaker_id))).first()
    if own is None:
        return
    genuine = cosine_similarity(clip.vector, own)
    impostor = next((c.score for c in candidates if c.speaker_id != speaker_id), None)
    if genuine >= settings.learn_min_score and (impostor is None or genuine > impostor):
        await learn(session, speaker_id, clip.vector, clip.speech_seconds, settings.max_learned_samples)


def record_results(session: AsyncSession, room: Room) -> None:
    """A game just finished: keep everyone's final place (wins, badges, the weekly cup)."""
    places = ranks(room)
    for p in room.players:
        session.add(
            GameResult(
                user_id=p.user_id,
                room_code=room.code,
                game_no=room.game_no,
                mode=room.mode,
                speed=room.speed,
                rank=places[p.user_id],
                points=p.points,
                players=len(room.players),
            )
        )


def play_row(
    user_id: int, speaker_id: int, room: Room, mode: str, points: int, user: User | None, live: bool | None, score: float | None = None
) -> GamePlay:
    shared = user is not None and on_map(user)
    return GamePlay(
        score=round(score, 4) if score is not None else None,
        speaker_id=speaker_id,
        user_id=user_id,
        room_code=room.code,
        mode=mode,
        points=points,
        live_passed=live,
        lat=user.lat if shared else None,
        lon=user.lon if shared else None,
    )


# ---------- turn clips ----------


def clip_key(room: Room, turn_number: int) -> str:
    return f"clip:{room.code}:{room.game_no}:{turn_number}"


def needs_clip(room: Room) -> bool:
    """Does the game itself play this turn's clip to the others (not just the replay)?"""
    return room.mode in ("guess", "telephone") or (room.mode == "impersonate" and room.crowd)


async def put_clip(rooms: RoomStore, key: str, audio: bytes, content_type: str) -> None:
    await rooms.store.put(key, json.dumps({"type": content_type, "audio": base64.b64encode(audio).decode()}), CLIP_SECONDS)


async def clip_response(rooms: RoomStore, key: str | None) -> Response:
    raw = await rooms.store.get(key) if key else None
    if raw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no clip to listen to right now.")
    clip = json.loads(raw)
    return Response(base64.b64decode(clip["audio"]), media_type=clip["type"], headers={"Cache-Control": "no-store"})


async def drop_clips(rooms: RoomStore, room: Room, *keys: str | None) -> None:
    """Without the replay, a clip goes as soon as the game no longer plays it to anyone."""
    if room.replay:
        return
    for key in keys:
        if key and key != room.clip_key:
            await rooms.store.delete(key)


def similarities(vector, room: Room, voices: dict[int, list[float]]) -> dict[str, float]:
    """How much a clip sounds like each player in the room (cosine similarity), best first."""
    sims = {p.username: cosine_similarity(vector, voices[p.speaker_id]) for p in room.players if p.speaker_id in voices}
    return dict(sorted(sims.items(), key=lambda kv: -kv[1]))


async def users_by_id(session: AsyncSession, room: Room) -> dict[int, User]:
    rows = await session.exec(select(User).where(User.id.in_([p.user_id for p in room.players])))
    return {u.id: u for u in rows.all()}


async def finish_reveal(session: AsyncSession, rooms: RoomStore, room: Room) -> None:
    """Guess Who: reveal under the room lock, drop the clip (unless it's kept for the replay), book the points."""
    speaker_id = room.active_turn().player_id
    votes = dict(room.votes)
    key = room.clip_key
    live = room.pending.liveness.passed if room.pending and room.pending.liveness else None
    points = reveal(room, has_clip=room.replay and key is not None)
    await rooms.save(room)
    await drop_clips(rooms, room, key)
    users = await users_by_id(session, room)
    for p in room.players:
        if p.user_id == speaker_id:
            session.add(play_row(p.user_id, p.speaker_id, room, "guess", points.get(p.user_id, 0), users.get(p.user_id), live, room.last_result.score))
        elif p.user_id in votes:
            session.add(play_row(p.user_id, p.speaker_id, room, "guess_vote", points.get(p.user_id, 0), users.get(p.user_id), None))
    if room.status == "finished":
        record_results(session, room)
    await session.commit()


async def finish_rating(session: AsyncSession, rooms: RoomStore, room: Room) -> None:
    """Humans vs AI: add up the stars under the room lock, reveal both verdicts and book the turn."""
    player = room.player(room.active_turn().player_id)
    key = room.clip_key
    live = room.pending.liveness.passed if room.pending and room.pending.liveness else None
    total = crowd_verdict(room, has_clip=room.replay and key is not None)
    await rooms.save(room)
    await drop_clips(rooms, room, key)
    user = (await users_by_id(session, room)).get(player.user_id)
    session.add(play_row(player.user_id, player.speaker_id, room, "impersonate", total, user, live, room.last_result.score))
    if room.status == "finished":
        record_results(session, room)
    await session.commit()


# ---------- endpoints ----------


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
async def create_room(body: RoomCreateIn, user: CurrentUser, session: SessionDep, rooms: RoomsDep) -> RoomOut:
    """Start a new game. Share its code (e.g. TIGER-42) so friends can join from their phones."""
    host = await as_player(session, user)
    await leave_other_rooms(rooms, user.id)
    return out(await rooms.create(host, **body.model_dump()), user.id)


@router.get("/{code}", response_model=RoomOut)
async def get_room(code: str, user: CurrentUser, rooms: RoomsDep) -> RoomOut:
    return out(await get_or_404(rooms, code), user.id)


@router.post("/{code}/join", response_model=RoomOut, dependencies=[Depends(rate_limit)])
async def join_room(code: str, user: CurrentUser, session: SessionDep, rooms: RoomsDep) -> RoomOut:
    player = await as_player(session, user)
    room = await get_or_404(rooms, code)
    await leave_other_rooms(rooms, user.id, keep=room.code)
    async with rooms.lock(room.code):
        room = await get_or_404(rooms, code)
        if room.player(user.id):
            return out(room, user.id)  # already in
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "This game has already started. Join the next one!")
        if len(room.players) >= MAX_PLAYERS:
            raise HTTPException(status.HTTP_409_CONFLICT, f"This game is full ({MAX_PLAYERS} players).")
        room.players.append(player)
        await rooms.save(room)
    return out(room, user.id)


@router.post("/{code}/leave", response_model=RoomOut | None)
async def leave_room(code: str, user: CurrentUser, rooms: RoomsDep) -> RoomOut | None:
    room = await rooms.leave(code, user.id)
    return out(room, user.id) if room else None


@router.patch("/{code}", response_model=RoomOut)
async def change_room(code: str, body: RoomCreateIn, user: CurrentUser, rooms: RoomsDep) -> RoomOut:
    """The host picks the game type, rounds and options before starting."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        if room.host_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the host can change the game.")
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "The game is already running.")
        for field, value in body.model_dump().items():
            setattr(room, field, value)
        await rooms.save(room)
    return out(room, user.id)


@router.post("/{code}/start", response_model=RoomOut)
async def start_room(code: str, user: CurrentUser, rooms: RoomsDep) -> RoomOut:
    """The host starts the game (or a rematch with the same players)."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        if room.host_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the host can start the game.")
        if room.status == "playing":
            raise HTTPException(status.HTTP_409_CONFLICT, "The game is already running.")
        need = min_players(room.mode)
        if len(room.players) < need:
            which = {"guess": " for Guess Who", "telephone": " for Broken telephone"}.get(room.mode, "")
            raise HTTPException(status.HTTP_409_CONFLICT, f"You need at least {need} players{which}. Share the code with friends!")
        start_game(room)
        await rooms.save(room)
    return out(room, user.id)


@router.post("/{code}/turn", response_model=RoomOut, dependencies=[Depends(rate_limit)])
async def take_turn(
    code: str,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    rooms: RoomsDep,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    challenges: Annotated[ChallengeStore, Depends(get_challenges)],
    file: Annotated[UploadFile, File(description="You, saying the line from GET /challenge?kind=line.")],
    challenge_id: Annotated[str, Form(description="From GET /challenge. Game turns always need the phrase.")],
) -> RoomOut:
    """Your turn: send your recording. The server checks the phrase and the voice and scores it."""
    room = await get_or_404(rooms, code)
    turn = room.active_turn()
    if turn is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The game isn't running.")
    if turn.player_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "It's not your turn yet.")
    if room.phase != "speak":
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already recorded. Now the others are having their say!")
    turn_index, received = room.turn_index, time.time()
    player, target = room.player(turn.player_id), room.player(turn.target_id)
    target_name = target.username if target else "the last voice"

    # The slow part (speech-to-text + voice model) runs without holding the room lock.
    clip, liveness = await live_clip(request, file, challenge_id, embedder, settings, challenges)
    failed = liveness is not None and not liveness.passed
    voices = dict(
        (await session.exec(select(Speaker.id, Speaker.embedding).where(Speaker.id.in_([p.speaker_id for p in room.players])))).all()
    )
    sims = {} if failed else similarities(clip.vector, room, voices)
    sounded_like = {name: pct(s) for name, s in sims.items()}
    own = sims.get(player.username)

    # Keep the clip if the game plays it to the others, or for the replay. Never a failed one.
    key = None
    if not failed and (room.replay or needs_clip(room)):
        key = clip_key(room, turn_index + 1)
        await file.seek(0)
        await put_clip(rooms, key, await file.read(), file.content_type or "audio/webm")
    content_type = file.content_type or "audio/webm"

    score, drift = None, None
    if failed:
        points, message = failed_liveness(player.username)
    elif room.mode == "guess":
        # The AI guesses too: which player in the room does the clip sound most like?
        best = next(iter(sims.items()), (None, 0.0))
        ai_guess = best[0] if best[1] >= settings.match_threshold else None
        pending = Pending(liveness=liveness, score=own, sounded_like=sounded_like, ai_guess=ai_guess)
        async with rooms.lock(room.code):
            room = await get_or_404(rooms, code)
            if room.status != "playing" or room.turn_index != turn_index:
                await rooms.store.delete(key)
                raise HTTPException(status.HTTP_409_CONFLICT, "The game moved on while you were recording.")
            open_voting(room, key, content_type, pending)
            await rooms.save(room)
        return out(room, user.id)
    elif room.mode == "yourself":
        candidates = await nearest_speakers(session, clip.vector, settings.top_k)
        decision = decide(candidates, settings.match_threshold, settings.min_margin)
        points, message = score_yourself(player.username, player.speaker_id, decision.speaker_id, decision.label, decision.score)
        score = own
        await improve_voice(session, settings, player.speaker_id, clip, candidates)
    elif room.mode == "disguise":
        candidates = await nearest_speakers(session, clip.vector, settings.top_k)
        decision = decide(candidates, settings.match_threshold, settings.min_margin)
        framed = decision.label if decision.is_match and decision.speaker_id != player.speaker_id else None
        score = own or 0.0
        points, message = score_disguise(player.username, score, framed)
    elif room.mode == "telephone":
        if turn.chain_start:
            points, message = CHAIN_START_POINTS, f"{player.username} starts a chain. Next: copy that voice! {CHAIN_START_POINTS} points."
        else:
            score = cosine_similarity(clip.vector, room.chain_last) if room.chain_last else 0.0
            points, message = score_copy(player.username, target_name, score)
            if room.chain_origin:
                drift = pct(cosine_similarity(clip.vector, room.chain_origin))
                origin = chain_origin_name(room)
                if origin and origin != target_name:
                    message += f" The voice now sounds {drift}% like {origin}, who started it."
    else:
        target_voice = voices.get(target.speaker_id) if target else None
        score = cosine_similarity(clip.vector, target_voice) if target_voice is not None else 0.0
        points, message = score_impersonation(player.username, target_name, score, score >= settings.match_threshold)

    async with rooms.lock(room.code):
        room = await get_or_404(rooms, code)
        if room.status != "playing" or room.turn_index != turn_index:
            await drop_clips(rooms, room, key)
            raise HTTPException(status.HTTP_409_CONFLICT, "The game moved on while you were recording.")
        # The clock stops when the recording arrives, not when the AI has finished listening.
        bonus = speed_bonus(room, points, datetime.fromtimestamp(received, timezone.utc))
        if room.mode == "impersonate" and room.crowd and not failed and voters(room):
            # Humans vs AI: the others rate it first; the AI's verdict waits for the reveal.
            pending = Pending(points=points, message=message, liveness=liveness, score=score, bonus=bonus, sounded_like=sounded_like)
            open_rating(room, key, content_type, pending)
            await rooms.save(room)
            return out(room, user.id)
        old_key = room.clip_key
        if room.mode == "telephone" and not failed:
            room.chain_last = clip.vector.tolist()
            if turn.chain_start:
                room.chain_origin = room.chain_last
            room.clip_key, room.clip_type = key, content_type  # the voice the next player copies
        apply_turn(room, points, message, liveness, bonus, score=score, sounded_like=sounded_like, has_clip=room.replay and key is not None, drift=drift)
        await rooms.save(room)
    await drop_clips(rooms, room, old_key, key)

    live = liveness.passed if liveness else None
    session.add(play_row(user.id, player.speaker_id, room, room.mode, room.last_result.points, user, live, score))
    if room.status == "finished":
        record_results(session, room)
    await session.commit()
    return out(room, user.id)


@router.get("/{code}/clip")
async def get_clip(code: str, user: CurrentUser, rooms: RoomsDep) -> Response:
    """The clip to listen to right now: Guess Who's mystery voice, the impression to rate, or the voice to copy."""
    room = await get_or_404(rooms, code)
    member(room, user)
    return await clip_response(rooms, room.clip_key)


@router.get("/{code}/replay/{turn_number}")
async def get_replay(code: str, turn_number: int, user: CurrentUser, rooms: RoomsDep) -> Response:
    """Play back a finished turn of this game (when the replay is on). Clips are deleted after an hour."""
    room = await get_or_404(rooms, code)
    member(room, user)
    done = room.history[turn_number - 1] if 1 <= turn_number <= len(room.history) else None
    if not room.replay or done is None or not done.has_clip:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no recording of that turn.")
    return await clip_response(rooms, clip_key(room, turn_number))


@router.post("/{code}/vote", response_model=RoomOut)
async def vote(code: str, body: VoteIn, user: CurrentUser, session: SessionDep, rooms: RoomsDep) -> RoomOut:
    """Guess Who: name the player you think spoke. You can change your mind until everyone has voted."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        member(room, user)
        turn = room.active_turn()
        if room.mode != "guess" or turn is None or room.phase != "vote":
            raise HTTPException(status.HTTP_409_CONFLICT, "There's nothing to vote on right now.")
        if user.id == turn.player_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "You're the speaker. Keep a straight face!")
        if room.player(body.suspect_id) is None or body.suspect_id == user.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Vote for another player in this game.")
        room.votes[user.id] = body.suspect_id
        if everyone_voted(room):
            await finish_reveal(session, rooms, room)
        else:
            await rooms.save(room)
    return out(room, user.id)


@router.post("/{code}/rate", response_model=RoomOut)
async def rate(code: str, body: RateIn, user: CurrentUser, session: SessionDep, rooms: RoomsDep) -> RoomOut:
    """Humans vs AI: give the impression 1-5 stars. You can change your mind until everyone has rated."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        member(room, user)
        turn = room.active_turn()
        if turn is None or room.phase != "rate":
            raise HTTPException(status.HTTP_409_CONFLICT, "There's nothing to rate right now.")
        if user.id == turn.player_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "No rating your own impression!")
        room.votes[user.id] = body.stars
        if everyone_voted(room):
            await finish_rating(session, rooms, room)
        else:
            await rooms.save(room)
    return out(room, user.id)


@router.post("/{code}/advance", response_model=RoomOut)
async def advance(code: str, user: CurrentUser, session: SessionDep, rooms: RoomsDep) -> RoomOut:
    """Time's up: any player's screen calls this when the countdown ends. The server checks the clock."""
    async with rooms.lock(code):
        room = await get_or_404(rooms, code)
        member(room, user)
        turn = room.active_turn()
        if turn is None or not timed_out(room):
            raise HTTPException(status.HTTP_409_CONFLICT, "Not yet!")
        if room.phase == "vote":
            await finish_reveal(session, rooms, room)
            return out(room, user.id)
        if room.phase == "rate":
            await finish_rating(session, rooms, room)
            return out(room, user.id)
        name = room.player(turn.player_id).username
        apply_turn(room, 0, f"Time's up! {name} ran out of time. No points.", None)
        await rooms.save(room)
        if room.status == "finished":
            record_results(session, room)
            await session.commit()
    return out(room, user.id)


@router.post("/{code}/react", status_code=status.HTTP_204_NO_CONTENT)
async def react(code: str, body: ReactIn, user: CurrentUser, rooms: RoomsDep) -> Response:
    """Send an emoji that floats across everyone's screen."""
    room = await get_or_404(rooms, code)
    member(room, user)
    if body.emoji not in REACTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Pick one of {' '.join(REACTIONS)}")
    if await rooms.store.incr(f"react:{user.id}:{int(time.time() // 10)}", 10) > 8:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Easy there! Too many reactions.")
    await rooms.store.publish(f"room:{room.code}", json.dumps({"reaction": body.emoji, "from": user.username}))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
