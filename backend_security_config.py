#!/usr/bin/env python3
"""
SmartLog V2 — Corrected Backend Security Configuration
This file provides the IDEAL security configuration for the Flask app.
It is NOT loaded by the app directly; instead, use it as a reference
to update app.py, config.py, and other files.

Usage:
  python backend_security_config.py   (prints diff-like instructions)
"""

import os, sys

SEPARATOR = '-' * 60


def print_instructions():
    print(SEPARATOR)
    print('  SmartLog V2 — Recommended Backend Security Configuration')
    print('  Use these settings to harden the application.')
    print(SEPARATOR)
    print()

    # ─── 1. config.py ────────────────────────────────────────
    print('## 1. config.py — Replace BaseConfig')
    print()
    print('''
class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError('SECRET_KEY environment variable is required.')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    PRODUCTION = False
    ''')
    print('Key changes:')
    print('  - Remove default SECRET_KEY (was dev-secret-change-in-prod)')
    print('  - Raise RuntimeError instead of silently using default')
    print('  - Add PERMANENT_SESSION_LIFETIME (was set only in app.py)')
    print('  - Set SESSION_COOKIE_SECURE = True by default')
    print()

    # ─── 2. app.py — Session & Security Headers ──────────────
    print(SEPARATOR)
    print('## 2. app.py — Production Security Headers (near line 393)')
    print()
    print('''
@app.after_request
def production_security_headers(response):
    if not PRODUCTION:
        return response
    host = request.host.split(':')[0].lower()
    if host in ('localhost', '127.0.0.1', '::1'):
        return response
    if request.scheme == 'http':
        secure_url = request.url.replace('http://', 'https://', 1)
        return redirect(secure_url, code=301)

    # HSTS — 1 year
    response.headers['Strict-Transport-Security'] = \\
        'max-age=31536000; includeSubDomains; preload'

    # Prevent MIME sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'

    # Content Security Policy
    csp = getattr(app, '_csp_string', None)
    if not csp:
        from config import ProductionConfig
        csp = ProductionConfig.csp_string()
        app._csp_string = csp
    response.headers['Content-Security-Policy'] = csp

    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions policy (restrict browser features)
    response.headers['Permissions-Policy'] = \\
        'camera=(), microphone=(), geolocation=(self), payment=()'

    # Prevent caching of sensitive pages
    if request.path.startswith('/admin'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'

    return response
''')
    print('Additions:')
    print('  - Referrer-Policy: strict-origin-when-cross-origin')
    print('  - Permissions-Policy: restricts camera/mic/geolocation')
    print('  - Cache-Control: no-store for /admin pages')
    print()

    # ─── 3. app.py — CSRF (near line 383) ───────────────────
    print(SEPARATOR)
    print('## 3. app.py — CSRF Validation (before_request)')
    print()
    print('''
@app.before_request
def check_csrf():
    # Only validate state-changing methods
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return
    # Skip static, auth, and health endpoints
    skip = ('/static/', '/manifest.json', '/sw.js', '/uploads/',
            '/api/health', '/login', '/api/auth/token',
            '/force-password-change')
    if request.path.startswith(skip):
        return
    # Fetch requests (offline token sync) use Bearer token auth
    if request.headers.get('Authorization', '').startswith('Bearer '):
        return
    # Validate CSRF token for session-authenticated JSON requests
    if request.is_json:
        token = request.headers.get('X-CSRFToken')
        if not token or token != session.get('csrf_token'):
            log.warning('CSRF validation failed: %s %s',
                        request.method, request.path)
            return jsonify({'ok': False,
                            'msg': 'طلب غير مصرح به. أعد تحميل الصفحة.'}), 403
''')
    print('Notes:')
    print('  - Skips validation for Bearer token auth (offline sync)')
    print('  - Logs CSRF failures (important for audit)')
    print()

    # ─── 4. Error Handlers ──────────────────────────────────
    print(SEPARATOR)
    print('## 4. app.py — Add 500 Error Handler (near line 365)')
    print()
    print('''
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    log.error('Internal server error: %s %s', request.method, request.path)
    log.exception(e)
    if PRODUCTION:
        return render_template('errors/500.html'), 500
    raise  # Re-raise in development so debugger shows stack

@app.errorhandler(403)
def forbidden(e):
    return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية للوصول إلى هذه الصفحة.'}), 403
''')
    print('Create templates:')
    print('  - templates/errors/404.html — Page not found')
    print('  - templates/errors/500.html — Generic error page (no traceback)')
    print()

    # ─── 5. app.py — Remove traceback leak ──────────────────
    print(SEPARATOR)
    print('## 5. routes/auth.py — Fix init-db endpoint (line 149)')
    print()
    print('Replace:')
    print('''
    return jsonify({'ok': False, 'msg': str(exc), 'traceback': traceback.format_exc()})
''')
    print('With:')
    print('''
    log.error('Init-db failed: %s', exc)
    log.exception(exc)
    return jsonify({'ok': False, 'msg': 'فشلت عملية تهيئة قاعدة البيانات. راجع سجل الأخطاء.'})
''')
    print()

    # ─── 6. Rate Limiting for API Token ─────────────────────
    print(SEPARATOR)
    print('## 6. routes/api_offline_sync.py — Add rate limiting')
    print()
    print('Add to issue_token():')
    print('''
@api_offline_sync_bp.route('/api/auth/token', methods=['POST'])
def issue_token():
    allowed, remaining = check_rate_limit('api_token', 10, 300)  # 10 per 5 min
    if not allowed:
        return jsonify({'ok': False, 'msg': 'طلبات كثيرة. حاول لاحقاً.'}), 429
    ...
''')
    print()

    # ─── 7. Persist API Tokens ──────────────────────────────
    print(SEPARATOR)
    print('## 7. routes/api_offline_sync.py — Persist tokens in DB')
    print()
    print('Create a model:')
    print('''
class ApiToken(db.Model):
    __tablename__ = 'api_tokens'
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False)
''')
    print('Store SHA-256 hash of token (never store raw token).')
    print()

    # ─── 8. CSP — Remove unsafe-inline if possible ──────────
    print(SEPARATOR)
    print('## 8. config.py — CSP improvements')
    print()
    print('Current CSP uses `\'unsafe-inline\'` for scripts and styles.')
    print('To remove it, move all inline JS to app.js and inline CSS to style.css.')
    print('For now, add a nonce-based approach:')
    print()
    print('''
@app.context_processor
def inject_csp_nonce():
    import uuid
    nonce = uuid.uuid4().hex
    g.csp_nonce = nonce
    return {'csp_nonce': nonce}

# Then use {{ csp_nonce }} in templates:
# <script nonce="{{ csp_nonce }}">...</script>
# And in CSP: script-src 'self' 'nonce-{nonce}' https://cdn...
''')
    print()

    # ─── 9. Environment Validation ──────────────────────────
    print(SEPARATOR)
    print('## 9. App Startup — Validate all required env vars')
    print()
    print('Add to app.py after line 50:')
    print('''
REQUIRED_ENV_VARS = ['SECRET_KEY', 'DATABASE_URL']
if PRODUCTION:
    REQUIRED_ENV_VARS.extend(['FIELD_ENCRYPTION_KEY', 'BACKUP_ENCRYPTION_KEY'])
missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
if missing:
    log.error('FATAL: Missing required env vars: %s', missing)
    if PRODUCTION:
        sys.exit(1)
''')
    print()

    # ─── 10. Input Validation Middleware ─────────────────────
    print(SEPARATOR)
    print('## 10. app.py — Global input validation (before_request)')
    print()
    print('''
# Optional: Reject requests with excessively large JSON bodies
@app.before_request
def limit_request_size():
    if request.is_json:
        cl = request.content_length or 0
        if cl > 1024 * 1024:  # 1 MB JSON limit
            return jsonify({'ok': False, 'msg': 'حجم الطلب كبير جداً.'}), 413
''')
    print()

    print(SEPARATOR)
    print('  END OF SECURITY CONFIGURATION')
    print(SEPARATOR)


if __name__ == '__main__':
    print_instructions()
