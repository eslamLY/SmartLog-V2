"""
SmartLog - Render Deploy via CDP (Chrome DevTools Protocol)
Connects to running Edge browser with remote debugging.
"""
import time, os, json
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\deploy_screenshots'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')


def deploy():
    log('Connecting to Edge via CDP...')
    log('Make sure Edge was started with: --remote-debugging-port=9222')

    with sync_playwright() as p:
        # Connect to the running Edge browser
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        log(f'Connected! Pages: {len(browser.contexts)}')

        # Get the first context and page
        ctx = browser.contexts[0]
        pages = ctx.pages
        log(f'Pages open: {len(pages)}')

        if not pages:
            page = ctx.new_page()
        else:
            page = pages[0]

        # Check current URL
        current_url = page.url
        log(f'Current URL: {current_url[:80]}')

        if 'dashboard.render.com' not in current_url:
            log('Navigating to Render dashboard...')
            page.goto('https://dashboard.render.com', wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, '01_dashboard.png'))

        # Wait a bit for page to fully load
        time.sleep(3)
        current_url = page.url
        log(f'After navigation: {current_url[:80]}')

        # Check if we're logged in
        if 'login' in current_url.lower() or 'auth' in current_url.lower() or 'github.com/login' in current_url:
            log('NOT LOGGED IN. Waiting for manual login...')
            log('Please log in to Render in the browser window.')
            log('Waiting up to 5 minutes...')
            for i in range(300):
                time.sleep(1)
                try:
                    if 'dashboard.render.com' in page.url and 'login' not in page.url.lower() and 'github.com/login' not in page.url:
                        log(f'Login detected after {i+1}s!')
                        break
                except:
                    pass
            else:
                log('Timeout waiting for login!')
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, '02_login_timeout.png'))
                return False

        log('Logged in! Looking for smartlog-v2 service...')
        time.sleep(5)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '03_logged_in.png'))

        # Get page content to find service links
        content = page.content()
        log(f'Page content length: {len(content)} chars')

        # Look for smartlog-v2 link
        service_found = False
        for attempt in range(10):
            try:
                # Try to find the service link
                service_link = page.locator('a:has-text("smartlog-v2")').first
                if service_link.is_visible(timeout=2000):
                    log('Found smartlog-v2 service link!')
                    service_link.click()
                    service_found = True
                    break
            except:
                pass

            try:
                service_link = page.locator('text=smartlog-v2').first
                if service_link.is_visible(timeout=2000):
                    log('Found via text selector!')
                    service_link.click()
                    service_found = True
                    break
            except:
                pass

            log(f'Attempt {attempt+1}: service not found, waiting...')
            time.sleep(3)

        if not service_found:
            log('Could not find smartlog-v2 service')
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, '04_no_service.png'))
            return False

        time.sleep(5)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '05_service_page.png'))
        log(f'Service page URL: {page.url[:80]}')

        # Look for Manual Deploy button
        log('Looking for Manual Deploy...')
        for attempt in range(10):
            try:
                manual_deploy = page.locator('button:has-text("Manual Deploy")').first
                if manual_deploy.is_visible(timeout=3000):
                    log('Found Manual Deploy button!')
                    manual_deploy.click()
                    time.sleep(2)
                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, '06_manual_deploy.png'))

                    # Look for "Deploy latest commit"
                    log('Looking for Deploy latest commit...')
                    for a in range(5):
                        try:
                            deploy_btn = page.locator('button:has-text("Deploy latest commit")').first
                            if deploy_btn.is_visible(timeout=3000):
                                log('Found Deploy latest commit!')
                                deploy_btn.click()
                                time.sleep(3)
                                page.screenshot(path=os.path.join(SCREENSHOT_DIR, '07_deploying.png'))
                                log('DEPLOY TRIGGERED SUCCESSFULLY!')
                                return True
                        except:
                            pass

                        try:
                            deploy_opt = page.locator('[role="menuitem"]:has-text("Deploy")').first
                            if deploy_opt.is_visible(timeout=3000):
                                log('Found deploy menu option!')
                                deploy_opt.click()
                                time.sleep(3)
                                page.screenshot(path=os.path.join(SCREENSHOT_DIR, '07_deploying.png'))
                                log('DEPLOY TRIGGERED SUCCESSFULLY!')
                                return True
                        except:
                            pass
                        time.sleep(1)
            except:
                pass

            # Try alternative: look for "Deploy" button directly
            try:
                deploy_btn = page.locator('button:has-text("Deploy")').first
                if deploy_btn.is_visible(timeout=2000):
                    log('Found generic Deploy button!')
                    deploy_btn.click()
                    time.sleep(3)
                    page.screenshot(path=os.path.join(SCREENSHOT_DIR, '06_deploy.png'))
                    log('DEPLOY TRIGGERED!')
                    return True
            except:
                pass

            log(f'Attempt {attempt+1}: deploy button not found, refreshing...')
            page.reload()
            time.sleep(5)

        log('Could not find deploy button after all attempts')
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, '08_failed.png'))
        return False


if __name__ == '__main__':
    print('=' * 60)
    print('  SmartLog - Render Auto-Deployer (CDP)')
    print('  Connects to running Edge browser')
    print('=' * 60)
    print()
    print(f'Screenshots: {SCREENSHOT_DIR}')
    print()
    result = deploy()
    print()
    if result:
        print('SUCCESS! Deploy triggered!')
    else:
        print('FAILED. Manual steps needed:')
        print('  1. In the open browser, click "smartlog-v2"')
        print('  2. Click "Manual Deploy" -> "Deploy latest commit"')
        print()
        print(f'Check screenshots in: {SCREENSHOT_DIR}')
    print()
    input('Press Enter to exit...')
