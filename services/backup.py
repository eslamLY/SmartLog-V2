"""Dialect-aware backup/restore for SQLite and PostgreSQL.

SQLite keeps the original single-file copy semantics. PostgreSQL is handled by a
logical export of replayable INSERT statements built through SQLAlchemy, so no
`pg_dump`/`psql` binary is required -- the Render image is built from
`python:3.11-slim`, which ships no postgresql-client. When `pg_dump` does happen
to exist it is preferred, and logical dumps are still understood by `verify()`.
"""
import os, re, json, uuid, shutil, sqlite3, subprocess
from datetime import datetime, UTC

from sqlalchemy import inspect, select, text

from models import db, AuditLog

try:
    from sqlalchemy.dialects.postgresql import JSONB as _JSONB
except ImportError:  # pragma: no cover
    _JSONB = None

_TABLE_COMMENT = re.compile(r'^--\s*table\s+"?(\w+)"?\s*\((\d+)\s+rows?\)\s*$')
_PG_COPY = re.compile(r'^(?:COPY|INSERT INTO)\s+"?(\w+)"?')


class BackupError(Exception):
    """Recoverable backup failure; message is surfaced to the API caller."""


class BackupService:

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BACKUP_DIR = os.path.join(BASE, 'backups')
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # ── dialect helpers ──────────────────────────────────────────────────────

    @classmethod
    def engine_name(cls, db_uri: str) -> str:
        """'sqlite' or 'postgresql'; raises BackupError for anything else."""
        if db_uri.startswith('sqlite:'):
            return 'sqlite'
        if db_uri.startswith(('postgresql:', 'postgres://', 'postgresql+psycopg2:')):
            return 'postgresql'
        raise BackupError(f'محرّك قاعدة بيانات غير مدعوم: {db_uri.split(":", 1)[0]}')

    @classmethod
    def _resolve_db_path(cls, db_uri: str):
        """SQLite file path, or None when the target is not SQLite."""
        if cls.engine_name(db_uri) != 'sqlite':
            return None
        src = db_uri.replace('sqlite:///', '', 1)
        if not os.path.isabs(src):
            src = os.path.join(cls.BASE, 'instance', src)
        return src

    @classmethod
    def _backup_path(cls, bid: str, engine: str) -> str:
        ext = 'db' if engine == 'sqlite' else 'sql'
        return os.path.join(cls.BACKUP_DIR, f'backup_{bid}.{ext}')

    @staticmethod
    def _quote(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    @classmethod
    def _is_json_type(cls, col) -> bool:
        if _JSONB is not None and isinstance(col.type, _JSONB):
            return True
        return str(col.type).upper().startswith('JSON')

    # ── literal serialization ────────────────────────────────────────────────

    @staticmethod
    def _pg_literal(value, is_json=False):
        if value is None:
            return 'NULL'
        if isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            return "'\\x" + bytes(value).hex() + "'"
        if isinstance(value, datetime):
            return "'" + value.isoformat(sep=' ') + "'"
        if is_json and isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return "'" + str(value).replace("'", "''") + "'"

    @classmethod
    def _insert_sql(cls, engine, table, row: dict) -> str:
        cols = ', '.join(cls._quote(c.name) for c in table.columns)
        vals = ', '.join(
            cls._pg_literal(row[c.name], is_json=cls._is_json_type(c)) for c in table.columns
        )
        verb = 'INSERT OR REPLACE INTO' if engine == 'sqlite' else 'INSERT INTO'
        return f'{verb} {cls._quote(table.name)} ({cols}) VALUES ({vals});'

    # ── PostgreSQL export ────────────────────────────────────────────────────

    @staticmethod
    def _pg_dump_binary():
        for name in ('pg_dump', 'pg_dump.exe'):
            path = shutil.which(name)
            if path:
                return path
        return None

    @classmethod
    def _pg_dump(cls, dst: str, db_uri: str) -> int:
        binary = cls._pg_dump_binary()
        if not binary:
            return 0
        try:
            proc = subprocess.run(
                [binary, '--no-owner', '--no-acl', '--clean', '--if-exists',
                 '-f', dst, db_uri],
                capture_output=True, text=True, timeout=900,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 0
        if proc.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
            return os.path.getsize(dst)
        if os.path.exists(dst):
            os.remove(dst)
        return 0

    @classmethod
    def _export_postgresql(cls, dst: str, db_uri: str) -> int:
        size = cls._pg_dump(dst, db_uri)
        if size:
            return size
        inspector = inspect(db.engine)
        known = db.metadata.tables
        written = 0
        with open(dst, 'w', encoding='utf-8') as fh:
            fh.write('-- SmartLog logical backup\n')
            for name in sorted(inspector.get_table_names()):
                table = known.get(name)
                if table is None:
                    continue
                rows = db.session.execute(select(table)).mappings().all()
                if not rows:
                    continue
                fh.write(f'-- table {name} ({len(rows)} rows)\n')
                for row in rows:
                    fh.write(cls._insert_sql('postgresql', table, row) + '\n')
                    written += 1
        if not written:
            os.remove(dst)
            raise BackupError('لا توجد بيانات للتصدير.')
        return os.path.getsize(dst)

    @classmethod
    def _verify_dump(cls, fp: str) -> tuple:
        tables, emps = set(), 0
        with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
            for raw in fh:
                line = raw.strip()
                m = _TABLE_COMMENT.match(line)
                if m:
                    tables.add(m.group(1))
                    if m.group(1) == 'employees':
                        emps = int(m.group(2))
                    continue
                m = _PG_COPY.match(line)
                if m:
                    tables.add(m.group(1))
        if not tables:
            raise BackupError('النسخة لا تحتوي على جداول معروفة.')
        return len(tables), emps

    # ── index bookkeeping ────────────────────────────────────────────────────

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
    def _entry(cls, bid: str):
        return next((b for b in cls._read_index() if b['id'] == bid), None)

    @classmethod
    def _record(cls, bid, size, engine):
        idx = cls._read_index()
        idx.insert(0, {
            'id': bid,
            'created_at': datetime.now(UTC).isoformat(),
            'size': size,
            'engine': engine,
        })
        cls._write_index(idx)

    @staticmethod
    def _audit(action, user_name, ip_address, payload):
        db.session.add(AuditLog(
            user_name=user_name,
            action=action,
            entity_type='backup',
            entity_id=None,
            changes=json.dumps(payload, ensure_ascii=False),
            ip_address=ip_address,
        ))
        db.session.commit()

    # ── public API (signatures preserved) ────────────────────────────────────

    @classmethod
    def list(cls):
        return cls._read_index()

    @classmethod
    def create(cls, db_uri: str, user_name: str, ip_address: str):
        try:
            engine = cls.engine_name(db_uri)
        except BackupError as exc:
            return None, str(exc)
        bid = uuid.uuid4().hex[:12]
        dst = cls._backup_path(bid, engine)
        try:
            if engine == 'sqlite':
                src = cls._resolve_db_path(db_uri)
                if not os.path.exists(src):
                    return None, 'قاعدة البيانات غير موجودة.'
                shutil.copy2(src, dst)
                size = os.path.getsize(dst)
            else:
                size = cls._export_postgresql(dst, db_uri)
        except BackupError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f'فشل النسخ: {exc}'
        cls._record(bid, size, engine)
        cls._audit('create', user_name, ip_address, {'id': bid, 'engine': engine})
        return bid, None

    @classmethod
    def restore(cls, bid: str, db_uri: str):
        try:
            engine = cls.engine_name(db_uri)
        except BackupError as exc:
            return str(exc)
        src = cls._backup_path(bid, engine)
        if not os.path.exists(src):
            return 'النسخة غير موجودة.'
        try:
            if engine == 'sqlite':
                shutil.copy2(src, cls._resolve_db_path(db_uri))
            else:
                cls._restore_postgresql(src)
        except BackupError as exc:
            return str(exc)
        except Exception as exc:
            return f'فشل الاستعادة: {exc}'
        return None

    @classmethod
    def _reset_postgresql_sequences(cls) -> int:
        """Realign identity/serial sequences after a restore.

        `TRUNCATE` keeps the sequence cursor, and the dump replays explicit
        primary keys, so without this the first INSERT after a restore collides
        with a restored row.

        Driven from the catalog rather than Inspector.get_pk_autoincrement_column
        (which raises for tables without a usable single-column autoincrement
        key and was being silently skipped, leaving sequences unmoved). Returns
        the number of sequences realigned.
        """
        rows = db.session.execute(text(
            "SELECT c.table_name, c.column_name "
            "FROM information_schema.columns c "
            "JOIN pg_class t ON t.relname = c.table_name "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "AND n.nspname = c.table_schema "
            "WHERE c.table_schema = ANY(current_schemas(false)) "
            "AND c.column_default LIKE 'nextval%' "
            "AND t.relkind = 'r'"
        )).fetchall()
        for tname, cname in rows:
            col, tbl = cls._quote(cname), cls._quote(tname)
            db.session.execute(text(
                f"SELECT setval(pg_get_serial_sequence(:t, :c), "
                f"COALESCE(MAX({col}), 1), MAX({col}) IS NOT NULL) FROM {tbl}"
            ), {'t': tname, 'c': cname})
        db.session.commit()
        return len(rows)

    @classmethod
    def _fk_defs(cls):
        """(table, constraint_name, ADD CONSTRAINT ddl) for every modelled FK."""
        out = []
        for t in db.metadata.sorted_tables:
            for fk in t.foreign_keys:
                name = f'fk_{t.name}_{fk.parent.name}'
                out.append((t.name, name,
                            f'ALTER TABLE {cls._quote(t.name)} ADD CONSTRAINT '
                            f'{cls._quote(name)} FOREIGN KEY '
                            f'({cls._quote(fk.parent.name)}) REFERENCES '
                            f'{cls._quote(fk.column.table.name)} '
                            f'({cls._quote(fk.column.name)})'
                            + (f' ON DELETE {fk.ondelete}' if fk.ondelete else "")))
        return out

    @classmethod
    def _restore_postgresql(cls, src: str) -> None:
        statements = []
        with open(src, 'r', encoding='utf-8', errors='replace') as fh:
            for raw in fh:
                line = raw.strip()
                if line and not line.startswith('--'):
                    statements.append(line)
        if not statements:
            raise BackupError('النسخة لا تحتوي على بيانات قابلة للاستعادة.')
        names = sorted(db.metadata.tables)
        fks = cls._fk_defs()
        # The logical export is written in table-name order, which is not
        # dependency order, and the FKs are IMMEDIATE. Drop them for the load and
        # re-add afterwards -- re-adding succeeds only if the restored data is
        # referentially intact, so it doubles as the integrity check.
        try:
            for tname, cname, _ in fks:
                db.session.execute(text(
                    f'ALTER TABLE {cls._quote(tname)} '
                    f'DROP CONSTRAINT IF EXISTS {cls._quote(cname)}'))
            for name in reversed(names):
                db.session.execute(text(f'TRUNCATE TABLE {cls._quote(name)} CASCADE'))
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            raise BackupError(f'تعذر تفريغ الجداول: {exc}') from exc
        try:
            for stmt in statements:
                db.session.execute(text(stmt))
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            raise BackupError(f'فشل تحميل البيانات: {exc}') from exc
        try:
            for _tname, _cname, ddl in fks:
                db.session.execute(text(ddl))
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            raise BackupError(
                f'البيانات المستعادة تخالف قيود التكامل: {exc}') from exc
        try:
            cls._reset_postgresql_sequences()
        except Exception as exc:
            db.session.rollback()
            raise BackupError(f'فشل مزامنة التسلسلات: {exc}') from exc

    @classmethod
    def verify(cls, bid: str, user_name: str, ip_address: str):
        entry = cls._entry(bid)
        if entry is None:
            return False, 'ملف النسخة الاحتياطية غير موجود.', None, None
        engine = entry.get('engine', 'sqlite')
        fp = cls._backup_path(bid, engine)
        if not os.path.exists(fp):
            return False, 'ملف النسخة الاحتياطية غير موجود.', None, None
        try:
            if engine == 'sqlite':
                with sqlite3.connect(fp) as conn:
                    tables = conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    ).fetchone()[0]
                    emps = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
            else:
                tables, emps = cls._verify_dump(fp)
        except BackupError as exc:
            return False, str(exc), None, None
        except Exception as exc:
            return False, f'النسخة تالفة: {exc}', None, None
        cls._audit('verify', user_name, ip_address,
                   {'id': bid, 'tables': tables, 'employees': emps})
        return True, f'النسخة سليمة: {tables} جدول، {emps} موظف.', tables, emps

    @classmethod
    def delete(cls, bid: str):
        entry = cls._entry(bid)
        engine = entry.get('engine', 'sqlite') if entry else 'sqlite'
        fp = cls._backup_path(bid, engine)
        if os.path.exists(fp):
            os.remove(fp)
        cls._write_index([b for b in cls._read_index() if b['id'] != bid])

    @classmethod
    def download_path(cls, bid: str):
        entry = cls._entry(bid)
        engine = entry.get('engine', 'sqlite') if entry else 'sqlite'
        fp = cls._backup_path(bid, engine)
        return fp if os.path.exists(fp) else None
