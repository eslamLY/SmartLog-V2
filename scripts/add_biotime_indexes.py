"""
إضافة فهارس لجدول biotime_devices لتحسين أداء الاستعلامات.
"""
import psycopg2

DATABASE_URL = "postgresql://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a.frankfurt-postgres.render.com/smartlog_db?sslmode=require"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # اكتشاف الأعمدة الموجودة في الجدول
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'biotime_devices'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    print("Columns in biotime_devices:")
    for col, dtype in columns:
        print(f"  • {col} ({dtype})")

    # تحديد اسم عمود الرقم التسلسلي والعمود المنطقي الموجود فعلياً
    col_names = {c[0] for c in columns}
    serial_col = None
    active_col = None

    for candidate in ['device_sn', 'serial_number', 'serial', 'device_serial', 'sn', 'serial_no']:
        if candidate in col_names:
            serial_col = candidate
            break
    for candidate in ['is_active', 'active', 'enabled', 'status', 'is_online']:
        if candidate in col_names:
            active_col = candidate
            break

    if not serial_col or not active_col:
        print("\n[ERROR] Could not determine column names for indexing.")
        print(f"  Serial candidates found: {serial_col}")
        print(f"  Active candidates found: {active_col}")
        return

    INDEXES = [
        ("idx_biotime_devices_sn", serial_col),
        ("idx_biotime_devices_status", active_col),
    ]

    print(f"\nCreating indexes on biotime_devices using columns: {serial_col}, {active_col}")
    for idx_name, column in INDEXES:
        sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON biotime_devices ({column});"
        cur.execute(sql)
        print(f"  [OK] {idx_name} on biotime_devices({column})")

    conn.commit()

    # عرض النتيجة
    cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'biotime_devices' ORDER BY indexname")
    rows = cur.fetchall()
    print(f"\nActive indexes on 'biotime_devices':")
    for name, definition in rows:
        print(f"  • {name}")

    cur.close()
    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
