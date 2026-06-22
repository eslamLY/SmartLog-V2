import json
from datetime import datetime

from models import db, AuditLog


class AuditService:

    @staticmethod
    def query(date_str: str = None, action: str = None):
        q = AuditLog.query
        if date_str:
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d').date()
                q = q.filter(db.func.date(AuditLog.timestamp) == d)
            except (ValueError, TypeError):
                pass
        if action:
            q = q.filter_by(action=action)
        logs = q.order_by(AuditLog.timestamp.desc()).limit(500).all()
        return [{
            'id': l.id,
            'user_name': l.user_name,
            'action': l.action,
            'entity_type': l.entity_type,
            'entity_id': l.entity_id,
            'changes': json.loads(l.changes) if l.changes else None,
            'ip_address': l.ip_address,
            'timestamp': l.timestamp.isoformat()
        } for l in logs]
