from models import db
from models.employee import Employee


class TaxCalculator:
    SOCIAL_SECURITY_RATE = 0.05
    INCOME_TAX_BRACKETS = [
        (0, 1000, 0.0),
        (1000, 2000, 0.05),
        (2000, 3500, 0.10),
        (3500, 5000, 0.15),
        (5000, float('inf'), 0.20),
    ]

    @classmethod
    def calculate(cls, gross_salary, total_deductions=0, employee=None):
        taxable_income = max(0, gross_salary - total_deductions)
        social_security = cls.calculate_social_security(gross_salary)
        income_tax = cls.calculate_income_tax(taxable_income)
        total_tax = round(income_tax + social_security, 2)
        effective_rate = round(total_tax / gross_salary * 100, 2) if gross_salary else 0
        return {
            'gross': gross_salary,
            'taxable_income': round(taxable_income, 2),
            'income_tax': round(income_tax, 2),
            'social_security': round(social_security, 2),
            'total_tax': total_tax,
            'effective_rate': effective_rate,
            'net_after_tax': round(gross_salary - total_deductions - total_tax, 2),
            'bracket': cls.get_tax_bracket(taxable_income),
        }

    @classmethod
    def calculate_income_tax(cls, taxable_income):
        tax = 0.0
        remaining = taxable_income
        for lower, upper, rate in cls.INCOME_TAX_BRACKETS:
            if remaining <= 0:
                break
            bracket_amount = min(remaining, upper - lower)
            tax += bracket_amount * rate
            remaining -= bracket_amount
        return tax

    @classmethod
    def calculate_social_security(cls, gross_salary):
        max_ss = 5000
        ss_base = min(gross_salary, max_ss)
        return ss_base * cls.SOCIAL_SECURITY_RATE

    @classmethod
    def get_tax_bracket(cls, taxable_income):
        for lower, upper, rate in cls.INCOME_TAX_BRACKETS:
            if lower <= taxable_income < upper:
                return {
                    'lower': lower,
                    'upper': upper,
                    'rate': rate * 100,
                    'label': f'{lower:,} - {upper:,} د.ل' if upper < float('inf') else f'{lower:,}+ د.ل',
                }
        return {'lower': 0, 'upper': 0, 'rate': 0, 'label': 'معفى'}

    @classmethod
    def get_brackets_info(cls):
        return [
            {
                'lower': b[0],
                'upper': b[1] if b[1] < float('inf') else None,
                'rate': b[2] * 100,
                'label': f'{b[0]:,} - {b[1]:,} د.ل' if b[1] < float('inf') else f'{b[0]:,}+ د.ل',
            }
            for b in cls.INCOME_TAX_BRACKETS
        ]

    @classmethod
    def calculate_bulk(cls, employees_data):
        results = []
        for item in employees_data:
            gross = item.get('gross', 0)
            deductions = item.get('deductions', 0)
            emp = item.get('employee')
            tax = cls.calculate(gross, deductions, emp)
            results.append({**item, 'tax': tax})
        return results

    @classmethod
    def estimate_annual_tax(cls, monthly_gross, months=12):
        monthly = cls.calculate(monthly_gross)
        annual_tax = monthly['total_tax'] * months
        annual_gross = monthly_gross * months
        return {
            'monthly_gross': monthly_gross,
            'monthly_tax': monthly['total_tax'],
            'annual_gross': annual_gross,
            'annual_tax': round(annual_tax, 2),
            'effective_annual_rate': round(annual_tax / annual_gross * 100, 2) if annual_gross else 0,
        }

    @classmethod
    def get_exemptions(cls, employee=None):
        exemptions = {
            'social_security': cls.SOCIAL_SECURITY_RATE * 100,
            'housing_allowance_exempt': True,
            'transport_allowance_exempt': True,
            'overtime_exempt_upto': 500,
        }
        if employee:
            exemptions['has_dependents'] = False
            exemptions['dependents_exemption'] = 0
            exemptions['disabled_exemption'] = 0
        return exemptions
