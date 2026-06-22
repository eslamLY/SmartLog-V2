import os, json, io, zlib, hashlib, shutil, struct, logging, sqlite3
from datetime import datetime, timedelta, date, UTC
from typing import Optional

logger = logging.getLogger(__name__)

def _get_backup_dir():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, 'backups')
    os.makedirs(d, exist_ok=True)
    return d

def _read_manifest(filepath: str) -> Optional[dict]:
    try:
        with open(filepath, 'rb') as f:
            prefix = f.read(4)
            if len(prefix) < 4:
                return None
            mlen = struct.unpack('>I', prefix)[0]
            if mlen > 1024 * 1024:
                return None
            manifest_json = f.read(mlen)
            if len(manifest_json) != mlen:
                return None
            return json.loads(manifest_json.decode('utf-8'))
    except Exception as e:
        logger.warning(f'Manifest read error {filepath}: {e}')
        return None

def _write_bak(filepath: str, manifest: dict, data: bytes) -> bool:
    try:
        mj = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
        with open(filepath, 'wb') as f:
            f.write(struct.pack('>I', len(mj)))
            f.write(mj)
            f.write(data)
        return True
    except Exception as e:
        logger.warning(f'BAK write error {filepath}: {e}')
        return False

def get_system_info() -> dict:
    import platform
    info = {'platform': platform.platform(), 'hostname': platform.node()}
    try:
        import psutil
        info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        info['memory_percent'] = psutil.virtual_memory().percent
        info['disk_free'] = psutil.disk_usage('/').free
    except ImportError:
        info['psutil'] = 'not available'
    return info

def get_backup_stats() -> dict:
    bdir = _get_backup_dir()
    total = 0
    total_size = 0
    encrypted = 0
    verified = 0
    by_type = {}
    by_date = {}
    for fn in os.listdir(bdir):
        if not fn.endswith('.bak'):
            continue
        fp = os.path.join(bdir, fn)
        manifest = _read_manifest(fp)
        if not manifest:
            continue
        total += 1
        sz = manifest.get('original_size', os.path.getsize(fp))
        total_size += sz
        btype = manifest.get('type', 'full')
        by_type[btype] = by_type.get(btype, 0) + 1
        dt_str = manifest.get('created_at', '')[:10]
        if dt_str:
            entry = by_date.get(dt_str, {'date': dt_str, 'count': 0, 'total_bytes': 0})
            entry['count'] += 1
            entry['total_bytes'] += sz
            by_date[dt_str] = entry
        if manifest.get('encrypted'):
            encrypted += 1
    by_date_list = sorted(by_date.values(), key=lambda x: x['date'])
    total_backups = total
    verified_q = 0
    from models.backup import BackupMetadata
    from models import db
    try:
        verified_q = BackupMetadata.query.filter_by(status='verified').count()
    except Exception:
        pass
    return {
        'total_backups': total_backups,
        'total_size_bytes': total_size,
        'total_size_display': _format_bytes(total_size),
        'encryption_rate': round((encrypted / total_backups) * 100, 1) if total_backups else 0,
        'verified_rate': round((verified_q / total_backups) * 100, 1) if total_backups else 0,
        'by_type': by_type,
        'by_date': by_date_list,
        'success_rate': 95,
        'active_schedules': 0,
    }

def _format_bytes(b):
    if b < 1024:
        return f'{b} B'
    elif b < 1048576:
        return f'{b / 1024:.1f} KB'
    elif b < 1073741824:
        return f'{b / 1048576:.1f} MB'
    return f'{b / 1073741824:.2f} GB'

def _collect_database_data(tables: list = None) -> dict:
    from models import db
    from sqlalchemy import inspect, text
    engine = db.engine
    insp = inspect(engine)
    all_tables = insp.get_table_names()
    skip = {'alembic_version', 'spatial_ref_sys', 'backup_metadata', 'backup_schedules', 'backup_audit_logs', 'backup_config', 'backup_restore_logs'}
    output = {}
    for table in all_tables:
        if table in skip:
            continue
        if tables and table not in tables:
            continue
        try:
            with engine.connect() as conn:
                rs = conn.execute(text(f'SELECT * FROM "{table}"'))
                rows = [dict(row._mapping) for row in rs.fetchall()]
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, (datetime, date)):
                        row[k] = v.isoformat()
                    elif isinstance(v, bytes):
                        row[k] = v.hex()
            output[table] = rows
        except Exception as e:
            logger.warning(f'Cannot backup table {table}: {e}')
    return output

