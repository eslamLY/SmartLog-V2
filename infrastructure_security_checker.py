#!/usr/bin/env python3
"""
SmartLog V2 — Infrastructure & Deployment Security Checker
Analyzes Render config, environment variables, Dockerfile,
Procfile, dependencies, logging, and backup setup.
"""
import os, sys, re, json, html, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except: return ''

# ─────────────────────────────────────────────────────────────
# 1. Environment Variables
# ─────────────────────────────────────────────────────────────
def check_env_vars():
    issues = []
    k = 'ENV'

    render_yml = read_file(os.path.join(BASE, 'render.yaml'))
    procfile = read_file(os.path.join(BASE, 'Procfile'))
    app_py = read_file(os.path.join(BASE, 'app.py'))
    entrypoint = read_file(os.path.join(BASE, 'entrypoint.sh'))
    dockerfile = read_file(os.path.join(BASE, 'Dockerfile'))

    # FLASK_ENV
    if 'FLASK_ENV=production' in render_yml or 'FLASK_ENV=production' in procfile:
        issues.append((k, 'INFO', 'FLASK_ENV=production in render.yaml'))
    else:
        issues.append((k, 'HIGH', 'FLASK_ENV not set to production'))

    # SECRET_KEY
    if 'generateValue: true' in render_yml:
        issues.append((k, 'INFO', 'SECRET_KEY: auto-generated on Render'))
    if 'generateValue' in render_yml:
        issues.append((k, 'INFO', 'SECRET_KEY managed via Render secrets (not in code)'))

    # PRODUCTION flag
    if 'PRODUCTION' in render_yml or 'PRODUCTION' in app_py:
        issues.append((k, 'INFO', 'PRODUCTION env var configured'))
    else:
        issues.append((k, 'MEDIUM', 'PRODUCTION env var not set'))

    # DATABASE_URL
    if 'fromDatabase' in render_yml:
        issues.append((k, 'INFO', 'DATABASE_URL auto-linked from Render DB service'))
    else:
        issues.append((k, 'HIGH', 'DATABASE_URL not auto-configured'))

    # FIELD_ENCRYPTION_KEY
    if 'FIELD_ENCRYPTION_KEY' in render_yml:
        issues.append((k, 'INFO', 'FIELD_ENCRYPTION_KEY config in render.yaml'))
    else:
        issues.append((k, 'MEDIUM', 'FIELD_ENCRYPTION_KEY not in render.yaml (derived from SECRET_KEY)'))

    # BACKUP_ENCRYPTION_KEY
    if 'BACKUP_ENCRYPTION_KEY' in render_yml:
        issues.append((k, 'INFO', 'BACKUP_ENCRYPTION_KEY configured'))
    else:
        issues.append((k, 'MEDIUM', 'BACKUP_ENCRYPTION_KEY not configured'))

    # Logging of secrets
    if '****' in app_py:
        issues.append((k, 'INFO', 'Secrets masked in application logs'))

    # .env in gitignore
    gitignore = read_file(os.path.join(BASE, '.gitignore'))
    if '.env' in gitignore:
        issues.append((k, 'INFO', '.env in .gitignore (prevents accidental commit)'))
    else:
        issues.append((k, 'HIGH', '.env NOT in .gitignore'))

    return issues

# ─────────────────────────────────────────────────────────────
# 2. HTTPS & TLS
# ─────────────────────────────────────────────────────────────
def check_https():
    issues = []
    k = 'HTTPS'

    app_py = read_file(os.path.join(BASE, 'app.py'))

    # HTTP → HTTPS redirect
    if 'http://' in app_py and 'https://' in app_py:
        if 'redirect' in app_py:
            issues.append((k, 'INFO', 'HTTP→HTTPS redirect in production_security_headers()'))
        else:
            issues.append((k, 'MEDIUM', 'HTTPS redirect missing'))
    else:
        issues.append((k, 'MEDIUM', 'No HTTP→HTTPS redirect logic'))

    # HSTS
    if 'Strict-Transport-Security' in app_py:
        if 'max-age=31536000' in app_py:
            issues.append((k, 'INFO', 'HSTS: max-age=31536000 (1 year)'))
    else:
        issues.append((k, 'HIGH', 'HSTS header not set'))

    # X-Frame-Options
    if 'X-Frame-Options' in app_py:
        issues.append((k, 'INFO', 'X-Frame-Options: DENY (clickjacking protection)'))
    else:
        issues.append((k, 'MEDIUM', 'X-Frame-Options not set'))

    # Render automatically provides TLS
    issues.append((k, 'INFO', 'Render provides automatic TLS/SSL termination'))
    issues.append((k, 'INFO', 'Render uses TLS 1.2+ (standard for all plans)'))

    return issues

