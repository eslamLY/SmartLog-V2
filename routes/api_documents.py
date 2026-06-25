import os, io, logging
from datetime import date, datetime, timedelta, UTC
from uuid import uuid4

from flask import Blueprint, request, session, jsonify, send_file, current_app
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from models import db, ArchivedDocument, DocumentAuditLog, Notification
from utils.decorators import admin_required, login_required
from services.document_service import generate_unique_reference, generate_document_pdf
from functools import wraps
logger = logging.getLogger(__name__)
api_documents_bp = Blueprint('api_documents_bp', __name__)

def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error('API error in %s: %s', f.__name__, e)
            return jsonify({'ok': False, 'msg': str(e)}), 500
    return wrapper


ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024


@api_documents_bp.route('/api/documents/upload', methods=['POST'])
@safe_api
@admin_required
def upload_document():
    d = request.get_json(silent=True)
    if d is None:
        d = request.form.to_dict() if request.form else {}

    title = (d.get('title') or '').strip()
    if not title:
        return jsonify({'ok': False, 'msg': 'عنوان المستند مطلوب.'})

    department = (d.get('department') or '').strip() or None
    employee_id = d.get('employee_id')
    if employee_id is not None:
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'msg': 'employee_id غير صالح.'})

    is_public = bool(d.get('is_public', False))
    has_expiry = bool(d.get('has_expiry_date', False))
    expiry_date = None
    if has_expiry:
        expiry_str = d.get('expiry_date')
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                if expiry_date < date.today():
                    return jsonify({'ok': False, 'msg': 'تاريخ الانتهاء يجب أن يكون في المستقبل.'})
            except (ValueError, TypeError):
                return jsonify({'ok': False, 'msg': 'صيغة تاريخ الانتهاء غير صالحة (YYYY-MM-DD).'})
        else:
            return jsonify({'ok': False, 'msg': 'تاريخ الانتهاء مطلوب عند تفعيل الخيار.'})

    existing_active = ArchivedDocument.query.filter_by(
        title=title
    ).filter(
        or_(ArchivedDocument.expiry_date.is_(None),
            ArchivedDocument.expiry_date >= date.today())
    ).first()
    if existing_active:
        latest_version = db.session.query(
            db.func.max(ArchivedDocument.version)
        ).filter(
            ArchivedDocument.reference_code == existing_active.reference_code
        ).scalar() or 0
        version = latest_version + 1
        reference_code = existing_active.reference_code
    else:
        existing_count = ArchivedDocument.query.filter_by(title=title).count()
        if existing_count == 0:
            reference_code = generate_unique_reference('DOC')
        else:
            latest_ref = ArchivedDocument.query.filter_by(title=title).order_by(
                ArchivedDocument.created_at.desc()).first()
            reference_code = latest_ref.reference_code
        version = 1

    notes = (d.get('notes') or '').strip() or None
    f = request.files.get('file')
    file_path = None
    if not f or not f.filename:
        return jsonify({'ok': False, 'msg': 'الملف مطلوب.'})

    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'ok': False, 'msg': 'نوع الملف غير مسموح به. الأنواع المسموحة: PDF, JPG, PNG, DOCX'})

    content = f.read()
    if len(content) > MAX_FILE_SIZE:
        return jsonify({'ok': False, 'msg': 'حجم الملف يتجاوز 10 ميغابايت.'})
    f.seek(0)

    safe_name = f'{employee_id or "unknown"}_{uuid4().hex[:12]}.{ext}'
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, safe_name)
    f.save(save_path)
    file_path = f'documents/{safe_name}'

    try:
        doc = ArchivedDocument(
            reference_code=reference_code,
            title=title,
            department=department,
            employee_id=employee_id,
            is_public=is_public,
            has_expiry_date=has_expiry,
            expiry_date=expiry_date,
            version=version,
            uploaded_by=session['user_id'],
            file_path=file_path,
            notes=notes,
        )
        db.session.add(doc)
        db.session.flush()
        DocumentAuditLog.log(doc.id, 'upload', session['user_id'],
            f'رفع مستند "{title}" برمز {reference_code} (نسخة {version})')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f'Failed to create archived document: {e}')
        return jsonify({'ok': False, 'msg': 'فشل في حفظ المستند.'})

    return jsonify({
        'ok': True,
        'msg': f'✓ تم أرشفة المستند "{title}" برمز {reference_code} (نسخة {version}).',
        'document': {
            'id': doc.id,
            'reference_code': doc.reference_code,
            'title': doc.title,
            'version': doc.version,
            'department': doc.department,
            'is_public': doc.is_public,
            'has_expiry_date': doc.has_expiry_date,
            'expiry_date': doc.expiry_date.strftime('%Y-%m-%d') if doc.expiry_date else None,
            'expiry_status': doc.expiry_status,
            'created_at': doc.created_at.strftime('%Y-%m-%d %H:%M') if doc.created_at else None,
        }
    })


