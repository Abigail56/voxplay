from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Accept the plain URL a host gives you and turn it into an asyncpg URL.

    Neon, Render and others hand out `postgres://...` or `postgresql://...?sslmode=require`.
    SQLAlchemy needs `postgresql+asyncpg://`, and asyncpg spells the SSL option `ssl=require`
    (it rejects `sslmode` and `channel_binding`).
    """
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = []
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            if value != "disable":
                query.append(("ssl", "require"))
        elif key != "channel_binding":
            query.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    """All settings can be overridden with environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://voiceid:voiceid@localhost:5442/voiceid"
    # Liveness phrases and rate limits live here. Empty = keep them in this process's
    # memory (fine for tests and a single instance).
    redis_url: str = ""

    # Cosine-similarity cut-off between "same person" and "unknown".
    # Chosen with scripts/tune_threshold.py; see README "How the threshold was chosen".
    match_threshold: float = 0.40
    # Optional: require the winner to beat the runner-up by this much (0 = off).
    min_margin: float = 0.0
    top_k: int = 3

    # --- Liveness: "say this phrase" so a recording can't be replayed ---
    # When true, /identify only answers clips that say a fresh phrase from GET /challenge.
    require_liveness: bool = True
    challenge_ttl_seconds: int = 120
    # Share of the phrase's digits that must be heard, in order (0.8 = 5 of 6).
    liveness_min_match: float = 0.8
    # The same for game turns' silly lines (5 of 7 words). Funny voices are harder to transcribe.
    line_min_match: float = 0.7
    # faster-whisper model. "small.en" hears digits even better but is ~3x slower on a CPU.
    asr_model: str = "base.en"
    asr_dir: str = "/models/whisper"

    # --- Voice game: accounts and rooms ---
    # Signs the sign-in tokens. Set a long random value in production. Empty = a random one
    # per start, which signs everyone out whenever the API restarts (fine for development).
    jwt_secret: str = ""
    token_days: float = 7
    # Guest players (a name, no password) are deleted after this many days without playing.
    guest_retention_days: float = 30
    # Rooms are deleted this long after their last change.
    room_ttl_hours: float = 6
    # A player counts as "online" if their dashboard pinged this recently.
    online_seconds: int = 90

    # Comma-separated player names who may open the admin page, e.g. "chi,rita".
    admin_usernames: str = ""

    # --- Voice setup and learning ---
    # Players record this many takes of their voice, each checked for quality.
    min_enroll_clips: int = 3
    # Each take must sound like the others at least this much (catches a different person or heavy noise).
    enroll_consistency: float = 0.40
    # Turns recognised at least this confidently are added to the player's voiceprint...
    learn_min_score: float = 0.55
    # ...keeping this many of the most recent ones (enrollment clips are always kept).
    max_learned_samples: int = 20

    # --- Voice game map ---
    # Places are looked up with OpenStreetMap's Nominatim, whose policy asks for a User-Agent
    # that names the app. Add a contact (URL or email) here for anything beyond a demo.
    geocoder_user_agent: str = "WhosTalking-VoiceGame/1.0"
    # Where each turn was played from is forgotten after this many days.
    location_retention_days: float = 30

    # --- Public demo safety (all off by default; turned on in the cloud) ---
    # Visitors' enrollments are deleted after this many hours (0 = keep forever).
    demo_retention_hours: float = 0
    # Most visitor enrollments kept at once (0 = no limit).
    max_active_enrollments: int = 0
    # Enroll/identify requests allowed per visitor IP per minute (0 = no limit).
    rate_limit_per_minute: int = 0
    # Read the visitor's IP from X-Forwarded-For (only behind a trusted proxy, e.g. Hugging Face).
    trust_proxy_headers: bool = False
    # Enroll the bundled LibriSpeech readers on startup, so the demo always has someone to match.
    seed_sample_voices: bool = False
    sample_voices_dir: str = "sample_voices"

    min_speech_seconds: float = 1.0
    max_clip_seconds: float = 60.0
    max_upload_mb: int = 10
    max_files_per_request: int = 10

    model_source: str = "speechbrain/spkrec-ecapa-voxceleb"
    model_dir: str = "/models/spkrec-ecapa-voxceleb"
    torch_threads: int = 2

    cors_origins: str = "http://localhost:3010,http://localhost:3001"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @property
    def admin_names(self) -> set[str]:
        return {n.strip().lower() for n in self.admin_usernames.split(",") if n.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
