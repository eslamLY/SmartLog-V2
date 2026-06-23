"""Edit file on GitHub web UI (simple)"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://github.com/eslamLY/SmartLog-V2/edit/main/routes/auth.py',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    print('Page loaded')

    # Get body to check page state
    body = pg.inner_text('body')
    print(f'Body length: {len(body)}')

    # If body is short, wait more
    if len(body) < 500:
        print('Waiting for more content...')
        time.sleep(5)
        body = pg.inner_text('body')
        print(f'Body length after wait: {len(body)}')

    # Check if we can find the CodeMirror editor
    try:
        # GitHub uses a contenteditable div with class "cm-content"
        editor = pg.locator('.cm-content').first
        if editor.is_visible(timeout=5000):
            print('CodeMirror editor visible')
            
            # Click at the end of the file
            editor.click()
            pg.keyboard.press('Control+End')
            time.sleep(0.5)
            
            # Add newlines and the new route code
            pg.keyboard.press('Enter')
            pg.keyboard.press('Enter')
            time.sleep(0.2)
            
            new_code = """
@auth_bp.route('/api/init-db')
def init_database():
    from models import db
    try:
        from flask_migrate import upgrade
        upgrade()
    except Exception as exc:
        pass
    try:
        from utils.seeds import seed_enterprise, seed_db, seed_shift_types, seed_leave_types
        seed_enterprise()
        seed_db()
        seed_shift_types()
        seed_leave_types()
        return jsonify({'ok': True, 'msg': 'Database initialized successfully'})
    except Exception as exc:
        import traceback
        return jsonify({'ok': False, 'msg': str(exc), 'traceback': traceback.format_exc()})
"""
            pg.keyboard.type(new_code, delay=5)
            print('Typed new code')
            time.sleep(3)
            
            # Find and click Propose changes / Commit
            for text in ['Commit changes', 'Propose changes']:
                btn = pg.locator(f'button:has-text("{text}")').first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f'Clicked {text}')
                    time.sleep(3)
                    break
        else:
            print('Editor not visible')
            # Try to find any textarea or contenteditable
            edit_area = pg.locator('textarea, [contenteditable="true"]').first
            if edit_area.is_visible(timeout=2000):
                print('Found alternative edit area')
    except Exception as e:
        print(f'Error: {e}')
        pg.screenshot(path=r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\github_error.png')

    browser.close()
