-- ============================================================================
-- SmartLog V2 — Database Security Configuration Script
-- ============================================================================
-- Run: psql -U postgres -d smartlog_db -f database_security_config.sql
-- Target: PostgreSQL 15+ on Render
-- ============================================================================

-- ═══════════════════════════════════════════════════════════════════════════
-- 1. CREATE LIMITED DATABASE USER
-- ═══════════════════════════════════════════════════════════════════════════

-- Generate a strong random password:
--   openssl rand -base64 24
-- Then update Render env var DATABASE_URL with the new credentials.

-- Step 1: Create app user (DO NOT use postgres superuser)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'smartlog_app') THEN
    CREATE ROLE smartlog_app WITH LOGIN PASSWORD 'CHANGE_ME_TO_A_STRONG_PASSWORD' 
      CONNECTION LIMIT 25;
  END IF;
END
$$;

-- Step 2: Revoke superuser/createdb/createrole if they somehow have them
ALTER ROLE smartlog_app WITH NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- Step 3: Grant minimal privileges on the database
GRANT CONNECT ON DATABASE smartlog_db TO smartlog_app;

-- Step 4: Grant schema usage
GRANT USAGE ON SCHEMA public TO smartlog_app;

-- Step 5: Grant table privileges (read/write on data, no DDL)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartlog_app;

-- Step 6: Grant sequence usage (for auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smartlog_app;

-- Step 7: Set default privileges for future tables/sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smartlog_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO smartlog_app;

-- ═══════════════════════════════════════════════════════════════════════════
-- 2. ENABLE COLUMN-LEVEL ENCRYPTION SUPPORT
-- ═══════════════════════════════════════════════════════════════════════════

-- The app uses Fernet (AES-128) for field-level encryption.
-- The encryption key is managed by Flask, NOT PostgreSQL.
-- 
-- To verify encryption is working, check that encrypted columns exist:
SELECT 
  table_name, 
  column_name, 
  data_type 
FROM information_schema.columns 
WHERE column_name LIKE '%encrypted%'
  AND table_schema = 'public';

-- If you want PostgreSQL-level encryption (pgcrypto extension):
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Note: The app already handles field encryption. pgcrypto is optional
-- for additional DB-level functions.

-- ═══════════════════════════════════════════════════════════════════════════
-- 3. ENABLE AUDIT LOGGING
-- ═══════════════════════════════════════════════════════════════════════════

-- The application uses an AuditLog model (logical audit).
-- For PostgreSQL-level audit (trigger-based):

-- Step 1: Create audit schema
CREATE SCHEMA IF NOT EXISTS audit;

-- Step 2: Create audit log table
CREATE TABLE IF NOT EXISTS audit.audit_log (
    id              BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    operation       TEXT NOT NULL,  -- INSERT, UPDATE, DELETE, TRUNCATE
    old_data        JSONB,
    new_data        JSONB,
    changed_by      TEXT DEFAULT current_user,
    changed_at      TIMESTAMPTZ DEFAULT now(),
    query           TEXT,
    client_addr     INET,
    app_name        TEXT
);

-- Step 3: Create audit trigger function
CREATE OR REPLACE FUNCTION audit.trigger_audit()
RETURNS TRIGGER AS $$
DECLARE
    old_row JSONB;
    new_row JSONB;
BEGIN
    -- Build old/new row data (exclude large binary fields)
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT to_jsonb(OLD) INTO old_row;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT to_jsonb(NEW) INTO new_row;
    END IF;

    INSERT INTO audit.audit_log (
        table_name, operation, old_data, new_data, client_addr, app_name
    ) VALUES (
        TG_TABLE_NAME, TG_OP,
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE old_row END,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE new_row END,
        inet_client_addr(),
        current_setting('application_name', TRUE)
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 4: Create audit triggers on sensitive tables
-- IMPORTANT: Run these ONE AT A TIME on a staging DB first to test performance

-- Employees table (highest sensitivity)
-- DROP TRIGGER IF EXISTS audit_employees ON employees;
-- CREATE TRIGGER audit_employees
--   AFTER INSERT OR UPDATE OR DELETE ON employees
--   FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- Attendance logs
-- CREATE TRIGGER audit_attendance_logs
--   AFTER INSERT OR UPDATE OR DELETE ON attendance_logs
--   FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- Leave requests
-- CREATE TRIGGER audit_leave_requests
--   AFTER INSERT OR UPDATE OR DELETE ON leave_requests
--   FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- Payroll
-- CREATE TRIGGER audit_payroll
--   AFTER INSERT OR UPDATE OR DELETE ON payroll
--   FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- GPS logs
-- CREATE TRIGGER audit_gps_logs
--   AFTER INSERT OR UPDATE OR DELETE ON gps_logs
--   FOR EACH ROW EXECUTE FUNCTION audit.trigger_audit();

-- ═══════════════════════════════════════════════════════════════════════════
-- 4. ROW-LEVEL SECURITY (RLS)
-- ═══════════════════════════════════════════════════════════════════════════

-- Enable Row-Level Security on sensitive tables
-- This prevents users from seeing other users' data even with direct DB access

ALTER TABLE IF EXISTS employees ENABLE ROW LEVEL SECURITY;

-- Create policies for data isolation
-- Note: RLS policies require careful design. These are EXAMPLES.

-- POLICY: Employees can only see their own row
-- DROP POLICY IF EXISTS employee_data_isolation ON employees;
-- CREATE POLICY employee_data_isolation ON employees
--   FOR ALL
--   USING (current_setting('app.employee_id') = id::text);

-- ═══════════════════════════════════════════════════════════════════════════
-- 5. CONNECTION SECURITY
-- ═══════════════════════════════════════════════════════════════════════════

-- Require SSL for all connections (Render enforces this by default)
-- Verify SSL is enabled:
SHOW ssl;

-- Set statement timeout (prevents runaway queries)
ALTER ROLE smartlog_app SET statement_timeout = '30s';

-- Set idle session timeout
ALTER ROLE smartlog_app SET idle_in_transaction_session_timeout = '5min';

-- ═══════════════════════════════════════════════════════════════════════════
-- 6. BACKUP SECURITY
-- ═══════════════════════════════════════════════════════════════════════════

-- The application creates encrypted backups via backup_service.py.
-- For PostgreSQL-level backups:

-- Verify WAL archiving (if enabled on your PostgreSQL plan):
SHOW archive_mode;
SHOW archive_command;

-- For encrypted pg_dump:
--   PGPASSWORD="password" pg_dump --no-owner --encrypt-aes-256 \
--     -h host -U user -d dbname > backup_enc.sql.gpg

-- ═══════════════════════════════════════════════════════════════════════════
-- 7. VERIFICATION QUERIES
-- ═══════════════════════════════════════════════════════════════════════════

-- List all roles and their privileges
SELECT r.rolname, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
       r.rolconnlimit, r.rolreplication
FROM pg_roles r
WHERE r.rolname NOT LIKE 'pg_%'
ORDER BY r.rolsuper DESC, r.rolname;

-- List user table privileges
SELECT grantee, table_schema, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'smartlog_app'
ORDER BY table_name, privilege_type;

-- Check for unencrypted sensitive columns
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('password_hash', 'bank_account_number', 
                       'national_id', 'emergency_phone', 'phone')
  AND table_schema = 'public';

-- ═══════════════════════════════════════════════════════════════════════════
-- END OF CONFIGURATION
-- ═══════════════════════════════════════════════════════════════════════════
