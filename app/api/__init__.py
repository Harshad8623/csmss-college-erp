"""app/api/__init__.py — registers all v1 API blueprints under /api/v1/"""
from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')


def register_api(app):
    """Called from app/__init__.py to wire up all mobile API blueprints."""
    from app.api.v1.auth       import auth_api_bp
    from app.api.v1.dashboard  import dashboard_api_bp
    from app.api.v1.attendance import attendance_api_bp
    from app.api.v1.resources  import (
        marks_api_bp, notices_api_bp, notifications_api_bp,
        timetable_api_bp, assignments_api_bp, leaves_api_bp,
        grievances_api_bp, certificates_api_bp
    )
    from app.api.swagger import init_swagger

    prefix = '/api/v1'

    app.register_blueprint(auth_api_bp,          url_prefix=f'{prefix}/auth')
    app.register_blueprint(dashboard_api_bp,     url_prefix=f'{prefix}/dashboard')
    app.register_blueprint(attendance_api_bp,    url_prefix=f'{prefix}/attendance')
    app.register_blueprint(marks_api_bp,         url_prefix=f'{prefix}/marks')
    app.register_blueprint(notices_api_bp,       url_prefix=f'{prefix}/notices')
    app.register_blueprint(notifications_api_bp, url_prefix=f'{prefix}/notifications')
    app.register_blueprint(timetable_api_bp,     url_prefix=f'{prefix}/timetable')
    app.register_blueprint(assignments_api_bp,   url_prefix=f'{prefix}/assignments')
    app.register_blueprint(leaves_api_bp,        url_prefix=f'{prefix}/leaves')
    app.register_blueprint(grievances_api_bp,    url_prefix=f'{prefix}/grievances')
    app.register_blueprint(certificates_api_bp,  url_prefix=f'{prefix}/certificates')

    # Swagger docs at /api/docs
    init_swagger(app)
