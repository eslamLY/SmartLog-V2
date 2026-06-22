from flask import Blueprint, request, jsonify, render_template
from models import db
from models.rbac import (
    RbacRole, RbacPermission, RbacEmployeeRole,
    RbacAuditLog, RbacPermissionRequest, RbacRoleTemplate, RbacDelegation
)
from models.employee import Employee
from services.permission_service import (
    list_permissions, create_role, update_role, delete_role,
    assign_role, revoke_role, bulk_assign_roles, check_permission,
    get_employee_permissions, get_permission_matrix, get_role_assignments,
    get_employee_roles, create_permission_request, review_permission_request,
    create_delegation, revoke_delegation, auto_revoke_expired_delegations
)
from services.audit_service import (
    log_role_creation, log_role_update, log_role_delete,
    log_assignment, log_revocation, log_bulk_assign,
    log_permission_request, log_request_review,
    log_delegation, log_delegation_revoke,
    get_audit_logs, get_entity_history
)
from utils.decorators import login_required, admin_required

rbac_bp = Blueprint('rbac', __name__, url_prefix='/admin/rbac')

@rbac_bp.route('')
@login_required
def rbac_dashboard():
    return render_template('admin/rbac_dashboard.html')

@rbac_bp.route('/roles')
@login_required
def roles_page():
    return render_template('admin/roles_management.html')

@rbac_bp.route('/permissions')
@login_required
def permissions_page():
    return render_template('admin/permissions_management.html')

@rbac_bp.route('/assignments')
@login_required
def assignments_page():
    return render_template('admin/employee_assignments.html')

@rbac_bp.route('/analytics')
@login_required
def analytics_page():
    return render_template('admin/rbac_analytics.html')

@rbac_bp.route('/api/roles', methods=['GET'])
@login_required
def api_list_roles():
    roles = RbacRole.query.order_by(RbacRole.name).all()
    return jsonify({'ok': True, 'roles': [r.to_dict() for r in roles]})

@rbac_bp.route('/api/roles', methods=['POST'])
@login_required
def api_create_role():
    data = request.get_json()
    role = create_role(data, request.user_id)
    log_role_creation(role, request.user_id,
        ip_address=request.remote_addr, user_agent=request.user_agent.string if hasattr(request, 'user_agent') else None)
    return jsonify({'ok': True, 'role': role.to_dict()})

@rbac_bp.route('/api/roles/<int:role_id>', methods=['PUT'])
@login_required
def api_update_role(role_id):
    data = request.get_json()
    role = update_role(role_id, data, request.user_id)
    return jsonify({'ok': True, 'role': role.to_dict()})

@rbac_bp.route('/api/roles/<int:role_id>', methods=['DELETE'])
@login_required
def api_delete_role(role_id):
    try:
        role = RbacRole.query.get_or_404(role_id)
        role_name = role.name
        delete_role(role_id)
        log_role_delete(role_id, role_name, request.user_id,
            ip_address=request.remote_addr)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@rbac_bp.route('/api/roles/<int:role_id>', methods=['GET'])
@login_required
def api_get_role(role_id):
    role = RbacRole.query.get_or_404(role_id)
    return jsonify({'ok': True, 'role': role.to_dict()})

@rbac_bp.route('/api/permissions', methods=['GET'])
@login_required
def api_list_permissions():
    perms = list_permissions()
    return jsonify({'ok': True, 'permissions': [p.to_dict() for p in perms]})

@rbac_bp.route('/api/permissions', methods=['POST'])
@login_required
def api_create_permission():
    data = request.get_json()
    perm = RbacPermission(
        name=data['name'],
        name_ar=data.get('name_ar'),
        code=data['code'],
        description=data.get('description'),
        module=data.get('module'),
        is_high_risk=data.get('is_high_risk', False),
        requires_2fa=data.get('requires_2fa', False),
        requires_approval=data.get('requires_approval', False),
    )
    db.session.add(perm)
    db.session.commit()
    return jsonify({'ok': True, 'permission': perm.to_dict()})

