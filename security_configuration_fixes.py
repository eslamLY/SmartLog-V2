#!/usr/bin/env python3
"""
SmartLog V2 — Security Configuration Fixes
Copy-paste-ready code to fix all findings from the security audit.

Usage:
  1. Review each fix section
  2. Copy the relevant code into your application
  3. Update any placeholders (enclosed in <angle brackets>)
  4. Test before deploying to production
"""
import os
from datetime import timedelta

# ═══════════════════════════════════════════════════════════════
# SEC-003: Remove default SECRET_KEY from config.py
# ═══════════════════════════════════════════════════════════════
class ProductionConfig:
    """Replace your existing BaseConfig with this."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError('SECRET_KEY environment variable is not set!')
    # NEVER add a fallback default value


# ═══════════════════════════════════════════════════════════════
# SEC-008: Cookie security flags (add to create_app())
# ═══════════════════════════════════════════════════════════════
def configure_cookie_security(app):
    """Add to your create_app() function."""
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,    # requires HTTPS
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )


# ═══════════════════════════════════════════════════════════════
# SEC-016: Session idle timeout middleware
# ═══════════════════════════════════════════════════════════════
from flask import session, redirect, url_for, request
import time

def session_timeout_middleware():
    """Call before each request to enforce idle timeout."""
    if 'user_id' in session:
        last = session.get('last_activity', 0)
        now = time.time()
        # 30-minute idle timeout
        if now - last > 1800:
            session.clear()
            return redirect(url_for('auth.login'))
        session['last_activity'] = now


# ═══════════════════════════════════════════════════════════════
# SEC-005: Dockerfile non-root user
# ═══════════════════════════════════════════════════════════════
# Add these lines to your Dockerfile after COPY . .:
#
#   RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
#   USER appuser


# ═══════════════════════════════════════════════════════════════
# SEC-006: Enforce SSL on database connection
# ═══════════════════════════════════════════════════════════════
def configure_db_ssl(app):
    """Add sslmode=require for production database connections."""
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgresql://'):
        if 'sslmode' not in db_url:
            db_url += '?sslmode=require'
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url


# ═══════════════════════════════════════════════════════════════
# SEC-007: render.yaml production settings
# ═══════════════════════════════════════════════════════════════
# Add to render.yaml envVars section:
#
#   - key: FLASK_ENV
#     value: production
#   - key: PRODUCTION
#     value: "true"


# ═══════════════════════════════════════════════════════════════
# SEC-009: Password strength validation
# ═══════════════════════════════════════════════════════════════
import re

def validate_password_strength(password):
    """Returns (is_valid, error_message)."""
    if len(password) < 8:
        return False, 'Password must be at least 8 characters'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain an uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain a lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain a digit'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'Password must contain a special character'
    return True, ''


# ═══════════════════════════════════════════════════════════════
# SEC-010: Rate limit on /api/auth/token
# ═══════════════════════════════════════════════════════════════
# Add Flask-Limiter decorator to the token endpoint:
#
#   from flask_limiter import Limiter
#   from flask_limiter.util import get_remote_address
#
#   limiter = Limiter(key_func=get_remote_address)
#
#   @bp.route('/api/auth/token', methods=['POST'])
#   @limiter.limit('10 per minute')
#   def get_token():
#       ...


# ═══════════════════════════════════════════════════════════════
# SEC-015: Enable CSRF protection
# ═══════════════════════════════════════════════════════════════
def configure_csrf(app):
    """Enable full CSRF protection."""
    app.config.update(
        WTF_CSRF_CHECK_DEFAULT=True,
        WTF_CSRF_SSL_STRICT=True,
    )
    # Ensure all forms include: {{ form.hidden_tag() }}
    # For AJAX: include X-CSRFToken header from cookie


# ═══════════════════════════════════════════════════════════════
# SEC-018: Custom error handlers
# ═══════════════════════════════════════════════════════════════
def register_error_handlers(app):
    """Add custom error handlers to prevent information leakage."""

    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request'}, 400

    @app.errorhandler(403)
    def forbidden(e):
        return {'error': 'Forbidden'}, 403

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        from models.audit import AuditLog
        from flask import request
        AuditLog.log_action(
            action='RATE_LIMIT',
            details=f'IP {request.remote_addr} hit rate limit on {request.path}'
        )
        return {'error': 'Too many requests'}, 429

    @app.errorhandler(500)
    def internal_error(e):
        import logging
        logging.exception('Internal server error')
        return {'error': 'Internal server error'}, 500


# ═══════════════════════════════════════════════════════════════
# SEC-019: Persistent API token storage
# ═══════════════════════════════════════════════════════════════
# Replace the in-memory API_TOKENS dict with a database model:
#
#   class ApiToken(db.Model):
#       __tablename__ = 'api_tokens'
#       id = db.Column(db.Integer, primary_key=True)
#       user_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
#       token = db.Column(db.String(64), unique=True, nullable=False)
#       created_at = db.Column(db.DateTime, default=datetime.utcnow)
#       expires_at = db.Column(db.DateTime, nullable=True)
#       is_revoked = db.Column(db.Boolean, default=False)
#       last_used_at = db.Column(db.DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════════
# SEC-021: Set MAX_CONTENT_LENGTH
# ═══════════════════════════════════════════════════════════════
def configure_upload_limits(app):
    """Limit request body size to prevent DoS."""
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB


# ═══════════════════════════════════════════════════════════════
# SEC-026: Docker HEALTHCHECK
# ═══════════════════════════════════════════════════════════════
# Add to Dockerfile:
#
#   HEALTHCHECK --interval=30s --timeout=10s --start-period=15s \
#     CMD curl -f http://localhost:5000/api/health || exit 1
#   RUN apt-get install -y --no-install-recommends curl


# ═══════════════════════════════════════════════════════════════
# SEC-028: Log rate limit events
# ═══════════════════════════════════════════════════════════════
# Already included in register_error_handlers() above (429 handler)


# ═══════════════════════════════════════════════════════════════
# SEC-011/012: Field-level encryption for national_id & bank
# ═══════════════════════════════════════════════════════════════
# Add to models/employee.py:
#
#   national_id_encrypted = db.Column(db.LargeBinary, nullable=True)
#   bank_account_encrypted = db.Column(db.LargeBinary, nullable=True)
#
# Add getter/setter methods:
#
#   @property
#   def national_id(self):
#       if self.national_id_encrypted:
#           return get_fernet().decrypt(self.national_id_encrypted).decode()
#       return None
#
#   @national_id.setter
#   def national_id(self, value):
#       if value:
#           self.national_id_encrypted = get_fernet().encrypt(value.encode())
#
# Add migration script to move existing data:
#
#   for emp in Employee.query.all():
#       if emp.national_id and not emp.national_id_encrypted:
#           emp.national_id = emp.national_id  # triggers setter → encrypts
#   db.session.commit()


if __name__ == '__main__':
    print('SmartLog V2 — Security Configuration Fixes')
    print('This file contains copy-paste-ready code snippets.')
    print('Review each section, adapt to your codebase, and test.')
