import json, logging, requests, hmac, hashlib, time
from datetime import datetime, timedelta, UTC
from urllib.parse import urlencode

from models import db
from models.notification_log import NotificationLog, NotificationTemplate, WhatsAppConfig

logger = logging.getLogger(__name__)

WHATSAPP_PROVIDERS = {
    'ultramsg': {
        'base_url': 'https://api.ultramsg.com/{instance_id}/messages/chat',
        'required_keys': ['instance_id', 'token'],
    },
    'twilio': {
        'base_url': 'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json',
        'required_keys': ['account_sid', 'auth_token', 'from_number'],
    },
    'whatsapp_web': {
        'base_url': 'http://localhost:3001/api/send',
        'required_keys': ['webhook_url'],
    },
}

QUIET_HOURS_START = 22
QUIET_HOURS_END = 7


def is_quiet_hours():
    now = datetime.now(UTC).hour
    if QUIET_HOURS_START <= now or now < QUIET_HOURS_END:
        return True
    return False


def load_config():
    cfg = WhatsAppConfig.query.first()
    if not cfg:
        cfg = WhatsAppConfig(
            enabled=False,
            provider='ultramsg',
            instance_id='',
            token='',
            account_sid='',
            auth_token='',
            from_number='',
            webhook_url='',
            quiet_hours_enabled=True,
            notifications_enabled=json.dumps({
                'clock_in_alert': True,
                'late_alert': True,
                'absent_alert': True,
                'document_expiry': True,
                'monthly_summary': True,
                'device_offline': True,
            }, ensure_ascii=False),
        )
        db.session.add(cfg)
        db.session.commit()
    return cfg


def send_whatsapp(recipient, message, notification_type=None, reference_id=None):
    cfg = load_config()
    if not cfg.enabled:
        logger.warning('WhatsApp disabled.')
        return None
    if cfg.quiet_hours_enabled and is_quiet_hours():
        logger.info('Quiet hours — skipping message.')
        return None
    notif_settings = cfg.notifications_settings
    if notification_type and notif_settings.get(notification_type, True) is False:
        logger.info(f'Notification type {notification_type} disabled.')
        return None
    recipient = recipient.strip()
    if not recipient.startswith('+') and not recipient.startswith('2'):
        recipient = '+' + recipient
    success = False
    response_data = None
    error_msg = None
    try:
        if cfg.provider == 'ultramsg':
            resp = requests.post(
                WHATSAPP_PROVIDERS['ultramsg']['base_url'].format(instance_id=cfg.instance_id),
                data={
                    'token': cfg.token,
                    'to': recipient,
                    'body': message,
                    'priority': 10,
                },
                timeout=30,
            )
            result = resp.json()
            if resp.ok and result.get('sent'):
                success = True
                response_data = result
            else:
                error_msg = result.get('error', resp.text)
        elif cfg.provider == 'twilio':
            from twilio.rest import Client
            client = Client(cfg.account_sid, cfg.auth_token)
            msg = client.messages.create(
                body=message,
                from_=cfg.from_number,
                to=recipient,
            )
            success = msg.status in ('queued', 'sent', 'delivered')
            response_data = {'sid': msg.sid, 'status': msg.status}
        elif cfg.provider == 'whatsapp_web':
            resp = requests.post(
                WHATSAPP_PROVIDERS['whatsapp_web']['base_url'],
                json={'to': recipient, 'message': message, 'webhook': cfg.webhook_url},
                timeout=30,
            )
            if resp.ok:
                success = True
                response_data = resp.json()
            else:
                error_msg = resp.text
    except Exception as e:
        error_msg = str(e)
        logger.error(f'WhatsApp send failed: {e}')
    log = NotificationLog(
        recipient=recipient,
        message=message,
        notification_type=notification_type,
        reference_id=reference_id,
        status='sent' if success else 'failed',
        provider=cfg.provider,
        response_data=json.dumps(response_data, ensure_ascii=False) if response_data else None,
        error_message=error_msg,
    )
    db.session.add(log)
    db.session.commit()
    return log


def send_clock_in_alert(employee_name, clock_in_time, device_name, manager_phone):
    message = f'✅ {employee_name} سجّل حضوره في {clock_in_time} عبر {device_name}'
    return send_whatsapp(manager_phone, message, notification_type='clock_in_alert')


def send_late_alert(employee_name, late_minutes, employee_phone):
    message = f'⏰ تأخرت {late_minutes} دقيقة اليوم. يرجى التواصل مع مشرفك.'
    return send_whatsapp(employee_phone, message, notification_type='late_alert')


def send_absent_alert(employee_name, manager_phone):
    message = f'🚨 {employee_name} لم يسجّل حضوره حتى الآن'
    return send_whatsapp(manager_phone, message, notification_type='absent_alert')


def send_document_expiry_alert(document_type, employee_name, days_left, hr_phone):
    message = f'📄 مستند {document_type} للموظف {employee_name} ينتهي خلال {days_left} أيام'
    return send_whatsapp(hr_phone, message, notification_type='document_expiry')


def send_monthly_summary(employee_name, month, present_days, absent_days, employee_phone):
    message = f'📊 ملخص حضورك لشهر {month}: حاضر {present_days} يوم، غياب {absent_days} يوم'
    return send_whatsapp(employee_phone, message, notification_type='monthly_summary')


