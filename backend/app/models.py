from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Index, false, func, true
from sqlmodel import Field, Relationship, SQLModel

from .embedding import EMBEDDING_DIM


class Speaker(SQLModel, table=True):
    """An enrolled person. `embedding` is the centroid of all their samples.

    Privacy by design: we store only voiceprints (192 numbers per clip), never
    the raw recordings.
    """

    __tablename__ = "speakers"
    __table_args__ = (
        # HNSW index for fast cosine-distance search once there are many speakers.
        Index(
            "ix_speakers_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM), nullable=False))
    consent_given_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}
    )
    # Built-in demo voices (public LibriSpeech readers): never expire, can't be deleted by visitors.
    is_sample: bool = Field(default=False, sa_column_kwargs={"server_default": false()})
    # When this enrollment is deleted automatically (None = never). Used by the public demo.
    expires_at: datetime | None = Field(default=None, index=True, sa_type=DateTime(timezone=True))

    samples: list["VoiceSample"] = Relationship(
        back_populates="speaker", sa_relationship_kwargs={"cascade": "all, delete-orphan", "passive_deletes": True}
    )


class VoiceSample(SQLModel, table=True):
    """The embedding of one clip of a speaker (kept so the centroid can be recomputed).

    "enroll" clips come from recording your voice; "game" clips are learned from
    turns where the AI recognised you confidently (see adaptation.py).
    """

    __tablename__ = "voice_samples"

    id: int | None = Field(default=None, primary_key=True)
    speaker_id: int | None = Field(default=None, foreign_key="speakers.id", ondelete="CASCADE", index=True)
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM), nullable=False))
    speech_seconds: float
    source: str = Field(default="enroll", max_length=10, sa_column_kwargs={"server_default": "enroll"})
    created_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}
    )

    speaker: Speaker | None = Relationship(back_populates="samples")


class User(SQLModel, table=True):
    """A voice-game account. Their voice is an ordinary enrolled Speaker (named after them)."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=20, unique=True, index=True)  # lower-case, see schemas.SignupIn
    password_hash: str = Field(max_length=200)
    # Deleting the voice (e.g. from the voice lab) keeps the account; they can enroll again.
    speaker_id: int | None = Field(default=None, foreign_key="speakers.id", ondelete="SET NULL", unique=True)
    # Where they play from: the country and area they gave at sign-up (or detected), and that
    # place's point on the map. Always a place's centre (a neighbourhood or town), never a GPS fix.
    country: str | None = Field(default=None, max_length=2)  # ISO code, e.g. "NG"
    place: str | None = Field(default=None, max_length=120)  # e.g. "Yaba, Lagos"
    # Players can hide their pin from other players (admins still see it).
    share_location: bool = Field(default=True, sa_column_kwargs={"server_default": true()})
    lat: float | None = None
    lon: float | None = None
    location_updated_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    last_seen_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}
    )


class DailyAttempt(SQLModel, table=True):
    """One try at the daily challenge (3 a day; the best one counts)."""

    __tablename__ = "daily_attempts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    day: date = Field(index=True)  # UTC day
    score: int  # 0-100
    voice_score: float  # how much it sounded like you
    phrase_match: float  # how much of today's phrase was said
    created_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}
    )


class GameResult(SQLModel, table=True):
    """Each player's final place in a finished game (wins, badges, the weekly cup)."""

    __tablename__ = "game_results"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    room_code: str = Field(max_length=20)
    game_no: int  # rematches in the same room are new games
    mode: str = Field(max_length=20)
    speed: bool = False
    rank: int  # 1 = winner (ties share a rank)
    points: int
    players: int
    finished_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}, index=True
    )


class GamePlay(SQLModel, table=True):
    """One finished voice-game turn, for the dashboard's feed, totals and map.

    Points are worked out by the server, never sent by the browser. lat/lon are
    only filled in when the player shares their location (rounded, city level).
    Rows go with the user or speaker, and old locations are cleared after
    LOCATION_RETENTION_DAYS.
    """

    __tablename__ = "game_plays"

    id: int | None = Field(default=None, primary_key=True)
    speaker_id: int = Field(foreign_key="speakers.id", ondelete="CASCADE", index=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", ondelete="CASCADE", index=True)
    room_code: str | None = Field(default=None, max_length=20)
    mode: str = Field(max_length=20)
    points: int
    live_passed: bool | None = None  # False = the phrase wasn't said: a replay or a cheat attempt
    lat: float | None = None
    lon: float | None = None
    created_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}, index=True
    )


class ScoreSample(SQLModel, table=True):
    """From one real turn: how close the voice was to its owner, and to the closest other person.

    Only these two numbers are kept (no audio, no voiceprint, no name). Thousands of
    them show how well the AI separates real players on real phones, and where the
    match threshold should sit (see accuracy.py and the admin page).
    """

    __tablename__ = "score_samples"

    id: int | None = Field(default=None, primary_key=True)
    genuine: float  # similarity to the player's own voiceprint
    impostor: float | None  # similarity to the most similar *other* voiceprint
    source: str = Field(max_length=10)  # "game" or "daily"
    created_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()}, index=True
    )


class AppSetting(SQLModel, table=True):
    """Settings an admin changes at runtime (e.g. the match threshold), kept across restarts."""

    __tablename__ = "app_settings"

    key: str = Field(primary_key=True, max_length=50)
    value: str = Field(max_length=200)
