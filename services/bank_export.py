import io, csv, re
from datetime import date
from models import db
from models.employee import Employee
from models.payroll import BankPaymentDetail


class BankExportService:
    IBAN_PATTERN = re.compile(r'^LY\d{20}$')
    SUPPORTED_BANKS = ['البنك الأهلي الليبي', 'مصرف الجمهورية', 'المصرف التجاري الوطني',
                       'مصرف الصحارى', 'مصرف الوحدة', 'المصرف الإسلامي الليبي',
                       'مصرف الخليج الأول الليبي', 'مصرف الأمان', 'مصرف التضامن']

    @staticmethod
    def validate_iban(iban):
        if not iban:
            return False, 'رقم IBAN فارغ'
        clean = iban.replace(' ', '').upper()
        if not BankExportService.IBAN_PATTERN.match(clean):
            return False, 'صيغة IBAN غير صحيحة (يجب أن تبدأ بـ LY وتحتوي 22 حرفاً)'
        return True, ''

    @staticmethod
    def generate_payments(month, year, dept=None):
        qry = Employee.query.filter_by(role='employee', is_active=True)
        if dept:
            qry = qry.filter_by(department=dept)
        employees = qry.all()
        count = 0
        for emp in employees:
            total_salary = emp.total_salary
            existing = BankPaymentDetail.query.filter_by(
                employee_id=emp.id, month=month, year=year
            ).first()
            if existing:
                existing.net_amount = total_salary
                existing.iban = emp.bank_account_number or existing.iban
                existing.bank_name = emp.bank_name or existing.bank_name
            else:
                bpd = BankPaymentDetail(
                    employee_id=emp.id,
                    month=month,
                    year=year,
                    net_amount=total_salary,
                    iban=emp.bank_account_number or '',
                    bank_name=emp.bank_name or '',
                    status='pending',
                )
                db.session.add(bpd)
            count += 1
        db.session.commit()
        return {'ok': True, 'count': count, 'msg': f'تم إنشاء {count} قيد دفع'}

    @staticmethod
    def export_csv(month, year, status='pending'):
        payments = BankPaymentDetail.query.filter_by(month=month, year=year)
        if status:
            payments = payments.filter_by(status=status)
        payments = payments.order_by(BankPaymentDetail.employee_id).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['م', 'اسم الموظف', 'رقم الموظف', 'القسم', 'رقم IBAN',
                         'اسم البنك', 'صافي الراتب', 'الحالة'])
        for idx, p in enumerate(payments, 1):
            emp = Employee.query.get(p.employee_id)
            writer.writerow([
                idx,
                emp.full_name if emp else '',
                emp.username if emp else '',
                emp.department if emp else '',
                p.iban or '',
                p.bank_name or '',
                p.net_amount,
                p.status,
            ])
        return io.BytesIO(output.getvalue().encode('utf-8-sig')), f'payments_{month}_{year}.csv', 'text/csv'

    @staticmethod
    def export_txt(month, year, status='pending'):
        payments = BankPaymentDetail.query.filter_by(month=month, year=year)
        if status:
            payments = payments.filter_by(status=status)
        payments = payments.order_by(BankPaymentDetail.employee_id).all()
        lines = ['قائمة الرواتب للتحويل البنكي']
        lines.append(f'الشهر: {month} / السنة: {year}')
        lines.append(f'تاريخ التصدير: {date.today().isoformat()}')
        lines.append('')
        lines.append(f'{"الموظف":<25} {"IBAN":<25} {"الصافي":<10} {"البنك":<20}')
        lines.append('-' * 80)
        total = 0
        for p in payments:
            emp = Employee.query.get(p.employee_id)
            name = emp.full_name if emp else 'Unknown'
            lines.append(f'{name:<25} {p.iban or "—":<25} {p.net_amount:<10.2f} {p.bank_name or "—":<20}')
            total += p.net_amount
        lines.append('-' * 80)
        lines.append(f'الإجمالي: {"":<40} {total:<10.2f}')
        lines.append(f'عدد المستفيدين: {len(payments)}')
        return io.BytesIO('\n'.join(lines).encode('utf-8')), f'payments_{month}_{year}.txt', 'text/plain'

    @staticmethod
    def export_xml(month, year, status='pending'):
        payments = BankPaymentDetail.query.filter_by(month=month, year=year)
        if status:
            payments = payments.filter_by(status=status)
        payments = payments.order_by(BankPaymentDetail.employee_id).all()
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<PaymentList>')
        lines.append(f'  <Header Month="{month}" Year="{year}" Date="{date.today().isoformat()}" />')
        lines.append('  <Payments>')
        for p in payments:
            emp = Employee.query.get(p.employee_id)
            lines.append('    <Payment>')
            lines.append(f'      <EmployeeName>{emp.full_name if emp else ""}</EmployeeName>')
            lines.append(f'      <Username>{emp.username if emp else ""}</Username>')
            lines.append(f'      <IBAN>{p.iban or ""}</IBAN>')
            lines.append(f'      <BankName>{p.bank_name or ""}</BankName>')
            lines.append(f'      <Amount>{p.net_amount}</Amount>')
            lines.append(f'      <Status>{p.status}</Status>')
            lines.append('    </Payment>')
        lines.append('  </Payments>')
        lines.append('</PaymentList>')
        return io.BytesIO('\n'.join(lines).encode('utf-8')), f'payments_{month}_{year}.xml', 'application/xml'

    @staticmethod
    def get_missing_iban(month, year):
        payments = BankPaymentDetail.query.filter_by(month=month, year=year).all()
        missing = []
        for p in payments:
            if not p.iban:
                emp = Employee.query.get(p.employee_id)
                missing.append({
                    'id': p.id,
                    'employee_id': p.employee_id,
                    'employee_name': emp.full_name if emp else '',
                    'net_amount': p.net_amount,
                })
        return missing

    @staticmethod
    def validate_all_iban(month, year):
        payments = BankPaymentDetail.query.filter_by(month=month, year=year).all()
        results = []
        for p in payments:
            valid, msg = BankExportService.validate_iban(p.iban or '')
            emp = Employee.query.get(p.employee_id)
            results.append({
                'id': p.id,
                'employee_name': emp.full_name if emp else '',
                'iban': p.iban or '',
                'valid': valid,
                'message': msg,
            })
        return results
