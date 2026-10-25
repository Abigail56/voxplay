"""The players' dashboard, voice twins and live updates."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from sqlmodel import func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import CurrentUser, user_id_from_token
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active
from ..models import BrainClashResult, GamePlay, Speaker, User, VoiceSample
from ..schemas import (
    DashboardOut,
    DashboardPlay,
    DashboardPlayer,
    DashboardRoom,
    MapSampleOut,
    MapSpeakerOut,
    TwinOut,
    VoiceMapOut,
)
from ..voice_map import voice_map
from .accounts import on_map
from .rooms import RoomsDep

router = APIRouter(tags=["game"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def forget_old_locations(session: AsyncSession, settings: Settings) -> None:
    """Where each turn was played from is deleted after LOCATION_RETENTION_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.location_retention_days)
    await session.exec(update(GamePlay).where(GamePlay.created_at < cutoff).values(lat=None, lon=None))
    await session.commit()


@router.get("/stats")
async def stats(session: SessionDep, settings: SettingsDep) -> dict[str, int]:
    """Public live numbers for the landing page: players online now, players in all, matches and turns played.
    Real counts only (no names), so the site never shows made-up activity."""
    since = datetime.now(timezone.utc) - timedelta(seconds=settings.online_seconds)
    count = lambda q: session.scalar(q)  # noqa: E731
    return {
        "online": await count(select(func.count()).select_from(User).where(User.last_seen_at > since)) or 0,
        "players": await count(select(func.count()).select_from(User)) or 0,
        "matches": await count(select(func.count()).select_from(BrainClashResult)) or 0,
        "turns": await count(select(func.count()).select_from(GamePlay)) or 0,
    }


GAME_FOR_MODE = {"battle": "brain-clash", "quickfire": "brain-clash", "namefast": "brain-clash", "association": "brain-clash", "hum": "beat-drop", "story": "story-forge"}


