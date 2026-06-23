"""Scroll up in deploy logs to see startup messages"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/deploys/dep-d8t01467r5hc73ebj27g',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)

    # Try to scroll UP in the log viewer (newest logs are at bottom)
    # Render log viewer should auto-scroll or have scroll buttons
    # Let me try clicking on the time range selector to show older logs
    time_range = pg.locator('button:has-text("Jun 23, 5:41 AM")').first
    if time_range.is_visible(timeout=3000):
        time_range.click()
        print('Clicked time range')
        time.sleep(3)
        # Try clicking a custom range
        custom = pg.locator('button:has-text("Custom")').first
        if custom.is_visible(timeout=2000):
            custom.click()
            time.sleep(2)

    # Try to access the log stream directly
    # Sometimes Render has a "View all logs" or scroll buttons
    # Let me look for the scrollable log container
    log_container = pg.evaluate('''() => {
        const divs = document.querySelectorAll("div");
        for (const d of divs) {
            if (d.scrollHeight > d.clientHeight + 50) {
                return {
                    tag: d.tagName,
                    className: d.className.substring(0, 100),
                    scrollHeight: d.scrollHeight,
                    clientHeight: d.clientHeight,
                    innerText: d.innerText.substring(0, 500)
                };
            }
        }
        return null;
    }''')
    
    if log_container:
        print(f'Found scrollable container: class={log_container["className"]}')
        print(f'  scrollHeight={log_container["scrollHeight"]} clientHeight={log_container["clientHeight"]}')
        print(f'  text: {log_container["innerText"][:300]}')

    # Get ALL visible text that contains log-like content
    body = pg.inner_text('body')
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\full_log_content.txt', 'w', encoding='utf-8') as f:
        f.write(body)

    # Find lines with timestamps (format: HH:MM:SS)
    lines = body.split('\n')
    timestamp_lines = [l.strip() for l in lines if ':'.join(filter(str.isdigit, l[:8])) or ('AM' in l and ':' in l[:9])]
    print(f'\nTimestamp lines count: {len(timestamp_lines)}')
    
    # Focus on lines with startup info
    for line in lines:
        if any(kw in line for kw in ['starting', 'SmartLog starting', 'DATABASE_URL', 
                                      'DB connection', 'create_all', 'seed',
                                      'ready to serve', 'Startup:', 'startup complete']):
            print(f'  {line.strip()[:300]}')

    browser.close()
