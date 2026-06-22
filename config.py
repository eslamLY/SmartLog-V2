import os


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY') or (None if os.environ.get('PRODUCTION') else 'dev-default-insecure-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_CHECK_DEFAULT = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = 'development'
    PRODUCTION = False
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///bloodbank.db'
    ).replace('postgres://', 'postgresql://', 1)


class TestingConfig(BaseConfig):
    TESTING = True
    ENV = 'testing'
    PRODUCTION = False
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///test_bloodbank.db'
    ).replace('postgres://', 'postgresql://', 1)
    PRESERVE_CONTEXT_ON_EXCEPTION = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = 'production'
    PRODUCTION = True
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL'
    ).replace('postgres://', 'postgresql://', 1) if os.environ.get('DATABASE_URL') else None


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