@api_documents_bp.route('/api/documents/search')
@safe_api
@login_required
def search_documents():
    user_role = session.get('role', '')
    user_id = session.get('user_id')

    q = ArchivedDocument.query

    if hasattr(ArchivedDocument, 'is_deleted'):
        q = q.filter(ArchivedDocument.is_deleted == False)

    if user_role != 'admin':
        q = q.filter(
            or_(
                ArchivedDocument.employee_id == user_id,
                ArchivedDocument.is_public == True
            )
        )

    reference_code = request.args.get('reference_code', '').strip()
    if reference_code:
        q = q.filter(ArchivedDocument.reference_code.ilike(f'%{reference_code}%'))

    doc_type = request.args.get('doc_type', '').strip()
    if doc_type:
        q = q.filter(ArchivedDocument.title == doc_type)

    title_filter = request.args.get('title', '').strip()
    if title_filter:
        q = q.filter(ArchivedDocument.title.ilike(f'%{title_filter}%'))

    expiry_status = request.args.get('expiry_status', '').strip()
    if expiry_status:
        today = date.today()
        if expiry_status == 'expired':
            q = q.filter(ArchivedDocument.has_expiry_date == True,
                         ArchivedDocument.expiry_date < today)
        elif expiry_status == 'no_expiry':
            q = q.filter(ArchivedDocument.has_expiry_date == False)
        elif expiry_status == 'active':
            q = q.filter(
                or_(
                    ArchivedDocument.has_expiry_date == False,
                    ArchivedDocument.expiry_date >= today
                )
            )

    department = request.args.get('department', '').strip()
    if department:
        q = q.filter(ArchivedDocument.department == department)

    employee_id = request.args.get('employee_id', type=int)
    if employee_id is not None and user_role == 'admin':
        q = q.filter(ArchivedDocument.employee_id == employee_id)

    docs = q.order_by(ArchivedDocument.created_at.desc()).all()

    results = []
    for doc in docs:
        emp_name = doc.employee.full_name if doc.employee else None
        uploader_name = doc.uploader.full_name if doc.uploader else None
        results.append({
            'id': doc.id,
            'reference_code': doc.reference_code,
            'title': doc.title,
            'department': doc.department,
            'employee_name': emp_name,
            'employee_id': doc.employee_id,
            'is_public': doc.is_public,
            'has_expiry_date': doc.has_expiry_date,
            'expiry_date': doc.expiry_date.strftime('%Y-%m-%d') if doc.expiry_date else None,
            'expiry_status': doc.expiry_status,
            'version': doc.version,
            'uploaded_by': uploader_name,
            'notes': doc.notes,
            'created_at': doc.created_at.strftime('%Y-%m-%d %H:%M') if doc.created_at else None,
            'file_path': doc.file_path,
        })

    return jsonify({'ok': True, 'documents': results, 'total': len(results)})


