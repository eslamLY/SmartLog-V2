import logging
from datetime import datetime, UTC
from flask import session, g, request, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Company, CompanyAdmin

log = logging.getLogger(__name__)


def get_current_company():
    company_id = g.get('company_id') or session.get('company_id')
    if company_id:
        return Company.query.get(company_id)
    return None


def get_current_admin():
    admin_id = session.get('company_admin_id')
    if admin_id:
        return CompanyAdmin.query.get(admin_id)
    return None


def register_company(data):
    name_ar = data.get('name_ar', '').strip()
    username = data.get('username', '').strip().upper()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    plan = data.get('plan', 'starter')

    if not name_ar or not username or not password:
        return {'ok': False, 'msg': 'الاسم واسم المستخدم وكلمة المرور مطلوبة'}
    if len(password) < 6:
        return {'ok': False, 'msg': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'}

    exists = CompanyAdmin.query.filter_by(username=username).first()
    if exists:
        return {'ok': False, 'msg': 'اسم المستخدم موجود بالفعل'}

    company = Company(
        name_ar=name_ar,
        email=email,
        plan=plan,
        is_verified=False,
    )
    db.session.add(company)
    db.session.flush()

    admin = CompanyAdmin(
        company_id=company.id,
        username=username,
        password_hash=generate_password_hash(password),
        full_name=data.get('full_name', 'مدير النظام'),
        email=email,
    )
    db.session.add(admin)
    db.session.commit()

    return {'ok': True, 'msg': 'تم تسجيل الشركة بنجاح', 'company_id': company.id}


def login_company(username, password):
    admin = CompanyAdmin.query.filter_by(username=username, is_active=True).first()
    if not admin or not check_password_hash(admin.password_hash, password):
        return {'ok': False, 'msg': 'بيانات الدخول غير صحيحة'}

    company = Company.query.get(admin.company_id)
    if not company or not company.is_active:
        return {'ok': False, 'msg': 'حساب الشركة غير نشط'}

    admin.last_login = datetime.now(UTC)
    db.session.commit()

    session['company_admin_id'] = admin.id
    session['company_id'] = company.id
    session['company_admin_username'] = admin.username
    session['company_name'] = company.name_ar
    session['company_role'] = 'company_admin'

    return {'ok': True, 'msg': 'تم تسجيل الدخول بنجاح', 'company': company.to_dict()}


def set_company_context():
    company_id = session.get('company_id')
    if company_id:
        g.company_id = company_id
        g.company = Company.query.get(company_id)
    else:
        g.company_id = None
        g.company = None


def company_filter(query, model_class=None):
    company_id = g.get('company_id')
    if company_id and model_class:
        col = getattr(model_class, 'company_id', None)
        if col is not None:
            return query.filter(col == company_id)
    return query
