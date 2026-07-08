import io, os, math, calendar
from datetime import datetime, date, timedelta
from collections import defaultdict

from sqlalchemy import extract

from models import db
from models.employee import Employee
from models.attendance import AttendanceLog
from models.misc import LeaveRequest
from models.attendance_report import ReportDataService


class YTDService:
    @staticmethod
    def compute_ytd(employee_id=None, department_id=None):
        today = date.today()
        year_start = date(today.year, 1, 1)

        qry = Employee.query.filter(Employee.is_active == True, Employee.deleted_at == None)
        if employee_id:
            qry = qry.filter(Employee.id == employee_id)
        if department_id:
            qry = qry.filter(Employee.department_id == department_id)
        employees = qry.all()
        emp_ids = [e.id for e in employees]

        if not emp_ids:
            return {'rows': [], 'summary': {}}

        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(emp_ids),
            AttendanceLog.log_date >= year_start,
            AttendanceLog.log_date <= today,
        ).all()

        leaves = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_(emp_ids),
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= year_start,
        ).all()

        total_work_hours = 0.0
        total_present = 0
        total_late_minutes = 0
        total_overtime_hours = 0.0
        total_leave_days = 0

        logs_by_emp = defaultdict(list)
        for l in logs:
            logs_by_emp[l.employee_id].append(l)

        leaves_by_emp = defaultdict(list)
        for lv in leaves:
            leaves_by_emp[lv.employee_id].append(lv)

        rows = []
        for emp in employees:
            emp_logs = logs_by_emp.get(emp.id, [])
            emp_leaves = leaves_by_emp.get(emp.id, [])

            present = sum(1 for l in emp_logs if l.status in ('present', 'late'))
            late_mins = sum(l.late_minutes or 0 for l in emp_logs)

            work_seconds = 0
            overtime_seconds = 0
            break_mins = (emp.department_ref.break_duration_policy or 60) if emp.department_ref else 60

            for l in emp_logs:
                if l.clock_in and l.clock_out:
                    gross = (l.clock_out - l.clock_in).total_seconds()
                    net = gross - (break_mins * 60)
                    work_seconds += gross
                    if net > 8 * 3600:
                        overtime_seconds += net - 8 * 3600

            work_hours = round(work_seconds / 3600, 1)
            overtime_hours = round(overtime_seconds / 3600, 1)

            leave_days = 0
            for lv in emp_leaves:
                d = max(lv.start_date, year_start)
                ed = min(lv.end_date, today)
                while d <= ed:
                    if d.weekday() < 5:
                        leave_days += 1
                    d += timedelta(days=1)

            rows.append({
                'employee_id': emp.id,
                'employee_name': emp.full_name,
                'employee_code': emp.username,
                'department': emp.department,
                'department_id': emp.department_id,
                'present_days': present,
                'late_minutes': late_mins,
                'work_hours': work_hours,
                'overtime_hours': overtime_hours,
                'leave_days': leave_days,
            })

            total_work_hours += work_hours
            total_present += present
            total_late_minutes += late_mins
            total_overtime_hours = max(total_overtime_hours, overtime_hours)
            total_leave_days += leave_days

        working_days_ytd = sum(
            1 for d in range((today - year_start).days + 1)
            if (year_start + timedelta(days=d)).weekday() < 5
        )

        summary = {
            'total_employees': len(employees),
            'total_present': total_present,
            'total_late_minutes': total_late_minutes,
            'total_work_hours': round(total_work_hours, 1),
            'total_overtime_hours': max(r['overtime_hours'] for r in rows) if rows else 0,
            'total_leave_days': total_leave_days,
            'working_days_ytd': working_days_ytd,
            'year': today.year,
            'period_start': year_start.isoformat(),
            'period_end': today.isoformat(),
        }
        return {'rows': rows, 'summary': summary}