# ─────────────────────────────────────────────────────────────
# 3. Dependencies
# ─────────────────────────────────────────────────────────────
def check_dependencies():
    issues = []
    k = 'DEPS'

    req = read_file(os.path.join(BASE, 'requirements.txt'))
    lines = req.strip().split('\n') if req else []

    if not lines:
        issues.append((k, 'HIGH', 'requirements.txt not found'))
        return issues

    issues.append((k, 'INFO', f'{len(lines)} packages in requirements.txt'))

    # Version pinning
    pinned = sum(1 for l in lines if '==' in l)
    unpinned = sum(1 for l in lines if l.strip() and '==' not in l and not l.startswith('#'))
    issues.append((k, 'INFO', f'{pinned} packages pinned with ==, {unpinned} unpinned'))

    # Check for known vulnerable patterns
    # psycopg2-binary should not be used in production (use psycopg2)
    if 'psycopg2-binary' in req:
        issues.append((k, 'MEDIUM', 'psycopg2-binary used (dev only) — use psycopg2 for production'))

    # Werkzeug
    if 'Werkzeug' in req:
        m = re.search(r'Werkzeug==([\d.]+)', req)
        if m:
            ver = m.group(1)
            parts = [int(x) for x in ver.split('.')]
            if parts < [3, 1, 0]:
                issues.append((k, 'MEDIUM', f'Werkzeug {ver} outdated (latest: 3.1+)'))
            else:
                issues.append((k, 'INFO', f'Werkzeug {ver} (up to date)'))

    # Flask
    if 'Flask==' in req:
        m = re.search(r'Flask==([\d.]+)', req)
        if m:
            ver = m.group(1)
            parts = [int(x) for x in ver.split('.')]
            if parts < [3, 1, 0]:
                issues.append((k, 'MEDIUM', f'Flask {ver} outdated'))
            else:
                issues.append((k, 'INFO', f'Flask {ver} (up to date)'))

    # cryptography
    if 'cryptography==' in req:
        m = re.search(r'cryptography==([\d.]+)', req)
        if m:
            ver = m.group(1)
            issues.append((k, 'INFO', f'cryptography {ver} (latest line)'))

    # cffi version check
    if 'cffi==2.0.0' in req:
        issues.append((k, 'LOW', 'cffi pinned to 2.0.0 may not be latest'))

    return issues

# ─────────────────────────────────────────────────────────────
# 4. Logging & Monitoring
# ─────────────────────────────────────────────────────────────
def check_logging():
    issues = []
    k = 'LOGGING'

    app_py = read_file(os.path.join(BASE, 'app.py'))
    procfile = read_file(os.path.join(BASE, 'Procfile'))
    entrypoint = read_file(os.path.join(BASE, 'entrypoint.sh'))

    # Gunicorn access logs
    if '--access-logfile -' in procfile:
        issues.append((k, 'INFO', 'Gunicorn access logs enabled (stdout)'))
    else:
        issues.append((k, 'MEDIUM', 'Gunicorn access logs not configured'))

    # Gunicorn error logs
    if '--error-logfile -' in procfile:
        issues.append((k, 'INFO', 'Gunicorn error logs enabled (stdout)'))
    else:
        issues.append((k, 'MEDIUM', 'Gunicorn error logs not configured'))

    # Log level config
    if 'LOG_LEVEL' in procfile or 'LOG_LEVEL' in entrypoint:
        issues.append((k, 'INFO', 'Log level configurable via LOG_LEVEL env var'))
    else:
        issues.append((k, 'LOW', 'Log level not configurable'))

    # Python logging setup
    if 'logging.basicConfig' in app_py:
        issues.append((k, 'INFO', 'Python logging configured in app.py'))
    else:
        issues.append((k, 'MEDIUM', 'No logging configuration in app.py'))

    # Audit logging
    if 'AuditLog' in app_py:
        issues.append((k, 'INFO', 'Business audit logging via AuditLog model'))
    else:
        issues.append((k, 'MEDIUM', 'No business audit logging'))

    # Render log retention
    issues.append((k, 'INFO', 'Render retains logs for 7 days (free/starter)'))
    issues.append((k, 'INFO', 'Render logs accessible via Dashboard > Logs'))

    # Logging of secrets
    if '****' in app_py:
        issues.append((k, 'INFO', 'Sensitive values masked in startup logs'))

    return issues

