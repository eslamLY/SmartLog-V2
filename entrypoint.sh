#!/bin/bash
set -e

echo "=== [0/4] Checking environment ==="
if [ -n "$DATABASE_URL" ]; then
    DB_PROTO=$(echo "$DATABASE_URL" | cut -d: -f1)
    echo "[DB] DATABASE_URL detected (protocol: $DB_PROTO)"
else
    echo "[DB] FATAL: DATABASE_URL is NOT SET"
    echo "[DB] Go to Render Dashboard → Environment → Add DATABASE_URL"
    echo "[DB] Value should be: postgresql://user:pass@host:5432/dbname"
    exit 1
fi

echo "=== [1/4] Running database migrations ==="
flask db upgrade || echo "[WARN] flask db upgrade failed — will be retried inside app.py"

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