class ComplianceService:
    MAX_HOURS_PER_SHIFT = 12
    MAX_HOURS_PER_WEEK = 48
    MIN_BREAK_MINUTES = 30
    MIN_REST_HOURS = 11
    BREAK_TRIGGER_HOURS = 6

    @staticmethod
    def check_compliance(employee_id=None, department_id=None, year=None, month=None):
        today = date.today()
        year = year or today.year
        month = month or today.month
        _, last_day = calendar.monthrange(year, month)
        month_end   = date(year, month, last_day)

        qry = Employee.query.filter(Employee.is_active == True, Employee.deleted_at == None)
        if employee_id:
            qry = qry.filter(Employee.id == employee_id)
        if department_id:
            qry = qry.filter(Employee.department_id == department_id)
        employees = qry.all()
        emp_ids = [e.id for e in employees]

        if not emp_ids:
            return {'violations': [], 'summary': {}}

        logs = AttendanceLog.query.filter(
            AttendanceLog.employee_id.in_(emp_ids),
            AttendanceLog.log_date >= month_start,
            AttendanceLog.log_date <= month_end,
            AttendanceLog.clock_in.isnot(None),
        ).order_by(AttendanceLog.employee_id, AttendanceLog.log_date).all()

        logs_by_emp = defaultdict(list)
        for l in logs:
            logs_by_emp[l.employee_id].append(l)

        violations = []
        summary_counts = {'shift_overtime': 0, 'weekly_overtime': 0, 'missing_break': 0, 'rest_violation': 0}

        for emp in employees:
            emp_logs = logs_by_emp.get(emp.id, [])
            if not emp_logs:
                continue

            break_policy = (emp.department_ref.break_duration_policy or 60) if emp.department_ref else 60

            for l in emp_logs:
                if l.clock_in and l.clock_out:
                    gross_hours = (l.clock_out - l.clock_in).total_seconds() / 3600
                    if gross_hours > ComplianceService.MAX_HOURS_PER_SHIFT:
                        violations.append({
                            'employee_id': emp.id,
                            'employee_name': emp.full_name,
                            'date': l.log_date.isoformat(),
                            'type': 'shift_overtime',
                            'severity': 'high',
                            'details': f'{gross_hours:.1f} ساعة في مناوبة واحدة (الحد الأقصى {ComplianceService.MAX_HOURS_PER_SHIFT})',
                            'badge': '🚨',
                            'badge_label': 'تجاوز ساعات المناوبة',
                        })
                        summary_counts['shift_overtime'] += 1

                    if gross_hours > ComplianceService.BREAK_TRIGGER_HOURS:
                        break_hours = break_policy / 60
                        net_hours = gross_hours - break_hours
                        if net_hours >= gross_hours * 0.9:
                            violations.append({
                                'employee_id': emp.id,
                                'employee_name': emp.full_name,
                                'date': l.log_date.isoformat(),
                                'type': 'missing_break',
                                'severity': 'medium',
                                'details': f'مناوبة {gross_hours:.1f} ساعة بدون فترة راحة كافية (الحد الأدنى {break_policy} دقيقة)',
                                'badge': '📋',
                                'badge_label': 'فترة راحة مفقودة',
                            })
                            summary_counts['missing_break'] += 1

            weekly_hours = defaultdict(float)
            for l in emp_logs:
                if l.clock_in and l.clock_out:
                    iso_week = l.log_date.isoformat()
                    week_key = (l.log_date - timedelta(days=l.log_date.weekday())).isoformat()
                    gross = (l.clock_out - l.clock_in).total_seconds() / 3600
                    weekly_hours[week_key] += gross

            for week_key, wh in weekly_hours.items():
                if wh > ComplianceService.MAX_HOURS_PER_WEEK:
                    week_start = week_key
                    violations.append({
                        'employee_id': emp.id,
                        'employee_name': emp.full_name,
                        'date': week_start,
                        'type': 'weekly_overtime',
                        'severity': 'high',
                        'details': f'{wh:.1f} ساعة في الأسبوع (الحد الأقصى {ComplianceService.MAX_HOURS_PER_WEEK})',
                        'badge': '🚨',
                        'badge_label': 'تجاوز الساعات الأسبوعية',
                    })
                    summary_counts['weekly_overtime'] += 1

            emp_logs_sorted = sorted(emp_logs, key=lambda x: x.log_date)
            for i in range(len(emp_logs_sorted) - 1):
                cur = emp_logs_sorted[i]
                nxt = emp_logs_sorted[i + 1]
                if cur.clock_out and nxt.clock_in:
                    rest_hours = (nxt.clock_in - cur.clock_out).total_seconds() / 3600
                    if 0 < rest_hours < ComplianceService.MIN_REST_HOURS:
                        violations.append({
                            'employee_id': emp.id,
                            'employee_name': emp.full_name,
                            'date': cur.log_date.isoformat(),
                            'type': 'rest_violation',
                            'severity': 'medium',
                            'details': f'{rest_hours:.1f} ساعة راحة بين الأيام (الحد الأدنى {ComplianceService.MIN_REST_HOURS})',
                            'badge': '⚠️',
                            'badge_label': 'انتهاك فترة الراحة',
                        })
                        summary_counts['rest_violation'] += 1

        summary = {
            'total_violations': len(violations),
            'total_employees_checked': len(employees),
            'shift_overtime_count': summary_counts['shift_overtime'],
            'weekly_overtime_count': summary_counts['weekly_overtime'],
            'missing_break_count': summary_counts['missing_break'],
            'rest_violation_count': summary_counts['rest_violation'],
            'month': month,
            'year': year,
        }
        return {'violations': violations, 'summary': summary}


