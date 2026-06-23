"""Seed database directly via external connection"""
import sys, json
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')

EXTERNAL_DB_URL = 'postgresql+pg8000://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a.frankfurt-postgres.render.com/smartlog_db'

try:
    from sqlalchemy import create_engine, text
    from werkzeug.security import generate_password_hash
    from datetime import datetime, UTC
    
    engine = create_engine(EXTERNAL_DB_URL)
    
    with engine.connect() as conn:
        # Check if departments already exist
        result = conn.execute(text("SELECT COUNT(*) FROM departments"))
        dept_count = result.scalar()
        print(f'Existing departments: {dept_count}')
        
        if dept_count == 0:
            departments = [
                ('LAB', 'مختبر التحليل'), ('BB', 'بنك الدم'),
                ('NUR', 'التمريض'), ('REC', 'الاستقبال'),
                ('ADM', 'الإدارة'), ('WH', 'المستودع'),
                ('FIN', 'الشؤون المالية'), ('TRN', 'التدريب'),
                ('QC', 'مراقبة الجودة'), ('DON', 'التبرع'),
                ('AWR', 'التوعية'), ('MNT', 'الصيانة')
            ]
            for code, name in departments:
                conn.execute(text("INSERT INTO departments (code, name_ar) VALUES (:code, :name)"),
                           {"code": code, "name": name})
            conn.commit()
            print(f'Created {len(departments)} departments')
        
        # Check if admin exists
        result = conn.execute(text("SELECT COUNT(*) FROM employees WHERE username = 'ADM001'"))
        admin_count = result.scalar()
        print(f'Admin exists: {admin_count > 0}')
        
        if admin_count == 0:
            # Get department ID for 'الإدارة'
            dept = conn.execute(text("SELECT id FROM departments WHERE name_ar = 'الإدارة'")).first()
            dept_id = dept[0] if dept else None
            
            # Create admin
            conn.execute(text("""
                INSERT INTO employees (username, full_name, department, password_hash, 
                    role, is_active, created_at)
                VALUES (:u, :n, :d, :p, :r, true, :ts)
            """), {
                "u": "ADM001", "n": "مدير النظام", "d": "الإدارة",
                "p": generate_password_hash('admin123'),
                "r": "admin", "ts": datetime.now(UTC)
            })
            
            # Create sample employees
            samples = [
                ('EMP001', 'أحمد محمد الورفلي', 'مختبر التحليل', 3500),
                ('EMP002', 'فاطمة علي الزاوي', 'بنك الدم', 3200),
                ('EMP003', 'محمد سالم البراني', 'الاستقبال', 2800),
                ('EMP004', 'عائشة خالد الدرسي', 'التمريض', 3000),
                ('EMP005', 'يوسف إبراهيم الرفادي', 'المستودع', 2600),
                ('EMP006', 'مريم عمر الطاهر', 'مختبر التحليل', 3100),
                ('EMP007', 'خالد مصطفى القوراري', 'بنك الدم', 3300),
                ('EMP008', 'سارة نجيب الشلماني', 'الإدارة', 2900),
            ]
            
            for u, n, d, s in samples:
                dept = conn.execute(text("SELECT id FROM departments WHERE name_ar = :name"), {"name": d}).first()
                conn.execute(text("""
                    INSERT INTO employees (username, full_name, department, department_id, 
                        password_hash, role, is_active, created_at)
                    VALUES (:u, :n, :d, :did, :p, 'employee', true, :ts)
                """), {
                    "u": u, "n": n, "d": d, "did": dept[0] if dept else None,
                    "p": generate_password_hash('123456'),
                    "ts": datetime.now(UTC)
                })
            
            conn.commit()
            print(f'Created 1 admin + {len(samples)} employees')
        
        # Verify
        result = conn.execute(text("SELECT username, full_name, role FROM employees ORDER BY username"))
        employees = result.fetchall()
        print(f'\nEmployees in database ({len(employees)}):')
        for emp in employees:
            print(f'  {emp[0]}: {emp[1]} ({emp[2]})')
    
    engine.dispose()
    print('\n✅ Database seeding completed successfully!')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
