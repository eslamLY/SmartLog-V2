class PayrollService:
    PER_MINUTE_RATE_DENOM = 30 * 8 * 60

    @staticmethod
    def calculate_deduction(base_salary: float, late_minutes: int) -> float:
        if not base_salary or not late_minutes:
            return 0.0
        per_min = base_salary / PayrollService.PER_MINUTE_RATE_DENOM
        return round(late_minutes * per_min, 2)

    @staticmethod
    def hourly_rate(base_salary: float) -> float:
        if not base_salary:
            return 0.0
        return base_salary / (30 * 8)
