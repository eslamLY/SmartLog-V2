# -*- coding: utf-8 -*-
"""
Task 3 — Memory Leak in Rate Limiting.

Verifies that ``_periodic_cleanup`` removes expired entries from all
in-memory dictionaries and that the throttle in ``_maybe_cleanup``
prevents running on every request.
"""
import os
import sys
import time
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.rate_limit import (
    _ip_request_log, _ip_request_log_lock,
    _request_log, _user_action_log, _user_blocked_until, _user_offense_count,
    _banned_ips_cache, _banned_ips_cache_lock,
    _periodic_cleanup, _maybe_cleanup,
    reset_rate_limits,
)


class TestPeriodicCleanup:

    def setup_method(self):
        reset_rate_limits()
        import utils.rate_limit as rl
        rl._last_cleanup_time = 0.0

    # ── _ip_request_log cleanup ───────────────────────────────
    def test_prunes_stale_ip_entries(self):
        old = datetime.now(UTC) - timedelta(seconds=300)
        with _ip_request_log_lock:
            _ip_request_log['1.2.3.4'] = [old]
            _ip_request_log['5.6.7.8'] = [datetime.now(UTC)]
        _periodic_cleanup()
        with _ip_request_log_lock:
            assert '1.2.3.4' not in _ip_request_log
            assert '5.6.7.8' in _ip_request_log

    def test_keeps_recent_ip_entries(self):
        now = datetime.now(UTC)
        with _ip_request_log_lock:
            _ip_request_log['1.2.3.4'] = [now]
        _periodic_cleanup()
        with _ip_request_log_lock:
            assert '1.2.3.4' in _ip_request_log

    # ── _request_log cleanup ──────────────────────────────────
    def test_prunes_stale_route_entries(self):
        old = datetime.now(UTC) - timedelta(seconds=300)
        _request_log['/api/test'] = [old]
        _request_log['/api/recent'] = [datetime.now(UTC)]
        _periodic_cleanup()
        assert '/api/test' not in _request_log
        assert '/api/recent' in _request_log

    # ── _user_action_log cleanup ──────────────────────────────
    def test_prunes_stale_user_entries(self):
        old = datetime.now(UTC) - timedelta(seconds=300)
        _user_action_log[1] = [old]
        _user_action_log[2] = [datetime.now(UTC)]
        _periodic_cleanup()
        assert 1 not in _user_action_log
        assert 2 in _user_action_log

    def test_prunes_expired_user_blocks(self):
        old = datetime.now(UTC) - timedelta(seconds=60)
        _user_blocked_until[1] = old
        _user_offense_count[1] = 3
        _periodic_cleanup()
        assert 1 not in _user_blocked_until
        assert 1 not in _user_offense_count

    def test_keeps_active_user_blocks(self):
        future = datetime.now(UTC) + timedelta(minutes=5)
        _user_blocked_until[2] = future
        _user_offense_count[2] = 1
        _periodic_cleanup()
        assert 2 in _user_blocked_until
        assert _user_offense_count.get(2) == 1

    # ── _banned_ips_cache cleanup ─────────────────────────────
    def test_prunes_expired_banned_ips(self):
        old = datetime.now(UTC) - timedelta(seconds=60)
        with _banned_ips_cache_lock:
            _banned_ips_cache['1.2.3.4'] = {'expiry': old, 'response': {}}
            _banned_ips_cache['5.6.7.8'] = {
                'expiry': datetime.now(UTC) + timedelta(minutes=5), 'response': {}}
        _periodic_cleanup()
        with _banned_ips_cache_lock:
            assert '1.2.3.4' not in _banned_ips_cache
            assert '5.6.7.8' in _banned_ips_cache

    # ── reset_rate_limits clears everything ────────────────────
    def test_reset_clears_all(self):
        with _ip_request_log_lock:
            _ip_request_log['x'] = [datetime.now(UTC)]
        _request_log['/x'] = [datetime.now(UTC)]
        _user_action_log[99] = [datetime.now(UTC)]
        _user_blocked_until[99] = datetime.now(UTC) + timedelta(hours=1)
        with _banned_ips_cache_lock:
            _banned_ips_cache['y'] = {'expiry': datetime.now(UTC) + timedelta(hours=1), 'response': {}}
        reset_rate_limits()
        with _ip_request_log_lock:
            assert len(_ip_request_log) == 0
        assert len(_request_log) == 0
        assert len(_user_action_log) == 0
        assert len(_user_blocked_until) == 0
        assert len(_user_offense_count) == 0
        with _banned_ips_cache_lock:
            assert len(_banned_ips_cache) == 0


class TestCleanupThrottle:

    def setup_method(self):
        reset_rate_limits()
        import utils.rate_limit as rl
        rl._last_cleanup_time = 0.0

    def test_throttle_blocks_early_calls(self):
        """_maybe_cleanup does NOT run _periodic_cleanup twice in quick succession."""
        import utils.rate_limit as rl
        rl._last_cleanup_time = 0.0
        # First call should run
        rl._maybe_cleanup()
        t1 = rl._last_cleanup_time
        assert t1 > 0.0
        # Second call immediately after should be throttled
        rl._maybe_cleanup()
        assert rl._last_cleanup_time == t1

    def test_throttle_allows_after_cooldown(self):
        """_maybe_cleanup runs again after COOLDOWN seconds."""
        import utils.rate_limit as rl
        # Force last_cleanup to be far enough in the past
        rl._last_cleanup_time = time.monotonic() - rl._cleanup_COOLDOWN - 1.0
        rl._maybe_cleanup()
        # last_cleanup_time should have advanced
        assert rl._last_cleanup_time > time.monotonic() - 1

    def test_high_volume_does_not_grow(self):
        """Simulate many distinct IPs; after cleanup, only recent ones remain."""
        now = datetime.now(UTC)
        # Insert 1000 stale timestamps and 1 recent one at a unique key
        with _ip_request_log_lock:
            for i in range(1000):
                _ip_request_log[f'10.0.0.{i}'] = [now - timedelta(seconds=300)]
            _ip_request_log['10.0.200.1'] = [now]
        before = len(_ip_request_log)
        _periodic_cleanup()
        with _ip_request_log_lock:
            after = len(_ip_request_log)
        assert before == 1001
        assert after == 1

    def test_empty_dicts_no_error(self):
        """_periodic_cleanup handles empty state gracefully."""
        reset_rate_limits()
        _periodic_cleanup()  # must not raise
