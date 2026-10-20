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

    # Cosine-similarity cut-off between "same person" and "unknown".
    # Chosen with scripts/tune_threshold.py; see README "How the threshold was chosen".
    match_threshold: float = 0.40
    # Optional: require the winner to beat the runner-up by this much (0 = off).
    min_margin: float = 0.0
    top_k: int = 3

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
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
