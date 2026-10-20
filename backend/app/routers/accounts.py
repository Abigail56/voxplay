from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import text
from sqlmodel import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import daily
from ..auth import CurrentUser, create_token, hash_password, verify_password
from ..badges import Stats, badges
from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active, rate_limit
from ..embedding import Embedder
from ..geocode import Geocoder, GeocoderUnavailable, Place
from ..matching import compute_centroid
from ..models import DailyAttempt, GamePlay, GameResult, Speaker, User, VoiceSample
from ..rooms import IMPERSONATION_BONUS
from ..adaptation import inconsistent_takes
from ..schemas import BadgeOut, ClipCheckOut, LocationIn, LoginIn, MeOut, PlaceOut, SignupIn, TokenOut
from ..services import embed_uploads, get_embedder, prepare_upload

router = APIRouter(tags=["accounts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_geocoder(request: Request) -> Geocoder:
    return request.app.state.geocoder


GeocoderDep = Annotated[Geocoder, Depends(get_geocoder)]


def is_admin(user: User, settings: Settings) -> bool:
    return user.username in settings.admin_names


MAP_DOWN = "The map service isn't answering right now. Please try again in a moment."


async def find_place(geocoder: Geocoder, place: str, country: str) -> Place:
    try:
        found = await geocoder.search(place.strip(), country)
    except GeocoderUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MAP_DOWN) from None
    if found is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"We couldn't find '{place.strip()}' on the map. Try your town or area, e.g. 'Yaba, Lagos'.",
        )
    return found


def put_on_map(user: User, place: Place) -> None:
    user.country, user.place, user.lat, user.lon = place.country, place.name, place.lat, place.lon
    user.location_updated_at = datetime.now(timezone.utc)


async def active_speaker(session: AsyncSession, user: User) -> Speaker | None:
    if user.speaker_id is None:
        return None
    return (await session.exec(select(Speaker).where(Speaker.id == user.speaker_id, is_active()))).first()


async def me_out(session: AsyncSession, user: User, settings: Settings) -> MeOut:
    speaker = await active_speaker(session, user)
    samples = learned = 0
    if speaker:
        samples, learned = (
            await session.exec(
                select(func.count(), func.count().filter(VoiceSample.source == "game")).where(VoiceSample.speaker_id == speaker.id)
            )
        ).one()
    points, turns = (
        await session.exec(select(func.coalesce(func.sum(GamePlay.points), 0), func.count()).where(GamePlay.user_id == user.id))
    ).one()
    stats = await player_stats(session, user.id)
    return MeOut(
        id=user.id,
        username=user.username,
        is_admin=is_admin(user, settings),
        has_voice=speaker is not None,
        voice_samples=samples,
        learned_samples=learned,
        country=user.country,
        place=user.place,
        share_location=user.share_location,
        lat=user.lat,
        lon=user.lon,
        total_points=int(points),
        turns=int(turns),
        wins=stats.wins,
        badges=[BadgeOut(**vars(b)) for b in badges(stats)],
    )


async def player_stats(session: AsyncSession, user_id: int) -> Stats:
    """Everything the badges need, from the turns, results and daily tries."""
    mine = GamePlay.user_id == user_id
    turns, best, fooled, right = (
        await session.exec(
            select(
                func.count().filter(GamePlay.mode != "guess_vote"),
                func.coalesce(func.max(GamePlay.points).filter(GamePlay.mode == "yourself"), 0),
                func.count().filter(GamePlay.mode == "impersonate", GamePlay.points >= IMPERSONATION_BONUS),
                func.count().filter(GamePlay.mode == "guess_vote", GamePlay.points > 0),
            ).where(mine)
        )
    ).one()
    wins, speed_wins = (
        await session.exec(
            select(func.count().filter(GameResult.rank == 1), func.count().filter(GameResult.rank == 1, GameResult.speed))
            .where(GameResult.user_id == user_id)
        )
    ).one()
    days = (await session.exec(select(DailyAttempt.day).where(DailyAttempt.user_id == user_id).distinct())).all()
    # Countries of everyone in the games you've played (you included).
    countries = (
        await session.exec(
            text(
                "SELECT count(DISTINCT u.country) FROM game_results g JOIN users u ON u.id = g.user_id "
                "WHERE u.country IS NOT NULL AND (g.room_code, g.game_no) IN "
                "(SELECT room_code, game_no FROM game_results WHERE user_id = :uid)"
            ).bindparams(uid=user_id)
        )
    ).one()[0]
    return Stats(
        turns=int(turns),
        best_yourself=int(best),
        fooled=int(fooled),
        wins=int(wins),
        speed_wins=int(speed_wins),
        guesses_right=int(right),
        daily_days=len(days),
        best_streak=daily.best_streak(days),
        countries_met=int(countries or 0),
    )


