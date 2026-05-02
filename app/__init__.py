from flask import Flask, session, redirect, url_for, request
from config import Config
from app.extensions import db, login_manager, bcrypt, migrate, cache, limiter, csrf, jwt
import os

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    jwt.init_app(app)

    # Exempt all /api/v1/ routes from CSRF (they use JWT Bearer tokens)
    csrf.exempt_views = getattr(csrf, 'exempt_views', set())
    @app.after_request
    def _cors_api(response):
        if request.path.startswith('/api/'):
            response.headers['Access-Control-Allow-Origin']  = '*'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        return response

    # ── Session: make permanent so PERMANENT_SESSION_LIFETIME applies ────────
    @app.before_request
    def make_session_permanent():
        session.permanent = True

    # ── Force password change for new users ──────────────────────────────────
    @app.before_request
    def check_must_change_password():
        from flask_login import current_user
        # Only intercept authenticated users who still have default password
        if current_user.is_authenticated and getattr(current_user, 'must_change_password', False):
            # Allow the change-password page, auth flows, static files, SW, and API endpoints
            allowed = (
                'auth.change_password', 'auth.logout', 'auth.forgot_password',
                'auth.verify_otp', 'auth.reset_password',
                'static', 'service_worker', 'health',
                # Notification API must work even during first-login (polling, push subscribe)
                'notifications.unread_api', 'notifications.subscribe',
                'notifications.unsubscribe', 'notifications.push_status',
            )
            if request.endpoint not in allowed:
                return redirect(url_for('auth.change_password'))

    # ── Enable WAL mode for SQLite (prevents "database is locked") ───────────
    if 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        import sqlite3

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA busy_timeout=30000;")  # 30 seconds
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.close()


    os.makedirs(os.path.join(app.root_path, '..', app.config['UPLOAD_FOLDER']), exist_ok=True)

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.attendance.routes import attendance_bp
    from app.marks.routes import marks_bp
    from app.grievance.routes import grievance_bp
    from app.certificate.routes import certificate_bp
    from app.notices.routes import notices_bp
    from app.assignments.routes import assignments_bp
    from app.timetable.routes import timetable_bp
    from app.analytics.routes import analytics_bp
    from app.admin.routes import admin_bp
    from app.notifications.routes import notifications_bp
    from app.leaves.routes import leaves_bp
    from app.sessions.routes import sessions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(marks_bp)
    app.register_blueprint(grievance_bp)
    app.register_blueprint(certificate_bp)
    app.register_blueprint(notices_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(leaves_bp)
    app.register_blueprint(sessions_bp)

    # ── Mobile REST API (/api/v1/) ────────────────────────────────────────────
    from app.api import register_api
    from app.api.v1.auth       import auth_api_bp
    from app.api.v1.dashboard  import dashboard_api_bp
    from app.api.v1.attendance import attendance_api_bp
    from app.api.v1.resources  import (
        marks_api_bp, notices_api_bp, notifications_api_bp,
        timetable_api_bp, assignments_api_bp, leaves_api_bp,
        grievances_api_bp, certificates_api_bp
    )
    # Exempt all API blueprints from CSRF (they use JWT Bearer tokens instead)
    for bp in [auth_api_bp, dashboard_api_bp, attendance_api_bp,
               marks_api_bp, notices_api_bp, notifications_api_bp,
               timetable_api_bp, assignments_api_bp, leaves_api_bp,
               grievances_api_bp, certificates_api_bp]:
        csrf.exempt(bp)
    register_api(app)

    # ── Service Worker: must be served from root with Service-Worker-Allowed header ──
    # Without this, Chrome blocks the SW from controlling pages outside /static/
    @app.route('/sw.js')
    def service_worker():
        from flask import send_from_directory, make_response
        import os
        sw_path = os.path.join(app.root_path, '..', 'static')
        resp = make_response(send_from_directory(sw_path, 'sw.js'))
        resp.headers['Content-Type'] = 'application/javascript'
        resp.headers['Service-Worker-Allowed'] = '/'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    # Exempt push subscribe/unsubscribe from CSRF (uses X-CSRFToken header)
    from app.notifications.routes import subscribe, unsubscribe
    csrf.exempt(subscribe)
    csrf.exempt(unsubscribe)

    # ── Health check endpoint (used by Render, no auth or rate limiting) ──────
    @app.route('/health')
    def health():
        from flask import jsonify
        return jsonify({'status': 'ok', 'service': 'csmss-erp'}), 200

    # Inject globals into all templates
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.utils.cloudinary_upload import get_profile_pic_url
        from datetime import datetime
        
        def format_time_12hr(time_str):
            if not time_str:
                return ''
            try:
                dt = datetime.strptime(time_str, '%H:%M')
                return dt.strftime('%I:%M %p')
            except ValueError:
                try:
                    dt = datetime.strptime(time_str, '%H:%M:%S')
                    return dt.strftime('%I:%M %p')
                except ValueError:
                    return time_str

        unread = 0
        if current_user.is_authenticated and not request.path.startswith('/static'):
            from app.models import Notification
            unread = db.session.query(
                db.func.count(Notification.id)
            ).filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False
            ).scalar() or 0
        return dict(
            college_name=app.config['COLLEGE_NAME'],
            college_short=app.config['COLLEGE_SHORT'],
            unread_notifications=unread,
            profile_pic_url=get_profile_pic_url,  # callable in templates
            format_time_12hr=format_time_12hr,
        )

    # ── Error Handlers ───────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import render_template, request as req, redirect, url_for, flash, jsonify
        from flask_login import current_user as cu
        # API requests → return JSON 403
        if req.path.startswith('/api/') or req.headers.get('Accept', '').startswith('application/json'):
            return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to access this resource.'}), 403
        # Web requests → flash and redirect to dashboard
        if cu.is_authenticated:
            flash('You do not have permission to access that page.', 'danger')
            return redirect(url_for('dashboard.index'))
        try:
            return render_template('errors/403.html'), 403
        except Exception:
            return '<h1>403 Forbidden</h1><p>You do not have access to this resource.</p>', 403

    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template, request as req, jsonify
        if req.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        try:
            return render_template('errors/404.html'), 404
        except Exception:
            return '<h1>404 Not Found</h1>', 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()  # Rollback any broken transaction
        from flask import render_template, request as req, jsonify
        if req.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        try:
            return render_template('errors/500.html'), 500
        except Exception:
            return '<h1>500 Internal Server Error</h1><p>Something went wrong. Please try again.</p>', 500

    return app

