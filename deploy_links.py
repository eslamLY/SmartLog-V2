"""Get deploy logs from failed deploy"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # Scroll down to find the deploy entries
    pg.evaluate('window.scrollTo(0, 400)')
    time.sleep(1)

    # Take screenshot to see what's visible
    pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_view.png')

    # Check event list again - find items with Deploy failed and look for clickable elements
    html = pg.evaluate('''() => {
        // Get all anchor tags that have deploy in href
        const links = document.querySelectorAll("a");
        const deploys = [];
        for (const l of links) {
            if (l.href && l.href.includes("deploys") && l.href.includes("dep-")) {
                deploys.push({
                    text: l.textContent.trim().substring(0, 80),
                    href: l.href,
                    visible: l.offsetParent !== null
                });
            }
        }
        return deploys;
    }''')
    print('Deploy links found:', len(html))
    for d in html[:5]:
        print(f'  {d["href"]} visible={d["visible"]} text="{d["text"]}"')

    # If no deploy links found, try clicking the first failed deploy DIV
    if not html:
        fails = pg.locator('text=Deploy failed').all()
        print(f'Deploy failed elements on page: {len(fails)}')
        if fails:
            try:
                fails[0].click()
                time.sleep(4)
                print(f'After click URL: {pg.url}')
            except Exception as e:
                print(f'Click failed: {e}')

    browser.close()
