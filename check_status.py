import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]
    print('Current URL:', page.url[:100])
    print()

    content = page.content()
    keywords = ['building', 'deploying', 'live', 'failed', 'succeeded',
                'in progress', 'Build in progress', 'Deploying',
                'Deploy latest commit']

    for kw in keywords:
        if kw.lower() in content.lower():
            idx = content.lower().find(kw.lower())
            print('Found:', repr(kw))
            print('Context:', content[max(0,idx-80):idx+120])
            print()

    page.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots\10_status.png')
    print('Screenshot saved')
    browser.close()
