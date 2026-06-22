from datetime import datetime, date, UTC
from sqlalchemy import and_
from models import db
from models.employee import Employee
from models.employee_enhanced import (
    EmployeeGrade, EmployeePromotion, PromotionEligibility,
    EmployeeQualification, EmployeePerformance, EmployeeDisciplinaryAction
)


class PromotionService:

    @staticmethod
    def check_eligibility(employee_id):
        emp = Employee.query.get(employee_id)
        if not emp:
            return None
        extended = emp.extended
        if not extended or not extended.grade_id:
            return {'eligible': False, 'reason': 'No grade assigned'}
        current_grade = EmployeeGrade.query.get(extended.grade_id)
        if not current_grade:
            return {'eligible': False, 'reason': 'Grade not found'}
        target_grade = current_grade.next_grade
        if not target_grade:
            return {'eligible': False, 'reason': 'No higher grade available'}
        if emp.hire_date:
            service_years = date.today().year - emp.hire_date.year
        else:
            service_years = 0
        min_service_met = service_years >= (current_grade.min_years_for_promotion or 5)
        last_eval = EmployeePerformance.query.filter_by(
            employee_id=employee_id, status='completed'
        ).order_by(EmployeePerformance.created_at.desc()).first()
        performance_met = bool(last_eval and last_eval.score and last_eval.score >= 70)
        qual = EmployeeQualification.query.filter_by(employee_id=employee_id).first()
        required = current_grade.required_qualification
        qualifications_met = True
        if required and (not qual or qual.level != required):
            qualifications_met = False
        active_discipline = EmployeeDisciplinaryAction.query.filter(
            EmployeeDisciplinaryAction.employee_id == employee_id,
            EmployeeDisciplinaryAction.status == 'active'
        ).count()
        conduct_met = active_discipline == 0
        total = 4
        completed = sum([min_service_met, performance_met, qualifications_met, conduct_met])
        eligibility = PromotionEligibility.query.filter_by(employee_id=employee_id).first()
        if not eligibility:
            eligibility = PromotionEligibility(employee_id=employee_id)
        eligibility.current_grade_id = current_grade.id
        eligibility.target_grade_id = target_grade.id
        eligibility.min_service_met = min_service_met
        eligibility.performance_met = performance_met
        eligibility.qualifications_met = qualifications_met
        eligibility.conduct_met = conduct_met
        eligibility.total_requirements = total
        eligibility.completed_requirements = completed
        eligibility.last_evaluated_at = datetime.now(UTC)
        db.session.add(eligibility)
        db.session.commit()
        return {
            'eligible': completed == total,
            'current_grade': current_grade.name_ar,
            'target_grade': target_grade.name_ar,
            'current_salary': current_grade.base_salary,
            'target_salary': target_grade.base_salary,
            'service_years': service_years,
            'min_service_met': min_service_met,
            'performance_met': performance_met,
            'qualifications_met': qualifications_met,
            'conduct_met': conduct_met,
            'total_requirements': total,
            'completed_requirements': completed,
        }

    @staticmethod
    def execute_promotion(employee_id, decision_number=None, decision_date=None,
                          effective_date=None, approved_by=None, justification=None):
        emp = Employee.query.get(employee_id)
        if not emp:
            return {'success': False, 'error': 'Employee not found'}
        extended = emp.extended
        if not extended or not extended.grade_id:
            return {'success': False, 'error': 'No grade assigned'}
        current_grade = EmployeeGrade.query.get(extended.grade_id)
        target_grade = current_grade.next_grade if current_grade else None
        if not target_grade:
            return {'success': False, 'error': 'No higher grade available'}
        check = PromotionService.check_eligibility(employee_id)
        if not check or not check['eligible']:
            return {'success': False, 'error': 'Employee not eligible for promotion'}
        eff_date = effective_date or date.today()
        dec_date = decision_date or date.today()
        from_salary = current_grade.base_salary + current_grade.responsibility_allowance \
                      + current_grade.hazard_allowance + current_grade.transport_allowance \
                      + current_grade.housing_allowance
        to_salary = target_grade.base_salary + target_grade.responsibility_allowance \
                    + target_grade.hazard_allowance + target_grade.transport_allowance \
                    + target_grade.housing_allowance
        promotion = EmployeePromotion(
            employee_id=employee_id,
            from_grade_id=current_grade.id,
            to_grade_id=target_grade.id,
            from_grade_name=current_grade.name_ar,
            to_grade_name=target_grade.name_ar,
            from_salary=from_salary,
            to_salary=to_salary,
            decision_number=decision_number,
            decision_date=dec_date,
            effective_date=eff_date,
            approved_by=approved_by,
            justification=justification,
            status='completed',
        )
        db.session.add(promotion)
        extended.grade_id = target_grade.id
        db.session.commit()
        return {'success': True, 'promotion': promotion.to_dict()}

    @staticmethod
    def get_promotion_history(employee_id):
        return EmployeePromotion.query.filter_by(employee_id=employee_id)\
            .order_by(EmployeePromotion.effective_date.desc()).all()

    @staticmethod
    def get_pending_promotions():
        return EmployeePromotion.query.filter_by(status='pending')\
            .order_by(EmployeePromotion.created_at.desc()).all()

    @staticmethod
    def get_eligible_employees():
        employees = Employee.query.filter(
            Employee.role == 'employee', Employee.is_active == True
        ).all()
        results = []
        for emp in employees:
            if emp.extended and emp.extended.grade_id:
                grade = EmployeeGrade.query.get(emp.extended.grade_id)
                if grade and grade.next_grade_id:
                    check = PromotionService.check_eligibility(emp.id)
                    results.append({
                        'employee': emp,
                        'eligibility': check,
                    })
        return results

    @staticmethod
    def get_grade_chain():
        grades = EmployeeGrade.query.filter_by(is_active=True)\
            .order_by(EmployeeGrade.level).all()
        return [g.to_dict() for g in grades]