class ReportGenerationService:

    @staticmethod
    def generate_pdf_report(data, year, month):
        try:
            from weasyprint import HTML
            html = ReportGenerationService._build_pdf_html(data, year, month)
            pdf_bytes = HTML(string=html).write_pdf()
            return pdf_bytes
        except ImportError:
            return ReportGenerationService._generate_reportlab_pdf(data, year, month)

    @staticmethod
    def _build_pdf_html(data, year, month):
        rows_html = ''
        for i, r in enumerate(data['rows'], 1):
            status_color = '#22c55e' if r['overall_status'] == 'excellent' else '#3b82f6' if r['overall_status'] == 'good' else '#f59e0b' if r['overall_status'] == 'acceptable' else '#ef4444'
            rows_html += f'''
            <tr>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0">{i}</td>
                <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:600">{r['emp_name']}<br><span style="font-size:10px;color:#6b7280">{r['emp_code']}</span></td>
                <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">{r['department']}</td>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#22c55e;font-weight:600">{r['present']}</td>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#f59e0b">{r['late_count']}</td>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#ef4444">{r['absent']}</td>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0">{r['late_minutes']}</td>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#ef4444">{r['total_deduction']}</td>
                <td style="text-align:center;padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:700;color:{status_color}">{r['net_salary']}</td>
            </tr>'''
        summary = data['summary']
        s_color = '#22c55e' if summary['overall_pct'] >= 90 else '#f59e0b' if summary['overall_pct'] >= 75 else '#ef4444'
        html = f'''
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head><meta charset="utf-8"><title>تقرير الحضور</title>
        <style>
            @page {{ size: A4; margin: 1.5cm; }}
            body {{ font-family: 'DejaVu Sans', sans-serif; font-size: 12px; color: #1a2035; }}
            h1 {{ text-align: center; font-size: 18px; color: #991B1B; margin-bottom: 4px; }}
            .subtitle {{ text-align: center; font-size: 13px; color: #6b7280; margin-bottom: 20px; }}
            .summary {{ display: flex; justify-content: space-between; margin-bottom: 20px; padding: 12px; background: #f8fafc; border-radius: 8px; }}
            .summary-item {{ text-align: center; }}
            .summary-value {{ font-size: 20px; font-weight: 700; color: {s_color}; }}
            .summary-label {{ font-size: 10px; color: #6b7280; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
            th {{ background: #DC2626; color: #fff; padding: 8px; text-align: center; font-size: 11px; }}
            td {{ padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }}
            .footer {{ text-align: center; font-size: 10px; color: #9ca3af; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
        </style>
        </head><body>
            <h1>SMARTLOG</h1>
            <div class="subtitle">تقرير الحضور والانصراف — {month:02d}-{year}</div>
            <div class="summary">
                <div class="summary-item"><div class="summary-value">{summary['total_employees']}</div><div class="summary-label">إجمالي الموظفين</div></div>
                <div class="summary-item"><div class="summary-value">{summary['total_present']}</div><div class="summary-label">إجمالي الحضور</div></div>
                <div class="summary-item"><div class="summary-value">{summary['overall_pct']}%</div><div class="summary-label">معدل الحضور</div></div>
                <div class="summary-item"><div class="summary-value">{summary['total_late_minutes']}</div><div class="summary-label">دقائق تأخير</div></div>
                <div class="summary-item"><div class="summary-value">{summary['total_deductions']}</div><div class="summary-label">إجمالي الخصومات</div></div>
            </div>
            <table>
                <thead><tr>
                    <th>#</th><th>الموظف</th><th>القسم</th><th>حضور</th><th>تأخير</th><th>غياب</th><th>د.تأخير</th><th>الخصم</th><th>الصافي</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            <div class="footer">تم إنشاء هذا التقرير في {datetime.now().strftime('%Y-%m-%d %H:%M')} — جميع الحقوق محفوظة &copy; SMARTLOG</div>
        </body></html>'''
        return html

    @staticmethod
    def _generate_reportlab_pdf(data, year, month):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        except ImportError:
            return b''
        buf = io.BytesIO()
        font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'Arial.ttf')
        font_bold_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'ArialBold.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Arabic', font_path))
            if os.path.exists(font_bold_path):
                pdfmetrics.registerFont(TTFont('ArabicBold', font_bold_path))
                bold_font = 'ArabicBold'
            else:
                bold_font = 'Arabic'
            normal_font = 'Arabic'
        else:
            normal_font = 'Helvetica'
            bold_font = 'Helvetica-Bold'
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', fontName=bold_font, fontSize=16, textColor=HexColor('#991B1B'), alignment=TA_CENTER, spaceAfter=4)
        subtitle_style = ParagraphStyle('Subtitle', fontName=normal_font, fontSize=11, textColor=HexColor('#6b7280'), alignment=TA_CENTER, spaceAfter=16)
        normal_style = ParagraphStyle('Normal', fontName=normal_font, fontSize=9, alignment=TA_RIGHT, leading=14)
        header_style = ParagraphStyle('Header', fontName=bold_font, fontSize=9, textColor=HexColor('#FFFFFF'), alignment=TA_CENTER)
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
        elements = []
        elements.append(Paragraph('SMARTLOG', title_style))
        elements.append(Paragraph(f'تقرير الحضور والانصراف — {month:02d}-{year}', subtitle_style))
        elements.append(Spacer(1, 8))
        s = data['summary']
        summary_data = [
            ['إجمالي الموظفين', 'إجمالي الحضور', 'معدل الحضور', 'دقائق تأخير', 'إجمالي الخصومات'],
            [str(s['total_employees']), str(s['total_present']), f"{s['overall_pct']}%", str(s['total_late_minutes']), str(s['total_deductions'])],
        ]
        summary_table = Table(summary_data, colWidths=[3.2*cm]*5)
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), normal_font),
            ('FONTNAME', (0, 1), (-1, 1), bold_font),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (-1, 1), HexColor('#22C55E' if s['overall_pct'] >= 90 else '#F59E0B' if s['overall_pct'] >= 75 else '#EF4444')),
            ('ROWBACKGROUNDS', (0, 1), (-1, 1), [HexColor('#FFFFFF'), HexColor('#FEF2F2')]),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor('#E2E8F0')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 12))
        table_data = [['#', 'الموظف', 'القسم', 'حضور', 'تأخير', 'غياب', 'د.تأخير', 'الخصم', 'الصافي']]
        for i, r in enumerate(data['rows'], 1):
            table_data.append([
                str(i), f"{r['emp_name']}\n{r['emp_code']}", r['department'],
                str(r['present']), str(r['late_count']), str(r['absent']),
                str(r['late_minutes']), str(r['total_deduction']), str(r['net_salary']),
            ])
        col_widths = [1*cm, 3*cm, 2.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm]
        data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        data_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), bold_font),
            ('FONTNAME', (0, 1), (-1, -1), normal_font),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#DC2626')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), HexColor('#FEF2F2')]),
            ('GRID', (0, 0), (-1, -1), 0.3, HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(data_table)
        elements.append(Spacer(1, 12))
        footer_style = ParagraphStyle('Footer', fontName=normal_font, fontSize=8, textColor=HexColor('#9CA3AF'), alignment=TA_CENTER)
        elements.append(Paragraph(f'تم إنشاء هذا التقرير في {datetime.now().strftime("%Y-%m-%d %H:%M")} — جميع الحقوق محفوظة &copy; SMARTLOG', footer_style))
        doc.build(elements)
        buf.seek(0)
        return buf.read()
