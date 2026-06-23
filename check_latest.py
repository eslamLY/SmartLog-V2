"""Check latest successful deploy logs"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Find the live deploy link
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(4)

    links = pg.evaluate('''() => {
        const links = document.querySelectorAll("a");
        return Array.from(links).map(l => ({
            text: l.textContent.trim().substring(0, 100),
            href: l.href,
            visible: l.offsetParent !== null
        })).filter(l => l.visible && l.href.includes("deploys/dep-"));
    }''')
    print('Deploy links:')
    for l in links:
        print(f'  {l["href"]}')

    # The LAST link should be the latest deploy - click it
    if links:
        deploy_url = links[0]['href']  # First = latest (sorted desc?)
        pg.goto(deploy_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5)
        print(f'\nDeploy page: {pg.url}')

        # Check status
        body = pg.inner_text('body')
        if 'Live' in body:
            print('Status: LIVE')
        elif 'Failed' in body:
            print('Status: FAILED')
        elif 'Building' in body:
            print('Status: BUILDING')

        # Get full body text, look for seed-related messages
        with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\latest_deploy.txt', 'w', encoding='utf-8') as f:
            f.write(body)

        for kw in ['seed', 'Seed', 'Startup', 'Tables', 'database connection',
                    'DB connection', 'create_all', 'flask db', 'migration']:
            if kw in body:
                i = body.index(kw)
                print(f'{kw}: {body[max(0,i-50):i+300].replace(chr(10), " ")}')

    browser.close()
