import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

    # ── Bcrypt: 10 rounds = ~80ms per hash (12 rounds = ~300ms, no security gain at this scale)
    BCRYPT_LOG_ROUNDS = 10

    # ── Database URI (fix legacy postgres:// scheme for SQLAlchemy 2.x) ──────
    db_uri = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///college_erp.db')
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Connection pool: sized for 10,000 students + 200 teachers ────────────
    # SQLite is only for local dev; production must use PostgreSQL.
    if db_uri and 'sqlite' in db_uri:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"timeout": 30, "check_same_thread": False},
            "pool_pre_ping": True,
        }
    else:
        # PostgreSQL: 10 persistent + 20 burst connections per Gunicorn worker.
        # With 4 workers → max 120 DB connections (well within Render free tier).
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size":     10,
            "max_overflow":  20,
            "pool_timeout":  30,
            "pool_recycle":  300,
            "pool_pre_ping": True,
        }

    # ── Flask-Caching ─────────────────────────────────────────────────────────
    # Use Redis when REDIS_URL is set (Render/production), else fall back to
    # in-process SimpleCache (perfectly fine for a single-worker dev server).
    _redis_url = os.environ.get('REDIS_URL')
    if _redis_url:
        CACHE_TYPE            = 'RedisCache'
        CACHE_REDIS_URL       = _redis_url
    else:
        CACHE_TYPE            = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT     = 300   # 5 minutes

    # ── Flask-Limiter ─────────────────────────────────────────────────────────
    # Rate-limit storage: Redis in production, in-memory in dev
    RATELIMIT_STORAGE_URI     = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT          = '200 per minute'
    RATELIMIT_HEADERS_ENABLED  = True

    # ── General ───────────────────────────────────────────────────────────────
    UPLOAD_FOLDER         = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH    = 16 * 1024 * 1024  # 16 MB
    COLLEGE_NAME          = "CSMSS Chh. Shahu College of Engineering"
    COLLEGE_SHORT         = "CSMSS"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # Tighten rate limits in production
    RATELIMIT_DEFAULT = '100 per minute'


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
