"""
core/env.py — Environment detection, secrets, and safe logging.
"""
import os
import sys
import logging
from dotenv import load_dotenv

log = logging.getLogger('app')

# Load .env file if it exists
load_dotenv()


def detect_environment():
    """Detect FLASK_ENV, PRODUCTION, ON_RENDER and log safely."""
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development').lower()
    ON_RENDER = os.environ.get('RENDER', '').lower() == 'true'
    PRODUCTION = FLASK_ENV == 'production' or ON_RENDER \
                 or os.environ.get('PRODUCTION', '').lower() in ('1', 'true', 'yes')

    log.info('Environment:')
    for key in sorted(os.environ.keys()):
        val = os.environ[key]
        if any(s in key.upper() for s in ['KEY', 'SECRET', 'TOKEN', 'PASS', 'ENCRYPT']):
            val = '****'
        elif key == 'DATABASE_URL' and val:
            val = val.split('@')[0].split('://')[0] + '://****:****@' + val.split('@')[1] if '@' in val else '****'
        log.info('  %s=%s', key, val)
    log.info('Detected: FLASK_ENV=%s ON_RENDER=%s PRODUCTION=%s', FLASK_ENV, ON_RENDER, PRODUCTION)
    return FLASK_ENV, ON_RENDER, PRODUCTION


def resolve_database_url():
    """Validate, normalize, and return (url, masked_url, is_sqlite, is_configured)."""
    raw = os.environ.get('DATABASE_URL', '').strip()
    configured = True

    if not raw:
        log.error('WARNING: DATABASE_URL is NOT SET. App will start in DEGRADED mode.')
        if os.environ.get('RENDER', '').lower() == 'true':
            log.error('  To fix on Render: Dashboard -> Databases -> smartlog-db -> Connections -> Copy string')
        log.error('  Set: export DATABASE_URL=postgresql://user:pass@host:5432/db')
        raw = 'postgresql://placeholder:placeholder@localhost:5432/nonexistent'
        configured = False

    log.info('DATABASE_URL found: %d characters', len(raw))

    if raw.startswith('postgres://'):
        raw = raw.replace('postgres://', 'postgresql://', 1)
        log.info('Converted postgres:// -> postgresql://')

    is_sqlite = raw.startswith('sqlite:///')
    if is_sqlite:
        _rel = raw[len('sqlite:///'):]
        _abs = os.path.abspath(_rel)
        raw = f'sqlite:///{_abs}'
        log.info('Using SQLite at %s', _abs)
    elif not raw.startswith('postgresql://') or '@' not in raw:
        log.error('FATAL: DATABASE_URL must start with postgresql:// or sqlite:///')
        sys.exit(1)

    masked = raw
    if '@' in raw:
        masked = raw.split('@')[0].split('://')[0] + '://****:****@' + raw.split('@')[1]
    log.info('DATABASE_URL (masked): %s', masked)

    return raw, masked, is_sqlite, configured


def resolve_secret_key(PRODUCTION):
    """Return the secret key, exiting if missing in production."""
    key = os.environ.get('SECRET_KEY')
    if PRODUCTION and not key:
        log.error('FATAL: SECRET_KEY environment variable is missing!')
        sys.exit(1)
    return key or 'dev-secret-change-in-prod'
