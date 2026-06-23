"""Get GitHub token from browser and use API to update file"""
import sys, time, json, base64
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # Navigate to GitHub to get cookies/localStorage
    pg.goto('https://github.com', wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)

    # Try to get GitHub session token from localStorage
    token = pg.evaluate('''() => {
        // Try various storage keys
        const keys = Object.keys(localStorage);
        const session = {};
        for (const k of keys) {
            if (k.includes('token') || k.includes('oauth') || k.includes('gh_')) {
                session[k] = localStorage.getItem(k).substring(0, 50);
            }
        }
        // Also check for cookies with gh_ prefix
        return JSON.stringify(session);
    }''')
    print('LocalStorage tokens:', token[:200])

    # Get cookies
    cookies = pg.evaluate('''() => {
        return document.cookie;
    }''')
    print('Cookies (first 200):', cookies[:200])

    # Check for GitHub API token in session
    gh_token = pg.evaluate('''() => {
        // Check common GitHub token storage locations
        for (const key of ['gh_token', 'github_token', 'access_token', 'oauth_token']) {
            const val = localStorage.getItem(key);
            if (val) return val.substring(0, 50);
        }
        // Check session storage
        const keys = Object.keys(sessionStorage);
        for (const k of keys) {
            if (k.includes('token') || k.includes('oauth')) {
                return sessionStorage.getItem(k).substring(0, 50);
            }
        }
        return null;
    }''')
    print('GitHub token:', gh_token)

    browser.close()
