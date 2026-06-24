# SmartLog V2 — Security Monitoring Setup
> Generated: 2026-06-24 03:24:31

## 1. Log Analysis

### Key Log Sources
| Source | Location | Retention |
|--------|----------|-----------|
| Gunicorn Access Logs | Render Dashboard > Logs | 7 days (free/starter) |
| Gunicorn Error Logs | Render Dashboard > Logs | 7 days |
| Flask Application Logs | stdout (captured by Render) | 7 days |
| AuditLog DB Table | PostgreSQL `audit_logs` table | Indefinite |
| LoginAttempt DB Table | PostgreSQL `login_attempts` table | Indefinite |

### What to Monitor
- **429 responses**: Brute-force attempts, scraping, DDoS
- **401/403 responses**: Unauthorized access attempts
- **500 responses**: Potential exploits triggering unhandled errors
- **Unusual IP patterns**: Single IP hitting many endpoints rapidly
- **POST to GET-only endpoints**: Reconnaissance
- **Large request bodies**: Data exfiltration attempts

### Log Query Examples (Render Logs)
```
# Find all 429 rate-limit blocks
429

# Find all authorization failures
401 OR 403

# Find errors by IP
"203.0.113.42" AND (error OR exception OR 500)
```

## 2. Alert Configuration

### Render Alerts (Pro plan)
| Alert | Threshold | Action |
|-------|-----------|--------|
| High 5xx Rate | >5% of requests return 5xx in 5 min | Email + Slack |
| High 429 Rate | >20% of responses are 429 | Email + Slack |
| Low Health Check | Health check fails 3 times consecutively | Email + SMS |
| Memory/CPU Spike | >80% utilization for 5 min | Email |

### Custom Alert Script (Python)
```python
import os, smtplib, requests

def check_and_alert():
    # Check health endpoint
    r = requests.get('https://smartlog-v2-1.onrender.com/api/health')
    if r.status_code != 200:
        send_alert(f'Health check failed: {r.status_code}')

    # Check recent AuditLog for suspicious activity
    # (query your internal DB for recent 429s or auth failures)

def send_alert(message):
    print(f'[ALERT] {message}')
    # Add email/Slack/Telegram integration here

if __name__ == '__main__':
    check_and_alert()
```

## 3. Incident Response Procedures

### Triage (0-30 min)
1. Confirm incident via Render Dashboard > Logs
2. Determine scope: single user, endpoint, or system-wide
3. Check if data was accessed or modified

### Containment (30-60 min)
1. If DoS: enable stricter rate limiting or block offending IP
2. If auth bypass: rotate all sessions (change SECRET_KEY)
3. If data breach: isolate affected records, notify users

### Recovery (1-4 hours)
1. Restore from latest clean backup if data corrupted
2. Apply security patch or configuration change
3. Verify fix on staging, then deploy to production

### Post-Mortem (1-2 days)
1. Document root cause and timeline
2. Update security testing procedures
3. Update this monitoring setup document

## 4. Automated Security Testing Setup

### GitHub Actions (already configured: .github/workflows/github_actions_security.yml)
- Bandit SAST scan on every PR
- pip-audit dependency vulnerability scan
- Safety package check
- Infrastructure security checker
- Requirements security audit

### Periodic Testing Schedule
| Frequency | Test | Tool |
|-----------|------|------|
| Every PR | Static analysis (SAST) | Bandit |
| Daily | Dependency scan | pip-audit |
| Weekly | Full security suite | All checkers |
| Monthly | Penetration test | Manual + automation |
| Quarterly | Third-party audit | External firm |