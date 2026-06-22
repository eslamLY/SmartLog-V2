-- ============================================================
-- Migration: Add all new BioTimeDevice fields
-- Database: SQLite
-- ============================================================

-- Connection & Auth
ALTER TABLE biotime_devices ADD COLUMN port INTEGER DEFAULT 4370;
ALTER TABLE biotime_devices ADD COLUMN comm_password VARCHAR(20);
ALTER TABLE biotime_devices ADD COLUMN protocol VARCHAR(10) DEFAULT 'tcp_ip';

-- Device Identity & Hardware Info
ALTER TABLE biotime_devices ADD COLUMN device_model VARCHAR(30);
ALTER TABLE biotime_devices ADD COLUMN manufacture_date DATE;
ALTER TABLE biotime_devices ADD COLUMN warranty_expiry DATE;

ALTER TABLE biotime_devices ADD COLUMN fp_capacity INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN fp_enrolled INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN face_capacity INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN face_enrolled INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN card_capacity INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN card_enrolled INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN txlog_capacity INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN txlog_used INTEGER DEFAULT 0;

-- Assignment & Access Control
ALTER TABLE biotime_devices ADD COLUMN assigned_departments TEXT;
ALTER TABLE biotime_devices ADD COLUMN assigned_employees TEXT;
ALTER TABLE biotime_devices ADD COLUMN access_mode VARCHAR(20) DEFAULT 'fingerprint';
ALTER TABLE biotime_devices ADD COLUMN door_relay_enabled BOOLEAN DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN anti_passback_enabled BOOLEAN DEFAULT 0;

-- Sync & Schedule Settings
ALTER TABLE biotime_devices ADD COLUMN auto_sync_enabled BOOLEAN DEFAULT 1;
ALTER TABLE biotime_devices ADD COLUMN sync_interval INTEGER DEFAULT 5;
ALTER TABLE biotime_devices ADD COLUMN sync_window_start VARCHAR(5);
ALTER TABLE biotime_devices ADD COLUMN sync_window_end VARCHAR(5);
ALTER TABLE biotime_devices ADD COLUMN records_pulled INTEGER DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN sync_error_log TEXT;

-- Health Monitoring
ALTER TABLE biotime_devices ADD COLUMN is_online BOOLEAN DEFAULT 0;
ALTER TABLE biotime_devices ADD COLUMN last_online_at DATETIME;
ALTER TABLE biotime_devices ADD COLUMN uptime_percent_24h FLOAT DEFAULT 100.0;
ALTER TABLE biotime_devices ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- Device Event Logs
CREATE TABLE IF NOT EXISTS device_event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES biotime_devices(id),
    event_type VARCHAR(30) NOT NULL,
    message VARCHAR(300),
    error_code VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Device Health Snapshots (for uptime graphing)
CREATE TABLE IF NOT EXISTS device_health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES biotime_devices(id),
    is_online BOOLEAN DEFAULT 0,
    ping_ms FLOAT,
    fp_enrolled INTEGER DEFAULT 0,
    face_enrolled INTEGER DEFAULT 0,
    txlog_used INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
