import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]

    # Look for deploy log content
    body = page.text_content('body')

    # Find deploy failure reason
    keywords = ['Exited with status', 'FATAL', 'Error:', 'error:', 'Traceback',
                'ModuleNotFoundError', 'ImportError', 'No module', 'SyntaxError',
                'DATABASE_URL', 'connection refused', 'could not connect',
                'permission denied', 'not found', 'entrypoint']

    for kw in keywords:
        if kw.lower() in body.lower():
            idx = body.lower().index(kw.lower())
            start = max(0, idx - 100)
            end = min(len(body), idx + 300)
            print(f'=== Found: {kw} ===')
            print(body[start:end])
            print()

    browser.close()
