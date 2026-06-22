"""
routes/scenarios.py — What-if scenario builder API endpoints.
Allows managers to simulate the impact of various workforce changes.
"""

from datetime import date, timedelta
from collections import defaultdict
from flask import Blueprint, render_template, request, jsonify
from models import db
from models.employee import Employee
from models.employee_enhanced import EmployeeLeaveRequest, EmployeeExtended
from models.attendance import AttendanceLog
from utils.decorators import admin_required
from sqlalchemy import func

scenarios_bp = Blueprint('scenarios', __name__)


@scenarios_bp.route('/admin/scenarios')
@admin_required
def scenarios_page():
    return render_template('admin/scenarios.html')


@scenarios_bp.route('/api/scenarios/simulate', methods=['POST'])
@admin_required
def simulate():
    data = request.get_json(force=True) or {}
    scenario_type = data.get('type', 'departure')
    params = data.get('params', {})
    simulator = ScenarioSimulator()
    result = simulator.run(scenario_type, params)
    return jsonify(result)


@scenarios_bp.route('/api/scenarios/presets')
@admin_required
def list_presets():
    return jsonify({
        'presets': [
            {
                'id': 'worst_case_week',
                'name': 'أسوأ أسبوع ممكن',
                'description': 'محاكاة غياب 30% من الموظفين في نفس الأسبوع',
                'params': {'absence_pct': 30, 'duration_days': 7},
            },
            {
                'id': 'ramadan_impact',
                'name': 'تأثير شهر رمضان',
                'description': 'محاكاة تأثير رمضان على ساعات العمل والحضور',
                'params': {'month': 'ramadan', 'reduced_hours': True},
            },
            {
                'id': 'key_departure',
                'name': 'رحيل موظف رئيسي',
                'description': 'محاكاة تأثير رحيل موظف رئيسي على الإنتاجية',
                'params': {'role': 'manager', 'count': 1},
            },
            {
                'id': 'mass_recruitment',
                'name': 'توظيف دفعة جديدة',
                'description': 'محاكاة تأثير توظيف 10 موظفين جدد',
                'params': {'new_hires': 10, 'training_weeks': 4},
            },
        ]
    })


