#!/bin/bash
set -e

echo "=== [0/4] Checking environment ==="
echo "[ENV] FLASK_ENV=${FLASK_ENV:-development}"
echo "[ENV] RENDER=${RENDER:-false}"
echo "[ENV] PORT=${PORT:-5000}"

if [ -n "$DATABASE_URL" ]; then
    DB_PROTO=$(echo "$DATABASE_URL" | cut -d: -f1)
    echo "[DB] DATABASE_URL detected (protocol: $DB_PROTO)"
    echo "[DB] DATABASE_URL length: ${#DATABASE_URL} chars"
else
    echo "[DB] FATAL: DATABASE_URL is NOT SET"
    echo "[DB]"
    echo "[DB] This is expected on the FIRST deploy to Render."
    echo "[DB] The fromDatabase auto-linking takes effect on redeploy."
    echo "[DB]"
    echo "[DB] To fix manually:"
    echo "[DB]   1. Render Dashboard -> Databases -> smartlog-db -> Connections"
    echo "[DB]   2. Copy 'Connection String' (starts with postgresql://...)"
    echo "[DB]   3. Render Dashboard -> smartlog-backend -> Environment"
    echo "[DB]   4. Add environment variable:"
    echo "[DB]        Key:   DATABASE_URL"
    echo "[DB]        Value: <pasted connection string>"
    echo "[DB]   5. Click 'Save Changes' -> 'Manual Deploy' -> 'Deploy latest commit'"
    echo "[DB]"
    echo "[DB] Expected format: postgresql://user:password@host:5432/dbname"
    exit 1
fi

echo "=== [1/4] Running database migrations ==="
flask db upgrade 2>&1 || echo "[WARN] flask db upgrade failed — will be retried inside app.py"

echo "=== [2/4] Gunicorn will create tables + seed on import ==="
echo "      (app.py handles db.create_all() and run_startup() at import time)"

echo "=== [3/4] Starting Gunicorn ==="
exec gunicorn app:app \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers ${GUNICORN_WORKERS:-4} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info}
