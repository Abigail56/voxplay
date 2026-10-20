#!/bin/sh
# Start a private PostgreSQL and Redis inside the container, then the API.
set -e

PGDATA=/tmp/pgdata
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" -U voiceid --auth=trust >/dev/null
fi
pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -k /tmp" -l /tmp/postgres.log -w start
createdb -h 127.0.0.1 -U voiceid voiceid 2>/dev/null || true

redis-server --bind 127.0.0.1 --port 6379 --save "" --appendonly no --dir /tmp --pidfile /tmp/redis.pid --logfile /tmp/redis.log --daemonize yes

export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://voiceid@127.0.0.1:5432/voiceid}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips '*'
