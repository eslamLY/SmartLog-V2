"""Find live deploy link"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(6)

    # Find ALL anchor elements with href containing dep-
    all_links = pg.evaluate('''() => {
        const links = document.querySelectorAll("a");
        const results = [];
        for (const l of links) {
            if (l.href && l.href.includes("dep-")) {
                results.push({
                    text: l.textContent.trim().substring(0, 80),
                    href: l.href,
                    visible: l.offsetParent !== null
                });
            }
        }
        return results;
    }''')
    print(f'Found {len(all_links)} links with dep-')
    for l in all_links:
        print(f'  visible={l["visible"]} text="{l["text"]}" href="{l["href"]}"')

    # Also try to find the text "Deploy live" and get the link around it
    pg.evaluate('window.scrollTo(0, 0)')
    time.sleep(1)

    # Get all elements that contain "Deploy live"
    live_elements = pg.evaluate('''() => {
        const all = document.querySelectorAll("*");
        const results = [];
        for (const el of all) {
            if (el.textContent.includes("Deploy live")) {
                const link = el.closest("a");
                results.push({
                    text: el.textContent.trim().substring(0, 80),
                    linkHref: link ? link.href : "no link",
                    tag: el.tagName
                });
            }
        }
        return results;
    }''')
    print(f'\nElements containing "Deploy live":')
    for e in live_elements:
        print(f'  tag={e["tag"]} link={e["linkHref"]} text="{e["text"]}"')

    browser.close()
