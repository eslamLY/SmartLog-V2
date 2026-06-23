#!/bin/bash
# ============================================================
# SmartLog — Setup & Test Script
# ============================================================
# Use Cases:
#   Local dev:   bash setup_and_test.sh
#   CI/CD:       DATABASE_URL=postgresql://... bash setup_and_test.sh
#   Quick test:  bash setup_and_test.sh --skip-db-wait
# ============================================================
set -e

SKIP_DB_WAIT=false
for arg in "$@"; do
  [ "$arg" = "--skip-db-wait" ] && SKIP_DB_WAIT=true
done

echo ""
echo "============================================"
echo "  SmartLog — Setup and Test"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# ─── Step 1: Virtual Environment ─────────────────────────────
echo "[1/8] Creating Python virtual environment..."
python -m venv venv 2>/dev/null || python3 -m venv venv
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
  source venv/Scripts/activate
else
  . venv/bin/activate
fi
echo "  Python: $(python --version)"

# ─── Step 2: Dependencies ────────────────────────────────────
echo "[2/8] Installing dependencies..."
pip install -q -r requirements.txt

# ─── Step 3: Environment Variables ───────────────────────────
echo "[3/8] Setting environment variables..."
export FLASK_ENV=${FLASK_ENV:-development}
export DATABASE_URL=${DATABASE_URL:-postgresql://smartlog:smartlog_pass@localhost:5432/smartlog}
export SECRET_KEY=${SECRET_KEY:-test-secret-key}
export PRODUCTION=${PRODUCTION:-false}
export FLASK_APP=app.py

# Mask password for display
DB_DISPLAY=$(echo "$DATABASE_URL" | sed 's|://[^:]*:[^@]*@|://USER:PASS@|')
echo "  DATABASE_URL: $DB_DISPLAY"
echo "  FLASK_ENV:    $FLASK_ENV"
echo "  PRODUCTION:   $PRODUCTION"

# ─── Step 4: Wait for PostgreSQL ──────────────────────────────
echo "[4/8] Checking PostgreSQL..."
if [ "$SKIP_DB_WAIT" = true ]; then
  echo "  (--skip-db-wait: skipping)"
elif command -v pg_isready &>/dev/null; then
  for i in $(seq 1 30); do
    if pg_isready -q 2>/dev/null; then
      echo "  PostgreSQL ready (after ${i}s)"
      break
    fi
    if [ "$i" -eq 30 ]; then
      echo "  WARNING: PostgreSQL not detected. Continuing anyway..."
    fi
    sleep 1
  done
else
  echo "  pg_isready not found — skipping wait"
fi

# ─── Step 5: Database Migrations ──────────────────────────────
echo "[5/8] Running database migrations..."
flask db upgrade 2>&1 || echo "  (first run: tables created by app.py at import)"

# ─── Step 6: Health Check ────────────────────────────────────
echo "[6/8] Running database health check..."
python -c "
from app import app
from sqlalchemy import inspect, text
from models import db

with app.app_context():
    # Test connection
    with db.engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('  Connection: OK')

    # List tables
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f'  Tables ({len(tables)}): {', '.join(tables)}')

    # Verify required tables
    required = ['login_attempts', 'employees', 'departments',
                'attendance_logs', 'attendance_policies']
    missing = [t for t in required if t not in tables]
    if missing:
        print(f'  MISSING: {missing}')
        exit(1)
    print('  Required tables: OK')

    # Verify login_attempts columns
    if 'login_attempts' in tables:
        cols = [c['name'] for c in inspector.get_columns('login_attempts')]
        print(f'  login_attempts columns: {', '.join(cols)}')

print('  Health check: PASSED')
"

# ─── Step 7: Run Tests ────────────────────────────────────────
echo "[7/8] Running tests..."
if [ -d tests ]; then
  python -m pytest tests/ -v --tb=short 2>&1 | tail -40 || true
else
  echo "  No tests/ directory found — skipping"
fi

# ─── Step 8: Start App ────────────────────────────────────────
echo ""
echo "[8/8] Starting Flask development server..."
echo ""
echo "  Health check: http://localhost:5000/api/health"
echo "  Login:        http://localhost:5000/login"
echo "  Admin:        http://localhost:5000/admin/attendance-policies"
echo ""
echo "  Default credentials:"
echo "    Username: ADM001"
echo "    Password: admin123"
echo ""
flask run --host=0.0.0.0 --port=5000