def send_device_offline_alert(device_name, offline_since, it_admin_phone):
    message = f'🔴 جهاز البصمة {device_name} انقطع عن الاتصال منذ {offline_since}'
    return send_whatsapp(it_admin_phone, message, notification_type='device_offline')


def send_emergency_recall(employees_data):
    results = []
    now = datetime.now(UTC)
    for emp in employees_data:
        name = emp.get('full_name', '')
        phone = emp.get('phone', '')
        confirm_link = emp.get('confirm_link', '')
        message = (
            f'🚨 استدعاء طارئ من بنك الدم 🚨\n\n'
            f'نحتاج حضورك فوراً للعمل.\n'
            f'الرجاء الرد: هل يمكنك الحضور الآن؟\n\n'
            f'✅ نعم، سأحضر: {confirm_link}?response=yes\n'
            f'❌ لا أستطيع: {confirm_link}?response=no\n'
            f'⏰ سأحضر بعد: {confirm_link}?response=eta\n\n'
            f'{now.strftime("%Y-%m-%d %H:%M")}'
        )
        log = send_whatsapp(phone, message, notification_type='emergency_recall')
        results.append({'employee': name, 'phone': phone, 'status': log.status if log else 'failed'})
    return results


def check_and_send_absent_alerts():
    from models import Employee, AttendanceLog
    now = datetime.now(UTC)
    if now.hour < 9 or (now.hour == 9 and now.minute < 30):
        return 0
    today = now.date()
    employees = Employee.query.filter_by(is_active=True, deleted_at=None).all()
    sent = 0
    for emp in employees:
        if not emp.manager_id:
            continue
        clocked = AttendanceLog.query.filter_by(employee_id=emp.id, log_date=today).first()
        if clocked:
            continue
        manager = Employee.query.get(emp.manager_id)
        if manager and manager.phone:
            send_absent_alert(emp.full_name, manager.phone)
            sent += 1
    logger.info(f'Absent alerts sent: {sent}')
    return sent


def check_document_expiry_alerts():
    from models.documents import ArchivedDocument
    from models import Employee
    from datetime import date, timedelta
    today = date.today()
    for days in [30, 15, 7, 3, 1]:
        target = today + timedelta(days=days)
        docs = ArchivedDocument.query.filter(
            ArchivedDocument.expiry_date == target,
            ArchivedDocument.is_deleted == False,
        ).all()
        for doc in docs:
            employee = Employee.query.get(doc.employee_id)
            if not employee:
                continue
            doc.doc_type = doc.title
            hr_phone = 'admin'
            send_document_expiry_alert(doc.doc_type or 'مستند', employee.full_name, days, hr_phone)


def check_device_offline_alerts():
    from models.biotime_device import BioTimeDevice
    cutoff = datetime.now(UTC) - timedelta(minutes=10)
    offline_devices = BioTimeDevice.query.filter_by(is_active=True).filter(
        BioTimeDevice.last_online_at.is_(None) | (BioTimeDevice.last_online_at < cutoff)
    ).all()
    for dev in offline_devices:
        offline_since = dev.last_online_at.strftime('%H:%M') if dev.last_online_at else 'غير معروف'
        send_device_offline_alert(dev.name or dev.serial_number, offline_since, 'admin')


def get_message_log(page=1, per_page=50, notification_type=None, status=None):
    query = NotificationLog.query
    if notification_type:
        query = query.filter_by(notification_type=notification_type)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(NotificationLog.sent_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        'items': [item.to_dict() for item in items],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    }


def save_template(template_type, subject, body):
    tmpl = NotificationTemplate.query.filter_by(template_type=template_type).first()
    if not tmpl:
        tmpl = NotificationTemplate(template_type=template_type)
        db.session.add(tmpl)
    tmpl.subject = subject
    tmpl.body = body
    tmpl.updated_at = datetime.now(UTC)
    db.session.commit()
    return tmpl


def get_template(template_type):
    return NotificationTemplate.query.filter_by(template_type=template_type).first()


def update_whatsapp_config(data):
    cfg = load_config()
    if 'enabled' in data:
        cfg.enabled = bool(data['enabled'])
    if 'provider' in data:
        cfg.provider = data['provider']
    if 'instance_id' in data:
        cfg.instance_id = data['instance_id']
    if 'token' in data:
        cfg.token = data['token']
    if 'account_sid' in data:
        cfg.account_sid = data['account_sid']
    if 'auth_token' in data:
        cfg.auth_token = data['auth_token']
    if 'from_number' in data:
        cfg.from_number = data['from_number']
    if 'webhook_url' in data:
        cfg.webhook_url = data['webhook_url']
    if 'quiet_hours_enabled' in data:
        cfg.quiet_hours_enabled = bool(data['quiet_hours_enabled'])
    if 'notifications_enabled' in data:
        current = cfg.notifications_settings
        current.update(data['notifications_enabled'])
        cfg.notifications_enabled = json.dumps(current, ensure_ascii=False)
    db.session.commit()
    return cfg


def verify_webhook_signature(payload, signature, secret):
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
