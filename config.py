"""
SmartLog Configuration — Production-ready with static file settings.
"""
import os, sys, logging, hashlib
from datetime import timedelta

log = logging.getLogger('config')


def validate_database_url(raw: str) -> str:
    raw = (raw or '').strip()
    if not raw:
        log.error('FATAL: DATABASE_URL is empty or not set.')
        sys.exit(1)
    if raw.startswith('postgres://'):
        raw = raw.replace('postgres://', 'postgresql://', 1)
    if not raw.startswith('postgresql://') or '@' not in raw:
        log.error('FATAL: DATABASE_URL must be postgresql://user:pass@host/db')
        sys.exit(1)
    return raw


def masked_url(url: str) -> str:
    if '@' in url:
        return url.split('@')[0].split('://')[0] + '://****:****@' + url.split('@')[1]
    return url


def static_file_hash(filepath):
    """Generate a short content-hash for cache busting."""
    if os.path.isfile(filepath):
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    return 'dev'


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if SECRET_KEY is None:
        _is_prod = os.environ.get('PRODUCTION', '').lower() in ('true', '1', 'yes') \
                   or os.environ.get('RENDER', '').lower() == 'true' \
                   or os.environ.get('FLASK_ENV', 'development').lower() == 'production'
        if _is_prod:
            raise RuntimeError("SECRET_KEY environment variable is missing!")
        SECRET_KEY = 'dev-secret-change-in-prod'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_CHECK_DEFAULT = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    PRODUCTION = False

    # Static file configuration
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_FOLDER = os.path.join(ROOT_DIR, 'static')
    STATIC_URL = '/static'
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(seconds=3600)
    MAX_AGE_LONG = 31536000  # 1 year for versioned files
    MAX_AGE_SHORT = 3600     # 1 hour for non-versioned

    # Allowed CDN origins for Content-Security-Policy
    CDN_WHITELIST = {
        'cdn.jsdelivr.net',
        'cdnjs.cloudflare.com',
        'fonts.googleapis.com',
        'fonts.gstatic.com',
        'unpkg.com',
        'cdn.datatables.net',
        'd3js.org',
    }

    CSP_IMG_EXTRA = {
        '*.tile.openstreetmap.org',
    }

    @classmethod
    def csp_string(cls) -> str:
        join_cdn = lambda doms: ' '.join(f'https://{d}' for d in doms)
        cdn_script = join_cdn(cls.CDN_WHITELIST)
        cdn_style = join_cdn(cls.CDN_WHITELIST)
        cdn_font = join_cdn(cls.CDN_WHITELIST)
        cdn_img = join_cdn(cls.CDN_WHITELIST | cls.CSP_IMG_EXTRA)
        return (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' {cdn_script}; "
            f"style-src 'self' 'unsafe-inline' {cdn_style}; "
            f"img-src 'self' data: blob: https: {cdn_img}; "
            f"font-src 'self' data: {cdn_font}; "
            f"connect-src 'self' https:; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self'; "
            f"object-src 'none'; "
            f"upgrade-insecure-requests;"
        )

    @classmethod
    def init_db(cls, production: bool = False):
        url = validate_database_url(os.environ.get('DATABASE_URL'))
        cls.SQLALCHEMY_DATABASE_URI = url
        cls.SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(os.environ.get('DB_POOL_SIZE', '10')),
            'max_overflow': int(os.environ.get('DB_POOL_OVERFLOW', '20')),
            'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '3600')),
            'pool_pre_ping': True,
            'connect_args': {'sslmode': 'require'} if production else {},
        }


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = 'development'
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = 'production'
    PRODUCTION = True
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(seconds=86400)


TestingConfig = type('TestingConfig', (BaseConfig,), {
    'TESTING': True,
    'ENV': 'testing',
    'SESSION_COOKIE_SECURE': False,
    'REMEMBER_COOKIE_SECURE': False,
    'PRESERVE_CONTEXT_ON_EXCEPTION': False,
})

config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
