# Backend Code Security Review — SmartLog V2

**Date:** 2026-06-24  
**Reviewer:** Automated Security Audit  
**Target:** Flask application (Python 3.12)

---

## 1. `app.py` — Main Application Entry Point

### Critical Issues

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 77–80 | `sys.exit(1)` if DB URL doesn't start with `postgresql://` | **HIGH** | App crashes hard on misconfiguration. Acceptable for production but prevents local testing with SQLite. |
| 351 | `WTF_CSRF_CHECK_DEFAULT = False` | **MEDIUM** | Flask-WTF CSRF is imported but disabled globally. Custom X-CSRFToken validation added in Phase 3.3 mitigates this, but no audit trail if token missing. |
| 157–158 | Fernet key fallback | **LOW** | If `FIELD_ENCRYPTION_KEY` is unset, `SHA256(SECRET_KEY)` is used. Changing `SECRET_KEY` would corrupt all encrypted data. |

### Code Review Notes

- **Lines 22–27**: Logging configured before `app` creation. Good.
- **Lines 39–43**: Environment detection logic is clear. Good.
- **Lines 48–88**: `DATABASE_URL` parsing is strict. The `postgres://` -> `postgresql://` replacement is correct.
- **Lines 91–136**: Flask app config, session settings (`SESSION_COOKIE_HTTPONLY=True`, `SAME_SITE='Lax'`, `SECURE=True` in prod, 4h lifetime). All appropriately set.
- **Lines 139–150**: `context_processor` injects `csrf_token` from session. Token generated as `uuid.uuid4().hex` — 32 hex chars, sufficient entropy.
- **Lines 152–162**: Fernet key setup with fallback warning. Should log a WARNING not INFO.
- **Lines 198–200**: DB connection retry logic (5 retries, 3s delay). Good for Render cold start.
- **Lines 349–353**: CSRFProtect + Limiter initialization. Both configured.
- **Lines 355–365**: 429 handler with AuditLog entry + blocked template. Good.
- **Lines 383–390**: `check_auto_ban` — IP flood detection (266 req/min). Uses `check_ip_flood`.
- **Lines 393–412**: `production_security_headers` — HSTS, X-Content-Type-Options, X-Frame-Options, CSP. All correct.
- **Line 415–end**: Startup migrations and seed. Graceful with `rollback()` on failure.

---

## 2. `config.py` — Configuration

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 38 | `SECRET_KEY = 'dev-secret-change-in-prod'` | **HIGH** | Default secret in source code. Must be overridden via env var in production. |
| 43 | `WTF_CSRF_CHECK_DEFAULT = False` | **MEDIUM** | Disables Flask-WTF automatic CSRF checking. See mitigation in app.py. |
| 65–78 | CSP string generation | **INFO** | Uses `'unsafe-inline'` for scripts and styles. Required for inline `<script>` tags in templates. Safe because no user input is reflected inline. |

---

## 3. `routes/auth.py` — Authentication

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 53–104 | Login endpoint | **HIGH** | No rate limiting on `/api/auth/token` (separate file). |
| 55–57 | Rate limit check: 5 attempts / 300s | **INFO** | Properly implemented. |
| 60 | `username.upper()` | **INFO** | Normalization prevents case-sensitivity issues. |
| 65–70 | IP blocking via `LoginAttempt.blocked_until` | **INFO** | Blocked for 1 hour after 5 failures. |
| 73 | `check_password_hash(emp.password_hash, password)` | **INFO** | Uses werkzeug's constant-time comparison. |
| 83–88 | `session.permanent = True` + session data | **INFO** | 4-hour lifetime enforced. |
| 89 | Redirect to dashboard or force_password_change | **INFO** | Phase 3.4 improvement. |
| 127–149 | `/api/init-db` | **HIGH** | Protected with `role == 'admin'` + rate limit (2/hour). `traceback.format_exc()` on line 149 leaks stack traces on error. |
| 130 | `check_rate_limit('init_db', 2, 3600)` | **INFO** | Good — limits DB init to 2/hour. |

---

## 4. `routes/api_offline_sync.py` — Offline Sync API

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 13 | `API_TOKENS = {}` | **MEDIUM** | In-memory dict. Lost on app restart. Not shared across gunicorn workers. |
| 109–396 | `/api/attendance/offline-sync` | **MEDIUM** | Uses `validate_token()` for auth. No rate limiting. |
| 140–148 | Employee ID override | **MEDIUM** | `raw_employee_id` from user input can reference a *different* employee. The code queries `Employee.query.filter(...)` and uses `target.id`. If the token belongs to Employee A, but A sends employee_id=B's username, the attendance is logged for B. Limited by `is_active` check. |
| 399–423 | `/api/auth/token` | **MEDIUM** | No rate limiting. Brute-force possible. |
| 400–408 | Issues API token after password check | **INFO** | Token valid for 30 days (line 17). No refresh mechanism. |

---

## 5. `services/backup_service.py` — Backup System

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 127 | `text(f'SELECT * FROM "{table}"')` | **LOW** | Table name from `inspect.get_table_names()` (DB-controlled). Safe. |
| 473 | `text(f'SELECT * FROM "{table}"')` | **LOW** | Same as above. |

