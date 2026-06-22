import json
from datetime import datetime, UTC
from models import db
from models.rbac import RbacAuditLog

def log_action(action, entity_type, entity_id=None, changes=None,
               ip_address=None, user_agent=None, performed_by=None):
    log = RbacAuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=json.dumps(changes, ensure_ascii=False) if changes else None,
        ip_address=ip_address,
        user_agent=user_agent,
        performed_by=performed_by,
    )
    db.session.add(log)
    db.session.commit()
    return log

def log_role_creation(role, performer_id, ip=None, ua=None):
    return log_action('create', 'role', role.id,
        changes={'name': role.name, 'scope': role.scope},
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_role_update(role, before, after, performer_id, ip=None, ua=None):
    return log_action('update', 'role', role.id,
        changes={'before': before, 'after': after},
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_role_delete(role_id, role_name, performer_id, ip=None, ua=None):
    return log_action('delete', 'role', role_id,
        changes={'name': role_name},
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_assignment(employee_role, performer_id, ip=None, ua=None):
    return log_action('assign', 'employee_role', employee_role.id,
        changes={
            'employee_id': employee_role.employee_id,
            'role_id': employee_role.role_id,
            'assignment_type': employee_role.assignment_type,
        },
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_revocation(employee_role, performer_id, ip=None, ua=None):
    return log_action('revoke', 'employee_role', employee_role.id,
        changes={
            'employee_id': employee_role.employee_id,
            'role_id': employee_role.role_id,
        },
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_bulk_assign(results, performer_id, ip=None, ua=None):
    return log_action('bulk_assign', 'employee_role',
        changes={'count': len(results), 'results': results},
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_permission_request(pr, performer_id, ip=None, ua=None):
    return log_action('request', 'permission_request', pr.id,
        changes={
            'employee_id': pr.employee_id,
            'permissions': pr.requested_perms,
            'justification': pr.justification,
        },
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def log_request_review(pr, reviewer_id, ip=None, ua=None):
    return log_action('review', 'permission_request', pr.id,
        changes={
            'status': pr.status,
            'review_comment': pr.review_comment,
        },
        ip_address=ip, user_agent=ua, performed_by=reviewer_id)

def log_delegation(dlg, delegator_id, ip=None, ua=None):
    return log_action('delegate', 'delegation', dlg.id,
        changes={
            'delegator_id': dlg.delegator_id,
            'delegate_id': dlg.delegate_id,
            'permission_ids': dlg.permission_ids,
            'end_date': dlg.end_date.isoformat(),
        },
        ip_address=ip, user_agent=ua, performed_by=delegator_id)

def log_delegation_revoke(dlg, performer_id, ip=None, ua=None):
    return log_action('revoke_delegation', 'delegation', dlg.id,
        changes={
            'delegator_id': dlg.delegator_id,
            'delegate_id': dlg.delegate_id,
        },
        ip_address=ip, user_agent=ua, performed_by=performer_id)

def get_audit_logs(page=1, per_page=50, entity_type=None, action=None):
    q = RbacAuditLog.query
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    if action:
        q = q.filter_by(action=action)
    total = q.count()
    logs = q.order_by(RbacAuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return logs, total

def get_entity_history(entity_type, entity_id, page=1, per_page=50):
    q = RbacAuditLog.query.filter_by(entity_type=entity_type, entity_id=entity_id)
    total = q.count()
    logs = q.order_by(RbacAuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return logs, total
