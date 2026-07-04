import logging
from datetime import datetime, UTC

from flask import Blueprint, render_template, request, session, jsonify
from models import db, Company, CompanyAdmin, BiometricDevice, Employee
from utils.decorators import admin_required

admin_companies_bp = Blueprint('admin_companies', __name__)
log = logging.getLogger(__name__)


@admin_companies_bp.route('/admin/companies')
@admin_required
def admin_companies_list():
    return render_template('admin/companies.html')


@admin_companies_bp.route('/api/admin/companies/list')
@admin_required
def api_admin_companies_list():
    companies = Company.query.order_by(Company.created_at.desc()).all()
    return jsonify({
        'ok': True,
        'companies': [{
            'id': c.id,
            'name_ar': c.name_ar,
            'name_en': c.name_en,
            'email': c.email,
            'phone': c.phone,
            'plan': c.plan,
            'is_active': c.is_active,
            'is_verified': c.is_verified,
            'max_employees': c.max_employees,
            'max_devices': c.max_devices,
            'employee_count': c.employee_count,
            'device_count': c.device_count,
            'created_at': c.created_at.isoformat() if c.created_at else None,
        } for c in companies],
        'total': len(companies),
    })


@admin_companies_bp.route('/api/admin/companies/<int:cid>')
@admin_required
def api_admin_company_detail(cid):
    c = Company.query.get_or_404(cid)
    admins = CompanyAdmin.query.filter_by(company_id=c.id).all()
    devices = BiometricDevice.query.filter_by(company_id=c.id, deleted_at=None).all()
    employees = Employee.query.filter_by(company_id=c.id, deleted_at=None).count()

    return jsonify({
        'ok': True,
        'company': c.to_dict(),
        'admins': [a.to_dict() for a in admins],
        'devices': [d.to_dict() for d in devices],
        'employee_count': employees,
    })


@admin_companies_bp.route('/api/admin/companies/<int:cid>/toggle', methods=['POST'])
@admin_required
def api_admin_company_toggle(cid):
    c = Company.query.get_or_404(cid)
    c.is_active = not c.is_active
    db.session.commit()
    status = 'تفعيل' if c.is_active else 'تعطيل'
    return jsonify({'ok': True, 'msg': f'تم {status} الشركة'})


@admin_companies_bp.route('/api/admin/companies/<int:cid>/plan', methods=['POST'])
@admin_required
def api_admin_company_change_plan(cid):
    c = Company.query.get_or_404(cid)
    data = request.get_json() or {}
    new_plan = data.get('plan', '').strip()
    valid_plans = ['starter', 'pro', 'enterprise']
    if new_plan not in valid_plans:
        return jsonify({'ok': False, 'msg': 'باقة غير صالحة'}), 400

    c.plan = new_plan
    from models.company import PLANS
    p = PLANS.get(new_plan, PLANS['starter'])
    c.max_employees = p['max_employees']
    c.max_devices = p['max_devices']
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'تم تغيير باقة الشركة إلى {new_plan}'})


@admin_companies_bp.route('/api/admin/companies/<int:cid>/verify', methods=['POST'])
@admin_required
def api_admin_company_verify(cid):
    c = Company.query.get_or_404(cid)
    c.is_verified = True
    db.session.commit()
    return jsonify({'ok': True, 'msg': 'تم توثيق الشركة'})


@admin_companies_bp.route('/api/admin/companies/stats')
@admin_required
def api_admin_companies_stats():
    total = Company.query.count()
    active = Company.query.filter_by(is_active=True).count()
    verified = Company.query.filter_by(is_verified=True).count()
    total_employees = Employee.query.filter_by(deleted_at=None).count()
    total_devices = BiometricDevice.query.filter_by(deleted_at=None).count()
    plan_dist = dict(Company.query.with_entities(Company.plan, db.func.count(Company.id)).group_by(Company.plan).all())

    return jsonify({
        'ok': True,
        'total_companies': total,
        'active_companies': active,
        'verified_companies': verified,
        'total_employees': total_employees,
        'total_devices': total_devices,
        'plan_distribution': plan_dist,
    })
