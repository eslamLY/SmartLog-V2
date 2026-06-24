#!/usr/bin/env python3
"""
SmartLog V2 — Frontend Security Scanner
Scans all HTML template files, JS, and CSS for vulnerabilities.
"""
import os, re, sys, html
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

SEVERITY_COLORS = {
    'CRITICAL': ('#ef4444', '#fff'),
    'HIGH': ('#f97316', '#fff'),
    'MEDIUM': ('#eab308', '#000'),
    'LOW': ('#3b82f6', '#fff'),
    'INFO': ('#6b7280', '#fff'),
}

TEMPLATE_DIR = os.path.join(BASE, 'templates')
STATIC_DIR = os.path.join(BASE, 'static')


def find_files(pattern, root):
    result = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'venv', '.venv', '_temp')]
        for f in files:
            if re.search(pattern, f):
                result.append(os.path.join(dirpath, f))
    return result


def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


def count_files(root, pattern):
    return len(find_files(pattern, root))


# ─────────────────────────────────────────────────────────────
# CHECKS
# ─────────────────────────────────────────────────────────────

def check_jinja2_autoescaping():
    issues = []
    app_py = read_file(os.path.join(BASE, 'app.py'))
    # Flask enables autoescaping for .html by default
    issues.append(('JINJA2', 'INFO',
        'Flask enables Jinja2 autoescaping for .html templates by default'))
    # Check for |safe filter usage (bypasses escaping)
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        for i, line in enumerate(content.split('\n'), 1):
            if '|safe' in line and '{' in line:
                rel = os.path.relpath(fp, BASE)
                issues.append(('JINJA2', 'MEDIUM',
                    f'{rel}:{i} — |safe filter bypasses autoescaping: {line.strip()[:80]}'))
    if not any(i[1] == 'MEDIUM' for i in issues):
        issues.append(('JINJA2', 'INFO', 'No |safe filters found in templates'))
    return issues


def check_innerhtml_xss():
    issues = []
    total_innerhtml = 0
    files_with_unescaped = []
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'innerHTML' in line:
                total_innerhtml += 1
                # Check if data from API is directly assigned (no escaping)
                stripped = line.strip()
                if 'innerHTML' in stripped:
                    rel = os.path.relpath(fp, BASE)
                    # Count ++ for string concat with variables
                    if '+' in stripped and 'innerHTML' in stripped:
                        files_with_unescaped.append((rel, i, stripped[:80]))
    if total_innerhtml:
        issues.append(('XSS', 'HIGH',
            f'{total_innerhtml} innerHTML assignments found across templates — potential XSS'))
        for rel, li, line in files_with_unescaped[:10]:
            issues.append(('XSS', 'HIGH', f'  {rel}:{li} — {line}'))
        if len(files_with_unescaped) > 10:
            issues.append(('XSS', 'INFO',
                f'  ... and {len(files_with_unescaped)-10} more'))
    else:
        issues.append(('XSS', 'INFO', 'No innerHTML usage found'))
    return issues


def check_template_js_injection():
    issues = []
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        lines = content.split('\n')
        in_script = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if '<script' in stripped and '</script>' not in stripped:
                in_script = True
            if in_script:
                # Check for unescaped Jinja2 vars inside <script>
                matches = re.findall(r'\{\{[^}]*\}\}', line)
                for m in matches:
                    var = m.strip('{} ')
                    # If var is a string that could contain quotes
                    if var and not var.startswith('request.') and not var.startswith('url_for'):
                        rel = os.path.relpath(fp, BASE)
                        issues.append(('XSS', 'HIGH',
                            f'{rel}:{i} — Jinja2 var in <script> (may break escaping): {var}'))
            if '</script>' in stripped and '<script' not in stripped:
                in_script = False
    if not issues:
        issues.append(('XSS', 'INFO', 'No Jinja2 variables in script blocks'))
    return issues


def check_csrf_tokens():
    issues = []
    total_forms = 0
    forms_with_csrf = 0

    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        lines = content.split('\n')
        in_form = False
        for line in lines:
            stripped = line.strip()
            if '<form' in stripped:
                total_forms += 1
                in_form = True
            if in_form and ('csrf_token' in stripped or '__csrf' in stripped or
                            'X-CSRFToken' in stripped):
                forms_with_csrf += 1
                in_form = False
            if '</form>' in stripped:
                in_form = False

    # CSRF meta tag
    has_csrf_meta = False
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        if 'csrf-token' in content and 'meta' in content:
            has_csrf_meta = True
            break

    if has_csrf_meta:
        issues.append(('CSRF', 'INFO',
            'CSRF meta tag found (used by api() function)'))
    else:
        issues.append(('CSRF', 'HIGH', 'No CSRF meta tag in templates'))

    if total_forms:
        issues.append(('CSRF', 'INFO',
            f'{total_forms} HTML forms found, {forms_with_csrf} with CSRF'))
        if forms_with_csrf < total_forms:
            issues.append(('CSRF', 'MEDIUM',
                f'{total_forms - forms_with_csrf} forms missing CSRF tokens'))
    else:
        issues.append(('CSRF', 'INFO', 'No HTML forms found (API-driven)'))

    # Check api() in base.html
    base_html = read_file(os.path.join(TEMPLATE_DIR, 'base.html'))
    if 'X-CSRFToken' in base_html:
        issues.append(('CSRF', 'INFO',
            'api() function sends X-CSRFToken for POST requests'))
    else:
        issues.append(('CSRF', 'HIGH', 'api() function missing X-CSRFToken'))

    return issues


