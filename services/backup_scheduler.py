import os, json, logging, threading
from datetime import datetime, timedelta, UTC
from typing import Optional

from models import db
from models.backup import BackupSchedule, BackupAuditLog
from flask import current_app

logger = logging.getLogger(__name__)

_scheduler_thread = None
_scheduler_running = False
_scheduler_lock = threading.Lock()


def _check_interval(last_run: datetime, interval_type: str, interval_value: int) -> bool:
    if not last_run:
        return True
    now = datetime.now(UTC)
    if interval_type == 'minutes':
        return (now - last_run).total_seconds() >= interval_value * 60
    elif interval_type == 'hours':
        return (now - last_run).total_seconds() >= interval_value * 3600
    elif interval_type == 'days':
        return (now - last_run).total_seconds() >= interval_value * 86400
    elif interval_type == 'weekly':
        return (now - last_run).days >= 7
    elif interval_type == 'monthly':
        return (now - last_run).days >= 30
    return True


def create_schedule(name: str, backup_type: str, frequency: str,
                    frequency_value: int = 1, time_str: str = '02:00',
                    destination: str = 'local', encrypt: bool = True,
                    notify_on_success: bool = True,
                    notify_on_failure: bool = True,
                    retention_count: int = 20,
                    employee_filter: list = None) -> dict:
    schedule = BackupSchedule(
        name=name,
        backup_type=backup_type,
        frequency=frequency,
        frequency_value=frequency_value,
        time_str=time_str,
        destination=destination,
        encrypt=encrypt,
        notify_on_success=notify_on_success,
        notify_on_failure=notify_on_failure,
        retention_count=retention_count,
        employee_filter=json.dumps(employee_filter or [], ensure_ascii=False),
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.session.add(schedule)
    db.session.commit()
    return {'ok': True, 'id': schedule.id, 'name': schedule.name}


def update_schedule(schedule_id: int, **kwargs) -> dict:
    schedule = BackupSchedule.query.get(schedule_id)
    if not schedule:
        return {'ok': False, 'error': 'الجدول غير موجود'}
    for key, val in kwargs.items():
        if hasattr(schedule, key) and key not in ('id', 'created_at'):
            if key == 'employee_filter' and isinstance(val, list):
                val = json.dumps(val, ensure_ascii=False)
            setattr(schedule, key, val)
    db.session.commit()
    return {'ok': True}


def delete_schedule(schedule_id: int) -> dict:
    schedule = BackupSchedule.query.get(schedule_id)
    if not schedule:
        return {'ok': False, 'error': 'الجدول غير موجود'}
    db.session.delete(schedule)
    db.session.commit()
    log_action('delete_schedule', f'حذف جدول النسخ: {schedule.name}')
    return {'ok': True}


def list_schedules() -> list:
    schedules = BackupSchedule.query.order_by(BackupSchedule.created_at.desc()).all()
    return [{
        'id': s.id,
        'name': s.name,
        'backup_type': s.backup_type,
        'frequency': s.frequency,
        'frequency_value': s.frequency_value,
        'time_str': s.time_str,
        'destination': s.destination,
        'encrypt': s.encrypt,
        'is_active': s.is_active,
        'last_run': s.last_run.isoformat() if s.last_run else None,
        'last_status': s.last_status,
        'last_duration': s.last_duration,
        'last_size': s.last_size,
        'next_run': s.next_run.isoformat() if s.next_run else None,
        'total_runs': s.total_runs,
        'successful_runs': s.successful_runs,
        'failed_runs': s.failed_runs,
        'notify_on_success': s.notify_on_success,
        'notify_on_failure': s.notify_on_failure,
        'retention_count': s.retention_count,
        'employee_filter': json.loads(s.employee_filter) if s.employee_filter else [],
        'created_at': s.created_at.isoformat() if s.created_at else None,
    } for s in schedules]


def run_scheduled_backup(schedule_id: int) -> dict:
    schedule = BackupSchedule.query.get(schedule_id)
    if not schedule:
        return {'ok': False, 'error': 'الجدول غير موجود'}
    if not schedule.is_active:
        return {'ok': False, 'error': 'الجدول غير نشط'}
    start = datetime.now(UTC)
    from services.backup_service import create_full_backup, create_incremental_backup, create_selective_backup
    result = None
    try:
        if schedule.backup_type == 'full':
            result = create_full_backup(encrypt=schedule.encrypt)
        elif schedule.backup_type == 'incremental':
            from services.backup_service import list_backups
            backups = list_backups()
            last_path = backups[0]['filepath'] if backups else None
            result = create_incremental_backup(last_backup_path=last_path, encrypt=schedule.encrypt)
        elif schedule.backup_type == 'selective':
            tables = json.loads(schedule.employee_filter) if schedule.employee_filter else []
            result = create_selective_backup(tables=tables, encrypt=schedule.encrypt)
        else:
            result = create_full_backup(encrypt=schedule.encrypt)
    except Exception as e:
        logger.exception(f'Scheduled backup {schedule.name} failed')
        result = {'ok': False, 'error': str(e)}
    duration = (datetime.now(UTC) - start).total_seconds()
    schedule.last_run = start
    schedule.last_duration = round(duration, 2)
    schedule.total_runs += 1
    if result and result.get('ok'):
        schedule.last_status = 'success'
        schedule.successful_runs += 1
        schedule.last_size = result.get('size_bytes', 0)
        from services.backup_service import clean_old_backups
        clean_old_backups(max_count=schedule.retention_count)
        if schedule.notify_on_success:
            _send_notification(f'Backup OK: {schedule.name}', f'Completed in {round(duration, 1)}s')
    else:
        schedule.last_status = 'failed'
        schedule.failed_runs += 1
        schedule.last_size = 0
        error_msg = result.get('error', 'Unknown error') if result else 'Unknown failure'
        if schedule.notify_on_failure:
            _send_notification(f'Backup FAILED: {schedule.name}', f'Error: {error_msg}')
    _calculate_next_run(schedule)
    db.session.commit()
    result['schedule_id'] = schedule.id
    result['schedule_name'] = schedule.name
    result['duration_seconds'] = round(duration, 2)
    return result


def _calculate_next_run(schedule: BackupSchedule):
    now = datetime.now(UTC)
    if schedule.frequency == 'daily':
        parts = schedule.time_str.split(':')
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        next_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if next_dt <= now:
            next_dt += timedelta(days=1)
        schedule.next_run = next_dt
    elif schedule.frequency == 'weekly':
        parts = schedule.time_str.split(':')
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        next_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        days_ahead = 0
        while days_ahead < 7:
            if next_dt > now:
                break
            next_dt += timedelta(days=1)
            days_ahead += 1
        schedule.next_run = next_dt
    elif schedule.frequency == 'monthly':
        day_of_month = min(int(schedule.time_str.split(':')[0]), 28)
        next_dt = now.replace(day=day_of_month, hour=2, minute=0, second=0, microsecond=0)
        if next_dt <= now:
            if now.month == 12:
                next_dt = next_dt.replace(year=now.year + 1, month=1)
            else:
                next_dt = next_dt.replace(month=now.month + 1)
        schedule.next_run = next_dt
    elif schedule.frequency == 'hours':
        schedule.next_run = now + timedelta(hours=schedule.frequency_value or 1)
    elif schedule.frequency == 'minutes':
        schedule.next_run = now + timedelta(minutes=schedule.frequency_value or 30)
    else:
        schedule.next_run = now + timedelta(days=1)


def check_due_schedules() -> list:
    schedules = BackupSchedule.query.filter_by(is_active=True).all()
    now = datetime.now(UTC)
    executed = []
    for s in schedules:
        if s.next_run and s.next_run <= now:
            result = run_scheduled_backup(s.id)
            executed.append({'schedule_id': s.id, 'name': s.name, 'result': result.get('ok')})
        elif not s.next_run:
            _calculate_next_run(s)
            db.session.commit()
    return executed


def log_action(action: str, details: str = '', user_id: int = None, user_name: str = None) -> None:
    try:
        log = BackupAuditLog(
            action=action,
            details=details,
            user_id=user_id,
            user_name=user_name or 'system',
            created_at=datetime.now(UTC),
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning(f'Cannot log action {action}: {e}')


def get_scheduler_status() -> dict:
    schedules = BackupSchedule.query.filter_by(is_active=True).all()
    total = len(schedules)
    success_rate = 0
    total_runs_all = 0
    for s in schedules:
        total_runs_all += s.total_runs
    if total:
        success_sum = sum(s.successful_runs for s in schedules)
        total_sum = sum(s.total_runs for s in schedules) or 1
        success_rate = round((success_sum / total_sum) * 100, 1)
    next_run = min((s.next_run for s in schedules if s.next_run), default=None)
    return {
        'active_schedules': total,
        'success_rate': success_rate,
        'total_runs': total_runs_all,
        'next_run': next_run.isoformat() if next_run else None,
        'is_running': _scheduler_running,
    }


def _send_notification(title: str, message: str) -> None:
    try:
        logger.info(f'Backup notification: {title} - {message}')
    except Exception as e:
        logger.warning(f'Notification failed: {e}')


def start_scheduler_loop(interval_seconds: int = 60):
    global _scheduler_running, _scheduler_thread
    with _scheduler_lock:
        if _scheduler_running:
            return
        _scheduler_running = True
    def _loop():
        global _scheduler_running
        while _scheduler_running:
            try:
                with current_app.app_context():
                    executed = check_due_schedules()
                    if executed:
                        for e in executed:
                            logger.info(f'Scheduled backup {e["name"]}: {"success" if e["result"] else "failed"}')
            except Exception as ex:
                logger.warning(f'Scheduler loop error: {ex}')
            import time
            time.sleep(interval_seconds)
    _scheduler_thread = threading.Thread(target=_loop, daemon=True)
    _scheduler_thread.start()
    logger.info(f'Backup scheduler started (interval: {interval_seconds}s)')


def stop_scheduler_loop():
    global _scheduler_running
    _scheduler_running = False
    logger.info('Backup scheduler stopped')


def get_schedule_stats(schedule_id: int = None, days: int = 30) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    if schedule_id:
        logs = BackupAuditLog.query.filter(
            BackupAuditLog.schedule_id == schedule_id,
            BackupAuditLog.created_at >= since
        ).all()
    else:
        logs = BackupAuditLog.query.filter(
            BackupAuditLog.created_at >= since
        ).all()
    success = sum(1 for l in logs if 'success' in l.details.lower())
    failed = sum(1 for l in logs if 'fail' in l.details.lower())
    return {
        'total_events': len(logs),
        'success': success,
        'failed': failed,
        'rate': round((success / (success + failed)) * 100, 1) if (success + failed) else 100,
    }
