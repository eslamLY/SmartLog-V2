import hashlib
from datetime import datetime, UTC
from models import db

class QRToken(db.Model):
    __tablename__ = 'qr_tokens'

    id          = db.Column(db.Integer, primary_key=True)
    token_hash  = db.Column(db.String(64), unique=True, nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    expires_at  = db.Column(db.DateTime, nullable=False)
    used_at     = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def hash_raw(raw):
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def cleanup_expired():
        cutoff = datetime.now(UTC)
        QRToken.query.filter(QRToken.expires_at < cutoff).delete()
        db.session.commit()
