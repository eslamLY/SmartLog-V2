import csv
import io
from datetime import date
from models import db
from models.employee import Employee
from models.employee_enhanced import EmployeeExtended, EmployeeGrade


class GovernmentExport:

    @staticmethod
    def export_employee_registry(dept=None):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'الرقم الوظيفي', 'الاسم الكامل', 'الرقم الوطني', 'رقم الملف الحكومي',
            'الدرجة', 'الراتب الأساسي', 'تاريخ التعيين', 'الحالة',
            'الجنس', 'تاريخ الميلاد', 'القسم', 'المؤهل',
        ])
        q = Employee.query.filter_by(is_active=True)
        if dept:
            q = q.filter_by(department=dept)
        employees = q.order_by(Employee.full_name).all()
        for emp in employees:
            grade_name = ''
            base_salary = 0.0
            qual = ''
            if emp.extended:
                grade = EmployeeGrade.query.get(emp.extended.grade_id)
                grade_name = grade.name_ar if grade else ''
                base_salary = grade.base_salary if grade else 0.0
            if emp.qualifications:
                qual = emp.qualifications[0].level if emp.qualifications[0].level else ''
            writer.writerow([
                emp.employee_code or '',
                emp.full_name or '',
                emp.national_id or '',
                emp.extended.gov_file_number if emp.extended else '',
                grade_name,
                base_salary,
                emp.hire_date.isoformat() if emp.hire_date else '',
                emp.status or 'active',
                emp.gender or '',
                emp.date_of_birth.isoformat() if emp.date_of_birth else '',
                emp.department or '',
                qual,
            ])
        return output.getvalue()

    @staticmethod
    def export_pension_data():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'الرقم الوظيفي', 'الاسم', 'الراتب الأساسي', 'سن التقاعد',
            'نسبة المعاش', 'سنوات الخدمة', 'المعاش المتوقع',
            'رقم التأمينات', 'نسبة الاشتراك',
        ])
        employees = Employee.query.filter_by(is_active=True).all()
        for emp in employees:
            if not emp.extended:
                continue
            ext = emp.extended
            grade = EmployeeGrade.query.get(ext.grade_id)
            base = grade.base_salary if grade else 0.0
            writer.writerow([
                emp.employee_code or '',
                emp.full_name or '',
                base,
                ext.retirement_age or 60,
                ext.pension_rate or 2.5,
                ext.years_of_service or 0.0,
                ext.expected_pension or 0.0,
                ext.social_security_number or '',
                ext.social_security_rate or 8.0,
            ])
        return output.getvalue()

    @staticmethod
    def export_insurance_data():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'الرقم الوظيفي', 'الاسم', 'مستوى التأمين الصحي',
            'عدد المعالين', 'قسط التأمين الصحي', 'تغطية تأمين الحياة',
            'المستفيد', 'قسط الحياة', 'تغطية إصابات العمل',
        ])
        employees = Employee.query.filter_by(is_active=True).all()
        for emp in employees:
            if not emp.extended:
                continue
            ext = emp.extended
            writer.writerow([
                emp.employee_code or '',
                emp.full_name or '',
                ext.health_insurance_level or 'basic',
                ext.health_insurance_dependents or 0,
                ext.health_insurance_premium or 0.0,
                ext.life_insurance_coverage or 0.0,
                ext.life_insurance_beneficiary or '',
                ext.life_insurance_premium or 0.0,
                ext.injury_insurance_coverage or 0.0,
            ])
        return output.getvalue()

    @staticmethod
    def export_clearance_report():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'الرقم الوظيفي', 'الاسم', 'مستوى التصريح', 'تاريخ التصريح',
            'تاريخ انتهاء التصريح', 'جهة الإصدار', 'الحالة',
        ])
        employees = Employee.query.filter_by(is_active=True).all()
        for emp in employees:
            if not emp.extended:
                continue
            ext = emp.extended
            today = date.today()
            if ext.clearance_expiry and ext.clearance_expiry < today:
                status = 'منتهي'
            elif ext.clearance_date:
                status = 'ساري'
            else:
                status = 'غير محدد'
            writer.writerow([
                emp.employee_code or '',
                emp.full_name or '',
                ext.clearance_level or '',
                ext.clearance_date.isoformat() if ext.clearance_date else '',
                ext.clearance_expiry.isoformat() if ext.clearance_expiry else '',
                ext.clearance_authority or '',
                status,
            ])
        return output.getvalue()

    @staticmethod
    def generate_grade_distribution():
        grades = EmployeeGrade.query.filter_by(is_active=True)\
            .order_by(EmployeeGrade.level).all()
        result = []
        for g in grades:
            count = EmployeeExtended.query.filter_by(grade_id=g.id).count()
            result.append({
                'grade': g.name_ar,
                'code': g.code,
                'level': g.level,
                'count': count,
                'base_salary': g.base_salary,
            })
        return result