def _collect_uploads() -> list:
    from flask import current_app
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.isdir(upload_dir):
        return []
    result = []
    for root, dirs, files in os.walk(upload_dir):
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, upload_dir)
            try:
                with open(fp, 'rb') as f:
                    content = f.read()
                result.append({'path': rel.replace('\\', '/'), 'size': len(content), 'content_hex': content.hex()})
            except Exception as e:
                logger.warning(f'Cannot read upload {fp}: {e}')
    return result

def create_full_backup(include_uploads: bool = True, encrypt: bool = True, master_password: str = None, dest_dir: str = None) -> dict:
    start = datetime.now(UTC)
    db_data = _collect_database_data()
    manifest = {
        'type': 'full',
        'created_at': start.isoformat(),
        'hostname': __import__('platform').node(),
        'encrypted': encrypt,
        'compression': 'zlib',
        'original_size': 0,
        'tables': list(db_data.keys()),
        'record_counts': {t: len(r) for t, r in db_data.items()},
        'total_records': sum(len(r) for r in db_data.values()),
    }
    payload = {'database': db_data}
    if include_uploads:
        uploads = _collect_uploads()
        payload['uploads'] = uploads
        manifest['uploads_count'] = len(uploads)
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    compressed = zlib.compress(raw, level=9)
    manifest['original_size'] = len(raw)
    manifest['compressed_size'] = len(compressed)
    data = compressed
    if encrypt:
        from services.encryption_service import encrypt_data
        enc = encrypt_data(compressed, master_password)
        if enc:
            data = enc
            manifest['encrypted'] = True
            manifest['encryption_method'] = 'AES-256-Fernet'
    checksum = hashlib.sha256(data).hexdigest()
    manifest['checksum'] = checksum
    ts = start.strftime('%Y%m%d_%H%M%S')
    fn = f'backup_full_{ts}.bak'
    bdir = dest_dir or _get_backup_dir()
    fp = os.path.join(bdir, fn)
    ok = _write_bak(fp, manifest, data)
    if not ok:
        return {'ok': False, 'error': 'فشل كتابة ملف النسخة'}
    return {
        'ok': True,
        'filename': fn,
        'filepath': fp,
        'size_bytes': os.path.getsize(fp),
        'size_display': _format_bytes(os.path.getsize(fp)),
        'checksum': checksum,
        'type': 'full',
        'tables': len(db_data),
        'records': manifest['total_records'],
        'created_at': start.isoformat(),
        'duration': (datetime.now(UTC) - start).total_seconds(),
    }

def create_incremental_backup(last_backup_path: str = None, encrypt: bool = True, master_password: str = None) -> dict:
    from models import db
    from sqlalchemy import text
    start = datetime.now(UTC)
    if last_backup_path and os.path.exists(last_backup_path):
        prev = extract_backup_content(last_backup_path)
    else:
        prev = None
    current_data = _collect_database_data()
    changes = {}
    total_changed = 0
    for table, rows in current_data.items():
        prev_rows = {}
        if prev:
            prev_rows = {json.dumps(r, default=str, sort_keys=True) for r in prev.get('database', prev.get('changes', {})).get(table, [])}
        current_set = {json.dumps(r, default=str, sort_keys=True) for r in rows}
        added = current_set - prev_rows
        if added:
            changes[table] = [json.loads(a) for a in added]
            total_changed += len(changes[table])
    manifest = {
        'type': 'incremental',
        'created_at': start.isoformat(),
        'hostname': __import__('platform').node(),
        'encrypted': encrypt,
        'compression': 'zlib',
        'original_size': 0,
        'tables_changed': list(changes.keys()),
        'total_changes': total_changed,
    }
    payload = {'changes': changes}
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    compressed = zlib.compress(raw, level=9)
    manifest['original_size'] = len(raw)
    data = compressed
    if encrypt:
        from services.encryption_service import encrypt_data
        enc = encrypt_data(compressed, master_password)
        if enc:
            data = enc
    checksum = hashlib.sha256(data).hexdigest()
    manifest['checksum'] = checksum
    ts = start.strftime('%Y%m%d_%H%M%S')
    fn = f'backup_inc_{ts}.bak'
    bdir = _get_backup_dir()
    fp = os.path.join(bdir, fn)
    ok = _write_bak(fp, manifest, data)
    if not ok:
        return {'ok': False, 'error': 'فشل كتابة النسخة التدريجية'}
    return {
        'ok': True,
        'filename': fn,
        'filepath': fp,
        'size_bytes': os.path.getsize(fp),
        'size_display': _format_bytes(os.path.getsize(fp)),
        'checksum': checksum,
        'type': 'incremental',
        'changes': total_changed,
        'tables': len(changes),
        'created_at': start.isoformat(),
        'duration': (datetime.now(UTC) - start).total_seconds(),
    }

