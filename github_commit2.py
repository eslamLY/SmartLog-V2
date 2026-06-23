"""GitHub commit with dialog handling"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://github.com/eslamLY/SmartLog-V2/edit/main/routes/auth.py',
            wait_until='domcontentloaded', timeout=60000)
    time.sleep(8)

    # Click on editor
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

        # First button click opens the "Commit changes" dialog
        commit_btn = pg.locator('button:has-text("Commit changes...")').first
        if commit_btn.is_visible(timeout=3000):
            print('Found Commit changes... button')
            commit_btn.click()
            time.sleep(2)

            # Now the dialog should be open - find the final Commit changes button
            # Look for button inside the dialog/modal
            # Use JS to bypass backdrop overlay
            pg.evaluate('''() => {
                const btns = document.querySelectorAll("button");
                for (const b of btns) {
                    if (b.textContent.includes("Commit changes") && b.offsetParent !== null) {
                        b.click();
                        return;
                    }
                }
            }''')
            print('Clicked dialog Commit changes via JS')
            time.sleep(3)
            print(f'URL after: {pg.url}')
    else:
        print('Editor not visible')

    browser.close()
