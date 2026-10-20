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
