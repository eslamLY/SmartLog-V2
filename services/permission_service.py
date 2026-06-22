from datetime import datetime, date, UTC
from models import db
from models.rbac import (
    RbacRole, RbacPermission, RbacEmployeeRole,
    RbacAuditLog, RbacPermissionRequest, RbacDelegation
)
from models.employee import Employee

def get_employee_permissions(employee_id):
    roles = RbacEmployeeRole.query.filter_by(
        employee_id=employee_id, is_active=True
    ).all()
    perms = set()
    now = date.today()
    for er in roles:
        if er.expiry_date and er.expiry_date < now:
            continue
        role_perms = er.role.get_all_permissions() if er.role else set()
        perms |= role_perms
    delegations = RbacDelegation.query.filter_by(
        delegate_id=employee_id, is_active=True
    ).filter(
        RbacDelegation.end_date > datetime.now(UTC)
    ).all()
    for d in delegations:
        for pid in d.permission_ids.split(','):
            pid = pid.strip()
            if pid.isdigit():
                p = RbacPermission.query.get(int(pid))
                if p:
                    perms.add(p.code)
    return perms

def check_permission(employee_id, permission_code):
    perms = get_employee_permissions(employee_id)
    return permission_code in perms

def check_any_permission(employee_id, permission_codes):
    perms = get_employee_permissions(employee_id)
    return any(p in perms for p in permission_codes)

def check_all_permissions(employee_id, permission_codes):
    perms = get_employee_permissions(employee_id)
    return all(p in perms for p in permission_codes)

def list_permissions():
    return RbacPermission.query.order_by(RbacPermission.module, RbacPermission.name).all()

def get_permission_by_code(code):
    return RbacPermission.query.filter_by(code=code).first()

def create_role(data, performer_id):
    role = RbacRole(
        name=data['name'],
        name_ar=data.get('name_ar'),
        description=data.get('description'),
        parent_id=data.get('parent_id'),
        scope=data.get('scope', 'department'),
        risk_level=data.get('risk_level', 'low'),
        max_assignees=data.get('max_assignees'),
        created_by=performer_id,
    )
    db.session.add(role)
    db.session.flush()
    if data.get('permission_ids'):
        perms = RbacPermission.query.filter(RbacPermission.id.in_(data['permission_ids'])).all()
        role.permissions = perms
    if data.get('department_ids'):
        from models.department import Department
        depts = Department.query.filter(Department.id.in_(data['department_ids'])).all()
        role.departments = depts
    db.session.commit()
    return role

def update_role(role_id, data, performer_id):
    role = RbacRole.query.get_or_404(role_id)
    for field in ('name', 'name_ar', 'description', 'parent_id', 'scope', 'risk_level', 'max_assignees', 'is_active'):
        if field in data:
            setattr(role, field, data[field])
    if 'permission_ids' in data:
        perms = RbacPermission.query.filter(RbacPermission.id.in_(data['permission_ids'])).all()
        role.permissions = perms
    if 'department_ids' in data:
        from models.department import Department
        depts = Department.query.filter(Department.id.in_(data['department_ids'])).all()
        role.departments = depts
    role.updated_at = datetime.now(UTC)
    db.session.commit()
    return role

def delete_role(role_id):
    role = RbacRole.query.get_or_404(role_id)
    if role.is_system:
        raise ValueError('Cannot delete system role')
    db.session.delete(role)
    db.session.commit()

def assign_role(data, performer_id):
    er = RbacEmployeeRole(
        employee_id=data['employee_id'],
        role_id=data['role_id'],
        is_primary=data.get('is_primary', False),
        assignment_type=data.get('assignment_type', 'permanent'),
        effective_date=datetime.strptime(data['effective_date'], '%Y-%m-%d').date() if data.get('effective_date') else date.today(),
        expiry_date=datetime.strptime(data['expiry_date'], '%Y-%m-%d').date() if data.get('expiry_date') else None,
        season_months=','.join(data['season_months']) if data.get('season_months') else None,
        shift_type_ids=','.join(str(s) for s in data.get('shift_type_ids', [])) if data.get('shift_type_ids') else None,
        notes=data.get('notes'),
        assigned_by=performer_id,
    )
    db.session.add(er)
    db.session.commit()
    return er

