from datetime import datetime, date, timedelta, UTC
from sqlalchemy import and_
from models import db
from models.employee import Employee
from models.employee_enhanced import LeaveType, EmployeeLeaveBalance, EmployeeLeaveRequest


class LeaveService:

    @staticmethod
    def initialize_balances(employee_id, year):
        existing = EmployeeLeaveBalance.query.filter_by(
            employee_id=employee_id, year=year
        ).count()
        if existing:
            return False
        extended = Employee.query.get(employee_id).extended if Employee.query.get(employee_id) else None
        leave_types = LeaveType.query.filter_by(is_active=True, is_recurring=True).all()
        for lt in leave_types:
            default = lt.default_days
            if lt.code == 'annual' and extended:
                default = extended.annual_leave_days or default
            elif lt.code == 'sick' and extended:
                default = extended.sick_leave_days or default
            elif lt.code == 'maternity' and extended:
                default = extended.maternity_leave_days or default
            balance = EmployeeLeaveBalance(
                employee_id=employee_id,
                leave_type_id=lt.id,
                year=year,
                total_days=default,
                used_days=0.0,
                remaining_days=default,
                carried_over=0.0,
            )
            db.session.add(balance)
        db.session.commit()
        return True

    @staticmethod
    def request_leave(employee_id, leave_type_id, start_date, end_date,
                      reason=None, attachment=None):
        lt = LeaveType.query.get(leave_type_id)
        if not lt or not lt.is_active:
            return {'success': False, 'error': 'Leave type not found or inactive'}
        total_days = (end_date - start_date).days + 1
        if total_days <= 0:
            return {'success': False, 'error': 'Invalid date range'}
        if lt.max_consecutive and total_days > lt.max_consecutive:
            return {'success': False, 'error': f'Max consecutive days is {lt.max_consecutive}'}
        year = start_date.year
        balance = EmployeeLeaveBalance.query.filter_by(
            employee_id=employee_id, leave_type_id=leave_type_id, year=year
        ).first()
        if not balance:
            LeaveService.initialize_balances(employee_id, year)
            balance = EmployeeLeaveBalance.query.filter_by(
                employee_id=employee_id, leave_type_id=leave_type_id, year=year
            ).first()
        if balance and total_days > balance.remaining_days:
            return {'success': False, 'error': f'Insufficient balance. Remaining: {balance.remaining_days}'}
        overlapping = EmployeeLeaveRequest.query.filter(
            EmployeeLeaveRequest.employee_id == employee_id,
            EmployeeLeaveRequest.status.in_(['pending', 'approved']),
            EmployeeLeaveRequest.start_date <= end_date,
            EmployeeLeaveRequest.end_date >= start_date,
        ).first()
        if overlapping:
            return {'success': False, 'error': 'Overlapping leave request exists'}
        request = EmployeeLeaveRequest(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            status='pending',
            attachment=attachment,
        )
        db.session.add(request)
        db.session.commit()
        return {'success': True, 'request': request.to_dict()}

    @staticmethod
    def approve_leave(request_id, reviewer_id, comment=None):
        req = EmployeeLeaveRequest.query.get(request_id)
        if not req:
            return {'success': False, 'error': 'Leave request not found'}
        if req.status != 'pending':
            return {'success': False, 'error': f'Request already {req.status}'}
        req.status = 'approved'
        req.reviewed_by = reviewer_id
        req.review_comment = comment
        req.reviewed_at = datetime.now(UTC)
        balance = EmployeeLeaveBalance.query.filter_by(
            employee_id=req.employee_id,
            leave_type_id=req.leave_type_id,
            year=req.start_date.year
        ).first()
        if balance:
            balance.used_days += req.total_days
            balance.remaining_days = balance.total_days - balance.used_days
        db.session.commit()
        return {'success': True, 'request': req.to_dict()}

    @staticmethod
    def reject_leave(request_id, reviewer_id, comment=None):
        req = EmployeeLeaveRequest.query.get(request_id)
        if not req:
            return {'success': False, 'error': 'Leave request not found'}
        if req.status != 'pending':
            return {'success': False, 'error': f'Request already {req.status}'}
        req.status = 'rejected'
        req.reviewed_by = reviewer_id
        req.review_comment = comment
        req.reviewed_at = datetime.now(UTC)
        db.session.commit()
        return {'success': True, 'request': req.to_dict()}

    @staticmethod
    def get_employee_balance(employee_id, year=None):
        year = year or date.today().year
        balances = EmployeeLeaveBalance.query.filter_by(
            employee_id=employee_id, year=year
        ).all()
        return [b.to_dict() for b in balances]

    @staticmethod
    def get_employee_requests(employee_id, status=None):
        q = EmployeeLeaveRequest.query.filter_by(employee_id=employee_id)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(EmployeeLeaveRequest.created_at.desc()).all()

    @staticmethod
    def get_pending_requests():
        return EmployeeLeaveRequest.query.filter_by(status='pending')\
            .order_by(EmployeeLeaveRequest.created_at.desc()).all()

    @staticmethod
    def carry_over_balance(employee_id, from_year, to_year):
        balances = EmployeeLeaveBalance.query.filter_by(
            employee_id=employee_id, year=from_year
        ).all()
        created = []
        for b in balances:
            remaining = b.remaining_days
            if remaining <= 0:
                continue
            lt = LeaveType.query.get(b.leave_type_id)
            max_carry = 15 if lt and lt.code == 'annual' else 0
            carry = min(remaining, max_carry)
            existing = EmployeeLeaveBalance.query.filter_by(
                employee_id=employee_id, leave_type_id=b.leave_type_id, year=to_year
            ).first()
            if existing:
                existing.carried_over += carry
                existing.total_days += carry
                existing.remaining_days = existing.total_days - existing.used_days
            else:
                nb = EmployeeLeaveBalance(
                    employee_id=employee_id,
                    leave_type_id=b.leave_type_id,
                    year=to_year,
                    total_days=carry,
                    used_days=0.0,
                    remaining_days=carry,
                    carried_over=carry,
                )
                db.session.add(nb)
                created.append(nb)
        db.session.commit()
        return {'carried': len(created) + sum(1 for _ in balances if _.remaining_days > 0)}

    @staticmethod
    def get_leave_types():
        return LeaveType.query.filter_by(is_active=True).all()
