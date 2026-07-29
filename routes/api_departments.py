import logging
from datetime import datetime, UTC
from functools import wraps

from flask import Blueprint, request, jsonify, session
from models import db
from models.employee import Employee
from models.department import Department, DepartmentCertification
from models.shifts import ShiftType
from models.biotime_device import BioTimeDevice
from utils.decorators import admin_required
from services.cached_queries import invalidate_department_cache

departments_api_bp = Blueprint('departments_api', __name__)
LOGGER = logging.getLogger(__name__)


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': 'حدث خطأ داخلي.'}), 500
    return wrapper


def _serialize(dept):
    return {
        'id': dept.id,
        'code': dept.code,
        'name_ar': dept.name_ar,
        'name_en': dept.name_en,
        'icon': dept.icon,
        'color': dept.color,
        'description_ar': dept.description_ar,
        'description_en': dept.description_en,
        'dept_type': dept.dept_type,
        'is_active': dept.is_active,
        'parent_id': dept.parent_id,
        'parent_name': dept.parent.name_ar if dept.parent else None,
        'dept_level': dept.dept_level,
        'manager_id': dept.manager_id,
        'manager_name': dept.manager.full_name if dept.manager else None,
        'deputy_id': dept.deputy_id,
        'cost_center_code': dept.cost_center_code,
        'min_staff_required': dept.min_staff_required,
        'max_staff_capacity': dept.max_staff_capacity,
        'employee_count': dept.employee_count,
        'default_shift_id': dept.default_shift_id,
        'grace_period_override': dept.grace_period_override,
        'remote_work_allowed': dept.remote_work_allowed,
        'hierarchy_path': dept.hierarchy_path,
        'created_at': dept.created_at.isoformat() if dept.created_at else None,
    }


@departments_api_bp.route('/api/departments/list')
@admin_required
@safe_api
def list_departments():
    depts = Department.query.order_by(Department.id).all()
    return jsonify({'departments': [_serialize(d) for d in depts]})


@departments_api_bp.route('/api/departments/add', methods=['POST'])
@admin_required
@safe_api
def add_department():
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    name_ar = data.get('name_ar', '').strip()
    if not code:
        code = Department.generate_code()
    if not name_ar:
        return jsonify({'ok': False, 'msg': 'اسم القسم مطلوب'}), 400
    existing = Department.query.filter_by(code=code).first()
    if existing:
        return jsonify({'ok': False, 'msg': f'الكود {code} مستخدم بالفعل'}), 400
    parent_id = data.get('parent_id')
    if parent_id:
        parent = Department.query.get(int(parent_id))
        dept_level = (parent.dept_level or 0) + 1 if parent else 1
    else:
        parent_id = None
        dept_level = 1
    d = Department(
        code=code,
        name_ar=name_ar,
        name_en=data.get('name_en', '').strip() or None,
        icon=data.get('icon', 'building'),
        color=data.get('color', '#e53935'),
        description_ar=data.get('description_ar', '').strip() or None,
        description_en=data.get('description_en', '').strip() or None,
        dept_type=data.get('dept_type', 'operational'),
        is_active=data.get('is_active', True),
        parent_id=parent_id,
        dept_level=dept_level,
        manager_id=int(data['manager_id']) if data.get('manager_id') else None,
        deputy_id=int(data['deputy_id']) if data.get('deputy_id') else None,
        cost_center_code=data.get('cost_center_code', '').strip() or None,
        min_staff_required=int(data.get('min_staff_required', 2)),
        max_staff_capacity=int(data.get('max_staff_capacity', 50)),
        default_shift_id=int(data['default_shift_id']) if data.get('default_shift_id') else None,
        grace_period_override=int(data['grace_period_override']) if data.get('grace_period_override') else None,
        remote_work_allowed=bool(data.get('remote_work_allowed', False)),
    )
    db.session.add(d)
    db.session.flush()

    certs = data.get('certifications', [])
    for cert in certs:
        cert_name = cert.strip() if isinstance(cert, str) else cert.get('name', '').strip()
        if cert_name:
            db.session.add(DepartmentCertification(department_id=d.id, certification=cert_name))

    device_ids = data.get('allowed_device_ids', [])
    if device_ids:
        devices = BioTimeDevice.query.filter(BioTimeDevice.id.in_(device_ids)).all()
        d.allowed_devices = devices

    db.session.commit()
    invalidate_department_cache()
    return jsonify({'ok': True, 'department': _serialize(d)}), 201