def check_third_party_scripts():
    issues = []
    seen_scripts = set()
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        for m in re.finditer(r'<script[^>]*src=["\']([^"\']+)["\']', content):
            src = m.group(1)
            if src.startswith('http') and 'self' not in src:
                if src not in seen_scripts:
                    seen_scripts.add(src)
                    issues.append(('THIRDPARTY', 'INFO',
                        f'External script: {src}'))

    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        for m in re.finditer(r'<link[^>]*href=["\']([^"\']+)["\']', content):
            href = m.group(1)
            if href.startswith('http') and 'self' not in href:
                key = f'link:{href}'
                if key not in seen_scripts:
                    seen_scripts.add(key)
                    issues.append(('THIRDPARTY', 'INFO',
                        f'External CSS/font: {href}'))

    # Check SRI (Subresource Integrity)
    sri_count = 0
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        sri_count += content.count('integrity=')
        if sri_count > 0:
            break

    if sri_count == 0:
        issues.append(('THIRDPARTY', 'HIGH',
            'No Subresource Integrity (integrity=) attributes on any CDN resource'))
    else:
        issues.append(('THIRDPARTY', 'INFO',
            f'SRI found on {sri_count} resource(s)'))

    return issues


def check_storage_usage():
    issues = []
    for fp in find_files(r'\.(html|js)$', os.path.join(BASE, 'templates')) + \
             find_files(r'\.(html|js)$', STATIC_DIR):
        content = read_file(fp)
        if 'localStorage' in content or 'sessionStorage' in content:
            rel = os.path.relpath(fp, BASE)
            issues.append(('STORAGE', 'MEDIUM', f'{rel} — uses client-side storage'))
    for fp in find_files(r'\.(html|js)$', os.path.join(BASE, 'templates')) + \
             find_files(r'\.(html|js)$', STATIC_DIR):
        content = read_file(fp)
        if re.search(r'(password|token|secret|key|ssn|credit|nid)', content,
                     re.IGNORECASE):
            # Check if in script context
            if '<script' in content or 'var ' in content or 'let ' in content:
                rel = os.path.relpath(fp, BASE)
                issues.append(('STORAGE', 'HIGH',
                    f'{rel} — possible sensitive data handled in client JS'))
                break
    if not issues:
        issues.append(('STORAGE', 'INFO', 'No client-side storage of sensitive data found'))
    return issues


def check_dangerous_js():
    issues = []
    patterns = {
        'eval(': 'CRITICAL',
        'new Function(': 'HIGH',
        'document.write(': 'HIGH',
        'setTimeout("': 'MEDIUM',
        'setInterval("': 'MEDIUM',
    }
    for fp in find_files(r'\.(html|js)$', os.path.join(BASE, 'templates')) + \
             find_files(r'\.(html|js)$', STATIC_DIR):
        content = read_file(fp)
        for pat, sev in patterns.items():
            idx = content.find(pat)
            if idx != -1:
                line_num = content[:idx].count('\n') + 1
                rel = os.path.relpath(fp, BASE)
                issues.append((f'JS-{sev}', sev,
                    f'{rel}:{line_num} — dangerous function: {pat}'))
    # Check template literal injections in innerHTML
    for fp in find_files(r'\.html$', TEMPLATE_DIR):
        content = read_file(fp)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'innerHTML' in line:
                # Check if template literal uses variable from API
                if '${' in line and 'data' in line.lower():
                    rel = os.path.relpath(fp, BASE)
                    issues.append(('XSS', 'HIGH',
                        f'{rel}:{i} — API data in innerHTML via template literal'))
                    break
    if not any(i[1] in ('CRITICAL', 'HIGH', 'MEDIUM') for i in issues):
        issues.append(('JS-SAFE', 'INFO', 'No dangerous JS functions found'))
    return issues


def check_template_file_list():
    files = find_files(r'\.html$', TEMPLATE_DIR)
    issues = [('TEMPLATES', 'INFO', f'{len(files)} HTML template files scanned')]
    return issues


