"""
pg_backup_local.py — PostgreSQL Full Backup via psycopg2 (Windows/Render SNI-safe)
Usage:
    python scripts/pg_backup_local.py

Output: ~/Desktop/SmartLog_Backup_YYYY-MM-DD_HHMMSS.sql
"""

import os, sys, re, gzip, time, textwrap
from datetime import datetime
from getpass import getpass

DB_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://smartlog_db_user:lmeG1NNv41Y6WrCRGfuxQ1x5AYQxdlBe@dpg-d8svlqurnols739v473g-a.frankfurt-postgres.render.com/smartlog_db?sslmode=require',
)


def parse_url(url: str) -> dict:
    """Parse a PostgreSQL URL into connection parameters."""
    m = re.match(
        r'postgresql://(?:(?P<user>[^:]+)(?::(?P<pass>[^@]+))?@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<dbname>.+?)(?:\?.*)?$',
        url,
    )
    if not m:
        raise ValueError(f'Cannot parse DATABASE_URL: {url[:60]}...')
    parts = m.groupdict()
    ssl_mode = 'require'
    if 'sslmode=' in url:
        m2 = re.search(r'sslmode=(\w+)', url)
        if m2:
            ssl_mode = m2.group(1)
    return {
        'host': parts['host'],
        'port': int(parts['port'] or 5432),
        'dbname': parts['dbname'],
        'user': parts['user'] or 'postgres',
        'password': parts['pass'] or '',
        'sslmode': ssl_mode,
    }


def connect(params: dict):
    import psycopg2
    conn = psycopg2.connect(**params)
    conn.set_session(autocommit=True)
    return conn


def get_all_tables(conn) -> list[dict]:
    """Return list of {schema, name, type, has_sequences} ordered by dependency."""
    cur = conn.cursor()
    cur.execute("""
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    """)
    rows = cur.fetchall()
    cur.close()
    tables = []
    for schema, name, _ in rows:
        # skip django/pg internal
        if schema == 'public' and name.startswith('sql_'):
            continue
        tables.append({'schema': schema, 'name': name, 'type': 'TABLE'})
    return tables