@rbac_bp.route('/api/permissions/<int:perm_id>', methods=['PUT'])
@login_required
def api_update_permission(perm_id):
    perm = RbacPermission.query.get_or_404(perm_id)
    data = request.get_json()
    for field in ('name', 'name_ar', 'code', 'description', 'module', 'is_high_risk', 'requires_2fa', 'requires_approval'):
        if field in data:
            setattr(perm, field, data[field])
    db.session.commit()
    return jsonify({'ok': True, 'permission': perm.to_dict()})

@rbac_bp.route('/api/assignments', methods=['GET'])
@login_required
def api_list_assignments():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    q = RbacEmployeeRole.query.order_by(RbacEmployeeRole.assigned_at.desc())
    total = q.count()
    assigns = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({'ok': True, 'assignments': [a.to_dict() for a in assigns], 'total': total})

@rbac_bp.route('/api/assignments', methods=['POST'])
@login_required
def api_assign_role():
    data = request.get_json()
    er = assign_role(data, request.user_id)
    log_assignment(er, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True, 'assignment': er.to_dict()})

@rbac_bp.route('/api/assignments/<int:assignment_id>/revoke', methods=['POST'])
@login_required
def api_revoke_role(assignment_id):
    er = RbacEmployeeRole.query.get_or_404(assignment_id)
    revoke_role(assignment_id, request.user_id)
    log_revocation(er, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True})

@rbac_bp.route('/api/assignments/bulk', methods=['POST'])
@login_required
def api_bulk_assign():
    data = request.get_json()
    results = bulk_assign_roles(data, request.user_id)
    log_bulk_assign(results, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True, 'results': results})

@rbac_bp.route('/api/employee-permissions/<int:employee_id>', methods=['GET'])
@login_required
def api_employee_permissions(employee_id):
    perms = get_employee_permissions(employee_id)
    roles = get_employee_roles(employee_id)
    return jsonify({'ok': True, 'permissions': list(perms), 'roles': [r.to_dict() for r in roles]})

@rbac_bp.route('/api/permission-check', methods=['POST'])
@login_required
def api_check_permission():
    data = request.get_json()
    result = check_permission(data['employee_id'], data['permission_code'])
    return jsonify({'ok': True, 'has_permission': result})

@rbac_bp.route('/api/permission-matrix', methods=['POST'])
@login_required
def api_permission_matrix():
    data = request.get_json()
    result = get_permission_matrix(data['role_ids'])
    return jsonify({'ok': True, **result})

@rbac_bp.route('/api/audit-logs', methods=['GET'])
@login_required
def api_audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    entity_type = request.args.get('entity_type')
    action = request.args.get('action')
    logs, total = get_audit_logs(page=page, per_page=per_page, entity_type=entity_type, action=action)
    return jsonify({'ok': True, 'logs': [l.to_dict() for l in logs], 'total': total})

@rbac_bp.route('/api/permission-requests', methods=['GET'])
@login_required
def api_list_requests():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    q = RbacPermissionRequest.query.order_by(RbacPermissionRequest.created_at.desc())
    total = q.count()
    reqs = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({'ok': True, 'requests': [r.to_dict() for r in reqs], 'total': total})

@rbac_bp.route('/api/permission-requests', methods=['POST'])
@login_required
def api_create_request():
    data = request.get_json()
    pr = create_permission_request(data, request.user_id)
    log_permission_request(pr, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True, 'request': pr.to_dict()})

@rbac_bp.route('/api/permission-requests/<int:req_id>/review', methods=['POST'])
@login_required
def api_review_request(req_id):
    data = request.get_json()
    pr = review_permission_request(req_id, data, request.user_id)
    log_request_review(pr, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True, 'request': pr.to_dict()})

@rbac_bp.route('/api/delegations', methods=['GET'])
@login_required
def api_list_delegations():
    delegations = RbacDelegation.query.order_by(RbacDelegation.created_at.desc()).all()
    return jsonify({'ok': True, 'delegations': [d.to_dict() for d in delegations]})

