# Render Security Checklist — SmartLog V2

Comprehensive checklist for hardening the Render deployment. Tick each as verified.

---

## Pre-Deploy

- [ ] **SECRET_KEY** — auto-generated on first deploy; verify via Dashboard > Environment
- [ ] **DATABASE_URL** — auto-linked from `smartlog-db` service; verify connection
- [ ] **FIELD_ENCRYPTION_KEY** — set explicitly if separate from SECRET_KEY
- [ ] **BACKUP_ENCRYPTION_KEY** — set explicitly to enable encrypted backups
- [ ] **FLASK_ENV=production** — set in render.yaml
- [ ] **PRODUCTION=true** — set in render.yaml
- [ ] **LOG_LEVEL=info** — avoid debug in production
- [ ] **.env not committed** — verify .gitignore includes `.env`
- [ ] **requirements.txt pinned** — all packages use `==` version pinning

---

## Network Security

- [ ] **HTTPS enforced** — Render auto-proxies all requests over TLS
- [ ] **HSTS header** — `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- [ ] **X-Frame-Options: DENY** — prevents clickjacking
- [ ] **X-Content-Type-Options: nosniff** — prevents MIME sniffing
- [ ] **CSP headers** — restrict script-src, style-src, font-src to known origins
- [ ] **DB IP whitelist** — set `ipAllowList: []` (Render private network only)
- [ ] **No hardcoded secrets** — all credentials via env vars

---

## Application Hardening

- [ ] **Flask-Limiter** — rate limiting configured (brute-force protection)
- [ ] **WTForms CSRF** — CSRF protection on all forms
- [ ] **Flask session cookies** — `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`
- [ ] **Session timeout** — configurable idle timeout
- [ ] **Field-level encryption** — sensitive PII encrypted at rest
- [ ] **Input validation** — all user inputs sanitized (XSS prevention)
- [ ] **Jinja2 autoescaping** — enabled (Flask default)

---

## Docker Security

- [ ] **Non-root user** — add `RUN useradd -m appuser && USER appuser` to Dockerfile
- [ ] **Slim base image** — `python:3.13-slim` (smaller attack surface)
- [ ] **APT cache cleaned** — `rm -rf /var/lib/apt/lists/*`
- [ ] **pip no-cache-dir** — `pip install --no-cache-dir`
- [ ] **No build tools in final image** — multi-stage build ideal
- [ ] **Read-only root filesystem** — consider `--read-only` flag
- [ ] **No secrets in image layers** — all via runtime env vars

---

## Logging & Monitoring

- [ ] **Gunicorn access logs** — `--access-logfile -` in Procfile
- [ ] **Gunicorn error logs** — `--error-logfile -` in Procfile
- [ ] **Audit logging** — business events tracked via AuditLog model
- [ ] **Sensitive data masked** — no secrets, tokens, or keys in logs
- [ ] **Log level configurable** — via LOG_LEVEL env var
- [ ] **Render logs retention** — 7 days on free/starter; longer on Pro

---

## Backups & Disaster Recovery

- [ ] **Automated DB backups** — Render Pro: PITR; Starter: manual pg_dump
- [ ] **Encrypted backups** — BACKUP_ENCRYPTION_KEY configured
- [ ] **Backup scheduling** — APScheduler cron job for periodic backups
- [ ] **Restore tested** — verify `restore_backup()` works on staging
- [ ] **Off-site backup** — push encrypted backups to external storage (S3, B2)
- [ ] **Disaster recovery package** — `create_disaster_recovery_package()` tested

---

## CI/CD (GitHub Actions)

- [ ] **GitHub Secrets** — used for all tokens, keys, passwords
- [ ] **SAST scanning** — Bandit or similar in CI pipeline
- [ ] **Dependency scanning** — Dependabot enabled
- [ ] **No secrets in Actions logs** — avoid `echo` of secret values
- [ ] **Branch protection** — main branch requires PR + passing checks

---

## Post-Deploy Verification

- [ ] **Health endpoint responds** `GET /api/health` → 200
- [ ] **Static files load** — check `/static/css/style.css` etc.
- [ ] **CSP headers present** — verify via browser DevTools > Network > Response Headers
- [ ] **No debug endpoints** — `/debug*` removed or gated by FLASK_DEBUG
- [ ] **Rate limiting active** — test with rapid requests → 429 after limit
- [ ] **HTTPS enforced** — `http://` → redirects to `https://`
- [ ] **Login works** — end-to-end auth flow
- [ ] **File upload works** — test with valid and invalid file types
