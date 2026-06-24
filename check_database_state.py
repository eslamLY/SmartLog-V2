#!/usr/bin/env python3
"""
SmartLog V2 — Check Current Database State
Connects to PostgreSQL, lists tables/columns, compares with expected schema.
Can be run as CLI tool or used as module.
Usage: python check_database_state.py
"""
import os, sys
from datetime import datetime

# Models expected in database (from __init__.py imports)
EXPECTED_TABLES = {
    'employees': ['id', 'full_name', 'username', 'password_hash', 'email', 'phone', 'department',
                  'role', 'device_id', 'is_active', 'force_password_change', 'password_changed_at',
                  'created_at', 'updated_at', 'deleted_at'],
    'departments': ['id', 'name_ar', 'name_en', 'code', 'is_active', 'created_at', 'updated_at'],
    'attendance_logs': ['id', 'employee_id', 'clock_in', 'clock_out', 'date', 'status', 'latitude',
                        'longitude', 'gps_accuracy', 'device_id', 'sync_id', 'created_at'],
    'login_attempts': ['id', 'ip_address', 'attempts', 'last_attempt', 'blocked_until'],
    'blocked_ips': ['id', 'ip_address', 'violation_count', 'banned_at', 'ban_expiry', 'is_permanent', 'is_active', 'updated_at'],
    'biometric_credentials': ['id', 'employee_id', 'credential_id', 'public_key', 'device_info', 'biometric_type', 'is_active', 'last_used', 'created_at'],
    'trusted_devices': ['id', 'employee_id', 'device_name', 'device_fingerprint', 'device_os', 'ip_address', 'is_trusted', 'last_used', 'created_at'],
    'audit_logs': ['id', 'user_id', 'action', 'entity_type', 'entity_id', 'details', 'ip_address', 'created_at'],
    'leave_requests': ['id', 'employee_id', 'leave_type', 'start_date', 'end_date', 'status', 'reason', 'approved_by', 'created_at', 'updated_at'],
    'outing_requests': ['id', 'employee_id', 'outing_type', 'start_time', 'end_time', 'status', 'reason', 'created_at'],
    'branding_config': ['id', 'tenant_name', 'primary_color', 'bg_color', 'logo_url', 'updated_at'],
    'notifications': ['id', 'employee_id', 'title', 'message', 'type', 'is_read', 'created_at'],
    'shift_types': ['id', 'name_ar', 'name_en', 'start_time', 'end_time', 'is_active', 'created_at'],
    'employee_documents': ['id', 'employee_id', 'doc_type', 'doc_number', 'file_path', 'notes', 'created_at'],
    'payroll_records': ['id', 'employee_id', 'month', 'year', 'base_salary', 'allowances', 'deductions', 'net_salary', 'status', 'generated_at', 'paid_at'],
    'rbac_roles': ['id', 'name', 'name_ar', 'description', 'parent_id', 'scope', 'is_system', 'is_active', 'risk_level', 'max_assignees', 'created_at', 'updated_at'],
    'rbac_permissions': ['id', 'name', 'name_ar', 'code', 'description', 'module', 'is_high_risk', 'requires_2fa', 'requires_approval', 'created_at'],
    'role_permissions': ['role_id', 'permission_id'],
    'rbac_employee_roles': ['id', 'employee_id', 'role_id', 'is_primary', 'assignment_type', 'effective_date', 'expiry_date', 'is_active', 'assigned_at'],
    'employee_grades': ['id', 'name', 'level', 'min_salary', 'max_salary', 'is_active', 'created_at'],
    'employee_qualifications': ['id', 'employee_id', 'qualification_type', 'field', 'institution', 'graduation_year', 'grade', 'created_at'],
    'employee_promotions': ['id', 'employee_id', 'from_grade', 'to_grade', 'reason', 'approved_by', 'effective_date', 'created_at'],
    'gps_logs': ['id', 'employee_id', 'latitude', 'longitude', 'accuracy', 'timestamp', 'created_at'],
}

def check_database(db_url=None):
    if not db_url:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print('[ERROR] DATABASE_URL not set')
            print('Usage: python check_database_state.py "postgresql://..."')
            return False

    try:
        from sqlalchemy import create_engine, inspect, text
        engine = create_engine(db_url, connect_args={'connect_timeout': 10})
        with engine.connect() as c: c.execute(text('SELECT 1'))
    except Exception as e:
        print(f'[ERROR] Connection failed: {e}')
        return False

    inspector = inspect(engine)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    existing = set(inspector.get_table_names())
    expected_set = set(EXPECTED_TABLES.keys())

    print('=' * 60)
    print('  SMARTLOG V2 — DATABASE STATE REPORT')
    print(f'  {now}')
    print('=' * 60)

    with engine.connect() as c:
        r = c.execute(text('SELECT current_database(), version()'))
        db_name, ver = r.fetchone()
        print(f'\n  Database: {db_name}')
        print(f'  Version:  {ver.split(",")[0]}')
        total = c.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
        print(f'  Tables in schema: {total}')

    print(f'\n  --- Existing Tables ({len(existing)}) ---')
    for i, t in enumerate(sorted(existing), 1):
        cols = inspector.get_columns(t)
        pk = inspector.get_pk_constraint(t)
        pks = pk.get('constrained_columns', [])
        parts = []
        for c in cols:
            nn = 'NOT NULL' if not c['nullable'] else 'nullable'
            pkf = ' PK' if c['name'] in pks else ''
            parts.append(f'{c["name"]}({c["type"]}{pkf},{nn})')
        print(f'  {i:2d}. {t} ({len(cols)} cols)')
        for p in parts: print(f'       - {p}')

    missing = sorted(expected_set - existing)
    extra = sorted(existing - expected_set)

    if missing:
        print(f'\n  --- MISSING TABLES ({len(missing)}) ---')
        for t in missing:
            expected_cols = EXPECTED_TABLES.get(t, [])
            print(f'  [MISSING] {t} ({len(expected_cols)} expected cols)')
            for c in expected_cols: print(f'      - {c}')

    if extra:
        print(f'\n  --- Extra Tables ({len(extra)}) ---')
        for t in extra:
            cols = inspector.get_columns(t)
            print(f'  [EXTRA] {t} ({len(cols)} cols)')

    print(f'\n  --- Column Check ---')
    any_missing = False
    for t in sorted(existing & expected_set):
        have = {c['name'] for c in inspector.get_columns(t)}
        want = set(EXPECTED_TABLES[t])
        miss = want - have
        if miss:
            any_missing = True
            print(f'  [INCOMPLETE] {t} missing: {", ".join(sorted(miss))}')
    if not any_missing and not missing:
        print('  All tables and columns match expected schema')

    print(f'\n  {"=" * 56}')
    print(f'  SUMMARY')
    print(f'  {"=" * 56}')
    print(f'  Existing: {len(existing)}  Expected: {len(expected_set)}')
    print(f'  Missing:  {len(missing)}  Extra: {len(extra)}')
    need_migration = bool(missing or any_missing)
    if need_migration:
        print(f'\n  STATUS: MIGRATION REQUIRED — {len(missing)} table(s) missing')
    else:
        print(f'\n  STATUS: DATABASE OK')
    print(f'  {"=" * 56}')

    engine.dispose()
    return not need_migration

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DATABASE_URL', '')
    sys.exit(0 if check_database(url) else 1)
