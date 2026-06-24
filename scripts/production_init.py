#!/usr/bin/env python3
"""
Production Database Initialization
===================================
1. Create/ensure admin user with hashed password (admin / admin2020)
2. Clear all test employee data (keep system config)
3. Reset ID sequences

Usage:
    python scripts/production_init.py               # standalone (needs DATABASE_URL)
    flask init-production                           # Flask CLI

Or via route: /admin/init-production (protected by admin login)
"""

import os, sys
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def count_rows(conn, table):
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def safe_commit(conn):
    try:
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def run(conn):
    """Core logic — uses a connection-like object (Flask db.session or SQLAlchemy Connection)."""

    # ─────────────────────────────────────────────────
    # STEP 1 — Admin user
    # ─────────────────────────────────────────────────
    print("=" * 55)
    print("  STEP 1/3 : Admin user")
    print("=" * 55)

    password = "admin2020"
    pw_hash = generate_password_hash(password, method='pbkdf2:sha256')
    print(f"  Password      : {password}")
    print(f"  Hash (first 40): {pw_hash[:40]}...")

    existing = conn.execute(
        text("SELECT id, username, role FROM employees WHERE username = 'ADMIN'")
    ).fetchone()

    if existing:
        print(f"  Admin user already exists — id={existing[0]}, updating ...")
        conn.execute(text(
            "UPDATE employees SET password_hash = :pw, role = 'admin', "
            "is_active = TRUE, force_password_change = FALSE WHERE username = 'ADMIN'"
        ), {'pw': pw_hash})
        safe_commit(conn)
        print("  Updated.")
    else:
        print("  Creating admin user ...")
        conn.execute(text("""
            INSERT INTO employees
                (username, full_name, department, password_hash, role, is_active,
                 email, permission_level, force_password_change, created_at)
            VALUES
                ('ADMIN', :name, :dept, :pw, 'admin', TRUE,
                 'admin@smartlog.local', 'admin', FALSE, NOW())
        """), {'pw': pw_hash, 'name': 'مدير النظام', 'dept': 'الإدارة'})
        safe_commit(conn)
        print("  Created.")

    admin_count = conn.execute(
        text("SELECT COUNT(*) FROM employees WHERE username = 'ADMIN'")
    ).scalar()
    print(f"  Admin records : {admin_count}")
    print()

    # ─────────────────────────────────────────────────
    # STEP 2 — Clear test data
    # ─────────────────────────────────────────────────
    print("=" * 55)
    print("  STEP 2/3 : Clear test data")
    print("=" * 55)

    deletion_groups = [
        ['rbac_delegations', 'rbac_permission_requests', 'rbac_employee_roles', 'rbac_audit_logs'],
        ['employee_permissions'],
        ['employee_leave_requests', 'employee_leave_balances', 'employee_training',
         'employee_performance', 'employee_disciplinary_actions', 'employee_delegations',
         'employee_children', 'employee_extended'],
        ['employee_promotions', 'promotion_eligibility', 'employee_qualifications',
         'employee_certifications', 'employee_grades'],
        ['salary_advances', 'deduction_records', 'salary_components', 'payroll_records',
         'payroll_audit_logs', 'bank_payment_details', 'approval_steps', 'approval_workflows'],
        ['salary_slip_archives', 'leave_balances', 'employee_profiles'],
        ['attendance_anomalies', 'employee_patterns'],
        ['attendance_review_queue'],
        ['shift_swap_requests', 'shift_exceptions', 'shift_coverage_rules', 'shift_schedules'],
        ['outing_requests', 'leave_requests'],
        ['attendance_logs', 'attendance_policies'],
        ['document_references', 'archived_documents', 'employee_documents', 'document_audit_logs'],
        ['gps_logs', 'photo_verifications', 'geofence_events', 'trusted_locations',
         'location_audit_logs', 'alert_logs', 'gps_tracking_sessions'],
        ['device_event_logs', 'device_health_snapshots'],
        ['biometric_credentials', 'login_attempts', 'blocked_ips', 'trusted_devices'],
        ['notifications'],
        ['audit_logs'],
        ['prediction_result', 'model_performance_log', 'anomaly_log', 'risk_assessment',
         'custom_rule', 'holiday_calendar'],
        ['department_transfers', 'department_announcements', 'department_certifications',
         'dept_required_certs', 'dept_allowed_devices', 'dept_alert_recipients'],
        ['report_corrections', 'scheduled_reports'],
        ['email_logs', 'sms_logs'],
        ['backup_restore_logs', 'backup_audit_logs', 'backup_metadata', 'backup_schedules'],
        ['employees'],
    ]

    total_deleted = 0
    for group in deletion_groups:
        for table in group:
            try:
                cnt = count_rows(conn, table)
                if cnt == 0:
                    continue
                if table == 'employees':
                    pre = count_rows(conn, "employees")
                    conn.execute(text("DELETE FROM employees WHERE username != 'ADMIN'"))
                    safe_commit(conn)
                    post = count_rows(conn, "employees")
                    deleted = pre - post
                else:
                    conn.execute(text(f"DELETE FROM {table}"))
                    safe_commit(conn)
                    deleted = cnt
                if deleted > 0:
                    print(f"  {table + ':':45s} {deleted:>6} rows deleted")
                    total_deleted += deleted
            except Exception as e:
                if "relation" in str(e) and "does not exist" in str(e):
                    continue
                print(f"  {table + ':':45s} SKIP ({e})")
                safe_commit(conn)

    print(f"\n  Total deleted : {total_deleted} rows")
    print()

    # ─────────────────────────────────────────────────
    # STEP 3 — Reset sequences
    # ─────────────────────────────────────────────────
    print("=" * 55)
    print("  STEP 3/3 : Reset sequences")
    print("=" * 55)

    sequences = [
        ('employees_id_seq', 2),
        ('attendance_logs_id_seq', 1),
        ('leave_requests_id_seq', 1),
        ('outing_requests_id_seq', 1),
        ('payroll_records_id_seq', 1),
        ('audit_logs_id_seq', 1),
        ('notifications_id_seq', 1),
        ('login_attempts_id_seq', 1),
        ('rbac_roles_id_seq', 1),
        ('rbac_permissions_id_seq', 1),
        ('shift_types_id_seq', 1),
        ('departments_id_seq', 1),
        ('branches_id_seq', 1),
    ]

    for seq, start in sequences:
        try:
            conn.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH {start}"))
            safe_commit(conn)
            print(f"  {seq + ':':40s} RESTART WITH {start}")
        except Exception:
            pass

    print()

    # ─────────────────────────────────────────────────
    # VERIFICATION
    # ─────────────────────────────────────────────────
    print("=" * 55)
    print("  VERIFICATION")
    print("=" * 55)

    checks = [
        ('Admin user',      "SELECT COUNT(*) FROM employees WHERE username = 'ADMIN' AND role = 'admin'"),
        ('Non-admin users', "SELECT COUNT(*) FROM employees WHERE username != 'ADMIN'"),
        ('Attendance logs', "SELECT COUNT(*) FROM attendance_logs"),
        ('Leave requests',  "SELECT COUNT(*) FROM leave_requests"),
        ('Payroll records', "SELECT COUNT(*) FROM payroll_records"),
        ('Audit logs',      "SELECT COUNT(*) FROM audit_logs"),
    ]

    all_ok = True
    for label, sql in checks:
        cnt = conn.execute(text(sql)).scalar()
        expected = 1 if label == 'Admin user' else 0
        status = 'OK' if cnt == expected else 'FAIL'
        if status == 'FAIL':
            all_ok = False
        print(f"  [{status}] {label + ':':20s} {cnt} {'(expected ' + str(expected) + ')' if status == 'FAIL' else ''}")

    print()
    if all_ok:
        print("  " + "#" * 45)
        print("  #  PRODUCTION INITIALIZATION COMPLETE  #")
        print("  " + "#" * 45)
        print()
        print("  Login credentials:")
        print("    URL      : /login")
        print("    Username : ADMIN")
        print("    Password : admin2020")
        print("    Role     : admin (full access)")
        print()
        return 0
    else:
        print("  WARNING: Some checks did not pass. Review output above.")
        return 1


def main(db_session=None):
    """
    Main entry point.

    If db_session is provided (Flask route mode), use it.
    Otherwise create a standalone engine+connection (CLI mode).
    """
    if db_session is not None:
        return run(db_session)

    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        print("FATAL: DATABASE_URL environment variable is not set.")
        return 1
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    masked = url.split('@')[0].split('://')[0] + '://****:****@' + url.split('@')[1]
    print(f"Connecting to: {masked}")

    from sqlalchemy import create_engine
    engine = create_engine(url, pool_pre_ping=True)
    conn = engine.connect()
    print("Connected.\n")

    try:
        result = run(conn)
    finally:
        conn.close()
        engine.dispose()

    return result


if __name__ == '__main__':
    sys.exit(main())