---

## 6. `services/restoration_service.py` — Restore System

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 37 | `text(f'DELETE FROM "{table}"')` | **MEDIUM** | Table name from backup file (potentially tampered). Mitigated in Phase 3.2 with `_validate_tables()` whitelist. |
| 59 | `text(f'INSERT OR REPLACE INTO "{table}" (...)` | **MEDIUM** | Same. Now validated. |

---

## 7. `services/encryption_service.py` — Encryption

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 13 | `PBKDF2_ITERATIONS = 600000` | **INFO** | Strong iteration count (OWASP recommends 600K for PBKDF2-SHA256). |
| 17–32 | `_get_or_derive_key()` | **INFO** | Derives Fernet key from master password + random salt + PBKDF2. |
| 72–96 | `secure_delete()` | **LOW** | Overwrites file 3 times before deletion. Not guaranteed on SSD (wear leveling) or Windows. Better to use OS-level `cipher /w` or encrypted filesystem. |

---

## 8. `utils/decorators.py` — Auth Decorators

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 10–53 | `login_required`, `admin_required`, `employee_required` | **INFO** | All check `user_id` in session, timeout via `last_activity`, and redirect to login. |
| 55–79 | `audit_log_action` | **INFO** | Logs action, entity type, IP, path, and sanitized args (excludes password/token/api_key). |
| 81–92 | `own_data_only` | **INFO** | Prevents employee accessing other employees' data. |

---

## 9. `utils/helpers.py` — Validation Helpers

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 10–18 | `validate_password_strength` | **INFO** | Minimum 8 chars, must have upper + lower + digit. Good baseline. |
| 20–28 | `validate_coordinates`, `validate_latitude`, `validate_longitude` | **INFO** | Proper range checks. |
| 31–34 | `validate_employee_id` | **INFO** | Digit-only, 3-10 chars. |
| 36–38 | `validate_date_iso` | **INFO** | Regex checks ISO 8601 format. |
| 47–48 | `safe_json` | **INFO** | Escapes `<`, `>`, `&`, `'` in JSON output. |

---

## 10. `models/employee.py` — Employee Model

| Line | Issue | Severity | Description |
|------|-------|----------|-------------|
| 11 | `password_hash = db.Column(db.String(256))` | **INFO** | 256 chars is sufficient for pbkdf2:sha256 hash. |
| 12–13 | `base_salary_encrypted`, `email_encrypted`, `phone_encrypted` | **INFO** | Fernet-encrypted columns. |
| 89–133 | `secure_email`, `secure_phone`, `base_salary` properties | **INFO** | Transparent decrypt on read, encrypt on write. Fallback to plaintext if decrypt fails. |
| 119–132 | `base_salary` property | **LOW** | Returns `0.0` if decrypt fails. Could hide data corruption. |

---

## 11. `utils/rate_limit.py` (referenced from app.py)

| Issue | Severity | Description |
|-------|----------|-------------|
| IP flood limit: 266 req/min | **INFO** | Human users < 100 req/min on normal usage. 266 allows some burst. |
| Login rate limit: 5/5min | **INFO** | Standard. |
| DB init rate limit: 2/hour | **INFO** | Good for sensitive operation. |
| Per-IP action tracking | **INFO** | `_user_action_log` tracks all actions per user/IP. |

---

## Overall Security Posture

| Category | Rating | Notes |
|----------|--------|-------|
| **Password Hashing** | ✅ GOOD | pbkdf2:sha256 via werkzeug |
| **Session Security** | ✅ GOOD | HttpOnly + SameSite=Lax + Secure(prod) + 4h timeout |
| **SQL Injection** | ✅ GOOD | ORM used throughout; raw SQL limited to table names |
| **Input Validation** | ⚠️ ADEQUATE | Password, GPS, phone validated; more needed on API fields |
| **Error Handling** | ⚠️ ADEQUATE | 429 handler present; 500 handler missing; traceback leak on init-db |
| **API Security** | ⚠️ ADEQUATE | Most endpoints have auth; offline-sync needs rate limiting |
| **CSRF** | ⚠️ MITIGATED | Flask-WTF disabled; custom X-CSRFToken in Phase 3.3 |
| **Encryption** | ✅ GOOD | Fernet AES-128 for fields; PBKDF2 for backup keys |
| **Rate Limiting** | ✅ GOOD | Login, IP flood, DB init all rate-limited |

### Top 5 Recommended Fixes

1. **HIGH**: Remove `traceback.format_exc()` from `/api/init-db` — returns stack traces to client
2. **MEDIUM**: Add rate limiting to `/api/auth/token` — no brute-force protection on API token issuance
3. **MEDIUM**: Persist API tokens in database instead of in-memory dict — lost on restart, not worker-safe
4. **MEDIUM**: Change default `SECRET_KEY` in `config.py` — `'dev-secret-change-in-prod'` appears in source
5. **LOW**: Add `@app.errorhandler(500)` to prevent default Flask debug page in production
