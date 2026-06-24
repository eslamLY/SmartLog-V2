# Render Deployment Security — SmartLog V2

## Overview

Render is the production hosting platform for SmartLog V2. This document covers the security posture of the deployment configuration.

---

## Infrastructure Diagram

```
Internet ──→ Render Edge (TLS) ──→ Web Service (Gunicorn+Flask) ──→ PostgreSQL
                                        │
                                   Render Private Network
                                        │
                                   smartlog-db (starter, PG 16)
```

All traffic between the internet and Render is encrypted via TLS 1.2+. Communication between the web service and database occurs over Render's private network — traffic never traverses the public internet.

---

## Environment Variables

| Variable | Source | Security Notes |
|---|---|---|
| `SECRET_KEY` | Auto-generated on deploy | 32-byte hex, never stored in code |
| `DATABASE_URL` | Auto-linked from DB service | Render injects via private network |
| `FIELD_ENCRYPTION_KEY` | Derived from SECRET_KEY or explicit | Encrypts PII at rest |
| `BACKUP_ENCRYPTION_KEY` | Manual set in Dashboard | Encrypts backup archives |
| `FLASK_ENV` | `production` in render.yaml | Disables Flask debug mode |
| `PRODUCTION` | `true` in render.yaml | Enables production security headers |

Render secrets are never exposed in logs, git history, or build artifacts.

---

## TLS / HTTPS

- Render provides automatic TLS termination at the edge
- TLS 1.2+ enforced (Render does not support SSLv3, TLS 1.0, or 1.1)
- Application sets HSTS header: `max-age=31536000; includeSubDomains`
- HTTP → HTTPS redirect via `production_security_headers()` middleware
- Certificate management is fully automated by Render (Let's Encrypt)

---

## Dockerfile Hardening

Current posture:
- Base image: `python:3.13-slim` — minimal attack surface
- APT packages cleaned: `rm -rf /var/lib/apt/lists/*`
- pip installed: `--no-cache-dir`
- Layer caching: requirements copied before source code

**Recommended improvements:**
1. Add non-root user: `RUN useradd -m appuser && USER appuser`
2. Add HEALTHCHECK instruction (though Render uses external health check)
3. Consider multi-stage build to exclude build tools (gcc, libpq-dev) from final image

---

## Render Configuration

**render.yaml highlights:**
- `runtime: docker` — ensures consistent environment between dev and prod
- `autoDeploy: true` — every push to main triggers a deploy
- `healthCheckPath: /api/health` — Render monitors application health
- `ipAllowList: []` — DB accessible only from Render private network (not public internet)
- `plan: starter` — 512 MB RAM (web), 1 GB RAM (DB)

**Gunicorn configuration (Procfile):**
- 2 workers / 4 threads — adequate for starter plan
- 120s timeout — prevents slow-client attacks from hanging workers
- Access + error logs to stdout — collected by Render log infrastructure

---

## Backup & Recovery

| Tier | Backup Type | Frequency | Retention |
|---|---|---|---|
| Starter (current) | Manual `pg_dump` | On-demand via backup service | Manual |
| Pro | Automated | Daily + PITR | 7 days |
| Custom | Encrypted archive | Cron via APScheduler | Configurable |

Encrypted backups can be pushed to external storage (S3, Backblaze B2) for off-site redundancy.

---

## Rate Limits & Abuse Prevention

- Flask-Limiter configured with per-IP and per-endpoint limits
- Login endpoint: 10 requests/min/IP
- Registration: 3 requests/min/IP
- API endpoints: 60 requests/min/IP
- Global: 200 requests/min

---

## Monitoring & Incident Response

- Health endpoint: `GET /api/health` — returns 200 OK when operational
- Render logs: accessible via Dashboard > Logs (7-day retention)
- Audit trail: business events logged via `AuditLog` database model
- Render status: https://status.render.com
- Support: Render Community or paid support channels

---

## Security Contacts & References

- Render Security: https://render.com/security
- Render Status: https://status.render.com
- Render Docs: https://render.com/docs
- OWASP Top 10: https://owasp.org/Top10
- Flask Security: https://flask.palletsprojects.com/en/stable/security/
