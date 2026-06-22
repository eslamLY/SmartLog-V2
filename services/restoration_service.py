import os, io, json, zlib, hashlib, logging, shutil, zipfile
from datetime import datetime, UTC
from typing import Optional

from models import db
from flask import current_app

logger = logging.getLogger(__name__)


def restore_from_backup(filepath: str, master_password: str = None,
                        create_backup_first: bool = True,
                        tables: list = None) -> dict:
    if not os.path.exists(filepath):
        return {'ok': False, 'error': 'ملف النسخة غير موجود'}
    from services.backup_service import extract_backup_content
    content = extract_backup_content(filepath)
    if not content:
        return {'ok': False, 'error': 'لا يمكن قراءة محتويات النسخة'}
    if create_backup_first:
        from services.backup_service import create_full_backup
        pre = create_full_backup()
        if not pre.get('ok'):
            logger.warning('Pre-restore backup failed, continuing anyway')
    steps = []
    try:
        steps.append({'step': 'قراءة النسخة', 'status': 'success'})
        db_data = content.get('database', content.get('changes', {}))
        if tables:
            db_data = {k: v for k, v in db_data.items() if k in tables}
        total_records = sum(len(v) for v in db_data.values())
        from sqlalchemy import text
        for table, rows in db_data.items():
            if not rows:
                continue
            try:
                db.session.execute(text(f'DELETE FROM "{table}"'))
            except Exception as e:
                logger.warning(f'Cannot clear table {table}: {e}')
            if not rows:
                steps.append({'step': f'مسح {table}', 'status': 'success', 'records': 0})
                continue
            col_names = list(rows[0].keys())
            placeholders = ', '.join(f':{c}' for c in col_names)
            cols = ', '.join(f'"{c}"' for c in col_names)
            try:
                for row in rows:
                    clean = {}
                    for c in col_names:
                        val = row.get(c)
                        if isinstance(val, str):
                            try:
                                from datetime import datetime as dt
                                dt.fromisoformat(val)
                            except (ValueError, TypeError):
                                pass
                        clean[c] = val
                    db.session.execute(
                        text(f'INSERT OR REPLACE INTO "{table}" ({cols}) VALUES ({placeholders})'),
                        clean
                    )
                steps.append({'step': f'استعادة {table}', 'status': 'success', 'records': len(rows)})
            except Exception as e:
                steps.append({'step': f'استعادة {table}', 'status': 'failed', 'error': str(e)})
        uploads = content.get('uploads', [])
        if uploads:
            upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            restored_files = 0
            for u in uploads:
                try:
                    dest = os.path.join(upload_dir, u['path'])
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, 'wb') as f:
                        f.write(bytes.fromhex(u['content_hex']))
                    restored_files += 1
                except Exception as e:
                    logger.warning(f'Cannot restore upload {u.get("path")}: {e}')
            steps.append({'step': 'استعادة الملفات', 'status': 'success', 'records': restored_files})
        elapsed = (datetime.now(UTC) - datetime.fromisoformat(content.get('created_at', datetime.now(UTC).isoformat()))).total_seconds()
        return {
            'ok': True,
            'type': content.get('type', 'full'),
            'created_at': content.get('created_at'),
            'tables_restored': len(db_data),
            'records_restored': total_records,
            'uploads_restored': len(uploads),
            'steps': steps,
            'duration_seconds': round(abs(elapsed), 1),
        }
    except Exception as e:
        logger.exception('Restore failed')
        return {'ok': False, 'error': str(e), 'steps': steps}


def preview_restore_content(filepath: str) -> Optional[dict]:
    from services.backup_service import extract_backup_content
    content = extract_backup_content(filepath)
    if not content:
        return None
    db_data = content.get('database', content.get('changes', {}))
    result = {
        'type': content.get('type', 'full'),
        'created_at': content.get('created_at'),
        'tables': {},
        'total_records': 0,
        'has_uploads': 'uploads' in content,
        'total_uploads': len(content.get('uploads', [])),
    }
    for table, rows in db_data.items():
        result['tables'][table] = len(rows)
        result['total_records'] += len(rows)
    return result


def compare_backups(filepath_a: str, filepath_b: str) -> dict:
    from services.backup_service import extract_backup_content
    a = extract_backup_content(filepath_a)
    b = extract_backup_content(filepath_b)
    if not a or not b:
        return {'ok': False, 'error': 'لا يمكن قراءة إحدى النسختين'}
    db_a = a.get('database', a.get('changes', {}))
    db_b = b.get('database', b.get('changes', {}))
    all_tables = set(list(db_a.keys()) + list(db_b.keys()))
    differences = {}
    for table in all_tables:
        rows_a = db_a.get(table, [])
        rows_b = db_b.get(table, [])
        ids_a = {json.dumps(r, default=str, sort_keys=True) for r in rows_a}
        ids_b = {json.dumps(r, default=str, sort_keys=True) for r in rows_b}
        added = len(ids_b - ids_a)
        removed = len(ids_a - ids_b)
        if added or removed:
            differences[table] = {'before': len(rows_a), 'after': len(rows_b), 'added': added, 'removed': removed}
    return {
        'ok': True,
        'backup_a': {'filename': os.path.basename(filepath_a), 'created_at': a.get('created_at'), 'type': a.get('type')},
        'backup_b': {'filename': os.path.basename(filepath_b), 'created_at': b.get('created_at'), 'type': b.get('type')},
        'differences': differences,
        'total_tables_changed': len(differences),
    }


