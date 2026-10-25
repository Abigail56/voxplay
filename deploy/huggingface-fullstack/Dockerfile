# All of VOXPLAY in one free Hugging Face Space (Docker SDK, CPU basic: 2 vCPU, 16 GB RAM):
# the site, the API, PostgreSQL + pgvector and Redis, behind nginx on the Space's one port.
#   /      -> Next.js site (127.0.0.1:3000)
#   /api/  -> FastAPI (127.0.0.1:8000), prefix stripped, WebSockets included
#
# Free Spaces can't reach an external PostgreSQL, so the database lives in the container and
# is wiped whenever the Space restarts or wakes from sleep. Sample voices are re-enrolled on start.

# ---- 1. build the site ----
# Debian (glibc), not Alpine, so the standalone server and its node binary run in the final image.
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same origin as the site, so no CORS and no address to know in advance.
ENV NEXT_PUBLIC_API_URL=/api \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- 2. the API, as in backend/Dockerfile ----
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf

WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt -r requirements-dev.txt

ENV MODEL_DIR=/models/spkrec-ecapa-voxceleb

# Bake the pretrained models into the image (no download at start-up).
RUN python -c "from speechbrain.inference.speaker import EncoderClassifier; \
EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir='/models/spkrec-ecapa-voxceleb')" \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8', download_root='/models/whisper')" \
    && chmod -R a+rwX /models

# A private PostgreSQL with pgvector, a private Redis, and nginx in front of everything.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql postgresql-17-pgvector redis-server nginx \
    && rm -rf /var/lib/apt/lists/*

COPY --from=web /usr/local/bin/node /usr/local/bin/node

# Hugging Face runs the container as user 1000.
RUN useradd --create-home --uid 1000 user

ENV PATH="/usr/lib/postgresql/17/bin:${PATH}" \
    # Override any of these under the Space's Settings -> Variables.
    RATE_LIMIT_PER_MINUTE=20 \
    TRUST_PROXY_HEADERS=true \
    SEED_SAMPLE_VOICES=true \
    REQUIRE_LIVENESS=true \
    TORCH_THREADS=2

COPY --chown=user backend/ /app/
COPY --chown=user --from=web /web/.next/standalone /web/
COPY --chown=user --from=web /web/.next/static /web/.next/static
COPY --chown=user --from=web /web/public /web/public
COPY --chown=user nginx.conf start.sh /app/
RUN chmod +x /app/start.sh

USER user
EXPOSE 7860
CMD ["/app/start.sh"]