def on_map(user: User) -> bool:
    """Shown to other players: they gave a place and haven't hidden their pin."""
    return user.share_location and user.lat is not None and user.lon is not None


def token_for(request: Request, user: User, settings: Settings) -> str:
    return create_token(user.id, request.app.state.jwt_secret, settings.token_days)


@router.post("/auth/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
async def signup(
    body: SignupIn, request: Request, session: SessionDep, settings: SettingsDep, geocoder: GeocoderDep
) -> TokenOut:
    """Create a game account, with the country and town or area you play from.

    Next step: enroll your voice with POST /me/voice.
    """
    if (await session.exec(select(User.id).where(User.username == body.username))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"The name '{body.username}' is taken. Try another one.")
    # Your voice will be enrolled under your username, so it can't clash with a voice-lab name.
    if (await session.exec(select(Speaker.id).where(func.lower(Speaker.name) == body.username))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"The name '{body.username}' is taken. Try another one.")
    place = await find_place(geocoder, body.place, body.country)
    user = User(username=body.username, password_hash=hash_password(body.password))
    put_on_map(user, place)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenOut(token=token_for(request, user, settings), user=await me_out(session, user, settings))


@router.post("/auth/login", response_model=TokenOut, dependencies=[Depends(rate_limit)])
async def login(body: LoginIn, request: Request, session: SessionDep, settings: SettingsDep) -> TokenOut:
    user = (await session.exec(select(User).where(User.username == body.username))).first()
    # The same message either way, so nobody can find out which usernames exist.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password.")
    return TokenOut(token=token_for(request, user, settings), user=await me_out(session, user, settings))


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> MeOut:
    return await me_out(session, user, settings)


@router.post("/me/voice", response_model=MeOut, dependencies=[Depends(rate_limit)])
async def enroll_my_voice(
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    consent: Annotated[bool, Form(description="You agree to your voiceprint being stored for the game.")],
    files: Annotated[list[UploadFile], File(description="3 clips of 5-10 s of your normal speaking voice.")],
) -> MeOut:
    """Enroll (or re-record) your voice. Replaces any voice you enrolled before.

    Every take must pass the quality check (long enough, loud enough, clean, not distorted)
    and sound like the other takes, so the voiceprint is built from good material.
    """
    if not consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Consent is required: a voiceprint is biometric data, so we only store it if you agree.",
        )
    if len(files) < settings.min_enroll_clips:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Record {settings.min_enroll_clips} takes of your voice, please."
        )
    taken = (
        await session.exec(
            select(Speaker.id).where(func.lower(Speaker.name) == user.username, Speaker.id != user.speaker_id)
        )
    ).first()
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A voice-lab speaker is already called '{user.username}'.")
    clips = await embed_uploads(files, embedder, settings)
    bad = [f"Take {i}: {c.quality.problems[0]}" for i, c in enumerate(clips, 1) if c.quality and not c.quality.ok]
    if bad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, " ".join(bad))
    odd = inconsistent_takes([c.vector for c in clips], settings.enroll_consistency)
    if odd:
        takes = " and ".join(f"take {i + 1}" for i in odd)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{takes.capitalize()} doesn't sound like the others. Was it someone else, or very noisy? Redo it in your normal voice.",
        )
    now = datetime.now(timezone.utc)
    speaker = await active_speaker(session, user)
    if speaker is None:
        if user.speaker_id is not None:
            # An expired demo enrollment: clear it out so the name is free again.
            await session.exec(delete(Speaker).where(Speaker.id == user.speaker_id))
        speaker = Speaker(name=user.username, embedding=[0.0] * len(clips[0].vector), consent_given_at=now)
        session.add(speaker)
        await session.flush()
        user.speaker_id = speaker.id
    else:
        await session.exec(delete(VoiceSample).where(VoiceSample.speaker_id == speaker.id))
    speaker.embedding = compute_centroid([c.vector for c in clips]).tolist()
    speaker.consent_given_at = now
    speaker.expires_at = now + timedelta(hours=settings.demo_retention_hours) if settings.demo_retention_hours > 0 else None
    for c in clips:
        session.add(VoiceSample(speaker_id=speaker.id, embedding=c.vector.tolist(), speech_seconds=c.speech_seconds))
    session.add(user)
    await session.commit()
    return await me_out(session, user, settings)


