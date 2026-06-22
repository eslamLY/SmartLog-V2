"""اختبار التأكد من رفض الإقلاع في الإنتاج عند فقدان المتغيرات"""

import subprocess, sys, os

_VALID_FERNET_KEY = 'vbbixqOsKysfSF0hsEuNjonVd5tXOksDoYG2dPdJ_Zg='

def _run(code):
    """Run Python code in subprocess clearing inherited test env vars first."""
    return subprocess.run([sys.executable, '-c', code],
        capture_output=True, text=True, timeout=10,
        cwd=os.path.join(os.path.dirname(__file__), '..'))

def test_production_crashes_without_field_key():
    code = (
        'import os; '
        'os.environ.pop("SECRET_KEY",None); os.environ.pop("DATABASE_URL",None); os.environ.pop("FIELD_ENCRYPTION_KEY",None); '
        'os.environ["FLASK_ENV"] = "production"; '
        'os.environ["SECRET_KEY"] = "prod-secret"; '
        'os.environ["DATABASE_URL"] = "sqlite:///prod.db"; '
        'from app import app'
    )
    r = _run(code)
    assert r.returncode != 0, 'Expected RuntimeError but app imported'
    assert 'CRITICAL CONFIGURATION ERROR' in r.stderr
    assert 'FIELD_ENCRYPTION_KEY' in r.stderr

def test_production_crashes_without_secret_key():
    code = (
        'import os; '
        'os.environ.pop("SECRET_KEY",None); os.environ.pop("DATABASE_URL",None); os.environ.pop("FIELD_ENCRYPTION_KEY",None); '
        'os.environ["FLASK_ENV"] = "production"; '
        'os.environ["DATABASE_URL"] = "sqlite:///prod.db"; '
        f'os.environ["FIELD_ENCRYPTION_KEY"] = "{_VALID_FERNET_KEY}"; '
        'from app import app'
    )
    r = _run(code)
    assert r.returncode != 0
    assert 'SECRET_KEY' in r.stderr

def test_production_crashes_without_database_url():
    code = (
        'import os; '
        'os.environ.pop("SECRET_KEY",None); os.environ.pop("DATABASE_URL",None); os.environ.pop("FIELD_ENCRYPTION_KEY",None); '
        'os.environ["FLASK_ENV"] = "production"; '
        'os.environ["SECRET_KEY"] = "prod-secret"; '
        f'os.environ["FIELD_ENCRYPTION_KEY"] = "{_VALID_FERNET_KEY}"; '
        'from app import app'
    )
    r = _run(code)
    assert r.returncode != 0
    assert 'DATABASE_URL' in r.stderr

def test_production_boots_with_all_vars():
    code = (
        'import os; '
        'os.environ.pop("SECRET_KEY",None); os.environ.pop("DATABASE_URL",None); os.environ.pop("FIELD_ENCRYPTION_KEY",None); '
        'os.environ["FLASK_ENV"] = "production"; '
        'os.environ["SECRET_KEY"] = "prod-secret"; '
        'os.environ["DATABASE_URL"] = "sqlite:///prod.db"; '
        f'os.environ["FIELD_ENCRYPTION_KEY"] = "{_VALID_FERNET_KEY}"; '
        'from app import app; '
        'print("OK:" + str(app.config["PRODUCTION"]))'
    )
    r = _run(code)
    assert r.returncode == 0, f'stderr: {r.stderr}'
    assert 'OK:True' in r.stdout
