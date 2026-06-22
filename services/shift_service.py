from datetime import datetime, date, UTC
from collections import defaultdict

from models import db, Employee, ShiftType, ShiftSchedule, ShiftSwapRequest
from models import ShiftCoverageRule, ShiftException
from models import LeaveRequest, OutingRequest
from utils.helpers import coverage_status as simple_coverage_status


def check_employee_availability(employee_id, sched_date, exclude_schedule_id=None):
    conflicts = []
    q = ShiftSchedule.query.filter_by(
        employee_id=employee_id, scheduled_date=sched_date, status='confirmed')
    if exclude_schedule_id:
        q = q.filter(ShiftSchedule.id != exclude_schedule_id)
    if q.count() > 0:
        conflicts.append(('duplicate', 'لديه مناوبة في هذا اليوم'))

    leave = LeaveRequest.query.filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= sched_date,
        db.or_(LeaveRequest.end_date.is_(None), LeaveRequest.end_date >= sched_date)
    ).first()
    if leave:
        conflicts.append(('leave_conflict', f'إجازة {leave.request_type} من {leave.start_date} إلى {leave.end_date or "غير محدد"})'))

    outing = OutingRequest.query.filter_by(
        employee_id=employee_id, outing_date=sched_date, status='approved'
    ).first()
    if outing:
        conflicts.append(('outing_conflict', f'أذن خروج: {outing.reason or "بدون سبب"}'))

    return conflicts


def get_schedule_conflicts(employee_id, sched_date):
    return check_employee_availability(employee_id, sched_date)


def validate_coverage(sched_date, shift_type_id, department=None):
    st = ShiftType.query.get(shift_type_id)
    if not st:
        return {'status': 'unknown', 'count': 0, 'min_staff': 0}

    count = ShiftSchedule.query.filter_by(
        shift_type_id=shift_type_id, scheduled_date=sched_date,
        status='confirmed').count()

    dow = sched_date.weekday()
    rule = ShiftCoverageRule.query.filter_by(
        shift_type_id=shift_type_id, is_active=True
    ).filter(
        db.or_(ShiftCoverageRule.department.is_(None), ShiftCoverageRule.department == department)
    ).filter(
        db.or_(ShiftCoverageRule.day_of_week.is_(None), ShiftCoverageRule.day_of_week == dow)
    ).order_by(
        ShiftCoverageRule.day_of_week.desc().nullslast(),
        ShiftCoverageRule.department.desc().nullslast()
    ).first()

    min_staff = rule.min_staff if rule else st.min_staff
    max_staff = rule.max_staff if rule and rule.max_staff else st.max_staff
    status, color = simple_coverage_status(count, min_staff)

    return {
        'status': status, 'color': color, 'count': count,
        'min_staff': min_staff, 'max_staff': max_staff,
        'rule_id': rule.id if rule else None,
    }


def auto_find_substitute(shift_schedule_id, department=None):
    ss = ShiftSchedule.query.get(shift_schedule_id)
    if not ss:
        return []

    st = ss.shift_type
    sched_date = ss.scheduled_date
    dept = department or (Employee.query.get(ss.employee_id).department if ss.employee_id else None)

    candidates = Employee.query.filter_by(is_active=True, role='employee')
    if dept:
        candidates = candidates.filter_by(department=dept)

    available = []
    for emp in candidates.all():
        if emp.id == ss.employee_id:
            continue
        conflicts = check_employee_availability(emp.id, sched_date)
        if not conflicts:
            existing = ShiftSchedule.query.filter_by(
                employee_id=emp.id, scheduled_date=sched_date).first()
            if not existing:
                available.append({
                    'id': emp.id, 'name': emp.full_name,
                    'department': emp.department,
                })
    return available


def apply_leave_conflicts(leave_request):
    if leave_request.status != 'approved':
        return 0

    schedules = ShiftSchedule.query.filter_by(
        employee_id=leave_request.employee_id, status='confirmed'
    ).filter(
        ShiftSchedule.scheduled_date >= leave_request.start_date
    ).filter(
        db.or_(
            ShiftSchedule.scheduled_date <= leave_request.end_date,
            leave_request.end_date.is_(None)
        )
    ).all()

    now = datetime.now(UTC)
    count = 0
    for ss in schedules:
        ss.conflict_status = 'leave_conflict'
        existing_exception = ShiftException.query.filter_by(
            employee_id=leave_request.employee_id,
            shift_schedule_id=ss.id,
            exception_type='leave'
        ).first()
        if not existing_exception:
            db.session.add(ShiftException(
                employee_id=leave_request.employee_id,
                shift_schedule_id=ss.id,
                exception_date=ss.scheduled_date,
                exception_type='leave',
                reason=f'إجازة {leave_request.request_type}'
            ))
        count += 1
    db.session.commit()
    return count


def resolve_conflicts_for_date(sched_date):
    schedules = ShiftSchedule.query.filter_by(
        scheduled_date=sched_date, status='confirmed'
    ).all()

    updated = 0
    for ss in schedules:
        conflicts = check_employee_availability(ss.employee_id, sched_date, exclude_schedule_id=ss.id)
        if conflicts:
            new_status = conflicts[0][0]
            if ss.conflict_status != new_status:
                ss.conflict_status = new_status
                updated += 1
        else:
            if ss.conflict_status != 'ok':
                ss.conflict_status = 'ok'
                updated += 1
    if updated:
        db.session.commit()
    return updated
