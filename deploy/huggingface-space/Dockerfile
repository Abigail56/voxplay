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

# Bake the pretrained models into the image (no download at start-up).
RUN python -c "from speechbrain.inference.speaker import EncoderClassifier; \
EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir='/models/spkrec-ecapa-voxceleb')" \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8', download_root='/models/whisper')" \
    && chmod -R a+rwX /models

# --- Space-specific from here on ---

# A private PostgreSQL with the pgvector extension, and a private Redis.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql postgresql-17-pgvector redis-server \
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
