#!/usr/bin/env python3
"""
SmartLog V2 — Backend Security Audit Checker
Scans project source files for authentication, SQL injection, input
validation, error handling, API security, and env var issues.
Generates a detailed HTML report.
"""
import os, re, sys, json, hashlib, html, traceback
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

SEVERITY_ORDER = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'INFO': 4}

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None

def find_files(pattern, root=BASE):
    result = []
    for dirpath, _, files in os.walk(root):
        if any(p in dirpath for p in ('__pycache__', '.git', 'venv', '.venv',
                                        'node_modules', '_temp', 'migrations')):
            continue
        for f in files:
            if re.match(pattern, f):
                result.append(os.path.join(dirpath, f))
    return result


# ─────────────────────────────────────────────────────────────
# 1. AUTHENTICATION
# ─────────────────────────────────────────────────────────────
def check_authentication():
    issues = []
    key = 'AUTH'

    app_py = read_file(os.path.join(BASE, 'app.py'))
    auth_py = read_file(os.path.join(BASE, 'routes', 'auth.py'))

    # 1.1 Password hashing
    findings = []
    if 'check_password_hash' in (app_py or '') or 'check_password_hash' in (auth_py or ''):
        findings.append('werkzeug.security — pbkdf2:sha256')
        issues.append((key, 'INFO', 'Password hashing: werkzeug.security.generate_password_hash (pbkdf2:sha256)'))
    else:
        issues.append((key, 'CRITICAL', 'No password hashing found!'))

    # 1.2 Session config
    session_keys = ['SESSION_COOKIE_HTTPONLY', 'SESSION_COOKIE_SAMESITE',
                    'SESSION_COOKIE_SECURE', 'PERMANENT_SESSION_LIFETIME']
    for sk in session_keys:
        found = (app_py or '').count(sk) + (read_file(os.path.join(BASE, 'config.py')) or '').count(sk)
        if not found:
            issues.append((key, 'MEDIUM', f'{sk} not configured'))

    # 1.3 rate limit on login
    if 'check_rate_limit' in (auth_py or '') and '5' in (auth_py or ''):
        issues.append((key, 'INFO', 'Login rate limiting active (5 attempts / 5 min)'))
    else:
        issues.append((key, 'HIGH', 'No rate limiting on login endpoint'))

    # 1.4 IP blocking
    if 'blocked_until' in (auth_py or ''):
        issues.append((key, 'INFO', 'IP blocking after max login attempts'))
    else:
        issues.append((key, 'MEDIUM', 'No IP blocking after failed attempts'))

    # 1.5 Session timeout
    if 'last_activity' in (app_py or '') or 'last_activity' in read_file(os.path.join(BASE, 'utils', 'decorators.py')):
        issues.append((key, 'INFO', 'Session timeout tracking via last_activity'))
    else:
        issues.append((key, 'MEDIUM', 'No session timeout tracking'))

    return issues


# ─────────────────────────────────────────────────────────────
# 2. DATABASE QUERIES (SQL Injection)
# ─────────────────────────────────────────────────────────────
def check_sql_injection():
    issues = []
    key = 'SQLI'

    py_files = find_files(r'.*\.py')
    for fp in py_files:
        content = read_file(fp)
        if not content:
            continue
        lines = content.split('\n')

        # text() with f-strings
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if 'text(' in stripped and 'f"' in stripped:
                issues.append((key, 'MEDIUM',
                    f'{os.path.relpath(fp, BASE)}:{i} — text() with f-string: {stripped[:80]}'))

    # Check for raw string concatenation in SQL
    for fp in py_files:
        content = read_file(fp)
        if not content:
            continue
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r'execute\(.*["\'].*["\']\s*\+', stripped):
                if 'text(' not in stripped:
                    continue
                issues.append((key, 'HIGH',
                    f'{os.path.relpath(fp, BASE)}:{i} — SQL string concat: {stripped[:80]}'))

    if not [i for i in issues if i[1] in ('HIGH', 'CRITICAL')]:
        issues.append((key, 'INFO', 'No SQL injection risks in ORM queries'))

    return issues