@rbac_bp.route('/api/delegations', methods=['POST'])
@login_required
def api_create_delegation():
    data = request.get_json()
    dlg = create_delegation(data, request.user_id)
    log_delegation(dlg, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True, 'delegation': dlg.to_dict()})

@rbac_bp.route('/api/delegations/<int:dlg_id>/revoke', methods=['POST'])
@login_required
def api_revoke_delegation(dlg_id):
    dlg = RbacDelegation.query.get_or_404(dlg_id)
    revoke_delegation(dlg_id)
    log_delegation_revoke(dlg, request.user_id,
        ip_address=request.remote_addr)
    return jsonify({'ok': True})

@rbac_bp.route('/api/analytics', methods=['GET'])
@login_required
def api_analytics():
    total_roles = RbacRole.query.count()
    total_perms = RbacPermission.query.count()
    total_assignments = RbacEmployeeRole.query.filter_by(is_active=True).count()
    total_employees = Employee.query.filter_by(is_active=True).count()
    total_requests = RbacPermissionRequest.query.filter_by(status='pending').count()
    high_risk_count = RbacPermission.query.filter_by(is_high_risk=True).count()
    active_delegations = RbacDelegation.query.filter_by(is_active=True).count()
    roles_with_count = []
    for role in RbacRole.query.all():
        cnt = RbacEmployeeRole.query.filter_by(role_id=role.id, is_active=True).count()
        roles_with_count.append({'role': role.name, 'count': cnt})
    return jsonify({
        'ok': True,
        'total_roles': total_roles,
        'total_permissions': total_perms,
        'total_assignments': total_assignments,
        'total_employees': total_employees,
        'pending_requests': total_requests,
        'high_risk_permissions': high_risk_count,
        'active_delegations': active_delegations,
        'roles_distribution': roles_with_count,
        'coverage': round((total_assignments / total_employees * 100) if total_employees else 0, 1),
    })

@rbac_bp.route('/api/templates', methods=['GET'])
@login_required
def api_list_templates():
    tmpls = RbacRoleTemplate.query.all()
    return jsonify({'ok': True, 'templates': [t.to_dict() for t in tmpls]})

@rbac_bp.route('/api/templates', methods=['POST'])
@login_required
def api_create_template():
    data = request.get_json()
    tmpl = RbacRoleTemplate(
        name=data['name'],
        description=data.get('description'),
        permissions=','.join(data.get('permission_ids', [])),
        scope=data.get('scope', 'department'),
        risk_level=data.get('risk_level', 'low'),
    )
    db.session.add(tmpl)
    db.session.commit()
    return jsonify({'ok': True, 'template': tmpl.to_dict()})

@rbac_bp.route('/api/templates/<int:tmpl_id>/apply', methods=['POST'])
@login_required
def api_apply_template(tmpl_id):
    tmpl = RbacRoleTemplate.query.get_or_404(tmpl_id)
    data = request.get_json()
    perm_ids = [int(p) for p in tmpl.permissions.split(',') if p.strip().isdigit()] if tmpl.permissions else []
    role_data = {
        'name': data.get('name', tmpl.name),
        'description': tmpl.description,
        'scope': tmpl.scope,
        'risk_level': tmpl.risk_level,
        'permission_ids': perm_ids,
        'department_ids': data.get('department_ids', []),
    }
    role = create_role(role_data, request.user_id)
    return jsonify({'ok': True, 'role': role.to_dict()})

@rbac_bp.route('/api/employees', methods=['GET'])
@login_required
def api_employees_list():
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.full_name).all()
    return jsonify({
        'ok': True,
        'employees': [{
            'id': e.id, 'full_name': e.full_name,
            'department': e.department, 'job_title': e.job_title
        } for e in employees]
    })

@rbac_bp.route('/api/departments', methods=['GET'])
@login_required
def api_departments_list():
    from models.department import Department
    depts = Department.query.order_by(Department.name_ar).all()
    return jsonify({
        'ok': True,
        'departments': [{'id': d.id, 'name_ar': d.name_ar, 'code': d.code} for d in depts]
    })
