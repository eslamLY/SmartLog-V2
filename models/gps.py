import json
from datetime import datetime, UTC

from models import db


class GeofenceZone(db.Model):
    __tablename__ = 'geofence_zones'
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(100), nullable=False)
    name_en          = db.Column(db.String(100), nullable=True)
    zone_type        = db.Column(db.String(20), default='circle')
    coordinates      = db.Column(db.Text, nullable=True)
    center_lat       = db.Column(db.Float, nullable=True)
    center_lng       = db.Column(db.Float, nullable=True)
    radius           = db.Column(db.Float, default=200.0)
    color            = db.Column(db.String(10), default='#22c55e')
    address          = db.Column(db.String(300), nullable=True)
    purpose          = db.Column(db.String(300), nullable=True)
    work_hours_start = db.Column(db.String(5), default='08:00')
    work_hours_end   = db.Column(db.String(5), default='17:00')
    work_days        = db.Column(db.Text, default='["sat","sun","mon","tue","wed","thu"]')
    is_active        = db.Column(db.Boolean, default=True)
    is_restricted    = db.Column(db.Boolean, default=False)
    is_trusted       = db.Column(db.Boolean, default=False)
    alert_on_entry   = db.Column(db.Boolean, default=True)
    alert_on_exit    = db.Column(db.Boolean, default=True)
    assigned_employees = db.Column(db.Text, nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at       = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    events = db.relationship('GeofenceEvent', backref='zone', lazy=True,
                             foreign_keys='GeofenceEvent.zone_id')

    def set_coordinates(self, coords):
        self.coordinates = json.dumps(coords, ensure_ascii=False)

    def get_coordinates(self):
        if not self.coordinates:
            return []
        try:
            return json.loads(self.coordinates)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_work_days(self, days_list):
        self.work_days = json.dumps(days_list, ensure_ascii=False)

    def get_work_days(self):
        if not self.work_days:
            return ['sat', 'sun', 'mon', 'tue', 'wed', 'thu']
        try:
            return json.loads(self.work_days)
        except (json.JSONDecodeError, TypeError):
            return ['sat', 'sun', 'mon', 'tue', 'wed', 'thu']

    def set_assigned_employee_ids(self, ids_list):
        self.assigned_employees = json.dumps(ids_list, ensure_ascii=False)

    def get_assigned_employee_ids(self):
        if not self.assigned_employees:
            return []
        try:
            return json.loads(self.assigned_employees)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_effective_radius(self):
        if self.zone_type == 'circle' and self.radius:
            return float(self.radius)
        return 0.0

    def contains(self, lat, lng):
        from utils.helpers import haversine
        if self.zone_type == 'circle' and self.center_lat and self.center_lng and self.radius:
            dist = haversine(float(lat), float(lng),
                             float(self.center_lat), float(self.center_lng))
            return dist <= float(self.radius), dist
        if self.zone_type in ('polygon', 'rectangle'):
            coords = self.get_coordinates()
            if not coords or len(coords) < 3:
                return False, None
            n = len(coords)
            inside = False
            j = n - 1
            for i in range(n):
                yi, xi = coords[i]['lat'], coords[i]['lng']
                yj, xj = coords[j]['lat'], coords[j]['lng']
                if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                    inside = not inside
                j = i
            if inside:
                return True, 0.0
            min_dist = float('inf')
            for i in range(n):
                d = haversine(lat, lng, coords[i]['lat'], coords[i]['lng'])
                min_dist = min(min_dist, d)
            return False, min_dist
        return False, None


class GeofenceEvent(db.Model):
    __tablename__ = 'geofence_events'
    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    zone_id     = db.Column(db.Integer, db.ForeignKey('geofence_zones.id'), nullable=False)
    event_type  = db.Column(db.String(20), nullable=False)
    lat         = db.Column(db.Float, nullable=True)
    lng         = db.Column(db.Float, nullable=True)
    accuracy    = db.Column(db.Float, default=0.0)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='geofence_events', lazy=True,
                               foreign_keys=[employee_id])