def create_selective_backup(tables: list = None, encrypt: bool = True, master_password: str = None) -> dict:
    start = datetime.now(UTC)
    if not tables:
        return {'ok': False, 'error': 'لم يتم تحديد جداول'}
    db_data = _collect_database_data(tables=tables)
    if not db_data:
        return {'ok': False, 'error': 'لا توجد بيانات للجداول المحددة'}
    manifest = {
        'type': 'selective',
        'created_at': start.isoformat(),
        'hostname': __import__('platform').node(),
        'encrypted': encrypt,
        'compression': 'zlib',
        'original_size': 0,
        'tables': list(db_data.keys()),
        'record_counts': {t: len(r) for t, r in db_data.items()},
        'total_records': sum(len(r) for r in db_data.values()),
    }
    payload = {'database': db_data}
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    compressed = zlib.compress(raw, level=9)
    manifest['original_size'] = len(raw)
    data = compressed
    if encrypt:
        from services.encryption_service import encrypt_data
        enc = encrypt_data(compressed, master_password)
        if enc:
            data = enc
    checksum = hashlib.sha256(data).hexdigest()
    manifest['checksum'] = checksum
    ts = start.strftime('%Y%m%d_%H%M%S')
    fn = f'backup_sel_{ts}.bak'
    bdir = _get_backup_dir()
    fp = os.path.join(bdir, fn)
    ok = _write_bak(fp, manifest, data)
    if not ok:
        return {'ok': False, 'error': 'فشل كتابة النسخة الانتقائية'}
    return {
        'ok': True,
        'filename': fn,
        'filepath': fp,
        'size_bytes': os.path.getsize(fp),
        'size_display': _format_bytes(os.path.getsize(fp)),
        'checksum': checksum,
        'type': 'selective',
        'tables': len(db_data),
        'records': manifest['total_records'],
        'created_at': start.isoformat(),
        'duration': (datetime.now(UTC) - start).total_seconds(),
    }

def list_backups() -> list:
    bdir = _get_backup_dir()
    backups = []
    for fn in sorted(os.listdir(bdir), reverse=True):
        if not fn.endswith('.bak'):
            continue
        fp = os.path.join(bdir, fn)
        m = _read_manifest(fp)
        if not m:
            continue
        backups.append({
            'filename': fn,
            'filepath': fp,
            'type': m.get('type', 'full'),
            'created_at': m.get('created_at', ''),
            'size_bytes': os.path.getsize(fp),
            'size_display': _format_bytes(os.path.getsize(fp)),
            'encrypted': m.get('encrypted', False),
            'checksum': m.get('checksum', ''),
            'tables': m.get('tables', m.get('tables_changed', [])),
            'total_records': m.get('total_records', m.get('total_changes', 0)),
        })
    return backups

def extract_backup_content(filepath: str, master_password: str = None) -> Optional[dict]:
    manifest = _read_manifest(filepath)
    if not manifest:
        return None
    try:
        with open(filepath, 'rb') as f:
            prefix = f.read(4)
            mlen = struct.unpack('>I', prefix)[0]
            f.seek(4 + mlen)
            data = f.read()
    except Exception as e:
        logger.warning(f'Cannot read payload {filepath}: {e}')
        return None
    if manifest.get('encrypted'):
        from services.encryption_service import decrypt_data
        dec = decrypt_data(data, master_password)
        if not dec:
            logger.warning(f'Cannot decrypt {filepath}')
            return None
        data = dec
    try:
        decompressed = zlib.decompress(data)
    except zlib.error:
        decompressed = data
    try:
        content = json.loads(decompressed.decode('utf-8'))
    except Exception as e:
        logger.warning(f'Cannot parse payload {filepath}: {e}')
        return None
    content['type'] = manifest.get('type', 'full')
    content['created_at'] = manifest.get('created_at', '')
    return content

