from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sample_count: int
    consent_given_at: datetime
    created_at: datetime
    is_sample: bool = False
    expires_at: datetime | None = None


class CandidateOut(BaseModel):
    speaker_id: int
    name: str
    score: float


class ChallengeOut(BaseModel):
    challenge_id: str
    phrase: str  # what the person has to say, e.g. "four seven two nine one six" or a silly line
    expires_in_seconds: int


class LivenessOut(BaseModel):
    passed: bool
    phrase: str  # what they were asked to say
    heard: str  # what speech-to-text heard
    match: float  # share of the phrase's words heard in order (0..1)


class IdentifyOut(BaseModel):
    label: str  # the speaker's name, or "unknown"
    is_match: bool
    speaker_id: int | None
    score: float  # cosine similarity of the best candidate (confidence)
    threshold: float
    reason: str
    speech_seconds: float
    candidates: list[CandidateOut]
    liveness: LivenessOut | None = None  # None when no phrase was checked


class TwinOut(BaseModel):
    speaker_id: int
    name: str
    score: float  # cosine similarity of the two voiceprints


class MapSpeakerOut(BaseModel):
    speaker_id: int
    name: str
    x: float  # map position in [-1, 1]
    y: float
    twin: TwinOut | None  # the enrolled voice most similar to this one
    consistency: float | None  # how alike this person's own clips are (0..1)


class MapSampleOut(BaseModel):
    speaker_id: int
    x: float
    y: float


class VoiceMapOut(BaseModel):
    me: int | None  # your speaker_id, so the game can highlight you
    speakers: list[MapSpeakerOut]
    samples: list[MapSampleOut]  # one dot per enrollment clip


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    threshold: float
    speakers: int
    demo_retention_hours: float  # visitor enrollments are deleted after this long (0 = never)
    liveness_required: bool  # /identify needs a phrase from GET /challenge


# ---------- voice game: accounts ----------


class SignupIn(BaseModel):
    # Lower-case letters, digits and _, so names are easy to type and can't look alike ("Ada" vs "ada").
    username: str = Field(pattern=r"^[a-z0-9_]{3,20}$")
    password: str = Field(min_length=8, max_length=200)
    # Where you play from: shown as your pin on the players' map.
    country: str = Field(pattern=r"^[A-Za-z]{2}$", description="ISO country code, e.g. NG")
    place: str = Field(min_length=2, max_length=120, description="Your town or area, e.g. 'Yaba, Lagos'")

    @field_validator("username", mode="before")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


class GuestIn(BaseModel):
    """Play now with just a name; save the account later with ClaimIn."""

    name: str = Field(min_length=2, max_length=20)

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split()) if isinstance(v, str) else v


class ClaimIn(BaseModel):
    """Turn a guest into a full player: a name and password, and optionally where they play from."""

    username: str = Field(pattern=r"^[a-z0-9_]{3,20}$")
    password: str = Field(min_length=8, max_length=200)
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    place: str | None = Field(default=None, min_length=2, max_length=120)

    @field_validator("username", mode="before")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


class LoginIn(BaseModel):
    username: str
    password: str

    @field_validator("username", mode="before")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


class BadgeOut(BaseModel):
    id: str
    emoji: str
    name: str
    description: str
    earned: bool
    progress: int
    goal: int


class MeOut(BaseModel):
    id: int
    username: str
    is_guest: bool = False  # played with just a name: no password or voice yet
    nickname: str | None = None  # a guest's display name
    is_admin: bool
    has_voice: bool
    voice_samples: int
    learned_samples: int = 0  # of those, clips learned from your games
    country: str | None
    place: str | None  # e.g. "Yaba, Lagos"
    share_location: bool  # false = hidden from other players' map
    lat: float | None  # the place's point on the map
    lon: float | None
    total_points: int
    turns: int
    wins: int = 0
    badges: list[BadgeOut] = []


class TokenOut(BaseModel):
    token: str
    user: MeOut


class LocationIn(BaseModel):
    """Move your pin (country + place), and/or show or hide it from other players."""

    share: bool = True
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    place: str | None = Field(default=None, min_length=2, max_length=120)


class PlaceOut(BaseModel):
    name: str  # e.g. "Yaba, Lagos"
    country: str  # ISO code
    lat: float
    lon: float


# ---------- voice game: rooms and dashboard ----------


class RoomCreateIn(BaseModel):
    mode: Literal["yourself", "impersonate", "disguise", "guess", "telephone"] = "yourself"
    rounds: int = Field(default=2, ge=1, le=5)
    speed: bool = False  # 20 seconds a turn, bonus for being quick
    twists: bool = False  # a silly style for every turn
    crowd: bool = False  # impersonate: the players rate each impression too (humans vs AI)
    double_final: bool = False  # the last round counts double
    replay: bool = True  # keep each turn's clip for an hour, for the replay