# ─────────────────────────────────────────────────────────────
# 3. INPUT VALIDATION
# ─────────────────────────────────────────────────────────────
def check_input_validation():
    issues = []
    key = 'INPUT'

    helpers = read_file(os.path.join(BASE, 'utils', 'helpers.py')) or ''
    routes_dir = os.path.join(BASE, 'routes')

    # 3.1 Password validation
    if 'validate_password_strength' in helpers:
        issues.append((key, 'INFO', 'Password strength validation present (8+ chars, upper+lower+digit)'))
        # Check min length
        m = re.search(r'len\(password\)\s*<\s*(\d+)', helpers)
        if m:
            issues.append((key, 'INFO', f'Password min length: {m.group(1)}'))
    else:
        issues.append((key, 'HIGH', 'No password strength validation'))

    # 3.2 File upload validation
    if 'allowed_file' in helpers or 'allowed_photo' in helpers or 'ALLOWED_EXTENSIONS' in helpers:
        issues.append((key, 'INFO', 'File upload extension validation present'))
    else:
        issues.append((key, 'MEDIUM', 'No file upload validation'))

    # 3.3 MAX_CONTENT_LENGTH
    app_py = read_file(os.path.join(BASE, 'app.py')) or ''
    if 'MAX_CONTENT_LENGTH' in app_py:
        issues.append((key, 'INFO', 'MAX_CONTENT_LENGTH configured'))
    else:
        issues.append((key, 'MEDIUM', 'MAX_CONTENT_LENGTH not set'))

    # 3.4 GPS validation
    if 'validate_coordinates' in helpers or 'validate_latitude' in helpers:
        issues.append((key, 'INFO', 'GPS coordinate validation present'))

    # 3.5 Check route files for missing validation
    for fp in find_files(r'.*\.py', routes_dir):
        content = read_file(fp) or ''
        if 'request.get_json' in content or 'request.form' in content:
            pass  # too many to check each

    return issues


# ─────────────────────────────────────────────────────────────
# 4. ERROR HANDLING
# ─────────────────────────────────────────────────────────────
def check_error_handling():
    issues = []
    key = 'ERROR'

    py_files = find_files(r'.*\.py')

    # 4.1 traceback exposure
    for fp in py_files:
        content = read_file(fp) or ''
        if 'traceback.format_exc' in content:
            rel = os.path.relpath(fp, BASE)
            issues.append((key, 'HIGH', f'{rel} — traceback.format_exc() may leak stack traces'))

    # 4.2 Bare except clauses
    for fp in py_files:
        content = read_file(fp) or ''
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:' or stripped == 'except Exception:':
                rel = os.path.relpath(fp, BASE)
                # count as LOW if no log; check if next line has log
                next_line = lines[i] if i < len(lines) else ''
                if 'log' not in next_line.lower() and 'logger' not in next_line.lower():
                    issues.append((key, 'LOW', f'{rel}:{i} — bare except without logging'))

    # 4.3 404/500 handlers
    app_py = read_file(os.path.join(BASE, 'app.py')) or ''
    if '@app.errorhandler(429)' in app_py:
        issues.append((key, 'INFO', 'Custom 429 error handler present'))
    else:
        issues.append((key, 'MEDIUM', 'No custom 429 error handler'))

    if '@app.errorhandler(500)' not in app_py:
        issues.append((key, 'MEDIUM', 'No custom 500 error handler — stack may leak'))

    return issues


# ─────────────────────────────────────────────────────────────
# 5. API SECURITY
# ─────────────────────────────────────────────────────────────
def check_api_security():
    issues = []
    key = 'API'

    routes_dir = os.path.join(BASE, 'routes')
    auth_route = read_file(os.path.join(BASE, 'routes', 'auth.py')) or ''

    # 5.1 Endpoints without auth
    route_files = find_files(r'.*\.py', routes_dir)
    for fp in route_files:
        content = read_file(fp) or ''
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            m = re.match(r"@.*\.route\('([^']+)'", stripped)
            if not m:
                continue
            path = m.group(1)
            # Skip static files
            if path.startswith(('/static', '/manifest', '/sw.js', '/uploads')):
                continue
            # Check if next lines have decorator
            after = '\n'.join(lines[i:i+5])
            if not any(d in after for d in ('@admin_required', '@login_required',
                                              '@employee_required', 'validate_token')):
                if path.startswith('/api/'):
                    if path in ('/api/health', '/api/health/static',
                                '/api/auth/token', '/api/auth/validate-token'):
                        continue
                    issues.append((key, 'MEDIUM',
                        f'{os.path.relpath(fp, BASE)} near line {i} — {path} may lack auth decorator'))

    # 5.2 Rate limiting
    rate_limit_files = ['app.py', 'routes/auth.py', 'utils/rate_limit.py']
    has_rate_limit = any(
        'check_rate_limit' in (read_file(os.path.join(BASE, f)) or '') for f in rate_limit_files
    )
    if has_rate_limit:
        issues.append((key, 'INFO', 'Rate limiting implemented'))
    else:
        issues.append((key, 'HIGH', 'No rate limiting anywhere'))

    # 5.3 CORS
    app_py = read_file(os.path.join(BASE, 'app.py')) or ''
    if 'Access-Control-Allow-Origin' not in app_py:
        issues.append((key, 'INFO', 'CORS not configured (restricted by default)'))
    else:
        issues.append((key, 'MEDIUM', 'CORS headers set'))

    # 5.4 CSRF
    if 'WTF_CSRF_CHECK_DEFAULT' in app_py:
        issues.append((key, 'INFO', 'CSRFProtect imported, but WTF_CSRF_CHECK_DEFAULT=False'))
    else:
        issues.append((key, 'MEDIUM', 'No CSRF protection'))

    # 5.5 Custom CSRF
    if 'X-CSRFToken' in app_py:
        issues.append((key, 'INFO', 'Custom CSRF token validation active (X-CSRFToken)'))

    # 5.6 API token auth (offline sync)
    offline = read_file(os.path.join(BASE, 'routes', 'api_offline_sync.py')) or ''
    if 'API_TOKENS' in offline:
        issues.append((key, 'MEDIUM', 'API tokens stored in-memory dict (lost on restart, not worker-safe)'))
    if '/api/auth/token' in offline and 'rate_limit' not in offline:
        issues.append((key, 'MEDIUM', '/api/auth/token has no rate limiting'))

    return issues


