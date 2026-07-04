import subprocess, sys, os

_VALID_FERNET_KEY = 'vbbixqOsKysfSF0hsEuNjonVd5tXOksDoYG2dPdJ_Zg='

def _run(code):
    """Run Python code in subprocess clearing inherited test env vars first."""
    env = os.environ.copy()
    for k in list(env.keys()):
        if k in ('SECRET_KEY', 'DATABASE_URL', 'FIELD_ENCRYPTION_KEY', 'FLASK_ENV', 'PRODUCTION', 'RENDER', 'RATELIMIT_ENABLED'):
            del env[k]
    return subprocess.run([sys.executable, '-c', code],
        capture_output=True, text=True, timeout=10,
        cwd=os.path.join(os.path.dirname(__file__), '..'),
        env=env)

def test_production_crashes_without_secret_key():
    code = (
        'import os; '
        'os.environ["FLASK_ENV"] = "production"; '
        'os.environ["DATABASE_URL"] = "sqlite:///prod.db"; '
        f'os.environ["FIELD_ENCRYPTION_KEY"] = "{_VALID_FERNET_KEY}"; '
        'from app import app'
    )
    r = _run(code)
    assert r.returncode != 0
    assert 'SECRET_KEY' in r.stderr

def test_production_boots_with_all_vars():
    code = (
        'import os; '
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

def test_production_boots_without_database_url():
    code = (
        'import os; '
        'os.environ["FLASK_ENV"] = "production"; '
        'os.environ["SECRET_KEY"] = "prod-secret"; '
        f'os.environ["FIELD_ENCRYPTION_KEY"] = "{_VALID_FERNET_KEY}"; '
        'from app import app; '
        'print("OK:" + str(app.config.get("PRODUCTION")))'
    )
    r = _run(code)
    assert r.returncode == 0, f'stderr: {r.stderr}'
    assert 'OK:True' in r.stdout
