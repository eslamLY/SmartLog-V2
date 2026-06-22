import os, json, logging
from datetime import datetime, UTC
from io import StringIO

from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
from models import db
from models.backup import BackupMetadata, BackupSchedule, BackupAuditLog, BackupConfig, BackupRestoreLog

logger = logging.getLogger(__name__)

backup_bp = Blueprint('backup_management', __name__, url_prefix='/admin/backup')


@backup_bp.route('')
def backup_dashboard():
    return render_template('admin/backup_management.html')


@backup_bp.route('/api/stats')
def get_stats():
    from services.backup_service import get_backup_stats, _get_backup_dir, _read_manifest
    from models.backup import BackupMetadata, BackupSchedule
    from models import db
    import os
    stats = get_backup_stats()
    # Convert by_type dict to array format for Chart.js
    by_type_arr = [{'type': k, 'count': v} for k, v in stats.get('by_type', {}).items()]
    # Build by_status from database
    by_status = {}
    try:
        rows = db.session.query(BackupMetadata.status, db.func.count(BackupMetadata.id)).group_by(BackupMetadata.status).all()
        by_status = {r[0] or 'completed': r[1] for r in rows}
    except Exception:
        pass
    by_status_arr = [{'status': k, 'count': v} for k, v in by_status.items()]
    # Build by_schedule from database
    by_schedule_arr = []
    try:
        scheds = BackupSchedule.query.all()
        for s in scheds:
            by_schedule_arr.append({'name': s.name, 'runs': s.total_runs or 0})
    except Exception:
        pass
    return jsonify({
        'ok': True,
        'total_backups': stats.get('total_backups', 0),
        'total_size_bytes': stats.get('total_size_bytes', 0),
        'total_size_display': stats.get('total_size_display', '0 B'),
        'encryption_rate': stats.get('encryption_rate', 0),
        'verified_rate': stats.get('verified_rate', 0),
        'active_schedules': stats.get('active_schedules', 0),
        'by_date': [{'date': d['date'], 'size_mb': round(d['total_bytes'] / 1048576, 2)} for d in stats.get('by_date', [])],
        'by_type': by_type_arr,
        'by_status': by_status_arr,
        'by_schedule': by_schedule_arr,
    })


@backup_bp.route('/api/list')
def list_backups():
    backup_type = request.args.get('type')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = BackupMetadata.query.filter(BackupMetadata.deleted_at.is_(None))
    if backup_type:
        query = query.filter_by(backup_type=backup_type)
    query = query.order_by(BackupMetadata.created_at.desc())
    total = query.count()
    backups = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'ok': True,
        'backups': [{
            'id': b.id,
            'filename': b.filename,
            'type': b.backup_type,
            'size_bytes': b.size_bytes,
            'size_display': b.size_display,
            'checksum': b.checksum,
            'encrypted': b.encrypted,
            'location': b.location,
            'status': b.status,
            'verified_at': b.verified_at.isoformat() if b.verified_at else None,
            'is_locked': b.is_locked,
            'description': b.description,
            'created_at': b.created_at.isoformat() if b.created_at else None,
        } for b in backups],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@backup_bp.route('/api/upload', methods=['POST'])
def upload_backup():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'لم يتم رفع أي ملف'})
    f = request.files['file']
    if not f.filename:
        return jsonify({'ok': False, 'error': 'اسم الملف فارغ'})
    from services.backup_service import _get_backup_dir
    bdir = _get_backup_dir()
    fn = secure_filename(f.filename)
    fp = os.path.join(bdir, fn)
    f.save(fp)
    from services.backup_service import _read_manifest
    manifest = _read_manifest(fp)
    if not manifest:
        os.remove(fp)
        return jsonify({'ok': False, 'error': 'ملف نسخة احتياطية غير صالح'})
    meta = BackupMetadata(
        filename=fn,
        backup_type=manifest.get('type', 'full'),
        size_bytes=os.path.getsize(fp),
        checksum=manifest.get('checksum', ''),
        encrypted=manifest.get('encrypted', False),
        filepath=fp,
        created_at=datetime.now(UTC),
    )
    db.session.add(meta)
    db.session.commit()
    return jsonify({
        'ok': True,
        'filename': fn,
        'id': meta.id,
        'size_bytes': os.path.getsize(fp),
        'type': manifest.get('type'),
    })


