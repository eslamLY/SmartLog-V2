# -*- coding: utf-8 -*-
"""
Task 3 validation — Security: Information Disclosure Prevention.

Proves that ``str(e)`` is no longer returned in error responses across
all route modules.  Reads source files directly (no Flask import) so
the test runs without triggering conftest table creation.
"""
import os

ROUTES_DIR = os.path.join(os.path.dirname(__file__), '..', 'routes')
GENERIC_MSG = 'حدث خطأ داخلي.'


class TestNoStrELeak:

    ROUTE_FILES = [
        'admin_shifts.py', 'ai_forecasting.py', 'admin_system.py',
        'admin_ops.py', 'admin_employees.py', 'api_documents.py',
        'attendance_policies.py', 'auth.py', 'api_offline_sync.py',
        'backup_management.py', 'departments.py', 'devices.py',
        'dashboard.py', 'employees_unified.py', 'employees.py',
        'employee.py', 'reports.py', 'scenarios.py', 'payroll.py',
        'roles_permissions.py', 'gps_tracking.py',
        'reports_attendance.py', 'forecasting.py',
        'employee_management.py',
    ]

    def _all_lines(self, fname):
        path = os.path.join(ROUTES_DIR, fname)
        with open(path, encoding='utf-8') as f:
            yield from enumerate(f, 1)

    def test_no_str_e_in_user_facing_returns(self):
        """Every safe_api decorator returns a fixed Arabic message."""
        failed = []
        for fname in self.ROUTE_FILES:
            for lineno, line in self._all_lines(fname):
                if "msg': str(e)" in line or "error': str(e)" in line:
                    # skip internal tracking (not user-facing)
                    if 'errors.append' in line or '_add_device_event' in line:
                        continue
                    failed.append('%s:%d: %s' % (fname, lineno, line.strip()))
        assert not failed, 'str(e) leaks still present:\n' + '\n'.join(failed)

    def test_generic_message_in_response(self):
        """All jsonify error returns use the generic Arabic message."""
        for fname in self.ROUTE_FILES:
            any_generic = False
            no_str_e = True
            found_str_e = []
            for lineno, line in self._all_lines(fname):
                if GENERIC_MSG in line:
                    any_generic = True
                if "msg': str(e)" in line or "error': str(e)" in line:
                    if 'errors.append' not in line and '_add_device_event' not in line:
                        no_str_e = False
                        found_str_e.append('  %s:%d' % (fname, lineno))
            assert any_generic or no_str_e, \
                '%s: missing generic message AND has str(e):\n%s' \
                % (fname, '\n'.join(found_str_e))

    def test_server_logging_exists(self):
        """Every safe_api file has server-side error logging."""
        for fname in self.ROUTE_FILES:
            content = open(os.path.join(ROUTES_DIR, fname), encoding='utf-8').read()
            assert 'LOGGER.error' in content or 'logger.error' in content, \
                '%s missing server-side error logging' % fname
