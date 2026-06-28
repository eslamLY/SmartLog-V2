"""
Batch-fix all hardcoded /static/ paths in templates to use url_for().
Run: python scripts/fix_static_refs.py

Before: href="/static/css/style.css"
After:  href="{{ url_for('static', filename='css/style.css') }}"

Before: src="/static/js/app.js"
After:  src="{{ url_for('static', filename='js/app.js') }}"
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, 'templates')

PATTERN = re.compile(r'(href|src)=["\']/static/([^"\']+)["\']')
REPLACEMENT = r'\1="{{ url_for(\'static\', filename=\'\2\') }}"'

def fix_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    new_content = PATTERN.sub(REPLACEMENT, content)
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

def main():
    fixed = []
    errors = []
    for root, dirs, files in os.walk(TEMPLATES):
        for f in files:
            if f.endswith('.html'):
                filepath = os.path.join(root, f)
                try:
                    if fix_file(filepath):
                        rel = os.path.relpath(filepath, ROOT)
                        fixed.append(rel)
                        print(f'  [FIXED] {rel}')
                except Exception as e:
                    errors.append(f'{filepath}: {e}')
                    print(f'  [ERROR] {filepath}: {e}')
    print(f'\nFixed: {len(fixed)} files')
    if errors:
        print(f'Errors: {len(errors)} files')
        for e in errors:
            print(f'  {e}')
    return len(errors) == 0

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
