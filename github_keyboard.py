"""GitHub commit using keyboard navigation"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://github.com/eslamLY/SmartLog-V2/edit/main/routes/auth.py',
            wait_until='domcontentloaded', timeout=60000)
    time.sleep(8)

    editor = pg.locator('.cm-content').first
    if editor.is_visible(timeout=5000):
        editor.click()
        pg.keyboard.press('Control+End')
        time.sleep(0.5)
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
        time.sleep(2)

        # Press Ctrl+Enter (GitHub shortcut to commit)
        pg.keyboard.press('Control+Enter')
        print('Pressed Ctrl+Enter')
        time.sleep(3)
        print(f'URL: {pg.url}')

        # Check if redirected to the file view
        if 'edit' not in pg.url:
            print('SUCCESS - redirected away from edit page!')
        else:
            print('Still on edit page - trying alternative')

            # Try Tab Tab Tab Enter to navigate to the commit button
            pg.keyboard.press('Tab')
            time.sleep(0.3)
            pg.keyboard.press('Tab')
            time.sleep(0.3)
            pg.keyboard.press('Tab')
            time.sleep(0.3)
            pg.keyboard.press('Enter')
            time.sleep(3)
            print(f'URL after Tab+Enter: {pg.url}')

    browser.close()
