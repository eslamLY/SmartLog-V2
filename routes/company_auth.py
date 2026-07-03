import logging
from datetime import datetime, UTC
from functools import wraps

from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from models import db, Company, CompanyAdmin
from services.company_service import register_company, login_company, set_company_context
from utils.rate_limit import check_rate_limit

company_auth_bp = Blueprint('company_auth', __name__)
log = logging.getLogger(__name__)


def company_login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'company_admin_id' not in session:
            return redirect(url_for('company_auth.company_login'))
        set_company_context()
        return f(*a, **kw)
    return deco


@company_auth_bp.route('/company/register', methods=['GET', 'POST'])
def company_register():
    if request.method == 'POST':
        data = request.get_json() or {}
        result = register_company(data)
        return jsonify(result)
    return render_template('company/register.html')


@company_auth_bp.route('/company/login', methods=['GET', 'POST'])
def company_login():
    if request.method == 'POST':
        allowed, remaining = check_rate_limit('company_login', 5, 300)
        if not allowed:
            return jsonify({'ok': False, 'msg': 'لقد تجاوزت الحد المسموح به. يرجى الانتظار 5 دقائق.'}), 429
        data = request.get_json() or {}
        username = data.get('username', '').strip().upper()
        password = data.get('password', '').strip()
        result = login_company(username, password)
        if result['ok']:
            return jsonify({'ok': True, 'redirect': url_for('company_dashboard.company_dashboard')})
        return jsonify(result)
    return render_template('company/login.html')


@company_auth_bp.route('/company/logout')
def company_logout():
    session.pop('company_admin_id', None)
    session.pop('company_id', None)
    session.pop('company_admin_username', None)
    session.pop('company_name', None)
    session.pop('company_role', None)
    return redirect(url_for('company_auth.company_login'))


@company_auth_bp.route('/api/company/profile')
@company_login_required
def company_profile_api():
    from services.company_service import get_current_company, get_current_admin
    company = get_current_company()
    admin = get_current_admin()
    if not company or not admin:
        return jsonify({'ok': False, 'msg': 'غير مصرح به'}), 403
    return jsonify({
        'ok': True,
        'company': company.to_dict(),
        'admin': admin.to_dict(),
    })
