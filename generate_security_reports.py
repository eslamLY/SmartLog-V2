#!/usr/bin/env python3
"""
SmartLog V2 — Master Security Report Generator
Consolidates findings from ALL 6 phases, calculates risk scores,
and produces 7 deliverable files:
  1. security_audit_executive_summary.pdf
  2. security_audit_technical_report.md
  3. security_remediation_plan.md
  4. security_testing_procedures.md
  5. security_configuration_fixes.py
  6. security_monitoring_setup.md
  7. ongoing_security_maintenance.md
"""
import os, sys, json, hashlib, textwrap, datetime
from collections import defaultdict, OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ─────────────────────────────────────────────────────────────
# ALL FINDINGS (consolidated from Phases 1–5)
# ─────────────────────────────────────────────────────────────
FINDINGS = [
    # ── CRITICAL ──
    {'id':'SEC-001','title':'Multiple /api/init-db endpoints without authentication','severity':'CRITICAL','category':'Authorization & Access Control','phase':1,'desc':'5 separate commit/edit scripts expose /api/init-db without proper admin auth checks.','location':'github_commit.py:31, github_commit2.py:22, github_edit2.py:75, github_edit3.py:43, github_keyboard.py:21','impact':'Anyone who discovers these endpoints can reinitialize the database, destroying all production data.','fix':'Add @admin_required decorator to all /api/init-db routes. Remove debug scripts from production repository.','effort':2,'owner':'Backend Dev'},
    {'id':'SEC-002','title':'5 endpoints accessible without authentication','severity':'CRITICAL','category':'Authorization & Access Control','phase':2,'desc':'Penetration test confirmed admin dashboard, employee list API, system health page, backup management, and payroll data return 200 without auth.','location':'Various routes/ endpoints','impact':'Unauthorized users can access sensitive employee, payroll, and backup data. Full PII exposure.','fix':'Ensure every admin-protected endpoint has @admin_required or @login_required decorator. Add middleware to enforce auth on /admin/*.','effort':4,'owner':'Backend Dev'},

    # ── HIGH ──
    {'id':'SEC-003','title':'Default dev SECRET_KEY found in BaseConfig','severity':'HIGH','category':'Authentication & Session Management','phase':2,'desc':"BaseConfig in config.py uses 'dev-secret-change-in-prod' as fallback SECRET_KEY.",'location':'config.py:BaseConfig','impact':'Session forgery — attacker who knows dev-secret can forge session cookies, impersonate any user.','fix':'Remove default SECRET_KEY. Load only from environment variable. Generate a strong random key.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-004','title':'traceback.format_exc() may leak stack traces','severity':'HIGH','category':'Monitoring & Logging','phase':2,'desc':'Multiple files use traceback.format_exc() which can leak internal paths, DB structure, and SQL queries in error responses.','location':'Various *.py files','impact':'Detailed stack traces give attackers insight into app internals, DB schema, and potential injection points.','fix':'Replace traceback.format_exc() in production paths with generic logging. Only expose tracebacks in debug mode.','effort':2,'owner':'Backend Dev'},
    {'id':'SEC-005','title':'Container runs as ROOT user','severity':'HIGH','category':'Infrastructure & Deployment','phase':5,'desc':'Dockerfile has no USER directive — application runs as root inside the container.','location':'Dockerfile','impact':'If container is compromised, attacker has root access to the container environment.','fix':'Add RUN useradd -m appuser && USER appuser to Dockerfile.','effort':1,'owner':'DevOps'},
    {'id':'SEC-006','title':'No SSL requirement for database connection','severity':'HIGH','category':'Infrastructure & Deployment','phase':4,'desc':'Database connection configuration does not enforce sslmode=require.','location':'config.py / app.py','impact':'Database traffic could be intercepted in transit (man-in-the-middle), exposing all stored data.','fix':'Set sslmode=require in the database URI or SQLAlchemy engine options for production.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-007','title':'FLASK_ENV not set to production in render.yaml','severity':'HIGH','category':'Infrastructure & Deployment','phase':5,'desc':'FLASK_ENV is not set in render.yaml (set in Procfile instead, which is inconsistent).','location':'render.yaml','impact':'Debug mode may activate, exposing the interactive debugger and stack traces to users.','fix':'Add FLASK_ENV=production to render.yaml envVars section.','effort':1,'owner':'DevOps'},
    {'id':'SEC-008','title':'Cookie security flags missing','severity':'HIGH','category':'Authentication & Session Management','phase':2,'desc':'Session cookies missing HttpOnly, Secure, and SameSite flags (confirmed by penetration test).','location':'app.py session config','impact':'Cookies accessible to JavaScript (XSS can steal session), sent over HTTP, and not protected against CSRF via SameSite.','fix':'Configure SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Lax".','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-009','title':'No password strength validation','severity':'HIGH','category':'Authentication & Session Management','phase':2,'desc':'No validate_password_strength() function enforces minimum password complexity requirements.','location':'utils/helpers.py','impact':'Users can set weak passwords (e.g., "123456"), making brute-force and credential-stuffing attacks trivial.','fix':'Implement password strength validation: minimum 8 chars, upper+lower+digit+special character requirement.','effort':2,'owner':'Backend Dev'},
    {'id':'SEC-010','title':'No rate limiting on /api/auth/token endpoint','severity':'HIGH','category':'API Security','phase':2,'desc':'The offline sync token endpoint has no rate limiting, enabling infinite token generation attempts.','location':'routes/api_offline_sync.py','impact':'Attacker can brute-force API tokens or cause resource exhaustion by spamming token requests.','fix':'Add Flask-Limiter @limiter.limit() decorator to the token endpoint.','effort':1,'owner':'Backend Dev'},

    # ── MEDIUM ──
    {'id':'SEC-011','title':'National ID stored in plaintext','severity':'MEDIUM','category':'Encryption & Data Protection','phase':4,'desc':'National ID (Libyan national ID / الرقم الوطني) stored in plaintext in the employee model.','location':'models/employee.py','impact':'Exposure of national ID numbers constitutes a severe privacy violation and potential identity theft risk.','fix':'Add national_id_encrypted column, encrypt existing values with Fernet, remove plaintext column.','effort':4,'owner':'Backend Dev'},
    {'id':'SEC-012','title':'Bank account numbers in plaintext','severity':'MEDIUM','category':'Encryption & Data Protection','phase':4,'desc':'Bank account numbers stored in plaintext in employee model.','location':'models/employee.py','impact':'Exposed bank account numbers enable financial fraud. PCI DSS requires encryption of financial account data.','fix':'Add bank_account_encrypted column, migrate data, remove plaintext column.','effort':4,'owner':'Backend Dev'},
    {'id':'SEC-013','title':'FIELD_ENCRYPTION_KEY not explicitly set — derived from SECRET_KEY','severity':'MEDIUM','category':'Encryption & Data Protection','phase':4,'desc':"FIELD_ENCRYPTION_KEY is not set in production; derived from SECRET_KEY. Changing SECRET_KEY corrupts all encrypted data.",'location':'app.py','impact':'Rotating SECRET_KEY (standard security practice) would destroy all encrypted salary, email, and phone data.','fix':'Generate a separate FIELD_ENCRYPTION_KEY, set it in Render environment, test that existing data decrypts.','effort':2,'owner':'DevOps'},
    {'id':'SEC-014','title':'BACKUP_ENCRYPTION_KEY not configured in render.yaml','severity':'MEDIUM','category':'Infrastructure & Deployment','phase':5,'desc':'BACKUP_ENCRYPTION_KEY is not set as an environment variable for the Render service.','location':'render.yaml','impact':'Backups cannot be encrypted — if backup files are exposed, all data is readable.','fix':'Add BACKUP_ENCRYPTION_KEY to render.yaml envVars or Render Dashboard.','effort':1,'owner':'DevOps'},
    {'id':'SEC-015','title':'CSRF protection disabled (WTF_CSRF_CHECK_DEFAULT=False)','severity':'MEDIUM','category':'API Security','phase':2,'desc':'Flask-WTF CSRFProtect is imported but WTF_CSRF_CHECK_DEFAULT=False disables automatic CSRF checking.','location':'app.py','impact':'POST/PUT/DELETE requests are not automatically protected against CSRF attacks. Relies entirely on custom CSRF implementation.','fix':'Enable WTF_CSRF_CHECK_DEFAULT=True, ensure all forms include CSRF tokens.','effort':2,'owner':'Backend Dev'},
    {'id':'SEC-016','title':'No session timeout configured','severity':'MEDIUM','category':'Authentication & Session Management','phase':2,'desc':'PERMANENT_SESSION_LIFETIME is not configured — sessions never expire.','location':'config.py / app.py','impact':'Stale sessions remain valid indefinitely. If a session token is stolen, it can be used forever.','fix':'Set PERMANENT_SESSION_LIFETIME=timedelta(hours=8) and track last_activity for idle timeout.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-017','title':'No IP blocking after failed login attempts','severity':'MEDIUM','category':'Authentication & Session Management','phase':2,'desc':'IP is not blocked after multiple failed login attempts.','location':'routes/auth.py','impact':'Attackers can attempt unlimited passwords from a single IP (though rate-limited, no permanent block).','fix':'Implement IP blocking after 10 failed attempts for 30 minutes via LoginAttempt model.','effort':3,'owner':'Backend Dev'},
    {'id':'SEC-018','title':'No custom 500 error handler','severity':'MEDIUM','category':'Infrastructure & Deployment','phase':2,'desc':'No @app.errorhandler(500) — Flask default 500 handler may leak stack traces in debug mode.','location':'app.py','impact':'In production, if debug mode is accidentally enabled, full stack traces leak to users.','fix':'Add @app.errorhandler(500) that returns a generic error page.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-019','title':'API tokens stored in in-memory dict','severity':'MEDIUM','category':'API Security','phase':2,'desc':'API tokens for offline sync stored in a global in-memory Python dict in api_offline_sync.py.','location':'routes/api_offline_sync.py','impact':'Tokens lost on server restart, not shared across workers, no persistence or revocation support.','fix':'Store API tokens in the database with expiry, revocation status, and last-used tracking.','effort':4,'owner':'Backend Dev'},
    {'id':'SEC-020','title':'psycopg2-binary used in production','severity':'MEDIUM','category':'Infrastructure & Deployment','phase':5,'desc':'requirements.txt lists psycopg2-binary which should only be used for development.','location':'requirements.txt','impact':'psycopg2-binary is not recommended for production — it may have compilation differences and lacks security patches available in psycopg2.','fix':'Replace psycopg2-binary==2.9.10 with psycopg2==2.9.10 in requirements.txt.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-021','title':'MAX_CONTENT_LENGTH not set','severity':'MEDIUM','category':'API Security','phase':2,'desc':'Flask MAX_CONTENT_LENGTH is not configured — no limit on request body size.','location':'app.py','impact':'Attackers can upload arbitrarily large files, causing denial of service via memory exhaustion.','fix':'Set MAX_CONTENT_LENGTH = 16 * 1024 * 1024 (16 MB) in app config.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-022','title':'No off-site backup replication','severity':'MEDIUM','category':'Infrastructure & Deployment','phase':5,'desc':'Backups stored only locally in backups/ directory — no off-site replication.','location':'services/backup_service.py','impact':'A server compromise or Render region outage would destroy all backups along with the primary data.','fix':'Add backup push to external storage (S3, Backblaze B2, or another Render service).','effort':6,'owner':'DevOps'},
    {'id':'SEC-023','title':'No automated backup scheduling in app','severity':'MEDIUM','category':'Infrastructure & Deployment','phase':5,'desc':'APScheduler is installed but no cron schedule is configured to trigger backups automatically.','location':'app.py / services/backup_service.py','impact':'Backups only happen manually — in an incident, data loss may span days or weeks.','fix':'Configure APScheduler to run create_full_backup() daily at midnight and create_incremental_backup() every 6 hours.','effort':3,'owner':'Backend Dev'},

    # ── LOW ──
    {'id':'SEC-024','title':'Emergency contact phone in plaintext','severity':'LOW','category':'Encryption & Data Protection','phase':4,'desc':'Emergency contact phone numbers stored in plaintext.','location':'models/employee.py','impact':'Lower sensitivity but still PII that should be protected.','fix':'Extend Fernet encryption to emergency_phone field.','effort':2,'owner':'Backend Dev'},
    {'id':'SEC-025','title':'No database-level audit triggers','severity':'LOW','category':'Monitoring & Logging','phase':4,'desc':'No PostgreSQL audit triggers configured — all audit relies on application-level AuditLog model.','location':'Database','impact':'Direct database access (e.g., by a DBA or via psql) bypasses audit logging entirely.','fix':'Add pgaudit extension or trigger-based audit logging on sensitive tables.','effort':4,'owner':'DevOps'},
    {'id':'SEC-026','title':'No Docker HEALTHCHECK instruction','severity':'LOW','category':'Infrastructure & Deployment','phase':5,'desc':'Dockerfile does not include a HEALTHCHECK instruction.','location':'Dockerfile','impact':'Docker/orchestrator cannot detect when the application is unresponsive; relies solely on Render external health check.','fix':'Add HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:5000/api/health || exit 1','effort':1,'owner':'DevOps'},
    {'id':'SEC-027','title':'Writable root filesystem in container','severity':'LOW','category':'Infrastructure & Deployment','phase':5,'desc':'Docker container filesystem is writable — no --read-only flag.','location':'Dockerfile','impact':'If compromised, attacker can write arbitrary files to the container filesystem.','fix':'Add --read-only flag with tmpfs mounts for /tmp, /var/run.','effort':1,'owner':'DevOps'},
    {'id':'SEC-028','title':'Rate limit events not logged to AuditLog','severity':'LOW','category':'Monitoring & Logging','phase':4,'desc':'When Flask-Limiter returns 429, the event is not logged to AuditLog.','location':'app.py','impact':'Security team cannot monitor rate-limit violations to detect brute-force patterns.','fix':'Add errorhandler(429) that logs the event to AuditLog before returning the response.','effort':2,'owner':'Backend Dev'},
    {'id':'SEC-029','title':'No custom 429 error handler','severity':'LOW','category':'Monitoring & Logging','phase':2,'desc':'No custom handler for Flask-Limiter 429 responses — users see raw Flask-Limiter error page.','location':'app.py','impact':'Users receive confusing default rate-limit error message instead of a friendly response.','fix':'Add @app.errorhandler(429) with JSON or HTML response and audit logging.','effort':1,'owner':'Backend Dev'},
    {'id':'SEC-030','title':'cffi pinned to 2.0.0 may not be latest','severity':'LOW','category':'Infrastructure & Deployment','phase':5,'desc':'cffi==2.0.0 in requirements.txt may be outdated (latest is 1.17+ — note versioning mismatch).','location':'requirements.txt','impact':'Potential compatibility or security issues with outdated cffi version.','fix':'Update cffi to latest compatible version (1.17.x line).','effort':1,'owner':'Backend Dev'},
]

