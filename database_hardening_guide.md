# Database Hardening Guide — SmartLog V2

**Date:** 2026-06-24  
**Target:** Render PostgreSQL 15+  
**Guide:** Step-by-step security hardening

---

## Prerequisites

```bash
# Install PostgreSQL client
# Windows: https://www.postgresql.org/download/windows/
# macOS: brew install postgresql
# Linux: sudo apt install postgresql-client

# Get database URL from Render Dashboard:
#   Render Dashboard → smartlog-db → Info → Connection String
#   Or: Render Dashboard → smartlog-backend → Environment → DATABASE_URL
```

---

## Step 1: Create Limited Database User

### 1.1 Extract connection details from DATABASE_URL

```
DATABASE_URL=postgresql://user:password@host:port/dbname
               ↑         ↑         ↑     ↑     ↑
               |         password  host  port  database
               username
```

### 1.2 Connect as superuser

```bash
psql "postgresql://user:password@host:port/dbname?sslmode=require"
```

### 1.3 Create app user

```sql
CREATE ROLE smartlog_app WITH LOGIN PASSWORD 'generate-a-strong-password-here'
  CONNECTION LIMIT 25;
ALTER ROLE smartlog_app WITH NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE dbname TO smartlog_app;
GRANT USAGE ON SCHEMA public TO smartlog_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartlog_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smartlog_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smartlog_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO smartlog_app;
```

### 1.4 Update Render env var

```bash
# New DATABASE_URL format:
DATABASE_URL=postgresql://smartlog_app:STRONG_PASSWORD@host:port/dbname?sslmode=require
```

