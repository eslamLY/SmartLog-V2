"""Check deploy log from Render dashboard - fixed for unicode"""
import time, re, sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]

    # Go to deploys page
    page.goto(
        'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys',
        wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    raw = page.inner_text('body')

    # Find deploy IDs (dep-xxxx)
    dep_ids = re.findall(r'dep-[a-z0-9]+', raw)
    print('Deploy IDs found:', dep_ids)

    if not dep_ids:
        # Maybe page hasn't loaded, try waiting
        page.wait_for_timeout(5000)
        raw = page.inner_text('body')
        dep_ids = re.findall(r'dep-[a-z0-9]+', raw)
        print('Deploy IDs found (2nd attempt):', dep_ids)

    # Try the failed deploy (latest one)
    for dep_id in dep_ids[:3]:
        print(f'\n--- Deploy: {dep_id} ---')
        try:
            page.goto(
                f'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/{dep_id}',
                wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(5000)

            log_text = page.inner_text('body')

            # Check for deploy status
            for kw in ['failed', 'live', 'building', 'created']:
                if kw in log_text.lower():
                    # Find context around it
                    idx = log_text.lower().index(kw)
                    start = max(0, idx - 30)
                    end = min(len(log_text), idx + 80)
                    snippet = log_text[start:end].replace('\n', '|')
                    print(f'  Status "{kw}": {snippet[:200]}')

            # Check for error keywords in log
            found_errors = False
            for kw in ['Traceback', 'ImportError', 'ModuleNotFound',
                        'FATAL', 'SyntaxError', 'No module',
                        'Error:', 'exit 1', 'permission denied',
                        'not found', 'connection refused']:
                if kw.lower() in log_text.lower():
                    idx = log_text.lower().index(kw.lower())
                    start = max(0, idx - 50)
                    end = min(len(log_text), idx + 300)
                    snippet = log_text[start:end].replace('\n', '|')
                    print(f'  Error "{kw}": {snippet[:400]}')
                    found_errors = True

            if not found_errors:
                print('  No recognizable errors found')

        except Exception as e:
            print(f'  Error: {e}')

    browser.close()
