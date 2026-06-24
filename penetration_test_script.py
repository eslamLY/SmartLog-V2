#!/usr/bin/env python3
"""
PHASE 2: MANUAL PENETRATION TESTING
=====================================
Tests the live SmartLog application for common web vulnerabilities.

Target: https://smartlog-v2-1.onrender.com
Output: penetration_test_report.txt

Tests performed:
  1. SQL Injection - Login form
  2. Cross-Site Scripting (XSS) - Login form
  3. Brute Force - Rate limit verification
  4. Session Security - Cookie analysis
  5. Endpoint Authorization - Unauthenticated access
  6. Security Headers - CSP, HSTS, etc.
  7. Path Traversal - File paths
  8. Information Disclosure - Error messages

Usage:
    python penetration_test_script.py
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import ssl
import socket
from datetime import datetime
from pathlib import Path
from http.cookiejar import CookieJar

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
REPORT = ROOT / 'penetration_test_report.txt'
TIMESTAMP = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

BASE_URL = 'https://smartlog-v2-1.onrender.com'
TIMEOUT = 60

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = []
findings = []


def _s(text):
    """Strip unicode for console."""
    return text.encode('ascii', 'replace').decode('ascii')


def req(method='GET', path='/', data=None, headers=None, allow_redirects=True):
    """Make HTTP request to target."""
    url = BASE_URL + path
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode()
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
    req_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req_obj, timeout=TIMEOUT, context=ctx)
        body = resp.read().decode('utf-8', errors='replace')
        info = {
            'status': resp.status,
            'headers': dict(resp.headers),
            'body': body,
        }
        return info
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        return {'status': e.code, 'headers': dict(e.headers), 'body': body}
    except Exception as e:
        return {'status': 0, 'headers': {}, 'body': str(e)}


def finding(severity, category, title, detail, evidence=''):
    entry = {
        'severity': severity,
        'category': category,
        'title': title,
        'detail': detail,
        'evidence': evidence[:200] if evidence else '',
    }
    findings.append(entry)
    return entry


def p(text=''):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


# ── Test 1: SQL Injection ──────────────────────────────────────────────

def test_sql_injection():
    p('\n  [Test 1] SQL Injection on Login')
    payloads = [
        ("' OR '1'='1", "' OR '1'='1"),
        ("admin' --", "admin' --"),
        ("' UNION SELECT * FROM employees--", "UNION injection"),
        ("'; DROP TABLE employees--", "DROP TABLE injection"),
        ("ADM001' /*", "Comment injection"),
        ("\" OR 1=1--", "Double-quote injection"),
        ("ADM001' AND 1=1--", "Boolean-based"),
        ("' WAITFOR DELAY '00:00:05'--", "Time-based (MSSQL)"),
        ("' OR pg_sleep(5)--", "Time-based (PostgreSQL)"),
        ("${7*7}", "Expression language"),
    ]
    vulns = 0
    for payload, desc in payloads:
        start = time.time()
        resp = req('POST', '/login', {'username': payload, 'password': 'test'})
        elapsed = time.time() - start
        ok = '"ok":true' in resp['body']
        msg = resp['body'][:100] if resp['body'] else 'no response'

        if ok:
            vulns += 1
            p(f'    [!] POTENTIAL VULN: {desc} -> {msg}')

    if vulns == 0:
        p(f'    [PASS] All {len(payloads)} SQLi payloads blocked')
        finding('INFO', 'SQL Injection', 'SQLi on login form', 
                f'All {len(payloads)} payloads were rejected',
                'No SQLi payload succeeded')
    else:
        p(f'    [FAIL] {vulns} potential SQLi vectors found')
        finding('CRITICAL', 'SQL Injection', 'SQL Injection on login',
                f'{vulns} payloads returned success response',
                f'Payloads that bypassed: see above')

    return vulns == 0


# ── Test 2: XSS ────────────────────────────────────────────────────────

def test_xss():
    p('\n  [Test 2] Cross-Site Scripting (XSS)')
    payloads = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "{{7*7}}",
        "${7*7}",
        "javascript:alert(1)",
        "<svg onload=alert(1)>",
        "'-prompt(1)-'",
        "<scr<script>ipt>alert(1)</scr</script>ipt>",
    ]
    reflected = 0
    for payload in payloads:
        resp = req('POST', '/login', {'username': payload, 'password': 'test'})
        if payload in resp['body']:
            reflected += 1
            p(f'    [!] XSS reflected: {payload[:40]}')

    if reflected == 0:
        p(f'    [PASS] No XSS reflection detected')
        finding('INFO', 'XSS', 'XSS on login form',
                'No payload was reflected in response',
                'All XSS payloads neutralized')
    else:
        p(f'    [FAIL] {reflected} XSS vectors reflected')
        finding('HIGH', 'XSS', 'Reflected XSS on login',
                f'{reflected} payloads were reflected in response',
                f'Reflected payloads: see above')

    return reflected == 0


# ── Test 3: Brute Force / Rate Limiting ────────────────────────────────

def test_rate_limiting():
    p('\n  [Test 3] Brute Force Protection')
    responses = []
    for i in range(15):
        resp = req('POST', '/login', {'username': 'ADMIN', 'password': f'wrong{i}'})
        responses.append(resp['status'])
        if resp['status'] == 429:
            p(f'    Rate limited after {i+1} attempts (status 429)')
            break
        time.sleep(0.1)

    rate_limited = any(s == 429 for s in responses)
    if rate_limited:
        p(f'    [PASS] Rate limiting active (429 returned)')
        finding('INFO', 'Rate Limiting', 'Brute force protection active',
                'Server returned 429 after repeated login attempts',
                f'Responses: {responses}')
    else:
        p(f'    [WARN] No rate limiting detected after {len(responses)} attempts')
        finding('HIGH', 'Rate Limiting', 'No rate limiting on login',
                'Server did not return 429 after 15 rapid attempts',
                f'All responses: {responses}')

    return rate_limited


# ── Test 4: Session Security ───────────────────────────────────────────

def test_session_security():
    p('\n  [Test 4] Session Security')
    findings_local = []

    # Login to get session
    resp = req('POST', '/login', {'username': 'ADM001', 'password': 'admin123'})
    set_cookie = resp['headers'].get('Set-Cookie', '')
    
    checks = {
        'HttpOnly': 'httponly' in set_cookie.lower(),
        'Secure': 'secure' in set_cookie.lower(),
        'SameSite=Lax': 'samesite=lax' in set_cookie.lower(),
        'SameSite=Strict': 'samesite=strict' in set_cookie.lower(),
    }
    
    for check, present in checks.items():
        if present:
            p(f'    [PASS] {check} flag present')
        else:
            p(f'    [WARN] {check} flag MISSING')
            findings_local.append(check)

    # Check session fixation: old session should clear after login
    p(f'    Set-Cookie headers: {set_cookie[:120]}')

    if not findings_local:
        finding('INFO', 'Session Security', 'Session cookies properly configured',
                'HttpOnly, Secure, SameSite flags present',
                set_cookie[:150])
    else:
        finding('MEDIUM', 'Session Security', f'Missing cookie flags: {", ".join(findings_local)}',
                'Session cookie missing security flags',
                set_cookie[:150])

    return len(findings_local) == 0


# ── Test 5: Endpoint Authorization ─────────────────────────────────────

def test_endpoint_auth():
    p('\n  [Test 5] Endpoint Authorization')
    sensitive_endpoints = [
        ('/admin', 'Admin dashboard (unauthorized)'),
        ('/api/employees', 'Employee list API'),
        ('/admin/system-health', 'System health page'),
        ('/api/init-db', 'Database initialization'),
        ('/admin/backups', 'Backup management'),
        ('/admin/payroll', 'Payroll data'),
    ]
    
    open_endpoints = []
    for path, desc in sensitive_endpoints:
        resp = req('GET', path)
        # 302 Redirect to login page = protected (good)
        # 200 OK with content = unprotected (bad)
        if resp['status'] == 200 and 'login' not in resp['body'][:200].lower():
            open_endpoints.append((path, desc, resp['status']))
            p(f'    [!] {desc} accessible without auth (status {resp["status"]})')
        elif resp['status'] in (302, 301):
            p(f'    [PASS] {desc} redirected to login (status {resp["status"]})')
        elif resp['status'] in (401, 403):
            p(f'    [PASS] {desc} returned {resp["status"]} (unauthorized)')
        else:
            p(f'    [INFO] {desc} status {resp["status"]}')

    if open_endpoints:
        finding('CRITICAL', 'Authorization', f'{len(open_endpoints)} endpoints accessible without auth',
                'Sensitive endpoints return 200 without authentication',
                '\n'.join(f'{d} ({s})' for _, d, s in open_endpoints))
    else:
        finding('INFO', 'Authorization', 'All endpoints require authentication',
                'Sensitive endpoints properly protected',
                'All returned 302/401/403')

    return len(open_endpoints) == 0


# ── Test 6: Security Headers ───────────────────────────────────────────

def test_security_headers():
    p('\n  [Test 6] Security Headers')
    resp = req('GET', '/login')
    headers = resp['headers']
    
    required = [
        ('Content-Security-Policy', 'CSP'),
        ('Strict-Transport-Security', 'HSTS'),
        ('X-Content-Type-Options', 'X-Content-Type-Options'),
        ('X-Frame-Options', 'X-Frame-Options'),
    ]
    
    missing = []
    present = []
    for header, name in required:
        if header.lower() in {k.lower(): v for k, v in headers.items()}:
            actual = {k.lower(): v for k, v in headers.items()}[header.lower()]
            present.append((name, actual[:80]))
            p(f'    [PASS] {name}: {actual[:80]}')
        else:
            missing.append(name)
            p(f'    [FAIL] {name} MISSING')

    if present:
        finding('INFO', 'Security Headers', f'{len(present)} security headers present',
                'CSP, HSTS, X-Content-Type-Options, X-Frame-Options found',
                str({k: v for k, v in present}))
    if missing:
        finding('HIGH', 'Security Headers', f'Missing headers: {", ".join(missing)}',
                'Required security headers not in response',
                f'Present: {[h for h, _ in present]}')

    return len(missing) == 0


# ── Test 7: Information Disclosure ─────────────────────────────────────

def test_info_disclosure():
    p('\n  [Test 7] Information Disclosure')
    sensitive_paths = [
        ('/.env', '.env file'),
        ('/.git/config', 'Git config'),
        ('/requirements.txt', 'Requirements file'),
        ('/Procfile', 'Procfile'),
        ('/config.py', 'Config file'),
        ('/app.py', 'App source'),
        ('/debug', 'Debug endpoint'),
        ('/admin/backup/download', 'Backup download'),
        ('/instance/', 'Instance directory'),
        ('/.git/HEAD', 'Git HEAD'),
    ]
    
    exposed = 0
    for path, desc in sensitive_paths:
        resp = req('GET', path)
        if resp['status'] == 200 and resp['body'] and len(resp['body']) > 10:
            exposed += 1
            p(f'    [!] {desc} accessible ({resp["status"]}, {len(resp["body"])} bytes)')

    if exposed == 0:
        p(f'    [PASS] No sensitive files exposed')
        finding('INFO', 'Information Disclosure', 'No sensitive files exposed',
                'All tested paths returned non-200 status',
                'All paths properly restricted')
    else:
        finding('HIGH', 'Information Disclosure', f'{exposed} sensitive paths exposed',
                'Source/config files accessible via HTTP',
                'Paths exposed: see above')

    return exposed == 0


# ── Test 8: Path Traversal ─────────────────────────────────────────────

def test_path_traversal():
    p('\n  [Test 8] Path Traversal')
    traversal_payloads = [
        '/static/../../etc/passwd',
        '/static/../../.env',
        '/static/..%2f..%2f..%2fetc/passwd',
        '/static/....//....//....//etc/passwd',
        '/uploads/../../etc/passwd',
        '/static/../../../etc/passwd',
        '/favicon.ico',
    ]
    
    vulnerable = 0
    for path in traversal_payloads:
        resp = req('GET', path)
        if resp['status'] == 200 and ('root:' in resp['body'] or 'DATABASE_URL' in resp['body']):
            vulnerable += 1
            p(f'    [!] Path traversal possible: {path}')

    if vulnerable == 0:
        p(f'    [PASS] Path traversal blocked')
        finding('INFO', 'Path Traversal', 'Path traversal not possible',
                'All traversal payloads returned non-200 or harmless content',
                'Traversal blocked')
    else:
        finding('CRITICAL', 'Path Traversal', f'Path traversal possible ({vulnerable} vectors)',
                'Directory traversal allowed sensitive file access',
                'Vulnerable paths: see above')

    return vulnerable == 0


# ── Test 9: CORS Configuration ─────────────────────────────────────────

def test_cors():
    p('\n  [Test 9] CORS Configuration')
    resp = req('GET', '/login', headers={'Origin': 'https://evil.com'})
    cors_header = None
    for k, v in resp['headers'].items():
        if k.lower() == 'access-control-allow-origin':
            cors_header = v
            break
    
    if cors_header:
        p(f'    [!] CORS allows origin: {cors_header}')
        finding('HIGH', 'CORS', 'CORS allows external origins',
                f'Access-Control-Allow-Origin: {cors_header}',
                'CORS misconfiguration may allow cross-origin attacks')
    else:
        p(f'    [PASS] No CORS header (restricted by default)')
        finding('INFO', 'CORS', 'CORS properly restricted',
                'No Access-Control-Allow-Origin header (same-origin only)',
                'CORS not configured for external origins')

    return cors_header is None


# ── Test 10: Cookie Security (login session) ───────────────────────────

def test_cookie_attributes():
    p('\n  [Test 10] Cookie Attributes')
    resp = req('POST', '/login', {'username': 'ADM001', 'password': 'admin123'})
    set_cookie = resp['headers'].get('Set-Cookie', '')
    
    cookie_attrs = {}
    if set_cookie:
        parts = set_cookie.split(';')
        for part in parts:
            part = part.strip()
            if '=' in part and part.split('=')[0].strip().lower() in ('path', 'domain', 'max-age', 'expires'):
                k, v = part.split('=', 1)
                cookie_attrs[k.strip().lower()] = v
            elif part.lower() in ('httponly', 'secure', 'samesite=lax', 'samesite=strict'):
                cookie_attrs[part.lower()] = True

    issues = []
    if not cookie_attrs.get('httponly'):
        issues.append('HttpOnly missing')
    if not cookie_attrs.get('secure'):
        issues.append('Secure missing (may be OK on HTTP)')
    if not cookie_attrs.get('samesite=lax') and not cookie_attrs.get('samesite=strict'):
        issues.append('SameSite missing')

    if issues:
        p(f'    [WARN] Cookie issues: {", ".join(issues)}')
    else:
        p(f'    [PASS] Cookie attributes: HttpOnly, Secure, SameSite present')

    return len(issues) == 0


# ── Report Generation ──────────────────────────────────────────────────

def generate_report(passed, failed):
    lines = []
    lines.append('=' * 72)
    lines.append('  SMARTLOG V2 — PENETRATION TEST REPORT')
    lines.append('=' * 72)
    lines.append(f'  Target:    {BASE_URL}')
    lines.append(f'  Date:      {TIMESTAMP}')
    lines.append(f'  Tests:     10')
    lines.append(f'  Passed:    {passed}')
    lines.append(f'  Failed:    {failed}')
    lines.append(f'  Risk:      {"LOW" if failed == 0 else "MEDIUM" if failed <= 3 else "HIGH" if failed <= 5 else "CRITICAL"}')
    lines.append('=' * 72)

    lines.append('\n\nEXECUTIVE SUMMARY')
    lines.append('-' * 40)
    if failed == 0:
        lines.append('  All security checks PASSED. The application shows strong')
        lines.append('  resistance to common web attacks including SQL injection,')
        lines.append('  XSS, brute force, and path traversal.')
    else:
        lines.append(f'  {failed} test(s) FAILED. See detailed findings below.')

    lines.append('\n\nTEST RESULTS')
    lines.append('-' * 40)
    for f_item in findings:
        status = 'PASS' if f_item['severity'] == 'INFO' else 'FAIL'
        lines.append(f'\n  [{status}] {f_item["severity"]} - {f_item["title"]}')
        lines.append(f'    Category: {f_item["category"]}')
        lines.append(f'    Detail:   {f_item["detail"]}')
        if f_item['evidence']:
            lines.append(f'    Evidence: {f_item["evidence"][:150]}')

    lines.append('\n\nDETAILED FINDINGS')
    lines.append('-' * 40)
    for i, f_item in enumerate(findings, 1):
        lines.append(f'\n  {i}. [{f_item["severity"]}] {f_item["title"]}')
        lines.append(f'     {f_item["detail"]}')

    lines.append('\n\nRECOMMENDATIONS')
    lines.append('-' * 40)
    criticals = [f for f in findings if f['severity'] == 'CRITICAL']
    highs = [f for f in findings if f['severity'] == 'HIGH']
    mediums = [f for f in findings if f['severity'] == 'MEDIUM']
    for f_item in criticals + highs + mediums:
        lines.append(f'  → {f_item["title"]}: {f_item["detail"][:100]}')
    if not criticals and not highs:
        lines.append('  No critical or high severity issues found.')

    lines.append('\n\n' + '=' * 72)
    lines.append('  END OF REPORT')
    lines.append('=' * 72)

    report_text = '\n'.join(lines)
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write(report_text)
    return report_text


def main():
    p('=' * 56)
    p('  PHASE 2: PENETRATION TESTING')
    p(f'  Target: {BASE_URL}')
    p(f'  Time:   {TIMESTAMP}')
    p('=' * 56)

    passed = 0
    failed = 0

    tests = [
        ('SQL Injection', test_sql_injection),
        ('XSS', test_xss),
        ('Rate Limiting', test_rate_limiting),
        ('Session Security', test_session_security),
        ('Endpoint Auth', test_endpoint_auth),
        ('Security Headers', test_security_headers),
        ('Info Disclosure', test_info_disclosure),
        ('Path Traversal', test_path_traversal),
        ('CORS', test_cors),
        ('Cookie Attributes', test_cookie_attributes),
    ]

    for name, test_func in tests:
        p(f'\n  {"─"*50}')
        try:
            ok = test_func()
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            p(f'    [ERROR] Test crashed: {e}')
            failed += 1

    p(f'\n  {"="*50}')
    p(f'  SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests')
    p(f'  Report: {REPORT}')
    p(f'  {"="*50}')

    generate_report(passed, failed)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
