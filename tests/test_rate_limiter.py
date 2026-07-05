# -*- coding: utf-8 -*-
"""
Task 2 validation — Rate Limiter & Anti-Abuse.

Tests verify the rate-limit contract WITHOUT reloading the Flask app
(which is already imported by conftest and has tables created).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask
from utils.rate_limit import check_rate_limit, rate_limit_headers


class TestRateLimiter:

    def test_production_registers_without_error(self):
        """register_limiter runs without ConfigurationError in production."""
        from core.routes import register_limiter
        app = Flask(__name__)
        app.config['PRODUCTION'] = True
        app.config['TESTING'] = False
        register_limiter(app)

    def test_testing_registers_without_error(self):
        """register_limiter also works under TESTING."""
        from core.routes import register_limiter
        app = Flask(__name__)
        app.config['PRODUCTION'] = True
        app.config['TESTING'] = True
        register_limiter(app)

    def test_check_rate_limit_under_limit(self):
        """Under limit: returns (True, remaining)."""
        key = 'test_under'
        allowed, remaining = check_rate_limit(key, 5, 60)
        assert allowed is True
        assert isinstance(remaining, int)

    def test_check_rate_limit_headers(self):
        """rate_limit_headers returns the three expected headers."""
        headers = rate_limit_headers(10, 7, 60)
        assert headers['X-RateLimit-Limit'] == '10'
        assert headers['X-RateLimit-Remaining'] == '7'
        assert 'X-RateLimit-Reset' in headers

    def test_gps_cooldown_function_exists(self):
        """The GPS route function has a session-based 60 s cooldown check."""
        from routes.employee import gps_log
        import inspect
        source = inspect.getsource(gps_log)
        assert "gps_last_time" in source
        assert "elapsed < 60" in source

    def test_login_attempt_threshold(self):
        """Login route imports and uses a MAX_LOGIN_ATTEMPTS constant >= 5."""
        from routes.auth import MAX_LOGIN_ATTEMPTS
        assert MAX_LOGIN_ATTEMPTS >= 5

    def test_login_attempt_deletes_on_success(self):
        """Login route deletes attempt row on successful auth."""
        from routes.auth import login
        import inspect
        source = inspect.getsource(login)
        assert 'db.session.delete(attempt)' in source
        assert 'login_time' in source
