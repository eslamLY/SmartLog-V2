from core import create_app
from models import db, Employee, Department
from werkzeug.security import generate_password_hash
from datetime import datetime

app = create_app()

with app.app_context():
    # Create a test department if it doesn't exist
    dept = Department.query.filter_by(code='IT').first()
    if not dept:
        dept = Department(
            code='IT',
            name_ar='تقنية المعلومات',
            name_en='Information Technology',
            manager_id=None
        )
        db.session.add(dept)
        db.session.commit()
        print(f"✅ Created department: {dept.name_ar}")
    
    # Create admin user
    admin = Employee.query.filter_by(username='ADMIN001').first()
    if not admin:
        admin = Employee(
            username='ADMIN001',
            full_name='مدير النظام',
            email='admin@smartlog.ly',
            phone='0912345678',
            department=dept.name_ar,
            department_id=dept.id,
            job_title='System Administrator',
            employment_type='full_time',
            base_salary_encrypted='5000.0',
            is_active=True,
            role='admin',
            permission_level='admin',
            password_hash=generate_password_hash('admin123'),
            created_at=datetime.now()
        )
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Created admin user: {admin.username}")
    else:
        print(f"ℹ️  Admin user already exists: {admin.username}")
    
    # Create regular employee user
    emp = Employee.query.filter_by(username='EMP001').first()
    if not emp:
        emp = Employee(
            username='EMP001',
            full_name='موظف تجريبي',
            email='employee@smartlog.ly',
            phone='0912345679',
            department=dept.name_ar,
            department_id=dept.id,
            job_title='Software Developer',
            employment_type='full_time',
            base_salary_encrypted='3000.0',
            is_active=True,
            role='employee',
            permission_level='employee',
            password_hash=generate_password_hash('emp123'),
            created_at=datetime.now()
        )
        db.session.add(emp)
        db.session.commit()
        print(f"✅ Created employee user: {emp.username}")
    else:
        print(f"ℹ️  Employee user already exists: {emp.username}")
    
    print("\n" + "="*50)
    print("Test Users Created Successfully!")
    print("="*50)
    print(f"Admin Username: ADMIN001")
    print(f"Admin Password: admin123")
    print(f"Employee Username: EMP001")
    print(f"Employee Password: emp123")
    print("="*50)
