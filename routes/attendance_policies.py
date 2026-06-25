import logging
from datetime import datetime, UTC
from flask import Blueprint, render_template, request, session, jsonify
from functools import wraps
from models import db, AttendancePolicy, Department, ShiftType
from utils.decorators import admin_required

attendance_policies_bp = Blueprint('attendance_policies_bp', __name__)

LOGGER = logging.getLogger(__name__)


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper


@attendance_policies_bp.route('/admin/attendance-policies')
@admin_required
def admin_attendance_policies():
    policies = AttendancePolicy.query.order_by(AttendancePolicy.is_active.desc(), AttendancePolicy.id.desc()).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    shift_types = ShiftType.query.filter_by(is_active=True).order_by(ShiftType.name).all()
    return render_template('admin/attendance_policies.html',
                           policies=policies, departments=departments, shift_types=shift_types)


@attendance_policies_bp.route('/api/attendance-policies')
@admin_required
@safe_api
def api_attendance_policies():
    policies = AttendancePolicy.query.order_by(AttendancePolicy.is_active.desc(), AttendancePolicy.id.desc()).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'department_name': p.department.name_ar if p.department else None,
        'shift_type_name': p.shift_type.name if p.shift_type else None,
        'late_grace_minutes': p.late_grace_minutes,
        'early_leave_grace': p.early_leave_grace,
        'max_late_minutes': p.max_late_minutes,
        'min_work_hours': p.min_work_hours,
        'overtime_threshold_h': p.overtime_threshold_h,
        'overtime_multiplier': p.overtime_multiplier,
        'auto_deduct_absence': p.auto_deduct_absence,
        'allow_geofence_override': p.allow_geofence_override,
        'require_selfie': p.require_selfie,
        'max_early_leave_min': p.max_early_leave_min,
        'is_active': p.is_active,
    } for p in policies])


@attendance_policies_bp.route('/api/attendance-policies/add', methods=['POST'])
@admin_required
@safe_api
def api_add_policy():
    d = request.get_json() or {}
    name = d.get('name', '').strip()
    if not name:
        return jsonify({'ok': False, 'msg': 'اسم السياسة مطلوب.'})
    dept_id = int(d['department_id']) if d.get('department_id') else None
    shift_id = int(d['shift_type_id']) if d.get('shift_type_id') else None
    existing = AttendancePolicy.query.filter_by(name=name).first()
    if existing:
        return jsonify({'ok': False, 'msg': 'سياسة بنفس الاسم موجودة مسبقاً.'})
    policy = AttendancePolicy(
        name=name,
        department_id=dept_id,
        shift_type_id=shift_id,
        late_grace_minutes=int(d.get('late_grace_minutes', 15)),
        early_leave_grace=int(d.get('early_leave_grace', 10)),
        max_late_minutes=int(d.get('max_late_minutes', 120)),
        min_work_hours=float(d.get('min_work_hours', 6.0)),
        overtime_threshold_h=float(d.get('overtime_threshold_h', 8.0)),
        overtime_multiplier=float(d.get('overtime_multiplier', 1.5)),
        auto_deduct_absence=bool(d.get('auto_deduct_absence', False)),
        allow_geofence_override=bool(d.get('allow_geofence_override', False)),
        require_selfie=bool(d.get('require_selfie', False)),
        max_early_leave_min=int(d.get('max_early_leave_min', 60)),
    )
    db.session.add(policy)
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'✓ تم إنشاء سياسة "{policy.name}".'})


@attendance_policies_bp.route('/api/attendance-policies/<int:pid>/edit', methods=['POST'])
@admin_required
@safe_api
def api_edit_policy(pid):
    policy = AttendancePolicy.query.get_or_404(pid)
    d = request.get_json() or {}
    if 'name' in d:
        policy.name = str(d['name']).strip()
    for field in ('late_grace_minutes', 'early_leave_grace', 'max_late_minutes',
                  'max_early_leave_min'):
        if field in d:
            setattr(policy, field, int(d[field]))
    for field in ('min_work_hours', 'overtime_threshold_h', 'overtime_multiplier'):
        if field in d:
            setattr(policy, field, float(d[field]))
    for bool_field in ('auto_deduct_absence', 'allow_geofence_override', 'require_selfie'):
        if bool_field in d:
            setattr(policy, bool_field, bool(d[bool_field]))
    if 'department_id' in d:
        policy.department_id = int(d['department_id']) if d['department_id'] else None
    if 'shift_type_id' in d:
        policy.shift_type_id = int(d['shift_type_id']) if d['shift_type_id'] else None
    policy.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'✓ تم تحديث سياسة "{policy.name}".'})


@attendance_policies_bp.route('/api/attendance-policies/<int:pid>/toggle', methods=['POST'])
@admin_required
@safe_api
def api_toggle_policy(pid):
    policy = AttendancePolicy.query.get_or_404(pid)
    policy.is_active = not policy.is_active
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'{"تم التفعيل" if policy.is_active else "تم التعطيل"}'})


@attendance_policies_bp.route('/api/attendance-policies/<int:pid>/delete', methods=['POST'])
@admin_required
@safe_api
def api_delete_policy(pid):
    policy = AttendancePolicy.query.get_or_404(pid)
    name = policy.name
    db.session.delete(policy)
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'✓ تم حذف سياسة "{name}".'})


@attendance_policies_bp.route('/api/attendance-policies/<int:pid>')
@admin_required
@safe_api
def api_get_policy(pid):
    p = AttendancePolicy.query.get_or_404(pid)
    return jsonify({
        'id': p.id,
        'name': p.name,
        'department_id': p.department_id,
        'shift_type_id': p.shift_type_id,
        'late_grace_minutes': p.late_grace_minutes,
        'early_leave_grace': p.early_leave_grace,
        'max_late_minutes': p.max_late_minutes,
        'min_work_hours': p.min_work_hours,
        'overtime_threshold_h': p.overtime_threshold_h,
        'overtime_multiplier': p.overtime_multiplier,
        'auto_deduct_absence': p.auto_deduct_absence,
        'allow_geofence_override': p.allow_geofence_override,
        'require_selfie': p.require_selfie,
        'max_early_leave_min': p.max_early_leave_min,
        'is_active': p.is_active,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    })
