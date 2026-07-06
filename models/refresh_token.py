from datetime import datetime, UTC
from models import db


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False, index=True)
    token_hash  = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at  = db.Column(db.DateTime, nullable=False)
    is_revoked  = db.Column(db.Boolean, default=False)
    device_info = db.Column(db.String(200), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    revoked_at  = db.Column(db.DateTime, nullable=True)

    user = db.relationship('Employee', backref=db.backref('refresh_tokens', lazy='dynamic'))
