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
