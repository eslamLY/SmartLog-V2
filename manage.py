#!/usr/bin/env python3
"""
SmartLog V2 — Database Management CLI
Usage:
  python manage.py check-db         # Check database state
  python manage.py seed             # Seed initial data
  python manage.py reset-sequence   # Reset auto-increment sequences
"""
import os, sys, json, re

_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def _validate_identifier(name: str, label: str = 'identifier') -> str:
    """Reject identifiers with special chars that could enable SQL injection."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}': must contain only letters, digits, and underscores."
        )
    return name

def run_check():
    from check_database_state import check_database
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[ERROR] DATABASE_URL not set')
        sys.exit(1)
    ok = check_database(db_url)
    sys.exit(0 if ok else 1)

def run_seed():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[ERROR] DATABASE_URL not set')
        sys.exit(1)
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    print('Seeding data...')

    # Department
    depts = [
        ('مصلحة الطب الشرعي', 'Forensic Medicine', 'FOR'),
        ('مختبر بنك الدم', 'Blood Bank Lab', 'BBL'),
        ('قسم التبرع', 'Donation Dept', 'DON'),
        ('المستودعات', 'Warehouses', 'WRH'),
        ('الإدارة', 'Administration', 'ADM'),
        ('تقنية المعلومات', 'IT', 'IT'),
        ('قسم الجودة', 'Quality Dept', 'QLT'),
        ('التدريب', 'Training', 'TRN'),
    ]
    with engine.connect() as conn:
        for ar, en, code in depts:
            r = conn.execute(text("SELECT id FROM departments WHERE code=:c"), {'c': code})
            if not r.fetchone():
                conn.execute(
                    text("INSERT INTO departments (name_ar, name_en, code, is_active) VALUES (:ar, :en, :c, true)"),
                    {'ar': ar, 'en': en, 'c': code}
                )
                print(f'  + Department: {ar}')
        conn.commit()

        # Shift types
        shifts = [
            ('الفترة الصباحية', 'Morning Shift', '07:00', '15:00'),
            ('الفترة المسائية', 'Evening Shift', '15:00', '23:00'),
            ('الفترة الليلية', 'Night Shift', '23:00', '07:00'),
            ('دوام مرن', 'Flexible', '08:00', '16:00'),
            ('دوام كامل', 'Full Day', '08:00', '17:00'),
        ]
        for ar, en, start, end in shifts:
            r = conn.execute(text("SELECT id FROM shift_types WHERE name_en=:en"), {'en': en})
            if not r.fetchone():
                conn.execute(
                    text("INSERT INTO shift_types (name_ar, name_en, start_time, end_time, is_active) VALUES (:ar, :en, :s, :e, true)"),
                    {'ar': ar, 'en': en, 's': start, 'e': end}
                )
                print(f'  + Shift: {ar}')
        conn.commit()

        # Check/create admin user in employees table
        r = conn.execute(text("SELECT id FROM employees WHERE username = :u"), {'u': 'ADM001'})
        if not r.fetchone():
            from werkzeug.security import generate_password_hash
            conn.execute(
                text("INSERT INTO employees (full_name, username, password_hash, role, department, is_active) "
                     "VALUES (:name, :user, :pw, :role, :dept, true)"),
                {'name': 'مدير النظام', 'user': 'ADM001',
                 'pw': generate_password_hash('admin123'),
                 'role': 'admin', 'dept': 'الإدارة'}
            )
            print('  + Admin user: ADM001 / admin123')

        # Seed login_attempts placeholder
        r = conn.execute(text("SELECT id FROM login_attempts WHERE ip_address = :ip"), {'ip': '0.0.0.0'})
        if not r.fetchone():
            from datetime import datetime, UTC
            conn.execute(
                text("INSERT INTO login_attempts (ip_address, attempts, last_attempt) VALUES (:ip, 0, :now)"),
                {'ip': '0.0.0.0', 'now': datetime.now(UTC)}
            )
        conn.commit()
        print('  + Login attempts placeholder')

        # Seed branding config
        r = conn.execute(text("SELECT id FROM branding_config WHERE tenant_name = :tn"), {'tn': 'SMARTLOG'})
        if not r.fetchone():
            conn.execute(
                text("INSERT INTO branding_config (tenant_name, primary_color, bg_color) VALUES (:tn, :pc, :bc)"),
                {'tn': 'SMARTLOG', 'pc': '#dc2626', 'bc': '#0f172a'}
            )
            conn.commit()
            print('  + Branding config')

    engine.dispose()
    print('Done seeding.')

def run_reset_sequences():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[ERROR] DATABASE_URL not set')
        sys.exit(1)
    from sqlalchemy import create_engine, text, inspect
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.connect() as conn:
        for t in tables:
            try:
                _validate_identifier(t, 'table name')
            except ValueError:
                print(f'  SKIP table (invalid name): {t}')
                continue
            cols = [c for c in inspector.get_columns(t) if c.get('autoincrement') and c['primary_key']]
            for c in cols:
                col_name = c['name']
                try:
                    _validate_identifier(col_name, 'column name')
                except ValueError:
                    print(f'  SKIP column (invalid name): {t}.{col_name}')
                    continue
                seq = f'{t}_{col_name}_seq'
                try:
                    _validate_identifier(seq, 'sequence name')
                    r = conn.execute(
                        text(f"SELECT setval(:seq, COALESCE((SELECT max({col_name}) FROM {t}), 1))"),
                        {'seq': seq}
                    )
                    print(f'  Reset sequence: {seq} -> {r.scalar()}')
                except ValueError:
                    print(f'  SKIP sequence (invalid name): {seq}')
                    continue
                except Exception:
                    pass
        conn.commit()
    engine.dispose()
    print('Done resetting sequences.')

def run_sanitize_names():
    """Clean up '.' placeholder in employee full_name that comes from ZKTeco empty surname."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[ERROR] DATABASE_URL not set')
        sys.exit(1)
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    def _sanitize(name):
        if not name:
            return name
        name = name.strip()
        name = name.rstrip('^ .\t')
        name = name.strip()
        parts = name.split(maxsplit=1)
        if len(parts) == 2:
            first, last = parts
            last_clean = last.rstrip('^ .\t').strip()
            if last_clean == '.' or last_clean == '':
                return first
            return f'{first} {last_clean}'
        return name

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, full_name FROM employees WHERE full_name LIKE '%. %' OR full_name LIKE '%.'")
        )
        rows = result.fetchall()
        fixed = 0
        log = []
        for row in rows:
            eid, old_name = row
            new_name = _sanitize(old_name)
            if new_name != old_name:
                conn.execute(
                    text("UPDATE employees SET full_name = :new WHERE id = :id"),
                    {'new': new_name, 'id': eid}
                )
                log.append({'id': eid, 'old': old_name, 'new': new_name})
                fixed += 1
        conn.commit()
        engine.dispose()

    print(f'=== Sanitize Names Complete ===')
    print(f'Records updated: {fixed}')
    if log:
        print('--- Changes ---')
        for entry in log:
            print(f'  ID {entry["id"]}: "{entry["old"]}" -> "{entry["new"]}"')
    print(f'Records unaffected: skipped clean entries.')
    if fixed == 0:
        print('No dirty names found (already clean or no matching records).')

    # Regression check
    print('--- Regression Check ---')
    engine2 = create_engine(db_url)
    with engine2.connect() as conn:
        dirty = conn.execute(
            text("SELECT id, full_name FROM employees WHERE "
                 "full_name LIKE '%. ' OR full_name LIKE '%.' OR "
                 "full_name LIKE '% .%' OR full_name LIKE '%^. %'")
        ).fetchall()
        engine2.dispose()
    if dirty:
        print(f'WARNING: {len(dirty)} records still have dirty names:')
        for r in dirty:
            print(f'  ID {r[0]}: "{r[1]}"')
    else:
        print('PASS: No employee record has "." stored as a name component after cleanup.')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == 'check-db' or cmd == 'check':
        run_check()
    elif cmd == 'seed':
        run_seed()
    elif cmd == 'reset-sequence':
        run_reset_sequences()
    elif cmd in ('db-check', 'dbcheck'):
        run_check()
    elif cmd == 'sanitize-names':
        run_sanitize_names()
    elif cmd == 'stamp':
        print('Stamping Alembic to head (d4f2c8b1a93e)...')
        import subprocess
        subprocess.run(['flask', 'db', 'stamp', 'd4f2c8b1a93e'], check=True)
        print('Done.')
    else:
        print('Usage: python manage.py <command>')
        print('Commands:')
        print('  check-db       Check database state')
        print('  seed           Seed initial data')
        print('  reset-sequence Reset auto-increment sequences')
        print('  sanitize-names Clean up dot placeholders in employee full_name')
        print('  stamp          Stamp Alembic to head revision')
        sys.exit(1)
