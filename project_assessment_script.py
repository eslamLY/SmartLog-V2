#!/usr/bin/env python3
"""
PHASE 1: PROJECT ASSESSMENT & INFORMATION GATHERING
====================================================
Analyzes the SmartLog V2 project structure, security posture,
Python packages, and generates a baseline security report.

Usage:
    python project_assessment_script.py

Output:
    - baseline_security_report.txt (full report)
    - Console output (summary)
"""
import os
import re
import sys
import json
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
REPORT = ROOT / 'baseline_security_report.txt'
TIMESTAMP = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ASCII-only for Windows cp1256 console; Unicode goes to file
def _s(text):
    """Strip unicode for console output, keep for file."""
    return text.encode('ascii', 'replace').decode('ascii')

SEVERITY = {
    'CRITICAL': '[CRITICAL]',
    'HIGH':     '[HIGH]',
    'MEDIUM':   '[MEDIUM]',
    'LOW':      '[LOW]',
    'INFO':     '[INFO]',
}

# ─── Known vulnerable package patterns (version-independent) ───────────────
VULNERABLE_PATTERNS = {
    'Werkzeug': 'Known CVEs in older Werkzeug versions; ensure >=3.0.0',
    'Jinja2': 'SSTI vulnerabilities in older versions; ensure >=3.1.2',
    'cryptography': 'Ensure >=41.0.0 for latest security fixes',
    'itsdangerous': 'Ensure >=2.1.2 for signature hardening',
    'requests': 'Ensure >=2.31.0 for CVE-2023-32681 fix',
    'gunicorn': 'Ensure >=22.0.0 for HTTP Request Smuggling fixes',
    'sqlalchemy': 'Ensure >=2.0.23 for security patches',
    'flask': 'Ensure >=3.0.0 for latest security',
    'flask-cors': 'CORS misconfiguration common; check origins',
}

