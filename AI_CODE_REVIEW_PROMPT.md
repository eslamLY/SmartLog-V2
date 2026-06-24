# برومت مراجعة الكود وإضافة Endpoints الجديدة

## السياق
أنت مطور Python/Flask خبير. المشروع هو SMARTLOG — نظام إدارة الحضور والموارد البشرية الذكي (SMARTLOG - Attendance & HR Management System).

## الملف الرئيسي
- `app.py` (3028 سطر) - تطبيق Flask مع SQLAlchemy
- يستخدم SQLite/PostgreSQL
- يحتوي على 16 نماذج: Employee, Department, AttendanceLog, LeaveRequest, OutingRequest, LoginAttempt, ShiftType, ShiftSchedule, ShiftSwapRequest, GPSLog, BioTimeDevice, BrandingConfig, TrustedDevice, BiometricCredential, Notification, EmployeeDocument

## الـ endpoints الموجودة حالياً (70+ endpoint)

### الموظف (Employee)
- `/employee/clockin` (POST) - تسجيل الحضور مع GPS و selfie
- `/employee/clockout` (POST) - تسجيل الانصراف
- `/employee/geofence` (POST) - فحص موقع GPS
- `/employee/leaves` (GET) - عرض طلبات الإجازات
- `/employee/leaves/new` (POST) - إنشاء طلب إجازة
- `/employee/history` (GET) - عرض سجل الحضور الشهري
- `/employee/clock-in/qr` (POST) - تسجيل الحضور عبر QR
- `/employee/permission/outing` (POST) - طلب إذن خروج
- `/employee/shifts` (GET) - عرض المناوبات
- `/employee/shifts/swap/request` (POST) - طلب تبديل مناوبة
- `/employee/shifts/swaps/<id>/respond` (POST) - الرد على طلب التبديل
- `/api/shifts/employee/<id>/<month>/<year>` (GET) - مناوبات موظف
- `/employee/gps/log` (POST) - تسجيل GPS
- `/employee/biometrics/register` (POST) - تسجيل بايومتريك
- `/employee/biometrics/verify` (POST) - التحقق من بايومتريك

