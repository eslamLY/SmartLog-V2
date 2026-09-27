"""Zero-loss SQLite -> PostgreSQL migration for SmartLog V2.

Design notes
------------
* The SQLite source is opened with ``mode=ro``. It is never written, so it
  remains a complete fallback.
* Schema is emitted from SQLAlchemy metadata, but **foreign keys are created in
  a second pass**. ``departments`` and ``employees`` reference each other, which
  no topological table order can satisfy with inline ``CREATE TABLE ...
  REFERENCES``. Splitting constraint creation from table creation sidesteps the
  cycle entirely and is valid PostgreSQL.
* Primary keys are inserted verbatim so IDs stay stable, then every sequence is
  advanced past ``MAX(id)`` with ``setval(pg_get_serial_sequence(...))``.
* Values are coerced using the *model* column type, not the SQLite storage class,
  because SQLite is dynamically typed and stores booleans as 0/1 integers and
  datetimes as ISO text.

Usage
-----
    python scripts/migrate_sqlite_to_pg.py --source smartlog.db \
        --target postgresql://postgres@localhost:5432/smartlog --dry-run
    python scripts/migrate_sqlite_to_pg.py --source smartlog.db \
        --target postgresql://... --execute --verify
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Tables that must never be copied verbatim.
SKIP_TABLES = {"alembic_version"}

# Table pairs caught in a mutual FK cycle; their constraints are added late.
DEFERRED_FK_TABLES = {"departments", "employees"}


def connect_sqlite_ro(path: pathlib.Path):
    """Open SQLite strictly read-only so the fallback source is never mutated."""
    import sqlite3

    con = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    con.text_factory = str
    return con


# --------------------------------------------------------------------------
# value transformation
# --------------------------------------------------------------------------
def _parse_dt(raw):
    if isinstance(raw, dt.datetime):
        return raw
    s = str(raw).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        parsed = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def _parse_date(raw):
    if isinstance(raw, dt.date) and not isinstance(raw, dt.datetime):
        return raw
    if isinstance(raw, dt.datetime):
        return raw.date()
    try:
        return dt.datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def coerce(column, raw):
    """Convert one SQLite value into something the PG driver will accept."""
    if raw is None:
        return None

    tname = type(column.type).__name__

    if tname == "Boolean":
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip().lower()
        if s in ("1", "true", "t", "yes", "y"):
            return True
        if s in ("0", "false", "f", "no", "n"):
            return False
        return None

    if tname == "DateTime":
        return _parse_dt(raw)

    if tname == "Date":
        return _parse_date(raw)

    if tname in ("Integer", "BigInteger", "SmallInteger"):
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return int(raw)
        s = str(raw).strip()
        if s == "":
            return None          # empty string is not a valid integer in PG
        try:
            return int(float(s))
        except ValueError:
            return None

    if tname == "Float":
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        s = str(raw).strip()
        if s == "":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    if tname in ("JSON", "JSONB"):
        if isinstance(raw, (dict, list)):
            return raw
        s = str(raw).strip()
        if not s:
            return None
        try:
            return json.loads(s)      # let SQLAlchemy re-serialise
        except (ValueError, TypeError):
            return None

    if isinstance(raw, bytes):
        return raw                    # psycopg2 maps bytes -> bytea

    return raw


# --------------------------------------------------------------------------
# schema emission
# --------------------------------------------------------------------------
def _fkless_clone(table, md):
    """Copy a table with all ForeignKey constraints removed.

    Done in a throwaway MetaData so the live application metadata is untouched.
    """
    clone = table.to_metadata(md)
    for c in clone.columns:
        c.foreign_keys.clear()
    for const in list(clone.constraints):
        if const.__class__.__name__ == "ForeignKeyConstraint":
            clone.constraints.discard(const)
    return clone


def emit_schema(metadata, out: pathlib.Path):
    """Write PG DDL: tables first (FKs stripped), then ALTER TABLE ADD CONSTRAINT."""
    from sqlalchemy import MetaData
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable, CreateIndex

    d = postgresql.dialect()
    scratch = MetaData()
    tables = list(metadata.sorted_tables)
    create_stmts, fk_stmts, idx_stmts = [], [], []

    for t in tables:
        create_stmts.append(str(CreateTable(_fkless_clone(t, scratch)).compile(dialect=d)))
        # Column(unique=True, index=True) is emitted by SQLAlchemy as a unique
        # INDEX, not a table constraint, and CreateTable does not render indexes.
        # Omitting them silently dropped the uniqueness that FKs such as
        # archived_documents.reference_code -> document_references.reference_code
        # depend on, so they must be created explicitly.
        for ix in sorted(t.indexes, key=lambda i: i.name or ""):
            idx_stmts.append(str(CreateIndex(ix).compile(dialect=d)))
        for fk in t.foreign_keys:
            fk_stmts.append(
                f'ALTER TABLE "{t.name}" ADD CONSTRAINT "fk_{t.name}_{fk.parent.name}" '
                f'FOREIGN KEY ("{fk.parent.name}") REFERENCES "{fk.column.table.name}" '
                f'("{fk.column.name}")'
                + (f' ON DELETE {fk.ondelete}' if fk.ondelete else "")
            )

    parts = [
        "-- SmartLog V2 :: PostgreSQL schema",
        "-- generated by scripts/migrate_sqlite_to_pg.py",
        "-- FKs are added after table creation so mutual cycles resolve.",
        "",
        ";\n\n".join(create_stmts) + ";",
    ]
    if idx_stmts:
        parts += ["", "-- ---- indexes (incl. UNIQUE indexes backing FK targets) ----",
                  ";\n".join(idx_stmts) + ";"]
    parts += ["", "-- ---- deferred foreign keys ----", ";\n".join(fk_stmts) + ";"]
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return len(create_stmts), len(fk_stmts), len(idx_stmts)


def create_schema(engine, metadata):
    """Create tables then add every FK via ALTER, bypassing dependency cycles."""
    from sqlalchemy import MetaData, text
    from sqlalchemy.schema import CreateTable, CreateIndex

    scratch = MetaData()
    with engine.begin() as conn:
        for t in metadata.sorted_tables:
            conn.execute(CreateTable(_fkless_clone(t, scratch), if_not_exists=True))
        # unique=True/index=True columns surface as Index objects; they must be
        # created before the FKs that reference them.
        for t in metadata.sorted_tables:
            for ix in sorted(t.indexes, key=lambda i: i.name or ""):
                conn.execute(CreateIndex(ix, if_not_exists=True))
        for t in metadata.sorted_tables:
            for fk in t.foreign_keys:
                name = f"fk_{t.name}_{fk.parent.name}"
                conn.execute(text(f'ALTER TABLE "{t.name}" DROP CONSTRAINT IF EXISTS "{name}"'))
                stmt = (f'ALTER TABLE "{t.name}" ADD CONSTRAINT "{name}" '
                        f'FOREIGN KEY ("{fk.parent.name}") '
                        f'REFERENCES "{fk.column.table.name}" ("{fk.column.name}")')
                if fk.ondelete:
                    stmt += f" ON DELETE {fk.ondelete}"
                conn.execute(text(stmt))


# --------------------------------------------------------------------------
# ETL
# --------------------------------------------------------------------------
def sqlite_tables(con):
    q = ("SELECT name FROM sqlite_master WHERE type='table' "
         "AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [r[0] for r in con.execute(q)]


def load(con, engine, metadata, dry_run=True, batch=500, log=print):
    from sqlalchemy import insert, select, text

    present = set(sqlite_tables(con))
    stats, problems = {}, []

    for t in metadata.sorted_tables:
        name = t.name
        if name in SKIP_TABLES:
            log(f"  skip   {name} (managed by Alembic, not copied)")
            continue
        if name not in present:
            stats[name] = 0
            continue

        cols = list(t.columns)
        # Select columns BY NAME. A bare `SELECT *` combined with positional
        # indexing silently shifts values into the wrong columns whenever the
        # SQLite physical column order differs from the SQLAlchemy mapping.
        cur = con.execute(
            'SELECT ' + ', '.join(f'"{c.name}"' for c in cols) + f' FROM "{name}"')
        rows = cur.fetchall()
        payload = []
        for r in rows:
            rec = {}
            for i, c in enumerate(cols):
                rec[c.name] = coerce(c, r[i])
            payload.append(rec)

        stats[name] = len(payload)
        if not payload:
            continue
        if dry_run:
            continue

        with engine.begin() as pc:
            for i in range(0, len(payload), batch):
                pc.execute(insert(t), payload[i:i + batch])
        log(f"  loaded {name}: {len(payload)}")

    return stats, problems


def reset_sequences(engine, metadata, log=print):
    """Advance every SERIAL/IDENTITY sequence past MAX(id)."""
    from sqlalchemy import text

    done = 0
    with engine.begin() as conn:
        for t in metadata.sorted_tables:
            pk = list(t.primary_key.columns)
            if len(pk) != 1 or pk[0].name != "id":
                continue
            if not getattr(pk[0], "autoincrement", False):
                continue
            seq = conn.execute(text(
                "SELECT pg_get_serial_sequence(:t, 'id')"), {"t": name_of(t)}).scalar()
            if not seq:
                continue
            mx = conn.execute(text(f'SELECT MAX("id") FROM "{name_of(t)}"')).scalar()
            if mx is None:
                # Empty table: a PostgreSQL sequence cannot be set to 0
                # (setval raises NumericValueOutOfRange, min value is 1).
                # setval(seq, 1, false) makes the next value 1.
                conn.execute(text("SELECT setval(:s, 1, false)"), {"s": seq})
            else:
                # setval(seq, max, true) -> next value is max + 1
                conn.execute(text("SELECT setval(:s, :v, true)"), {"s": seq, "v": int(mx)})
            done += 1
    log(f"  sequences reset: {done}")
    return done


def name_of(t):
    return t.name


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------
def _canon(coltype, value):
    """Canonicalise a value using its DECLARED column type.

    The raw sqlite3 driver hands back 0/1 for Boolean and ISO strings for
    DateTime, while psycopg2 returns bool and datetime objects. Comparing the
    Python values directly reports those as differences even though the data is
    identical, so normalise by the SQLAlchemy type before hashing.
    """
    import datetime as _dt
    import decimal
    if value is None:
        return ('null', '')
    tn = str(coltype).upper()
    if 'BOOL' in tn:
        if isinstance(value, str):
            return ('bool', value.strip() not in ('', '0', 'false', 'False', 'FALSE'))
        return ('bool', bool(value))
    if 'DATETIME' in tn or 'TIMESTAMP' in tn:
        if isinstance(value, _dt.datetime):
            return ('ts', value.replace(tzinfo=None).isoformat(sep=' '))
        try:
            return ('ts', _dt.datetime.fromisoformat(str(value).strip()).isoformat(sep=' '))
        except ValueError:
            return ('ts', str(value))
    if tn.startswith('DATE') and 'TIME' not in tn:
        if isinstance(value, _dt.datetime):
            return ('date', value.date().isoformat())
        if isinstance(value, _dt.date):
            return ('date', value.isoformat())
        try:
            return ('date', _dt.date.fromisoformat(str(value).strip()[:10]).isoformat())
        except ValueError:
            return ('date', str(value))
    if any(k in tn for k in ('INT', 'FLOAT', 'NUMERIC', 'DECIMAL')):
        try:
            return ('num', decimal.Decimal(str(value)).normalize())
        except (decimal.InvalidOperation, ValueError):
            return ('num', str(value))
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ('bytes', bytes(value).hex())
    if isinstance(value, str):
        return ('str', value)
    return ('other', str(value))


def _digest(rows, cols):
    """Order-independent content hash so a count match alone cannot hide corruption."""
    import hashlib
    keyed = sorted(
        (tuple(_canon(c.type, v) for c, v in zip(cols, r)) for r in rows),
        key=lambda t: repr(t),
    )
    h = hashlib.sha256()
    for t in keyed:
        h.update(("\x1f".join(f"{a}:{b}" for a, b in t) + "\x1e").encode('utf-8'))
    return h.hexdigest()


def verify(con, engine, metadata, log=print):
    from sqlalchemy import text

    rows, bad, ck_bad = [], 0, 0
    present = set(sqlite_tables(con))
    with engine.connect() as conn:
        for t in metadata.sorted_tables:
            if t.name in SKIP_TABLES:
                continue
            if t.name in present:
                cols = list(t.columns)
                cur = con.execute(
                    'SELECT ' + ', '.join(f'"{c.name}"' for c in cols) + f' FROM "{t.name}"')
                s_rows = cur.fetchall()
            else:
                cols, s_rows = None, []
            src = len(s_rows)
            try:
                dst = conn.execute(text(f'SELECT COUNT(*) FROM "{t.name}"')).scalar()
            except Exception:
                dst = None
            ok = dst == src
            bad += not ok

            ck = "n/a"
            if cols and dst:
                p_cols = ", ".join(f'"{c.name}"' for c in cols)
                p_rows = conn.execute(text(f'SELECT {p_cols} FROM "{t.name}"')).fetchall()
                s_ck, p_ck = _digest(s_rows, cols), _digest(p_rows, cols)
                same = s_ck == p_ck
                ck = "OK" if same else "MISMATCH"
                ck_bad += not same
            rows.append((t.name, src, dst, "OK" if ok else "MISMATCH", ck))
            if not ok:
                log(f"  MISMATCH {t.name}: sqlite={src} postgres={dst}")
            elif ck == "MISMATCH":
                log(f"  CHECKSUM MISMATCH {t.name}: counts agree but content differs")

    total_src = sum(r[1] for r in rows)
    total_dst = sum((r[2] or 0) for r in rows)
    log(f"\n  tables compared   : {len(rows)}")
    log(f"  rows sqlite       : {total_src}")
    log(f"  rows postgres     : {total_dst}")
    log(f"  count mismatches  : {bad}")
    log(f"  checksum mismatch : {ck_bad}")
    return rows, bad + ck_bad


def main():
    ap = argparse.ArgumentParser(description="Migrate SmartLog V2 from SQLite to PostgreSQL.")
    ap.add_argument("--source", default=str(ROOT / "smartlog.db"))
    ap.add_argument("--target", default=None, help="postgresql:// user:pass@host:port/db")
    ap.add_argument("--execute", action="store_true", help="perform writes (default: dry run)")
    ap.add_argument("--ddl-only", action="store_true", help="just write postgres_schema.sql")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--verify", dest="verify", action="store_true", default=True,
                    help="row-count + checksum verification after load (default)")
    ap.add_argument("--no-verify", dest="verify", action="store_false",
                    help="skip verification")
    args = ap.parse_args()

    os_env_secret = "change-me"
    import os
    os.environ.setdefault("SECRET_KEY", os_env_secret)
    os.environ["RATELIMIT_ENABLED"] = "false"

    import models  # noqa: F401
    from models import db

    src = pathlib.Path(args.source)
    if not src.exists():
        sys.exit(f"source not found: {src}")

    ntab, nfk, nix = emit_schema(db.metadata, ROOT / "postgres_schema.sql")
    print(f"[schema] {ntab} tables, {nix} indexes, {nfk} deferred FK constraints "
          f"-> {ROOT / 'postgres_schema.sql'}")

    if args.ddl_only:
        return 0

    if not args.target:
        print("[etl] no --target given; running SQLite-side analysis only")
        con = connect_sqlite_ro(src)
        stats, _ = load(con, None, db.metadata, dry_run=True)
        con.close()
        nonempty = {k: v for k, v in stats.items() if v}
        print(f"[etl] tables with data: {len(nonempty)}, rows: {sum(nonempty.values())}")
        for k, v in sorted(nonempty.items(), key=lambda x: -x[1]):
            print(f"    {k:<32} {v}")
        return 0

    from sqlalchemy import create_engine
    # psycopg2 does not accept sslmode as a URI query parameter; pass it through
    # connect_args instead, otherwise the driver raises on connect.
    connect_args = {}
    if 'sslmode=' in args.target:
        from sqlalchemy.engine import make_url
        connect_args['sslmode'] = make_url(args.target).query.get('sslmode')
    eng = create_engine(args.target, future=True, connect_args=connect_args or None)
    con = connect_sqlite_ro(src)
    try:
        # Schema creation is a WRITE. It must not happen on a dry run.
        if args.execute:
            create_schema(eng, db.metadata)
            print("[schema] created")
        else:
            print("[schema] DRY RUN - target left untouched")
        stats, _ = load(con, eng, db.metadata, dry_run=not args.execute, batch=args.batch)
        if args.execute:
            reset_sequences(eng, db.metadata)
            if not args.verify:
                print("[verify] skipped (--no-verify)")
                return 0
            _, bad = verify(con, eng, db.metadata)
            print("[verify]", "PASS" if not bad else f"{bad} MISMATCHES")
            return 1 if bad else 0
    finally:
        con.close()
        eng.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