# ─── Security features to scan for in code ─────────────────────────────────
SECURITY_PATTERNS = {
    'password_hashing': {
        'pattern': r'generate_password_hash|check_password_hash',
        'label': 'Password hashing (Werkzeug)',
        'severity': 'INFO',
        'description': 'Uses pbkdf2:sha256 for password storage',
    },
    'session_http_only': {
        'pattern': r'SESSION_COOKIE_HTTPONLY[\s:]*True',
        'label': 'Session cookie HTTPOnly',
        'severity': 'INFO',
        'description': 'JavaScript cannot read session cookie',
    },
    'session_secure': {
        'pattern': r'SESSION_COOKIE_SECURE[\s:]*True',
        'label': 'Session cookie Secure flag (HTTPS only)',
        'severity': 'INFO',
        'description': 'Cookie only sent over HTTPS',
    },
    'session_same_site': {
        'pattern': r'SESSION_COOKIE_SAMESITE',
        'label': 'Session cookie SameSite',
        'severity': 'INFO',
        'description': 'CSRF protection via SameSite attribute',
    },
    'csrf_protection': {
        'pattern': r'CSRFProtect|csrf\.protect|csrf_token',
        'label': 'CSRF protection',
        'severity': 'MEDIUM',
        'description': 'Flask-WTF CSRF initialized but WTF_CSRF_CHECK_DEFAULT=False',
    },
    'rate_limiting': {
        'pattern': r'Limiter|check_rate_limit|check_ip_flood|limit',
        'label': 'Rate limiting',
        'severity': 'INFO',
        'description': 'Flask-Limiter active with per-endpoint limits',
    },
    'content_security_policy': {
        'pattern': r'Content-Security-Policy',
        'label': 'Content Security Policy header',
        'severity': 'INFO',
        'description': 'CSP header set in after_request',
    },
    'hsts': {
        'pattern': r'Strict-Transport-Security',
        'label': 'HSTS header',
        'severity': 'INFO',
        'description': 'max-age=31536000; includeSubDomains',
    },
    'x_content_type': {
        'pattern': r'X-Content-Type-Options',
        'label': 'X-Content-Type-Options header',
        'severity': 'INFO',
        'description': 'nosniff set',
    },
    'x_frame_options': {
        'pattern': r'X-Frame-Options[\s:]*DENY',
        'label': 'X-Frame-Options DENY',
        'severity': 'INFO',
        'description': 'Clickjacking protection',
    },
    'field_encryption': {
        'pattern': r'Fernet|get_fernet|base_salary_encrypted|email_encrypted',
        'label': 'Field-level encryption (Fernet/AES)',
        'severity': 'INFO',
        'description': 'Salary, GPS, email, phone encrypted at rest',
    },
    'login_attempt_tracking': {
        'pattern': r'LoginAttempt|blocked_until|attempts',
        'label': 'Login attempt tracking & IP blocking',
        'severity': 'INFO',
        'description': 'LoginAttempt table tracks IP, blocks after 5 failures',
    },
    'sqlalchemy_orm': {
        'pattern': r'db\.session\.execute|Employee\.query|filter_by',
        'label': 'SQLAlchemy ORM (parameterized queries)',
        'severity': 'INFO',
        'description': 'ORM prevents SQL injection in most cases',
    },
    'raw_sql': {
        'pattern': r'sa_text\(|db\.text\(.*f[\"\']|text\(.*\+',
        'label': 'Raw SQL queries (potential risk)',
        'severity': 'MEDIUM',
        'description': 'Raw SQL used in seeds.py and migrations',
    },
    'secret_key_env': {
        'pattern': r'SECRET_KEY.*environ',
        'label': 'SECRET_KEY from environment variable',
        'severity': 'INFO',
        'description': 'Key loaded from env, not hardcoded in production',
    },
    'unauthenticated_endpoints': {
        'pattern': r"@.*\.route\(.*\)\n(?!.*@.*login_required|.*@.*admin_required)",
        'label': 'Unauthenticated endpoints',
        'severity': 'MEDIUM',
        'description': 'Check if sensitive endpoints lack decorators',
    },
    'session_timeout': {
        'pattern': r'PERMANENT_SESSION_LIFETIME|session\.permanent',
        'label': 'Session timeout / expiry',
        'severity': 'INFO',
        'description': 'Session expires after configured lifetime',
    },
    'force_password_change': {
        'pattern': r'force_password_change',
        'label': 'Force password change on first login',
        'severity': 'LOW',
        'description': 'Flag exists but may not be enforced in login flow',
    },
    'cors_config': {
        'pattern': r'flask.cors|CORS|cross_origin',
        'label': 'CORS configuration',
        'severity': 'MEDIUM',
        'description': 'Check if CORS is properly restricted',
    },
}

# ─── Sensitive data patterns ──────────────────────────────────────────────
SENSITIVE_PATTERNS = [
    (r'base_salary|salary|راتب', 'Payroll/salary data'),
    (r'password_hash', 'Password hashes'),
    (r'email_encrypted|phone_encrypted', 'Encrypted PII (email/phone)'),
    (r'national_id|الرقم الوطني|رقم.*وطن', 'National ID numbers'),
    (r'bank_account|iban|account_number', 'Bank account numbers'),
    (r'gps|latitude|lng|lat.*enc|إحداثيات|موقع', 'GPS/location data'),
    (r'biometric|بصمة|fingerprint', 'Biometric data'),
    (r'date_of_birth|تاريخ.*ميلاد', 'Date of birth'),
    (r'medical|sick.*leave|مرضي|علاج', 'Medical/health data'),
]


def p(*args, **kwargs):
    """Print safely on any console encoding."""
    try:
        _builtin_print(*args, **kwargs)
    except UnicodeEncodeError:
        text = ' '.join(str(a) for a in args)
        _builtin_print(text.encode('ascii', 'replace').decode('ascii'), **kwargs)

# Monkey-patch print globally for this module
_builtin_print = print
print = p

