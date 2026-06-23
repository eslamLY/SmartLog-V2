"""Check deploy log from Render dashboard"""
import time, re
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]

    # Go to deploys page
    page.goto(
        'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys',
        wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    body = page.text_content('body')

    # Find deploy IDs (dep-xxxx)
    dep_ids = re.findall(r'dep-[a-z0-9]+', body)
    print('Deploy IDs found:', dep_ids)

    # Try each deploy
    for dep_id in dep_ids:
        print(f'\n--- Checking deploy: {dep_id} ---')
        try:
            page.goto(
                f'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/{dep_id}',
                wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)
            log_text = page.text_content('body')

            # Look for error details
            found = False
            for kw in ['Traceback', 'ImportError', 'ModuleNotFound',
                        'FATAL:', 'Error:', 'exit 1', 'SyntaxError',
                        'ERR!', 'failed with', 'No module']:
                if kw.lower() in log_text.lower():
                    idx = log_text.lower().index(kw.lower())
                    start = max(0, idx - 100)
                    end = min(len(log_text), idx + 500)
                    print(f'Found "{kw}":')
                    print(log_text[start:end])
                    print()
                    found = True

            # Also look for the deploy log section
            print(f'Page title: {page.title()[:100]}')

            # Look for log viewer tabs/buttons
            log_tabs = ['Logs', 'Build log', 'Runtime log', 'Console']
            for tab in log_tabs:
                try:
                    btn = page.locator(f'button:has-text("{tab}")').first
                    if btn.is_visible(timeout=1000):
                        print(f'Found log tab: {tab}')
                        btn.click()
                        time.sleep(3)
                        # Get log content
                        log_area = page.text_content('body')
                        # Find error keywords in log
                        for kw in ['Traceback', 'Error', 'FATAL', 'exit 1']:
                            if kw in log_area:
                                idx = log_area.index(kw)
                                print(f'  Log contains: {kw}')
                                print(f'  Context: {log_area[max(0,idx-50):idx+200]}')
                except:
                    pass

        except Exception as e:
            print(f'Error on {dep_id}: {e}')

    print('\nDone')
    browser.close()