def check_security_headers_in_templates():
    issues = []
    # Check for Content-Security-Policy meta tag
    csp_meta_found = False
    base_html = read_file(os.path.join(TEMPLATE_DIR, 'base.html'))
    if 'Content-Security-Policy' in base_html or 'http-equiv' in base_html:
        csp_meta_found = True
    issues.append(('HEADERS', 'INFO' if csp_meta_found else 'MEDIUM',
        'CSP via meta tag: ' + ('found' if csp_meta_found else 'not found (set via server headers)')))
    return issues


# ─────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────

def generate_html_report(all_issues):
    by_category = {}
    for cat, sev, desc in all_issues:
        by_category.setdefault(cat, []).append((sev, desc))

    cat_order = ['TEMPLATES', 'JINJA2', 'XSS', 'CSRF', 'HEADERS',
                 'STORAGE', 'THIRDPARTY', 'JS-SAFE', 'JS-CRITICAL',
                 'JS-HIGH', 'JS-MEDIUM']

    rows = []
    for cat in cat_order:
        if cat not in by_category:
            continue
        for sev, desc in by_category[cat]:
            bg, fg = SEVERITY_COLORS.get(sev, ('#6b7280', '#fff'))
            rows.append(f'''<tr>
<td><span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;font-size:11px">{sev}</span></td>
<td style="color:#8899b4;font-size:12px">{cat}</td>
<td>{html.escape(desc)}</td>
</tr>''')

    severity_count = {}
    for cat, sev, desc in all_issues:
        severity_count[sev] = severity_count.get(sev, 0) + 1

    total = len(all_issues)
    high = severity_count.get('CRITICAL', 0) + severity_count.get('HIGH', 0)
    medium = severity_count.get('MEDIUM', 0)

    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Frontend Security Audit — SmartLog V2</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'system-ui',sans-serif;background:#080c18;color:#f0f4f9;padding:20px;font-size:14px}}
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
<h1>Frontend Security Audit Report</h1>
<div style="color:#8899b4;margin-bottom:16px">SmartLog V2 — {NOW}</div>

<div class="summary">
<div class="summary-card"><div class="num" style="color:{"#ef4444" if high else "#22c55e"}">{total}</div><div class="label">Total Checks</div></div>
<div class="summary-card"><div class="num" style="color:#ef4444">{high}</div><div class="label">Critical/High</div></div>
<div class="summary-card"><div class="num" style="color:#eab308">{medium}</div><div class="label">Medium</div></div>
</div>

<h2>Vulnerability Scan Results</h2>
<table>
<tr><th>Severity</th><th>Category</th><th>Description</th></tr>
{chr(10).join(rows)}
</table>

<div class="footer">
Generated by frontend_security_checker.py — {NOW}
</div>
</body>
</html>'''


def main():
    print('=' * 60)
    print('  SmartLog V2 — Frontend Security Audit')
    print(f'  {NOW}')
    print('=' * 60)
    print()

    checks = [
        ('Template Files', check_template_file_list),
        ('Jinja2 Autoescaping', check_jinja2_autoescaping),
        ('innerHTML XSS', check_innerhtml_xss),
        ('Jinja2 in Scripts', check_template_js_injection),
        ('CSRF Tokens', check_csrf_tokens),
        ('Third-Party Scripts', check_third_party_scripts),
        ('Storage Usage', check_storage_usage),
        ('Dangerous JS', check_dangerous_js),
        ('Security Headers', check_security_headers_in_templates),
    ]

    all_issues = []
    for name, fn in checks:
        print(f'  Checking {name}...')
        try:
            issues = fn()
            all_issues.extend(issues)
        except Exception as e:
            print(f'  [ERROR] {name}: {e}')

    print()
    print('=' * 60)
    print('  SUMMARY')
    print('=' * 60)
    severity_breakdown = {}
    for cat, sev, desc in all_issues:
        severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1

    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
        c = severity_breakdown.get(sev, 0)
        if c:
            print(f'  {sev:>10}: {c}')
    print(f'  {"TOTAL":>10}: {len(all_issues)}')

    # HTML report
    html = generate_html_report(all_issues)
    report_path = os.path.join(BASE, 'frontend_security_report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n  HTML report: {report_path}')

    print()
    print('  DETAILED FINDINGS:')
    for cat, sev, desc in all_issues:
        color = {'CRITICAL': '!', 'HIGH': '-', 'MEDIUM': '=', 'LOW': '~', 'INFO': ' '}.get(sev, ' ')
        print(f'  [{color}{sev:>7}{color}] {desc[:120]}')

    print()
    print('=' * 60)
    print('  Frontend Security Audit Complete')
    print('=' * 60)

    return 0 if severity_breakdown.get('CRITICAL', 0) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