@backup_bp.route('/api/create', methods=['POST'])
def create_backup():
    data = request.get_json(silent=True) or {}
    backup_type = data.get('type', 'full')
    encrypt = data.get('encrypt', True)
    tables = data.get('tables')
    description = data.get('description', '')
    from services.backup_service import create_full_backup, create_incremental_backup, create_selective_backup
    if backup_type == 'incremental':
        result = create_incremental_backup(encrypt=encrypt)
    elif backup_type == 'selective':
        result = create_selective_backup(tables=tables, encrypt=encrypt)
    else:
        result = create_full_backup(encrypt=encrypt)
    if result.get('ok'):
        meta = BackupMetadata(
            filename=result['filename'],
            backup_type=backup_type,
            size_bytes=result.get('size_bytes', 0),
            checksum=result.get('checksum'),
            encrypted=encrypt,
            filepath=result.get('filepath'),
            description=description,
            created_at=datetime.now(UTC),
        )
        db.session.add(meta)
        db.session.commit()
        result['id'] = meta.id
    return jsonify(result)


@backup_bp.route('/api/delete/<int:backup_id>', methods=['DELETE'])
def delete_backup(backup_id):
    meta = BackupMetadata.query.get(backup_id)
    if not meta:
        return jsonify({'ok': False, 'error': 'النسخة غير موجودة'})
    from services.backup_service import delete_backup_file
    delete_backup_file(meta.filename, meta.filepath)
    meta.deleted_at = datetime.now(UTC)
    meta.status = 'deleted'
    db.session.commit()
    return jsonify({'ok': True})


@backup_bp.route('/api/restore', methods=['POST'])
def restore_backup():
    data = request.get_json(silent=True) or {}
    backup_id = data.get('backup_id')
    tables = data.get('tables')
    create_backup_first = data.get('create_backup_first', True)
    meta = BackupMetadata.query.get(backup_id)
    if not meta:
        return jsonify({'ok': False, 'error': 'النسخة غير موجودة'})
    from services.restoration_service import restore_from_backup
    result = restore_from_backup(
        meta.filepath,
        create_backup_first=create_backup_first,
        tables=tables,
    )
    log = BackupRestoreLog(
        backup_id=backup_id,
        backup_filename=meta.filename,
        restore_type='partial' if tables else 'full',
        status='completed' if result.get('ok') else 'failed',
        records_restored=result.get('records_restored', 0),
        tables_restored=result.get('tables_restored', 0),
        duration_seconds=result.get('duration_seconds'),
        error_message=result.get('error'),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(result)


@backup_bp.route('/api/preview/<int:backup_id>')
def preview_backup(backup_id):
    meta = BackupMetadata.query.get(backup_id)
    if not meta:
        return jsonify({'ok': False, 'error': 'النسخة غير موجودة'})
    from services.restoration_service import preview_restore_content
    content = preview_restore_content(meta.filepath)
    if not content:
        return jsonify({'ok': False, 'error': 'لا يمكن قراءة المحتويات'})
    return jsonify({'ok': True, 'content': content})


@backup_bp.route('/api/verify/<int:backup_id>')
def verify_backup(backup_id):
    meta = BackupMetadata.query.get(backup_id)
    if not meta:
        return jsonify({'ok': False, 'error': 'النسخة غير موجودة'})
    from services.backup_service import verify_backup_integrity
    result = verify_backup_integrity(meta.filepath)
    if result.get('ok'):
        meta.verified_at = datetime.now(UTC)
        meta.status = 'verified'
        db.session.commit()
    return jsonify(result)


@backup_bp.route('/api/verify-all', methods=['POST'])
def verify_all_backups():
    backups = BackupMetadata.query.filter(
        BackupMetadata.deleted_at.is_(None),
        BackupMetadata.status != 'verified'
    ).all()
    from services.backup_service import verify_backup_integrity
    results = []
    for b in backups:
        r = verify_backup_integrity(b.filepath)
        if r.get('ok'):
            b.verified_at = datetime.now(UTC)
            b.status = 'verified'
        else:
            b.status = 'corrupted'
        results.append({'id': b.id, 'filename': b.filename, 'ok': r.get('ok')})
    db.session.commit()
    return jsonify({'ok': True, 'results': results})


@backup_bp.route('/api/schedules')
def list_schedules():
    from services.backup_scheduler import list_schedules
    return jsonify({'ok': True, 'schedules': list_schedules()})


@backup_bp.route('/api/schedules/create', methods=['POST'])
def create_schedule():
    data = request.get_json(silent=True) or {}
    from services.backup_scheduler import create_schedule
    result = create_schedule(
        name=data.get('name', ''),
        backup_type=data.get('backup_type', 'full'),
        frequency=data.get('frequency', 'daily'),
        frequency_value=data.get('frequency_value', 1),
        time_str=data.get('time_str', '02:00'),
        destination=data.get('destination', 'local'),
        encrypt=data.get('encrypt', True),
        notify_on_success=data.get('notify_on_success', True),
        notify_on_failure=data.get('notify_on_failure', True),
        retention_count=data.get('retention_count', 20),
        employee_filter=data.get('employee_filter'),
    )
    return jsonify(result)


@backup_bp.route('/api/schedules/update/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    data = request.get_json(silent=True) or {}
    from services.backup_scheduler import update_schedule
    result = update_schedule(schedule_id, **data)
    return jsonify(result)


@backup_bp.route('/api/schedules/delete/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    from services.backup_scheduler import delete_schedule
    result = delete_schedule(schedule_id)
    return jsonify(result)


@backup_bp.route('/api/schedules/run/<int:schedule_id>', methods=['POST'])
def run_schedule(schedule_id):
    from services.backup_scheduler import run_scheduled_backup
    result = run_scheduled_backup(schedule_id)
    return jsonify(result)


@backup_bp.route('/api/schedules/status')
def scheduler_status():
    from services.backup_scheduler import get_scheduler_status
    return jsonify({'ok': True, **get_scheduler_status()})


@backup_bp.route('/api/schedules/toggle/<int:schedule_id>', methods=['POST'])
def toggle_schedule(schedule_id):
    schedule = BackupSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'ok': False, 'error': 'الجدول غير موجود'})
    schedule.is_active = not schedule.is_active
    db.session.commit()
    return jsonify({'ok': True, 'is_active': schedule.is_active})


@backup_bp.route('/api/audit')
def list_audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 30, type=int)
    action = request.args.get('action')
    query = BackupAuditLog.query
    if action:
        query = query.filter_by(action=action)
    query = query.order_by(BackupAuditLog.created_at.desc())
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'ok': True,
        'logs': [{
            'id': l.id,
            'action': l.action,
            'details': l.details,
            'user_name': l.user_name,
            'created_at': l.created_at.isoformat() if l.created_at else None,
        } for l in logs],
        'total': total,
        'page': page,
    })


