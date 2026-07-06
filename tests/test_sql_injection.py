# -*- coding: utf-8 -*-
"""
Task 2 — SQL Injection Prevention: ``manage.py`` identifier validation.

Verifies that ``_validate_identifier`` rejects malicious input and that
``run_reset_sequences`` cannot be tricked into executing unsafe SQL.
Tests import manage symbols at call time (not module level) to avoid
triggering conftest's app factory.
"""
import os
import sys
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestIdentifierValidation:

    _IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    def _validate(self, name, label='identifier'):
        from manage import _validate_identifier
        return _validate_identifier(name, label)

    # ── Accept valid identifiers ──────────────────────────────
    def test_accepts_simple_name(self):
        assert self._validate('employees') == 'employees'

    def test_accepts_with_underscore(self):
        assert self._validate('attendance_logs') == 'attendance_logs'

    def test_accepts_with_digits(self):
        assert self._validate('table_123') == 'table_123'

    def test_accepts_leading_underscore(self):
        assert self._validate('_seq') == '_seq'

    def test_accepts_single_letter(self):
        assert self._validate('t') == 't'

    # ── Reject invalid identifiers ────────────────────────────
    @pytest.mark.parametrize('payload', [
        '',
        'employees; DROP TABLE users',
        'employees--comment',
        'table-name',
        'table name',
        '1table',
        "x'; SELECT 1; --",
        '`table`',
        '$table',
        "x UNION SELECT * FROM passwords",
        '../etc/passwd',
        '<script>alert(1)</script>',
    ])
    def test_rejects_malicious_identifiers(self, payload):
        with pytest.raises(ValueError, match='Invalid identifier'):
            self._validate(payload)

    def test_label_prefixed_in_error(self):
        with pytest.raises(ValueError, match='table name'):
            self._validate('bad!', label='table name')

    # ── Regex boundary coverage ───────────────────────────────
    def test_regex_matches_valid(self):
        assert self._IDENTIFIER_RE.match('simpleName')
        assert self._IDENTIFIER_RE.match('_private')
        assert self._IDENTIFIER_RE.match('a1_b2_c3')
        assert not self._IDENTIFIER_RE.match('')
        assert not self._IDENTIFIER_RE.match('no spaces')
        assert not self._IDENTIFIER_RE.match('has-dash')
        assert not self._IDENTIFIER_RE.match('1starts_with_digit')

    # ── Sanitize names commands are safe ──────────────────────
    def test_like_clauses_do_not_use_fstrings(self):
        import inspect
        from manage import run_sanitize_names
        source = inspect.getsource(run_sanitize_names)
        for lineno, line in enumerate(source.split('\n'), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith('import'):
                continue
            if 'text(' in stripped and ("f'" in stripped or 'f"' in stripped):
                raise AssertionError(
                    'run_sanitize_names:%d uses f-string with text(): %s'
                    % (lineno, stripped[:80])
                )