### المشرف (Admin)
- `/admin` (GET) - لوحة التحكم
- `/admin/employees` (GET) - إدارة الموظفين
- `/admin/employees/add` (POST) - إضافة موظف
- `/admin/employees/<id>/edit` (POST) - تعديل موظف
- `/admin/employees/<id>/reset-device` (POST) - إعادة تعيين الجهاز
- `/admin/employees/<id>/toggle` (POST) - تفعيل/تعطيل موظف
- `/admin/employees/<id>/grant-permission` (POST) - منح إذن خروج
- `/admin/employees/<id>/remote-wipe` (POST) - محو عن بُعد
- `/admin/departments` (GET) - إدارة الأقسام
- `/admin/departments/add` (POST) - إضافة قسم
- `/admin/departments/<id>/toggle` (POST) - تفعيل/تعطيل قسم
- `/admin/departments/<id>/delete` (POST) - حذف قسم
- `/admin/attendance` (GET) - إدارة الحضور
- `/admin/attendance/manual-clockin` (POST) - تسجيل حضور يدوي
- `/admin/leaves` (GET) - إدارة طلبات الإجازات
- `/admin/leaves/<id>/action` (POST) - اتخاذ إجراء على طلب إجازة
- `/admin/outings/<id>/action` (POST) - اتخاذ إجراء على طلب خروج
- `/admin/requests/review` (GET) - مراجعة الطلبات
- `/admin/reports` (GET) - التقارير
- `/admin/reports/excel` (GET) - تصدير Excel
- `/admin/reports/pdf` (GET) - تصدير PDF
- `/admin/reports/section` (GET) - تقرير القسم
- `/admin/reports/employee/<id>` (GET) - تقرير الموظف
- `/admin/payroll` (GET) - الرواتب
- `/admin/shifts` (GET) - إدارة المناوبات
- `/admin/shifts/types` (GET) - أنواع المناوبات
- `/admin/shifts/types/add` (POST) - إضافة نوع مناوبة
- `/admin/shifts/types/<id>/edit` (POST) - تعديل نوع مناوبة
- `/admin/shifts/types/<id>/toggle` (POST) - تفعيل/تعطيل نوع مناوبة
- `/admin/shifts/assign` (POST) - تعيين مناوبة
- `/admin/shifts/assign/bulk` (POST) - تعيين جماعي
- `/admin/shifts/copy-week` (POST) - نسخ أسبوع
- `/admin/shifts/auto-rotate` (POST) - تدوير تلقائي
- `/admin/shifts/<id>/cancel` (POST) - إلغاء مناوبة
- `/api/shifts/day/<date>` (GET) - مناوبات يوم معين
- `/admin/shifts/clear-day` (POST) - مسح يوم
- `/admin/shifts/swaps` (GET) - طلبات التبديل
- `/admin/shifts/swaps/<id>/action` (POST) - اتخاذ إجراء على طلب تبديل
- `/admin/shifts/export` (GET) - تصدير المناوبات
- `/admin/shifts/coverage` (GET) - تغطية المناوبات
- `/admin/analytics` (GET) - التحليلات
- `/admin/salary-slip/<id>` (GET) - كشف راتب
- `/admin/gps` (GET) - إدارة GPS
- `/admin/devices` (GET) - إدارة الأجهزة
- `/admin/devices/add` (POST) - إضافة جهاز
- `/admin/devices/<id>/toggle` (POST) - تفعيل/تعطيل جهاز
- `/admin/devices/<id>/sync` (POST) - مزامنة جهاز
- `/admin/live/stats` (GET) - إحصائيات مباشرة
- `/admin/live/events` (GET) - أحداث مباشرة (SSE)
- `/admin/devices/security` (GET) - أمان الأجهزة
- `/admin/biometrics` (GET) - البايومتريك
- `/admin/notifications` (GET) - الإشعارات
- `/admin/notifications/send` (POST) - إرسال إشعار
- `/api/notifications/history` (GET) - سجل الإشعارات
- `/api/notifications/read/<id>` (POST) - تعليم إشعار كمقروء
- `/api/notifications/unread-count` (GET) - عدد الإشعارات غير المقروءة
- `/admin/document-vault` (GET) - خزينة المستندات
- `/admin/documents` (GET) - المستندات
- `/admin/documents/upload` (POST) - رفع مستند
- `/admin/documents/<id>/verify` (POST) - التحقق من مستند
- `/admin/documents/<id>/delete` (POST) - حذف مستند
- `/admin/documents/download/<id>` (GET) - تحميل مستند
- `/admin/branding` (GET) - العلامة التجارية
- `/admin/branding/save` (POST) - حفظ العلامة التجارية
- `/admin/branding/logo` (POST) - رفع شعار

### عام
- `/api/qr-token` (GET) - توليد token للـ QR
- `/api/branding` (GET) - إعدادات العلامة التجارية
- `/api/admin/ai-predictor` (GET) - التنبؤ بالاحتياجات من الموظفين
- `/api/hardware/punch` (POST) - تسجيل من الأجهزة
- `/api/notifications` (GET) - الإشعارات

## المهمة

### الجزء الأول: مراجعة الكود الموجاد (النواقص الفعلية المكتشفة)