def verify_backup_integrity(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {'ok': False, 'error': 'الملف غير موجود'}
    manifest = _read_manifest(filepath)
    if not manifest:
        return {'ok': False, 'error': 'لا يمكن قراءة المانيفست'}
    checks = []
    checks.append({'check': 'ملف المانيفست', 'status': 'pass'})
    try:
        size = os.path.getsize(filepath)
        if size < 50:
            return {'ok': False, 'error': 'حجم الملف صغير جداً'}
        checks.append({'check': 'حجم الملف', 'status': 'pass', 'detail': _format_bytes(size)})
    except Exception as e:
        return {'ok': False, 'error': f'خطأ في قراءة الملف: {e}'}
    content = extract_backup_content(filepath)
    if not content:
        return {'ok': False, 'error': 'لا يمكن استخراج المحتويات (قد يكون التشفير غير متطابق)'}
    checks.append({'check': 'استخراج المحتويات', 'status': 'pass'})
    db_data = content.get('database', content.get('changes', {}))
    total_records = sum(len(v) for v in db_data.values())
    checks.append({'check': 'البيانات', 'status': 'pass', 'detail': f'{len(db_data)} جداول, {total_records} سجل'})
    expected_cs = manifest.get('checksum', '')
    if expected_cs:
        try:
            with open(filepath, 'rb') as f:
                prefix = f.read(4)
                mlen = struct.unpack('>I', prefix)[0]
                f.seek(4 + mlen)
                actual_cs = hashlib.sha256(f.read()).hexdigest()
            if actual_cs == expected_cs:
                checks.append({'check': 'التكامل (SHA256)', 'status': 'pass'})
            else:
                checks.append({'check': 'التكامل (SHA256)', 'status': 'fail', 'detail': 'عدم تطابق التوقيع'})
                return {'ok': False, 'error': 'فشل التحقق من التكامل', 'checks': checks}
        except Exception as e:
            checks.append({'check': 'التكامل', 'status': 'error', 'detail': str(e)})
    return {'ok': True, 'checks': checks, 'type': manifest.get('type'), 'created_at': manifest.get('created_at')}

def delete_backup_file(filename: str = None, filepath: str = None) -> bool:
    if filepath and os.path.exists(filepath):
        from services.encryption_service import secure_delete
        secure_delete(filepath)
        return True
    if filename:
        bdir = _get_backup_dir()
        fp = os.path.join(bdir, filename)
        if os.path.exists(fp):
            secure_delete(fp)
            return True
    return False

def clean_old_backups(max_count: int = 20, max_age_days: int = None) -> dict:
    bdir = _get_backup_dir()
    backups = []
    for fn in os.listdir(bdir):
        if not fn.endswith('.bak'):
            continue
        fp = os.path.join(bdir, fn)
        backups.append((fn, fp, os.path.getmtime(fp)))
    backups.sort(key=lambda x: x[2], reverse=True)
    deleted = 0
    if max_age_days:
        cutoff = datetime.now(UTC).timestamp() - max_age_days * 86400
        for fn, fp, mtime in backups:
            if mtime < cutoff:
                delete_backup_file(filepath=fp)
                deleted += 1
    if max_count and len(backups) > max_count:
        for fn, fp, mtime in backups[max_count:]:
            if os.path.exists(fp):
                delete_backup_file(filepath=fp)
                deleted += 1
    return {'ok': True, 'deleted': deleted}

def export_backup_to_sql(backup_id: int = None) -> dict:
    from models import db
    from sqlalchemy import text
    try:
        lines = []
        lines.append('-- Blood Bank Database Export')
        lines.append(f'-- Generated: {datetime.now(UTC).isoformat()}')
        lines.append('')
        engine = db.engine
        from sqlalchemy import inspect
        insp = inspect(engine)
        for table in insp.get_table_names():
            if table.startswith('backup_'):
                continue
            with engine.connect() as conn:
                result = conn.execute(text(f'SELECT * FROM "{table}"'))
                rows = [dict(r._mapping) for r in result.fetchall()]
            if not rows:
                continue
            col_names = list(rows[0].keys())
            cols = ', '.join(f'"{c}"' for c in col_names)
            lines.append(f'-- Table: {table} ({len(rows)} rows)')
            for row in rows:
                vals = []
                for c in col_names:
                    v = row[c]
                    if v is None:
                        vals.append('NULL')
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    elif isinstance(v, bytes):
                        vals.append(f"X'{v.hex()}'")
                    else:
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                lines.append(f'INSERT OR REPLACE INTO "{table}" ({cols}) VALUES ({", ".join(vals)});')
            lines.append('')
        sql = '\n'.join(lines)
        export_dir = os.path.join(_get_backup_dir(), 'sql_exports')
        os.makedirs(export_dir, exist_ok=True)
        fn = f'db_export_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.sql'
        fp = os.path.join(export_dir, fn)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(sql)
        return {'ok': True, 'filename': fn, 'filepath': fp, 'size_bytes': os.path.getsize(fp), 'tables': len(insp.get_table_names())}
    except Exception as e:
        logger.exception('SQL export failed')
        return {'ok': False, 'error': str(e)}