def verify_restore_capability(filepath: str) -> dict:
    checks = []
    result = {'ok': True, 'checks': checks}
    if not os.path.exists(filepath):
        return {'ok': False, 'error': 'الملف غير موجود'}
    meta_check = {'name': 'فحص الملف', 'status': 'success'}
    checks.append(meta_check)
    from services.backup_service import verify_backup_integrity
    integrity = verify_backup_integrity(filepath)
    if integrity.get('ok'):
        checks.append({'name': 'فحص التكامل', 'status': 'success'})
    else:
        checks.append({'name': 'فحص التكامل', 'status': 'failed', 'error': integrity.get('error')})
        result['ok'] = False
    content = preview_restore_content(filepath)
    if content:
        checks.append({'name': 'فحص المحتويات', 'status': 'success',
                       'details': f'{content["total_records"]} سجل في {len(content["tables"])} جداول'})
        table_check = True
        for t, c in content['tables'].items():
            try:
                from sqlalchemy import inspect
                insp = inspect(db.engine)
                if t in insp.get_table_names():
                    checks.append({'name': f'جدول {t}', 'status': 'success', 'details': f'{c} سجل'})
                else:
                    checks.append({'name': f'جدول {t}', 'status': 'warning', 'details': 'الجدول غير موجود في قاعدة البيانات الحالية'})
            except Exception as e:
                checks.append({'name': f'جدول {t}', 'status': 'warning', 'error': str(e)})
    else:
        checks.append({'name': 'فحص المحتويات', 'status': 'failed', 'error': 'لا يمكن قراءة المحتويات'})
        result['ok'] = False
    try:
        test_dir = os.path.join(current_app.instance_path, 'restore_test')
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, 'write_test.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        checks.append({'name': 'صلاحية الكتابة', 'status': 'success'})
    except Exception as e:
        checks.append({'name': 'صلاحية الكتابة', 'status': 'failed', 'error': str(e)})
        result['ok'] = False
    return result


def archive_old_backups(destination_dir: str, max_age_days: int = 90,
                        backup_dir: str = None) -> dict:
    from services.backup_service import _get_backup_dir
    backup_dir = backup_dir or _get_backup_dir()
    if not os.path.isdir(backup_dir):
        return {'ok': False, 'error': 'مجلد النسخ غير موجود'}
    os.makedirs(destination_dir, exist_ok=True)
    now = datetime.now(UTC).timestamp()
    cutoff = now - max_age_days * 86400
    archived = 0
    for fn in os.listdir(backup_dir):
        if not fn.endswith('.bak'):
            continue
        fp = os.path.join(backup_dir, fn)
        mtime = os.path.getmtime(fp)
        if mtime < cutoff:
            dest = os.path.join(destination_dir, fn)
            shutil.move(fp, dest)
            archived += 1
    return {'ok': True, 'archived': archived, 'destination': destination_dir}


def create_disaster_recovery_package(output_dir: str = None) -> dict:
    from services.backup_service import create_full_backup, get_system_info
    start = datetime.now(UTC)
    if output_dir is None:
        output_dir = os.path.join(current_app.instance_path, 'disaster_recovery')
    os.makedirs(output_dir, exist_ok=True)
    backup = create_full_backup(include_uploads=True, encrypt=True, dest_dir=output_dir)
    if not backup.get('ok'):
        return {'ok': False, 'error': 'فشل إنشاء النسخة'}
    info = get_system_info()
    readme = f"""حزمة التعافي من الكوارث - Disaster Recovery Package
تم الإنشاء: {start.isoformat()}
النظام: {info.get('platform', 'unknown')}
المضيف: {info.get('hostname', 'unknown')}
ملف النسخة: {backup.get('filename', 'unknown')}
حجم النسخة: {backup.get('size_display', 'unknown')}
التوقيع: {backup.get('checksum', 'unknown')}
للتعافي: استخدم وظيفة استرجاع النسخة في لوحة التحكم
"""
    readme_path = os.path.join(output_dir, 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme)
    return {
        'ok': True,
        'package_dir': output_dir,
        'backup': backup,
        'readme': readme_path,
        'created_at': start.isoformat(),
    }