#### نواقص الأمان (20 مشكلة مكتشفة)
1. **لا يوجد CSRF protection** - لم أر أي استخدام لـ CSRF tokens في النماذج
2. **لا يوجد CORS configuration** - لم أر أي إعدادات CORS
3. **لا يوجد Content Security Policy (CSP)** - لم أر أي CSP headers
4. **لا يوجد HSTS headers** - لم أر أي HSTS
5. **لا يوجد X-Frame-Options** - لم أر أي حماية من clickjacking
6. **لا يوجد X-Content-Type-Options** - لم أر أي حماية من MIME sniffing
7. **لا يوجد Referrer-Policy** - لم أر أي سياسة referrer
8. **لا يوجد Permissions-Policy** - لم أر أي سياسة permissions
9. **لا يوجد input validation شامل** - بعض الـ endpoints تتحقق من البيانات لكن ليس بشكل منهجي
10. **لا يوجد output encoding** - البيانات تُعرض مباشرة في HTML (Jinja2 يقوم بذلك تلقائياً لكن يجب التأكد)
11. **لا يوجد rate limiting على جميع الـ endpoints** - بعضها محمي لكن ليس الكل
12. **لا يوجد logging للأحداث الأمنية** - لا يوجد سجل للأحداث الأمنية مثل محاولات الاختراق
13. **لا يوجد audit trail** - لا يوجد سجل لتتبع التغييرات
14. **لا يوجد password policy** - لا يوجد تحقق من قوة كلمة المرور
15. **لا يوجد two-factor authentication** - لا يوجد 2FA
16. **لا يوجد session fixation protection** - لا يوجد re-generation of session ID بعد login
17. **لا يوجد secure cookie flags** - لم أر أي إعدادات secure, httponly, samesite للكوكيز
18. **لا يوجد IP whitelist/blacklist** - لا يوجد قائمة IPs مسموحة أو محظورة
19. **لا يوجد request size limit شامل** - بعض الـ endpoints محمية لكن ليس الكل
20. **لا يوجد file upload validation كامل** - يتحقق من الامتداد لكن ليس من المحتوى الفعلي

#### نواقص الأداء (6 مشاكل مكتشفة)
1. **N+1 queries في عدة أماكن**:
   - `admin_shifts()`: لكل schedule يتم عمل Employee.query.get(ss.employee_id)
   - `api_day_shifts()`: لكل schedule يتم عمل Employee.query.get(ss.employee_id)
   - `admin_shift_swaps()`: لكل swap يتم جلب requester و target
   - `admin_analytics()`: لكل موظف يتم جلب logs
   - `admin_payroll()`: لكل موظف يتم جلب logs و shifts
   - `employee_shifts()`: لكل schedule يتم جلب shift_type

2. **لا توجد indexes على الأعمدة المستخدمة في البحث**:
   - لا يوجد index على AttendanceLog.log_date
   - لا يوجد index على AttendanceLog.employee_id
   - لا يوجد index على AttendanceLog.status
   - لا يوجد index على ShiftSchedule.scheduled_date
   - لا يوجد index على ShiftSchedule.employee_id
   - لا يوجد index على LeaveRequest.status
   - لا يوجد index على Notification.is_read
   - لا يوجد index على EmployeeDocument.expiry_date

3. **لا يوجد caching**:
   - لا يوجد cache للبيانات المتكررة مثل قائمة الموظفين
   - لا يوجد cache للإعدادات
   - لا يوجد cache للـ shift types

4. **لا يوجد pagination على القوائم الطويلة**:
   - `admin_employees()`: لا يوجد pagination
   - `admin_attendance()`: لا يوجد pagination
   - `admin_leaves()`: لا يوجد pagination
   - `admin_shifts()`: لا يوجد pagination

5. **لا يوجد lazy loading للصور**:
   - الصور في HTML لا تستخدم lazy loading

6. **لا يوجد database connection pooling مخصص**:
   - SQLAlchemy يستخدم connection pool افتراضياً لكن لم أر أي تخصيص

#### نواقص الكود (7 مشاكل مكتشفة)
1. **لا يوجد error handling شامل**:
   - بعض الـ endpoints لا تحتوي على try/except
   - الأخطاء لا تُسجل (logging)

2. **لا يوجد validation شامل**:
   - بعض البيانات لا تُتحقق من صحتها
   - لا يوجد schema validation

