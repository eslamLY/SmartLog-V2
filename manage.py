"""Flask CLI commands for database management and diagnostics.
Usage:
    flask db upgrade          # Apply pending migrations
    flask db migrate          # Auto-detect model changes (generate migration)
    flask db-health           # Check connection + verify all tables
    flask db-verify           # Test SQL query execution on each table
    flask db-repair           # Create missing tables without migration
"""

import sys, logging
from datetime import datetime, UTC
from flask import current_app
from flask.cli import with_appcontext

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('manage')


def init_app(app):
    from flask_migrate import Migrate
    from models import db
    migrate = Migrate(app, db)

    @app.cli.command('db-health')
    @with_appcontext
    def db_health():
        """Verify database connection and check all required tables exist."""
        from sqlalchemy import inspect
        from models import db

        log.info('=== Database Health Check ===')
        url = db.engine.url.render_as_string()
        masked = url.split('@')[0].split('://')[0] + '://****:****@' + url.split('@')[1] if '@' in url else url
        log.info('Database URL: %s', masked)

        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('SELECT 1'))
            log.info('Connection: OK')
        except Exception as e:
            log.error('Connection FAILED: %s', e)
            sys.exit(1)

        inspector = inspect(db.engine)
        all_tables = inspector.get_table_names()
        log.info('Tables found (%d): %s', len(all_tables),
                 ', '.join(sorted(all_tables)))

        required = ['login_attempts', 'employees', 'departments',
                    'attendance_logs', 'attendance_policies', 'biotime_devices']
        missing = [t for t in required if t not in all_tables]
        if missing:
            log.error('MISSING TABLES (%d): %s', len(missing), ', '.join(missing))
            sys.exit(1)
        log.info('All required tables present: OK')

        for table in required:
            if table in all_tables:
                cols = [c['name'] for c in inspector.get_columns(table)]
                log.info('  %-25s (%d cols): %s',
                         table, len(cols), ', '.join(cols))

        log.info('=== Health Check PASSED ===')

    @app.cli.command('db-verify')
    @with_appcontext
    def db_verify():
        """Run SELECT 1 on every table to verify read access."""
        from sqlalchemy import inspect, text
        from models import db

        log.info('=== Table Verification ===')
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if not tables:
            log.error('No tables found in database!')
            sys.exit(1)

        failures = []
        for table in tables:
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(f'SELECT 1 FROM "{table}" LIMIT 1'))
                log.info('  OK: %s', table)
            except Exception as e:
                log.error('  FAIL: %s — %s', table, e)
                failures.append(table)

        if failures:
            log.error('%d table(s) FAILED verification', len(failures))
            sys.exit(1)
        log.info('=== All %d tables verified OK ===', len(tables))

    @app.cli.command('db-repair')
    @with_appcontext
    def db_repair():
        """Create any missing tables without running full migration."""
        from sqlalchemy import inspect
        from models import db

        log.info('=== Database Repair ===')
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        log.info('Existing tables: %d', len(existing))

        db.create_all()
        after = set(inspect(db.engine).get_table_names())
        created = after - existing
        if created:
            log.info('Created %d missing table(s): %s',
                     len(created), ', '.join(sorted(created)))
        else:
            log.info('No missing tables — all present')

        log.info('=== Repair Complete ===')


def _mask_url(url: str) -> str:
    if '@' in url:
        return url.split('@')[0].split('://')[0] + '://****:****@' + url.split('@')[1]
    return url
