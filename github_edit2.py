"""Use GitHub web UI to edit auth.py"""
import sys, time, json
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    # First check if we're logged into GitHub
    pg.goto('https://github.com/eslamLY/SmartLog-V2/edit/main/routes/auth.py',
            wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    print(f'URL: {pg.url}')
    print(f'Title: {pg.title()}')

    body = pg.inner_text('body')
    print(f'Body length: {len(body)}')

    if 'Sign in' in body:
        print('NOT logged in to GitHub')
        # Try to go to the file page instead
        pg.goto('https://github.com/eslamLY/SmartLog-V2/blob/main/routes/auth.py',
                wait_until='domcontentloaded', timeout=30000)
        time.sleep(4)
        body2 = pg.inner_text('body')
        if 'Raw' in body2 and 'Blame' in body2:
            print('On file page - looking for Edit button')
            
            # Find the Edit button (pencil icon)
            edit_btn = pg.locator('a:has-text("Edit"), button:has-text("Edit"), [aria-label*="Edit"], [title*="Edit"]').first
            if edit_btn.is_visible(timeout=3000):
                edit_btn.click()
                time.sleep(4)
                print(f'After edit: {pg.url}')
                
                # Now we should be in the editor
                page_body = pg.inner_text('body')
                print(f'Editor page body (first 500): {page_body[:500]}')

                # Check for the code editor
                try:
                    # Look for the CM (CodeMirror) editor
                    cm_line = pg.locator('.cm-line').first
                    if cm_line.is_visible(timeout=3000):
                        print('CodeMirror editor found')
                        # Get all lines
                        lines = pg.locator('.cm-line').all()
                        print(f'Editor has {len(lines)} lines')

                        # To modify the file, we need to use keyboard input
                        # Click at the end of the file and add the new route
                except:
                    pass
    else:
        print('Already logged in to GitHub')

        # We're on the edit page, find the editor
        try:
            # GitHub uses CodeMirror which uses .cm-content
            cm = pg.locator('.cm-content').first
            if cm.is_visible(timeout=3000):
                print('CodeMirror editor found')
                # Click at end of file to focus
                cm.click()
                time.sleep(1)
                
                # Select all and replace or navigate to end
                pg.keyboard.press('Control+End')
                time.sleep(0.5)
                pg.keyboard.press('Enter')
                pg.keyboard.press('Enter')
                
                # Type the new route code
                new_code = '''
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
'''
                pg.keyboard.type(new_code)
                print('Typed new code')
                time.sleep(2)
                
                # Find and click Propose changes / Commit button
                commit_btn = pg.locator('button:has-text("Commit changes")').first
                if commit_btn.is_visible(timeout=3000):
                    commit_btn.click()
                    time.sleep(2)
                    print('Clicked Commit changes')
                else:
                    print('Commit changes button not found')
        except Exception as e:
            print(f'Error editing: {e}')

    browser.close()