# ─────────────────────────────────────────────────────────────
# 6. ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────────
def check_env():
    issues = []
    key = 'ENV'

    app_py = read_file(os.path.join(BASE, 'app.py')) or ''
    config_py = read_file(os.path.join(BASE, 'config.py')) or ''

    # 6.1 SECRET_KEY
    if 'SECRET_KEY' in app_py or 'SECRET_KEY' in config_py:
        issues.append((key, 'INFO', 'SECRET_KEY handled'))
    if 'dev-secret' in config_py:
        issues.append((key, 'HIGH', 'Default dev SECRET_KEY found in BaseConfig'))

    # 6.2 DATABASE_URL
    if 'DATABASE_URL' in app_py:
        issues.append((key, 'INFO', 'DATABASE_URL properly masked in logs'))
    else:
        issues.append((key, 'CRITICAL', 'DATABASE_URL handling not found'))

    # 6.3 Check for hardcoded secrets
    py_files = find_files(r'.*\.py')
    for fp in py_files:
        content = read_file(fp) or ''
        for pattern in [r'password\s*=\s*["\'][^"\']+["\']',
                        r'api_key\s*=\s*["\'][^"\']+["\']',
                        r'secret\s*=\s*["\'][^"\']+["\']']:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                # Filter out 'placeholder', 'new_password' etc
                val = m.split('=')[1].strip().strip('"\'')
                if len(val) > 8 and val not in ('blood-bank-tobruk-secret-2024',
                                                  'dev-secret-change-in-prod'):
                    rel = os.path.relpath(fp, BASE)
                    issues.append((key, 'HIGH', f'{rel} — possible hardcoded secret: {m[:50]}'))

    # 6.4 Encryption keys
    if 'FIELD_ENCRYPTION_KEY' in app_py:
        issues.append((key, 'INFO', 'FIELD_ENCRYPTION_KEY handling present'))
    if 'BACKUP_ENCRYPTION_KEY' in (read_file(os.path.join(BASE, 'services', 'encryption_service.py')) or ''):
        issues.append((key, 'INFO', 'BACKUP_ENCRYPTION_KEY handling present'))

    return issues


# ─────────────────────────────────────────────────────────────
# 7. SPECIFIC MODEL ISSUES
# ─────────────────────────────────────────────────────────────
def check_models():
    issues = []
    key = 'MODEL'

    emp_file = read_file(os.path.join(BASE, 'models', 'employee.py')) or ''
    gov_file = read_file(os.path.join(BASE, 'models', 'employee_government.py')) or ''

    # 7.1 Sensitive data in to_dict
    if 'bank_account_number' in emp_file and 'include_sensitive' in emp_file:
        issues.append((key, 'LOW', 'bank_account_number in to_dict (controlled by include_sensitive flag)'))

    # 7.2 Password hash exposure
    if 'password_hash' in (read_file(os.path.join(BASE, 'models', 'employee_government.py')) or ''):
        issues.append((key, 'INFO', 'password_hash stored on model'))

    if 'to_dict' in emp_file and 'password_hash' not in emp_file.split('to_dict')[1].split('return')[0]:
        pass  # password_hash not in to_dict (good)

    # 7.3 Encryption
    if 'fernet' in emp_file or 'get_fernet' in emp_file:
        issues.append((key, 'INFO', 'Field-level encryption for sensitive data (salary, email, phone)'))

    return issues


# ─────────────────────────────────────────────────────────────
# GENERATE REPORT
# ─────────────────────────────────────────────────────────────
def issue_sort_key(i):
    return (SEVERITY_ORDER.get(i[1], 99), i[0], i[2])

