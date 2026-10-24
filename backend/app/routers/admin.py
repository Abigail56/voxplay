"""The admin page: everything about players, games and turns, and a few clean-up actions.

Only players named in ADMIN_USERNAMES get in. Admins see every player's place name,
including the ones hidden from other players, so keep that list short. The map
only gets the coordinates of players who share their location.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlmodel import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import CurrentUser
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active
from ..models import GamePlay, Speaker, User
from ..schemas import AdminOverview, AdminPlay, AdminPlayer, AdminRoom
from .accounts import is_admin, on_map
from .rooms import RoomsDep

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def require_admin(user: CurrentUser, settings: SettingsDep) -> User:
    if not is_admin(user, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only.")
    return user


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def online_cutoff(settings: Settings) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=settings.online_seconds)


@router.get("/overview", response_model=AdminOverview)
async def overview(session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> AdminOverview:
    users = (await session.exec(select(User))).all()
    voiced = set((await session.exec(select(Speaker.id).where(is_active()))).all())
    player_voices = {u.speaker_id for u in users if u.speaker_id}
    # Only players' turns (rows from before accounts existed have no user).
    by_players = GamePlay.user_id.is_not(None)
    turns, points, cheats = (
        await session.exec(
            select(
                func.count(),
                func.coalesce(func.sum(GamePlay.points), 0),
                func.count().filter(GamePlay.live_passed.is_(False)),
            ).where(by_players)
        )
    ).one()
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today = (await session.exec(select(func.count()).where(by_players, GamePlay.created_at >= midnight))).one()
    all_rooms = await rooms.all()
    cutoff = online_cutoff(settings)
    return AdminOverview(
        players=len(users),
        online=sum(1 for u in users if u.last_seen_at and u.last_seen_at > cutoff),
        with_voice=sum(1 for u in users if u.speaker_id in voiced),
        countries=len({u.country for u in users if u.country}),
        lab_speakers=len(voiced - player_voices),
        games_live=sum(1 for r in all_rooms if r.status != "finished"),
        games_total=len(all_rooms),
        turns_total=int(turns),
        turns_today=int(today),
        cheat_attempts=int(cheats),
        points_total=int(points),
    )


@router.get("/players", response_model=list[AdminPlayer])
async def players(session: SessionDep, settings: SettingsDep, rooms: RoomsDep) -> list[AdminPlayer]:
    users = (await session.exec(select(User).order_by(User.created_at.desc()))).all()
    voiced = set((await session.exec(select(Speaker.id).where(is_active()))).all())
    stats = {
        uid: (int(p), int(t), int(c))
        for uid, p, t, c in (
            await session.exec(
                select(
                    GamePlay.user_id,
                    func.sum(GamePlay.points),
                    func.count(),
                    func.count().filter(GamePlay.live_passed.is_(False)),
                ).group_by(GamePlay.user_id)
            )
        ).all()
    }
    room_of = {p.user_id: r.code for r in await rooms.all() if r.status != "finished" for p in r.players}
    cutoff = online_cutoff(settings)
    return [
        AdminPlayer(
            user_id=u.id,
            username=u.username,
            is_admin=is_admin(u, settings),
            online=bool(u.last_seen_at and u.last_seen_at > cutoff),
            has_voice=u.speaker_id in voiced,
            country=u.country,
            place=u.place,
            # Only pins the player shares go on the admin map; a hidden one's coordinates stay on the server.
            lat=u.lat if on_map(u) else None,
            lon=u.lon if on_map(u) else None,
            share_location=u.share_location,
            room_code=room_of.get(u.id),
            total_points=stats.get(u.id, (0, 0, 0))[0],
            turns=stats.get(u.id, (0, 0, 0))[1],
            cheat_attempts=stats.get(u.id, (0, 0, 0))[2],
            created_at=u.created_at,
            last_seen_at=u.last_seen_at,
        )
        for u in users
    ]


@router.get("/plays", response_model=list[AdminPlay])
async def plays(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    cheats_only: bool = False,
) -> list[AdminPlay]:
    query = select(GamePlay, User.username).join(User, GamePlay.user_id == User.id)
    if cheats_only:
        query = query.where(GamePlay.live_passed.is_(False))
    rows = (await session.exec(query.order_by(GamePlay.created_at.desc(), GamePlay.id.desc()).limit(limit))).all()
    return [
        AdminPlay(
            id=p.id,
            username=name,
            room_code=p.room_code,
            mode=p.mode,
            points=p.points,
            live_passed=p.live_passed,
            created_at=p.created_at,
        )
        for p, name in rows
    ]


@router.get("/rooms", response_model=list[AdminRoom])
async def all_rooms(session: SessionDep, rooms: RoomsDep) -> list[AdminRoom]:
    names = dict((await session.exec(select(User.id, User.username))).all())
    return [
        AdminRoom(
            code=r.code,
            host=names.get(r.host_id, "?"),
            mode=r.mode,
            status=r.status,
            players=[p.username for p in r.players],
            turn=r.turn_index,
            turns_total=len(r.plan),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in await rooms.all()
    ]


@router.post("/rooms/{code}/end", response_model=AdminRoom)
async def end_room(code: str, session: SessionDep, rooms: RoomsDep) -> AdminRoom:
    """Stop a game now (e.g. someone left it stuck). Scores so far are kept."""
    async with rooms.lock(code):
        room = await rooms.get(code)
        if room is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such game.")
        room.status = "finished"
        await rooms.save(room)
    host = (await session.exec(select(User.username).where(User.id == room.host_id))).first() or "?"
    return AdminRoom(
        code=room.code,
        host=host,
        mode=room.mode,
        status=room.status,
        players=[p.username for p in room.players],
        turn=room.turn_index,
        turns_total=len(room.plan),
        created_at=room.created_at,
        updated_at=room.updated_at,
    )


@router.delete("/players/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(user_id: int, request: Request, admin: CurrentUser, session: SessionDep, rooms: RoomsDep) -> Response:
    """Delete a player with their voice, turns and place (e.g. an offensive name)."""
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use 'Delete player' on your own card to delete yourself.")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such player.")
    await rooms.leave_everywhere(user.id)
    if user.speaker_id is not None:
        await session.exec(delete(Speaker).where(Speaker.id == user.speaker_id))
    await session.delete(user)
    await session.commit()
    await request.app.state.store.publish("dashboard", "changed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
