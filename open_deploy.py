"""Find and click failed deploy entry"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    clickable = pg.evaluate('''() => {
        const all = document.querySelectorAll('a, button, [role="button"], div');
        return Array.from(all).map(el => ({
            text: el.textContent.trim().substring(0, 120),
            tag: el.tagName,
            rect: el.getBoundingClientRect(),
            visible: el.offsetParent !== null
        })).filter(e => e.visible && (e.text.includes("Deploy failed") || e.text.includes("Deploy started")));
    }''')
    print('Deploy entries:')
    for c in clickable:
        print(f'  {c["tag"]} y={c["rect"]["y"]} text="{c["text"]}"')

    if clickable:
        first = clickable[0]
        pg.evaluate(f'window.scrollTo(0, {max(0, first["rect"]["y"] - 200)})')
        time.sleep(1)
        try:
            fail_entry = pg.locator('a').filter(has_text='Deploy failed').first
            if fail_entry.is_visible(timeout=2000):
                fail_entry.click()
                time.sleep(4)
                print(f'After click: {pg.url}')
                body = pg.inner_text('body')
                with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_log.txt', 'w', encoding='utf-8') as f:
                    f.write(body)
                for kw in ['Error', 'Traceback', 'ModuleNotFound', 'ImportError']:
                    if kw in body:
                        i = body.index(kw)
                        print(f'{kw}: {body[max(0,i-30):i+500].replace(chr(10), " ")}')
        except Exception as e:
            print(f'Click failed: {e}')
            # Try clicking first entry as fallback
            pg.evaluate('''() => {
                const links = document.querySelectorAll('a');
                for (const l of links) {
                    if (l.textContent.includes("Deploy failed")) {
                        l.click();
                        return;
                    }
                }
            }''')
            time.sleep(3)
            print(f'After JS click: {pg.url}')
            body = pg.inner_text('body')
            print('Body snippet:', body[:1000].replace(chr(10), ' '))

    browser.close()
