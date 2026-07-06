"""
core/__init__.py — SmartLog application factory.
Usage:
    from core import create_app
    app = create_app()
"""
import os
import threading
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s %(message)s')
log = logging.getLogger('app')
log.info('=' * 60)
log.info('SmartLog starting up')
log.info('=' * 60)

from flask import Flask
from itsdangerous import URLSafeTimedSerializer

from models import db

from core._state import db_ready_event


def _init_db_background(app: Flask):
    """Initialize DB in a daemon thread so the container starts fast.

    Guards:
        - SystemExit from auto_create_tables does not kill the thread
          silently; the event is *not* set, so the request barrier will
          block until a new worker process retries.
        - threading.Event provides a memory fence so ``DB_READY`` is
          visible across threads on all platforms.
    """
    from core.database import test_db_connection, auto_create_tables, run_startup
    if not app.config.get('_DB_CONFIGURED'):
        log.warning('DATABASE_URL not configured — DB_READY set true trivially')
        app.config['DB_READY'] = True
        db_ready_event.set()
        return
    with app.app_context():
        try:
            if test_db_connection(app, db):
                auto_create_tables(app, db, '', app.config.get('PRODUCTION', False))
                run_startup(app, db)
                app.config['DB_READY'] = True
                db_ready_event.set()
                log.info('Background DB init: complete')
            else:
                log.error('Background DB init: could not connect after retries')
        except SystemExit:
            log.error('Background DB init: sys.exit() called — thread terminated')
        except Exception as exc:
            log.error('Background DB init: failed (%s)', exc)


def create_app():
    # ── 1. Environment ──────────────────────────────────────
    from core.env import detect_environment, resolve_database_url, resolve_secret_key
    FLASK_ENV, ON_RENDER, PRODUCTION = detect_environment()
    _DB_URL, _masked, _IS_SQLITE, _DB_CONFIGURED = resolve_database_url()

    # ── 2. Flask app instance ────────────────────────────────
    app = Flask(__name__)
    app.config['ENV'] = FLASK_ENV
    app.config['PRODUCTION'] = PRODUCTION
    app.config['ON_RENDER'] = ON_RENDER

    # ── 3. Database config ──────────────────────────────────
    from core.database import configure_sqlalchemy, build_fernet, init_db
    configure_sqlalchemy(app, _DB_URL, _IS_SQLITE, PRODUCTION)

    # ── 4. Secret key & session ─────────────────────────────
    app.secret_key = resolve_secret_key(PRODUCTION)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 14400
    if PRODUCTION:
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True

    # ── 5. Upload & static folders ──────────────────────────
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.static_folder = os.path.join(_BASE, 'static')
    app.static_url_path = '/static'
    app.template_folder = os.path.join(_BASE, 'templates')
    if PRODUCTION:
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400
        app.config['TEMPLATES_AUTO_RELOAD'] = False

    # ── 6. Encryption ────────────────────────────────────────
    fernet = build_fernet(app)

    # ── 7. DB init (SQLAlchemy + Migrate) ────────────────────
    migrate = init_db(app, db, fernet)  # noqa — kept in scope

    # ── 8. DB init (async background thread — container starts fast) ──
    app.config['DB_READY'] = False
    app.config['_DB_CONFIGURED'] = _DB_CONFIGURED

    # ── 9. Jinja2, PWA, context processor ────────────────────
    from core.routes import register_jinja
    register_jinja(app, PRODUCTION)

    # ── 10. Rate limiter ──────────────────────────────────────
    from core.routes import register_limiter
    register_limiter(app)

    # ── 11. Blueprints ────────────────────────────────────────
    from core.routes import register_blueprints
    register_blueprints(app)

    # ── 12. Middleware (before/after request) ─────────────────
    from core.middleware import register_middleware
    register_middleware(app, PRODUCTION)

    # ── 13. Error handlers ────────────────────────────────────
    from core.routes import register_error_handlers
    register_error_handlers(app)

    # ── 14. Health endpoints ──────────────────────────────────
    from core.routes import register_health_endpoints
    register_health_endpoints(app, _DB_CONFIGURED, FLASK_ENV, ON_RENDER)

    # ── 14b. Background DB init thread ─────────────────────────
    if _DB_CONFIGURED:
        log.info('Starting background DB init thread...')
        t = threading.Thread(target=_init_db_background, args=(app,),
                             daemon=True)
        t.start()

    # ── 15. Init route + CLI ─────────────────────────────────
    from core.routes import register_init_route, register_cli
    register_init_route(app)
    register_cli(app)

    # ── 16. QR serializer ─────────────────────────────────────
    app.qr_serializer = URLSafeTimedSerializer(app.secret_key)

    log.info('=' * 60)
    log.info('SmartLog startup complete — ready to serve')
    log.info('=' * 60)

    return app
