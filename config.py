import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── CRITICAL: SECRET_KEY must be set as an env var on Render ──────────────
    # A random key generated at startup means EVERY Gunicorn worker (and every
    # restart) gets a DIFFERENT key — sessions from worker-1 break on worker-2.
    # Set SECRET_KEY in Render Environment Variables. Never leave it unset in prod.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-local-only-DO-NOT-USE-IN-PROD'

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
    SITE_URL              = os.environ.get('SITE_URL', 'https://csmss-college-erp.onrender.com')

    # ── Email / SMTP Settings (For Forgot Password OTP) ───────────────────────
    MAIL_SERVER           = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT             = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS          = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    MAIL_USERNAME         = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD         = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER   = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME

    # ── Web Push (VAPID) Settings ─────────────────────────────────────────────
    VAPID_PUBLIC_KEY    = os.environ.get('VAPID_PUBLIC_KEY', '')
    VAPID_PRIVATE_KEY   = os.environ.get('VAPID_PRIVATE_KEY', '').replace('\\n', '\n')
    VAPID_CLAIMS_EMAIL  = os.environ.get('VAPID_CLAIMS_EMAIL', 'admin@college.edu')

    # ── CSRF Protection (Flask-WTF) ───────────────────────────────────────────
    WTF_CSRF_ENABLED      = True
    WTF_CSRF_TIME_LIMIT   = 3600   # CSRF token expires in 1 hour

    # ── Session Security ──────────────────────────────────────────────────────
    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)   # Auto-logout after 8h
    SESSION_COOKIE_HTTPONLY    = True    # JS cannot read session cookie
    SESSION_COOKIE_SAMESITE    = 'Lax'  # CSRF mitigation
    # Auto-enable Secure flag when deployed on HTTPS (Render/production)
    SESSION_COOKIE_SECURE      = os.environ.get('FLASK_ENV', 'production') == 'production'


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
