-- =============================================================================
-- SmartLog V2 — Performance Indexes
-- =============================================================================
-- Run: psql "$DATABASE_URL" -f migrations/add_performance_indexes.sql

-- AttendanceLog — most heavily queried table
CREATE INDEX IF NOT EXISTS idx_attendance_logs_emp_date
    ON attendance_logs (employee_id, log_date DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_logs_date_status
    ON attendance_logs (log_date, status);
CREATE INDEX IF NOT EXISTS idx_attendance_logs_emp_date_status
    ON attendance_logs (employee_id, log_date DESC, status);
CREATE INDEX IF NOT EXISTS idx_attendance_logs_clock_in
    ON attendance_logs (clock_in) WHERE clock_in IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_attendance_logs_emp_clock_in
    ON attendance_logs (employee_id, clock_in) WHERE clock_in IS NOT NULL;

-- Employees — filtered by role, department, is_active constantly
CREATE INDEX IF NOT EXISTS idx_employees_role_dept_active
    ON employees (role, department_id, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_employees_department_active
    ON employees (department, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_employees_username
    ON employees (username);

-- GPS Logs — time-series queries
CREATE INDEX IF NOT EXISTS idx_gps_logs_employee_time
    ON gps_logs (employee_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gps_logs_created_at
    ON gps_logs (created_at DESC);

-- Leave Requests
CREATE INDEX IF NOT EXISTS idx_leave_requests_emp_status
    ON leave_requests (employee_id, status);
CREATE INDEX IF NOT EXISTS idx_leave_requests_date_range
    ON leave_requests (start_date, end_date) WHERE status = 'approved';

-- Shift Schedules
CREATE INDEX IF NOT EXISTS idx_shift_schedules_emp_date
    ON shift_schedules (employee_id, scheduled_date DESC);
CREATE INDEX IF NOT EXISTS idx_shift_schedules_date_status
    ON shift_schedules (scheduled_date, status);

-- Notifications
CREATE INDEX IF NOT EXISTS idx_notifications_emp_read
    ON notifications (employee_id, is_read, created_at DESC);

-- Geofence Events
CREATE INDEX IF NOT EXISTS idx_geofence_events_emp_zone
    ON geofence_events (employee_id, zone_id, created_at DESC);

-- Payroll Records
CREATE INDEX IF NOT EXISTS idx_payroll_records_emp_month
    ON payroll_records (employee_id, year, month);

-- Biometric Devices
CREATE INDEX IF NOT EXISTS idx_biometric_devices_company
    ON biometric_devices (company_id, deleted_at) WHERE deleted_at IS NULL;

-- GPS Logs — frequent time-based range queries
CREATE INDEX IF NOT EXISTS idx_gps_logs_created_at_date
    ON gps_logs (created_at) WHERE created_at >= NOW() - INTERVAL '5 minutes';

-- Login Attempts
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip
    ON login_attempts (ip_address);

-- Blocked IPs
CREATE INDEX IF NOT EXISTS idx_blocked_ips_active
    ON blocked_ips (ip_address) WHERE is_active = true;

-- Audit Logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_time
    ON audit_logs (user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
    ON audit_logs (entity_type, entity_id);

-- Document References — expiry queries
CREATE INDEX IF NOT EXISTS idx_archived_documents_expiry
    ON archived_documents (expiry_date) WHERE has_expiry_date = true AND is_deleted = false;

-- Alembic version check
INSERT INTO alembic_version (version_num) VALUES ('add_perf_indexes_v1')
ON CONFLICT (version_num) DO NOTHING;