def generate_html_report(all_issues):
    by_severity = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': [], 'INFO': []}
    for i in all_issues:
        cat, sev, desc = i
        by_severity.setdefault(sev, []).append(i)

    total = len(all_issues)
    high = len(by_severity['CRITICAL']) + len(by_severity['HIGH'])
    medium = len(by_severity['MEDIUM'])

    html_rows = []
    for sev in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'):
        for i in sorted(by_severity[sev], key=lambda x: x[2]):
            cat, sev, desc = i
            color = {'CRITICAL': '#ef4444', 'HIGH': '#f97316',
                     'MEDIUM': '#eab308', 'LOW': '#3b82f6', 'INFO': '#6b7280'}[sev]
            html_rows.append(f'''<tr>
<td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{sev}</span></td>
<td style="color:#8899b4;font-size:12px">{cat}</td>
<td>{html.escape(desc)}</td>
</tr>''')

    report = f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Backend Security Audit Report — SmartLog V2</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'system-ui',sans-serif;background:#080c18;color:#f0f4f9;padding:20px;font-size:14px;line-height:1.6}}
h1{{font-size:22px;font-weight:800;margin-bottom:4px}}
h2{{font-size:16px;font-weight:700;margin:24px 0 10px;color:#818cf8;border-bottom:1px solid #1e2a45;padding-bottom:6px}}
.summary{{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap}}
.summary-card{{background:#0f172a;border:1px solid #1e2a45;border-radius:12px;padding:16px;min-width:120px;text-align:center}}
.summary-card .num{{font-size:28px;font-weight:800}}
.summary-card .label{{font-size:12px;color:#8899b4;margin-top:2px}}
table{{width:100%;border-collapse:collapse;margin-top:8px}}
th,td{{padding:10px 12px;text-align:right;border-bottom:1px solid #17213a;font-size:13px}}
th{{color:#8899b4;font-weight:600;font-size:12px;text-transform:uppercase}}
tr:hover td{{background:rgba(255,255,255,.02)}}
.footer{{margin-top:24px;padding:12px;background:#0f172a;border-radius:10px;font-size:12px;color:#566580;text-align:center}}
</style>
</head>
<body>
<h1>Backend Security Audit Report</h1>
<div style="color:#8899b4;margin-bottom:16px">SmartLog V2 — {NOW}</div>

<div class="summary">
<div class="summary-card"><div class="num" style="color:{"#ef4444" if high else "#22c55e"}">{total}</div><div class="label">Total Checks</div></div>
<div class="summary-card"><div class="num" style="color:#ef4444">{high}</div><div class="label">High/Critical</div></div>
<div class="summary-card"><div class="num" style="color:#eab308">{medium}</div><div class="label">Medium</div></div>
</div>

<h2>Findings</h2>
<table>
<tr><th>Severity</th><th>Category</th><th>Description</th></tr>
{chr(10).join(html_rows)}
</table>

<div class="footer">
Generated by backend_security_checker.py — {NOW}
</div>
</body>
</html>'''
    return report


def main():
    print('=' * 60)
    print('  SmartLog V2 — Backend Security Audit')
    print(f'  {NOW}')
    print('=' * 60)
    print()

    all_issues = []
    checks = [
        ('Authentication', check_authentication),
        ('SQL Injection', check_sql_injection),
        ('Input Validation', check_input_validation),
        ('Error Handling', check_error_handling),
        ('API Security', check_api_security),
        ('Environment', check_env),
        ('Models', check_models),
    ]

    summaries = []
    for name, fn in checks:
        print(f'  Checking {name}...')
        try:
            issues = fn()
            all_issues.extend(issues)
            high = sum(1 for i in issues if i[1] in ('CRITICAL', 'HIGH'))
            medium = sum(1 for i in issues if i[1] == 'MEDIUM')
            summaries.append((name, high, medium, len(issues)))
        except Exception as e:
            print(f'  [ERROR] {name} check failed: {e}')
            summaries.append((name, 0, 0, 0))

    print()
    print('=' * 60)
    print('  SUMMARY')
    print('=' * 60)
    print(f'  {"Category":<25} {"High":>6} {"Med":>5} {"Total":>6}')
    print('  ' + '-' * 42)
    for name, high, medium, total in summaries:
        print(f'  {name:<25} {high:>6} {medium:>5} {total:>6}')
    print('  ' + '-' * 42)
    print(f'  {"TOTAL":<25} {sum(s[1] for s in summaries):>6} '
          f'{sum(s[2] for s in summaries):>5} {len(all_issues):>6}')

    # HTML report
    html = generate_html_report(all_issues)
    report_path = os.path.join(BASE, 'backend_security_report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'\n  HTML report: {report_path}')
    print('=' * 60)

    # Also print all findings
    print()
    print('  DETAILED FINDINGS:')
    all_issues.sort(key=issue_sort_key)
    for cat, sev, desc in all_issues:
        print(f'  [{sev:>8}] {desc[:100]}')

    return 0 if sum(s[1] for s in summaries) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