@api_documents_bp.route('/api/documents/download-pdf/<int:doc_id>')
@safe_api
@login_required
def download_document_pdf(doc_id):
    doc = ArchivedDocument.query.get(doc_id)
    if not doc:
        return jsonify({'ok': False, 'msg': 'المستند غير موجود.'}), 404

    user_role = session.get('role', '')
    user_id = session.get('user_id')

    if user_role != 'admin':
        if doc.employee_id != user_id and not doc.is_public:
            return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية للوصول إلى هذا المستند.'}), 403

    try:
        pdf_bytes = generate_document_pdf(doc_id)
    except Exception as e:
        logger.error(f'PDF generation failed for doc {doc_id}: {e}')
        return jsonify({'ok': False, 'msg': 'فشل في إنشاء ملف PDF.'}), 500

    safe_name = doc.title.replace('/', '_').replace('\\', '_').replace(' ', '_')
    filename = f'{doc.reference_code}_{safe_name}.pdf'

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


@api_documents_bp.route('/api/documents/<int:doc_id>/edit', methods=['PUT'])
@safe_api
@admin_required
def edit_document(doc_id):
    doc = ArchivedDocument.query.get_or_404(doc_id)
    d = request.get_json(silent=True) or request.form.to_dict() if request.form else {}

    title = (d.get('title') or '').strip()
    if title:
        doc.title = title

    dept = (d.get('department') or '').strip() or None
    if 'department' in d:
        doc.department = dept

    emp_id = d.get('employee_id')
    if emp_id is not None:
        try:
            doc.employee_id = int(emp_id)
        except (TypeError, ValueError):
            pass

    if 'is_public' in d:
        doc.is_public = bool(d.get('is_public', False))

    if 'has_expiry_date' in d:
        doc.has_expiry_date = bool(d.get('has_expiry_date', False))
        if doc.has_expiry_date:
            expiry_str = d.get('expiry_date')
            if expiry_str:
                try:
                    doc.expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
        else:
            doc.expiry_date = None

    if 'notes' in d:
        doc.notes = (d.get('notes') or '').strip() or None

    f = request.files.get('file')
    if f and f.filename:
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        if ext in ALLOWED_EXTENSIONS:
            content = f.read()
            if len(content) <= MAX_FILE_SIZE:
                f.seek(0)
                safe_name = f'{doc.employee_id or "unknown"}_{uuid4().hex[:12]}.{ext}'
                upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
                os.makedirs(upload_dir, exist_ok=True)
                f.save(os.path.join(upload_dir, safe_name))
                doc.file_path = f'documents/{safe_name}'

    DocumentAuditLog.log(doc.id, 'edit', session['user_id'],
        f'تحديث المستند "{doc.title}" — الرمز {doc.reference_code}')
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم تحديث المستند.', 'document': {'id': doc.id, 'updated_at': doc.updated_at.strftime('%Y-%m-%d %H:%M') if doc.updated_at else None}})


@api_documents_bp.route('/api/documents/<int:doc_id>/delete', methods=['POST'])
@safe_api
@admin_required
def delete_document(doc_id):
    doc = ArchivedDocument.query.get_or_404(doc_id)
    doc.is_deleted = True
    doc.deleted_at = datetime.now(UTC)
    doc.deleted_by = session['user_id']
    DocumentAuditLog.log(doc.id, 'delete', session['user_id'],
        f'نقل المستند "{doc.title}" ({doc.reference_code}) إلى سلة المهملات')
    db.session.commit()
    return jsonify({'ok': True, 'msg': '✓ تم نقل المستند إلى سلة المهملات.'})


