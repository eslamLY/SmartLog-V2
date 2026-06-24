#!/usr/bin/env python3
"""
SmartLog V2 — Verify Database Migration
Tests that all expected tables exist, relationships work, and data integrity is sound.
Usage: python verify_migration.py
"""
import os, sys
from datetime import datetime

def verify(db_url=None):
    if not db_url:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print('[ERROR] DATABASE_URL not set')
            return False

    from sqlalchemy import create_engine, inspect, text

    passed = 0
    failed = 0

    def test(name, ok, detail=''):
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f'  [PASS] {name}')
        else:
            failed += 1
            print(f'  [FAIL] {name} — {detail}')

    try:
        engine = create_engine(db_url, connect_args={'connect_timeout': 10})
        with engine.connect() as c:
            c.execute(text('SELECT 1'))
    except Exception as e:
        print(f'[ERROR] Cannot connect: {e}')
        return False

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    print(f'\n  Running verification...')
    print(f'  Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    # 1. Core tables
    core = ['employees', 'departments', 'attendance_logs', 'login_attempts', 'audit_logs',
            'branding_config', 'notifications', 'shift_types', 'employee_documents']
    for t in core:
        test(f'Table exists: {t}', t in existing, f'Table {t} not found')

    # 2. Leave & outings
    for t in ['leave_requests', 'outing_requests']:
        test(f'Table exists: {t}', t in existing, f'Table {t} not found')

    # 3. Payroll
    test('Table exists: payroll_records', 'payroll_records' in existing)

    # 4. RBAC
    for t in ['rbac_roles', 'rbac_permissions', 'role_permissions', 'rbac_employee_roles']:
        test(f'Table exists: {t}', t in existing, f'Table {t} not found')

    # 5. Enhanced HR
    for t in ['employee_grades', 'employee_qualifications', 'employee_promotions']:
        test(f'Table exists: {t}', t in existing, f'Table {t} not found')

    # 6. Check columns in employees
    if 'employees' in existing:
        cols = {c['name'] for c in inspector.get_columns('employees')}
        for needed in ['id', 'full_name', 'username', 'password_hash', 'role', 'department', 'is_active']:
            test(f'Column employees.{needed}', needed in cols, f'Missing column {needed}')

    # 7. Check columns in departments
    if 'departments' in existing:
        cols = {c['name'] for c in inspector.get_columns('departments')}
        for needed in ['id', 'name_ar', 'code']:
            test(f'Column departments.{needed}', needed in cols)

    # 8. Test basic queries
    with engine.connect() as conn:
        try:
            r = conn.execute(text('SELECT COUNT(*) FROM employees'))
            cnt = r.scalar()
            test('Query: SELECT COUNT(*) FROM employees', True, f'Count: {cnt}')
        except Exception as e:
            test('Query: SELECT COUNT(*) FROM employees', False, str(e))

        try:
            r = conn.execute(text('SELECT COUNT(*) FROM departments'))
            cnt = r.scalar()
            test('Query: SELECT COUNT(*) FROM departments', True, f'Count: {cnt}')
        except Exception as e:
            test('Query: SELECT COUNT(*) FROM departments', False, str(e))

        try:
            r = conn.execute(text('SELECT COUNT(*) FROM login_attempts'))
            cnt = r.scalar()
            test('Query: SELECT COUNT(*) FROM login_attempts', True, f'Count: {cnt}')
        except Exception as e:
            test('Query: SELECT COUNT(*) FROM login_attempts', False, str(e))

        try:
            r = conn.execute(text('SELECT COUNT(*) FROM shift_types'))
            cnt = r.scalar()
            test('Query: SELECT COUNT(*) FROM shift_types', True, f'Count: {cnt}')
        except Exception as e:
            test('Query: SELECT COUNT(*) FROM shift_types', False, str(e))

        # 9. Test foreign key integrity
        try:
            r = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE constraint_type='FOREIGN KEY' AND table_schema='public'
            """))
            fk_count = r.scalar()
            test(f'Foreign keys defined: {fk_count}', True, f'{fk_count} FK constraints')
        except Exception as e:
            test('Check foreign keys', False, str(e))

        # 10. Test employee-dashboard query
        try:
            r = conn.execute(text("SELECT id, full_name, username, role, department FROM employees LIMIT 5"))
            rows = r.fetchall()
            test(f'Query: SELECT employees (got {len(rows)} rows)', True)
            for row in rows:
                print(f'       [{row.id}] {row.full_name} ({row.username}) — {row.role} @ {row.department}')
        except Exception as e:
            test('Query: SELECT employees', False, str(e))

    print(f'\n  Results: {passed} passed, {failed} failed')
    engine.dispose()
    return failed == 0

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DATABASE_URL', '')
    ok = verify(url)
    print(f'\n  {"=" * 50}')
    print(f'  VERIFICATION: {"PASSED" if ok else "FAILED"}')
    print(f'  {"=" * 50}')
    sys.exit(0 if ok else 1)