def get_columns(conn, schema: str, table: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT c.column_name, c.data_type, c.is_nullable, c.column_default,
               c.character_maximum_length,
               CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_pk,
               CASE WHEN c.data_type IN ('integer','bigint','smallint','serial','bigserial')
                      AND c.column_default LIKE 'nextval%%' THEN TRUE ELSE FALSE END AS is_serial
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
              ON tc.constraint_name = ku.constraint_name
             AND tc.table_schema = ku.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        ) pk ON pk.column_name = c.column_name
        WHERE c.table_schema = %s AND c.table_name = %s
        ORDER BY c.ordinal_position
    """, (schema, table, schema, table))
    cols = cur.fetchall()
    cur.close()
    result = []
    for row in cols:
        result.append({
            'name': row[0], 'type': row[1], 'nullable': row[2],
            'default': row[3], 'max_len': row[4], 'is_pk': row[5],
            'is_serial': row[6],
        })
    return result


def fetch_all_data(conn, schema: str, table: str, columns: list[dict], chunk=500) -> list[list]:
    """Fetch all rows, returning as list of lists."""
    col_names = [c['name'] for c in columns]
    cur = conn.cursor()
    cur.execute(f'SELECT {",".join(col_names)} FROM {quote_ident(schema)}.{quote_ident(table)}')
    rows = []
    while True:
        batch = cur.fetchmany(chunk)
        if not batch:
            break
        rows.extend(batch)
    cur.close()
    return rows


def quote_ident(name: str) -> str:
    return f'"{name}"'


def escape_value(val, col: dict) -> str:
    if val is None:
        return 'NULL'
    if col['type'] in ('integer', 'bigint', 'smallint', 'real', 'double precision',
                       'numeric', 'money', 'serial', 'bigserial', 'smallserial'):
        return str(val)
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, bytes):
        val = val.decode('utf-8', errors='replace')
    s = str(val)
    s = s.replace("'", "''")
    s = s.replace('\\', '\\\\')
    return f"'{s}'"


def generate_insert(schema: str, table: str, columns: list[dict], rows: list[list]) -> str:
    if not rows:
        return ''
    col_names = [quote_ident(c['name']) for c in columns]
    stmt = f'INSERT INTO {quote_ident(schema)}.{quote_ident(table)} ({",".join(col_names)}) VALUES\n'
    vals_list = []
    for row in rows:
        escaped = [escape_value(val, col) for val, col in zip(row, columns)]
        vals_list.append(f'({",".join(escaped)})')
    return stmt + ',\n'.join(vals_list) + ';\n\n'


def generate_create_schema(conn, schema: str, table: str, columns: list[dict]) -> str:
    col_defs = []
    for c in columns:
        defn = f'  {quote_ident(c["name"])} {c["type"]}'
        if c['is_serial']:
            if c['type'] == 'integer':
                defn = f'  {quote_ident(c["name"])} SERIAL'
            elif c['type'] == 'bigint':
                defn = f'  {quote_ident(c["name"])} BIGSERIAL'
        if c['is_pk']:
            # PK is set below
            pass
        if not c['nullable'] and not c['is_pk']:
            defn += ' NOT NULL'
        if c['default'] and not c['is_serial']:
            # Use the server default as-is (it's from information_schema)
            defn += f' DEFAULT {c["default"]}'
        col_defs.append(defn)
    pk_cols = [quote_ident(c['name']) for c in columns if c['is_pk']]
    if pk_cols:
        col_defs.append(f'  PRIMARY KEY ({",".join(pk_cols)})')
    return (
        f'CREATE TABLE IF NOT EXISTS {quote_ident(schema)}.{quote_ident(table)} (\n'
        + ',\n'.join(col_defs)
        + '\n);\n\n'
    )


def build_constraints_and_indexes(conn, schema: str, table: str) -> str:
    """Generate ALTER TABLE statements for foreign keys and indexes."""
    output = []
    cur = conn.cursor()
    # Foreign keys
    cur.execute("""
        SELECT tc.constraint_name, kcu.column_name,
               ccu.table_schema AS ref_schema, ccu.table_name AS ref_table,
               ccu.column_name AS ref_column, rc.update_rule, rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints rc
          ON rc.constraint_name = tc.constraint_name
         AND rc.constraint_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = %s AND tc.table_name = %s
    """, (schema, table))
    for row in cur.fetchall():
        output.append(
            f'ALTER TABLE {quote_ident(schema)}.{quote_ident(table)} '
            f'ADD CONSTRAINT {quote_ident(row[0])} '
            f'FOREIGN KEY ({quote_ident(row[1])}) '
            f'REFERENCES {quote_ident(row[2])}.{quote_ident(row[3])} ({quote_ident(row[4])}) '
            f'ON UPDATE {row[5]} ON DELETE {row[6]};\n'
        )
    # Indexes (non-unique, non-PK)
    cur.execute("""
        SELECT i.indexrelid::regclass::text, ix.indisunique,
               array_agg(a.attname ORDER BY a.attnum) AS cols
        FROM pg_index ix
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
        WHERE t.relname = %s
          AND ix.indisprimary = FALSE
          AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)
        GROUP BY i.indexrelid, ix.indisunique
    """, (table, schema))
    for row in cur.fetchall():
        idx_name = row[0]
        unique = 'UNIQUE ' if row[1] else ''
        cols = ', '.join(quote_ident(c) for c in row[2])
        output.append(
            f'CREATE {unique}INDEX IF NOT EXISTS {quote_ident(idx_name)} '
            f'ON {quote_ident(schema)}.{quote_ident(table)} ({cols});\n'
        )
    cur.close()
    return ''.join(output)


def setval_sequences(conn) -> str:
    """Generate SELECT setval() for all sequences in public."""
    output = []
    cur = conn.cursor()
    cur.execute("""
        SELECT sequence_name FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    """)
    seqs = cur.fetchall()
    for (seq_name,) in seqs:
        output.append(
            f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM "
            f"{seq_name.replace('_id_seq', '')}), 1)) "
            f"WHERE (SELECT MAX(id) FROM {seq_name.replace('_id_seq', '')}) IS NOT NULL;\n"
        )
    cur.close()
    return ''.join(output)


def print_wrap(msg: str):
    width = min(72, os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 72)
    for line in msg.split('\n'):
        for wrapped in textwrap.wrap(line, width=width):
            print(f'  {wrapped}')


def main():
    print('=' * 60)
    print('  SmartLog — PostgreSQL Backup Tool (psycopg2 / SNI-safe)')
    print(f'  Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # ── 1. Parse connection ────────────────────────────────
    print('\n[1/6] Parsing DATABASE_URL...')
    params = parse_url(DB_URL)
    masked = {**params, 'password': '****'}
    print(f'       Host: {params["host"]}:{params["port"]}')
    print(f'       DB:   {params["dbname"]}')
    print(f'       User: {params["user"]}')
    print(f'       SSL:  {params["sslmode"]}')

    # ── 2. Connect ─────────────────────────────────────────
    print('\n[2/6] Connecting to PostgreSQL on Render (sslmode=require)...')
    try:
        conn = connect(params)
        cur = conn.cursor()
        cur.execute('SELECT version()')
        ver = cur.fetchone()[0]
        cur.close()
        print(f'       Connected OK')
        print_wrap(f'       {ver}')
    except Exception as e:
        print(f'\n  ERROR: Connection failed:\n       {e}')
        sys.exit(1)

    # ── 3. Get all tables ──────────────────────────────────
    print('\n[3/6] Scanning tables...')
    tables = get_all_tables(conn)
    print(f'       Found {len(tables)} tables')

    # ── 4. Build output path ────────────────────────────────
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_file = os.path.join(desktop, f'SmartLog_Backup_{timestamp}.sql')
    print(f'\n[4/6] Output file:')
    print(f'       {out_file}')

    # ── 5. Export ───────────────────────────────────────────
    print(f'\n[5/6] Exporting data...')
    start = time.time()
    total_rows = 0
    total_size = 0
    exported = []
    skipped = []

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f'-- SmartLog Database Backup\n')
        f.write(f'-- Generated: {datetime.now().isoformat()}\n')
        f.write(f'-- Host: {params["host"]}:{params["port"]}\n')
        f.write(f'-- Database: {params["dbname"]}\n')
        f.write(f'-- SSL Mode: {params["sslmode"]}\n')
        f.write(f'\nSET statement_timeout = 0;\n')
        f.write(f'SET lock_timeout = 0;\n')
        f.write(f'SET client_encoding = \'UTF8\';\n')
        f.write(f'SET standard_conforming_strings = on;\n')
        f.write(f'SELECT pg_catalog.set_config(\'search_path\', \'\', false);\n')
        f.write(f'SET idle_in_transaction_session_timeout = 0;\n')
        f.write(f'SET row_security = off;\n\n')
        f.write(f'BEGIN;\n\n')

        for i, tbl in enumerate(tables, 1):
            schema, name = tbl['schema'], tbl['name']
            label = f'{i}/{len(tables)}  {schema}.{name}'
            try:
                cols = get_columns(conn, schema, name)
                if not cols:
                    skipped.append(f'{schema}.{name} (no columns)')
                    continue

                # DDL
                ddl = generate_create_schema(conn, schema, name, cols)
                f.write(f'-- Table: {schema}.{name}\n{ddl}')
                cons = build_constraints_and_indexes(conn, schema, name)
                if cons:
                    f.write(f'-- Constraints & indexes for {schema}.{name}\n{cons}')

                # Data
                rows = fetch_all_data(conn, schema, name, cols)
                insert_sql = generate_insert(schema, name, cols, rows)
                if insert_sql:
                    f.write(insert_sql)
                total_rows += len(rows)
                print(f'       {label}  {len(rows)} rows  OK')
                exported.append((schema, name, len(rows)))
            except Exception as e:
                print(f'       {label}  ERROR: {e}')
                skipped.append(f'{schema}.{name} ({e})')

        # Sequences
        seqs = setval_sequences(conn)
        if seqs:
            f.write(f'-- Sequences\n{seqs}')

        f.write('COMMIT;\n')

    # ── 6. Done ─────────────────────────────────────────────
    elapsed = time.time() - start
    file_size = os.path.getsize(out_file)
    print(f'\n[6/6] Backup complete!')
    print(f'       Tables exported: {len(exported)}')
    print(f'       Total rows:      {total_rows:,}')
    print(f'       File size:       {file_size / 1024:.1f} KB ({file_size / 1024 / 1024:.2f} MB)')
    print(f'       Time:            {elapsed:.1f} seconds')
    print(f'       Saved to:')
    print(f'       {out_file}')
    if skipped:
        print(f'\n  WARNING: {len(skipped)} table(s) had issues:')
        for s in skipped:
            print(f'    - {s}')
    print()
    print('  TIP: To restore, run:')
    print(f'    psql -U <user> -h <host> -d <db> -f "{out_file}"')
    print()
    print('=' * 60)

    conn.close()


if __name__ == '__main__':
    main()