3. **لا يوجد logging**:
   - لا يوجد logging للأخطاء
   - لا يوجد logging للأحداث المهمة

4. **لا يوجد tests**:
   - لا يوجد unit tests
   - لا يوجد integration tests

5. **لا يوجد documentation**:
   - لا يوجد docstrings لمعظم الدوال
   - لا يوجد API documentation

6. **لا يوجد configuration management**:
   - بعض القيم hard-coded في الكود
   - لا يوجد environment variables لجميع الإعدادات

7. **لا يوجد database migrations منظم**:
   - التغييرات على قاعدة البيانات تتم يدوياً عبر ALTER TABLE في seed_enterprise()

### الجزء الثاني: الـ Endpoints المفقودة فعلياً (10 endpoints)

**ملاحظة هامة**: معظم الـ endpoints المقترحة في البرومت السابق موجودة بالفعل في المشروع! المشروع شامل جداً ويحتوي على 70+ endpoint. النواقص الحقيقية هي:

#### 1. إدارة النسخ الاحتياطي (Backup/Restore)
```
POST /api/admin/backup
- إنشاء نسخة احتياطية من قاعدة البيانات
- Response: {backup_id, created_at, file_path}

GET /api/admin/backups
- عرض جميع النسخ الاحتياطية
- Response: [{id, created_at, file_path, size}]

POST /api/admin/restore/<backup_id>
- استعادة قاعدة البيانات من نسخة احتياطية
- Validation: backup exists, admin only
```

#### 2. سجل التدقيق (Audit Logs)
```
GET /api/admin/audit-logs
- عرض سجل التدقيق
- Query params: user_id, action, start_date, end_date
- Response: [{id, user_id, action, entity_type, entity_id, changes, timestamp}]

POST /api/admin/audit-logs
- إنشاء سجل تدقيق (يُستخدم داخلياً)
- Body: {user_id, action, entity_type, entity_id, changes}
```

#### 3. تفضيلات المستخدم (User Preferences)
```
GET /api/user/preferences
- عرض تفضيلات المستخدم الحالي
- Response: {theme, language, notifications_enabled, email_notifications}

PUT /api/user/preferences
- تحديث تفضيلات المستخدم
- Body: {theme, language, notifications_enabled, email_notifications}
```

#### 4. تكامل التقويم (Calendar Integration)
```
GET /api/employee/calendar/ical
- تصدير مناوبات الموظف بصيغة iCal
- Response: text/calendar

GET /api/department/calendar/ical/<department_id>
- تصدير مناوبات القسم بصيغة iCal
- Response: text/calendar
```

#### 5. إشعارات البريد الإلكتروني (Email Notifications)
```
POST /api/admin/email/send
- إرسال إشعار بريد إلكتروني
- Body: {to, subject, body, type}
- Validation: email format, admin only

GET /api/admin/email/templates
- عرض قوالب البريد الإلكتروني
- Response: [{id, name, subject, body}]

POST /api/admin/email/templates
- إنشاء قالب بريد إلكتروني جديد
- Body: {name, subject, body}
```

#### 6. إشعارات SMS (SMS Notifications)
```
POST /api/admin/sms/send
- إرسال إشعار SMS
- Body: {to, message}
- Validation: phone number format, admin only

GET /api/admin/sms/history
- عرض سجل إشعارات SMS
- Response: [{id, to, message, status, sent_at}]
```

#### 7. إشعارات Push (Push Notifications)
```
POST /api/employee/push/register
- تسجيل جهاز للإشعارات Push
- Body: {device_token, platform}
- Validation: device token format

POST /api/admin/push/broadcast
- إرسال إشعار push لجميع الموظفين
- Body: {title, message, data}
- Validation: admin only
```

