import os, json, uuid, shutil, sqlite3
from datetime import datetime, UTC

from models import db, AuditLog


class BackupService:

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BACKUP_DIR = os.path.join(BASE, 'backups')
    os.makedirs(BACKUP_DIR, exist_ok=True)

    @classmethod
    def _index_path(cls):
        return os.path.join(cls.BACKUP_DIR, 'index.json')

    @classmethod
    def _read_index(cls):
        idx = cls._index_path()
        if not os.path.exists(idx):
            with open(idx, 'w', encoding='utf-8') as f:
                json.dump([], f)
            return []
        with open(idx, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def _write_index(cls, data):
        with open(cls._index_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def _resolve_db_path(cls, db_uri: str):
        src = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(src):
            src = os.path.join(cls.BASE, 'instance', src)
        return src

    @classmethod
    def list(cls):
        return cls._read_index()

    @classmethod
    def create(cls, db_uri: str, user_name: str, ip_address: str):
        src = cls._resolve_db_path(db_uri)
        if not os.path.exists(src):
            return None, 'قاعدة البيانات غير موجودة.'
        bid = uuid.uuid4().hex[:12]
        dst = os.path.join(cls.BACKUP_DIR, f'backup_{bid}.db')
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            return None, f'فشل النسخ: {str(e)}'
        idx = cls._read_index()
        size = os.path.getsize(dst)
        idx.insert(0, {
            'id': bid,
            'created_at': datetime.now(UTC).isoformat(),
            'size': size
        })
        cls._write_index(idx)
        audit = AuditLog(
            user_name=user_name,
            action='create',
            entity_type='backup',
            entity_id=None,
            changes=json.dumps({'id': bid}),
            ip_address=ip_address
        )
        db.session.add(audit)
        db.session.commit()
        return bid, None

    @classmethod
    def restore(cls, bid: str, db_uri: str):
        src = os.path.join(cls.BACKUP_DIR, f'backup_{bid}.db')
        if not os.path.exists(src):
            return 'النسخة غير موجودة.'
        dst = cls._resolve_db_path(db_uri)
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            return f'فشل الاستعادة: {str(e)}'
        return None

    @classmethod
    def verify(cls, bid: str, user_name: str, ip_address: str):
        fp = os.path.join(cls.BACKUP_DIR, f'backup_{bid}.db')
        if not os.path.exists(fp):
            return False, 'ملف النسخة الاحتياطية غير موجود.', None, None
        try:
            conn = sqlite3.connect(fp)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            tables = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM employees")
            emps = cur.fetchone()[0]
            conn.close()
        except Exception as e:
            return False, f'النسخة تالفة: {str(e)}', None, None
        audit = AuditLog(
            user_name=user_name, action='verify',
            entity_type='backup', entity_id=None,
            changes=json.dumps({'id': bid, 'tables': tables, 'employees': emps}),
            ip_address=ip_address
        )
        db.session.add(audit)
        db.session.commit()
        return True, f'النسخة سليمة: {tables} جدول، {emps} موظف.', tables, emps

    @classmethod
    def delete(cls, bid: str):
        fp = os.path.join(cls.BACKUP_DIR, f'backup_{bid}.db')
        if os.path.exists(fp):
            os.remove(fp)
        idx = [b for b in cls._read_index() if b['id'] != bid]
        cls._write_index(idx)

    @classmethod
    def download_path(cls, bid: str):
        fp = os.path.join(cls.BACKUP_DIR, f'backup_{bid}.db')
        if not os.path.exists(fp):
            return None
        return fp
