import os
import logging

from flask import (Blueprint, render_template, request, session,
                   jsonify, send_file, current_app, redirect, url_for)

from functools import wraps
from utils.decorators import admin_required, login_required
from services.branding import BrandingService
from services.backup import BackupService
from services.audit import AuditService
from services.health import HealthService

admin_system_bp = Blueprint('admin_system_bp', __name__)

LOGGER = logging.getLogger(__name__)


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            LOGGER.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper


# ─── BRANDING ────────────────────────────────────────────────────────────────


@admin_system_bp.route('/admin/branding')
@admin_required
def admin_branding():
    cfg = BrandingService.get_or_create()
    return render_template('admin/branding.html', cfg=cfg)


@admin_system_bp.route('/admin/branding/save', methods=['POST'])
@admin_required
def save_branding():
    BrandingService.update(request.get_json() or {})
    return jsonify({'ok': True, 'msg': '✓ تم تحديث العلامة التجارية.'})


@admin_system_bp.route('/admin/branding/logo', methods=['POST'])
@admin_required
def upload_logo():
    url = BrandingService.upload_logo(
        request.files.get('logo'),
        current_app.config['UPLOAD_FOLDER']
    )
    if not url:
        return jsonify({'ok': False, 'msg': 'يرجى اختيار صورة صالحة (png/jpg).'})
    return jsonify({'ok': True, 'msg': '✓ تم تحديث الشعار.', 'url': url})


@admin_system_bp.route('/uploads/<path:filename>')
@admin_required
def uploaded_file(filename):
    return send_file(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))


@admin_system_bp.route('/api/branding')
@safe_api
def api_branding():
    return jsonify(BrandingService.to_dict(BrandingService.get_or_create()))


# ─── SYSTEM HEALTH ───────────────────────────────────────────────────────────


@admin_system_bp.route('/admin/system-health')
@admin_required
def admin_system_health():
    return render_template('admin/system_health.html')


@admin_system_bp.route('/api/admin/metrics')
@admin_required
@safe_api
def api_admin_metrics():
    return jsonify(HealthService.get_metrics())


# ─── BACKUPS ─────────────────────────────────────────────────────────────────


@admin_system_bp.route('/admin/backups')
@admin_required
def admin_backups():
    return redirect(url_for('backup_management.backup_dashboard'))


@admin_system_bp.route('/api/admin/backups')
@admin_required
@safe_api
def api_list_backups():
    return jsonify(BackupService.list())


@admin_system_bp.route('/api/admin/backup', methods=['POST'])
@admin_required
@safe_api
def api_create_backup():
    bid, err = BackupService.create(
        current_app.config['SQLALCHEMY_DATABASE_URI'],
        session.get('full_name', 'المدير'),
        request.remote_addr
    )
    if err:
        return jsonify({'ok': False, 'msg': err})
    return jsonify({'ok': True, 'msg': f'✓ تم إنشاء النسخة الاحتياطية {bid}.', 'id': bid})


@admin_system_bp.route('/api/admin/restore/<bid>', methods=['POST'])
@admin_required
@safe_api
def api_restore_backup(bid):
    err = BackupService.restore(bid, current_app.config['SQLALCHEMY_DATABASE_URI'])
    if err:
        return jsonify({'ok': False, 'msg': err})
    return jsonify({'ok': True, 'msg': '✓ تمت استعادة قاعدة البيانات. يُرجى إعادة تشغيل الخادم.'})


@admin_system_bp.route('/api/admin/backups/<bid>/verify', methods=['POST'])
@admin_required
@safe_api
def api_verify_backup(bid):
    ok, msg, *_ = BackupService.verify(
        bid,
        session.get('full_name', 'admin'),
        request.remote_addr
    )
    return jsonify({'ok': ok, 'msg': msg})


@admin_system_bp.route('/api/admin/backups/<bid>/delete', methods=['POST'])
@admin_required
@safe_api
def api_delete_backup(bid):
    BackupService.delete(bid)
    return jsonify({'ok': True, 'msg': '✓ تم حذف النسخة.'})


@admin_system_bp.route('/api/admin/backups/<bid>/download')
@admin_required
@safe_api
def api_download_backup(bid):
    fp = BackupService.download_path(bid)
    if not fp:
        return jsonify({'ok': False, 'msg': 'غير موجود.'})
    return send_file(fp, as_attachment=True, download_name=f'backup_{bid}.db')


# ─── AUDIT LOGS ──────────────────────────────────────────────────────────────


@admin_system_bp.route('/admin/audit-logs')
@admin_required
def admin_audit_logs():
    return render_template('admin/audit_logs.html')


@admin_system_bp.route('/api/admin/audit-logs')
@admin_required
@safe_api
def api_audit_logs():
    return jsonify(AuditService.query(
        request.args.get('date'),
        request.args.get('action')
    ))