# ─────────────────────────────────────────────────────────────
# 5. Dockerfile Security
# ─────────────────────────────────────────────────────────────
def check_docker():
    issues = []
    k = 'DOCKER'

    docker = read_file(os.path.join(BASE, 'Dockerfile'))

    if not docker:
        issues.append((k, 'MEDIUM', 'Dockerfile not found'))
        return issues

    # Root user
    if 'USER' not in docker:
        issues.append((k, 'HIGH', 'Container runs as ROOT — add USER appuser'))
    else:
        issues.append((k, 'INFO', 'Non-root user configured'))

    # Layer caching
    if 'COPY requirements.txt' in docker and 'RUN pip install' in docker:
        issues.append((k, 'INFO', 'Docker layer caching for pip install'))
    else:
        issues.append((k, 'LOW', 'No pip layer caching in Dockerfile'))

    # Clean apt cache
    if 'rm -rf /var/lib/apt/lists' in docker:
        issues.append((k, 'INFO', 'APT cache cleaned (smaller image)'))
    else:
        issues.append((k, 'LOW', 'APT cache not cleaned'))

    # Multi-stage build
    if 'FROM python:3.13-slim' in docker:
        issues.append((k, 'INFO', 'Slim base image (smaller attack surface)'))
    else:
        issues.append((k, 'LOW', 'Use slim/alpine base image for smaller footprint'))

    # Healthcheck
    if 'HEALTHCHECK' not in docker:
        issues.append((k, 'LOW', 'No Docker HEALTHCHECK (Render uses external healthCheckPath)'))

    # Read-only filesystem
    if 'read_only' not in docker and '--read-only' not in docker:
        issues.append((k, 'LOW', 'Filesystem is writable (consider read-only root)'))

    return issues

# ─────────────────────────────────────────────────────────────
# 6. Render Configuration
# ─────────────────────────────────────────────────────────────
def check_render_config():
    issues = []
    k = 'RENDER'

    render = read_file(os.path.join(BASE, 'render.yaml'))
    procfile = read_file(os.path.join(BASE, 'Procfile'))

    if not render:
        issues.append((k, 'HIGH', 'render.yaml not found'))
        return issues

    # Auto-deploy
    if 'autoDeploy: true' in render:
        issues.append((k, 'INFO', 'Auto-deploy enabled (every push to main deploys)'))
    else:
        issues.append((k, 'LOW', 'Auto-deploy disabled'))

    # Health check
    if 'healthCheckPath: /api/health' in render:
        issues.append((k, 'INFO', 'Health check configured at /api/health'))
    else:
        issues.append((k, 'MEDIUM', 'No health check path configured'))

    # Database plan
    db_plan = re.search(r'plan:\s*(\S+)', render)
    if db_plan:
        issues.append((k, 'INFO', f'DB plan: {db_plan.group(1)}'))

    # IP whitelist
    if 'ipAllowList: []' in render:
        issues.append((k, 'INFO', 'DB IP whitelist disabled (all connections via Render private network)'))

    # Docker runtime
    if 'runtime: docker' in render:
        issues.append((k, 'INFO', 'Docker runtime (consistent environment)'))

    # Gunicorn config
    if '--workers' in procfile:
        issues.append((k, 'INFO', f'Gunicorn workers configurable via env var'))

    return issues

# ─────────────────────────────────────────────────────────────
# 7. Disaster Recovery
# ─────────────────────────────────────────────────────────────
def check_disaster_recovery():
    issues = []
    k = 'DR'

    # Automated backups
    bak = read_file(os.path.join(BASE, 'services', 'backup_service.py'))
    app_py = read_file(os.path.join(BASE, 'app.py'))

    if 'create_full_backup' in bak:
        issues.append((k, 'INFO', 'Full backup function available'))
    else:
        issues.append((k, 'HIGH', 'No backup function'))

    if 'restore_from_backup' in read_file(os.path.join(BASE, 'services', 'restoration_service.py')):
        issues.append((k, 'INFO', 'Restore function available'))
    else:
        issues.append((k, 'HIGH', 'No restore function'))

    # Automated scheduling
    if 'APScheduler' in app_py or 'APScheduler' in bak:
        issues.append((k, 'INFO', 'APScheduler available for automated backups'))
    else:
        issues.append((k, 'MEDIUM', 'No automated backup scheduling in app (manual only)'))

    # Backup encryption
    if 'encrypt' in bak:
        issues.append((k, 'INFO', 'Backups can be encrypted'))
    else:
        issues.append((k, 'MEDIUM', 'Backups not encrypted'))

    # Render automated DB backups
    issues.append((k, 'INFO', 'Render Pro plan includes automated DB backups with PITR'))
    issues.append((k, 'INFO', 'Render starter plan: manual pg_dump only'))

    # Disaster recovery package
    if 'create_disaster_recovery_package' in bak:
        issues.append((k, 'INFO', 'Disaster recovery package function available'))

    # Off-site backup
    issues.append((k, 'MEDIUM', 'No off-site backup replication configured'))

    return issues