class VoteIn(BaseModel):
    suspect_id: int  # Guess Who: the player you think spoke


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)  # humans vs AI: how good was that impression?


class ReactIn(BaseModel):
    emoji: str


class DashboardPlayer(BaseModel):
    user_id: int
    username: str
    online: bool
    has_voice: bool
    country: str | None
    place: str | None  # None if they hide their pin
    lat: float | None
    lon: float | None
    room_code: str | None  # the game they're in right now, if any
    room_status: str | None
    total_points: int
    turns: int


class DashboardRoom(BaseModel):
    code: str
    host: str
    mode: str
    status: str
    players: list[str]
    turn: int  # turns played so far
    turns_total: int


class DashboardPlay(BaseModel):
    username: str
    room_code: str | None
    mode: str
    points: int
    created_at: datetime


class DashboardOut(BaseModel):
    me: int
    online: int
    players: list[DashboardPlayer]
    rooms: list[DashboardRoom]
    recent_plays: list[DashboardPlay]


# ---------- admin ----------


class AdminOverview(BaseModel):
    players: int
    online: int
    with_voice: int
    countries: int
    lab_speakers: int  # voices enrolled in the voice lab, not by a player
    games_live: int  # waiting or playing right now
    games_total: int  # still kept in Redis
    turns_total: int
    turns_today: int
    cheat_attempts: int  # turns where the live check failed
    points_total: int


class AdminPlayer(BaseModel):
    user_id: int
    username: str
    is_admin: bool
    online: bool
    has_voice: bool
    country: str | None
    place: str | None
    lat: float | None
    lon: float | None
    share_location: bool
    room_code: str | None
    total_points: int
    turns: int
    cheat_attempts: int
    created_at: datetime | None
    last_seen_at: datetime | None


class AdminPlay(BaseModel):
    id: int
    username: str
    room_code: str | None
    mode: str
    points: int
    live_passed: bool | None
    created_at: datetime


class AdminRoom(BaseModel):
    code: str
    host: str
    mode: str
    status: str
    players: list[str]
    turn: int
    turns_total: int
    created_at: datetime
    updated_at: datetime


# ---------- daily challenge and leaderboards ----------


class DailyEntry(BaseModel):
    username: str
    country: str | None
    score: int


class DailyAttemptOut(BaseModel):
    score: int
    voice_score: float
    phrase_match: float
    heard: str
    message: str


class DailyOut(BaseModel):
    day: date
    phrase: str
    attempts_left: int
    best: int | None  # your best score today
    streak: int  # days in a row, including today if you've played
    ends_in_seconds: int
    leaderboard: list[DailyEntry]  # today, best first
    last_attempt: DailyAttemptOut | None = None


class CountryScore(BaseModel):
    country: str
    points: int
    players: int


class WeeklyEntry(BaseModel):
    username: str
    country: str | None
    points: int
    wins: int


class LeaderboardsOut(BaseModel):
    week_start: date
    week_ends_in_seconds: int
    countries: list[CountryScore]  # this week, most points first
    weekly_top: list[WeeklyEntry]  # this week's Top 8
    last_week_champion: WeeklyEntry | None


# ---------- voice setup ----------


class ClipCheckOut(BaseModel):
    """Is this take good enough to learn your voice from?"""

    ok: bool
    speech_seconds: float
    loudness_db: float
    snr_db: float
    problems: list[str]  # what to fix, in plain words



# ---------- solo play (against the built-in voices) ----------


class SoloVoice(BaseModel):
    speaker_id: int
    name: str  # e.g. "Reader 1272"


class SoloOut(BaseModel):
    voices: list[SoloVoice]
    rounds: int  # solo turns you've played
    right: int  # mystery voices you picked out
    points: int


class SoloRoundOut(BaseModel):
    round_id: str
    options: list[SoloVoice]  # one of them is the mystery voice
    expires_in_seconds: int


class SoloGuessIn(BaseModel):
    speaker_id: int


class SoloGuessOut(BaseModel):
    right: bool
    answer: SoloVoice
    ai_guess: SoloVoice | None  # the AI's pick, from the same introductions you heard
    points: int
    message: str


class SoloTurnOut(BaseModel):
    points: int
    message: str
    score: float | None  # the voice score behind the points
    liveness: LivenessOut | None
    sounded_like: dict[str, int]  # the closest voices the game knows (0-100), best first