@router.post("/me/voice/check", response_model=ClipCheckOut, dependencies=[Depends(rate_limit)])
async def check_take(user: CurrentUser, settings: SettingsDep, file: Annotated[UploadFile, File()]) -> ClipCheckOut:
    """Instant feedback on one take before enrolling: "✓ good", or what to fix ("too quiet…")."""
    # min_speech=0: a too-short take gets the friendly "Too short…" advice, not an error.
    q = (await prepare_upload(file, settings, min_speech=0)).quality
    return ClipCheckOut(ok=q.ok, speech_seconds=q.speech_seconds, loudness_db=q.loudness_db, snr_db=q.snr_db, problems=list(q.problems))


@router.put("/me/location", response_model=MeOut)
async def set_my_location(
    body: LocationIn, request: Request, user: CurrentUser, session: SessionDep, settings: SettingsDep, geocoder: GeocoderDep
) -> MeOut:
    """Move your pin to another place, and/or show or hide it on the other players' map."""
    if body.place:
        put_on_map(user, await find_place(geocoder, body.place, body.country or user.country or ""))
    user.share_location = body.share
    session.add(user)
    await session.commit()
    await request.app.state.store.publish("dashboard", "changed")
    return await me_out(session, user, settings)


@router.get("/places/search", response_model=PlaceOut, dependencies=[Depends(rate_limit)])
async def search_place(
    geocoder: GeocoderDep,
    q: Annotated[str, Query(min_length=2, max_length=120, description="Town or area, e.g. 'Yaba, Lagos'")],
    country: Annotated[str, Query(pattern=r"^[A-Za-z]{2}$")],
) -> PlaceOut:
    """Check a place before signing up: 'We'll put you at Yaba, Lagos'."""
    place = await find_place(geocoder, q, country)
    return PlaceOut(name=place.name, country=place.country, lat=place.lat, lon=place.lon)


@router.get("/places/here", response_model=PlaceOut, dependencies=[Depends(rate_limit)])
async def place_here(
    geocoder: GeocoderDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> PlaceOut:
    """The neighbourhood a GPS point is in ("Use my current location"). The point itself isn't stored."""
    try:
        place = await geocoder.reverse(lat, lon)
    except GeocoderUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MAP_DOWN) from None
    if place is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "We couldn't work out where that is. Type your town instead.")
    return PlaceOut(name=place.name, country=place.country, lat=place.lat, lon=place.lon)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(request: Request, user: CurrentUser, session: SessionDep) -> Response:
    """Delete your account, your voiceprint, your game history and your location. For good."""
    await request.app.state.rooms.leave_everywhere(user.id)
    if user.speaker_id is not None:
        await session.exec(delete(Speaker).where(Speaker.id == user.speaker_id))
    await session.delete(user)
    await session.commit()
    await request.app.state.store.publish("dashboard", "changed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

