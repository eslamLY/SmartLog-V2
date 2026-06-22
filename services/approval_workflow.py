from datetime import datetime, date, timedelta, UTC
from models import db
from models.employee import Employee
from models.payroll import ApprovalWorkflow, ApprovalStep, PayrollAuditLog


class ApprovalEngine:
    @staticmethod
    def create_approval_workflow(employee_id, proposed_gross, proposed_net=None,
                                  month=None, year=None, reason='', created_by=None):
        emp = Employee.query.get(employee_id)
        if not emp:
            return {'ok': False, 'msg': 'الموظف غير موجود'}
        today = date.today()
        month = month or today.month
        year = year or today.year
        existing = ApprovalWorkflow.query.filter_by(
            employee_id=employee_id, month=month, year=year, status='pending'
        ).first()
        if existing:
            return {'ok': False, 'msg': 'يوجد طلب موافقة معلق لهذا الموظف'}
        proposed_net = proposed_net or proposed_gross
        wf = ApprovalWorkflow(
            employee_id=employee_id,
            month=month,
            year=year,
            current_gross=emp.base_salary,
            proposed_gross=proposed_gross,
            proposed_net=proposed_net,
            status='pending',
            current_step=1,
            total_steps=2,
            notes=reason,
        )
        db.session.add(wf)
        db.session.flush()
        managers = Employee.query.filter_by(role='admin', is_active=True).order_by(Employee.id).all()
        approvers = managers[:2]
        if not approvers:
            return {'ok': False, 'msg': 'لا يوجد مدراء للموافقة'}
        for idx, mgr in enumerate(approvers):
            step = ApprovalStep(
                workflow_id=wf.id,
                step_order=idx + 1,
                approver_id=mgr.id,
                approver_name=mgr.full_name,
                status='pending',
            )
            db.session.add(step)
        db.session.commit()
        PayrollAuditLog.log(
            action='initiate_approval',
            employee_id=employee_id,
            changed_by=created_by,
            details=f'إنشاء طلب موافقة راتب: {emp.base_salary} -> {proposed_gross} د.ل',
        )
        return {'ok': True, 'msg': 'تم إنشاء طلب الموافقة', 'workflow_id': wf.id}

    @staticmethod
    def process_step(workflow_id, action, comment='', user_id=None):
        wf = ApprovalWorkflow.query.get(workflow_id)
        if not wf:
            return {'ok': False, 'msg': 'طلب الموافقة غير موجود'}
        if wf.status != 'pending':
            return {'ok': False, 'msg': f'الطلب已 {wf.status}'}
        if action not in ('approve', 'reject', 'request_changes'):
            return {'ok': False, 'msg': 'إجراء غير صالح'}
        step = ApprovalStep.query.filter_by(
            workflow_id=workflow_id, step_order=wf.current_step, status='pending'
        ).first()
        if not step:
            return {'ok': False, 'msg': 'لا توجد خطوة موافقة معلقة'}
        step.status = action
        step.comment = comment
        step.acted_at = datetime.now(UTC)
        step.acted_by = user_id
        if action == 'reject':
            wf.status = 'rejected'
            wf.reviewed_at = datetime.now(UTC)
            wf.reviewed_by = user_id
        elif action == 'request_changes':
            wf.status = 'changes_requested'
        elif action == 'approve':
            if wf.current_step >= wf.total_steps:
                wf.status = 'approved'
                wf.reviewed_at = datetime.now(UTC)
                wf.reviewed_by = user_id
                emp = Employee.query.get(wf.employee_id)
                if emp:
                    emp.base_salary = wf.proposed_gross
            else:
                wf.current_step += 1
        db.session.commit()
        emp = Employee.query.get(wf.employee_id)
        PayrollAuditLog.log(
            action=f'approval_{action}',
            employee_id=wf.employee_id,
            changed_by=user_id,
            details=f'{action} على طلب الموافقة لـ {emp.full_name if emp else ""}',
        )
        status_map = {'approved': 'تمت الموافقة', 'rejected': 'مرفوض', 'changes_requested': 'طلب تعديل'}
        return {
            'ok': True,
            'msg': status_map.get(action, 'تم التحديث'),
            'workflow_id': wf.id,
            'status': wf.status,
            'current_step': wf.current_step,
        }

    @staticmethod
    def get_pending_approvals(month=None, year=None, dept=None):
        qry = ApprovalWorkflow.query.filter_by(status='pending')
        if month and year:
            qry = qry.filter_by(month=month, year=year)
        if dept:
            qry = qry.join(Employee).filter(Employee.department == dept)
        workflows = qry.order_by(ApprovalWorkflow.created_at.desc()).all()
        results = []
        for wf in workflows:
            emp = Employee.query.get(wf.employee_id)
            results.append({
                'id': wf.id,
                'employee_id': wf.employee_id,
                'employee_name': emp.full_name if emp else '',
                'employee_username': emp.username if emp else '',
                'department': emp.department if emp else '',
                'current_gross': wf.current_gross,
                'proposed_gross': wf.proposed_gross,
                'proposed_net': wf.proposed_net,
                'status': wf.status,
                'current_step': wf.current_step,
                'total_steps': wf.total_steps,
                'created_at': wf.created_at.isoformat() if wf.created_at else '',
                'notes': wf.notes or '',
            })
        return results

    @staticmethod
    def get_approval_history(employee_id=None, limit=50):
        qry = ApprovalWorkflow.query
        if employee_id:
            qry = qry.filter_by(employee_id=employee_id)
        workflows = qry.order_by(ApprovalWorkflow.created_at.desc()).limit(limit).all()
        results = []
        for wf in workflows:
            emp = Employee.query.get(wf.employee_id)
            steps = ApprovalStep.query.filter_by(workflow_id=wf.id).order_by(ApprovalStep.step_order).all()
            results.append({
                'id': wf.id,
                'employee_name': emp.full_name if emp else '',
                'month': wf.month,
                'year': wf.year,
                'current_gross': wf.current_gross,
                'proposed_gross': wf.proposed_gross,
                'status': wf.status,
                'steps': [{
                    'order': s.step_order,
                    'approver': s.approver_name,
                    'status': s.status,
                    'comment': s.comment,
                    'acted_at': s.acted_at.isoformat() if s.acted_at else '',
                } for s in steps],
                'created_at': wf.created_at.isoformat() if wf.created_at else '',
            })
        return results

    @staticmethod
    def bulk_approve(workflow_ids, user_id=None):
        results = []
        for wid in workflow_ids:
            result = ApprovalEngine.process_step(wid, 'approve', 'موافقة جماعية', user_id)
            results.append({'id': wid, 'ok': result['ok'], 'msg': result['msg']})
        return results

    @staticmethod
    def cancel_workflow(workflow_id, reason='', user_id=None):
        wf = ApprovalWorkflow.query.get(workflow_id)
        if not wf:
            return {'ok': False, 'msg': 'غير موجود'}
        wf.status = 'cancelled'
        wf.notes = (wf.notes or '') + f'\nألغي: {reason}'
        db.session.commit()
        PayrollAuditLog.log(
            action='cancel_approval',
            employee_id=wf.employee_id,
            changed_by=user_id,
            details=f'إلغاء طلب الموافقة: {reason}',
        )
        return {'ok': True, 'msg': 'تم إلغاء الطلب'}