@api_documents_bp.route('/api/documents/<int:doc_id>/download')
@safe_api
@login_required
def download_original_document(doc_id):
    doc = ArchivedDocument.query.get_or_404(doc_id)

    user_role = session.get('role', '')
    user_id = session.get('user_id')
    if user_role != 'admin' and doc.employee_id != user_id and not doc.is_public:
        return jsonify({'ok': False, 'msg': 'ليس لديك صلاحية للوصول إلى هذا المستند.'}), 403

    if not doc.file_path:
        return jsonify({'ok': False, 'msg': 'هذا المستند لا يحتوي على ملف مرفوع.'}), 404

    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
    if not os.path.exists(full_path):
        return jsonify({'ok': False, 'msg': 'الملف غير موجود على الخادم.'}), 404

    ext = doc.file_path.rsplit('.', 1)[-1].lower()
    mime_map = {'pdf': 'application/pdf', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
    safe_name = doc.title.replace('/', '_').replace('\\', '_').replace(' ', '_')
    fname = f'{doc.reference_code}_{safe_name}.{ext}'

    return send_file(full_path, mimetype=mime_map.get(ext, 'application/octet-stream'), as_attachment=True, download_name=fname)


@api_documents_bp.route('/api/documents/<int:doc_id>/audit')
@safe_api
@admin_required
def document_audit_log(doc_id):
    doc = ArchivedDocument.query.get_or_404(doc_id)
    logs = doc.audit_logs.order_by(DocumentAuditLog.performed_at.desc()).limit(50).all()
    results = []
    for log in logs:
        performer_name = log.performer.full_name if log.performer else 'نظام'
        results.append({
            'id': log.id,
            'action': log.action,
            'performer': performer_name,
            'performed_at': log.performed_at.strftime('%Y-%m-%d %H:%M') if log.performed_at else None,
            'description': log.description,
            'details': log.details,
        })
    return jsonify({'ok': True, 'logs': results})


@api_documents_bp.route('/api/documents/<int:doc_id>/versions')
@safe_api
@admin_required
def document_versions(doc_id):
    doc = ArchivedDocument.query.get_or_404(doc_id)
    versions = ArchivedDocument.query.filter_by(reference_code=doc.reference_code).order_by(ArchivedDocument.version.desc()).all()
    results = []
    for v in versions:
        uploader_name = v.uploader.full_name if v.uploader else '—'
        results.append({
            'id': v.id,
            'version': v.version,
            'title': v.title,
            'file_path': v.file_path,
            'created_at': v.created_at.strftime('%Y-%m-%d %H:%M') if v.created_at else None,
            'uploaded_by': uploader_name,
            'expiry_date': v.expiry_date.strftime('%Y-%m-%d') if v.expiry_date else None,
            'has_expiry_date': v.has_expiry_date,
            'is_current': v.id == doc_id,
        })
    return jsonify({'ok': True, 'versions': results, 'reference_code': doc.reference_code})


@api_documents_bp.route('/api/documents/check-expiry', methods=['POST'])
@safe_api
@admin_required
def check_document_expiry():
    today = date.today()
    soon = ArchivedDocument.query.filter(
        ArchivedDocument.has_expiry_date == True,
        ArchivedDocument.is_deleted == False,
        ArchivedDocument.expiry_date.isnot(None),
        ArchivedDocument.expiry_date <= today + timedelta(days=30),
        ArchivedDocument.expiry_date >= today
    ).all()
    notified = 0
    for doc in soon:
        delta = (doc.expiry_date - today).days
        if delta in (30, 15, 7, 3, 1) or delta <= 0:
            emp_name = doc.employee.full_name if doc.employee else '—'
            notif = Notification(
                employee_id=1,
                type='document_expiry',
                title='مستند على وشك الانتهاء',
                message=f'المستند "{doc.title}" للموظف {emp_name} سينتهي في {doc.expiry_date.strftime("%Y-%m-%d")}',
                icon='ti-alert-triangle',
                ntype='warning',
                reference_id=doc.id,
                url='/admin/documents'
            )
            db.session.add(notif)
            notified += 1
    db.session.commit()
    return jsonify({'ok': True, 'msg': f'✓ تم التحقق من {len(soon)} مستند. {notified} إشعار جديد.'})
