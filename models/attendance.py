from datetime import datetime, date, UTC
from models import db, get_fernet


class AttendancePolicy(db.Model):
    __tablename__ = 'attendance_policies'

    id                     = db.Column(db.Integer, primary_key=True)
    name                   = db.Column(db.String(100), nullable=False)
    department_id          = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    shift_type_id          = db.Column(db.Integer, db.ForeignKey('shift_types.id'), nullable=True)
    late_grace_minutes     = db.Column(db.Integer, default=15)
    early_leave_grace      = db.Column(db.Integer, default=10)
    max_late_minutes       = db.Column(db.Integer, default=120, comment='بعدها يُعتبر غياب')
    min_work_hours         = db.Column(db.Float, default=6.0, comment='أقل ساعات عمل للتسجيل')
    overtime_threshold_h   = db.Column(db.Float, default=8.0, comment='بعدها يُحتسب إضافي')
    overtime_multiplier    = db.Column(db.Float, default=1.5)
    auto_deduct_absence    = db.Column(db.Boolean, default=False, comment='خصم تلقائي من الراتب')
    allow_geofence_override = db.Column(db.Boolean, default=False)
    require_selfie         = db.Column(db.Boolean, default=False)
    max_early_leave_min    = db.Column(db.Integer, default=60, comment='أقصى دقائق خروج مبكر مسموح')
    is_active              = db.Column(db.Boolean, default=True)
    created_at             = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at             = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    department   = db.relationship('Department', foreign_keys=[department_id], backref='attendance_policies')
    shift_type   = db.relationship('ShiftType', foreign_keys=[shift_type_id], backref='attendance_policies')

    @staticmethod
    def resolve(employee, scheduled_shift=None):
        """Resolve the applicable policy for an employee.
        Priority: shift-specific → department-specific → global default.
        """
        if scheduled_shift:
            shift_policy = AttendancePolicy.query.filter_by(
                shift_type_id=scheduled_shift.shift_type_id, is_active=True).first()
            if shift_policy:
                return shift_policy
        dept_policy = AttendancePolicy.query.filter_by(
            department_id=employee.department_id, shift_type_id=None, is_active=True).first()
        if dept_policy:
            return dept_policy
        default = AttendancePolicy.query.filter_by(
            department_id=None, shift_type_id=None, is_active=True).first()
        if default:
            return default
        return None


class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'
    id                  = db.Column(db.Integer, primary_key=True)
    employee_id         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    log_date            = db.Column(db.Date, nullable=False, default=date.today)
    clock_in            = db.Column(db.DateTime, nullable=True)
    clock_out           = db.Column(db.DateTime, nullable=True)
    lat_in              = db.Column(db.Float, nullable=True)
    lat_in_enc          = db.Column(db.Text, nullable=True)
    lng_in              = db.Column(db.Float, nullable=True)
    lng_in_enc          = db.Column(db.Text, nullable=True)
    lat_out             = db.Column(db.Float, nullable=True)
    lat_out_enc         = db.Column(db.Text, nullable=True)
    lng_out             = db.Column(db.Float, nullable=True)
    lng_out_enc         = db.Column(db.Text, nullable=True)
    distance_in         = db.Column(db.Integer, default=0)
    status              = db.Column(db.String(20), default='absent')
    selfie_data         = db.Column(db.Text, nullable=True)
    late_minutes        = db.Column(db.Integer, default=0)
    early_leave_minutes = db.Column(db.Integer, default=0)
    overtime_minutes    = db.Column(db.Integer, default=0)
    is_inside_geofence  = db.Column(db.Boolean, default=True)
    geofence_violated_at= db.Column(db.DateTime, nullable=True)
    has_exit_permission = db.Column(db.Boolean, default=False)
    override_reason     = db.Column(db.String(200), nullable=True)
    policy_id           = db.Column(db.Integer, db.ForeignKey('attendance_policies.id'), nullable=True)

    def set_clock_in_coords(self, lat, lng):
        self.lat_in = lat; self.lng_in = lng
        try:
            self.lat_in_enc = get_fernet().encrypt(str(lat).encode()).decode()
            self.lng_in_enc = get_fernet().encrypt(str(lng).encode()).decode()
        except Exception:
            pass

    def set_clock_out_coords(self, lat, lng):
        self.lat_out = lat; self.lng_out = lng
        try:
            self.lat_out_enc = get_fernet().encrypt(str(lat).encode()).decode()
            self.lng_out_enc = get_fernet().encrypt(str(lng).encode()).decode()
        except Exception:
            pass