@router.get("/results")
async def results(session: SessionDep, limit: int = 8) -> list[dict]:
    """Public: the latest finished team matches (Brain Clash, Beat Drop, Story Forge), newest first.
    Team names and scores only, never player names, so it's safe on the landing page."""
    rows = (await session.exec(select(BrainClashResult).order_by(BrainClashResult.finished_at.desc()).limit(min(max(limit, 1), 20)))).all()
    return [
        {
            "id": r.id,
            "game": GAME_FOR_MODE.get(r.mode, "brain-clash"),
            "team_a": r.team_a,
            "team_b": r.team_b,
            "score_a": r.score_a,
            "score_b": r.score_b,
            "winner": r.winner,
            "rounds": r.rounds_played,
            "finished_at": r.finished_at,
        }
        for r in rows
    ]


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(user: CurrentUser, session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> DashboardOut:
    """Everyone who plays: who's online, where (if they share it), their games and scores."""
    await forget_old_locations(session, settings)

    users = (await session.exec(select(User).order_by(User.username))).all()
    voiced = set((await session.exec(select(Speaker.id).where(is_active()))).all())
    totals = {
        uid: (int(points), int(turns))
        for uid, points, turns in (
            await session.exec(
                select(GamePlay.user_id, func.sum(GamePlay.points), func.count()).group_by(GamePlay.user_id)
            )
        ).all()
    }
    live_rooms = [r for r in await rooms.all() if r.status != "finished"]
    room_of = {p.user_id: r for r in live_rooms for p in r.players}
    online_since = datetime.now(timezone.utc) - timedelta(seconds=settings.online_seconds)

    players = []
    for u in users:
        shared = on_map(u)
        room = room_of.get(u.id)
        points, turns = totals.get(u.id, (0, 0))
        players.append(
            DashboardPlayer(
                user_id=u.id,
                username=u.username,
                online=bool(u.last_seen_at and u.last_seen_at > online_since),
                has_voice=u.speaker_id in voiced,
                country=u.country,
                place=u.place if shared else None,
                lat=u.lat if shared else None,
                lon=u.lon if shared else None,
                room_code=room.code if room else None,
                room_status=room.status if room else None,
                total_points=points,
                turns=turns,
            )
        )
    players.sort(key=lambda p: (not p.online, -p.total_points, p.username))

    names = {u.id: u.username for u in users}
    plays = (
        await session.exec(
            select(GamePlay, User.username)
            .join(User, GamePlay.user_id == User.id)
            .order_by(GamePlay.created_at.desc(), GamePlay.id.desc())
            .limit(20)
        )
    ).all()
    return DashboardOut(
        me=user.id,
        online=sum(p.online for p in players),
        players=players,
        rooms=[
            DashboardRoom(
                code=r.code,
                host=names.get(r.host_id, "?"),
                mode=r.mode,
                status=r.status,
                players=[p.username for p in r.players],
                turn=r.turn_index,
                turns_total=len(r.plan),
            )
            for r in live_rooms
        ],
        recent_plays=[
            DashboardPlay(username=name, room_code=p.room_code, mode=p.mode, points=p.points, created_at=p.created_at)
            for p, name in plays
        ],
    )


@router.get("/voice-twins", response_model=VoiceMapOut)
async def voice_twins(user: CurrentUser, session: SessionDep) -> VoiceMapOut:
    """Who sounds like whom: every player's voice (and each of their clips) as a point on a 2D map.

    Players only, not the voice-lab speakers. Only map positions and similarity scores
    are returned, never the voiceprints themselves.
    """
    players = (
        await session.exec(
            select(Speaker.id, User.username, Speaker.embedding).join(User, User.speaker_id == Speaker.id).where(is_active())
        )
    ).all()
    ids = [sid for sid, _, _ in players]
    samples = (
        await session.exec(
            select(VoiceSample.speaker_id, VoiceSample.embedding).where(VoiceSample.speaker_id.in_(ids)).order_by(VoiceSample.id)
        )
    ).all()
    points, dots = voice_map(players, samples)
    return VoiceMapOut(
        me=user.speaker_id if user.speaker_id in ids else None,
        speakers=[
            MapSpeakerOut(
                speaker_id=p.speaker_id,
                name=p.name,
                x=p.x,
                y=p.y,
                consistency=p.consistency,
                twin=TwinOut(speaker_id=p.twin.speaker_id, name=p.twin.name, score=p.twin.score) if p.twin else None,
            )
            for p in points
        ],
        samples=[MapSampleOut(speaker_id=d.speaker_id, x=d.x, y=d.y) for d in dots],
    )


async def mark_seen(websocket: WebSocket, user_id: int) -> None:
    async with websocket.app.state.sessionmaker() as session:
        await session.exec(update(User).where(User.id == user_id).values(last_seen_at=datetime.now(timezone.utc)))
        await session.commit()


@router.websocket("/ws")
async def live(
    websocket: WebSocket, token: str = "", room: str | None = None, bc: str | None = None, screen: str = ""
) -> None:
    """Live updates for the dashboard and (optionally) one room.

    The server only says *what* changed ({"type": "dashboard"} or {"type": "room"});
    the browser then fetches the new state over plain HTTP. With `bc=<code>` it also passes on changes
    to that Brain Clash room as {"type": "brain_clash"}. Emoji reactions come
    through as they are: {"type": "reaction", "reaction": "🔥", "from": "ada"}. Messages come through
    the shared store's pub/sub, so a change made on any API instance arrives here.
    The browser sends {"type": "ping"} every 15 s, which keeps the player "online".

    A party screen connects with `bc=<code>&screen=<the host's screen key>` instead of a token: it hears
    only that room, and doesn't count as a player.
    """
    user_id = user_id_from_token(token, websocket.app.state.jwt_secret)
    on_screen = None
    if user_id is None and bc and screen:
        on_screen = await websocket.app.state.bc_rooms.get(bc)
        if on_screen is not None and not on_screen.screen_key_ok(screen):
            on_screen = None
    if user_id is None and on_screen is None:
        await websocket.close(code=4401)  # 4401: "please sign in again"
        return
    await websocket.accept()
    store = websocket.app.state.store
    if on_screen is not None:
        channels = [f"bc:{bc.upper()}"]
    else:
        channels = ["dashboard"] + ([f"room:{room.upper()}"] if room else []) + ([f"bc:{bc.upper()}"] if bc else [])

    async def forward(events) -> None:
        async for channel, message in events:
            if message.startswith("{"):  # an emoji reaction: pass it on as it is
                await websocket.send_json({"type": "reaction", **json.loads(message)})
            else:
                kind = "room" if channel.startswith("room:") else "brain_clash" if channel.startswith("bc:") else "dashboard"
                await websocket.send_json({"type": kind})

    async def receive() -> None:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping" and user_id is not None:
                await mark_seen(websocket, user_id)

    # Listen first, then say we're here, so no update can slip through in between.
    async with store.subscribe(*channels) as events:
        if user_id is not None:
            await mark_seen(websocket, user_id)
            await store.publish("dashboard", "changed")  # someone came online
        tasks = [asyncio.create_task(forward(events)), asyncio.create_task(receive())]
        try:
            # Ends when the browser goes away (receive fails) or sending fails.
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