class AlertLog(db.Model):
    __tablename__ = 'alert_logs'
    id                   = db.Column(db.Integer, primary_key=True)
    alert_type           = db.Column(db.String(50), nullable=False)
    severity             = db.Column(db.String(20), default='info')
    is_critical          = db.Column(db.Boolean, default=False)
    employee_id          = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    employee_name        = db.Column(db.String(100), nullable=True)
    description          = db.Column(db.String(500), nullable=False)
    details              = db.Column(db.Text, nullable=True)
    lat                  = db.Column(db.Float, nullable=True)
    lng                  = db.Column(db.Float, nullable=True)
    acknowledged_at      = db.Column(db.DateTime, nullable=True)
    acknowledged_by      = db.Column(db.Integer, nullable=True)
    acknowledged_by_name = db.Column(db.String(100), nullable=True)
    snoozed_until        = db.Column(db.DateTime, nullable=True)
    notes                = db.Column(db.Text, nullable=True)
    created_at           = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='alert_logs', lazy=True,
                               foreign_keys=[employee_id])


class TrustedLocation(db.Model):
    __tablename__ = 'trusted_locations'
    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    lat         = db.Column(db.Float, nullable=False)
    lng         = db.Column(db.Float, nullable=False)
    radius      = db.Column(db.Float, default=100.0)
    address     = db.Column(db.String(300), nullable=True)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='trusted_locations', lazy=True,
                               foreign_keys=[employee_id])


class LocationAuditLog(db.Model):
    __tablename__ = 'location_audit_logs'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    user_name    = db.Column(db.String(100), nullable=True)
    action       = db.Column(db.String(50), nullable=False)
    target_employee_id = db.Column(db.Integer, nullable=True)
    target_name  = db.Column(db.String(100), nullable=True)
    ip_address   = db.Column(db.String(50), nullable=True)
    details      = db.Column(db.Text, nullable=True)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class TrackingPolicy(db.Model):
    __tablename__ = 'tracking_policies'
    id                    = db.Column(db.Integer, primary_key=True)
    employee_id           = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    policy_type           = db.Column(db.String(30), default='work_hours_only')
    tracking_enabled      = db.Column(db.Boolean, default=True)
    work_hours_only       = db.Column(db.Boolean, default=True)
    allow_opt_out         = db.Column(db.Boolean, default=True)
    opted_out             = db.Column(db.Boolean, default=False)
    data_retention_days   = db.Column(db.Integer, default=90)
    notify_on_entry       = db.Column(db.Boolean, default=True)
    notify_on_exit        = db.Column(db.Boolean, default=True)
    created_at            = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at            = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='tracking_policy', lazy=True,
                               foreign_keys=[employee_id])


class PhotoVerification(db.Model):
    __tablename__ = 'photo_verifications'
    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    photo_path  = db.Column(db.String(300), nullable=False)
    lat         = db.Column(db.Float, nullable=True)
    lng         = db.Column(db.Float, nullable=True)
    accuracy    = db.Column(db.Float, default=0.0)
    verified    = db.Column(db.Boolean, default=False)
    verified_by = db.Column(db.Integer, nullable=True)
    notes       = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    employee = db.relationship('Employee', backref='photo_verifications', lazy=True,
                               foreign_keys=[employee_id])


class GPSTrackingSession(db.Model):
    __tablename__ = 'gps_tracking_sessions'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    device_id     = db.Column(db.String(120), nullable=True)
    ip_address    = db.Column(db.String(50), nullable=True)
    user_agent    = db.Column(db.String(300), nullable=True)
    is_active     = db.Column(db.Boolean, default=True)
    started_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    ended_at      = db.Column(db.DateTime, nullable=True)
    last_ping_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    total_updates = db.Column(db.Integer, default=0)

    employee = db.relationship('Employee', backref='tracking_sessions', lazy=True,
                               foreign_keys=[employee_id])
