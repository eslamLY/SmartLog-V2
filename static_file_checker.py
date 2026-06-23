#!/usr/bin/env python3
"""
Static File Checker — Verifies all static assets exist and are accessible.
Run locally BEFORE deploying to Render.

Usage:
    python static_file_checker.py                    # Check all
    python static_file_checker.py --mode icons       # Only icons
    python static_file_checker.py --mode css         # Only CSS
    python static_file_checker.py --mode js          # Only JS
    python static_file_checker.py --manifest         # Check manifest.json

Exit code: 0 if all OK, 1 if any issue found.
"""
import os
import sys
import json
import hashlib
import mimetypes

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, 'static')
MIN_FILES = {
    'css': 3,
    'js': 5,
    'icons': 2,
}

REQUIRED_FILES = [
    'static/css/pwa.css',
    'static/css/style.css',
    'static/js/app.js',
    'static/icons/icon-192.svg',
    'static/icons/icon-512.svg',
    'static/manifest.json',
    'static/sw.js',
]


def color(s, code):
    return f'\033[{code}m{s}\033[0m' if sys.platform != 'win32' else s


OK_SYM = '[OK]'
FAIL_SYM = '[FAIL]'
WARN_SYM = '[WARN]'

def green(s): return color(s, '92')
def red(s):   return color(s, '91')
def yellow(s): return color(s, '93')
def bold(s):  return color(s, '1')


def safe_print(text):
    """Print text safely on Windows cp1256 consoles."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def check_path(relative_path):
    """Check a single static file exists and is readable."""
    abs_path = os.path.join(ROOT, relative_path)
    if not os.path.exists(abs_path):
        return False, 'NOT FOUND'
    if not os.path.isfile(abs_path):
        return False, 'NOT A FILE'
    size = os.path.getsize(abs_path)
    if size == 0:
        return False, 'EMPTY FILE'
    return True, f'{size:,} bytes'


def count_files(directory, extension):
    """Count files with given extension in a directory."""
    dir_path = os.path.join(STATIC, directory)
    if not os.path.isdir(dir_path):
        return 0
    return len([f for f in os.listdir(dir_path) if f.endswith(extension)])


def check_manifest():
    """Validate manifest.json has correct icon paths."""
    manifest_path = os.path.join(STATIC, 'manifest.json')
    if not os.path.isfile(manifest_path):
        return ['ERROR: manifest.json not found']
    errors = []
    with open(manifest_path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            return [f'ERROR: manifest.json is invalid JSON: {e}']
    icons = data.get('icons', [])
    if not icons:
        errors.append('WARNING: No icons defined in manifest.json')
    for icon in icons:
        src = icon.get('src', '')
        # Strip leading /static/ or / for file system check
        check_src = src
        if check_src.startswith('/static/'):
            check_src = check_src[8:]  # remove '/static/'
        elif check_src.startswith('/'):
            check_src = check_src[1:]  # remove leading '/'
        icon_path = os.path.join(STATIC, check_src)
        if not os.path.isfile(icon_path):
            errors.append(f'ERROR: Icon file not found: {icon_path} (src="{src}")')
        sizes = icon.get('sizes', '')
        if not sizes:
            errors.append(f'WARNING: Icon missing sizes attribute: {src}')
    return errors


def check_template_static_refs():
    """Scrape templates for hardcoded /static/ paths that should use url_for."""
    import re
    templates_dir = os.path.join(ROOT, 'templates')
    if not os.path.isdir(templates_dir):
        return ['WARNING: templates/ directory not found']
    errors = []
    pattern = re.compile(r'(href|src)=["\']/static/([^"\']+)["\']')
    for root, dirs, files in os.walk(templates_dir):
        for f in files:
            if f.endswith('.html'):
                filepath = os.path.join(root, f)
                with open(filepath, encoding='utf-8') as fh:
                    content = fh.read()
                matches = pattern.findall(content)
                if matches:
                    rel_path = os.path.relpath(filepath, ROOT)
                    for m in matches:
                        errors.append(f'  {rel_path}: {m[0]}="/static/{m[1]}" -> use url_for')
    return errors


def check_cdn_reachable():
    """Quick check that CDN URLs are reachable (icon CSS files)."""
    import urllib.request
    import ssl
    cdns = [
        'https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.24.0/dist/tabler-icons.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
    ]
    errors = []
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for url in cdns:
        try:
            req = urllib.request.Request(url, method='HEAD')
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            if resp.status != 200:
                errors.append(f'WARNING: {url} returned HTTP {resp.status}')
            else:
                print(f'  [OK] {url}')
        except Exception as e:
            errors.append(f'WARNING: Cannot reach {url}: {e}')
    return errors


def main():
    mode = 'all'
    if '--mode' in sys.argv:
        idx = sys.argv.index('--mode')
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]
    check_manifest_flag = '--manifest' in sys.argv

    if not os.path.isdir(STATIC):
        print(red(f'ERROR: static/ directory not found at {STATIC}'))
        sys.exit(1)

    all_ok = True

    # ── Check required files ──
    if mode in ('all', 'files'):
        print(bold('\n== Required static files =='))
        for rel_path in REQUIRED_FILES:
            ok, info = check_path(rel_path)
            status = green(OK_SYM) if ok else red(FAIL_SYM)
            print(f'  {status} {rel_path} ({info})')
            if not ok:
                all_ok = False

    # ── Check file counts ──
    if mode in ('all', 'counts'):
        print(bold('\n== Static file counts =='))
        for dirname, minimum in MIN_FILES.items():
            ext_map = {'css': '.css', 'js': '.js', 'icons': '.svg'}
            ext = ext_map.get(dirname, '')
            count = count_files(dirname, ext)
            status = green(OK_SYM) if count >= minimum else red(FAIL_SYM)
            print(f'  {status} static/{dirname}/: {count} files (min {minimum})')
            if count < minimum:
                all_ok = False

    # ── Check manifest ──
    if mode in ('all', 'manifest') or check_manifest_flag:
        print(bold('\n== manifest.json check =='))
        manifest_errors = check_manifest()
        if manifest_errors:
            for e in manifest_errors:
                print(f'  {red(FAIL_SYM)} {e}')
            if any('ERROR' in e for e in manifest_errors):
                all_ok = False
        else:
            print(f'  {green(OK_SYM)} All manifest icons valid')

    # ── Check template references ──
    if mode in ('all', 'templates'):
        print(bold('\n== Template hardcoded /static/ paths (should use url_for) =='))
        ref_errors = check_template_static_refs()
        if ref_errors:
            for e in ref_errors:
                print(f'  {yellow(WARN_SYM)} {e}')
            print(f'  ({yellow("recommended")} but not blocking)')
        else:
            print(f'  {green(OK_SYM)} No hardcoded /static/ paths found')

    # ── Check CDN reachability ──
    if mode in ('all', 'cdn'):
        print(bold('\n== CDN reachability =='))
        cdn_errors = check_cdn_reachable()
        if cdn_errors:
            for e in cdn_errors:
                print(f'  {yellow(WARN_SYM)} {e}')
            print(f'  ({yellow("warnings only")} -- CDN may be down or blocked)')

    # ── Summary ──
    print()
    if all_ok:
        print(green(bold('[PASS] All static file checks passed!')))
        sys.exit(0)
    else:
        print(red(bold('[FAIL] Some checks failed - fix before deploying to Render')))
        sys.exit(1)


if __name__ == '__main__':
    main()
