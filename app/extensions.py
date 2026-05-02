from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager

db           = SQLAlchemy()
login_manager = LoginManager()
bcrypt       = Bcrypt()
migrate      = Migrate()
cache        = Cache()
csrf         = CSRFProtect()
jwt          = JWTManager()

# Rate-limit keyed on the real client IP (works behind Render/Nginx proxy)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
)

login_manager.login_view            = 'auth.login'
login_manager.login_message         = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'
