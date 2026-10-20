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
