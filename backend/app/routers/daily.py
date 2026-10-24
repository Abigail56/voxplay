"""The daily challenge, and this week's leaderboards (country vs country, the weekly cup)."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.concurrency import run_in_threadpool

from .. import daily
from ..adaptation import learn
from ..auth import CurrentUser
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import rate_limit
from ..embedding import Embedder
from ..liveness import phrase_match
from ..matching import cosine_similarity
from ..models import DailyAttempt, GamePlay, GameResult, User
from ..schemas import (
    CountryScore,
    DailyAttemptOut,
    DailyEntry,
    DailyOut,
    LeaderboardsOut,
    WeeklyEntry,
)
from ..services import get_embedder, get_transcriber, nearest_speakers, prepare_upload
from .accounts import active_speaker

router = APIRouter(tags=["daily"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def daily_state(session: AsyncSession, user: User, last: DailyAttemptOut | None = None) -> DailyOut:
    day = daily.today()
    mine = (await session.exec(select(DailyAttempt).where(DailyAttempt.user_id == user.id, DailyAttempt.day == day))).all()
    days = (await session.exec(select(DailyAttempt.day).where(DailyAttempt.user_id == user.id).distinct())).all()
    board = (
        await session.exec(
            select(User.username, User.country, func.max(DailyAttempt.score).label("best"))
            .join(User, DailyAttempt.user_id == User.id)
            .where(DailyAttempt.day == day)
            .group_by(User.username, User.country)
            .order_by(func.max(DailyAttempt.score).desc(), User.username)
            .limit(20)
        )
    ).all()
    return DailyOut(
        day=day,
        phrase=daily.phrase_for(day),
        attempts_left=max(0, daily.ATTEMPTS_PER_DAY - len(mine)),
        best=max((a.score for a in mine), default=None),
        streak=daily.streak(days, day),
        ends_in_seconds=daily.seconds_left(day),
        leaderboard=[DailyEntry(username=n, country=c, score=s) for n, c, s in board],
        last_attempt=last,
    )


@router.get("/daily", response_model=DailyOut)
async def get_daily(user: CurrentUser, session: SessionDep) -> DailyOut:
    """Today's tongue-twister, your tries left, your streak and today's leaderboard."""
    return await daily_state(session, user)


@router.post("/daily", response_model=DailyOut, dependencies=[Depends(rate_limit)])
async def try_daily(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    file: Annotated[UploadFile, File(description="You, saying today's phrase.")],
) -> DailyOut:
    """Say today's phrase in your own voice. Score = how much you sound like you x how much of it you said."""
    speaker = await active_speaker(session, user)
    if speaker is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Enroll your voice first, so the game can recognise you.")
    day = daily.today()
    used = (await session.exec(select(func.count()).where(DailyAttempt.user_id == user.id, DailyAttempt.day == day))).one()
    if used >= daily.ATTEMPTS_PER_DAY:
        raise HTTPException(status.HTTP_409_CONFLICT, "That's your 3 tries for today. Come back tomorrow for a new phrase!")

    prepared = await prepare_upload(file, settings)
    transcriber = get_transcriber(request)
    vector = await run_in_threadpool(embedder.embed, prepared.samples)
    heard = await run_in_threadpool(transcriber.transcribe, prepared.decoded)
    match = phrase_match(daily.phrase_for(day), heard)
    voice = cosine_similarity(vector, speaker.embedding)
    points = daily.score(voice, match)
    if match >= 0.8:  # they really said today's phrase: a genuine try worth learning from
        others = [c for c in await nearest_speakers(session, vector, 3) if c.speaker_id != speaker.id]
        impostor = others[0].score if others else None
        if voice >= settings.learn_min_score and (impostor is None or voice > impostor):
            await learn(session, speaker.id, vector, prepared.speech_seconds, settings.max_learned_samples)
    if match < daily.MIN_PHRASE_MATCH:
        message = f"We only heard {round(match * 100)}% of today's phrase. Say the whole thing!"
    else:
        message = f"{points} points! You said {round(match * 100)}% of the phrase and sounded {max(0, round(voice * 100))}% like you."
    session.add(DailyAttempt(user_id=user.id, day=day, score=points, voice_score=round(voice, 4), phrase_match=round(match, 2)))
    await session.commit()
    await request.app.state.store.publish("dashboard", "changed")
    last = DailyAttemptOut(score=points, voice_score=round(voice, 4), phrase_match=round(match, 2), heard=heard, message=message)
    return await daily_state(session, user, last)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())  # Monday


