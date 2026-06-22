import json
from datetime import datetime, date, UTC
from models import db


class DocumentReference(db.Model):
    __tablename__ = 'document_references'
    id             = db.Column(db.Integer, primary_key=True)
    reference_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class ArchivedDocument(db.Model):
    __tablename__ = 'archived_documents'
    id              = db.Column(db.Integer, primary_key=True)
    reference_code  = db.Column(db.String(30), db.ForeignKey('document_references.reference_code'), nullable=False)
    title           = db.Column(db.String(200), nullable=False)
    file_path       = db.Column(db.String(300), nullable=True)
    department      = db.Column(db.String(50), nullable=True)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    is_public       = db.Column(db.Boolean, default=False)
    has_expiry_date = db.Column(db.Boolean, default=False)
    expiry_date     = db.Column(db.Date, nullable=True)
    version         = db.Column(db.Integer, default=1)
    uploaded_by     = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    notes       = db.Column(db.Text, nullable=True)
    is_deleted  = db.Column(db.Boolean, default=False)
    deleted_at  = db.Column(db.DateTime, nullable=True)
    deleted_by  = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)

    employee   = db.relationship('Employee', foreign_keys=[employee_id], backref='archived_documents')
    uploader   = db.relationship('Employee', foreign_keys=[uploaded_by])
    deleter    = db.relationship('Employee', foreign_keys=[deleted_by])
    reference_doc = db.relationship('DocumentReference', backref=db.backref('documents', lazy=True),
                                    foreign_keys=[reference_code],
                                    primaryjoin='ArchivedDocument.reference_code == DocumentReference.reference_code')

    __table_args__ = (
        db.UniqueConstraint('reference_code', 'version', name='uq_archived_doc_ref_version'),
    )

    @property
    def is_expired(self):
        if not self.has_expiry_date or not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    @property
    def expiry_status(self):
        if not self.has_expiry_date or not self.expiry_date:
            return 'no_expiry'
        delta = (self.expiry_date - date.today()).days
        if delta < 0:
            return 'expired'
        if delta <= 7:
            return 'expiring_soon'
        return 'active'


class DocumentAuditLog(db.Model):
    __tablename__ = 'document_audit_logs'
    id            = db.Column(db.Integer, primary_key=True)
    document_id   = db.Column(db.Integer, db.ForeignKey('archived_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    action        = db.Column(db.String(20), nullable=False)
    performed_by  = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    performed_at  = db.Column(db.DateTime, default=lambda: datetime.now(UTC), index=True)
    details       = db.Column(db.Text, nullable=True)
    description   = db.Column(db.String(300), nullable=True)

    performer     = db.relationship('Employee', foreign_keys=[performed_by])
    document      = db.relationship('ArchivedDocument', backref=db.backref('audit_logs', lazy='dynamic', order_by='DocumentAuditLog.performed_at.desc()'))

    @classmethod
    def log(cls, document_id, action, performed_by, description, details=None):
        entry = cls(document_id=document_id, action=action, performed_by=performed_by,
                    description=description, details=json.dumps(details) if details else None)
        db.session.add(entry)
        return entry
