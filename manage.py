#!/usr/bin/env python3
"""
SmartLog V2 — Database Management CLI
Usage:
  python manage.py check-db         # Check database state
  python manage.py seed             # Seed initial data
  python manage.py reset-sequence   # Reset auto-increment sequences
"""
import os, sys, json

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
        r = conn.execute(text("SELECT id FROM employees WHERE username='ADM001'"))
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
        r = conn.execute(text("SELECT id FROM login_attempts WHERE ip_address='0.0.0.0'"))
        if not r.fetchone():
            from datetime import datetime, UTC
            conn.execute(
                text("INSERT INTO login_attempts (ip_address, attempts, last_attempt) VALUES ('0.0.0.0', 0, :now)"),
                {'now': datetime.now(UTC)}
            )
        conn.commit()
        print('  + Login attempts placeholder')

        # Seed branding config
        r = conn.execute(text("SELECT id FROM branding_config WHERE tenant_name='بنك دم طبرق'"))
        if not r.fetchone():
            conn.execute(
                text("INSERT INTO branding_config (tenant_name, primary_color, bg_color) VALUES ('بنك دم طبرق', '#e53935', '#0f172a')")
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
            cols = [c for c in inspector.get_columns(t) if c.get('autoincrement') and c['primary_key']]
            for c in cols:
                seq = f'{t}_{c["name"]}_seq'
                try:
                    r = conn.execute(text(f"SELECT setval('{seq}', COALESCE((SELECT max({c['name']}) FROM {t}), 1))"))
                    print(f'  Reset sequence: {seq} -> {r.scalar()}')
                except:
                    pass
        conn.commit()
    engine.dispose()
    print('Done resetting sequences.')

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
    else:
        print('Usage: python manage.py <command>')
        print('Commands:')
        print('  check-db       Check database state')
        print('  seed           Seed initial data')
        print('  reset-sequence Reset auto-increment sequences')
        sys.exit(1)
