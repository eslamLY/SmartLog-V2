# Render Deployment Instructions — SmartLog V2

## الطريقة 1: Blueprint (الأسهل) — ينشئ كل شيء تلقائياً

1. اذهب إلى https://dashboard.render.com
2. سجل الدخول بحساب GitHub الخاص بك
3. اضغط **New +** ← **Blueprint**
4. اختر repository: `eslamLY/SmartLog-V2`
5. Render سيقرأ ملف `render.yaml` وينشئ تلقائياً:
   - **PostgreSQL Database** (smartlog-db, starter plan, $7/month)
   - **Web Service** (smartlog-backend, starter plan, $7/month)
6. اضغط **Apply** — انتظر 5-10 دقائق حتى يكتمل الإنشاء

## الطريقة 2: يدوي (إذا لم يعمل Blueprint)

### أولاً: إنشاء قاعدة البيانات
1. Dashboard → **New +** → **PostgreSQL**
2. Name: `smartlog-db`
3. Database: `smartlog`
4. Plan: Starter ($7/mo)
5. Region: Oregon
6. اضغط **Create Database**

### ثانياً: إنشاء Web Service
1. Dashboard → **New +** → **Web Service**
2. Connect GitHub repository → اختر `eslamLY/SmartLog-V2`
3. الإعدادات:
   - **Name**: `smartlog-backend`
   - **Runtime**: `Docker`
   - **Branch**: `main`
   - **Plan**: Starter ($7/mo)
   - **Region**: Oregon
4. اضغط **Advanced** ← **Add Environment Variables** ← أضف:

| Key | Value |
|-----|-------|
| `FLASK_ENV` | `production` |
| `PRODUCTION` | `true` |
| `FLASK_APP` | `app.py` |
| `LOG_LEVEL` | `info` |

5. **SECRET_KEY**: اضغط "Generate" (أو أدخل قيمة عشوائية)
6. **DATABASE_URL**: اربطها بقاعدة البيانات من القائمة
7. **Health Check Path**: `/api/health`
8. اضغط **Create Web Service**

## بعد النشر

1. انتظر حتى يظهر "Live" في أعلى الصفحة
2. اختبر: افتح `https://smartlog-backend.onrender.com/api/health`
3. المتوقع: `{"status":"ok","database":"connected"}`

## إعدادات إضافية (مستحبة)

أضف في Dashboard → Environment:

| Key | Value | ملاحظة |
|-----|-------|--------|
| `FIELD_ENCRYPTION_KEY` | *(توليد مفتاح Fernet)* | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BACKUP_ENCRYPTION_KEY` | *(توليد مفتاح Fernet)* | نفس الطريقة |
| `DB_POOL_SIZE` | `10` | |
| `DB_POOL_OVERFLOW` | `20` | |
| `DB_POOL_RECYCLE` | `3600` | |
| `GUNICORN_WORKERS` | `2` | |
| `GUNICORN_THREADS` | `4` | |

## استكشاف الأخطاء

- **الـ container لا يبدأ**: تأكد من أن `.dockerignore` لا يستثني `entrypoint.sh` أو `requirements.txt` أو `app.py`
- **خطأ في قاعدة البيانات**: تأكد من ربط DATABASE_URL بقاعدة البيانات
- **الصفحات لا تظهر**: تأكد من أن `/static/` موجود على GitHub (`git ls-files static/`)
- **الـ logs**: Render Dashboard → Service → Logs

## رابط التطبيق بعد النشر

https://smartlog-backend.onrender.com