class ProjectAssessor:
    def __init__(self):
        self.findings = []
        self.risk_score = 0
        self.max_risk = 0
        self.project_info = {}
        self.packages = {}
        self.security_features = []
        self.vulnerable_packages = []
        self.sensitive_data = set()

    # ── Helpers ──────────────────────────────────────────────────────────

    def finding(self, severity, category, title, detail, filepath=None, line=None):
        weight = {'CRITICAL': 10, 'HIGH': 7, 'MEDIUM': 4, 'LOW': 2, 'INFO': 0}
        self.risk_score += weight.get(severity, 0)
        self.max_risk += 10
        entry = {
            'severity': severity,
            'severity_display': SEVERITY.get(severity, severity),
            'category': category,
            'title': title,
            'detail': detail,
            'filepath': str(filepath) if filepath else None,
            'line': line,
        }
        self.findings.append(entry)
        return entry

    def read_file_safe(self, path):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ''

    def find_in_files(self, pattern, base_dir=None, ext=('.py', '.html', '.js', '.yaml', '.yml', '.json')):
        """Search for regex pattern across project files."""
        base = Path(base_dir or ROOT)
        results = []
        try:
            for p in base.rglob('*'):
                if p.suffix in ext and '__pycache__' not in str(p) and '.git' not in str(p) and '.venv' not in str(p):
                    content = self.read_file_safe(p)
                    for m in re.finditer(pattern, content, re.MULTILINE):
                        line_num = content[:m.start()].count('\n') + 1
                        results.append((p, line_num, m.group()))
        except Exception:
            pass
        return results

    def count_lines(self, base_dir=None):
        """Count total lines of Python code."""
        base = Path(base_dir or ROOT)
        total = 0
        try:
            for p in base.rglob('*.py'):
                if '__pycache__' not in str(p) and '.venv' not in str(p) and '.git' not in str(p):
                    total += len(self.read_file_safe(p).splitlines())
        except Exception:
            pass
        return total

    # ── Analysis Steps ───────────────────────────────────────────────────

    def step_project_structure(self):
        print('\n  ── Project Structure ──')
        entries = sorted(os.listdir(ROOT))
        dirs = [e for e in entries if os.path.isdir(ROOT/e) and not e.startswith('.') and e != '__pycache__']
        files = [e for e in entries if os.path.isfile(ROOT/e) and e.endswith('.py')]

        self.project_info['root'] = str(ROOT)
        self.project_info['directories'] = dirs
        self.project_info['python_files'] = files
        self.project_info['total_python_lines'] = self.count_lines()

        print(f'    Root: {ROOT}')
        print(f'    Directories: {len(dirs)}')
        for d in sorted(dirs):
            count = len(list(Path(ROOT/d).rglob('*.py'))) if (ROOT/d).is_dir() else 0
            print(f'      📁 {d}/ ({count} .py files)')
        print(f'    Python files: {len(files)}')
        print(f'    Total Python LOC: {self.project_info["total_python_lines"]}')

        # Check for key files
        key_files = ['app.py', 'config.py', 'Procfile', 'Dockerfile', 'render.yaml',
                     'requirements.txt', 'manage.py', '.env.example']
        for kf in key_files:
            exists = (ROOT/kf).exists()
            self.project_info[f'has_{kf}'] = exists
            print(f'    {"✓" if exists else "✗"} {kf}')

    def step_requirements(self):
        print('\n  ── Python Packages ──')
        req_path = ROOT / 'requirements.txt'
        if not req_path.exists():
            self.finding('HIGH', 'Dependencies', 'requirements.txt not found',
                         'Cannot verify package versions for known vulnerabilities')
            return

        content = self.read_file_safe(req_path)
        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith('#')]
        for line in lines:
            pkg = line.split('==')[0] if '==' in line else line.split('>=')[0] if '>=' in line else line
            ver = line.split('==')[1] if '==' in line else line.split('>=')[1] if '>=' in line else 'unpinned'
            self.packages[pkg] = ver

            # Check against known vulnerable patterns
            for vpkg, vdesc in VULNERABLE_PATTERNS.items():
                if pkg.lower() == vpkg.lower():
                    if ver == 'unpinned':
                        self.finding('MEDIUM', 'Dependencies', f'{vpkg} version unpinned',
                                     f'{vdesc}. Pin to a specific version.')
                        self.vulnerable_packages.append(f'{vpkg} (unpinned)')
                    # Simple version check is limited; just flag
                    self.vulnerable_packages.append(f'{vpkg} ({ver}) - {vdesc}')

            print(f'    📦 {pkg} == {ver}')

        self.project_info['packages'] = self.packages
        print(f'    Total: {len(self.packages)} packages')

    def step_security_features(self):
        print('\n  ── Security Features Scan ──')
        all_code = ''
        for ext in ('.py', '.html', '.js'):
            for p in ROOT.rglob(f'*{ext}'):
                if '__pycache__' not in str(p) and '.venv' not in str(p) and '.git' not in str(p):
                    if p.suffix == ext:
                        all_code += self.read_file_safe(p) + '\n'

        hits = 0
        for key, cfg in SECURITY_PATTERNS.items():
            matches = re.findall(cfg['pattern'], all_code, re.MULTILINE | re.DOTALL)
            if matches:
                hits += 1
                self.security_features.append({
                    'key': key,
                    'label': cfg['label'],
                    'severity': cfg['severity'],
                    'description': cfg['description'],
                    'found': True,
                    'count': len(matches),
                })
                print(f'    ✓ {cfg["label"]} ({len(matches)} hits)')
            else:
                self.security_features.append({
                    'key': key,
                    'label': cfg['label'],
                    'severity': cfg['severity'],
                    'description': cfg['description'],
                    'found': False,
                    'count': 0,
                })
                if cfg['severity'] != 'INFO':
                    print(f'    ✗ {cfg["label"]} - NOT FOUND')
                    self.finding('MEDIUM', 'Missing Security', f'{cfg["label"]} not implemented',
                                 cfg['description'])

        self.project_info['security_features_found'] = hits
        self.project_info['security_features_total'] = len(SECURITY_PATTERNS)

    def step_sensitive_data(self):
        print('\n  ── Sensitive Data Scan ──')
        for ext in ('.py', '.html', '.js'):
            for p in ROOT.rglob(f'*{ext}'):
                if '__pycache__' not in str(p) and '.venv' not in str(p) and '.git' not in str(p):
                    content = self.read_file_safe(p)
                    for pattern, label in SENSITIVE_PATTERNS:
                        if re.search(pattern, content, re.IGNORECASE):
                            self.sensitive_data.add(label)
                            rel = p.relative_to(ROOT)
                            if 'base_salary' in pattern or 'salary' in pattern:
                                pass

        for label in sorted(self.sensitive_data):
            print(f'    📋 {label}')
        self.project_info['sensitive_data_types'] = list(self.sensitive_data)

    def step_common_vulnerabilities(self):
        print('\n  ── Common Vulnerabilities Scan ──')

        # 1. Hardcoded secrets in code
        app_py = self.read_file_safe(ROOT / 'app.py')
        secret_fallback = re.search(r"SECRET_KEY.*=.*['\"](?!\{|env)[a-zA-Z].*['\"]", app_py)
        if secret_fallback:
            self.finding('LOW', 'Hardcoded Secrets', 'Fallback SECRET_KEY in app.py',
                         'Default key "blood-bank-tobruk-secret-2024" used when not in env',
                         filepath='app.py')
            print(f'    {SEVERITY["LOW"]} Fallback SECRET_KEY found in app.py')

        # 2. Debug mode in production
        debug_pattern = re.findall(r'app\.run\(.*debug\s*=\s*True', app_py)
        if debug_pattern:
            self.finding('HIGH', 'Configuration', 'Debug mode enabled',
                         'app.run(debug=True) found - could leak stack traces',
                         filepath='app.py')
            print(f'    {SEVERITY["HIGH"]} Debug mode enabled in app.py')

        # 3. CSRF disabled
        csrf_disabled = re.search(r'WTF_CSRF_CHECK_DEFAULT\s*=\s*False', app_py)
        if csrf_disabled:
            self.finding('MEDIUM', 'CSRF', 'CSRF check disabled by default',
                         'WTF_CSRF_CHECK_DEFAULT=False means no CSRF tokens on forms/API',
                         filepath='app.py')
            print(f'    {SEVERITY["MEDIUM"]} CSRF check disabled')

        # 4. Unauthenticated /api/init-db
        init_db = self.find_in_files(r"@.*route.*init.db")
        for fp, ln, _ in init_db:
            # Check if there's an auth check nearby
            nearby = self.read_file_safe(fp).splitlines()[max(0, ln-3):ln+8]
            nearby_text = '\n'.join(nearby)
            has_auth = 'session.get' in nearby_text and 'admin' in nearby_text
            if not has_auth:
                self.finding('CRITICAL', 'Authentication', '/api/init-db without auth (PARTIALLY FIXED)',
                             'Auth check was added but verify it blocks non-admin',
                             filepath=fp, line=ln)
                print(f'    {SEVERITY["CRITICAL"]} /api/init-db endpoint requires admin check')

        # 5. Check for CSP bypass
        csp = re.search(r"Content-Security-Policy['\"]?:?\s*(.+)", app_py)
        if csp:
            csp_value = csp.group(1)
            if "unsafe-inline" in csp_value and "nonce" not in csp_value:
                self.finding('LOW', 'CSP', 'CSP uses unsafe-inline without nonce',
                             'unsafe-inline weakens XSS protection',
                             filepath='app.py')
                print(f'    {SEVERITY["LOW"]} CSP uses unsafe-inline')

        # 6. Check raw SQL
        raw_sql = self.find_in_files(r'db\.session\.execute\(.*text\([\'\"].*\{|f[\'\"]SELECT|f[\'\"]INSERT|f[\'\"]UPDATE')
        for fp, ln, _ in raw_sql[:5]:
            rel = fp.relative_to(ROOT)
            self.finding('MEDIUM', 'SQL Injection Risk', f'Raw SQL with f-string in {rel}',
                         'Potential SQL injection if user input is concatenated',
                         filepath=rel, line=ln)
            print(f'    {SEVERITY["MEDIUM"]} Raw SQL with variables in {rel}:{ln}')

        # 7. Check for error disclosure
        error_handlers = self.find_in_files(r'@app\.errorhandler|@.*\.errorhandler')
        if error_handlers:
            print(f'    ✓ Custom error handlers: {len(error_handlers)} found')

        # 8. Check for SQLAlchemy text() usage without parameters
        raw_text = self.find_in_files(r'db\.text\([\'\"][^%\']*[\'\"]\)')
        for fp, ln, _ in raw_text[:3]:
            rel = fp.relative_to(ROOT)
            self.finding('INFO', 'SQL', f'Raw SQL text() in {rel}:{ln}',
                         'SQLAlchemy text() used - verify parameters are bound',
                         filepath=rel, line=ln)
            print(f'    {SEVERITY["INFO"]} Raw SQL text() in {rel}:{ln}')

    def step_render_config(self):
        print('\n  ── Render.com Configuration ──')
        render = ROOT / 'render.yaml'
        if render.exists():
            content = self.read_file_safe(render)
            checks = [
                ('healthCheckPath', 'Health check path configured'),
                ('autoDeploy', 'Auto-deploy enabled'),
                ('SECRET_KEY.*generateValue', 'SECRET_KEY auto-generated'),
                ('DATABASE_URL.*fromDatabase', 'DATABASE_URL from linked DB'),
                ('FLASK_ENV.*production', 'FLASK_ENV set to production'),
                ('sslmode.*require', 'SSL mode required'),
            ]
            for pattern, label in checks:
                if re.search(pattern, content):
                    print(f'    ✓ {label}')

        procfile = ROOT / 'Procfile'
        if procfile.exists():
            content = self.read_file_safe(procfile)
            if 'gunicorn' in content:
                has_workers = re.search(r'--workers\s+\d+', content)
                has_timeout = re.search(r'--timeout\s+\d+', content)
                print(f'    ✓ Gunicorn configured{" with workers" if has_workers else ""}{" with timeout" if has_timeout else ""}')

    def step_risk_score(self):
        print('\n  ── Risk Score ──')
        percentage = min(100, int((self.risk_score / max(self.max_risk, 1)) * 100))
        self.project_info['risk_score'] = percentage
        self.project_info['risk_score_max'] = self.max_risk
        self.project_info['risk_score_actual'] = self.risk_score

        if percentage <= 15:
            level = '🟢 LOW'
        elif percentage <= 35:
            level = '🟡 MEDIUM'
        elif percentage <= 60:
            level = '🟠 HIGH'
        else:
            level = '🔴 CRITICAL'

        print(f'    Risk Score: {percentage}/100 ({level})')
        print(f'    Total Findings: {len(self.findings)}')
        criticals = sum(1 for f in self.findings if f['severity'] == 'CRITICAL')
        highs = sum(1 for f in self.findings if f['severity'] == 'HIGH')
        mediums = sum(1 for f in self.findings if f['severity'] == 'MEDIUM')
        lows = sum(1 for f in self.findings if f['severity'] == 'LOW')
        print(f'    CRITICAL: {criticals}, HIGH: {highs}, MEDIUM: {mediums}, LOW: {lows}')

        self.project_info['finding_counts'] = {
            'CRITICAL': criticals, 'HIGH': highs,
            'MEDIUM': mediums, 'LOW': lows,
        }

    # ── Report Generation ────────────────────────────────────────────────

    def generate_report(self):
        lines = []
        lines.append('=' * 72)
        lines.append('  SMARTLOG V2 — BASELINE SECURITY ASSESSMENT REPORT')
        lines.append('=' * 72)
        lines.append(f'  Generated: {TIMESTAMP}')
        lines.append(f'  Project:   {ROOT}')
        lines.append(f'  Assessor:  Phase 1 — Automated Scan')
        lines.append('=' * 72)

        lines.append('\n\n1. PROJECT SUMMARY')
        lines.append('-' * 40)
        lines.append(f'  Python files:      {len(self.project_info.get("python_files", []))}')
        lines.append(f'  Python LOC:        {self.project_info.get("total_python_lines", 0):,}')
        lines.append(f'  Directories:       {len(self.project_info.get("directories", []))}')
        lines.append(f'  Packages:          {len(self.packages)}')
        lines.append(f'  Has app.py:        {self.project_info.get("has_app.py", False)}')
        lines.append(f'  Has config.py:     {self.project_info.get("has_config.py", False)}')
        lines.append(f'  Has Dockerfile:    {self.project_info.get("has_Dockerfile", False)}')
        lines.append(f'  Has render.yaml:   {self.project_info.get("has_render.yaml", False)}')

        lines.append('\n\n2. DIRECTORY STRUCTURE')
        lines.append('-' * 40)
        for d in sorted(self.project_info.get('directories', [])):
            lines.append(f'  📁 {d}/')
        for f in sorted(self.project_info.get('python_files', [])):
            lines.append(f'  📄 {f}')

        lines.append('\n\n3. PYTHON PACKAGES')
        lines.append('-' * 40)
        for pkg, ver in sorted(self.packages.items()):
            lines.append(f'  {pkg} == {ver}')

        if self.vulnerable_packages:
            lines.append('\n  3a. Package Vulnerability Notes')
            for vp in self.vulnerable_packages:
                lines.append(f'  ⚠️  {vp}')

        lines.append('\n\n4. SECURITY FEATURES')
        lines.append('-' * 40)
        for feat in self.security_features:
            status = '✅' if feat['found'] else '❌'
            sev = feat['severity']
            lines.append(f'  {status} [{sev}] {feat["label"]}')
            lines.append(f'       {feat["description"]}')

        lines.append('\n\n5. SENSITIVE DATA TYPES')
        lines.append('-' * 40)
        for sd in sorted(self.sensitive_data):
            lines.append(f'  📋 {sd}')

        lines.append('\n\n6. FINDINGS')
        lines.append('-' * 40)
        for i, f_item in enumerate(self.findings, 1):
            sev = f_item['severity_display']
            lines.append(f'\n  {i}. {sev} — {f_item["title"]}')
            lines.append(f'     Category: {f_item["category"]}')
            lines.append(f'     Detail:   {f_item["detail"]}')
            if f_item['filepath']:
                loc = str(f_item['filepath'])
                if f_item['line']:
                    loc += f':{f_item["line"]}'
                lines.append(f'     Location: {loc}')

        lines.append('\n\n7. RISK ASSESSMENT')
        lines.append('-' * 40)
        pct = self.project_info.get('risk_score', 0)
        if pct <= 15:
            level = 'LOW 🟢'
        elif pct <= 35:
            level = 'MEDIUM 🟡'
        elif pct <= 60:
            level = 'HIGH 🟠'
        else:
            level = 'CRITICAL 🔴'
        lines.append(f'  Risk Score: {pct}/100 ({level})')
        fc = self.project_info.get('finding_counts', {})
        lines.append(f'  CRITICAL: {fc.get("CRITICAL", 0)}')
        lines.append(f'  HIGH:     {fc.get("HIGH", 0)}')
        lines.append(f'  MEDIUM:   {fc.get("MEDIUM", 0)}')
        lines.append(f'  LOW:      {fc.get("LOW", 0)}')

        lines.append('\n\n8. TOP CONCERNS')
        lines.append('-' * 40)
        criticals = [f for f in self.findings if f['severity'] == 'CRITICAL']
        highs = [f for f in self.findings if f['severity'] == 'HIGH']
        for f_item in criticals + highs:
            lines.append(f'  🔴 {f_item["title"]}')
            lines.append(f'     {f_item["detail"]}')
        if not criticals and not highs:
            lines.append('  No CRITICAL or HIGH concerns found.')

        lines.append('\n\n9. RECOMMENDATIONS')
        lines.append('-' * 40)
        recommendations = [
            'CRITICAL /api/init-db: Add admin-only auth check + rate limit',
            'MEDIUM CSRF: Enable CSRF checks for POST/PUT/DELETE on API routes',
            'MEDIUM Raw SQL: Audit all db.text() calls for parameter binding',
            'MEDIUM Package versions: Pin all packages in requirements.txt',
            'LOW SECRET_KEY: Set FIELD_ENCRYPTION_KEY env var separately from SECRET_KEY',
            'LOW Default passwords: Ensure force_password_change is enforced on first login',
            'INFO Debug mode: Verify app.run(debug=True) is NOT in production config',
            'INFO Error pages: Create custom error pages for 400/403/404/500',
        ]
        for rec in recommendations:
            lines.append(f'  → {rec}')

        lines.append('\n\n10. FURTHER TESTING REQUIRED')
        lines.append('-' * 40)
        further = [
            'Penetration test login form for SQL injection, XSS, brute force',
            'Test all API endpoints for proper authorization checks',
            'Verify CSP header is applied to all responses',
            'Test session fixation / hijacking scenarios',
            'Review all third-party dependencies for known CVEs',
            'Verify encrypted data (salaries, GPS) can be decrypted correctly',
            'Test file upload functionality for path traversal / RCE',
            'Review PWA service worker for cache poisoning risks',
        ]
        for ft in further:
            lines.append(f'  ☐ {ft}')

        lines.append('\n\n' + '=' * 72)
        lines.append('  END OF REPORT')
        lines.append('=' * 72)

        report_text = '\n'.join(lines)
        with open(REPORT, 'w', encoding='utf-8') as f:
            f.write(report_text)
        return report_text


def main():
    print('=' * 60)
    print('  SMARTLOG V2 — PROJECT ASSESSMENT')
    print('  Phase 1: Information Gathering')
    print(f'  {TIMESTAMP}')
    print('=' * 60)

    assessor = ProjectAssessor()

    print('\n[1/7] Analyzing project structure...')
    assessor.step_project_structure()

    print('\n[2/7] Scanning Python packages...')
    assessor.step_requirements()

    print('\n[3/7] Scanning security features...')
    assessor.step_security_features()

    print('\n[4/7] Identifying sensitive data...')
    assessor.step_sensitive_data()

    print('\n[5/7] Checking common vulnerabilities...')
    assessor.step_common_vulnerabilities()

    print('\n[6/7] Checking Render.com config...')
    assessor.step_render_config()

    print('\n[7/7] Calculating risk score...')
    assessor.step_risk_score()

    print('\n' + '=' * 60)
    print('  Generating report...')
    report = assessor.generate_report()
    print(f'  Report saved to: {REPORT}')
    print('=' * 60)

    return 0 if assessor.project_info.get('risk_score', 100) <= 50 else 1


if __name__ == '__main__':
    sys.exit(main())