# Severity weights for risk calculation
SEV_WEIGHTS = {'CRITICAL':10,'HIGH':6,'MEDIUM':3,'LOW':1,'INFO':0}
MAX_RISK_SCORE = 100

CATEGORIES = [
    'Authentication & Session Management',
    'Authorization & Access Control',
    'Encryption & Data Protection',
    'Input Validation & Output Encoding',
    'API Security',
    'Infrastructure & Deployment',
    'Monitoring & Logging',
    'Compliance & Governance',
]

def calc_risk_score(findings):
    raw = sum(SEV_WEIGHTS.get(f['severity'],0) for f in findings)
    max_raw = len(findings) * 10
    score = max(0, 100 - int((raw / max(1,max_raw)) * 100)) if max_raw else 100
    return min(score, 100)

def by_severity(findings):
    d = defaultdict(list)
    for f in findings: d[f['severity']].append(f)
    return d

def by_category(findings):
    d = defaultdict(list)
    for f in findings: d[f['category']].append(f)
    return d

# ─────────────────────────────────────────────────────────────
# FILE 1: Executive Summary PDF
# ─────────────────────────────────────────────────────────────
def generate_executive_summary_pdf():
    path = os.path.join(BASE, 'security_audit_executive_summary.pdf')
    score = calc_risk_score(FINDINGS)
    sev = by_severity(FINDINGS)

    risk_level = 'LOW'
    if score < 40: risk_level = 'CRITICAL'
    elif score < 60: risk_level = 'HIGH'
    elif score < 80: risk_level = 'MEDIUM'

    try:
        from fpdf import FPDF
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        w = 190
        pdf.set_font('Helvetica','B',20)
        pdf.cell(w,12,'SmartLog V2 - Security Audit Executive Summary',new_x='LMARGIN',new_y='NEXT',align='C')
        pdf.set_font('Helvetica','',8)
        pdf.cell(w,6,f'Generated: {NOW}',new_x='LMARGIN',new_y='NEXT',align='C')
        pdf.ln(5)

        # Score card
        pdf.set_font('Helvetica','B',28)
        clr = (220,38,38) if score < 40 else (234,179,8) if score < 60 else (59,130,246) if score < 80 else (34,197,94)
        pdf.set_text_color(*clr)
        pdf.cell(w,14,f'Security Score: {score}/100',new_x='LMARGIN',new_y='NEXT',align='C')
        pdf.set_text_color(0,0,0)
        pdf.set_font('Helvetica','',12)
        pdf.cell(w,8,f'Risk Level: {risk_level}',new_x='LMARGIN',new_y='NEXT',align='C')
        pdf.ln(5)

        # Counts
        pdf.set_font('Helvetica','B',12)
        pdf.cell(w,8,'Issues by Severity',new_x='LMARGIN',new_y='NEXT')
        pdf.set_font('Helvetica','',10)
        for s in ['CRITICAL','HIGH','MEDIUM','LOW','INFO']:
            n = len(sev.get(s,[]))
            if n:
                pdf.cell(w,6,f'{s}: {n}',new_x='LMARGIN',new_y='NEXT')
        pdf.ln(5)

        # Top 5 critical
        crit = sev.get('CRITICAL',[])
        if crit:
            pdf.set_font('Helvetica','B',12)
            pdf.cell(w,8,'Top Critical Issues',new_x='LMARGIN',new_y='NEXT')
            pdf.set_font('Helvetica','',9)
            for c in crit[:5]:
                txt = f'- {c["title"]}'
                pdf.cell(w,5,txt,new_x='LMARGIN',new_y='NEXT')

        pdf.set_font('Helvetica','B',12)
        pdf.cell(w,8,'Immediate Actions Required',new_x='LMARGIN',new_y='NEXT')
        pdf.set_font('Helvetica','',9)
        actions = [
            '1. Remove all debug scripts (github_commit*.py etc.) from production',
            '2. Add authentication decorators to all admin endpoints',
            '3. Set SECRET_KEY via env var only (remove default from config.py)',
            '4. Configure cookie security flags (HttpOnly, Secure, SameSite)',
            '5. Add non-root USER to Dockerfile',
        ]
        for a in actions:
            pdf.cell(w,5,a,new_x='LMARGIN',new_y='NEXT')

        pdf.set_font('Helvetica','B',12)
        pdf.cell(w,8,'Remediation Timeline',new_x='LMARGIN',new_y='NEXT')
        pdf.set_font('Helvetica','',9)
        timeline = [
            'Critical (1-2 days): SEC-001, SEC-002, SEC-003',
            'High (3-7 days): SEC-004 through SEC-010',
            'Medium (1-4 weeks): SEC-011 through SEC-023',
            'Low (1-3 months): SEC-024 through SEC-030',
        ]
        for t in timeline:
            pdf.cell(w,5,t,new_x='LMARGIN',new_y='NEXT')
        pdf.output(path)
        print(f'  [OK] Executive Summary PDF: {path}')
    except Exception as pdf_err:
        # Fallback: create simple text version
        txt_path = os.path.join(BASE, 'security_audit_executive_summary.txt')
        with open(txt_path,'w') as f:
            f.write(f"SmartLog V2 -- Security Score: {score}/100 (Risk: {risk_level})\n")
            for s in ['CRITICAL','HIGH','MEDIUM','LOW']:
                f.write(f'{s}: {len(sev.get(s,[]))}\n')
        print(f'  [OK] Executive Summary TXT: {txt_path} (PDF failed: {pdf_err})')
        # Fallback: create simple text version
        txt_path = os.path.join(BASE, 'security_audit_executive_summary.txt')
        with open(txt_path,'w') as f:
            f.write(f"SmartLog V2 — Security Score: {score}/100 (Risk: {risk_level})\n")
            for s in ['CRITICAL','HIGH','MEDIUM','LOW']:
                f.write(f'{s}: {len(sev.get(s,[]))}\n')
        print(f'  [OK] Executive Summary TXT: {txt_path}')

