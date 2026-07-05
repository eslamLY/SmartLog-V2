"""
core/routes.py — Blueprint registration, error handlers, health endpoints,
Jinja2 filters, rate limiter, init route, and CLI commands.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, UTC

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import generate_csrf
from models import db, AuditLog

log = logging.getLogger('app')


def register_blueprints(app: Flask):
    """Import and register all route blueprints (28 total)."""
    from routes.employee import employee_bp
    from routes.auth import auth_bp
    app.register_blueprint(employee_bp)
    app.register_blueprint(auth_bp)

    from routes.admin_attendance import admin_attendance_bp
    from routes.attendance_policies import attendance_policies_bp
    from routes.employees import admin_employees_bp
    from routes.employees_unified import employees_bp
    from routes.devices import admin_devices_bp
    from routes.admin_system import admin_system_bp
    from routes.admin_shifts import admin_shifts_bp
    from routes.admin_ops import admin_ops_bp
    from routes.api_hrms import hrms_api_bp
    from routes.api_documents import api_documents_bp
    from routes.departments import admin_departments_bp
    from routes.dashboard import admin_dashboard_bp
    from routes.reports import admin_reports_bp
    from routes.reports_attendance import reports_attendance_bp
    from routes.payroll import payroll_bp
    from routes.api_offline_sync import api_offline_sync_bp
    from routes.gps_tracking import gps_bp
    from models.api_gps_receiver import gps_api_bp
    from routes.backup_management import backup_bp
    from routes.roles_permissions import rbac_bp
    from routes.employee_management import employee_mgmt_bp
    from routes.ai_forecasting import ai_forecast_bp
    from routes.forecasting import forecast_bp
    from routes.scenarios import scenarios_bp
    from routes.company_auth import company_auth_bp
    from routes.company_dashboard import company_dashboard_bp
    from routes.device_api import device_api_bp
    from routes.company_employees import company_employees_bp
    from routes.company_devices import company_devices_bp
    from routes.admin_companies import admin_companies_bp

    for bp in [admin_attendance_bp, attendance_policies_bp, admin_employees_bp,
               employees_bp, admin_devices_bp, admin_system_bp, admin_shifts_bp,
               admin_ops_bp, hrms_api_bp, api_documents_bp, admin_departments_bp,
               admin_dashboard_bp, admin_reports_bp, reports_attendance_bp, payroll_bp,
               api_offline_sync_bp, gps_bp, gps_api_bp, backup_bp, rbac_bp,
               employee_mgmt_bp, ai_forecast_bp, forecast_bp, scenarios_bp,
               company_auth_bp, company_dashboard_bp, device_api_bp,
               company_employees_bp, company_devices_bp, admin_companies_bp]:
        app.register_blueprint(bp)


def register_health_endpoints(app: Flask, _DB_CONFIGURED, FLASK_ENV, ON_RENDER):
    """Health check and performance monitoring endpoints."""
    _start_time = time.time()

    @app.route('/api/health')
    def api_health_inline():
        db_ready = app.config.get('DB_READY', False)
        result = {
            'status': 'healthy', 'database': 'ready' if db_ready else 'connecting',
            'database_configured': _DB_CONFIGURED,
            'timestamp': datetime.now(UTC).isoformat(),
            'environment': FLASK_ENV, 'on_render': ON_RENDER,
        }
        if not _DB_CONFIGURED:
            result['database'] = 'not_configured'
            result['message'] = 'DATABASE_URL not set — app in degraded mode'
            return jsonify(result), 503
        if db_ready:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
                result['database'] = 'connected'
            except Exception as exc:
                result['database'] = 'retrying: ' + str(exc)
        result['uptime_seconds'] = int(time.time() - _start_time)
        return jsonify(result), 200

    @app.route('/api/health/static')
    def api_static_health():
        static_dir = app.static_folder or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
        checks = {
            'css_pwa': os.path.isfile(os.path.join(static_dir, 'css', 'pwa.css')),
            'js_app': os.path.isfile(os.path.join(static_dir, 'js', 'app.js')),
            'icon_192': os.path.isfile(os.path.join(static_dir, 'icons', 'icon-192.svg')),
            'icon_512': os.path.isfile(os.path.join(static_dir, 'icons', 'icon-512.svg')),
            'manifest': os.path.isfile(os.path.join(static_dir, 'manifest.json')),
            'sw': os.path.isfile(os.path.join(static_dir, 'sw.js')),
        }
        all_ok = all(checks.values())
        return jsonify({
            'status': 'ok' if all_ok else 'degraded',
            'static_folder': static_dir, 'checks': checks, 'all_ok': all_ok,
            'count_css': len([f for f in os.listdir(os.path.join(static_dir, 'css')) if f.endswith('.css')]) if os.path.isdir(os.path.join(static_dir, 'css')) else 0,
            'count_js': len([f for f in os.listdir(os.path.join(static_dir, 'js')) if f.endswith('.js')]) if os.path.isdir(os.path.join(static_dir, 'js')) else 0,
        })

    @app.route('/api/performance/top-slow')
    def api_performance_top_slow():
        from core.middleware import _request_times
        paths = []
        for path, times in _request_times.items():
            if times:
                avg_ms = sum(times) / len(times)
                max_ms = max(times)
                paths.append({'path': path, 'avg_ms': round(avg_ms, 1), 'max_ms': max_ms, 'count': len(times)})
        paths.sort(key=lambda x: x['avg_ms'], reverse=True)
        return jsonify(paths[:30])


def register_jinja(app: Flask, PRODUCTION):
    """Context processor and custom filters."""

    @app.context_processor
    def inject_static_vars():
        from utils.icon_helper import static_url, icon, icon_html, needed_cdn_libs
        return dict(
            static_url=static_url, icon=icon, icon_html=icon_html,
            needed_cdn_libs=needed_cdn_libs,
            static_version=int(time.time()),
            PRODUCTION=PRODUCTION,
            csrf_token=generate_csrf(),
        )

    @app.template_filter('todatetime')
    def todatetime_filter(val):
        from datetime import date
        if isinstance(val, (list, tuple)) and len(val) == 3:
            return date(val[0], val[1], val[2])
        return val

    # PWA offline page
    @app.route('/pwa/offline')
    def pwa_offline():
        return render_template('pwa/offline.html'), 200, {'Service-Worker-Allowed': '/'}


def register_limiter(app: Flask):
    """Set up Flask-Limiter with per-route overrides.

    Storage:
        In-memory (``memory://``) — acceptable for per-minute limits on a
        single container.  Per-route limits in the request handler layer
        (``utils/rate_limit.check_rate_limit``) also use in-memory but are
        the primary defence; Flask-Limiter is a secondary guard.

        To persist across workers/gunicorn restarts, add Redis to the
        Render stack and set ``RATELIMIT_STORAGE_URL=redis://...``.
    """
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False
    import logging
    log = logging.getLogger('app')
    if not app.config.get('TESTING') and app.config.get('PRODUCTION'):
        log.info('Flask-Limiter: using in-memory storage (add Redis for persistence)')
    limiter = Limiter(get_remote_address, app=app,
                      default_limits=["10000 per day", "2000 per hour"])
    from routes.auth import login as _login_view
    from routes.employee import clock_in_qr as _clock_in_qr_view
    limiter.limit("5 per minute", methods=["POST"])(_login_view)
    limiter.limit("5 per minute")(_clock_in_qr_view)


def register_error_handlers(app: Flask):
    """Custom error pages for 500 and 429."""

    @app.errorhandler(500)
    def internal_error_handler(e):
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log.error('500 Internal Server Error:\n%s', tb)
        try:
            db.session.rollback()
        except Exception:
            pass
        if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
            return jsonify({'ok': False, 'error': str(exc_value), 'traceback': tb}), 500
        return f"""<!doctype html><meta charset="utf-8"><title>500 Error</title>
<pre style="background:#1a1a2e;color:#e2e8f0;padding:20px;font-size:13px;direction:ltr;text-align:left;overflow:auto;height:100vh">{tb}</pre>""", 500

    @app.errorhandler(429)
    def rate_limit_handler(e):
        ip = request.remote_addr or 'unknown'
        try:
            db.session.add(AuditLog(user_name='rate_limiter', action='block',
                entity_type='request', changes=json.dumps({'ip': ip, 'path': request.path}),
                ip_address=ip))
            db.session.commit()
        except Exception:
            db.session.rollback()
        if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
            return jsonify({'ok': False, 'msg': 'Too many requests'}), 429
        return render_template('blocked.html'), 429


def register_init_route(app: Flask):
    """One-time production initialisation route."""

    @app.route('/admin/init-production', methods=['GET', 'POST'])
    def admin_init_production():
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('auth.login'))
        if request.method == 'GET':
            return render_template('admin/admin_init.html', employee_name=session.get('full_name', ''))
        from scripts.production_init import main as run_init
        import io, contextlib
        buf = io.StringIO()
        rc = 1
        try:
            db.session.rollback()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = run_init(db_session=db.session)
            db.session.commit()
        except Exception as e:
            buf.write(f'\nERROR: {e}\n')
            import traceback
            traceback.print_exc(file=buf)
            try:
                db.session.rollback()
            except Exception:
                pass
            rc = 1
        output = buf.getvalue()
        session.clear()
        return f"""<!DOCTYPE html><html dir=rtl lang=ar><head><meta charset=utf-8>
<title>{'تهيئة قاعدة البيانات' if rc == 0 else 'حدث خطأ'}</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel=stylesheet>
<style>body{{font-family:'Cairo',sans-serif;background:#080c18;color:#e2e8f0;padding:24px;max-width:800px;margin:auto;line-height:1.8}}
pre{{background:#0f172a;padding:16px;border-radius:10px;border:1px solid #1e2a45;overflow-x:auto;font-size:13px}}
.btn{{display:inline-block;padding:10px 24px;background:#6366f1;color:#fff;border-radius:10px;text-decoration:none;font-weight:700}}
.rc{{color:#22c55e;font-size:24px;font-weight:700}}</style></head><body>
<h1>{'تم بنجاح ✓' if rc == 0 else 'فشل ✗'}</h1>
<pre>{output}</pre>
<a href='/login' class=btn>تسجيل الدخول بحساب ADMIN</a></body></html>"""


def register_cli(app: Flask):
    """Custom Flask CLI commands."""

    @app.cli.command('init-production')
    def init_production_cli():
        import scripts.production_init as init
        sys.exit(init.main())
