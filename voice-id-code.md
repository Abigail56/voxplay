# Voice ID: all source code

Every text file in the project, grouped by folder. Not included here (they're in the zip): `frontend/package-lock.json` and the sample voice clips.

## `voice-id/.env.example`

```bash
# Copy to .env to override defaults (docker compose reads it automatically).
MATCH_THRESHOLD=0.40
```

## `voice-id/.gitignore`

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env
node_modules/
.next/
data/samples/
dist/
```

## `voice-id/README.md`

````markdown
# Voice ID: AI speaker recognition

Record or upload a voice clip and the system tells you **which enrolled person is
speaking**. If the voice doesn't match anyone closely enough, it answers **"unknown"**.

- **Model:** pretrained [SpeechBrain ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb), trained on VoxCeleb. We don't train anything ourselves.
- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), PostgreSQL + **pgvector**, FFmpeg
- **Frontend:** Next.js 15, React 19, TypeScript, Zustand, browser `MediaRecorder` for the microphone
- **Everything runs in Docker**, so you don't install PyTorch or Node on your machine.

---

## How it works (step by step)

1. **Preprocess** ([backend/app/audio.py](backend/app/audio.py)).
   FFmpeg decodes any common format (wav, mp3, **webm/opus from the browser**, ogg, m4a, flac),
   mixes it to **mono** and resamples it to **16 kHz** (the rate the model expects).
   An energy-based voice-activity detector then **trims silence**. Clips with less than
   1 second of speech are rejected.
2. **Embed** ([backend/app/embedding.py](backend/app/embedding.py)).
   ECAPA-TDNN turns the clip into a **192-number voiceprint** (an "embedding").
   Clips of the same person point in roughly the same direction.
3. **Enroll** (`POST /speakers`). Each sample's embedding is stored, and their average
   (the **centroid**) is stored on the speaker row in a pgvector `vector(192)` column.
4. **Identify** (`POST /identify`). PostgreSQL finds the nearest centroids using pgvector's
   cosine-distance operator `<=>` (with an HNSW index). The pure function `decide()` in
   [backend/app/matching.py](backend/app/matching.py) then returns the best speaker
   if its **cosine similarity ≥ threshold (0.40)**, otherwise `"unknown"`.

```
browser mic / file ──► FFmpeg (16 kHz mono) ──► trim silence ──► ECAPA-TDNN ──► 192-d voiceprint
                                                                                     │
                       name + score  ◄── decide(threshold) ◄── pgvector top-k  ◄─────┘
                       or "unknown"
```

---

## Quick start

Requirements: Docker with Docker Compose. Ports used: **3010** (web), **8010** (API) and
**5442** (Postgres). They're chosen so they don't clash with a local Postgres on 5432.

```bash
docker compose up -d --build
```

The first start downloads the model (~80 MB) into a Docker volume, which takes about a minute.
Wait until the API is ready:

```bash
curl http://localhost:8010/health
```

Then open:

- **App:** http://localhost:3010. Enroll yourself (2–3 clips of 5–10 s each), then identify a new recording.
- **API docs (Swagger):** http://localhost:8010/docs

> The microphone only works on `localhost` or HTTPS, because browsers block it on plain-HTTP remote hosts.

### Try it with real voices (no microphone needed)

```bash
# download 9 LibriSpeech speakers x 6 clips into ./data/samples (a few MB)
docker compose run --rm api python scripts/fetch_samples.py

# enroll 3 of them, identify held-out clips as wav/mp3/webm + a stranger -> "unknown"
docker compose run --rm api python scripts/e2e_demo.py --api http://api:8000
```

### Run the tests

```bash
docker compose run --rm api pytest -v
```

There are 33 tests:
- `test_matching.py`: cosine similarity, centroids, ranking, threshold/"unknown" decisions, margin rule, EER
- `test_audio.py`: resampling, silence trimming, rejecting garbage and too-short audio
- `test_api.py`: full HTTP flow (enroll → list → identify → unknown → delete) against a real
  pgvector database (`voiceid_test`). It uses a tiny fake embedder, so it runs in seconds without PyTorch.

### Stop / clean up

```bash
docker compose down        # stop
docker compose down -v     # stop AND delete the database + model cache volumes
```

---

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/speakers` | Enroll: form fields `name`, `consent=true`, one or more `files` |
| `POST` | `/speakers/{id}/samples` | Add more samples to an existing speaker (recomputes the centroid) |
| `GET` | `/speakers` | List enrolled speakers with sample counts |
| `GET` | `/speakers/{id}` | One speaker |
| `DELETE` | `/speakers/{id}` | Permanently delete a speaker and all of their voiceprints |
| `POST` | `/identify` | Form field `file` → best match or `"unknown"` |
| `GET` | `/health` | Model loaded? threshold? number of speakers |

Example:

```bash
curl -F name=Ada -F consent=true -F files=@ada1.wav -F files=@ada2.mp3 http://localhost:8010/speakers
curl -F file=@mystery.webm http://localhost:8010/identify
```

```json
{
  "label": "Ada",
  "is_match": true,
  "speaker_id": 1,
  "score": 0.7123,
  "threshold": 0.4,
  "reason": "Score is above the threshold.",
  "speech_seconds": 6.1,
  "candidates": [
    {"speaker_id": 1, "name": "Ada", "score": 0.7123},
    {"speaker_id": 2, "name": "Bayo", "score": 0.0912}
  ]
}
```

`score` is the cosine similarity between the clip and the speaker's voiceprint, used as the
confidence. In practice it falls between about −0.1 and 1.0, and higher is more confident.

---

## How the threshold was chosen

`scripts/tune_threshold.py` measures how well the model separates voices **on real data**:

1. For each of **9 LibriSpeech speakers**, 2 clips build the centroid (like enrollment) and the
   other 3–4 clips are test clips.
2. Each test clip is scored against **its own speaker** (34 *genuine* scores) and against
   **every other speaker** (272 *impostor* scores).
3. For each candidate threshold it reports the **false-accept rate** (a stranger is accepted as
   someone), the **false-reject rate** (a real speaker is called unknown) and an **open-set
   accuracy**: each speaker is left out of the database in turn, so their clips *must* come back
   "unknown".

Results (full output in [docs/threshold-tuning.txt](docs/threshold-tuning.txt)):

| | min | mean | max |
|---|---|---|---|
| genuine scores | 0.350 | **0.716** | 0.913 |
| impostor scores | −0.108 | **0.098** | 0.350 |

| threshold | false accepts | false rejects | open-set accuracy |
|---|---|---|---|
| 0.30 | 1.5 % | 0.0 % | 98.7 % |
| 0.35 (EER) | 0.4 % | 2.9 % | 97.1 % |
| **0.40 (chosen)** | **0.0 %** | **2.9 %** | **97.4 %** |
| 0.50 | 0.0 % | 8.8 % | 92.2 % |

**Why 0.40:** it's the lowest threshold with **zero false accepts** on this data. For an identity
system, wrongly naming a stranger as someone is worse than asking a real person to try again.
It also leaves a clear gap above the mean impostor score (0.10).

**Tune it for your setting.** LibriSpeech is clean read speech. Laptop microphones in noisy rooms
give lower genuine scores. If enrolled people often get "unknown", try `0.30–0.35`. To be stricter,
use `0.45–0.50`. You can also set `MIN_MARGIN` (e.g. `0.05`) so the system says "unknown" when two
speakers score almost the same. Best of all, record your own clips into `data/samples/<name>/`
and re-run:

```bash
docker compose run --rm api python scripts/tune_threshold.py --data /data/samples
MATCH_THRESHOLD=0.35 docker compose up -d api      # or put it in .env
```

### End-to-end verification

[docs/e2e-demo-output.txt](docs/e2e-demo-output.txt) shows the result of
`scripts/e2e_demo.py`. Three speakers were enrolled with 2 clips each. Held-out clips sent as
**wav, mp3 and webm/opus** were all identified correctly (scores 0.62–0.83), and a never-enrolled
speaker came back **"unknown"** every time (scores 0.12–0.17). **21/21 correct.** One clip
with only 0.8 s of speech was rejected with a clear 422 error, which is the intended behaviour.

---

## Consent and privacy

A voiceprint is **biometric data**. Under laws such as the GDPR (Art. 9), Nigeria's NDPA 2023
and Illinois' BIPA, it needs explicit consent and careful handling. This project builds that in:

- **Consent is required.** `POST /speakers` refuses to enroll anyone unless `consent=true`, and
  the UI has a consent checkbox. The time of consent is stored (`consent_given_at`).
- **Enroll only people who agree**, and tell them what it's for and how long it's kept.
- **Raw audio is never stored.** Only the 192-number embeddings are kept, and uploads are
  processed in memory or in a temp file that is deleted right away.
- **Right to be forgotten.** `DELETE /speakers/{id}` (the "Delete" button) removes the speaker
  and all of their sample embeddings (`ON DELETE CASCADE`).
- **Treat embeddings as sensitive.** Even without the audio, they identify a person. In production,
  add authentication, HTTPS, encrypted backups and access logging, and don't expose the API publicly as-is.
- **It isn't proof of identity.** Voices can be imitated or synthesised (deepfakes). Use this for
  convenience features, not for authorising payments or access on its own.

---

## Folder structure

```
voice-id/
├── docker-compose.yml          # db (pgvector) :5442, api :8010, web :3010
├── .env.example                # MATCH_THRESHOLD override
├── README.md
├── docs/
│   ├── threshold-tuning.txt    # output of scripts/tune_threshold.py
│   └── e2e-demo-output.txt     # output of scripts/e2e_demo.py
├── data/                       # sample voices land in data/samples/<speaker>/ (git-ignored)
├── backend/
│   ├── Dockerfile              # python:3.11-slim + ffmpeg + CPU-only PyTorch
│   ├── requirements.txt / requirements-dev.txt
│   ├── db-init/01-test-db.sql  # creates the voiceid_test database
│   ├── app/
│   │   ├── main.py             # FastAPI app factory, lifespan (loads model), CORS, /health
│   │   ├── config.py           # settings from env vars (threshold, limits, DB URL)
│   │   ├── audio.py            # FFmpeg decode → 16 kHz mono, silence trimming, validation
│   │   ├── embedding.py        # ECAPA-TDNN wrapper (SpeechBrain)
│   │   ├── matching.py         # cosine similarity, centroids, decide() → name / unknown
│   │   ├── services.py         # upload → preprocess → embed (in a worker thread)
│   │   ├── db.py, models.py    # SQLAlchemy async + pgvector tables
│   │   ├── schemas.py          # Pydantic response models
│   │   └── routers/
│   │       ├── speakers.py     # enroll, add samples, list, get, delete
│   │       └── identify.py     # pgvector nearest-neighbour search + decide()
│   ├── scripts/
│   │   ├── fetch_samples.py    # download LibriSpeech test voices
│   │   ├── tune_threshold.py   # genuine/impostor scores, EER, threshold sweep
│   │   └── e2e_demo.py         # enroll + identify via the running API
│   └── tests/                  # pytest: matching, audio, API
└── frontend/
    ├── Dockerfile              # node:22-alpine multi-stage, Next.js standalone
    ├── app/                    # layout.tsx, page.tsx, globals.css
    ├── components/
    │   ├── ClipInput.tsx       # record (MediaRecorder) or upload audio
    │   ├── EnrollForm.tsx      # name + samples + consent checkbox
    │   ├── IdentifyPanel.tsx   # result, confidence bar vs threshold, candidates
    │   └── SpeakerList.tsx     # enrolled people + delete
    ├── lib/api.ts              # typed fetch wrapper for the backend
    └── store/useSpeakerStore.ts# Zustand store for the speaker list
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `MATCH_THRESHOLD` | `0.40` | Minimum cosine similarity for a match |
| `MIN_MARGIN` | `0.0` | Required lead over the runner-up (0 = off) |
| `MIN_SPEECH_SECONDS` | `1.0` | Reject clips with less speech than this |
| `MAX_CLIP_SECONDS` | `60` | Reject longer clips |
| `MAX_UPLOAD_MB` | `10` | Per-file upload limit |
| `CORS_ORIGINS` | `http://localhost:3010,http://localhost:3001` | Comma-separated allowed origins (the Voice ID UI and the portfolio demo page) |
| `DEMO_RETENTION_HOURS` | `0` | Delete visitors' enrollments after this many hours (0 = keep) |
| `MAX_ACTIVE_ENROLLMENTS` | `0` | Most visitor enrollments kept at once (0 = no limit) |
| `RATE_LIMIT_PER_MINUTE` | `0` | Enroll/identify requests per visitor IP per minute (0 = off) |
| `TRUST_PROXY_HEADERS` | `false` | Read the visitor IP from `X-Forwarded-For` (only behind a proxy) |
| `SEED_SAMPLE_VOICES` | `false` | Enroll the LibriSpeech readers in `backend/sample_voices/` on startup |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8010` | Frontend → API URL (build arg) |

## Public demo and deployment

For a public demo, turn on the settings above. They're already on in the Hugging Face Space image. The demo
then works like this:

- **Sample voices.** Three LibriSpeech readers (`backend/sample_voices/`, CC BY 4.0) are enrolled at startup, so
  there is always someone to match. They can't be deleted or changed (`403`).
- **Visitors' enrollments expire.** Each gets `expires_at`. Expired speakers disappear from every endpoint at once,
  and a background job deletes them for good every 5 minutes (`app/demo.py`).
- **Abuse limits.** Per-IP rate limit (`429`) and a cap on active enrollments (`503 demo is full`).

**Deploying to a free Hugging Face Space:** run `sh deploy/make-hf-space.sh` and upload `dist/hf-space/`. Full steps
are in the portfolio's `docs/DEPLOY.md`. Free Spaces can't reach outside databases, so the Space image
(`deploy/huggingface-space/`) runs its own PostgreSQL + pgvector next to the API. Data lasts only while the Space
runs, which suits a demo with 24-hour enrollments.

`DATABASE_URL` also accepts the plain `postgresql://…?sslmode=require` strings that hosts like Neon give you;
`app/config.py` converts them for asyncpg.

## Notes and ideas for next steps

- **Versions.** `huggingface_hub` is pinned to `0.25.2` because SpeechBrain 1.0.3 calls
  `hf_hub_download(use_auth_token=...)`, which newer versions removed.
- **Speed and memory.** The API uses about 500 MB of RAM with the model loaded. On a 4-core laptop
  (CPU only, 2 PyTorch threads) one `/identify` call for a typical 10–15 s clip takes about 1.5 s,
  including decoding. Raise `TORCH_THREADS` if you have more cores.
- **Ideas:** Redis caching of embeddings for repeated clips, Alembic migrations, auth (JWT),
  speaker verification mode ("is this Ada?" with a stricter threshold), anti-spoofing / liveness checks,
  and showcasing it on your portfolio site.
````

## `voice-id/backend/.dockerignore`

```
__pycache__/
.pytest_cache/
.venv/
*.pyc
```

## `voice-id/backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

# FFmpeg decodes mp3 / webm / ogg / m4a and resamples to 16 kHz mono.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
# CPU-only PyTorch keeps the image ~1.5 GB smaller than the CUDA build.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt -r requirements-dev.txt

ENV MODEL_DIR=/models/spkrec-ecapa-voxceleb

# Download the pretrained model (~80 MB) into the image, so the app starts without
# waiting for a download. Readable and writable by any user: Hugging Face Spaces
# run the container as user 1000, not root.
RUN python -c "from speechbrain.inference.speaker import EncoderClassifier; \
EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir='/models/spkrec-ecapa-voxceleb')" \
    && chmod -R a+rwX /models

COPY . .

# Hosts such as Hugging Face Spaces and Render tell the app which port to use via $PORT.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]
```

## `voice-id/backend/app/__init__.py`

```python

```

## `voice-id/backend/app/audio.py`

```python
"""Audio preprocessing: any common format -> clean 16 kHz mono float32 samples.

Steps
-----
1. decode_to_mono_16k: FFmpeg decodes wav / mp3 / webm (browser recordings) /
   ogg / m4a / flac, mixes to mono and resamples to 16 kHz, which is what the
   ECAPA model was trained on.
2. trim_silence: a simple energy-based voice activity detector drops quiet
   frames (leading/trailing silence and long pauses) so the voiceprint is built
   from speech, not from room noise.
3. preprocess: runs both and rejects clips with too little speech.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16_000


class AudioError(ValueError):
    """Raised for audio we cannot use. The message is safe to show to users."""


def decode_to_mono_16k(data: bytes) -> np.ndarray:
    """Decode audio bytes of (almost) any format with FFmpeg."""
    if not data:
        raise AudioError("The audio file is empty.")

    # Write to a temp file instead of piping: some containers (mp4/m4a from
    # Safari) keep their index at the end and need a seekable input.
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-i", path,
                "-vn",  # ignore any video stream
                "-ac", "1",  # mono
                "-ar", str(SAMPLE_RATE),  # 16 kHz
                "-f", "f32le", "pipe:1",  # raw 32-bit float samples to stdout
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioError("Decoding the audio took too long.") from exc
    finally:
        os.unlink(path)

    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="ignore").strip().splitlines()
        raise AudioError(f"Could not decode audio ({detail[-1] if detail else 'unknown format'}).")

    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise AudioError("The file contains no audio samples.")
    return audio


def trim_silence(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_ms: int = 30,
    top_db: float = 35.0,
    floor_db: float = -55.0,
    pad_frames: int = 3,
) -> np.ndarray:
    """Keep only the frames that contain speech.

    A frame counts as speech when its loudness (RMS in dB) is within `top_db`
    of the loudest frame AND above an absolute `floor_db` (so pure hiss is never
    "speech"). Each speech frame keeps `pad_frames` neighbours on both sides so
    that soft word endings are not chopped off.
    """
    frame_len = int(sample_rate * frame_ms / 1000)
    if audio.size < frame_len:
        return audio[:0]

    audio = audio - float(np.mean(audio))  # remove DC offset
    n_frames = audio.size // frame_len
    frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)

    threshold = max(float(db.max()) - top_db, floor_db)
    voiced = db > threshold
    if not voiced.any():
        return audio[:0]

    # Dilate the voiced mask by pad_frames on each side.
    if pad_frames > 0:
        kernel = np.ones(2 * pad_frames + 1, dtype=int)
        voiced = np.convolve(voiced.astype(int), kernel, mode="same") > 0

    return frames[voiced].reshape(-1).astype(np.float32)


@dataclass(frozen=True)
class PreparedAudio:
    samples: np.ndarray
    original_seconds: float
    speech_seconds: float


def preprocess(
    data: bytes,
    min_speech_seconds: float = 1.0,
    max_seconds: float = 60.0,
) -> PreparedAudio:
    """Decode, trim silence and validate one uploaded clip."""
    audio = decode_to_mono_16k(data)
    original_seconds = audio.size / SAMPLE_RATE
    if original_seconds > max_seconds:
        raise AudioError(f"Clip is {original_seconds:.0f}s long; the maximum is {max_seconds:.0f}s.")

    speech = trim_silence(audio)
    speech_seconds = speech.size / SAMPLE_RATE
    if speech_seconds < min_speech_seconds:
        raise AudioError(
            f"Only {speech_seconds:.1f}s of speech found; please record at least "
            f"{min_speech_seconds:.0f}s of clear speech."
        )

    # Peak-normalise so very quiet recordings are not penalised.
    peak = float(np.max(np.abs(speech)))
    if peak > 0:
        speech = (speech / peak * 0.95).astype(np.float32)

    return PreparedAudio(speech, round(original_seconds, 2), round(speech_seconds, 2))
```

## `voice-id/backend/app/config.py`

```python
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
```

## `voice-id/backend/app/db.py`

```python
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Enable pgvector and create tables. (A bigger project would use Alembic migrations.)"""
    from . import models  # noqa: F401  - registers the tables on Base.metadata

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # create_all only creates missing tables. These bring databases made by an
        # older version of this app up to date (Alembic would do this in a bigger project).
        await conn.execute(text("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS is_sample BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_speakers_expires_at ON speakers (expires_at)"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session
```

## `voice-id/backend/app/demo.py`

```python
"""Rules that make the API safe to leave open as a public demo.

- Visitors' enrollments expire (DEMO_RETENTION_HOURS) and are deleted by a background job.
- Built-in sample voices (LibriSpeech readers) are always there to match against.
- A simple per-IP rate limit (RATE_LIMIT_PER_MINUTE) stops one visitor hammering the model.

Everything here is switched off by default, so local development behaves as before.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from .audio import AudioError, preprocess
from .config import Settings
from .embedding import Embedder
from .matching import compute_centroid
from .models import Speaker, VoiceSample

log = logging.getLogger("voiceid.demo")

AUDIO_EXT = {".wav", ".flac", ".mp3", ".webm", ".ogg", ".m4a"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def is_active():
    """SQL condition: the speaker hasn't expired yet (or never expires)."""
    return or_(Speaker.expires_at.is_(None), Speaker.expires_at > now())


async def delete_expired(session: AsyncSession) -> int:
    """Delete every expired enrollment (their voice samples go with them). Returns how many."""
    result = await session.execute(
        delete(Speaker).where(Speaker.expires_at.is_not(None), Speaker.expires_at <= now())
    )
    await session.commit()
    return result.rowcount or 0


async def cleanup_loop(sessionmaker: async_sessionmaker[AsyncSession], every_seconds: int = 300) -> None:
    """Background task: delete expired enrollments every few minutes."""
    while True:
        try:
            async with sessionmaker() as session:
                removed = await delete_expired(session)
            if removed:
                log.info("Deleted %d expired enrollment(s).", removed)
        except Exception:  # never let the loop die; try again next round
            log.exception("Cleanup of expired enrollments failed")
        await asyncio.sleep(every_seconds)


class RateLimiter:
    """Allow at most `limit` requests per client IP in any 60-second window (in memory).

    Good enough for a single-instance demo. Several instances would share the count
    in Redis instead, like the portfolio API's contact form does.
    """

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        cutoff = time.monotonic() - self.window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(time.monotonic())
            return True


def client_ip(request: Request, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """FastAPI dependency for the expensive endpoints (enroll, add samples, identify)."""
    settings: Settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    if not limiter.allow(client_ip(request, settings.trust_proxy_headers)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests from you in the last minute. Please wait a moment and try again.",
        )


async def seed_sample_voices(
    sessionmaker: async_sessionmaker[AsyncSession], embedder: Embedder, folder: Path
) -> int:
    """Enroll each sub-folder of `folder` as a permanent sample speaker (once).

    folder/<Speaker name>/*.webm  ->  speaker "<Speaker name>" with one sample per file.
    """
    if not folder.is_dir():
        log.warning("Sample voices folder %s not found; skipping.", folder)
        return 0

    added = 0
    async with sessionmaker() as session:
        for person in sorted(p for p in folder.iterdir() if p.is_dir()):
            if await session.scalar(select(Speaker.id).where(Speaker.name == person.name)):
                continue
            vectors, seconds = [], []
            for clip in sorted(f for f in person.iterdir() if f.suffix.lower() in AUDIO_EXT):
                try:
                    prepared = await run_in_threadpool(preprocess, clip.read_bytes())
                except AudioError as exc:
                    log.warning("Skipping sample %s: %s", clip, exc)
                    continue
                vectors.append(await run_in_threadpool(embedder.embed, prepared.samples))
                seconds.append(prepared.speech_seconds)
            if not vectors:
                continue
            session.add(
                Speaker(
                    name=person.name,
                    embedding=compute_centroid(vectors).tolist(),
                    consent_given_at=now(),  # public research recordings (LibriSpeech, CC BY 4.0)
                    is_sample=True,
                    expires_at=None,
                    samples=[VoiceSample(embedding=v.tolist(), speech_seconds=s) for v, s in zip(vectors, seconds)],
                )
            )
            added += 1
        await session.commit()
    if added:
        log.info("Enrolled %d sample voice(s) from %s.", added, folder)
    return added
```

## `voice-id/backend/app/embedding.py`

```python
"""Speaker embeddings with the pretrained SpeechBrain ECAPA-TDNN model.

The model (speechbrain/spkrec-ecapa-voxceleb) was trained on thousands of
VoxCeleb speakers. We never train it; we only use it to turn a clip into a
192-dimensional voiceprint. It is downloaded from Hugging Face on first start
(about 80 MB) and cached in MODEL_DIR.
"""

from __future__ import annotations

import threading
import warnings
from typing import Protocol

import numpy as np

from .matching import l2_normalize

EMBEDDING_DIM = 192


class Embedder(Protocol):
    """Anything that turns 16 kHz mono samples into a unit-length vector.

    The tests use a tiny fake embedder that follows this protocol, so they run
    in milliseconds without PyTorch.
    """

    def embed(self, samples: np.ndarray) -> np.ndarray: ...


class EcapaEmbedder:
    def __init__(self, source: str, savedir: str, num_threads: int = 2) -> None:
        # Imported here so that importing this module (e.g. in tests) does not
        # pull in PyTorch.
        import torch
        from speechbrain.inference.speaker import EncoderClassifier

        # SpeechBrain 1.0 triggers harmless deprecation warnings in newer PyTorch.
        warnings.filterwarnings("ignore", category=FutureWarning, module="speechbrain")
        torch.set_num_threads(num_threads)
        self._torch = torch
        self._model = EncoderClassifier.from_hparams(
            source=source, savedir=savedir, run_opts={"device": "cpu"}
        )
        self._model.eval()
        # One inference at a time: keeps memory predictable on small machines.
        self._lock = threading.Lock()

    def embed(self, samples: np.ndarray) -> np.ndarray:
        wav = self._torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32)).unsqueeze(0)
        with self._lock, self._torch.inference_mode():
            emb = self._model.encode_batch(wav)  # shape (1, 1, 192)
        return l2_normalize(emb.squeeze().cpu().numpy())
```

## `voice-id/backend/app/main.py`

```python
"""FastAPI entry point: `uvicorn app.main:app`."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .db import create_engine, init_db
from .demo import RateLimiter, cleanup_loop, is_active, seed_sample_voices
from .embedding import EcapaEmbedder, Embedder
from .models import Speaker
from .routers import identify, speakers
from .schemas import HealthOut

log = logging.getLogger("voiceid")


def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    """Build the app. Tests pass a fake `embedder` so no ML model is loaded."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessionmaker = create_engine(settings.database_url)
        await init_db(engine)
        app.state.sessionmaker = sessionmaker
        app.state.settings = settings
        app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
        app.state.embedder = embedder
        if embedder is None:
            log.info("Loading speaker-embedding model %s ...", settings.model_source)
            app.state.embedder = await run_in_threadpool(
                EcapaEmbedder, settings.model_source, settings.model_dir, settings.torch_threads
            )
            log.info("Model ready.")

        if settings.seed_sample_voices:
            folder = Path(settings.sample_voices_dir)
            if not folder.is_absolute():
                folder = Path(__file__).resolve().parents[1] / folder
            await seed_sample_voices(sessionmaker, app.state.embedder, folder)

        cleanup = None
        if settings.demo_retention_hours > 0:
            cleanup = asyncio.create_task(cleanup_loop(sessionmaker))
        yield
        if cleanup:
            cleanup.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup
        await engine.dispose()

    app = FastAPI(
        title="Voice ID - speaker recognition API",
        description="Enroll people by voice and identify who is speaking.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Routes read settings via Depends(get_settings); make them see *these* settings.
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(speakers.router)
    app.include_router(identify.router)

    @app.get("/health", response_model=HealthOut, tags=["health"])
    async def health(request: Request) -> HealthOut:
        async with request.app.state.sessionmaker() as session:
            count = await session.scalar(select(func.count()).select_from(Speaker).where(is_active())) or 0
        return HealthOut(
            status="ok",
            model_loaded=request.app.state.embedder is not None,
            threshold=settings.match_threshold,
            speakers=count,
            demo_retention_hours=settings.demo_retention_hours,
        )

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
```

## `voice-id/backend/app/matching.py`

```python
"""Pure matching logic: no database, no ML model, no I/O.

Everything here works on plain NumPy vectors, which keeps it easy to unit test.

How speaker matching works
--------------------------
1. Every voice clip is turned into a 192-number "embedding" (a voiceprint) by the
   ECAPA-TDNN model. Clips from the same person point in roughly the same direction.
2. A speaker can have several enrollment clips. We average their (normalised)
   embeddings into one "centroid" per speaker.
3. To identify a new clip we compute the cosine similarity between its embedding
   and every centroid. Cosine similarity is 1.0 for identical directions,
   about 0 for unrelated voices.
4. The best-scoring speaker wins, but only if the score is at least the
   threshold. Otherwise the answer is "unknown".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

UNKNOWN_LABEL = "unknown"


def l2_normalize(vector: Sequence[float] | np.ndarray) -> np.ndarray:
    """Scale a vector to length 1 so that a dot product equals cosine similarity."""
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0 or not np.isfinite(norm):
        raise ValueError("Cannot normalise a zero or non-finite vector")
    return arr / norm


def cosine_similarity(a: Sequence[float] | np.ndarray, b: Sequence[float] | np.ndarray) -> float:
    """Cosine similarity in [-1, 1]. Higher means more alike."""
    a_arr, b_arr = l2_normalize(a), l2_normalize(b)
    if a_arr.shape != b_arr.shape:
        raise ValueError(f"Shape mismatch: {a_arr.shape} vs {b_arr.shape}")
    # Clip to guard against tiny floating point overshoots such as 1.0000001.
    return float(np.clip(np.dot(a_arr, b_arr), -1.0, 1.0))


def compute_centroid(embeddings: Iterable[Sequence[float] | np.ndarray]) -> np.ndarray:
    """Average several embeddings of one speaker into a single unit-length voiceprint.

    Each embedding is normalised first so that a long, loud clip does not
    outweigh a short, quiet one.
    """
    normalised = [l2_normalize(e) for e in embeddings]
    if not normalised:
        raise ValueError("At least one embedding is required")
    return l2_normalize(np.mean(np.stack(normalised), axis=0))


@dataclass(frozen=True)
class Candidate:
    speaker_id: int
    name: str
    score: float


@dataclass(frozen=True)
class Decision:
    label: str  # speaker name, or "unknown"
    speaker_id: int | None
    score: float  # best cosine similarity (our confidence score)
    is_match: bool
    reason: str


def rank_candidates(
    query: Sequence[float] | np.ndarray,
    speakers: Iterable[tuple[int, str, Sequence[float] | np.ndarray]],
) -> list[Candidate]:
    """Score a query embedding against (id, name, centroid) tuples, best first."""
    candidates = [
        Candidate(speaker_id=sid, name=name, score=cosine_similarity(query, centroid))
        for sid, name, centroid in speakers
    ]
    return sorted(candidates, key=lambda c: c.score, reverse=True)


def decide(candidates: Sequence[Candidate], threshold: float, min_margin: float = 0.0) -> Decision:
    """Turn ranked candidates into a final answer.

    - No enrolled speakers           -> unknown
    - Best score below the threshold -> unknown (voice is not close enough to anyone)
    - Best and runner-up too close   -> unknown (only if min_margin > 0; avoids
      confidently picking between two similar voices)
    - Otherwise                      -> the best speaker
    """
    if not candidates:
        return Decision(UNKNOWN_LABEL, None, 0.0, False, "No speakers are enrolled yet.")

    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    best = ranked[0]

    if best.score < threshold:
        return Decision(
            UNKNOWN_LABEL,
            None,
            best.score,
            False,
            f"Best match '{best.name}' scored {best.score:.3f}, below the threshold {threshold:.3f}.",
        )

    if min_margin > 0 and len(ranked) > 1:
        margin = best.score - ranked[1].score
        if margin < min_margin:
            return Decision(
                UNKNOWN_LABEL,
                None,
                best.score,
                False,
                f"'{best.name}' and '{ranked[1].name}' are too close to call "
                f"(margin {margin:.3f} < {min_margin:.3f}).",
            )

    return Decision(best.name, best.speaker_id, best.score, True, "Score is above the threshold.")


def equal_error_rate(genuine: Sequence[float], impostor: Sequence[float]) -> tuple[float, float]:
    """Find the threshold where false accepts and false rejects are (nearly) equal.

    genuine  = scores of clips compared with their *own* speaker
    impostor = scores of clips compared with *other* speakers
    Returns (eer, threshold). Used by scripts/tune_threshold.py.
    """
    g = np.asarray(genuine, dtype=np.float64)
    i = np.asarray(impostor, dtype=np.float64)
    if g.size == 0 or i.size == 0:
        raise ValueError("Need both genuine and impostor scores")

    best_gap, best = np.inf, (1.0, 0.0)
    for t in np.unique(np.concatenate([g, i])):
        far = float(np.mean(i >= t))  # impostors wrongly accepted
        frr = float(np.mean(g < t))  # genuine speakers wrongly rejected
        gap = abs(far - frr)
        if gap < best_gap:
            best_gap, best = gap, ((far + frr) / 2, float(t))
    return best
```

## `voice-id/backend/app/models.py`

```python
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .embedding import EMBEDDING_DIM


class Speaker(Base):
    """An enrolled person. `embedding` is the centroid of all their samples.

    Privacy by design: we store only voiceprints (192 numbers per clip), never
    the raw recordings.
    """

    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    consent_given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Built-in demo voices (public LibriSpeech readers): never expire, can't be deleted by visitors.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # When this enrollment is deleted automatically (NULL = never). Used by the public demo.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    samples: Mapped[list["VoiceSample"]] = relationship(
        back_populates="speaker", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # HNSW index for fast cosine-distance search once there are many speakers.
        Index(
            "ix_speakers_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class VoiceSample(Base):
    """The embedding of one enrollment clip (kept so the centroid can be recomputed)."""

    __tablename__ = "voice_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    speaker_id: Mapped[int] = mapped_column(ForeignKey("speakers.id", ondelete="CASCADE"), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    speech_seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    speaker: Mapped[Speaker] = relationship(back_populates="samples")
```

## `voice-id/backend/app/routers/__init__.py`

```python

```

## `voice-id/backend/app/routers/identify.py`

```python
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import is_active, rate_limit
from ..embedding import Embedder
from ..matching import Candidate, decide
from ..models import Speaker
from ..schemas import CandidateOut, IdentifyOut
from ..services import embed_upload, get_embedder

router = APIRouter(tags=["identify"])


@router.post("/identify", response_model=IdentifyOut, dependencies=[Depends(rate_limit)])
async def identify(
    session: Annotated[AsyncSession, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="The recording to identify.")],
) -> IdentifyOut:
    """Who is speaking? Returns the best match, or 'unknown' below the threshold."""
    clip = await embed_upload(file, embedder, settings)

    # pgvector does the nearest-neighbour search inside PostgreSQL.
    # `<=>` is cosine *distance* (1 - cosine similarity), so smaller is closer.
    distance = Speaker.embedding.cosine_distance(clip.vector.tolist()).label("distance")
    rows = await session.execute(
        select(Speaker.id, Speaker.name, distance).where(is_active()).order_by(distance).limit(settings.top_k)
    )
    candidates = [Candidate(sid, name, round(1.0 - float(d), 4)) for sid, name, d in rows.all()]

    decision = decide(candidates, settings.match_threshold, settings.min_margin)
    return IdentifyOut(
        label=decision.label,
        is_match=decision.is_match,
        speaker_id=decision.speaker_id,
        score=round(decision.score, 4),
        threshold=settings.match_threshold,
        reason=decision.reason,
        speech_seconds=clip.speech_seconds,
        candidates=[CandidateOut(speaker_id=c.speaker_id, name=c.name, score=c.score) for c in candidates],
    )
```

## `voice-id/backend/app/routers/speakers.py`

```python
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db import get_session
from ..demo import delete_expired, is_active, rate_limit
from ..embedding import Embedder
from ..matching import compute_centroid
from ..models import Speaker, VoiceSample
from ..schemas import SpeakerOut
from ..services import embed_uploads, get_embedder

router = APIRouter(prefix="/speakers", tags=["speakers"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def _sample_count(session: AsyncSession, speaker_id: int) -> int:
    return await session.scalar(select(func.count()).where(VoiceSample.speaker_id == speaker_id)) or 0


def _out(speaker: Speaker, count: int) -> SpeakerOut:
    return SpeakerOut(
        id=speaker.id,
        name=speaker.name,
        sample_count=count,
        consent_given_at=speaker.consent_given_at,
        created_at=speaker.created_at,
        is_sample=speaker.is_sample,
        expires_at=speaker.expires_at,
    )


async def _get_or_404(session: AsyncSession, speaker_id: int) -> Speaker:
    speaker = await session.scalar(select(Speaker).where(Speaker.id == speaker_id, is_active()))
    if speaker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Speaker not found.")
    return speaker


def _forbid_sample(speaker: Speaker) -> None:
    if speaker.is_sample:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Built-in sample voices can't be changed or deleted.")


@router.post(
    "", response_model=SpeakerOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)]
)
async def enroll_speaker(
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    name: Annotated[str, Form(min_length=1, max_length=100)],
    consent: Annotated[bool, Form(description="The person agreed to have their voiceprint stored.")],
    files: Annotated[list[UploadFile], File(description="One or more voice samples (3 x 5-10 s works well).")],
) -> SpeakerOut:
    """Enroll a new person from one or more voice samples."""
    if not consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Consent is required: voiceprints are biometric data, enroll only people who agree.",
        )
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name must not be blank.")

    if settings.demo_retention_hours > 0:
        # Free up names (and space) held by enrollments that have already expired.
        await delete_expired(session)
    if settings.max_active_enrollments > 0:
        visitors = await session.scalar(
            select(func.count()).select_from(Speaker).where(Speaker.is_sample.is_(False), is_active())
        )
        if (visitors or 0) >= settings.max_active_enrollments:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The demo is full right now. Enrollments are deleted automatically, so please try again later.",
            )
    if await session.scalar(select(Speaker.id).where(func.lower(Speaker.name) == name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A speaker called '{name}' already exists.")

    clips = await embed_uploads(files, embedder, settings)

    enrolled_at = datetime.now(timezone.utc)
    speaker = Speaker(
        name=name,
        embedding=compute_centroid([c.vector for c in clips]).tolist(),
        consent_given_at=enrolled_at,
        expires_at=(
            enrolled_at + timedelta(hours=settings.demo_retention_hours) if settings.demo_retention_hours > 0 else None
        ),
        samples=[VoiceSample(embedding=c.vector.tolist(), speech_seconds=c.speech_seconds) for c in clips],
    )
    session.add(speaker)
    await session.commit()
    await session.refresh(speaker)
    return _out(speaker, len(clips))


@router.post("/{speaker_id}/samples", response_model=SpeakerOut, dependencies=[Depends(rate_limit)])
async def add_samples(
    speaker_id: int,
    session: SessionDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    files: Annotated[list[UploadFile], File()],
) -> SpeakerOut:
    """Add more samples to an existing speaker (improves accuracy)."""
    speaker = await _get_or_404(session, speaker_id)
    _forbid_sample(speaker)
    clips = await embed_uploads(files, embedder, settings)

    for c in clips:
        session.add(VoiceSample(speaker_id=speaker.id, embedding=c.vector.tolist(), speech_seconds=c.speech_seconds))
    await session.flush()

    all_vectors = (await session.scalars(select(VoiceSample.embedding).where(VoiceSample.speaker_id == speaker.id))).all()
    speaker.embedding = compute_centroid(all_vectors).tolist()
    await session.commit()
    return _out(speaker, len(all_vectors))


@router.get("", response_model=list[SpeakerOut])
async def list_speakers(session: SessionDep) -> list[SpeakerOut]:
    rows = await session.execute(
        select(Speaker, func.count(VoiceSample.id))
        .outerjoin(VoiceSample)
        .where(is_active())
        .group_by(Speaker.id)
        .order_by(Speaker.created_at.desc(), Speaker.id.desc())
    )
    return [_out(speaker, count) for speaker, count in rows.all()]


@router.get("/{speaker_id}", response_model=SpeakerOut)
async def get_speaker(speaker_id: int, session: SessionDep) -> SpeakerOut:
    speaker = await _get_or_404(session, speaker_id)
    return _out(speaker, await _sample_count(session, speaker.id))


@router.delete("/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker(speaker_id: int, session: SessionDep) -> Response:
    """Permanently delete a speaker and all their voiceprints (right to be forgotten)."""
    speaker = await _get_or_404(session, speaker_id)
    _forbid_sample(speaker)
    await session.delete(speaker)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

## `voice-id/backend/app/schemas.py`

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class IdentifyOut(BaseModel):
    label: str  # the speaker's name, or "unknown"
    is_match: bool
    speaker_id: int | None
    score: float  # cosine similarity of the best candidate (confidence)
    threshold: float
    reason: str
    speech_seconds: float
    candidates: list[CandidateOut]


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    threshold: float
    speakers: int
    demo_retention_hours: float  # visitor enrollments are deleted after this long (0 = never)
```

## `voice-id/backend/app/services.py`

```python
"""Glue between HTTP uploads, audio preprocessing and the embedding model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from .audio import AudioError, preprocess
from .config import Settings
from .embedding import Embedder


@dataclass(frozen=True)
class ClipEmbedding:
    filename: str
    vector: np.ndarray
    speech_seconds: float


def get_embedder(request: Request) -> Embedder:
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model is still loading, try again shortly.")
    return embedder


async def embed_upload(upload: UploadFile, embedder: Embedder, settings: Settings) -> ClipEmbedding:
    """Read one uploaded file, clean it up and return its voiceprint."""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"'{upload.filename}' is larger than {settings.max_upload_mb} MB.",
        )

    def work() -> ClipEmbedding:
        # FFmpeg + the neural network are CPU-bound, so they run in a worker
        # thread and do not block the event loop for other requests.
        prepared = preprocess(data, settings.min_speech_seconds, settings.max_clip_seconds)
        return ClipEmbedding(upload.filename or "clip", embedder.embed(prepared.samples), prepared.speech_seconds)

    try:
        return await run_in_threadpool(work)
    except AudioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{upload.filename}: {exc}") from exc


async def embed_uploads(uploads: list[UploadFile], embedder: Embedder, settings: Settings) -> list[ClipEmbedding]:
    if not uploads:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Upload at least one voice sample.")
    if len(uploads) > settings.max_files_per_request:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"At most {settings.max_files_per_request} files per request.",
        )
    return [await embed_upload(u, embedder, settings) for u in uploads]
```

## `voice-id/backend/db-init/01-test-db.sql`

```sql
-- Runs once when the Postgres volume is first created.
-- A separate database for the automated tests so they never touch real data.
CREATE DATABASE voiceid_test OWNER voiceid;
```

## `voice-id/backend/pytest.ini`

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
testpaths = tests
```

## `voice-id/backend/requirements-dev.txt`

```text
pytest==8.3.4
pytest-asyncio==0.25.0
httpx==0.28.1
```

## `voice-id/backend/requirements.txt`

```text
# Web API
fastapi==0.115.6
uvicorn[standard]==0.32.1
python-multipart==0.0.20
pydantic-settings==2.7.0

# Database: PostgreSQL + pgvector
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
pgvector==0.3.6

# Audio + ML (CPU-only PyTorch wheels come from the extra index in the Dockerfile)
numpy==2.1.3
torch==2.5.1
torchaudio==2.5.1
speechbrain==1.0.3
huggingface_hub==0.25.2  # speechbrain 1.0.3 breaks with >=0.26 (use_auth_token removed)
requests==2.32.3   # used by speechbrain to download the model
soundfile==0.12.1  # silences speechbrain's "no torchaudio backend" warning
```

## `voice-id/backend/sample_voices/ATTRIBUTION.md`

```markdown
# Sample voices

Each folder is one built-in demo speaker. Its clips are enrolled automatically on startup
when `SEED_SAMPLE_VOICES=true`, so the public demo always has someone to match.

The recordings come from **LibriSpeech** (dev-clean), by Vassil Panayotov, Guoguo Chen, Daniel Povey and
Sanjeev Khudanpur, built from public-domain LibriVox audiobooks. They are licensed under
**CC BY 4.0**: https://www.openslr.org/12

They were converted to mono 32 kbps Opus (webm) to keep them small. Speaker numbers are the
LibriSpeech speaker IDs.
```

## `voice-id/backend/scripts/e2e_demo.py`

```python
"""End-to-end demo against the running API, using real voices.

1. Enrolls the first --speakers speakers from /data/samples (2 clips each).
2. Identifies their held-out clips, converted to wav, mp3 AND webm/opus
   (the format browsers record in) - each should return the right name.
3. Identifies clips from a speaker who was never enrolled - should be "unknown".

    docker compose run --rm api python scripts/e2e_demo.py --api http://api:8000
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx

FORMATS = {
    "wav": ["-f", "wav"],
    "mp3": ["-f", "mp3", "-b:a", "64k"],
    "webm": ["-f", "webm", "-c:a", "libopus", "-b:a", "32k"],
}
MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "webm": "audio/webm"}


def convert(path: Path, fmt: str) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), *FORMATS[fmt], "pipe:1"],
        capture_output=True, check=True,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://api:8000")
    parser.add_argument("--data", default="/data/samples")
    parser.add_argument("--speakers", type=int, default=3)
    parser.add_argument("--tests-per-speaker", type=int, default=2)
    args = parser.parse_args()

    folders = sorted(p for p in Path(args.data).iterdir() if p.is_dir())
    enrolled, stranger = folders[: args.speakers], folders[args.speakers]
    client = httpx.Client(base_url=args.api, timeout=120)

    # Start clean: remove speakers left from a previous demo run.
    demo_names = {f"Speaker {f.name}" for f in folders}
    for s in client.get("/speakers").json():
        if s["name"] in demo_names:
            client.delete(f"/speakers/{s['id']}")

    print("== Enrollment ==")
    for folder in enrolled:
        clips = sorted(folder.iterdir())[:2]
        files = [("files", (c.name, c.read_bytes(), "audio/flac")) for c in clips]
        r = client.post("/speakers", data={"name": f"Speaker {folder.name}", "consent": "true"}, files=files)
        r.raise_for_status()
        print(f"  enrolled {r.json()['name']!r} with {r.json()['sample_count']} samples")

    print("\n== Identification ==")
    passed = total = 0
    for folder in [*enrolled, stranger]:
        expected = "unknown" if folder is stranger else f"Speaker {folder.name}"
        for clip in sorted(folder.iterdir())[2 : 2 + args.tests_per_speaker]:
            for fmt in FORMATS:
                r = client.post("/identify", files={"file": (f"{clip.stem}.{fmt}", convert(clip, fmt), MIME[fmt])})
                if r.status_code == 422:  # e.g. too little speech - the API rejects it on purpose
                    print(f"  SKIP  {clip.name:<22} {fmt:<5} -> {r.json()['detail']}")
                    continue
                r.raise_for_status()
                body = r.json()
                ok = body["label"] == expected
                passed += ok
                total += 1
                print(
                    f"  {'PASS' if ok else 'FAIL'}  {clip.name:<22} {fmt:<5} -> {body['label']:<16}"
                    f" score {body['score']:.3f}  (expected {expected})"
                )

    print(f"\n{passed}/{total} correct (threshold {body['threshold']})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
```

## `voice-id/backend/scripts/fetch_samples.py`

```python
"""Download a few real voices to test with (a few MB).

Source: LibriSpeech dev-clean (people reading audiobooks, CC BY 4.0, recorded
for public research use), fetched clip-by-clip through the Hugging Face
dataset viewer API so we never download the full 340 MB file.

Output: /data/samples/<speaker_id>/<utterance>.flac

    docker compose run --rm api python scripts/fetch_samples.py
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROWS_URL = (
    "https://datasets-server.huggingface.co/rows?dataset=openslr/librispeech_asr"
    "&config=clean&split=validation&offset={offset}&length={length}"
)
TOTAL_ROWS = 2703  # size of dev-clean; rows are grouped by speaker


def get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/data/samples")
    parser.add_argument("--speakers", type=int, default=8)
    parser.add_argument("--clips", type=int, default=6, help="clips per speaker")
    args = parser.parse_args()

    out = Path(args.out)
    saved: dict[str, int] = {}
    # Jump through the dataset so each page lands on a different speaker.
    step = TOTAL_ROWS // (args.speakers + 1)
    for offset in range(0, TOTAL_ROWS, step):
        if len([s for s, n in saved.items() if n >= args.clips]) >= args.speakers:
            break
        rows = json.loads(get(ROWS_URL.format(offset=offset, length=args.clips * 2)))["rows"]
        for item in rows:
            row = item["row"]
            speaker = str(row["speaker_id"])
            if saved.get(speaker, 0) >= args.clips:
                continue
            folder = out / speaker
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{row['id']}.flac").write_bytes(get(row["audio"][0]["src"]))
            saved[speaker] = saved.get(speaker, 0) + 1

    for speaker, n in saved.items():
        print(f"  speaker {speaker}: {n} clips")
    print(f"Saved {len(saved)} speakers to {out}")


if __name__ == "__main__":
    main()
```

## `voice-id/backend/scripts/tune_threshold.py`

```python
"""Pick the "unknown" threshold from real data.

For every speaker folder in --data:
  * the first --enroll clips build that speaker's centroid (like enrollment),
  * every remaining clip is a test clip.
Each test clip is scored against its OWN centroid (a "genuine" score) and
against every OTHER speaker's centroid (an "impostor" score).

A good threshold sits between the two groups. We report:
  * the Equal Error Rate (EER) threshold - false accepts == false rejects,
  * a sweep of thresholds with false-accept / false-reject rates and
    open-set identification accuracy (where some speakers are "strangers").

    docker compose run --rm api python scripts/tune_threshold.py --data /data/samples
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audio import AudioError, preprocess  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embedding import EcapaEmbedder  # noqa: E402
from app.matching import UNKNOWN_LABEL, compute_centroid, decide, equal_error_rate, rank_candidates  # noqa: E402

AUDIO_EXT = {".wav", ".flac", ".mp3", ".webm", ".ogg", ".m4a"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/data/samples")
    parser.add_argument("--enroll", type=int, default=2, help="clips per speaker used for enrollment")
    args = parser.parse_args()

    settings = get_settings()
    embedder = EcapaEmbedder(settings.model_source, settings.model_dir, settings.torch_threads)

    folders = sorted(p for p in Path(args.data).iterdir() if p.is_dir())
    centroids: dict[str, np.ndarray] = {}
    tests: list[tuple[str, np.ndarray]] = []
    for folder in folders:
        vecs = []
        for f in sorted(f for f in folder.iterdir() if f.suffix.lower() in AUDIO_EXT):
            try:
                vecs.append(embedder.embed(preprocess(f.read_bytes()).samples))
            except AudioError as exc:
                print(f"  skipping {f.name}: {exc}")
        if len(vecs) <= args.enroll:
            continue
        centroids[folder.name] = compute_centroid(vecs[: args.enroll])
        tests += [(folder.name, v) for v in vecs[args.enroll :]]
        print(f"speaker {folder.name}: {args.enroll} enroll + {len(vecs) - args.enroll} test clips")

    names = list(centroids)
    genuine, impostor = [], []
    for owner, vec in tests:
        for name in names:
            score = float(np.dot(vec, centroids[name]))
            (genuine if name == owner else impostor).append(score)

    g, i = np.array(genuine), np.array(impostor)
    print(f"\n{len(names)} speakers, {len(g)} genuine and {len(i)} impostor comparisons")
    print(f"genuine  scores: min {g.min():.3f}  mean {g.mean():.3f}  max {g.max():.3f}")
    print(f"impostor scores: min {i.min():.3f}  mean {i.mean():.3f}  max {i.max():.3f}")
    eer, eer_t = equal_error_rate(g, i)
    print(f"EER {eer:.1%} at threshold {eer_t:.3f}")

    # Open-set check: leave each speaker out of the database in turn, so their
    # clips must come back "unknown", while everyone else's must be named.
    print("\nthreshold   FAR     FRR    open-set accuracy")
    for t in np.arange(0.20, 0.71, 0.05):
        far, frr = float(np.mean(i >= t)), float(np.mean(g < t))
        correct = total = 0
        for left_out in names:
            enrolled = [(k, n, centroids[n]) for k, n in enumerate(names) if n != left_out]
            for owner, vec in tests:
                expected = UNKNOWN_LABEL if owner == left_out else owner
                correct += decide(rank_candidates(vec, enrolled), float(t)).label == expected
                total += 1
        print(f"  {t:.2f}     {far:6.1%}  {frr:6.1%}   {correct / total:6.1%}")


if __name__ == "__main__":
    main()
```

## `voice-id/backend/tests/__init__.py`

```python

```

## `voice-id/backend/tests/helpers.py`

```python
"""Test helpers: synthetic audio and a fake embedder (no PyTorch needed)."""

import io
import wave

import numpy as np

from app.matching import l2_normalize


def tone_wav(freq_hz: float, seconds: float = 2.0, sample_rate: int = 22_050, silence: float = 0.0) -> bytes:
    """A sine 'voice' at freq_hz, optionally padded with silence on both sides.

    The odd sample rate (22.05 kHz) checks that resampling to 16 kHz works.
    """
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    tone = 0.5 * np.sin(2 * np.pi * freq_hz * t)
    pad = np.zeros(int(silence * sample_rate))
    signal = np.concatenate([pad, tone, pad])
    pcm = (signal * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class FakeEmbedder:
    """Maps the dominant pitch of a clip to a 192-d vector.

    Clips with the same pitch get the same "voiceprint", very different pitches
    get unrelated ones - just like a real speaker model, but deterministic.
    """

    def embed(self, samples: np.ndarray) -> np.ndarray:
        spectrum = np.abs(np.fft.rfft(samples))
        freq = np.argmax(spectrum) * 16_000 / len(samples)
        centre = freq / 50.0  # one "dimension" per 50 Hz
        x = np.arange(192)
        return l2_normalize(np.exp(-0.5 * ((x - centre) / 1.5) ** 2) + 1e-6)
```

## `voice-id/backend/tests/test_api.py`

```python
"""API tests against a real PostgreSQL + pgvector database, with a fake embedder.

Run inside Docker:  docker compose run --rm api pytest
They are skipped when TEST_DATABASE_URL is not set.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import Settings
from app.main import create_app

from .helpers import FakeEmbedder, tone_wav

TEST_DB = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")


@pytest.fixture
async def client():
    app = create_app(Settings(database_url=TEST_DB, match_threshold=0.5), embedder=FakeEmbedder())
    async with app.router.lifespan_context(app):
        async with app.state.sessionmaker() as s:
            await s.execute(text("TRUNCATE speakers, voice_samples RESTART IDENTITY CASCADE"))
            await s.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c


def wav(name, freq, **kw):
    return ("files", (name, tone_wav(freq, **kw), "audio/wav"))


async def enroll(client, name, *freqs, consent="true"):
    files = [wav(f"{name}{i}.wav", f) for i, f in enumerate(freqs)]
    return await client.post("/speakers", data={"name": name, "consent": consent}, files=files)


async def test_enroll_list_identify_delete(client):
    r = await enroll(client, "Ada", 200, 205)
    assert r.status_code == 201, r.text
    ada = r.json()
    assert ada["name"] == "Ada" and ada["sample_count"] == 2

    assert (await enroll(client, "Bayo", 600)).status_code == 201

    speakers = (await client.get("/speakers")).json()
    assert {s["name"] for s in speakers} == {"Ada", "Bayo"}

    # A new clip at Ada's "pitch" (with silence around it) -> Ada.
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(200, silence=0.5), "audio/wav")})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["label"] == "Ada" and body["is_match"] is True
    assert body["score"] > 0.9
    assert body["candidates"][0]["name"] == "Ada"

    # A voice nobody enrolled with -> unknown.
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(1500), "audio/wav")})
    assert r.json()["label"] == "unknown" and r.json()["is_match"] is False

    # Delete Ada: her voice is no longer recognised.
    assert (await client.delete(f"/speakers/{ada['id']}")).status_code == 204
    assert (await client.get(f"/speakers/{ada['id']}")).status_code == 404
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
    assert r.json()["label"] == "unknown"


async def test_enroll_requires_consent(client):
    r = await enroll(client, "Ada", 200, consent="false")
    assert r.status_code == 400
    assert "Consent" in r.json()["detail"]


async def test_duplicate_name_is_rejected(client):
    await enroll(client, "Ada", 200)
    assert (await enroll(client, "ada", 300)).status_code == 409


async def test_bad_audio_is_rejected(client):
    r = await client.post(
        "/speakers", data={"name": "X", "consent": "true"}, files=[("files", ("x.wav", b"nope", "audio/wav"))]
    )
    assert r.status_code == 422


async def test_add_samples_updates_count(client):
    ada = (await enroll(client, "Ada", 200)).json()
    r = await client.post(f"/speakers/{ada['id']}/samples", files=[wav("more.wav", 210)])
    assert r.status_code == 200 and r.json()["sample_count"] == 2


async def test_identify_with_no_speakers(client):
    r = await client.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
    assert r.json()["label"] == "unknown"
    assert r.json()["candidates"] == []


async def test_health(client):
    body = (await client.get("/health")).json()
    assert body["status"] == "ok" and body["model_loaded"] is True and body["threshold"] == 0.5
```

## `voice-id/backend/tests/test_audio.py`

```python
import shutil

import numpy as np
import pytest

from app.audio import SAMPLE_RATE, AudioError, decode_to_mono_16k, preprocess, trim_silence

from .helpers import tone_wav

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_trim_silence_removes_leading_and_trailing_silence():
    speech = 0.5 * np.sin(2 * np.pi * 200 * np.arange(SAMPLE_RATE) / SAMPLE_RATE)
    silence = np.zeros(SAMPLE_RATE)
    trimmed = trim_silence(np.concatenate([silence, speech, silence]).astype(np.float32))
    # ~1 s of speech plus a little padding, instead of 3 s.
    assert 0.95 < trimmed.size / SAMPLE_RATE < 1.3


def test_trim_silence_on_pure_silence_returns_empty():
    assert trim_silence(np.zeros(SAMPLE_RATE, dtype=np.float32)).size == 0


def test_trim_silence_ignores_quiet_hiss():
    hiss = np.random.default_rng(0).normal(scale=1e-4, size=SAMPLE_RATE).astype(np.float32)
    assert trim_silence(hiss).size == 0


@needs_ffmpeg
def test_decode_resamples_to_16k_mono():
    audio = decode_to_mono_16k(tone_wav(300, seconds=2.0, sample_rate=44_100))
    assert audio.dtype == np.float32
    assert abs(audio.size - 2 * SAMPLE_RATE) < 200


@needs_ffmpeg
def test_decode_rejects_garbage():
    with pytest.raises(AudioError):
        decode_to_mono_16k(b"this is not audio")


@needs_ffmpeg
def test_preprocess_trims_and_reports_durations():
    prepared = preprocess(tone_wav(250, seconds=2.0, silence=1.0))
    assert prepared.original_seconds == pytest.approx(4.0, abs=0.05)
    assert 1.9 < prepared.speech_seconds < 2.3
    assert np.max(np.abs(prepared.samples)) == pytest.approx(0.95, abs=0.01)


@needs_ffmpeg
def test_preprocess_rejects_too_little_speech():
    with pytest.raises(AudioError, match="speech"):
        preprocess(tone_wav(250, seconds=0.4, silence=1.0), min_speech_seconds=1.0)
```

## `voice-id/backend/tests/test_demo.py`

```python
"""Tests for the public-demo rules: expiry, sample voices, rate limit, database URLs."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text, update

from app.config import Settings, normalize_database_url
from app.demo import RateLimiter, delete_expired, seed_sample_voices
from app.main import create_app
from app.models import Speaker, VoiceSample

from .helpers import FakeEmbedder, tone_wav

TEST_DB = os.getenv("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")


# ---------- pure functions (no database) ----------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # What Neon gives you
        (
            "postgresql://u:p@ep-x.neon.tech/voiceid?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/voiceid?ssl=require",
        ),
        ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        # Already correct: unchanged
        ("postgresql+asyncpg://u:p@db:5432/voiceid", "postgresql+asyncpg://u:p@db:5432/voiceid"),
        ("postgresql://u:p@h/db?sslmode=disable", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_normalize_database_url(given, expected):
    assert normalize_database_url(given) == expected
    assert Settings(database_url=given).database_url == expected


def test_rate_limiter_allows_up_to_limit_per_key():
    limiter = RateLimiter(limit=2)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")  # other visitors are not affected


def test_rate_limiter_zero_means_off():
    limiter = RateLimiter(limit=0)
    assert all(limiter.allow("a") for _ in range(100))


# ---------- API with a real database ----------


def make_client(**overrides):
    settings = Settings(database_url=TEST_DB, match_threshold=0.5, **overrides)
    return create_app(settings, embedder=FakeEmbedder())


async def started(app):
    ctx = app.router.lifespan_context(app)
    await ctx.__aenter__()
    async with app.state.sessionmaker() as s:
        await s.execute(text("TRUNCATE speakers, voice_samples RESTART IDENTITY CASCADE"))
        await s.commit()
    return ctx


def wav(freq):
    return ("files", ("v.wav", tone_wav(freq), "audio/wav"))


@needs_db
async def test_enrollment_expires_and_is_cleaned_up():
    app = make_client(demo_retention_hours=24)
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            ada = (await c.post("/speakers", data={"name": "Ada", "consent": "true"}, files=[wav(200)])).json()
            expires = datetime.fromisoformat(ada["expires_at"])
            assert timedelta(hours=23.9) < expires - datetime.now(timezone.utc) <= timedelta(hours=24)
            assert ada["is_sample"] is False

            # Pretend 24 hours have passed.
            async with app.state.sessionmaker() as s:
                await s.execute(
                    update(Speaker).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
                )
                await s.commit()

            # Expired speakers vanish at once from every endpoint...
            assert (await c.get("/speakers")).json() == []
            assert (await c.get(f"/speakers/{ada['id']}")).status_code == 404
            r = await c.post("/identify", files={"file": ("q.wav", tone_wav(200), "audio/wav")})
            assert r.json()["label"] == "unknown"
            assert (await c.get("/health")).json()["demo_retention_hours"] == 24

            # ...and the name is free again, because enrolling clears expired rows first.
            again = await c.post("/speakers", data={"name": "Ada", "consent": "true"}, files=[wav(200)])
            assert again.status_code == 201

        # The cleanup job deletes expired rows and their voice samples for good.
        async with app.state.sessionmaker() as s:
            await s.execute(update(Speaker).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
            await s.commit()
            assert await delete_expired(s) == 1
            assert (await s.scalars(select(VoiceSample.id))).all() == []
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_no_expiry_by_default():
    app = make_client()
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            ada = (await c.post("/speakers", data={"name": "Ada", "consent": "true"}, files=[wav(200)])).json()
            assert ada["expires_at"] is None
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_sample_voices_are_seeded_once_and_protected(tmp_path: Path):
    for name, freq in [("Reader A", 300), ("Reader B", 700)]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "1.wav").write_bytes(tone_wav(freq))

    app = make_client(demo_retention_hours=24)
    ctx = await started(app)
    try:
        assert await seed_sample_voices(app.state.sessionmaker, app.state.embedder, tmp_path) == 2
        assert await seed_sample_voices(app.state.sessionmaker, app.state.embedder, tmp_path) == 0  # idempotent

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            speakers = (await c.get("/speakers")).json()
            assert {s["name"] for s in speakers} == {"Reader A", "Reader B"}
            assert all(s["is_sample"] and s["expires_at"] is None for s in speakers)

            r = await c.post("/identify", files={"file": ("q.wav", tone_wav(700), "audio/wav")})
            assert r.json()["label"] == "Reader B"

            sample_id = speakers[0]["id"]
            assert (await c.delete(f"/speakers/{sample_id}")).status_code == 403
            assert (await c.post(f"/speakers/{sample_id}/samples", files=[wav(300)])).status_code == 403
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_demo_full_limit():
    app = make_client(max_active_enrollments=1)
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            assert (await c.post("/speakers", data={"name": "A", "consent": "true"}, files=[wav(200)])).status_code == 201
            r = await c.post("/speakers", data={"name": "B", "consent": "true"}, files=[wav(600)])
            assert r.status_code == 503
    finally:
        await ctx.__aexit__(None, None, None)


@needs_db
async def test_rate_limit_returns_429():
    app = make_client(rate_limit_per_minute=2)
    ctx = await started(app)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            clip = {"file": ("q.wav", tone_wav(200), "audio/wav")}
            assert (await c.post("/identify", files=clip)).status_code == 200
            assert (await c.post("/identify", files=clip)).status_code == 200
            r = await c.post("/identify", files=clip)
            assert r.status_code == 429
            assert "Too many requests" in r.json()["detail"]
            assert (await c.get("/speakers")).status_code == 200  # reading is never limited
    finally:
        await ctx.__aexit__(None, None, None)
```

## `voice-id/backend/tests/test_matching.py`

```python
import numpy as np
import pytest

from app.matching import (
    UNKNOWN_LABEL,
    Candidate,
    compute_centroid,
    cosine_similarity,
    decide,
    equal_error_rate,
    l2_normalize,
    rank_candidates,
)


def test_l2_normalize_gives_unit_length():
    v = l2_normalize([3.0, 4.0])
    assert np.allclose(v, [0.6, 0.8])
    assert np.isclose(np.linalg.norm(v), 1.0)


def test_l2_normalize_rejects_zero_vector():
    with pytest.raises(ValueError):
        l2_normalize([0.0, 0.0])


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ([1, 0], [1, 0], 1.0),  # same direction
        ([1, 0], [0, 1], 0.0),  # unrelated
        ([1, 0], [-1, 0], -1.0),  # opposite
        ([1, 0], [5, 0], 1.0),  # length does not matter
    ],
)
def test_cosine_similarity(a, b, expected):
    assert cosine_similarity(a, b) == pytest.approx(expected)


def test_cosine_similarity_shape_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity([1, 0], [1, 0, 0])


def test_centroid_is_unit_length_average_direction():
    c = compute_centroid([[1, 0], [0, 1]])
    assert np.allclose(c, [np.sqrt(0.5), np.sqrt(0.5)])


def test_centroid_weights_each_clip_equally():
    # A "loud" clip (long vector) must not dominate a "quiet" one.
    assert np.allclose(compute_centroid([[100, 0], [0, 1]]), compute_centroid([[1, 0], [0, 1]]))


def test_centroid_needs_embeddings():
    with pytest.raises(ValueError):
        compute_centroid([])


def test_rank_candidates_orders_best_first():
    speakers = [(1, "Ada", [1, 0, 0]), (2, "Bayo", [0, 1, 0]), (3, "Chi", [0.7, 0.7, 0])]
    ranked = rank_candidates([0.9, 0.1, 0], speakers)
    assert [c.name for c in ranked] == ["Ada", "Chi", "Bayo"]
    assert ranked[0].score > ranked[1].score > ranked[2].score


def test_decide_returns_best_speaker_above_threshold():
    d = decide([Candidate(2, "Bayo", 0.30), Candidate(1, "Ada", 0.82)], threshold=0.4)
    assert d.is_match and d.label == "Ada" and d.speaker_id == 1
    assert d.score == pytest.approx(0.82)


def test_decide_unknown_below_threshold():
    d = decide([Candidate(1, "Ada", 0.25)], threshold=0.4)
    assert not d.is_match
    assert d.label == UNKNOWN_LABEL and d.speaker_id is None
    assert d.score == pytest.approx(0.25)  # still reported, for transparency


def test_decide_score_equal_to_threshold_is_a_match():
    assert decide([Candidate(1, "Ada", 0.4)], threshold=0.4).is_match


def test_decide_with_no_speakers():
    d = decide([], threshold=0.4)
    assert d.label == UNKNOWN_LABEL and not d.is_match


def test_decide_margin_rejects_ambiguous_result():
    cands = [Candidate(1, "Ada", 0.71), Candidate(2, "Bayo", 0.69)]
    assert decide(cands, threshold=0.4).label == "Ada"  # margin check off by default
    assert decide(cands, threshold=0.4, min_margin=0.05).label == UNKNOWN_LABEL


def test_end_to_end_with_synthetic_voiceprints():
    """Two 'people' whose clips scatter around their own true voiceprint."""
    rng = np.random.default_rng(0)
    ada_true, bayo_true, stranger = (l2_normalize(rng.normal(size=192)) for _ in range(3))

    def clip(true_vec):
        return l2_normalize(true_vec + rng.normal(scale=0.04, size=192))

    speakers = [
        (1, "Ada", compute_centroid([clip(ada_true) for _ in range(3)])),
        (2, "Bayo", compute_centroid([clip(bayo_true) for _ in range(3)])),
    ]
    assert decide(rank_candidates(clip(ada_true), speakers), 0.4).label == "Ada"
    assert decide(rank_candidates(clip(bayo_true), speakers), 0.4).label == "Bayo"
    assert decide(rank_candidates(clip(stranger), speakers), 0.4).label == UNKNOWN_LABEL


def test_equal_error_rate_perfect_separation():
    eer, threshold = equal_error_rate(genuine=[0.7, 0.8, 0.9], impostor=[0.1, 0.2, 0.3])
    assert eer == 0.0
    assert 0.3 < threshold <= 0.7


def test_equal_error_rate_overlap():
    eer, _ = equal_error_rate(genuine=[0.2, 0.8, 0.9], impostor=[0.1, 0.3, 0.85])
    assert 0.0 < eer < 0.5
```

## `voice-id/deploy/huggingface-space/Dockerfile`

```dockerfile
# Voice ID API for a free Hugging Face Space (Docker SDK, CPU basic: 2 vCPU, 16 GB RAM).
#
# Free Spaces can only open outgoing connections on web ports, so they can't reach an
# external PostgreSQL. This image therefore runs its own PostgreSQL + pgvector next to the
# API. Data lives only while the Space runs: sample voices are re-enrolled on every start,
# and visitors' enrollments are deleted after DEMO_RETENTION_HOURS anyway.
#
# The first steps are identical to backend/Dockerfile so Docker can reuse its cached layers.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt -r requirements-dev.txt

ENV MODEL_DIR=/models/spkrec-ecapa-voxceleb

# Bake the pretrained model into the image (no download at start-up).
RUN python -c "from speechbrain.inference.speaker import EncoderClassifier; \
EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir='/models/spkrec-ecapa-voxceleb')" \
    && chmod -R a+rwX /models

# --- Space-specific from here on ---

# A private PostgreSQL with the pgvector extension.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs the container as user 1000.
RUN useradd --create-home --uid 1000 user

ENV PATH="/usr/lib/postgresql/17/bin:${PATH}" \
    # Public-demo settings. Override any of them under the Space's Settings -> Variables.
    DEMO_RETENTION_HOURS=24 \
    MAX_ACTIVE_ENROLLMENTS=100 \
    RATE_LIMIT_PER_MINUTE=20 \
    TRUST_PROXY_HEADERS=true \
    SEED_SAMPLE_VOICES=true \
    TORCH_THREADS=2 \
    PORT=7860

COPY --chown=user . .
RUN chmod +x start.sh

USER user
EXPOSE 7860
CMD ["./start.sh"]
```

## `voice-id/deploy/huggingface-space/README.md`

```markdown
---
title: Voice ID API
emoji: 🎙️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Speaker recognition API (ECAPA-TDNN + pgvector)
---

# Voice ID API

The backend of [Voice ID](https://github.com/Abigail56): enroll people by voice and identify who is speaking.
A pretrained SpeechBrain ECAPA-TDNN model turns each clip into a 192-number voiceprint, and pgvector
finds the closest enrolled speaker by cosine similarity.

- Interactive API docs: open `/docs` on this Space.
- Try it with a microphone on the portfolio's live demo page.

**Privacy:** visitors' voiceprints are deleted automatically after 24 hours, raw audio is never stored,
and anyone can delete an enrollment at any time. Built-in sample voices are LibriSpeech readers (CC BY 4.0).
```

## `voice-id/deploy/huggingface-space/start.sh`

```bash
#!/bin/sh
# Start a private PostgreSQL inside the container, then the API.
set -e

PGDATA=/tmp/pgdata
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" -U voiceid --auth=trust >/dev/null
fi
pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -k /tmp" -l /tmp/postgres.log -w start
createdb -h 127.0.0.1 -U voiceid voiceid 2>/dev/null || true

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://voiceid@127.0.0.1:5432/voiceid}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips '*'
```

## `voice-id/deploy/make-hf-space.sh`

```bash
#!/bin/sh
# Builds dist/hf-space/: everything a Hugging Face Space needs, ready to upload.
#   sh deploy/make-hf-space.sh        (run from the voice-id folder)
set -e
cd "$(dirname "$0")/.."
rm -rf dist/hf-space
mkdir -p dist/hf-space
# The backend code, without tests, caches and local scripts...
tar -C backend --exclude=tests --exclude=scripts --exclude='__pycache__' --exclude='.pytest_cache' \
    --exclude='.venv' --exclude=db-init --exclude=Dockerfile --exclude=pytest.ini -cf - . \
  | tar -C dist/hf-space -xf -
# ...plus the Space's own Dockerfile, start script and README (with the Space settings at the top).
cp deploy/huggingface-space/Dockerfile deploy/huggingface-space/start.sh deploy/huggingface-space/README.md dist/hf-space/
echo "Ready: $(pwd)/dist/hf-space"
find dist/hf-space -type f | sort
```

## `voice-id/docker-compose.yml`

```yaml
# Ports are shifted (5442, 8010, 3010) so they do not clash with a local
# PostgreSQL on 5432 or other apps on 8000/3000.
name: voice-id

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: voiceid
      POSTGRES_PASSWORD: voiceid
      POSTGRES_DB: voiceid
    ports:
      - "5442:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/db-init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U voiceid -d voiceid"]
      interval: 3s
      timeout: 3s
      retries: 20

  api:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://voiceid:voiceid@db:5432/voiceid
      TEST_DATABASE_URL: postgresql+asyncpg://voiceid:voiceid@db:5432/voiceid_test
      MATCH_THRESHOLD: ${MATCH_THRESHOLD:-0.40}
      # The Voice ID UI (3010) and the portfolio demo page (3001) may call this API.
      CORS_ORIGINS: http://localhost:3010,http://localhost:3001
    ports:
      - "8010:8000"
    volumes:
      - models:/models          # pretrained model cache (downloaded once)
      - ./data:/data            # sample voices for scripts/ (optional)
    depends_on:
      db:
        condition: service_healthy

  web:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8010
    ports:
      - "3010:3000"
    depends_on:
      - api

volumes:
  pgdata:
  models:
```

## `voice-id/docs/e2e-demo-output.txt`

```text
== Enrollment ==
  enrolled 'Speaker 1272' with 2 samples
  enrolled 'Speaker 1988' with 2 samples
  enrolled 'Speaker 2277' with 2 samples

== Identification ==
  PASS  1272-135031-0013.flac  wav   -> Speaker 1272     score 0.649  (expected Speaker 1272)
  PASS  1272-135031-0013.flac  mp3   -> Speaker 1272     score 0.642  (expected Speaker 1272)
  PASS  1272-135031-0013.flac  webm  -> Speaker 1272     score 0.616  (expected Speaker 1272)
  SKIP  1272-135031-0014.flac  wav   -> 1272-135031-0014.wav: Only 0.8s of speech found; please record at least 1s of clear speech.
  SKIP  1272-135031-0014.flac  mp3   -> 1272-135031-0014.mp3: Only 0.9s of speech found; please record at least 1s of clear speech.
  SKIP  1272-135031-0014.flac  webm  -> 1272-135031-0014.webm: Only 0.8s of speech found; please record at least 1s of clear speech.
  PASS  1988-147956-0002.flac  wav   -> Speaker 1988     score 0.729  (expected Speaker 1988)
  PASS  1988-147956-0002.flac  mp3   -> Speaker 1988     score 0.707  (expected Speaker 1988)
  PASS  1988-147956-0002.flac  webm  -> Speaker 1988     score 0.719  (expected Speaker 1988)
  PASS  1988-147956-0003.flac  wav   -> Speaker 1988     score 0.744  (expected Speaker 1988)
  PASS  1988-147956-0003.flac  mp3   -> Speaker 1988     score 0.729  (expected Speaker 1988)
  PASS  1988-147956-0003.flac  webm  -> Speaker 1988     score 0.748  (expected Speaker 1988)
  PASS  2277-149896-0002.flac  wav   -> Speaker 2277     score 0.827  (expected Speaker 2277)
  PASS  2277-149896-0002.flac  mp3   -> Speaker 2277     score 0.799  (expected Speaker 2277)
  PASS  2277-149896-0002.flac  webm  -> Speaker 2277     score 0.798  (expected Speaker 2277)
  PASS  2277-149896-0003.flac  wav   -> Speaker 2277     score 0.793  (expected Speaker 2277)
  PASS  2277-149896-0003.flac  mp3   -> Speaker 2277     score 0.776  (expected Speaker 2277)
  PASS  2277-149896-0003.flac  webm  -> Speaker 2277     score 0.782  (expected Speaker 2277)
  PASS  251-137823-0020.flac   wav   -> unknown          score 0.143  (expected unknown)
  PASS  251-137823-0020.flac   mp3   -> unknown          score 0.116  (expected unknown)
  PASS  251-137823-0020.flac   webm  -> unknown          score 0.170  (expected unknown)
  PASS  251-137823-0021.flac   wav   -> unknown          score 0.134  (expected unknown)
  PASS  251-137823-0021.flac   mp3   -> unknown          score 0.153  (expected unknown)
  PASS  251-137823-0021.flac   webm  -> unknown          score 0.141  (expected unknown)

21/21 correct (threshold 0.4)
```

## `voice-id/docs/threshold-tuning.txt`

```text
Output of: docker compose run --rm api python scripts/tune_threshold.py --data /data/samples
Data: 9 LibriSpeech dev-clean speakers, 2 enrollment clips + 3-4 test clips each (2026-10-19)

  skipping 1272-135031-0014.flac: Only 0.8s of speech found; please record at least 1s of clear speech.
speaker 1272: 2 enroll + 3 test clips
speaker 1988: 2 enroll + 4 test clips
speaker 2277: 2 enroll + 4 test clips
speaker 251: 2 enroll + 4 test clips
speaker 3752: 2 enroll + 4 test clips
speaker 5694: 2 enroll + 4 test clips
speaker 6313: 2 enroll + 4 test clips
speaker 7976: 2 enroll + 3 test clips
speaker 8297: 2 enroll + 4 test clips

9 speakers, 34 genuine and 272 impostor comparisons
genuine  scores: min 0.350  mean 0.716  max 0.913
impostor scores: min -0.108  mean 0.098  max 0.350
EER 0.2% at threshold 0.350

threshold   FAR     FRR    open-set accuracy
  0.20      14.7%    0.0%    91.5%
  0.25       6.2%    0.0%    95.4%
  0.30       1.5%    0.0%    98.7%
  0.35       0.4%    2.9%    97.1%
  0.40       0.0%    2.9%    97.4%
  0.45       0.0%    2.9%    97.4%
  0.50       0.0%    8.8%    92.2%
  0.55       0.0%   11.8%    89.5%
  0.60       0.0%   17.6%    84.3%
  0.65       0.0%   23.5%    79.1%
  0.70       0.0%   35.3%    68.6%
```

## `voice-id/frontend/.dockerignore`

```
node_modules
.next
```

## `voice-id/frontend/.env.example`

```bash
# Where the FastAPI backend runs (baked in at build time).
NEXT_PUBLIC_API_URL=http://localhost:8010
```

## `voice-id/frontend/Dockerfile`

```dockerfile
# ---- 1. install dependencies ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- 2. build ----
FROM node:22-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8010
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS=--max-old-space-size=1536
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- 3. run (only the standalone output, ~50 MB) ----
FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
```

## `voice-id/frontend/app/globals.css`

```css
:root {
  --bg: #f6f7fb;
  --card: #ffffff;
  --text: #1c2030;
  --muted: #667085;
  --border: #e3e6ee;
  --primary: #3b5bdb;
  --danger: #e03131;
  --ok: #2b8a3e;
  --warn: #e67700;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #11131a;
    --card: #1b1e28;
    --text: #e9ebf2;
    --muted: #9aa1b5;
    --border: #2c3040;
    --primary: #748ffc;
    --danger: #ff6b6b;
    --ok: #69db7c;
    --warn: #ffa94d;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }
header h1 { margin: 0; font-size: 28px; }
header p { margin: 4px 0 24px; color: var(--muted); }
h2 { margin: 0 0 4px; font-size: 18px; }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 16px; }

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hint { color: var(--muted); font-size: 13px; margin: 0; }
.error { color: var(--danger); margin: 0; }
.success { color: var(--ok); margin: 0; }

.field { display: flex; flex-direction: column; gap: 4px; font-weight: 500; }
.field input {
  font: inherit;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
}

.consent { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; }
.consent input { margin-top: 3px; }

.clip-input { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

.btn {
  font: inherit;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  padding: 8px 14px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn:disabled, .btn.disabled { opacity: 0.5; cursor: not-allowed; }
.btn.primary { background: var(--primary); border-color: var(--primary); color: #fff; align-self: flex-start; }
.btn.danger { border-color: var(--danger); color: var(--danger); }
.btn.small { padding: 4px 10px; font-size: 13px; }
.btn.ghost { background: transparent; }
.link { background: none; border: none; color: var(--danger); cursor: pointer; font-size: 13px; }

.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--danger); animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: 0.3; } }

.clips { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.clips li { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.clips audio, .preview { height: 36px; max-width: 100%; }
.filename { font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }

.result { border-radius: 10px; padding: 14px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
.result.match { border-color: var(--ok); }
.result.unknown { border-color: var(--warn); }
.result .label { font-size: 22px; font-weight: 700; }
.result.match .label { color: var(--ok); }
.result.unknown .label { color: var(--warn); }

.scorebar { position: relative; height: 24px; background: var(--bg); border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }
.scorebar .fill { height: 100%; background: var(--primary); opacity: 0.35; }
.scorebar .threshold { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--text); }
.scorebar .value { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 12px; }

table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--border); }

.speakers { list-style: none; padding: 0; margin: 0; }
.speakers li { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--border); }
.speakers li:last-child { border-bottom: none; }

footer { margin-top: 24px; font-size: 13px; color: var(--muted); }
```

## `voice-id/frontend/app/layout.tsx`

```tsx
import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Voice ID",
  description: "Speaker recognition with ECAPA-TDNN, FastAPI and pgvector",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

## `voice-id/frontend/app/page.tsx`

```tsx
import { EnrollForm } from "@/components/EnrollForm";
import { IdentifyPanel } from "@/components/IdentifyPanel";
import { SpeakerList } from "@/components/SpeakerList";

export default function Home() {
  return (
    <main>
      <header>
        <h1>Voice ID</h1>
        <p>Enroll people by voice, then find out who is speaking.</p>
      </header>

      <div className="grid">
        <EnrollForm />
        <IdentifyPanel />
      </div>
      <SpeakerList />

      <footer>
        <strong>Privacy:</strong> a voiceprint is biometric data. Only enroll people who have agreed. Raw
        recordings are not stored, only the voiceprint numbers, and deleting a speaker removes them for good.
      </footer>
    </main>
  );
}
```

## `voice-id/frontend/components/ClipInput.tsx`

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

import type { Clip } from "@/lib/api";

// Browsers support different recording formats; pick the first one available.
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
}

function extensionFor(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("mp4")) return "m4a";
  return "audio";
}

let counter = 0;
export function makeClip(blob: Blob, filename: string): Clip {
  return { id: `clip-${Date.now()}-${counter++}`, blob, filename, url: URL.createObjectURL(blob) };
}

type Props = {
  onClip: (clip: Clip) => void;
  multiple?: boolean;
  disabled?: boolean;
};

/** Record from the microphone or pick audio files. Calls onClip for each clip. */
export function ClipInput({ onClip, multiple = false, disabled = false }: Props) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stop the microphone if the component unmounts mid-recording.
  useEffect(() => () => stopTracks(), []);

  function stopTracks() {
    if (timerRef.current) clearInterval(timerRef.current);
    recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
  }

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
      recorder.onstop = () => {
        stopTracks();
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        onClip(makeClip(blob, `recording-${new Date().toISOString().slice(11, 19)}.${extensionFor(type)}`));
      };
      recorderRef.current = recorder;
      recorder.start();
      setSeconds(0);
      setRecording(true);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      setError(
        (e as Error).name === "NotAllowedError"
          ? "Microphone permission was denied."
          : `Cannot start recording: ${(e as Error).message}`,
      );
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    Array.from(e.target.files ?? []).forEach((f) => onClip(makeClip(f, f.name)));
    e.target.value = ""; // allow picking the same file again
  }

  return (
    <div className="clip-input">
      {recording ? (
        <button type="button" className="btn danger" onClick={stop}>
          <span className="dot" /> Stop ({seconds}s)
        </button>
      ) : (
        <button type="button" className="btn" onClick={start} disabled={disabled}>
          🎙 Record
        </button>
      )}
      <label className={`btn ghost ${disabled || recording ? "disabled" : ""}`}>
        Upload file{multiple ? "s" : ""}
        <input type="file" accept="audio/*,.wav,.mp3,.webm,.ogg,.m4a,.flac" multiple={multiple} onChange={onFiles} hidden disabled={disabled || recording} />
      </label>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
```

## `voice-id/frontend/components/EnrollForm.tsx`

```tsx
"use client";

import { useState } from "react";

import type { Clip } from "@/lib/api";
import { useSpeakerStore } from "@/store/useSpeakerStore";

import { ClipInput } from "./ClipInput";

export function EnrollForm() {
  const enroll = useSpeakerStore((s) => s.enroll);
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [clips, setClips] = useState<Clip[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const canSubmit = name.trim() !== "" && consent && clips.length > 0 && !busy;

  function removeClip(id: string) {
    setClips((cs) => cs.filter((c) => c.id !== id));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const speaker = await enroll(name.trim(), consent, clips);
      setMessage({ kind: "ok", text: `Enrolled ${speaker.name} with ${speaker.sample_count} sample(s).` });
      setName("");
      setClips([]);
      setConsent(false);
    } catch (err) {
      setMessage({ kind: "error", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>1. Enroll a speaker</h2>
      <p className="hint">Add 2–3 clips of 5–10 seconds of natural speech for best results.</p>

      <label className="field">
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ada" maxLength={100} />
      </label>

      <ClipInput multiple onClip={(c) => setClips((cs) => [...cs, c])} disabled={busy} />

      {clips.length > 0 && (
        <ul className="clips">
          {clips.map((c) => (
            <li key={c.id}>
              <audio src={c.url} controls />
              <span className="filename">{c.filename}</span>
              <button type="button" className="link" onClick={() => removeClip(c.id)}>
                remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        This person agrees to have their voiceprint stored for identification and knows they can ask for it
        to be deleted.
      </label>

      <button className="btn primary" disabled={!canSubmit}>
        {busy ? "Enrolling…" : "Enroll speaker"}
      </button>
      {message && <p className={message.kind === "ok" ? "success" : "error"}>{message.text}</p>}
    </form>
  );
}
```

## `voice-id/frontend/components/IdentifyPanel.tsx`

```tsx
"use client";

import { useState } from "react";

import { api, type Clip, type IdentifyResult } from "@/lib/api";

import { ClipInput } from "./ClipInput";

export function IdentifyPanel() {
  const [clip, setClip] = useState<Clip | null>(null);
  const [result, setResult] = useState<IdentifyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function identify(c: Clip) {
    setClip(c);
    setResult(null);
    setError(null);
    setBusy(true);
    try {
      setResult(await api.identify(c));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>2. Who is speaking?</h2>
      <p className="hint">Record or upload a clip; it is identified automatically.</p>

      <ClipInput onClip={identify} disabled={busy} />
      {clip && <audio src={clip.url} controls className="preview" />}
      {busy && <p className="hint">Analysing voice…</p>}
      {error && <p className="error">{error}</p>}

      {result && (
        <div className={`result ${result.is_match ? "match" : "unknown"}`}>
          <div className="label">{result.is_match ? result.label : "Unknown speaker"}</div>
          <ScoreBar score={result.score} threshold={result.threshold} />
          <p className="hint">{result.reason}</p>
          {result.candidates.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Similarity</th>
                </tr>
              </thead>
              <tbody>
                {result.candidates.map((c) => (
                  <tr key={c.speaker_id}>
                    <td>{c.name}</td>
                    <td>{c.score.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}

function ScoreBar({ score, threshold }: { score: number; threshold: number }) {
  const pct = (v: number) => `${Math.max(0, Math.min(1, v)) * 100}%`;
  return (
    <div className="scorebar" title={`score ${score.toFixed(3)} / threshold ${threshold}`}>
      <div className="fill" style={{ width: pct(score) }} />
      <div className="threshold" style={{ left: pct(threshold) }} />
      <span className="value">
        confidence {score.toFixed(3)} · threshold {threshold.toFixed(2)}
      </span>
    </div>
  );
}
```

## `voice-id/frontend/components/SpeakerList.tsx`

```tsx
"use client";

import { useEffect } from "react";

import { useSpeakerStore } from "@/store/useSpeakerStore";

export function SpeakerList() {
  const { speakers, loading, error, fetchSpeakers, remove } = useSpeakerStore();

  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  async function onDelete(id: number, name: string) {
    if (!confirm(`Permanently delete ${name} and all of their voiceprints?`)) return;
    try {
      await remove(id);
    } catch (e) {
      alert((e as Error).message);
    }
  }

  return (
    <section className="card">
      <h2>Enrolled speakers</h2>
      {loading && <p className="hint">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && speakers.length === 0 && <p className="hint">Nobody enrolled yet.</p>}
      <ul className="speakers">
        {speakers.map((s) => (
          <li key={s.id}>
            <div>
              <strong>{s.name}</strong>
              <span className="hint">
                {" "}
                · {s.sample_count} sample{s.sample_count === 1 ? "" : "s"} · consent{" "}
                {new Date(s.consent_given_at).toLocaleDateString()}
              </span>
            </div>
            <button className="btn danger small" onClick={() => onDelete(s.id, s.name)}>
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

## `voice-id/frontend/lib/api.ts`

```typescript
// Typed wrapper around the FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export type Speaker = {
  id: number;
  name: string;
  sample_count: number;
  consent_given_at: string;
  created_at: string;
};

