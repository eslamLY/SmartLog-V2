"""Navigate to Environment tab by clicking sidebar link"""
import sys, time, json
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Go to service page
    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)

    # Find and click Environment link in sidebar
    sidebar_links = pg.evaluate('''() => {
        const links = document.querySelectorAll('a');
        return Array.from(links).map(l => ({
            text: l.textContent.trim().substring(0, 30),
            href: l.getAttribute('href') || '',
            rect: l.getBoundingClientRect(),
            visible: l.offsetParent !== null
        })).filter(l => l.text === 'Environment' || l.href.includes('environment'));
    }''')
    print('Environment links:')
    for link in sidebar_links:
        print(f'  text="{link["text"]}" href="{link["href"]}" visible={link["visible"]} rect={link["rect"]}')

    # Click the Environment link
    if sidebar_links:
        env_link = sidebar_links[0]
        if env_link['visible']:
            pg.evaluate(f'''() => {{
                const links = document.querySelectorAll('a');
                for (const l of links) {{
                    if (l.textContent.trim() === 'Environment' || l.href.includes('environment')) {{
                        l.click();
                        return;
                    }}
                }}
            }}''')
            time.sleep(5)
            print(f'Clicked, new URL: {pg.url}')

            # Now look for env var section
            body = pg.inner_text('body')
            # Find anything that looks like env vars
            for kw in ['Environment Variables', 'DATABASE_URL', 'SECRET_KEY',
                       'Add Variable', 'Add Environment', 'Key', 'Value',
                       'env var', 'No environment variables']:
                if kw in body:
                    i = body.index(kw)
                    print(f'Found "{kw}": {body[i:i+200].replace(chr(10), " ")}')

    # Try clicking the actual Environment tab even if URL didn't change
    try:
        env_btn = pg.locator('a:has-text("Environment")').first
        if env_btn.is_visible(timeout=2000):
            env_btn.click()
            time.sleep(3)
            print(f'After click via locator, URL: {pg.url}')
    except:
        pass

    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\env_body.txt', 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'\nBody length: {len(body)}')
    print('Body snippet:', body[1500:2500])

    browser.close()
