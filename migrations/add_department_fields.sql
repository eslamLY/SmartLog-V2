-- Migration: Add all new department fields
-- This script adds columns for Department Identity, Organizational Structure,
-- Staffing, Attendance Rules, Notifications, and creates new related tables.

-- Create new department tables
CREATE TABLE IF NOT EXISTS department_certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    certification VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS department_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    message TEXT NOT NULL,
    priority VARCHAR(10) DEFAULT 'normal',
    delivery_method VARCHAR(50) DEFAULT 'in_app',
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    sent_by INTEGER REFERENCES employees(id),
    target_type VARCHAR(20) DEFAULT 'all',
    target_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS department_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    from_department_id INTEGER REFERENCES departments(id),
    to_department_id INTEGER NOT NULL REFERENCES departments(id),
    transfer_date DATE NOT NULL,
    reason_type VARCHAR(30),
    reason_notes TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    approved_by_manager BOOLEAN DEFAULT 0,
    approved_by_hr BOOLEAN DEFAULT 0,
    manager_approved_at TIMESTAMP,
    hr_approved_at TIMESTAMP,
    executed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many tables
CREATE TABLE IF NOT EXISTS dept_required_certs (
    department_id INTEGER NOT NULL REFERENCES departments(id),
    certification VARCHAR(100) NOT NULL,
    PRIMARY KEY (department_id, certification)
);

CREATE TABLE IF NOT EXISTS dept_allowed_devices (
    department_id INTEGER NOT NULL REFERENCES departments(id),
    device_id INTEGER NOT NULL REFERENCES biotime_devices(id),
    PRIMARY KEY (department_id, device_id)
);

CREATE TABLE IF NOT EXISTS dept_alert_recipients (
    department_id INTEGER NOT NULL REFERENCES departments(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    PRIMARY KEY (department_id, employee_id)
);

-- Add new columns to departments table
ALTER TABLE departments ADD COLUMN code VARCHAR(20) UNIQUE;
ALTER TABLE departments ADD COLUMN icon VARCHAR(50) DEFAULT 'building';
ALTER TABLE departments ADD COLUMN color VARCHAR(7) DEFAULT '#e53935';
ALTER TABLE departments ADD COLUMN description_ar VARCHAR(200);
ALTER TABLE departments ADD COLUMN description_en VARCHAR(200);
ALTER TABLE departments ADD COLUMN dept_type VARCHAR(20) DEFAULT 'operational';
ALTER TABLE departments ADD COLUMN inactive_reason VARCHAR(200);
ALTER TABLE departments ADD COLUMN parent_id INTEGER REFERENCES departments(id);
ALTER TABLE departments ADD COLUMN dept_level INTEGER DEFAULT 1;
ALTER TABLE departments ADD COLUMN manager_id INTEGER REFERENCES employees(id);
ALTER TABLE departments ADD COLUMN deputy_id INTEGER REFERENCES employees(id);
ALTER TABLE departments ADD COLUMN cost_center_code VARCHAR(20);
ALTER TABLE departments ADD COLUMN max_staff_capacity INTEGER DEFAULT 50;
ALTER TABLE departments ADD COLUMN allowed_employment_types VARCHAR(200) DEFAULT 'full_time,part_time';
ALTER TABLE departments ADD COLUMN default_shift_id INTEGER REFERENCES shift_types(id);
ALTER TABLE departments ADD COLUMN grace_period_override INTEGER;
ALTER TABLE departments ADD COLUMN remote_work_allowed BOOLEAN DEFAULT 0;
ALTER TABLE departments ADD COLUMN break_duration_policy INTEGER DEFAULT 60;
ALTER TABLE departments ADD COLUMN overtime_max_weekly INTEGER DEFAULT 12;
ALTER TABLE departments ADD COLUMN overtime_requires_approval BOOLEAN DEFAULT 1;
ALTER TABLE departments ADD COLUMN overtime_auto_approve_under INTEGER DEFAULT 2;
ALTER TABLE departments ADD COLUMN whatsapp_group_id VARCHAR(50);
ALTER TABLE departments ADD COLUMN alert_settings TEXT;
ALTER TABLE departments ADD COLUMN alert_threshold_minutes INTEGER DEFAULT 15;
ALTER TABLE departments ADD COLUMN alert_understaffing_threshold INTEGER;
ALTER TABLE departments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Auto-generate codes for existing departments
UPDATE departments SET code = printf('DEPT-%03d', id) WHERE code IS NULL;
