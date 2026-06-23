#!/bin/bash
set -e

echo "=== [0/4] Checking environment ==="
echo "[ENV] FLASK_ENV=${FLASK_ENV:-development}"
echo "[ENV] RENDER=${RENDER:-false}"
echo "[ENV] PORT=${PORT:-5000}"

if [ -n "$DATABASE_URL" ]; then
    DB_PROTO=$(echo "$DATABASE_URL" | cut -d: -f1)
    echo "[DB] DATABASE_URL detected (protocol: $DB_PROTO, length: ${#DATABASE_URL} chars)"
else
    echo "[DB] WARNING: DATABASE_URL is NOT SET."
    echo "[DB] App will start in degraded mode (health check returns 503)."
    echo "[DB]"
    echo "[DB] To fix:"
    echo "[DB]   1. Render Dashboard -> Databases -> smartlog-db -> Connections"
    echo "[DB]   2. Copy 'Connection String'"
    echo "[DB]   3. smartlog-backend -> Environment -> Add DATABASE_URL"
    echo "[DB]   4. Save Changes (auto-restarts)"
fi

echo "=== [1/4] Running database migrations (if DB available) ==="
flask db upgrade 2>&1 || echo "[WARN] flask db upgrade skipped — will retry inside app.py"

echo "=== [2/4] Starting Gunicorn ==="
echo "      (app.py handles db.create_all() and run_startup() at import time)"
exec gunicorn app:app \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers ${GUNICORN_WORKERS:-4} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info}