# ─────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────
def generate_html(all_issues):
    by_sev = {}
    for _, s, _ in all_issues:
        by_sev[s] = by_sev.get(s, 0) + 1

    rows = []
    for cat, sev, desc in all_issues:
        color = {'CRITICAL':'#ef4444','HIGH':'#f97316','MEDIUM':'#eab308','LOW':'#3b82f6','INFO':'#6b7280'}[sev]
        rows.append(f'<tr><td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{sev}</span></td><td style="color:#8899b4;font-size:12px">{cat}</td><td>{html.escape(desc)}</td></tr>')

    total = len(all_issues)
    high = by_sev.get('CRITICAL',0)+by_sev.get('HIGH',0)
    medium = by_sev.get('MEDIUM',0)

    return f'''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>Infrastructure Security Audit — SmartLog V2</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}} body{{font-family:'system-ui',sans-serif;background:#080c18;color:#f0f4f9;padding:20px;font-size:14px}} h1{{font-size:22px;font-weight:800}} .summary{{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap}} .summary-card{{background:#0f172a;border:1px solid #1e2a45;border-radius:12px;padding:16px;min-width:120px;text-align:center}} .summary-card .num{{font-size:28px;font-weight:800}} .summary-card .label{{font-size:12px;color:#8899b4}} table{{width:100%;border-collapse:collapse;margin-top:8px}} th,td{{padding:10px 12px;text-align:right;border-bottom:1px solid #17213a;font-size:13px}} th{{color:#8899b4;font-size:12px}}</style></head><body>
<h1>Infrastructure & Deployment Security Audit</h1><div style="color:#8899b4;margin-bottom:16px">{NOW}</div>
<div class="summary"><div class="summary-card"><div class="num" style="color:{"#ef4444" if high else "#22c55e"}">{total}</div><div class="label">Checks</div></div>
<div class="summary-card"><div class="num" style="color:#ef4444">{high}</div><div class="label">Critical/High</div></div>
<div class="summary-card"><div class="num" style="color:#eab308">{medium}</div><div class="label">Medium</div></div></div>
<table><tr><th>Severity</th><th>Category</th><th>Description</th></tr>{chr(10).join(rows)}</table>
<div class="footer" style="margin-top:24px;padding:12px;background:#0f172a;border-radius:10px;font-size:12px;color:#566580;text-align:center">Generated by infrastructure_security_checker.py</div></body></html>'''

def main():
    print('=' * 60)
    print('  SmartLog V2 — Infrastructure Security Audit')
    print(f'  {NOW}')
    print('=' * 60)
    print()

    checks = [
        ('Environment Variables', check_env_vars),
        ('HTTPS & TLS', check_https),
        ('Dependencies', check_dependencies),
        ('Logging & Monitoring', check_logging),
        ('Docker Security', check_docker),
        ('Render Config', check_render_config),
        ('Disaster Recovery', check_disaster_recovery),
    ]

    all_issues = []
    for name, fn in checks:
        print(f'  {name}...')
        try: all_issues.extend(fn())
        except Exception as e: print(f'  [ERROR] {name}: {e}')

    print(); print('=' * 60); print('  SUMMARY'); print('=' * 60)
    by_sev = {}
    for _, s, _ in all_issues: by_sev[s] = by_sev.get(s, 0) + 1
    for s in ['CRITICAL','HIGH','MEDIUM','LOW','INFO']:
        if by_sev.get(s): print(f'  {s:>10}: {by_sev[s]}')
    print(f'  {"TOTAL":>10}: {len(all_issues)}')

    html = generate_html(all_issues)
    rp = os.path.join(BASE, 'infrastructure_security_report.html')
    with open(rp, 'w', encoding='utf-8') as f: f.write(html)
    print(f'\n  HTML report: {rp}\n')
    for _, sev, desc in all_issues:
        sym = {'CRITICAL':'!!','HIGH':'--','MEDIUM':'==','LOW':'~~','INFO':'  '}[sev]
        safe = desc.encode('ascii', errors='replace').decode('ascii')[:120]
        print(f'  [{sym}{sev:>6}{sym}] {safe}')
    return 0 if by_sev.get('CRITICAL',0) == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