class ScenarioSimulator:

    def run(self, scenario_type: str, params: dict) -> dict:
        handlers = {
            'departure': self._simulate_departure,
            'mass_absence': self._simulate_mass_absence,
            'leave_wave': self._simulate_leave_wave,
            'new_hire': self._simulate_new_hire,
            'budget_change': self._simulate_budget_change,
            'custom': self._simulate_custom,
        }
        handler = handlers.get(scenario_type, self._simulate_custom)
        return handler(params)

    def _simulate_departure(self, params: dict) -> dict:
        emp_id = params.get('employee_id')
        count = int(params.get('count', 1))
        if emp_id:
            emp = Employee.query.get(emp_id)
            if not emp:
                return {'error': 'الموظف غير موجود', 'scenario': 'departure'}
            employees = [emp]
            dept = emp.department
        else:
            dept = params.get('department')
            if dept:
                employees = Employee.query.filter_by(department=dept, is_active=True).limit(count).all()
            else:
                employees = Employee.query.filter_by(is_active=True).limit(count).all()
            if not employees:
                return {'error': 'لا يوجد موظفون', 'scenario': 'departure'}
        total_resource_loss = 0
        project_delay_days = 0
        total_salary_cost = 0
        for emp in employees:
            dept_total = Employee.query.filter_by(department=emp.department, is_active=True).count()
            total_resource_loss += (1 / max(dept_total, 1)) * 100
            project_delay_days += max(1, int(5 / max(dept_total, 1)))
            total_salary_cost += float(emp.base_salary or 0)
        hiring_cost = int(total_salary_cost * 1.5)
        weeks_to_replace = 8 + count * 2
        return {
            'scenario': 'departure',
            'scenario_name': f'رحيل {len(employees)} موظف',
            'impact': {
                'employees_leaving': len(employees),
                'resource_loss_pct': round(total_resource_loss, 1),
                'project_delay_days': project_delay_days,
                'total_salary_saved': int(total_salary_cost),
                'hiring_replacement_cost': hiring_cost,
                'weeks_to_full_recovery': weeks_to_replace,
            },
            'recommendation': f'بدء التوظيف فوراً. التكلفة التقديرية: {hiring_cost} د.ل. مدة التعافي: {weeks_to_replace} أسبوع.',
        }

    def _simulate_mass_absence(self, params: dict) -> dict:
        pct = float(params.get('percentage', 20))
        duration = int(params.get('duration_days', 3))
        dept = params.get('department')
        total_staff = 0
        affected = 0
        if dept:
            total_staff = Employee.query.filter_by(department=dept, is_active=True).count()
        else:
            total_staff = Employee.query.filter_by(is_active=True).count()
        affected = int(total_staff * pct / 100)
        available = total_staff - affected
        min_required = max(1, int(total_staff * 0.6))
        overtime_hours_needed = affected * duration * 2
        cost_per_overtime_hour = 15
        overtime_cost = overtime_hours_needed * cost_per_overtime_hour
        return {
            'scenario': 'mass_absence',
            'scenario_name': f'غياب {pct:.0f}% من الموظفين لمدة {duration} أيام',
            'impact': {
                'total_staff': total_staff,
                'absent': affected,
                'available': available,
                'min_required': min_required,
                'status': 'critical' if available < min_required else 'warning',
                'overtime_hours_needed': overtime_hours_needed,
                'overtime_cost_lyd': overtime_cost,
                'service_disruption_pct': round((1 - available / max(min_required, 1)) * 100, 1) if available < min_required else 0,
            },
            'recommendation': f'استدعاء {affected} موظف بديل. تكلفة الساعات الإضافية: {overtime_cost} د.ل.',
        }

    def _simulate_leave_wave(self, params: dict) -> dict:
        count = int(params.get('count', 5))
        dept = params.get('department')
        start_date = date.today() + timedelta(days=7)
        employees = []
        if dept:
            employees = Employee.query.filter_by(department=dept, is_active=True).limit(count * 2).all()
        else:
            employees = Employee.query.filter_by(is_active=True).limit(count * 2).all()
        if len(employees) < count:
            count = len(employees)
        affected = employees[:count]
        dept_impact = defaultdict(lambda: {'count': 0, 'total': 0})
        for emp in affected:
            dept_impact[emp.department]['count'] += 1
        for dept_name in dept_impact:
            dept_impact[dept_name]['total'] = Employee.query.filter_by(department=dept_name, is_active=True).count()
        impact_details = []
        for dept_name, info in dept_impact.items():
            remaining = info['total'] - info['count']
            min_req = max(1, int(info['total'] * 0.6))
            impact_details.append({
                'department': dept_name,
                'total': info['total'],
                'on_leave': info['count'],
                'remaining': remaining,
                'status': 'critical' if remaining < min_req else 'warning',
            })
        return {
            'scenario': 'leave_wave',
            'scenario_name': f'{count} موظف في إجازة في نفس الوقت',
            'start_date': start_date.isoformat(),
            'impact': {
                'employees_on_leave': count,
                'departments_affected': len(impact_details),
                'details': impact_details,
            },
            'recommendation': 'توزيع تواريخ الإجازات على فترات مختلفة لتجنب النقص',
        }

    def _simulate_new_hire(self, params: dict) -> dict:
        count = int(params.get('count', 5))
        dept = params.get('department')
        training_weeks = int(params.get('training_weeks', 4))
        if dept:
            current = Employee.query.filter_by(department=dept, is_active=True).count()
            name = dept
        else:
            current = Employee.query.filter_by(is_active=True).count()
            name = 'المؤسسة'
        new_total = current + count
        growth_pct = ((new_total / max(current, 1)) - 1) * 100
        monthly_cost_per_employee = 1500
        total_monthly_cost = monthly_cost_per_employee * count
        onboarding_cost = 2000 * count
        return {
            'scenario': 'new_hire',
            'scenario_name': f'توظيف {count} موظف جدد',
            'impact': {
                'department': name,
                'current_staff': current,
                'new_hires': count,
                'new_total': new_total,
                'growth_pct': round(growth_pct, 1),
                'training_weeks': training_weeks,
                'time_to_productivity': f'{training_weeks + 4} أسابيع',
                'monthly_salary_cost': monthly_cost_per_employee * count,
                'onboarding_cost': onboarding_cost,
                'total_first_year_cost': onboarding_cost + monthly_cost_per_employee * count * 12,
            },
            'recommendation': f'بدء المقابلات. الميزانية المقترحة: {onboarding_cost + monthly_cost_per_employee * 3} د.ل للربع الأول',
        }

    def _simulate_budget_change(self, params: dict) -> dict:
        pct = float(params.get('percentage', 10))
        direction = params.get('direction', 'cut')
        multiplier = -1 if direction == 'cut' else 1
        all_emps = Employee.query.filter_by(is_active=True).all()
        total_salary = sum(float(e.base_salary or 0) for e in all_emps)
        change_amount = total_salary * (pct / 100) * multiplier
        new_budget = float(total_salary) + change_amount
        employees = Employee.query.filter_by(is_active=True).count()
        if direction == 'cut' and pct > 15:
            risk_increase = 'high'
            likely_turnover = int(employees * 0.15)
        elif direction == 'cut':
            risk_increase = 'medium'
            likely_turnover = int(employees * 0.05)
        else:
            risk_increase = 'low'
            likely_turnover = 0
        return {
            'scenario': 'budget_change',
            'scenario_name': f'{"تخفيض" if direction == "cut" else "زيادة"} الميزانية بنسبة {pct:.0f}%',
            'impact': {
                'current_budget': float(total_salary),
                'change_amount': abs(change_amount),
                'new_budget': new_budget,
                'direction': direction,
                'risk_increase': risk_increase,
                'likely_turnover': likely_turnover,
                'per_employee_impact': round(abs(change_amount) / max(employees, 1)),
            },
            'recommendation': 'تخفيض ساعات العمل بدلاً من الرواتب' if direction == 'cut' else 'زيادة الميزانية التدريبية',
        }

    def _simulate_custom(self, params: dict) -> dict:
        return {
            'scenario': 'custom',
            'scenario_name': params.get('name', 'سيناريو مخصص'),
            'params': params,
            'impact': {'note': 'تم تسجيل السيناريو المخصص'},
            'recommendation': 'حلل النتائج واتخذ الإجراء المناسب',
        }