export type Candidate = { speaker_id: number; name: string; score: number };

export type IdentifyResult = {
  label: string; // speaker name or "unknown"
  is_match: boolean;
  speaker_id: number | null;
  score: number;
  threshold: number;
  reason: string;
  speech_seconds: number;
  candidates: Candidate[];
};

/** A recorded or uploaded clip waiting to be sent. */
export type Clip = { id: string; blob: Blob; filename: string; url: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(`Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join("; ")
          : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  listSpeakers: () => request<Speaker[]>("/speakers"),

  enroll(name: string, consent: boolean, clips: Clip[]) {
    const form = new FormData();
    form.append("name", name);
    form.append("consent", String(consent));
    clips.forEach((c) => form.append("files", c.blob, c.filename));
    return request<Speaker>("/speakers", { method: "POST", body: form });
  },

  deleteSpeaker: (id: number) => request<void>(`/speakers/${id}`, { method: "DELETE" }),

  identify(clip: Clip) {
    const form = new FormData();
    form.append("file", clip.blob, clip.filename);
    return request<IdentifyResult>("/identify", { method: "POST", body: form });
  },
};
```

## `voice-id/frontend/next.config.ts`

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a small self-contained server in .next/standalone for Docker.
  output: "standalone",
};

export default nextConfig;
```

## `voice-id/frontend/package.json`

```json
{
  "name": "voice-id-web",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3010",
    "build": "next build",
    "start": "next start -p 3010",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.5.28",
    "react": "19.2.9",
    "react-dom": "19.2.9",
    "zustand": "5.0.15"
  },
  "devDependencies": {
    "@types/node": "22.10.7",
    "@types/react": "19.2.2",
    "@types/react-dom": "19.2.2",
    "typescript": "5.7.3"
  }
}
```

## `voice-id/frontend/store/useSpeakerStore.ts`

```typescript
import { create } from "zustand";

import { api, type Clip, type Speaker } from "@/lib/api";

type SpeakerState = {
  speakers: Speaker[];
  loading: boolean;
  error: string | null;
  fetchSpeakers: () => Promise<void>;
  enroll: (name: string, consent: boolean, clips: Clip[]) => Promise<Speaker>;
  remove: (id: number) => Promise<void>;
};

// Global store for the enrolled-speaker list, shared by the enroll form and the list.
export const useSpeakerStore = create<SpeakerState>((set) => ({
  speakers: [],
  loading: false,
  error: null,

  fetchSpeakers: async () => {
    set({ loading: true, error: null });
    try {
      set({ speakers: await api.listSpeakers() });
    } catch (e) {
      set({ error: (e as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  enroll: async (name, consent, clips) => {
    const speaker = await api.enroll(name, consent, clips);
    set((s) => ({ speakers: [speaker, ...s.speakers] }));
    return speaker;
  },

  remove: async (id) => {
    await api.deleteSpeaker(id);
    set((s) => ({ speakers: s.speakers.filter((sp) => sp.id !== id) }));
  },
}));
```

## `voice-id/frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```