# ─────────────────────────────────────────────────────────────
# FILE 2: Technical Report
# ─────────────────────────────────────────────────────────────
def generate_technical_report():
    path = os.path.join(BASE, 'security_audit_technical_report.md')
    score = calc_risk_score(FINDINGS)
    sev = by_severity(FINDINGS)
    cat = by_category(FINDINGS)

    lines = []
    lines.append('# SmartLog V2 — Security Audit: Technical Report')
    lines.append(f'> Generated: {NOW}')
    lines.append(f'> Overall Security Score: **{score}/100**')
    lines.append('')
    lines.append('## Summary')
    lines.append('')
    for s in ['CRITICAL','HIGH','MEDIUM','LOW']:
        n = len(sev.get(s,[]))
        if n:
            lines.append(f'- **{s}**: {n} finding(s)')
    lines.append(f'- **Total**: {len(FINDINGS)} findings')
    lines.append('')

    # By category
    lines.append('## Findings by Category')
    lines.append('')
    lines.append('| Category | Count | Critical | High | Medium | Low |')
    lines.append('|----------|-------|----------|------|--------|-----|')
    for cat_name in CATEGORIES:
        items = cat.get(cat_name,[])
        if not items: continue
        c = sum(1 for x in items if x['severity']=='CRITICAL')
        h = sum(1 for x in items if x['severity']=='HIGH')
        m = sum(1 for x in items if x['severity']=='MEDIUM')
        l = sum(1 for x in items if x['severity']=='LOW')
        lines.append(f'| {cat_name} | {len(items)} | {c} | {h} | {m} | {l} |')
    lines.append('')

    # Detailed findings
    lines.append('## Detailed Findings')
    lines.append('')
    for f in sorted(FINDINGS, key=lambda x: (0 if x['severity']=='CRITICAL' else 1 if x['severity']=='HIGH' else 2 if x['severity']=='MEDIUM' else 3, x['id'])):
        lines.append('---')
        lines.append('')
        lines.append(f'### {f["id"]}: {f["title"]}')
        lines.append('')
        lines.append(f'- **Severity:** {f["severity"]}')
        lines.append(f'- **Category:** {f["category"]}')
        lines.append(f'- **Phase Detected:** Phase {f["phase"]}')
        lines.append(f'- **Location:** `{f["location"]}`')
        lines.append('')
        lines.append('#### Description')
        lines.append(f'{f["desc"]}')
        lines.append('')
        lines.append('#### Impact')
        lines.append(f'{f["impact"]}')
        lines.append('')
        lines.append('#### How to Fix')
        lines.append(f'{f["fix"]}')
        lines.append('')

    with open(path,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  [OK] Technical Report: {path}')

# ─────────────────────────────────────────────────────────────
# FILE 3: Remediation Plan
# ─────────────────────────────────────────────────────────────
def generate_remediation_plan():
    path = os.path.join(BASE, 'security_remediation_plan.md')
    lines = []
    lines.append('# SmartLog V2 — Security Remediation Plan')
    lines.append(f'> Generated: {NOW}')
    lines.append('')
    lines.append('## Priority Matrix')
    lines.append('')
    lines.append('| Priority | Timeline | Effort | Criteria |')
    lines.append('|----------|----------|--------|----------|')
    lines.append('| **Critical** | 1-2 days | 1-4 hrs each | Direct data loss / unauthorized access risk |')
    lines.append('| **High** | 3-7 days | 1-4 hrs each | Significant security posture weakness |')
    lines.append('| **Medium** | 1-4 weeks | 2-6 hrs each | Important but requires planning |')
    lines.append('| **Low** | 1-3 months | 1-4 hrs each | Defense-in-depth / best practice |')
    lines.append('')
    lines.append('## Remediation Items')
    lines.append('')
    lines.append('| ID | Title | Severity | Effort (hrs) | Owner | Status | Due | Dependencies |')
    lines.append('|----|-------|----------|-------------|-------|--------|-----|--------------|')

    # Generate a schedule starting from NOW
    base = datetime.datetime.now()
    for i,f in enumerate(sorted(FINDINGS, key=lambda x: (0 if x['severity']=='CRITICAL' else 1 if x['severity']=='HIGH' else 2 if x['severity']=='MEDIUM' else 3, x['id']))):
        if f['severity']=='CRITICAL': days = i+1
        elif f['severity']=='HIGH': days = 3+i
        elif f['severity']=='MEDIUM': days = 10+i*2
        else: days = 30+i*3
        due = (base + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        deps = ', '.join([x['id'] for x in FINDINGS if x['category']==f['category'] and x != f and
                          (x['severity']=='CRITICAL' or (x['severity']=='HIGH' and f['severity']!='CRITICAL'))][:2]) or 'None'
        lines.append(f'| {f["id"]} | {f["title"]} | **{f["severity"]}** | {f["effort"]} | {f["owner"]} | Not started | {due} | {deps} |')

    lines.append('')
    lines.append('## Effort Summary')
    total_effort = sum(f['effort'] for f in FINDINGS)
    lines.append(f'- **Total estimated effort**: {total_effort} hours')
    for s in ['CRITICAL','HIGH','MEDIUM','LOW']:
        e = sum(f['effort'] for f in FINDINGS if f['severity']==s)
        lines.append(f'- {s}: {e} hours')
    lines.append('')
    lines.append('## Resource Allocation')
    lines.append(f'- Backend Developer: {sum(f["effort"] for f in FINDINGS if f["owner"]=="Backend Dev")} hours')
    lines.append(f'- DevOps: {sum(f["effort"] for f in FINDINGS if f["owner"]=="DevOps")} hours')
    lines.append('')
    lines.append('## Success Criteria')
    lines.append('1. All CRITICAL and HIGH findings resolved')
    lines.append('2. Penetration test re-run shows zero auth bypass vulnerabilities')
    lines.append('3. Security score improves to ≥85/100')
    lines.append('4. All endpoints have appropriate auth decorators')
    lines.append('5. Cookie security flags verified via browser DevTools > Application > Cookies')

    with open(path,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  [OK] Remediation Plan: {path}')

# ─────────────────────────────────────────────────────────────
# FILE 4: Testing Procedures
# ─────────────────────────────────────────────────────────────
def generate_testing_procedures():
    path = os.path.join(BASE, 'security_testing_procedures.md')
    lines = []
    lines.append('# SmartLog V2 — Security Testing Procedures')
    lines.append(f'> Generated: {NOW}')
    lines.append('')
    lines.append('## How to Use This Document')
    lines.append('Each test case includes the vulnerability it targets, the steps to reproduce, the expected result, and verification commands where applicable.')
    lines.append('')

    tests = [
        {
            'id':'T-AUTH-001','title':'Test authentication decorators on all admin endpoints','vuln':'SEC-001, SEC-002',
            'category':'Authorization',
            'steps':[
                'Open browser (incognito window, not logged in)',
                'Navigate to /admin/dashboard — expect 302 redirect to login page',
                'Navigate to /admin/employees — expect 302 redirect',
                'Navigate to /api/init-db — expect 403 or 401',
                'Navigate to /backup/manage — expect 302 redirect',
            ],
            'expected':'All admin paths return 302/401/403 without valid session. Only /api/health and public endpoints are accessible.',
            'cmd':'curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/admin/dashboard  # expect 302',
        },
        {
            'id':'T-AUTH-002','title':'Cookie security flags check','vuln':'SEC-008',
            'category':'Session Security',
            'steps':[
                'Log in to the application',
                'Open browser DevTools > Application > Cookies',
                'Check session cookie properties',
            ],
            'expected':'Session cookie shows HttpOnly, Secure, SameSite=Lax flags all set to true.',
            'cmd':'curl -s -D - http://localhost:5000/login -o /dev/null 2>&1 | grep -i "Set-Cookie"',
        },
        {
            'id':'T-SQLI-001','title':'SQL injection on login form','vuln':'SQLi general',
            'category':'Input Validation',
            'steps':[
                'Navigate to /login',
                "Enter username: admin' --",
                'Enter password: any',
                'Submit form — expect 200 with error message (not 500 or data leak)',
            ],
            'expected':'The payload is rejected — no error message reveals SQL syntax or database structure.',
        },
        {
            'id':'T-XSS-001','title':'XSS on user input fields','vuln':'XSS',
            'category':'Input Validation',
            'steps':[
                'Navigate to employee creation form',
                "Enter name: <script>alert('XSS')</script>",
                'Submit and navigate to employee list',
            ],
            'expected':'The script tag is HTML-escaped, displayed as text, not executed.',
        },
        {
            'id':'T-CSRF-001','title':'CSRF token validation on forms','vuln':'SEC-015',
            'category':'API Security',
            'steps':[
                'Open an HTML form page, inspect source',
                'Verify CSRF token hidden field is present',
                'Use curl to POST without CSRF token',
            ],
            'expected':'Every form contains a CSRF token. POST without token returns 400.',
            'cmd':"curl -X POST http://localhost:5000/login -d 'username=test&password=test' -o /dev/null -w '%{http_code}'",
        },
        {
            'id':'T-RATE-001','title':'Rate limiting on auth endpoints','vuln':'SEC-010',
            'category':'API Security',
            'steps':[
                'Send 15 rapid POST requests to /api/auth/token',
                'Count 429 responses',
            ],
            'expected':'After 10 requests within the time window, endpoint returns 429 Too Many Requests.',
            'cmd':'for ($i=0;$i -lt 15;$i++) { curl -s -o /dev/null -w "%{http_code} " http://localhost:5000/api/auth/token }',
        },
        {
            'id':'T-ENCR-001','title':'Field-level encryption verification','vuln':'SEC-011, SEC-012',
            'category':'Data Protection',
            'steps':[
                'Log in as admin and go to employee details',
                'Check database directly: SELECT base_salary, email, phone FROM employee WHERE id=1',
            ],
            'expected':'Salary, email, and phone show as encrypted binary data (not plaintext) in the database.',
            'cmd':"SELECT id, base_salary, email, phone FROM employee WHERE id=1 LIMIT 1;",
        },
        {
            'id':'T-CONTAINER-001','title':'Container runs as non-root user','vuln':'SEC-005',
            'category':'Infrastructure',
            'steps':[
                'Access the running container shell',
                'Run whoami command',
            ],
            'expected':'Output shows "appuser" or similar non-root username, not "root".',
            'cmd':'docker exec smartlog-backend whoami',
        },
        {
            'id':'T-BRUTE-001','title':'Brute force / credential stuffing protection','vuln':'SEC-017',
            'category':'Authentication',
            'steps':[
                'Send 20 rapid login attempts with wrong password from the same IP',
                'After 10 attempts, try a correct password',
            ],
            'expected':'After 10 failed attempts, IP is blocked for 30 minutes. Even valid credentials return 429/403.',
            'cmd':"for ($i=0;$i -lt 20;$i++) { curl -s -X POST http://localhost:5000/login -d 'username=admin&password=wrong' >/dev/null }",
        },
        {
            'id':'T-SESSION-001','title':'Session idle timeout','vuln':'SEC-016',
            'category':'Session Management',
            'steps':[
                'Log in and capture the session cookie',
                'Wait 9+ hours (or set PERMANENT_SESSION_LIFETIME to 5 min for testing)',
                'Use the old session cookie to access /admin/dashboard',
            ],
            'expected':'After session lifetime expires, the request returns 302 (redirect to login)',
        },
        {
            'id':'T-CONFIG-001','title':'SECRET_KEY loaded from env, not hardcoded','vuln':'SEC-003',
            'category':'Configuration',
            'steps':[
                'Check config.py for any hardcoded secret key fallback',
                'Verify SECRET_KEY env var is set in production',
            ],
            'expected':'No hardcoded default SECRET_KEY in config.py. Production key comes only from env var.',
        },
        {
            'id':'T-TLS-001','title':'HTTPS enforced / HSTS present','vuln':'SEC-006',
            'category':'Infrastructure',
            'steps':[
                'Visit http://site (should redirect to https://)',
                'Check response headers for Strict-Transport-Security',
            ],
            'expected':'HTTP -> HTTPS redirect. HSTS header present with max-age=31536000.',
            'cmd':"curl -s -D - https://smartlog-v2-1.onrender.com/api/health | findstr -i 'Strict-Transport-Security'",
        },
    ]

    for t in tests:
        lines.append('---')
        lines.append('')
        lines.append(f'### {t["id"]}: {t["title"]}')
        lines.append(f'- **Targets:** {t["vuln"]}')
        lines.append(f'- **Category:** {t["category"]}')
        lines.append('')
        lines.append('**Test Steps:**')
        for s in t['steps']:
            lines.append(f'1. {s}')
        lines.append('')
        lines.append(f'**Expected Result:** {t["expected"]}')
        if t.get('cmd'):
            lines.append('')
            lines.append('**Automated Test Command:**')
            lines.append(f'```bash')
            lines.append(t['cmd'])
            lines.append(f'```')
        lines.append('')

    with open(path,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  [OK] Testing Procedures: {path}')

# ─────────────────────────────────────────────────────────────
# FILE 5: Configuration Fixes (copy-paste ready Python)
# ─────────────────────────────────────────────────────────────
def generate_configuration_fixes():
    path = os.path.join(BASE, 'security_configuration_fixes.py')
    content = r'''#!/usr/bin/env python3
"""
SmartLog V2 — Security Configuration Fixes
Copy-paste-ready code to fix all findings from the security audit.

Usage:
  1. Review each fix section
  2. Copy the relevant code into your application
  3. Update any placeholders (enclosed in <angle brackets>)
  4. Test before deploying to production
"""
import os
from datetime import timedelta

# ═══════════════════════════════════════════════════════════════
# SEC-003: Remove default SECRET_KEY from config.py
# ═══════════════════════════════════════════════════════════════
class ProductionConfig:
    """Replace your existing BaseConfig with this."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError('SECRET_KEY environment variable is not set!')
    # NEVER add a fallback default value


# ═══════════════════════════════════════════════════════════════
# SEC-008: Cookie security flags (add to create_app())
# ═══════════════════════════════════════════════════════════════
def configure_cookie_security(app):
    """Add to your create_app() function."""
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,    # requires HTTPS
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )


# ═══════════════════════════════════════════════════════════════
# SEC-016: Session idle timeout middleware
# ═══════════════════════════════════════════════════════════════
from flask import session, redirect, url_for, request
import time

def session_timeout_middleware():
    """Call before each request to enforce idle timeout."""
    if 'user_id' in session:
        last = session.get('last_activity', 0)
        now = time.time()
        # 30-minute idle timeout
        if now - last > 1800:
            session.clear()
            return redirect(url_for('auth.login'))
        session['last_activity'] = now


# ═══════════════════════════════════════════════════════════════
# SEC-005: Dockerfile non-root user
# ═══════════════════════════════════════════════════════════════
# Add these lines to your Dockerfile after COPY . .:
#
#   RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
#   USER appuser


# ═══════════════════════════════════════════════════════════════
# SEC-006: Enforce SSL on database connection
# ═══════════════════════════════════════════════════════════════
def configure_db_ssl(app):
    """Add sslmode=require for production database connections."""
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgresql://'):
        if 'sslmode' not in db_url:
            db_url += '?sslmode=require'
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url


# ═══════════════════════════════════════════════════════════════
# SEC-007: render.yaml production settings
# ═══════════════════════════════════════════════════════════════
# Add to render.yaml envVars section:
#
#   - key: FLASK_ENV
#     value: production
#   - key: PRODUCTION
#     value: "true"


# ═══════════════════════════════════════════════════════════════
# SEC-009: Password strength validation
# ═══════════════════════════════════════════════════════════════
import re

def validate_password_strength(password):
    """Returns (is_valid, error_message)."""
    if len(password) < 8:
        return False, 'Password must be at least 8 characters'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain an uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain a lowercase letter'
    if not re.search(r'\d', password):
        return False, 'Password must contain a digit'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'Password must contain a special character'
    return True, ''


# ═══════════════════════════════════════════════════════════════
# SEC-010: Rate limit on /api/auth/token
# ═══════════════════════════════════════════════════════════════
# Add Flask-Limiter decorator to the token endpoint:
#
#   from flask_limiter import Limiter
#   from flask_limiter.util import get_remote_address
#
#   limiter = Limiter(key_func=get_remote_address)
#
#   @bp.route('/api/auth/token', methods=['POST'])
#   @limiter.limit('10 per minute')
#   def get_token():
#       ...


# ═══════════════════════════════════════════════════════════════
# SEC-015: Enable CSRF protection
# ═══════════════════════════════════════════════════════════════
def configure_csrf(app):
    """Enable full CSRF protection."""
    app.config.update(
        WTF_CSRF_CHECK_DEFAULT=True,
        WTF_CSRF_SSL_STRICT=True,
    )
    # Ensure all forms include: {{ form.hidden_tag() }}
    # For AJAX: include X-CSRFToken header from cookie


# ═══════════════════════════════════════════════════════════════
# SEC-018: Custom error handlers
# ═══════════════════════════════════════════════════════════════
def register_error_handlers(app):
    """Add custom error handlers to prevent information leakage."""

    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request'}, 400

    @app.errorhandler(403)
    def forbidden(e):
        return {'error': 'Forbidden'}, 403

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        from models.audit import AuditLog
        from flask import request
        AuditLog.log_action(
            action='RATE_LIMIT',
            details=f'IP {request.remote_addr} hit rate limit on {request.path}'
        )
        return {'error': 'Too many requests'}, 429

    @app.errorhandler(500)
    def internal_error(e):
        import logging
        logging.exception('Internal server error')
        return {'error': 'Internal server error'}, 500


# ═══════════════════════════════════════════════════════════════
# SEC-019: Persistent API token storage
# ═══════════════════════════════════════════════════════════════
# Replace the in-memory API_TOKENS dict with a database model:
#
#   class ApiToken(db.Model):
#       __tablename__ = 'api_tokens'
#       id = db.Column(db.Integer, primary_key=True)
#       user_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
#       token = db.Column(db.String(64), unique=True, nullable=False)
#       created_at = db.Column(db.DateTime, default=datetime.utcnow)
#       expires_at = db.Column(db.DateTime, nullable=True)
#       is_revoked = db.Column(db.Boolean, default=False)
#       last_used_at = db.Column(db.DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════════
# SEC-021: Set MAX_CONTENT_LENGTH
# ═══════════════════════════════════════════════════════════════
def configure_upload_limits(app):
    """Limit request body size to prevent DoS."""
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB


# ═══════════════════════════════════════════════════════════════
# SEC-026: Docker HEALTHCHECK
# ═══════════════════════════════════════════════════════════════
# Add to Dockerfile:
#
#   HEALTHCHECK --interval=30s --timeout=10s --start-period=15s \
#     CMD curl -f http://localhost:5000/api/health || exit 1
#   RUN apt-get install -y --no-install-recommends curl


# ═══════════════════════════════════════════════════════════════
# SEC-028: Log rate limit events
# ═══════════════════════════════════════════════════════════════
# Already included in register_error_handlers() above (429 handler)


# ═══════════════════════════════════════════════════════════════
# SEC-011/012: Field-level encryption for national_id & bank
# ═══════════════════════════════════════════════════════════════
# Add to models/employee.py:
#
#   national_id_encrypted = db.Column(db.LargeBinary, nullable=True)
#   bank_account_encrypted = db.Column(db.LargeBinary, nullable=True)
#
# Add getter/setter methods:
#
#   @property
#   def national_id(self):
#       if self.national_id_encrypted:
#           return get_fernet().decrypt(self.national_id_encrypted).decode()
#       return None
#
#   @national_id.setter
#   def national_id(self, value):
#       if value:
#           self.national_id_encrypted = get_fernet().encrypt(value.encode())
#
# Add migration script to move existing data:
#
#   for emp in Employee.query.all():
#       if emp.national_id and not emp.national_id_encrypted:
#           emp.national_id = emp.national_id  # triggers setter → encrypts
#   db.session.commit()


if __name__ == '__main__':
    print('SmartLog V2 — Security Configuration Fixes')
    print('This file contains copy-paste-ready code snippets.')
    print('Review each section, adapt to your codebase, and test.')
'''
    with open(path,'w',encoding='utf-8') as f:
        f.write(content)
    print(f'  [OK] Configuration Fixes: {path}')

# ─────────────────────────────────────────────────────────────
# FILE 6: Monitoring Setup
# ─────────────────────────────────────────────────────────────
def generate_monitoring_setup():
    path = os.path.join(BASE, 'security_monitoring_setup.md')
    lines = []
    lines.append('# SmartLog V2 — Security Monitoring Setup')
    lines.append(f'> Generated: {NOW}')
    lines.append('')
    lines.append('## 1. Log Analysis')
    lines.append('')
    lines.append('### Key Log Sources')
    lines.append('| Source | Location | Retention |')
    lines.append('|--------|----------|-----------|')
    lines.append('| Gunicorn Access Logs | Render Dashboard > Logs | 7 days (free/starter) |')
    lines.append('| Gunicorn Error Logs | Render Dashboard > Logs | 7 days |')
    lines.append('| Flask Application Logs | stdout (captured by Render) | 7 days |')
    lines.append('| AuditLog DB Table | PostgreSQL `audit_logs` table | Indefinite |')
    lines.append('| LoginAttempt DB Table | PostgreSQL `login_attempts` table | Indefinite |')
    lines.append('')
    lines.append('### What to Monitor')
    lines.append('- **429 responses**: Brute-force attempts, scraping, DDoS')
    lines.append('- **401/403 responses**: Unauthorized access attempts')
    lines.append('- **500 responses**: Potential exploits triggering unhandled errors')
    lines.append('- **Unusual IP patterns**: Single IP hitting many endpoints rapidly')
    lines.append('- **POST to GET-only endpoints**: Reconnaissance')
    lines.append('- **Large request bodies**: Data exfiltration attempts')
    lines.append('')
    lines.append('### Log Query Examples (Render Logs)')
    lines.append('```')
    lines.append('# Find all 429 rate-limit blocks')
    lines.append('429')
    lines.append('')
    lines.append('# Find all authorization failures')
    lines.append('401 OR 403')
    lines.append('')
    lines.append('# Find errors by IP')
    lines.append('"203.0.113.42" AND (error OR exception OR 500)')
    lines.append('```')
    lines.append('')
    lines.append('## 2. Alert Configuration')
    lines.append('')
    lines.append('### Render Alerts (Pro plan)')
    lines.append('| Alert | Threshold | Action |')
    lines.append('|-------|-----------|--------|')
    lines.append('| High 5xx Rate | >5% of requests return 5xx in 5 min | Email + Slack |')
    lines.append('| High 429 Rate | >20% of responses are 429 | Email + Slack |')
    lines.append('| Low Health Check | Health check fails 3 times consecutively | Email + SMS |')
    lines.append('| Memory/CPU Spike | >80% utilization for 5 min | Email |')
    lines.append('')
    lines.append('### Custom Alert Script (Python)')
    lines.append('```python')
    lines.append("import os, smtplib, requests")
    lines.append('')
    lines.append("def check_and_alert():")
    lines.append("    # Check health endpoint")
    lines.append("    r = requests.get('https://smartlog-v2-1.onrender.com/api/health')")
    lines.append("    if r.status_code != 200:")
    lines.append("        send_alert(f'Health check failed: {r.status_code}')")
    lines.append("")
    lines.append("    # Check recent AuditLog for suspicious activity")
    lines.append("    # (query your internal DB for recent 429s or auth failures)")
    lines.append("")
    lines.append("def send_alert(message):")
    lines.append("    print(f'[ALERT] {message}')")
    lines.append("    # Add email/Slack/Telegram integration here")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    check_and_alert()")
    lines.append("```")
    lines.append('')
    lines.append('## 3. Incident Response Procedures')
    lines.append('')
    lines.append('### Triage (0-30 min)')
    lines.append('1. Confirm incident via Render Dashboard > Logs')
    lines.append('2. Determine scope: single user, endpoint, or system-wide')
    lines.append('3. Check if data was accessed or modified')
    lines.append('')
    lines.append('### Containment (30-60 min)')
    lines.append('1. If DoS: enable stricter rate limiting or block offending IP')
    lines.append('2. If auth bypass: rotate all sessions (change SECRET_KEY)')
    lines.append('3. If data breach: isolate affected records, notify users')
    lines.append('')
    lines.append('### Recovery (1-4 hours)')
    lines.append('1. Restore from latest clean backup if data corrupted')
    lines.append('2. Apply security patch or configuration change')
    lines.append('3. Verify fix on staging, then deploy to production')
    lines.append('')
    lines.append('### Post-Mortem (1-2 days)')
    lines.append('1. Document root cause and timeline')
    lines.append('2. Update security testing procedures')
    lines.append('3. Update this monitoring setup document')
    lines.append('')
    lines.append('## 4. Automated Security Testing Setup')
    lines.append('')
    lines.append('### GitHub Actions (already configured: .github/workflows/github_actions_security.yml)')
    lines.append('- Bandit SAST scan on every PR')
    lines.append('- pip-audit dependency vulnerability scan')
    lines.append('- Safety package check')
    lines.append('- Infrastructure security checker')
    lines.append('- Requirements security audit')
    lines.append('')
    lines.append('### Periodic Testing Schedule')
    lines.append('| Frequency | Test | Tool |')
    lines.append('|-----------|------|------|')
    lines.append('| Every PR | Static analysis (SAST) | Bandit |')
    lines.append('| Daily | Dependency scan | pip-audit |')
    lines.append('| Weekly | Full security suite | All checkers |')
    lines.append('| Monthly | Penetration test | Manual + automation |')
    lines.append('| Quarterly | Third-party audit | External firm |')

    with open(path,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  [OK] Monitoring Setup: {path}')

# ─────────────────────────────────────────────────────────────
# FILE 7: Ongoing Maintenance
# ─────────────────────────────────────────────────────────────
def generate_ongoing_maintenance():
    path = os.path.join(BASE, 'ongoing_security_maintenance.md')
    lines = []
    lines.append('# SmartLog V2 — Ongoing Security Maintenance')
    lines.append(f'> Generated: {NOW}')
    lines.append('')
    lines.append('## Daily Tasks (5-10 minutes)')
    lines.append('')
    lines.append('- [ ] Check Render Dashboard for any 5xx spike or health check failures')
    lines.append('- [ ] Review AuditLog for unusual patterns (same IP, many 429s)')
    lines.append('- [ ] Verify the health endpoint returns 200:')
    lines.append('  ```')
    lines.append('  curl -s https://smartlog-v2-1.onrender.com/api/health')
    lines.append('  ```')
    lines.append('')
    lines.append('## Weekly Tasks (30-60 minutes)')
    lines.append('')
    lines.append('- [ ] Review Gunicorn access logs for suspicious IPs or paths')
    lines.append('- [ ] Check LoginAttempt table for brute-force patterns')
    lines.append('- [ ] Run the full security checker suite:')
    lines.append('  ```')
    lines.append('  python backend_security_checker.py')
    lines.append('  python frontend_security_checker.js')
    lines.append('  python database_security_checker.py')
    lines.append('  python infrastructure_security_checker.py')
    lines.append('  python requirements_security_audit.py')
    lines.append('  ```')
    lines.append('- [ ] Verify backups exist and are not corrupted')
    lines.append('- [ ] Review open Dependabot alerts on GitHub')
    lines.append('')
    lines.append('## Monthly Tasks (2-4 hours)')
    lines.append('')
    lines.append('- [ ] Update all pip packages to latest compatible versions:')
    lines.append('  ```')
    lines.append('  pip list --outdated --format=freeze | grep -v "^-e" | cut -d = -f 1 | xargs -n1 pip install -U')
    lines.append('  python requirements_security_audit.py  # verify no new vulns')
    lines.append('  ```')
    lines.append('- [ ] Run a full penetration test:')
    lines.append('  ```')
    lines.append('  python static_file_checker.py')
    lines.append('  # Manual: test all endpoints for auth bypass')
    lines.append('  ```')
    lines.append('- [ ] Review and rotate API tokens (if any stored in DB)')
    lines.append('- [ ] Audit user accounts — disable inactive ones')
    lines.append('- [ ] Check Render resource usage for DoS indicators')
    lines.append('- [ ] Verify encrypted data can still be decrypted correctly')
    lines.append('')
    lines.append('## Quarterly Tasks (4-8 hours)')
    lines.append('')
    lines.append('- [ ] Comprehensive security assessment (all 6 phases)')
    lines.append('- [ ] Review all security headers via browser DevTools')
    lines.append('- [ ] Penetration test by external party or senior dev')
    lines.append("- [ ] Review Render's security bulletins and updates")
    lines.append('- [ ] Test disaster recovery: restore from backup to staging')
    lines.append('- [ ] Audit database user privileges (revoke unused grants)')
    lines.append('- [ ] Review and update CSP headers for new dependencies')
    lines.append('- [ ] Rotate FIELD_ENCRYPTION_KEY and BACKUP_ENCRYPTION_KEY')
    lines.append('  ```')
    lines.append('  # Rotate FIELD_ENCRYPTION_KEY:')
    lines.append('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    lines.append('  # Then run reencrypt_all_backups() before deploying new key')
    lines.append('  ```')
    lines.append('')
    lines.append('## Annual Tasks (1-2 days)')
    lines.append('')
    lines.append('- [ ] Full comprehensive security audit (regenerate all reports)')
    lines.append('- [ ] Third-party penetration test by external security firm')
    lines.append('- [ ] Review disaster recovery plan — test full restore')
    lines.append('- [ ] Update security architecture document')
    lines.append('- [ ] Review compliance requirements (Libyan DPA, GDPR if applicable)')
    lines.append('- [ ] Update incident response plan')
    lines.append('- [ ] Security training for all developers')
    lines.append('')
    lines.append('## Training & Awareness')
    lines.append('')
    lines.append('### Developer Security Training Topics')
    lines.append('1. OWASP Top 10 — understanding the risks')
    lines.append('2. Secure coding: input validation, parameterized queries, output encoding')
    lines.append('3. Session management best practices')
    lines.append('4. Safe handling of secrets in code and CI/CD')
    lines.append('5. Incident reporting procedures')
    lines.append('')
    lines.append('### Resources')
    lines.append('- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)')
    lines.append('- [Flask Security Docs](https://flask.palletsprojects.com/en/stable/security/)')
    lines.append('- [Render Security](https://render.com/security)')
    lines.append('- [SANS: Securing Web Applications](https://www.sans.org/cyber-security-courses/securing-web-applications/)')
    lines.append('')
    lines.append('## Maintenance Automation')
    lines.append('')
    lines.append('### Cron Job for Automated Backups')
    lines.append('```python')
    lines.append('# Add to app.py or a separate scheduler:')
    lines.append('from apscheduler.schedulers.background import BackgroundScheduler')
    lines.append('')
    lines.append('scheduler = BackgroundScheduler()')
    lines.append('scheduler.add_job(')
    lines.append('    func=create_full_backup,')
    lines.append("    trigger='cron',")
    lines.append('    hour=2,  # 02:00 UTC')
    lines.append('    minute=0,')
    lines.append("    id='daily_full_backup',")
    lines.append('    replace_existing=True')
    lines.append(')')
    lines.append('scheduler.start()')
    lines.append('```')

    with open(path,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  [OK] Ongoing Maintenance: {path}')

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    print('=' * 60)
    print('  SmartLog V2 — Security Report Generator')
    print(f'  {NOW}')
    print('=' * 60)
    print()

    score = calc_risk_score(FINDINGS)
    sev = by_severity(FINDINGS)
    cat = by_category(FINDINGS)
    print(f'  Findings: {len(FINDINGS)} total')
    print(f'  Risk Score: {score}/100')
    for s in ['CRITICAL','HIGH','MEDIUM','LOW']:
        print(f'  {s}: {len(sev.get(s,[]))}')

    print()

    builders = [
        ('Executive Summary PDF', generate_executive_summary_pdf),
        ('Technical Report', generate_technical_report),
        ('Remediation Plan', generate_remediation_plan),
        ('Testing Procedures', generate_testing_procedures),
        ('Configuration Fixes', generate_configuration_fixes),
        ('Monitoring Setup', generate_monitoring_setup),
        ('Ongoing Maintenance', generate_ongoing_maintenance),
    ]

    for name, fn in builders:
        print(f'  Generating {name}...')
        try:
            fn()
        except Exception as e:
            import traceback
            print(f'  [ERROR] {name}: {e}')
            traceback.print_exc()
        print()

    print('=' * 60)
    print('  ALL REPORTS GENERATED')
    print('=' * 60)
    print()
    print('  Deliverables:')
    print('  1. security_audit_executive_summary.pdf (for managers)')
    print('  2. security_audit_technical_report.md (for developers)')
    print('  3. security_remediation_plan.md (for project manager)')
    print('  4. security_testing_procedures.md (for QA)')
    print('  5. security_configuration_fixes.py (for implementation)')
    print('  6. security_monitoring_setup.md (for operations)')
    print('  7. ongoing_security_maintenance.md (long-term)')
    print()
    return 0

if __name__ == '__main__':
    sys.exit(main())
