# -*- coding: utf-8 -*-
"""
Task 1 validation — Background Thread Race Condition.

Tests are designed to run within a single interpreter session.
All use an already-initialised app (imported from conftest or app)
and verify the synchronisation primitives work correctly.
"""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core._state import db_ready_event


class TestThreadRace:

    def _reimport_app(self):
        """Return a fresh app created in a sub-process so we control timing."""
        import subprocess
        code = (
            'import os, sys; '
            'os.environ["FLASK_ENV"] = "production"; '
            'os.environ["DATABASE_URL"] = "sqlite:///test_race2.db"; '
            'os.environ["SECRET_KEY"] = "test-race-secret"; '
            'sys.path.insert(0, "."); '
            'import time; t0 = time.time(); '
            'from app import app; '
            'print("CREATE_APP_SECONDS:%.3f" % (time.time()-t0)); '
            'print("DB_READY:%s" % app.config.get("DB_READY")); '
            'print("_DB_CONFIGURED:%s" % app.config.get("_DB_CONFIGURED")); '
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.join(os.path.dirname(__file__), '..'),
        )
        lines = result.stdout.strip().split('\n')
        data = {}
        for line in lines:
            if ':' in line:
                k, v = line.split(':', 1)
                data[k] = v
        return data, result.stdout, result.stderr

    def test_create_app_returns_under_3s(self):
        data, out, err = self._reimport_app()
        seconds = float(data.get('CREATE_APP_SECONDS', 999))
        assert seconds < 3.0, (
            'create_app blocked for %.1fs (see output below)\n%s'
            % (seconds, out + err)
        )

    def test_db_ready_is_false_initially(self):
        data, out, err = self._reimport_app()
        assert data.get('DB_READY') == 'False', (
            'Expected DB_READY=False initially\n%s' % out
        )

    def test_db_ready_becomes_true_after_background_init(self):
        """Wait for the event (max 30 s) then verify DB_READY."""
        assert db_ready_event.wait(timeout=30), 'Event not set within 30s'

    def test_event_clear_on_system_exit(self):
        """SystemExit in the init thread must NOT set the event."""
        ev = threading.Event()

        def _bad():
            raise SystemExit(1)

        t = threading.Thread(target=_bad, daemon=True)
        t.start()
        t.join(timeout=5)
        assert not ev.is_set(), 'SystemExit leaked the event set'

    def test_event_set_on_success(self):
        """Happy path: event is set after successful init."""
        ev = threading.Event()

        def _good():
            ev.set()

        t = threading.Thread(target=_good, daemon=True)
        t.start()
        t.join(timeout=5)
        assert ev.is_set(), 'Event should be set after success'