@departments_api_bp.route('/api/departments/update', methods=['POST'])
@admin_required
@safe_api
def update_department():
    data = request.get_json() or {}
    dept_id = data.get('department_id') or data.get('id')
    if not dept_id:
        return jsonify({'ok': False, 'msg': 'department_id مطلوب'}), 400
    d = Department.query.get(int(dept_id))
    if not d:
        return jsonify({'ok': False, 'msg': 'القسم غير موجود'}), 404

    name_ar = data.get('name_ar', '').strip()
    if name_ar:
        d.name_ar = name_ar
    new_code = data.get('code', '').strip()
    if new_code and new_code != d.code:
        existing = Department.query.filter_by(code=new_code).first()
        if existing:
            return jsonify({'ok': False, 'msg': f'الكود {new_code} مستخدم بالفعل'}), 400
        d.code = new_code
    if 'name_en' in data:
        d.name_en = data.get('name_en', '').strip() or None
    if 'icon' in data:
        d.icon = data.get('icon', d.icon)
    if 'color' in data:
        d.color = data.get('color', d.color)
    if 'description_ar' in data:
        d.description_ar = data.get('description_ar', '').strip() or None
    if 'description_en' in data:
        d.description_en = data.get('description_en', '').strip() or None
    if 'dept_type' in data:
        d.dept_type = data.get('dept_type', d.dept_type)
    if 'is_active' in data:
        d.is_active = bool(data['is_active'])
    if 'parent_id' in data:
        new_parent_id = data['parent_id']
        if new_parent_id is not None and int(new_parent_id) == d.id:
            return jsonify({'ok': False, 'msg': 'لا يمكن جعل القسم تابعاً لنفسه'}), 400
        d.parent_id = int(new_parent_id) if new_parent_id else None
        if d.parent_id:
            parent = Department.query.get(d.parent_id)
            d.dept_level = (parent.dept_level or 0) + 1 if parent else 1
        else:
            d.dept_level = 1
    if 'manager_id' in data:
        d.manager_id = int(data['manager_id']) if data.get('manager_id') else None
    if 'deputy_id' in data:
        d.deputy_id = int(data['deputy_id']) if data.get('deputy_id') else None
    if 'cost_center_code' in data:
        d.cost_center_code = data.get('cost_center_code', '').strip() or None
    if 'min_staff_required' in data:
        d.min_staff_required = int(data['min_staff_required'])
    if 'max_staff_capacity' in data:
        d.max_staff_capacity = int(data['max_staff_capacity'])
    if 'default_shift_id' in data:
        d.default_shift_id = int(data['default_shift_id']) if data.get('default_shift_id') else None
    if 'grace_period_override' in data:
        d.grace_period_override = int(data['grace_period_override']) if data.get('grace_period_override') else None
    if 'remote_work_allowed' in data:
        d.remote_work_allowed = bool(data['remote_work_allowed'])
    if 'certifications' in data:
        DepartmentCertification.query.filter_by(department_id=d.id).delete()
        for cert in data['certifications']:
            cert_name = cert.strip() if isinstance(cert, str) else cert.get('name', '').strip()
            if cert_name:
                db.session.add(DepartmentCertification(department_id=d.id, certification=cert_name))
    if 'allowed_device_ids' in data:
        device_ids = data['allowed_device_ids']
        d.allowed_devices = BioTimeDevice.query.filter(BioTimeDevice.id.in_(device_ids)).all() if device_ids else []

    d.updated_at = datetime.now(UTC)
    db.session.commit()
    invalidate_department_cache()
    return jsonify({'ok': True, 'department': _serialize(d)})
