from datetime import datetime, date, UTC
from models import db, get_fernet

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
    is_inside_geofence  = db.Column(db.Boolean, default=True)
    geofence_violated_at= db.Column(db.DateTime, nullable=True)
    has_exit_permission = db.Column(db.Boolean, default=False)
    override_reason     = db.Column(db.String(200), nullable=True)

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