#### 8. إحصائيات متقدمة (Advanced Analytics)
```
GET /api/admin/analytics/export
- تصدير بيانات التحليلات بصيغة JSON
- Query params: start_date, end_date, metrics
- Response: {metrics, data, generated_at}

GET /api/admin/analytics/trends
- عرض اتجاهات الحضور على مدى سنة
- Response: {monthly_trends, quarterly_trends, yearly_summary}
```

#### 9. إدارة الأذونات (Permission Management)
```
GET /api/admin/permissions
- عرض جميع الأذونات
- Response: [{id, name, description}]

POST /api/admin/roles
- إنشاء دور جديد
- Body: {name, permissions[]}
- Validation: permissions exist

PUT /api/admin/employees/<id>/permissions
- تحديث أذونات موظف
- Body: {permissions[]}
- Validation: permissions exist
```

#### 10. صحة النظام (System Health)
```
GET /api/health
- فحص صحة النظام
- Response: {status, database, redis, disk, memory}

GET /api/admin/metrics
- عرض مقاييس النظام
- Response: {requests_per_minute, avg_response_time, error_rate, active_users}
```

## المتطلبات

### الأمان (بناءً على النواقص المكتشفة)
1. **إضافة CSRF protection**:
   - استخدم Flask-WTF أو CSRFProtect من flask_wtf.csrf
   - أضف CSRF tokens لجميع النماذج POST
   - استخدم `@csrf.exempt` للـ API endpoints الخارجية

2. **إضافة security headers**:
   ```python
   @app.after_request
   def add_security_headers(response):
       response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
       response.headers['X-Frame-Options'] = 'DENY'
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
       response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
       return response
   ```

3. **إضافة secure cookie flags**:
   ```python
   app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
   app.config['SESSION_COOKIE_HTTPONLY'] = True
   app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
   ```

4. **إضافة session fixation protection**:
   ```python
   session.regenerate()  # بعد login ناجح
   ```

5. **إضافة password policy**:
   - تحقق من طول كلمة المرور (8+ أحرف)
   - تحقق من وجود أحرف كبيرة وصغيرة وأرقام ورموز
   - منع كلمات المرور الشائعة

6. **إضافة comprehensive logging**:
   - استخدم logging module
   - سجل جميع محاولات login الفاشلة
   - سجل جميع التغييرات المهمة
   - سجل الأخطاء مع stack trace

7. **إضافة audit trail**:
   - أنشئ model جديد AuditLog
   - سجل جميع التغييرات على البيانات المهمة
   - سجل من قام بالتغيير ومتى وماذا تغير

### الأداء (بناءً على النواقص المكتشفة)
1. **إصلاح N+1 queries**:
   - استخدم `joinedload` و `selectinload` من SQLAlchemy
   - مثال:
     ```python
     from sqlalchemy.orm import joinedload
     schedules = ShiftSchedule.query.options(
         joinedload(ShiftSchedule.employee),
         joinedload(ShiftSchedule.shift_type)
     ).all()
     ```

2. **إضافة database indexes**:
   ```python
   # في models
   class AttendanceLog(db.Model):
       __table_args__ = (
           db.Index('idx_attendance_log_date', 'log_date'),
           db.Index('idx_attendance_employee', 'employee_id'),
           db.Index('idx_attendance_status', 'status'),
       )
   ```

3. **إضافة caching**:
   - استخدم Flask-Caching أو Redis
   - cache البيانات المتكررة مثل قائمة الموظفين
   - cache الإعدادات لمدة معينة

4. **إضافة pagination**:
   - استخدم `paginate()` من SQLAlchemy
   - مثال:
     ```python
     page = request.args.get('page', 1, type=int)
     per_page = 20
     employees = Employee.query.paginate(page=page, per_page=per_page)
     ```

### معالجة الأخطاء
1. **إضافة global error handler**:
   ```python
   @app.errorhandler(404)
   def not_found(error):
       return jsonify({'ok': False, 'msg': 'غير موجود'}), 404

   @app.errorhandler(500)
   def internal_error(error):
       db.session.rollback()
       logging.error(f"Server error: {error}")
       return jsonify({'ok': False, 'msg': 'خطأ في الخادم'}), 500
   ```

