"""
core/middleware.py — All before_request / after_request handlers.
"""
import time
import logging
import gzip
from collections import defaultdict
from datetime import datetime, UTC

from flask import request, jsonify, render_template, session, redirect
from flask_wtf.csrf import validate_csrf, ValidationError

from core._state import db_ready_event

log = logging.getLogger('app')

_request_times = defaultdict(list)
_SLOW_API_THRESHOLD_MS = 1000


def register_middleware(app, PRODUCTION):
    """Register all before/after request handlers."""

    # ── before_request ──────────────────────────────────────────────────
    # ⚠  ORDER MATTERS — db barrier must run first to prevent race with
    #    background thread (see core/__init__.py _init_db_background).

    @app.before_request
    def _wait_for_db():
        """Block non-health requests until the background thread finishes
        DB init.  Health checks and static assets pass through immediately
        so Render does not kill the container."""
        if request.path.startswith(('/api/health', '/static/', '/favicon.ico',
                                    '/manifest.json', '/sw.js')):
            return
        if app.config.get('_DB_CONFIGURED') and not app.config.get('DB_READY'):
            log.info('Request waiting for DB: %s', request.path)
            if not db_ready_event.wait(timeout=120):
                log.error('Request timed out waiting for DB: %s', request.path)
                return jsonify({'ok': False, 'msg': 'Database not ready yet'}), 503

    @app.before_request
    def request_start_time():
        request._start_time = time.time()

    @app.before_request
    def check_auto_ban():
        if not app.config.get('DB_READY', False):
            return
        if request.path.startswith(('/static/', '/manifest.json', '/sw.js',
                                    '/uploads/', '/logout', '/api/health', '/admin/backup')):
            return
        from utils.rate_limit import check_ip_flood
        ip = request.remote_addr or 'unknown'
        result = check_ip_flood(ip, max_requests=266, window_seconds=60)
        if not result['ok']:
            return render_template('blocked.html'), 429

    @app.before_request
    def set_company_middleware():
        from services.company_service import set_company_context
        set_company_context()

    @app.before_request
    def check_csrf():
        if app.config.get('TESTING'):
            return
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return
        if request.path.startswith(('/static/', '/manifest.json', '/sw.js',
                                    '/uploads/', '/api/health', '/login',
                                    '/company/', '/api/device/',
                                    '/api/v1/auth/login', '/api/v1/auth/refresh',
                                    '/api/v1/auth/logout')):
            return
        if request.is_json:
            token = request.headers.get('X-CSRFToken')
            if not token:
                return jsonify({'ok': False, 'msg': 'طلب غير مصرح به (CSRF). أعد تحميل الصفحة.'}), 403
            try:
                validate_csrf(token)
            except ValidationError:
                return jsonify({'ok': False, 'msg': 'طلب غير مصرح به (CSRF). أعد تحميل الصفحة.'}), 403

    # ── after_request ───────────────────────────────────────────────────

    @app.after_request
    def production_security_headers(response):
        if PRODUCTION:
            host = request.host.split(':')[0].lower()
            if host in ('localhost', '127.0.0.1', '::1'):
                return response
            if request.scheme == 'http':
                secure_url = request.url.replace('http://', 'https://', 1)
                return redirect(secure_url, code=301)
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            from config import ProductionConfig
            config_cls = ProductionConfig
        else:
            from config import DevelopmentConfig
            config_cls = DevelopmentConfig
        csp = getattr(app, '_csp_string', None)
        if not csp:
            csp = config_cls.csp_string() if hasattr(config_cls, 'csp_string') else config_cls.CSP_HEADER
            app._csp_string = csp
        response.headers['Content-Security-Policy'] = csp
        return response

    @app.after_request
    def performance_monitoring(response):
        if request.path.startswith('/api/'):
            elapsed = time.time() - request._start_time if hasattr(request, '_start_time') else 0
            elapsed_ms = int(elapsed * 1000)
            path = request.path
            _request_times[path].append(elapsed_ms)
            if len(_request_times[path]) > 100:
                _request_times[path] = _request_times[path][-50:]
            if elapsed_ms > _SLOW_API_THRESHOLD_MS:
                log.warning('SLOW API [%dms] %s from %s', elapsed_ms, path, request.remote_addr)
            response.headers['X-Response-Time-Ms'] = str(elapsed_ms)
        return response

    @app.after_request
    def compress_response(response):
        if not app.config.get('TESTING') and (response.content_type == 'application/json'
                and response.status_code == 200
                and len(response.data) > 1024):
            response.set_data(gzip.compress(response.data))
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
        return response

    return _request_times, _SLOW_API_THRESHOLD_MS