async def week_points(session: AsyncSession, start: date) -> dict[int, int]:
    """Points per player in the week starting `start`: game turns + each day's best daily score.

    Solo play doesn't count here: the weekly cup is for playing people."""
    begin = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end = begin + timedelta(days=7)
    points: dict[int, int] = defaultdict(int)
    games = await session.exec(
        select(GamePlay.user_id, func.sum(GamePlay.points))
        .where(
            GamePlay.user_id.is_not(None),
            GamePlay.created_at >= begin,
            GamePlay.created_at < end,
            GamePlay.mode.not_like("solo_%"),
        )
        .group_by(GamePlay.user_id)
    )
    for uid, pts in games.all():
        points[uid] += int(pts)
    best_per_day = (
        select(DailyAttempt.user_id, DailyAttempt.day, func.max(DailyAttempt.score).label("best"))
        .where(DailyAttempt.day >= start, DailyAttempt.day < start + timedelta(days=7))
        .group_by(DailyAttempt.user_id, DailyAttempt.day)
    )
    for uid, _, best in (await session.exec(best_per_day)).all():
        points[uid] += int(best)
    return points


async def week_wins(session: AsyncSession, start: date) -> dict[int, int]:
    begin = datetime.combine(start, time.min, tzinfo=timezone.utc)
    rows = await session.exec(
        select(GameResult.user_id, func.count())
        .where(GameResult.rank == 1, GameResult.finished_at >= begin, GameResult.finished_at < begin + timedelta(days=7))
        .group_by(GameResult.user_id)
    )
    return dict(rows.all())


@router.get("/leaderboards", response_model=LeaderboardsOut)
async def leaderboards(user: CurrentUser, session: SessionDep) -> LeaderboardsOut:
    """This week: country vs country, the weekly cup's Top 8, and last week's champion."""
    this_week = week_start(daily.today())
    users = {u.id: u for u in (await session.exec(select(User))).all()}

    def entries(points: dict[int, int], wins: dict[int, int]) -> list[WeeklyEntry]:
        rows = [
            WeeklyEntry(username=users[uid].username, country=users[uid].country, points=pts, wins=wins.get(uid, 0))
            for uid, pts in points.items()
            if uid in users and pts > 0
        ]
        return sorted(rows, key=lambda e: (-e.points, -e.wins, e.username))

    points, wins = await week_points(session, this_week), await week_wins(session, this_week)
    by_country: dict[str, list[int]] = defaultdict(list)
    for uid, pts in points.items():
        if uid in users and users[uid].country and pts > 0:
            by_country[users[uid].country].append(pts)
    countries = sorted(
        (CountryScore(country=c, points=sum(p), players=len(p)) for c, p in by_country.items()),
        key=lambda c: -c.points,
    )
    last = entries(await week_points(session, this_week - timedelta(days=7)), await week_wins(session, this_week - timedelta(days=7)))
    end = datetime.combine(this_week + timedelta(days=7), time.min, tzinfo=timezone.utc)
    return LeaderboardsOut(
        week_start=this_week,
        week_ends_in_seconds=max(0, int((end - datetime.now(timezone.utc)).total_seconds())),
        countries=countries,
        weekly_top=entries(points, wins)[:8],
        last_week_champion=last[0] if last else None,
    )
