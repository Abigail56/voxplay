#!/bin/sh
# Builds dist/hf-voxplay/: the whole app (site + API + database) for one Hugging Face Space.
#   sh deploy/make-hf-fullstack.sh        (run from the VoxPlay folder)
set -e
cd "$(dirname "$0")/.."
rm -rf dist/hf-voxplay
mkdir -p dist/hf-voxplay/backend dist/hf-voxplay/frontend
# The backend code, without tests, caches and local scripts...
tar -C backend --exclude=tests --exclude=scripts --exclude='__pycache__' --exclude='.pytest_cache' \
    --exclude='.venv' --exclude=db-init --exclude=Dockerfile --exclude=pytest.ini -cf - . \
  | tar -C dist/hf-voxplay/backend -xf -
# ...the site's source (the Space builds it)...
tar -C frontend --exclude=node_modules --exclude=.next --exclude='*.tsbuildinfo' --exclude=Dockerfile -cf - . \
  | tar -C dist/hf-voxplay/frontend -xf -
# ...plus the Space's own Dockerfile, nginx config, start script and README.
cp deploy/huggingface-fullstack/Dockerfile deploy/huggingface-fullstack/nginx.conf \
   deploy/huggingface-fullstack/start.sh deploy/huggingface-fullstack/README.md dist/hf-voxplay/
echo "Ready: $(pwd)/dist/hf-voxplay ($(du -sh dist/hf-voxplay | cut -f1))"