@backup_bp.route('/api/config', methods=['GET', 'PUT'])
def backup_config():
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        config = BackupConfig.query.first()
        if not config:
            config = BackupConfig()
            db.session.add(config)
        for key, val in data.items():
            if hasattr(config, key) and key not in ('id', 'created_at', 'updated_at'):
                setattr(config, key, val)
        config.updated_at = datetime.now(UTC)
        db.session.commit()
        return jsonify({'ok': True})
    config = BackupConfig.query.first()
    if not config:
        config = BackupConfig()
        db.session.add(config)
        db.session.commit()
    return jsonify({
        'ok': True,
        'config': {
            'encryption_enabled': config.encryption_enabled,
            'compression_enabled': config.compression_enabled,
            'compression_level': config.compression_level,
            'auto_verify': config.auto_verify,
            'verify_interval_days': config.verify_interval_days,
            'retention_days': config.retention_days,
            'max_local_backups': config.max_local_backups,
            'secure_delete_passes': config.secure_delete_passes,
            'notification_email': config.notification_email,
            'backup_directory': config.backup_directory,
            'auto_cleanup_enabled': config.auto_cleanup_enabled,
        },
    })


@backup_bp.route('/api/restore-logs')
def restore_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = BackupRestoreLog.query.order_by(BackupRestoreLog.created_at.desc())
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'ok': True,
        'logs': [{
            'id': l.id,
            'backup_filename': l.backup_filename,
            'restore_type': l.restore_type,
            'status': l.status,
            'records_restored': l.records_restored,
            'tables_restored': l.tables_restored,
            'duration_seconds': l.duration_seconds,
            'error_message': l.error_message,
            'performed_by_name': l.performed_by_name,
            'created_at': l.created_at.isoformat() if l.created_at else None,
        } for l in logs],
        'total': total,
        'page': page,
    })


@backup_bp.route('/api/export-sql', methods=['POST'])
def export_backup_sql():
    from services.backup_service import export_backup_to_sql
    result = export_backup_to_sql()
    return jsonify(result)


@backup_bp.route('/api/delete-old', methods=['POST'])
def delete_old_backups():
    data = request.get_json(silent=True) or {}
    days = data.get('days', 90)
    from services.backup_service import clean_old_backups
    result = clean_old_backups(max_age_days=days)
    return jsonify(result)


@backup_bp.route('/api/archived')
def list_archived():
    meta_backups = BackupMetadata.query.filter(
        BackupMetadata.deleted_at.isnot(None)
    ).order_by(BackupMetadata.deleted_at.desc()).all()
    return jsonify({
        'ok': True,
        'archived': [{
            'id': b.id,
            'filename': b.filename,
            'type': b.backup_type,
            'size_display': b.size_display,
            'deleted_at': b.deleted_at.isoformat() if b.deleted_at else None,
            'created_at': b.created_at.isoformat() if b.created_at else None,
        } for b in meta_backups],
    })
