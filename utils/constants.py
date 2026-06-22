import math

BLOOD_BANK_LAT       = 32.0755
BLOOD_BANK_LNG       = 23.9752
GEOFENCE_RADIUS_M    = 200
WORK_START_HOUR      = 8
WORK_START_MINUTE    = 0
LATE_GRACE_MINUTES   = 15
MAX_LOGIN_ATTEMPTS   = 5
SESSION_TIMEOUT_SECS = 900

MONTH_NAMES = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
               'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
DAY_NAMES   = ['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت']

DEPARTMENTS = ['مختبر التحليل','بنك الدم','التمريض','الاستقبال',
               'الإدارة','المستودع','الصيدلية']

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xlsx', 'xls'}
