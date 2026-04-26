from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from app.models import Roles, Status

def role_required(*roles):
    """Decorator to restrict access to specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                abort(403)
            if current_user.status != Status.ACTIVE:
                flash('Your account is not active. Please wait for approval.', 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def active_required(f):
    """Ensure user account is active."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.status != Status.ACTIVE:
            flash('Your account is pending approval.', 'warning')
            return redirect(url_for('auth.pending'))
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    """Only STAFF can access (admin + teachers)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in Roles.STAFF:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def log_action(action, details=None):
    """Log user actions to audit log."""
    from app.models import AuditLog
    from app.extensions import db
    from flask import request
    try:
        log = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
