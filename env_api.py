"""Try setting env var via Render API"""
import sys, json, urllib.request, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')

# Render API endpoint for updating environment variables of a service
# First we need an API key (from the user's Render dashboard)
# Let me check if there's one available in the browser session

# Actually let me try a different approach: use the browser to navigate
# to the Environment tab with a force reload
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Force load the environment page with cache disabled
    pg.goto(
        'https://dashboard.render.com/web/srv-d8su9cojs32c73cuo030/environment',
        wait_until='networkidle', timeout=30000)
    time.sleep(8)

    # Check what the page actually shows
    html = pg.content()
    with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\env_page2.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # Look for env var related elements in the DOM
    env_section = pg.evaluate('''() => {
        // Look for the specific elements
        const hasEnvvars = document.querySelector('[data-testid="env-var-form"]');
        const hasSecrets = document.querySelector('[data-testid="env-var-secrets"]');
        return {
            hasEnvVarForm: !!hasEnvvars,
            hasSecrets: !!hasSecrets,
            url: window.location.href,
            bodyClass: document.body.className,
            mainContent: document.querySelector('main') ? document.querySelector('main').innerText.substring(0, 500) : 'no main'
        };
    }''')
    print('Page analysis:', json.dumps(env_section, indent=2))

    # Check if we can find the "Add Environment Variable" button
    buttons = pg.evaluate('''() => {
        const all = document.querySelectorAll('button, a, [role="button"]');
        return Array.from(all).map(el => ({
            tag: el.tagName,
            text: el.textContent.trim().substring(0, 40),
            href: el.href || '',
            visible: el.offsetParent !== null
        })).filter(b => b.text.length > 0);
    }''')
    print('\nInteractive elements:')
    for btn in buttons:
        print(f'  {btn.tag} visible={btn.visible} text="{btn.text}" href="{btn.href[:60]}"')

    # Look for any input that might be for env vars
    inputs = pg.evaluate('''() => {
        const all = document.querySelectorAll('input, textarea, select');
        return Array.from(all).map(el => ({
            id: el.id,
            name: el.name,
            type: el.type,
            placeholder: el.placeholder,
            value: (el.value || '').substring(0, 30)
        }));
    }''')
    print(f'\nInputs ({len(inputs)}):')
    for inp in inputs[:20]:
        print(f'  id="{inp["id"]}" type={inp["type"]} val="{inp["value"]}"')

    browser.close()