def revoke_role(assignment_id, performer_id):
    er = RbacEmployeeRole.query.get_or_404(assignment_id)
    er.is_active = False
    er.revoked_at = datetime.now(UTC)
    er.revoked_by = performer_id
    db.session.commit()

def bulk_assign_roles(data, performer_id):
    results = []
    for emp_id in data['employee_ids']:
        try:
            er = RbacEmployeeRole(
                employee_id=emp_id,
                role_id=data['role_id'],
                assignment_type=data.get('assignment_type', 'permanent'),
                effective_date=datetime.strptime(data['effective_date'], '%Y-%m-%d').date() if data.get('effective_date') else date.today(),
                expiry_date=datetime.strptime(data['expiry_date'], '%Y-%m-%d').date() if data.get('expiry_date') else None,
                notes=data.get('notes'),
                assigned_by=performer_id,
            )
            db.session.add(er)
            results.append({'employee_id': emp_id, 'ok': True})
        except Exception as e:
            results.append({'employee_id': emp_id, 'ok': False, 'error': str(e)})
    db.session.commit()
    return results

def create_permission_request(data, employee_id):
    pr = RbacPermissionRequest(
        employee_id=employee_id,
        requested_perms=','.join(data.get('permission_codes', [])),
        justification=data.get('justification'),
        duration_days=data.get('duration_days'),
        risk_level=data.get('risk_level', 'low'),
    )
    db.session.add(pr)
    db.session.commit()
    return pr

def review_permission_request(request_id, data, reviewer_id):
    pr = RbacPermissionRequest.query.get_or_404(request_id)
    pr.status = data['status']
    pr.review_comment = data.get('review_comment')
    pr.reviewed_by = reviewer_id
    pr.reviewed_at = datetime.now(UTC)
    db.session.commit()
    return pr

def get_employee_roles(employee_id):
    return RbacEmployeeRole.query.filter_by(employee_id=employee_id).order_by(RbacEmployeeRole.assigned_at.desc()).all()

def get_role_assignments(role_id):
    return RbacEmployeeRole.query.filter_by(role_id=role_id, is_active=True).all()

def get_permission_matrix(role_ids):
    roles = RbacRole.query.filter(RbacRole.id.in_(role_ids)).all()
    all_perms = RbacPermission.query.order_by(RbacPermission.module, RbacPermission.name).all()
    matrix = []
    for p in all_perms:
        row = {'permission': p.to_dict()}
        for r in roles:
            row[f'role_{r.id}'] = p in r.permissions
        matrix.append(row)
    return {'roles': [r.to_dict() for r in roles], 'matrix': matrix}

def get_employee_effective_permissions(employee_id):
    perms = get_employee_permissions(employee_id)
    return list(perms)

def get_department_roles(department_id):
    from models.department import Department
    dept = Department.query.get(department_id)
    if not dept:
        return []
    roles = RbacRole.query.filter(
        RbacRole.departments.any(id=department_id)
    ).all()
    return roles

def get_high_risk_permissions():
    return RbacPermission.query.filter_by(is_high_risk=True).all()

def create_delegation(data, delegator_id):
    dlg = RbacDelegation(
        delegator_id=delegator_id,
        delegate_id=data['delegate_id'],
        permission_ids=','.join(str(p) for p in data.get('permission_ids', [])),
        end_date=datetime.strptime(data['end_date'], '%Y-%m-%d') if isinstance(data.get('end_date'), str) else data.get('end_date'),
        reason=data.get('reason'),
    )
    db.session.add(dlg)
    db.session.commit()
    return dlg

def revoke_delegation(delegation_id):
    dlg = RbacDelegation.query.get_or_404(delegation_id)
    dlg.is_active = False
    dlg.revoked_at = datetime.now(UTC)
    db.session.commit()

def auto_revoke_expired_delegations():
    expired = RbacDelegation.query.filter(
        RbacDelegation.is_active == True,
        RbacDelegation.end_date < datetime.now(UTC)
    ).all()
    for d in expired:
        d.is_active = False
        d.revoked_at = datetime.now(UTC)
    db.session.commit()
    return len(expired)
