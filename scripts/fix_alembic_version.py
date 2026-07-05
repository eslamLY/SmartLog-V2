"""
fix_alembic_version.py — تحديث alembic_version إلى أحدث head
تشغيل: python scripts/fix_alembic_version.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

with app.app_context():
    try:
        from flask_migrate import upgrade, stamp
        # Stamp to head to skip already-applied migrations
        stamp(revision='head')
        print('✓ Alembic stamped to head')
        
        # Check current version
        with db.engine.connect() as conn:
            current = conn.execute(db.text('SELECT version_num FROM alembic_version')).scalar()
            print(f'  Current version: {current}')
    except Exception as e:
        print(f'✗ Error: {e}')
