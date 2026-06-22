-- ============================================================
-- Migration: Add all new Employee fields for the HR system
-- Database: SQLite
-- ============================================================

-- Personal Info
ALTER TABLE employees ADD COLUMN phone_country_code VARCHAR(5) DEFAULT '+218';
ALTER TABLE employees ADD COLUMN national_id VARCHAR(20) NULL;
ALTER TABLE employees ADD COLUMN date_of_birth DATE NULL;
ALTER TABLE employees ADD COLUMN gender VARCHAR(10) NULL;
ALTER TABLE employees ADD COLUMN marital_status VARCHAR(20) NULL;
ALTER TABLE employees ADD COLUMN address TEXT NULL;
ALTER TABLE employees ADD COLUMN profile_photo VARCHAR(200) NULL;

-- Create unique index on national_id (ignore NULLs)
CREATE UNIQUE INDEX IF NOT EXISTS uq_employees_national_id ON employees(national_id) WHERE national_id IS NOT NULL;

-- Employment Info
ALTER TABLE employees ADD COLUMN job_title VARCHAR(100) NULL;
ALTER TABLE employees ADD COLUMN employment_type VARCHAR(20) DEFAULT 'full_time';
ALTER TABLE employees ADD COLUMN hire_date DATE NULL;
ALTER TABLE employees ADD COLUMN contract_end_date DATE NULL;
ALTER TABLE employees ADD COLUMN no_end_date BOOLEAN DEFAULT 0;
ALTER TABLE employees ADD COLUMN manager_id INTEGER REFERENCES employees(id);
ALTER TABLE employees ADD COLUMN shift_type_id INTEGER REFERENCES shift_types(id);
ALTER TABLE employees ADD COLUMN branch_id INTEGER REFERENCES branches(id);

-- BIOTIME Sync
ALTER TABLE employees ADD COLUMN biotime_emp_id INTEGER NULL;
ALTER TABLE employees ADD COLUMN assigned_devices TEXT NULL;
ALTER TABLE employees ADD COLUMN last_sync DATETIME NULL;
ALTER TABLE employees ADD COLUMN fp_enrolled BOOLEAN DEFAULT 0;
ALTER TABLE employees ADD COLUMN face_enrolled BOOLEAN DEFAULT 0;
ALTER TABLE employees ADD COLUMN sync_status VARCHAR(20) DEFAULT 'not_synced';

-- Financial
ALTER TABLE employees ADD COLUMN housing_allowance FLOAT DEFAULT 0.0;
ALTER TABLE employees ADD COLUMN transport_allowance FLOAT DEFAULT 0.0;
ALTER TABLE employees ADD COLUMN other_allowances TEXT NULL;
ALTER TABLE employees ADD COLUMN payment_method VARCHAR(20) DEFAULT 'bank_transfer';
ALTER TABLE employees ADD COLUMN bank_account_number VARCHAR(30) NULL;
ALTER TABLE employees ADD COLUMN bank_name VARCHAR(60) NULL;

-- System Access
ALTER TABLE employees ADD COLUMN permission_level VARCHAR(30) DEFAULT 'employee';
ALTER TABLE employees ADD COLUMN force_password_change BOOLEAN DEFAULT 1;
ALTER TABLE employees ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0;
ALTER TABLE employees ADD COLUMN password_changed_at DATETIME NULL;

-- Emergency Contact
ALTER TABLE employees ADD COLUMN emergency_contact_name VARCHAR(100) NULL;
ALTER TABLE employees ADD COLUMN emergency_relationship VARCHAR(30) NULL;
ALTER TABLE employees ADD COLUMN emergency_phone VARCHAR(20) NULL;
ALTER TABLE employees ADD COLUMN emergency_phone2 VARCHAR(20) NULL;

-- Soft Delete
ALTER TABLE employees ADD COLUMN deleted_at DATETIME NULL;
ALTER TABLE employees ADD COLUMN deleted_by INTEGER REFERENCES employees(id);
ALTER TABLE employees ADD COLUMN delete_reason VARCHAR(300) NULL;

-- Create branches table if not exists
CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(200),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
