"""Check deploy logs for failed deployment"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # Find all deploy entries and click the first failed one
    # Look for the "Deploy failed" entry
    entries = pg.evaluate('''() => {
        const all = document.querySelectorAll('a, button, [role="button"]');
        return Array.from(all).map(el => ({
            text: el.textContent.trim().substring(0, 100),
            tag: el.tagName,
            href: el.getAttribute('href') || '',
            rect: el.getBoundingClientRect(),
            visible: el.offsetParent !== null
        })).filter(e => e.text.includes('Deploy failed'));
    }''')
    print('Failed deploy entries:')
    for e in entries:
        print(f'  text="{e["text"]}" href={e["href"]} visible={e["visible"]}')

    # If found and visible, click it
    if entries and entries[0]['visible']:
        pg.evaluate('''() => {
            const all = document.querySelectorAll('a, button, [role="button"]');
            for (const el of all) {
                if (el.textContent.trim().includes('Deploy failed')) {
                    el.click();
                    return;
                }
            }
        }''')
        time.sleep(4)
        print(f'After click URL: {pg.url}')

        # Look for build log content
        body = pg.inner_text('body')
        # Look for error messages
        for kw in ['Error', 'error', 'Failed', 'failed', 'Traceback', 'Trace', 'pip', 'install', 'ModuleNotFound', 'ImportError']:
            if kw in body:
                i = body.index(kw) if kw in body else -1
                if i >= 0:
                    print(f'\nFound "{kw}" at {i}: {body[max(0,i-20):i+300].replace(chr(10), " ")}')

        # Save full body
        with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_log.txt', 'w', encoding='utf-8') as f:
            f.write(body)
    else:
        print('No failed deploy entries visible or clickable')

    browser.close()