2. **إضافة try/except لجميع الـ endpoints**:
   - التفاف جميع العمليات الحساسة بـ try/except
   - rollback للـ session في حالة الخطأ
   - تسجيل الأخطاء

### التوثيق (Documentation)
1. **إضافة docstrings**:
   ```python
   @app.route('/employee/clockin', methods=['POST'])
   @employee_required
   def clock_in():
       """
       تسجيل الحضور للموظف

       Request Body:
           lat (float): خط العرض
           lng (float): خط الطول
           selfie (str): صورة Selfie base64

       Returns:
           JSON: {ok: bool, msg: str, status: str, late_min: int, inside: bool, dist: int}
       """
   ```

2. **إضافة API documentation**:
   - استخدم Flask-RESTX أو Swagger
   - أو أنشئ ملف API.md منفصل

### الاختبار (Testing)
1. **إضافة unit tests**:
   - استخدم pytest
   - اختبر كل endpoint بشكل منفصل
   - اختبر الـ validation

2. **إضافة integration tests**:
   - اختبر الـ workflows الكاملة
   - اختبر التفاعل بين endpoints

### Configuration Management
1. **نقل hard-coded values إلى environment variables**:
   ```python
   WORK_START_HOUR = int(os.environ.get('WORK_START_HOUR', '8'))
   LATE_GRACE_MINUTES = int(os.environ.get('LATE_GRACE_MINUTES', '15'))
   GEOFENCE_RADIUS_M = int(os.environ.get('GEOFENCE_RADIUS_M', '200'))
   ```

2. **إنشاء config.py منفصل**:
   ```python
   class Config:
       SECRET_KEY = os.environ.get('SECRET_KEY')
       DATABASE_URL = os.environ.get('DATABASE_URL')
       # ... إعدادات أخرى
   ```

### Database Migrations
1. **استخدم Alembic**:
   - تثبيت Alembic
   - إنشاء migrations منفصلة
   - إدارة التغييرات على قاعدة البيانات بشكل منظم

## التنسيق
- استخدم Arabic للرسائل التي تظهر للمستخدم
- استخدم English للـ variable names و function names
- اتبع PEP 8 style guide
- استخدم type hints حيثما أمكن

## التسليم
1. قائمة بجميع المشاكل الموجودة في الكود الحالي (مرتبة حسب الأولوية) - **تم توفيرها أعلاه**
2. الكود المعدل لـ app.py مع الإصلاحات
3. الكود الجديد للـ endpoints المطلوبة (10 endpoints)
4. أي migrations مطلوبة لقاعدة البيانات (للـ indexes والـ models الجديدة)

---

## ملخص النواقص المكتشفة

### إجمالي النواقص: 33 مشكلة
- **الأمان**: 20 مشكلة
- **الأداء**: 6 مشاكل
- **الكود**: 7 مشاكل

### إجمالي الـ Endpoints المفقودة: 10 endpoints
- إدارة النسخ الاحتياطي: 3 endpoints
- سجل التدقيق: 2 endpoints
- تفضيلات المستخدم: 2 endpoints
- تكامل التقويم: 2 endpoints
- إشعارات البريد الإلكتروني: 3 endpoints
- إشعارات SMS: 2 endpoints
- إشعارات Push: 2 endpoints
- إحصائيات متقدمة: 2 endpoints
- إدارة الأذونات: 3 endpoints
- صحة النظام: 2 endpoints

**ملاحظة**: المشروع يحتوي على 70+ endpoint حالياً، وهو شامل جداً. النواقص المذكورة هي تحسينات إضافية وليست نقصاً أساسياً في الوظائف.
4. أي migrations مطلوبة لقاعدة البيانات
