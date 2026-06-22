from datetime import datetime, UTC
from models import db

class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    subject     = db.Column(db.String(200), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    id          = db.Column(db.Integer, primary_key=True)
    to_email    = db.Column(db.String(120), nullable=False)
    subject     = db.Column(db.String(200), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    status      = db.Column(db.String(20), default='pending')
    sent_at     = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class SmsLog(db.Model):
    __tablename__ = 'sms_logs'
    id          = db.Column(db.Integer, primary_key=True)
    to_phone    = db.Column(db.String(20), nullable=False)
    message     = db.Column(db.String(160), nullable=False)
    status      = db.Column(db.String(20), default='pending')
    sent_at     = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
