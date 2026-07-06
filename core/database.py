"""
core/database.py — SQLAlchemy init, connection pool, pre-flight test, Alembic stamp.
"""
import os
import sys
import time
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from cryptography.fernet import Fernet
import base64
import hashlib

log = logging.getLogger('app')


def configure_sqlalchemy(app: Flask, db_url: str, is_sqlite: bool, PRODUCTION: bool):
    """Set SQLALCHEMY_DATABASE_URI and engine options on the app."""
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    pool_size = int(os.environ.get('DB_POOL_SIZE', '10'))
    pool_overflow = int(os.environ.get('DB_POOL_OVERFLOW', '20'))
    pool_timeout = int(os.environ.get('DB_POOL_TIMEOUT', '30'))
    pool_recycle = int(os.environ.get('DB_POOL_RECYCLE', '3600'))

    if is_sqlite:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': pool_size,
            'max_overflow': pool_overflow,
            'pool_timeout': pool_timeout,
            'pool_recycle': pool_recycle,
            'pool_pre_ping': True,
            'connect_args': {'sslmode': 'require'} if PRODUCTION else {},
        }
    log.info('Engine options: pool_size=%d, max_overflow=%d, ssl=%s',
             pool_size, pool_overflow, 'require' if PRODUCTION else 'no')


def build_fernet(app: Flask):
    """Build Fernet encryption instance from FIELD_ENCRYPTION_KEY or derive from SECRET_KEY."""
    key_raw = os.environ.get('FIELD_ENCRYPTION_KEY')
    if key_raw:
        _key = key_raw.encode() if isinstance(key_raw, str) else key_raw
        log.info('FIELD_ENCRYPTION_KEY: custom key configured')
    else:
        _key = base64.urlsafe_b64encode(hashlib.sha256(app.secret_key.encode()).digest())
        log.warning('FIELD_ENCRYPTION_KEY not set — derived from SECRET_KEY.')
    return Fernet(_key)


def init_db(app: Flask, db: SQLAlchemy, fernet):
    """Wire Flask-SQLAlchemy, Migrate, and Fernet into the models."""
    from models import set_fernet as _set_fernet
    _set_fernet(fernet)
    db.init_app(app)
    return Migrate(app, db)


def test_db_connection(app: Flask, db: SQLAlchemy, max_retries=10, delay=5):
    """Retryable DB connection test. Returns True on success."""
    for attempt in range(1, max_retries + 1):
        try:
            with app.app_context():
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
            log.info('DB connection test PASSED (attempt %d/%d)', attempt, max_retries)
            return True
        except Exception as exc:
            log.warning('DB connection test FAILED (attempt %d/%d): %s', attempt, max_retries, exc)
            if attempt < max_retries:
                log.info('Retrying in %d seconds...', delay)
                time.sleep(delay)
    return False


def auto_create_tables(app: Flask, db: SQLAlchemy, masked_url: str, PRODUCTION: bool):
    """Create tables if missing and stamp Alembic to head."""
    with app.app_context():
        try:
            db.create_all()
            log.info('Tables: ALL verified (db.create_all() completed)')
            from flask_migrate import stamp
            stamp(revision='head')
            log.info('Alembic: stamped to head')
        except Exception as exc:
            log.warning('Alembic stamp skipped: %s', exc)
            if PRODUCTION:
                log.error('FATAL: db.create_all() failed: %s', exc)
                sys.exit(1)


def run_startup(app: Flask, db: SQLAlchemy):
    """Run migrations and seed data on startup."""
    with app.app_context():
        log.info('Startup: schema handled by db.create_all() — skipping flask db upgrade')

        for col, typ in [('early_leave_minutes', 'INTEGER DEFAULT 0'),
                         ('overtime_minutes', 'INTEGER DEFAULT 0'),
                         ('policy_id', 'INTEGER REFERENCES attendance_policies(id)')]:
            try:
                db.session.execute(db.text(f'ALTER TABLE attendance_logs ADD COLUMN {col} {typ}'))
                db.session.commit()
                log.info('Startup: added column attendance_logs.%s', col)
            except Exception:
                db.session.rollback()

        for col, typ in [('opening_balance', 'FLOAT DEFAULT 0'),
                         ('pending_days', 'FLOAT DEFAULT 0')]:
            try:
                db.session.execute(db.text(f'ALTER TABLE employee_leave_balances ADD COLUMN {col} {typ}'))
                db.session.commit()
                log.info('Startup: added column employee_leave_balances.%s', col)
            except Exception:
                db.session.rollback()

        try:
            from utils.seeds import seed_enterprise, seed_db, seed_shift_types, seed_leave_types
            seed_enterprise()
            seed_db()
            seed_shift_types()
            seed_leave_types()
            log.info('Startup: seed data loaded')
        except Exception as exc:
            log.warning('Startup: seeding skipped (%s)', exc)
