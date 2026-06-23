"""
SmartLog Production Configuration.
Validates DATABASE_URL, provides pool/SSL config, and defines env classes.
"""
import os, sys, logging

log = logging.getLogger('config')


def validate_database_url(raw: str) -> str:
    """Validate and normalize a DATABASE_URL string.
    - Checks it's set and non-empty
    - Converts postgres:// -> postgresql://
    - Verifies format: postgresql://user:pass@host:port/dbname
    Returns the normalized URL or exits with code 1.
    """
    raw = (raw or '').strip()
    if not raw:
        log.error('FATAL: DATABASE_URL is empty or not set.')
        log.error('  Expected: postgresql://user:password@host:5432/dbname')
        log.error('  On Render: auto-injected via render.yaml fromDatabase,')
        log.error('  or set manually in Dashboard -> Environment.')
        sys.exit(1)

    if raw.startswith('postgres://'):
        raw = raw.replace('postgres://', 'postgresql://', 1)
        log.info('DATABASE_URL: converted postgres:// -> postgresql://')

    if not raw.startswith('postgresql://'):
        log.error('FATAL: DATABASE_URL must start with postgresql://')
        log.error('  Got: %s', raw[:40])
        sys.exit(1)

    if '@' not in raw:
        log.error('FATAL: DATABASE_URL missing "@" (malformed)')
        log.error('  Expected: postgresql://user:pass@host:port/dbname')
        sys.exit(1)

    return raw


def masked_url(url: str) -> str:
    """Return a DATABASE_URL with credentials masked for logging."""
    if '@' in url:
        return url.split('@')[0].split('://')[0] + '://****:****@' + url.split('@')[1]
    return url


def pool_config() -> dict:
    return {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '10')),
        'max_overflow': int(os.environ.get('DB_POOL_OVERFLOW', '20')),
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '3600')),
        'pool_pre_ping': True,
    }


def ssl_config(production: bool) -> dict:
    return {'sslmode': 'require'} if production else {}


def engine_options(production: bool) -> dict:
    return {**pool_config(), 'connect_args': ssl_config(production)}


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_CHECK_DEFAULT = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')

    @classmethod
    def init_db(cls, production: bool = False):
        url = validate_database_url(os.environ.get('DATABASE_URL'))
        cls.SQLALCHEMY_DATABASE_URI = url
        cls.SQLALCHEMY_ENGINE_OPTIONS = engine_options(production)


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = 'development'
    PRODUCTION = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = 'production'
    PRODUCTION = True
    SESSION_COOKIE_SECURE = True


TestingConfig = type('TestingConfig', (BaseConfig,), {
    'TESTING': True,
    'ENV': 'testing',
    'PRODUCTION': False,
    'SESSION_COOKIE_SECURE': False,
    'PRESERVE_CONTEXT_ON_EXCEPTION': False,
})

config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
