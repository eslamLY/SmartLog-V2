import os
from datetime import datetime, UTC
from models import db, Employee, EmailLog, SmsLog


class NotificationService:

    @staticmethod
    def send_email(to: str, subject: str, body: str) -> dict:
        import smtplib, ssl
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = os.environ.get('SMTP_HOST', '')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_pass = os.environ.get('SMTP_PASSWORD', '')

        recipients = [to] if to else [
            emp.email for emp in Employee.query.filter(
                Employee.email.isnot(None), Employee.email != ''
            ).all()
        ]

        sent_count = 0
        for email_addr in recipients:
            log = EmailLog(to_email=email_addr, subject=subject, body=body,
                           status='pending', sent_at=datetime.now(UTC))
            db.session.add(log)
            db.session.flush()

            if smtp_host and smtp_user:
                try:
                    msg = MIMEMultipart('alternative')
                    msg['From'] = smtp_user
                    msg['To'] = email_addr
                    msg['Subject'] = subject
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    msg.attach(MIMEText(body.replace('\n', '<br>\n'), 'html', 'utf-8'))

                    context = ssl.create_default_context()
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                    server.starttls(context=context)
                    if smtp_user:
                        server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, email_addr, msg.as_string())
                    server.quit()

                    log.status = 'sent'
                    sent_count += 1
                except Exception as exc:
                    log.status = 'failed'
                    log.body = f'{body}\n\n--- SMTP ERROR ---\n{exc}'
            else:
                log.status = 'sent'
                sent_count += 1

        db.session.commit()
        return {'sent_count': sent_count}

    @staticmethod
    def send_sms(to: str, message: str) -> dict:
        if to:
            db.session.add(SmsLog(to_phone=to, message=message, status='sent'))
        else:
            for emp in Employee.query.filter(
                Employee.phone.isnot(None), Employee.phone != ''
            ).all():
                db.session.add(SmsLog(to_phone=emp.phone, message=message, status='sent'))
        db.session.commit()
        return {'sent_count': 1 if to else 0}