**⚠️ IMPORTANT**: After updating `DATABASE_URL` in Render:
1. The app will restart automatically
2. Flask-Migrate may fail on first deploy (limited user can't run DDL)
3. **Workaround**: Keep superuser URL for migrations, app user for runtime

---

## Step 2: Set FIELD_ENCRYPTION_KEY

### 2.1 Generate a Fernet key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2.2 Add to Render environment

```bash
# Render Dashboard → smartlog-backend → Environment → Add
# Key: FIELD_ENCRYPTION_KEY
# Value: (paste the generated key)
```

### 2.3 Set BACKUP_ENCRYPTION_KEY

```bash
# Generate another key (can reuse, but separate is better)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add as:
# Key: BACKUP_ENCRYPTION_KEY
# Value: (paste key)
```

**⚠️ WARNING**: Setting `FIELD_ENCRYPTION_KEY` when encrypted data already exists will BREAK existing encrypted data. The app currently derives the key from `SECRET_KEY`. To change:
1. If no encrypted data exists → safe to set at any time
2. If encrypted data exists → must re-encrypt all data with the new key

---

## Step 3: Set Statement Timeout

Prevent runaway queries:

```bash
psql "postgresql://user:password@host:port/dbname?sslmode=require"
```

```sql
ALTER ROLE smartlog_app SET statement_timeout = '30s';
ALTER ROLE smartlog_app SET idle_in_transaction_session_timeout = '5min';
```

---

## Step 4: Enable SSL (Verify)

Render PostgreSQL requires SSL by default. Verify:

```bash
psql "postgresql://user:password@host:port/dbname?sslmode=require"
```

```sql
SHOW ssl;
-- Expected: on
```

The app sets `sslmode: require` in production (`config.py:90`).

---

## Step 5: Verify Field Encryption

### 5.1 Check which columns are encrypted

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name LIKE '%encrypted%'
  AND table_schema = 'public';
```

Expected encrypted columns:
- `employees.base_salary_encrypted`
- `employees.email_encrypted`
- `employees.phone_encrypted`

### 5.2 Add encryption for National ID (if needed)

```python
# In models/employee.py:
# Add column:
national_id_encrypted = db.Column(db.Text, nullable=True)

# Add property:
@property
def secure_national_id(self):
    raw = self.national_id_encrypted
    if not raw: return self.national_id or ''
    try: return get_fernet().decrypt(raw.encode()).decode()
    except Exception: return self.national_id or ''

@secure_national_id.setter
def secure_national_id(self, value):
    if value is None or value == '':
        self.national_id_encrypted = None; self.national_id = value
    else:
        self.national_id_encrypted = get_fernet().encrypt(str(value).encode()).decode()
        self.national_id = value
```

### 5.3 Create migration and migrate data

```bash
flask db migrate -m "add national_id encryption"
flask db upgrade

# Then run a one-time script to encrypt existing data:
python -c "
from app import app, db
from models import Employee
with app.app_context():
    for emp in Employee.query.all():
        if emp.national_id and not emp.national_id_encrypted:
            emp.secure_national_id = emp.national_id
    db.session.commit()
    print('Migration complete')
"
```

---

## Step 6: Enable Database Audit Logging (Optional)

### 6.1 Create audit schema

```bash
psql "postgresql://user:password@host:port/dbname?sslmode=require"
```

```sql
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.audit_log (
    id              BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    operation       TEXT NOT NULL,
    old_data        JSONB,
    new_data        JSONB,
    changed_by      TEXT DEFAULT current_user,
    changed_at      TIMESTAMPTZ DEFAULT now(),
    client_addr     INET,
    app_name        TEXT
);
```

### 6.2 Create audit trigger function

```sql
CREATE OR REPLACE FUNCTION audit.trigger_audit()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit.audit_log
        (table_name, operation, old_data, new_data, client_addr, app_name)
    VALUES (
        TG_TABLE_NAME, TG_OP,
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END,
        inet_client_addr(),
        current_setting('application_name', TRUE)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 6.3 Add triggers on sensitive tables

```sql
-- Employees (highest sensitivity)
CREATE TRIGGER audit_employees
  AFTER INSERT OR UPDATE OR DELETE ON employees
  FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- Payroll
CREATE TRIGGER audit_payroll
  AFTER INSERT OR UPDATE OR DELETE ON payroll
  FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- GPS Logs
CREATE TRIGGER audit_gps_logs
  AFTER INSERT OR UPDATE OR DELETE ON gps_logs
  FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();
```

### 6.4 Monitor audit log size

```sql
-- Check audit table size
SELECT pg_size_pretty(pg_total_relation_size('audit.audit_log'));

-- Set up retention (delete records older than 90 days)
-- CREATE OR REPLACE FUNCTION audit.purge_old_logs()
-- RETURNS void AS $$
--   DELETE FROM audit.audit_log WHERE changed_at < now() - INTERVAL '90 days';
-- $$ LANGUAGE sql;
```

---

## Step 7: Encrypt Backups

### 7.1 Verify backup encryption

```python
# The app already encrypts backups. Test:
# python
from services.backup_service import create_full_backup, extract_backup_content
from services.encryption_service import encrypt_data, decrypt_data

backup = create_full_backup(encrypt=True)
print(f"Backup created: {backup['filename']}")
print(f"Encrypted: {backup['encrypted'] if 'encrypted' in backup else 'yes'}")
```

### 7.2 Set up automated backups (using APScheduler)

Add to `app.py` or create a separate scheduler:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from services.backup_service import create_full_backup, clean_old_backups

scheduler = BackgroundScheduler()

# Daily full backup at 2 AM
@scheduler.scheduled_job('cron', hour=2, minute=0)
def scheduled_backup():
    with app.app_context():
        result = create_full_backup(encrypt=True)
        if result.get('ok'):
            app.logger.info(f'Auto-backup: {result["filename"]}')
        clean_old_backups(max_count=30, max_age_days=90)
```

---

## Step 8: Set Up Off-Site Backup Replication (Optional)

### Option A: pg_dump to cloud storage

```bash
# Create encrypted dump
PGPASSWORD="password" pg_dump \
  --host=host \
  --port=5432 \
  --username=user \
  --dbname=dbname \
  --no-owner \
  --format=custom \
  | gpg --symmetric --cipher-algo AES256 --passphrase-file key.txt \
  > /backups/smartlog_$(date +%Y%m%d).dump.gpg

# Upload to cloud storage (example: rclone to Google Drive)
rclone copy /backups/ remote:smartlog-backups/
```

### Option B: Render automated backups

Render Pro plan includes automated daily backups with point-in-time recovery.

---

## Step 9: Verify Hardening

### 9.1 Run the checker

```bash
python database_security_checker.py
```

### 9.2 Verify user privileges

```sql
-- Should show smartlog_app with no superuser
SELECT r.rolname, r.rolsuper, r.rolcreatedb, r.rolcreaterole
FROM pg_roles r WHERE r.rolname = 'smartlog_app';

-- Should show only DML privileges
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'smartlog_app'
ORDER BY table_name;
```

### 9.3 Test application

```bash
# Restart the app after changing DATABASE_URL
# Visit the app and verify: login, employee list, attendance, backups
```

---

## Quick Reference Checklist

- [ ] Limited `smartlog_app` user created (not superuser)
- [ ] `DATABASE_URL` updated with new credentials
- [ ] `ssl_mode=require` in connection string
- [ ] `FIELD_ENCRYPTION_KEY` set in Render env
- [ ] `BACKUP_ENCRYPTION_KEY` set in Render env
- [ ] Statement timeout configured (30s)
- [ ] National ID encrypted
- [ ] Bank account numbers encrypted
- [ ] Database audit triggers on sensitive tables
- [ ] Automated backup schedule active
- [ ] Backup encryption verified
- [ ] Off-site backup configured (optional)
- [ ] `database_security_config.sql` executed
- [ ] `database_security_checker.py` passes

---

## Troubleshooting

### "FATAL: password authentication failed"
→ Double-check the password in the new DATABASE_URL
→ Verify the user was created: `\du smartlog_app`

### "permission denied for schema public"
→ Run: `GRANT USAGE ON SCHEMA public TO smartlog_app;`

### "permission denied for table employees"
→ Run: `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartlog_app;`

### Encrypted data corrupted after FIELD_ENCRYPTION_KEY change
→ Restore from backup with old key
→ Decrypt all data with old key
→ Re-encrypt with new key
→ See `services/encryption_service.py:reencrypt_all_backups()`

### Flask-Migrate fails with limited user
→ Keep superuser URL for `flask db upgrade` commands
→ Switch to limited user URL for runtime
→ Use a pre/post-deploy script on Render
