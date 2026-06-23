"""GitHub web editor - just commit code"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://github.com/eslamLY/SmartLog-V2/edit/main/routes/auth.py',
            wait_until='domcontentloaded', timeout=60000)
    time.sleep(8)

    body = pg.inner_text('body')
    print(f'Body: {len(body)} chars')

    if 'Commit changes' in body:
        print('Editor page loaded with Commit changes button')

        # Find the editor 
        editor = pg.locator('.cm-content').first
        if editor.is_visible(timeout=5000):
            print('Editor visible')
            
            # Click at end
            editor.click()
            pg.keyboard.press('Control+End')
            time.sleep(1)
            pg.keyboard.press('Enter')
            pg.keyboard.press('Enter')

            code = """\n@auth_bp.route('/api/init-db')
def init_database():
    from models import db
    try:
        from flask_migrate import upgrade
        upgrade()
    except Exception:
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
        return jsonify({'ok': False, 'msg': str(exc), 'traceback': traceback.format_exc()})"""
            
            pg.keyboard.type(code, delay=2)
            print('Typed')
            time.sleep(2)

            # Click Commit
            commit = pg.locator('button:has-text("Commit changes")')
            if commit.is_visible(timeout=3000):
                commit.click()
                print('Committed')
                time.sleep(3)

    browser.close()
