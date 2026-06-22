from datetime import datetime, UTC
from models import db

class Notification(db.Model):
    __tablename__ = 'notifications'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    title         = db.Column(db.String(100), nullable=False)
    message       = db.Column(db.Text, nullable=False)
    ntype         = db.Column(db.String(30), default='info')
    icon          = db.Column(db.String(30), nullable=True)
    url           = db.Column(db.String(200), nullable=True)
    is_read       = db.Column(db.Boolean, default=False)
    is_global     = db.Column(db.Boolean, default=False)
    type          = db.Column(db.String(50), nullable=True)
    reference_id  = db.Column(db.Integer, nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    employee      = db.relationship('Employee', backref='notifications', lazy=True)
