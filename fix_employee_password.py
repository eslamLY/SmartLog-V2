from core import create_app
from models import db, Employee
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    emp = Employee.query.filter_by(username='EMP001').first()
    if emp:
        emp.password_hash = generate_password_hash('emp123')
        db.session.commit()
        print(f"✅ Updated password for {emp.username}")
    else:
        print("❌ Employee not found")
