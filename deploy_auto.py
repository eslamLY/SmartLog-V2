"""
SmartLog - Automatic Render Deployer
Uses Playwright to automate Render dashboard deployment.
"""
import os, sys, time, json
from playwright.sync_api import sync_playwright

EDGE_PROFILE = os.path.expandvars(
    r'%LOCALAPPDATA%\Microsoft\Edge\User Data')
RENDER_URL = 'https://dashboard.render.com'
SERVICE_NAME = 'smartlog-v2'
SCREENSHOT_DIR = os.path.expandvars(
    r'%USERPROFILE%\OneDrive\Desktop\SmartLog V2\deploy_screenshots')

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')


def deploy():
    log('Starting Render auto-deployer...')
    log(f'Edge profile: {EDGE_PROFILE}')
    log(f'Screenshots: {SCREENSHOT_DIR}')

    with sync_playwright() as p:
        # Launch with Edge profile to preserve login session
        browser = p.chromium.launch_persistent_context(
            user_data_dir=EDGE_PROFILE,
            channel='msedge',
            headless=False,  # Show the browser so user can see what's happening
            args=['--start-maximized'],
            no_viewport=True,
        )

        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            # Navigate to Render dashboard
            log('Navigating to Render dashboard...')
            page.goto(RENDER_URL, wait_until='networkidle', timeout=60000)
            time.sleep(3)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, '01_dashboard.png'))

            # Check if we're logged in
            page_url = page.url
            log(f'Current URL: {page_url}')

            if 'login' in page_url.lower() or 'auth' in page_url.lower():
                log('NOT LOGGED IN - waiting for manual login...')
                # Wait for the user to log in
                page.wait_for_url('**/dashboard*', timeout=300000)
                log('Login detected, continuing...')
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, '02_logged_in.png'))

            # Wait for service list or service page
            time.sleep(5)

            # Check if we're on a service page or the main dashboard
            if SERVICE_NAME in page.url:
                log(f'Already on {SERVICE_NAME} page')
            else:
                log(f'Looking for {SERVICE_NAME} service...')
                # Try to find the service link
                try:
                    # Various selectors for Render dashboard service links
                    selectors = [
                        f'a[href*="{SERVICE_NAME}"]',
                        f'*:text("{SERVICE_NAME}")',
                        f'a:has-text("{SERVICE_NAME}")',
                        f'[data-testid*="service"]:has-text("{SERVICE_NAME}")',
                        f'div:has-text("{SERVICE_NAME}") a',
                    ]
                    clicked = False
                    for sel in selectors:
                        try:
                            el = page.locator(sel).first
                            if el.is_visible(timeout=3000):
                                log(f'Found service via: {sel}')
                                el.click()
                                clicked = True
                                break
                        except:
                            continue

                    if not clicked:
                        log('Could not find service link via selectors')
                        log('Saving page HTML for debugging...')
                        with open(os.path.join(SCREENSHOT_DIR, 'page.html'), 'w', encoding='utf-8') as f:
                            f.write(page.content())
                        page.screenshot(
                            path=os.path.join(SCREENSHOT_DIR, '03_no_service_found.png'))
                        return False
                except Exception as e:
                    log(f'Error finding service: {e}')
                    page.screenshot(
                        path=os.path.join(SCREENSHOT_DIR, '03_error.png'))
                    return False

            time.sleep(5)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, '04_service_page.png'))

            # Find and click "Manual Deploy" button
            log('Looking for Manual Deploy button...')
            try:
                deploy_selectors = [
                    'button:has-text("Manual Deploy")',
                    'button:has-text("manual")',
                    'a:has-text("Manual Deploy")',
                    '[data-testid*="deploy"]',
                    'button:has-text("Deploy")',
                ]
                deployed = False
                for sel in deploy_selectors:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            log(f'Found deploy button via: {sel}')
                            btn.click()
                            deployed = True
                            time.sleep(3)
                            page.screenshot(path=os.path.join(
                                SCREENSHOT_DIR, '05_deploy_clicked.png'))
                            break
                    except:
                        continue

                if not deployed:
                    log('Could not find Manual Deploy button')
                    page.screenshot(path=os.path.join(
                        SCREENSHOT_DIR, '05_no_deploy_button.png'))
                    return False

                # Look for "Deploy latest commit" option
                log('Looking for Deploy latest commit option...')
                try:
                    commit_selectors = [
                        'button:has-text("Deploy latest commit")',
                        'a:has-text("Deploy latest commit")',
                        'div:has-text("Deploy latest")',
                        'li:has-text("Deploy latest")',
                        '[role="menuitem"]:has-text("Deploy")',
                    ]
                    for sel in commit_selectors:
                        try:
                            opt = page.locator(sel).first
                            if opt.is_visible(timeout=5000):
                                log(f'Found deploy option via: {sel}')
                                opt.click()
                                time.sleep(2)
                                page.screenshot(path=os.path.join(
                                    SCREENSHOT_DIR, '06_deploying.png'))
                                break
                        except:
                            continue
                except Exception as e:
                    log(f'Error clicking deploy option: {e}')

            except Exception as e:
                log(f'Error during deploy: {e}')
                page.screenshot(path=os.path.join(
                    SCREENSHOT_DIR, '05_error.png'))
                return False

            log('Deploy triggered successfully!')
            log('Waiting 10 seconds for deployment to start...')
            time.sleep(10)
            page.screenshot(path=os.path.join(
                SCREENSHOT_DIR, '07_deploy_started.png'))
            log(f'Check progress at: {RENDER_URL}')
            return True

        except Exception as e:
            log(f'UNEXPECTED ERROR: {e}')
            page.screenshot(path=os.path.join(
                SCREENSHOT_DIR, '99_fatal_error.png'))
            return False
        finally:
            log('Closing browser...')
            browser.close()


if __name__ == '__main__':
    print('=' * 60)
    print('  SmartLog - Render Auto-Deployer')
    print('  Will open browser and deploy automatically')
    print('=' * 60)
    print()
    print(f'Edge profile: {EDGE_PROFILE}')
    print()
    result = deploy()
    print()
    if result:
        print('[SUCCESS] Deploy triggered!')
        print(f'  Check: https://smartlog-v2.onrender.com/api/health')
    else:
        print('[FAILED] Could not deploy automatically')
        print(f'  See screenshots in: {SCREENSHOT_DIR}')
        print()
        print('  Manual steps:')
        print('  1. Open https://dashboard.render.com')
        print('  2. Click "smartlog-v2" service')
        print('  3. Manual Deploy -> Deploy latest commit')
    print()
    input('Press Enter to exit...')
