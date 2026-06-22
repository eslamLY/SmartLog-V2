import io, os, logging
from datetime import datetime, date, UTC
from sqlalchemy import func, text

from models import db, DocumentReference, ArchivedDocument
from fpdf import FPDF
from flask import current_app

logger = logging.getLogger(__name__)

_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
_ARIAL_PATH = os.path.join(_FONTS_DIR, 'Arial.ttf')
_ARIAL_BOLD_PATH = os.path.join(_FONTS_DIR, 'ArialBold.ttf')
_ARIAL_ITALIC_PATH = os.path.join(_FONTS_DIR, 'ArialItalic.ttf')


def _init_pdf(pdf):
    if not os.path.exists(_ARIAL_PATH):
        raise RuntimeError(
            f'Arial Unicode font not found at "{_ARIAL_PATH}". '
            'Place Arial.ttf, ArialBold.ttf, and ArialItalic.ttf in the fonts/ directory.'
        )
    pdf.add_font('ArialUnicode', '', _ARIAL_PATH)
    pdf.add_font('ArialUnicode', 'B', _ARIAL_BOLD_PATH)
    pdf.add_font('ArialUnicode', 'I', _ARIAL_ITALIC_PATH)


def generate_unique_reference(doc_type='DOC'):
    now = datetime.now(UTC)
    year = now.year
    prefix = doc_type.upper()
    max_retries = 5

    for attempt in range(max_retries):
        try:
            latest = db.session.query(
                func.max(
                    func.cast(
                        func.substr(DocumentReference.reference_code, -4, 4),
                        db.Integer
                    )
                )
            ).filter(
                DocumentReference.reference_code.like(f'{prefix}-{year}-%')
            ).scalar()

            if latest and latest > 0:
                seq = latest + 1
            else:
                seq = 1

            ref_code = f'{prefix}-{year}-{seq:04d}'

            ref = DocumentReference(reference_code=ref_code)
            db.session.add(ref)
            db.session.flush()
            db.session.commit()
            return ref_code

        except Exception:
            db.session.rollback()
            if attempt == max_retries - 1:
                raise
    return None


def generate_document_pdf(doc_id):
    doc = ArchivedDocument.query.get(doc_id)
    if not doc:
        raise ValueError(f'Document with id {doc_id} not found.')

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    _init_pdf(pdf)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    pdf.set_font('ArialUnicode', 'B', 18)
    pdf.cell(0, 14, 'Document Record', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(8)

    pdf.set_font('ArialUnicode', '', 10)
    pdf.cell(0, 6, f'Generated: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}',
             new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(10)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    fields = [
        ('Reference Code', doc.reference_code),
        ('Title', doc.title),
        ('Department', doc.department or 'N/A'),
        ('Version', str(doc.version)),
        ('Public Document', 'Yes' if doc.is_public else 'No'),
    ]

    if doc.employee:
        fields.append(('Employee', f'{doc.employee.full_name} (ID: {doc.employee.id})'))
    else:
        fields.append(('Employee', 'N/A'))

    fields.append(('File Path', doc.file_path or 'N/A'))

    if doc.has_expiry_date and doc.expiry_date:
        fields.append(('Expiry Date', doc.expiry_date.strftime('%Y-%m-%d')))
        fields.append(('Expiry Status', doc.expiry_status))
    else:
        fields.append(('Expiry Date', 'No expiry'))

    fields.append(('Created At', doc.created_at.strftime('%Y-%m-%d %H:%M') if doc.created_at else 'N/A'))
    fields.append(('Updated At', doc.updated_at.strftime('%Y-%m-%d %H:%M') if doc.updated_at else 'N/A'))

    if doc.uploader:
        fields.append(('Uploaded By', doc.uploader.full_name))

    pdf.set_font('ArialUnicode', 'B', 11)
    pdf.cell(0, 10, 'Document Metadata', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    for label, value in fields:
        pdf.set_font('ArialUnicode', 'B', 10)
        pdf.cell(50, 7, label + ':', align='R')
        pdf.set_font('ArialUnicode', '', 10)
        pdf.cell(0, 7, '  ' + str(value), new_x='LMARGIN', new_y='NEXT')

    pdf.ln(8)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    pdf.set_font('ArialUnicode', 'I', 8)
    pdf.cell(0, 5, f'Document ID: {doc.id}  |  Page 1/1',
             new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.cell(0, 5, 'This is a computer-generated document.',
             new_x='LMARGIN', new_y='NEXT', align='C')

    if doc.file_path:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
        if os.path.exists(full_path):
            ext = doc.file_path.rsplit('.', 1)[-1].lower()
            if ext in ('jpg', 'jpeg', 'png'):
                try:
                    pdf.add_page()
                    page_w = pdf.w - 2 * pdf.l_margin
                    page_h = pdf.h - 2 * pdf.t_margin
                    pdf.image(full_path, x=pdf.l_margin, y=pdf.t_margin, w=page_w)
                except Exception as e:
                    logger.warning(f'Could not embed image for doc {doc_id}: {e}')
            elif ext == 'pdf':
                try:
                    from pypdf import PdfMerger
                    meta_buf = io.BytesIO()
                    pdf.output(meta_buf)
                    meta_buf.seek(0)

                    merger = PdfMerger()
                    merger.append(meta_buf)
                    merger.append(full_path)
                    output = io.BytesIO()
                    merger.write(output)
                    merger.close()
                    output.seek(0)
                    return output.read()
                except Exception as e:
                    logger.warning(f'Could not merge PDF for doc {doc_id}: {e}')

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf.read()
