"""
API decorators — role-based access control for mobile JWT endpoints.
Mirrors the web @role_required but works with JWT instead of Flask-Login.
"""
from functools import wraps
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask import jsonify
from app.models import User


def jwt_role_required(*roles):
    """
    Decorator that checks the JWT is valid AND the user has one of the given roles.
    Usage:
        @jwt_role_required('TEACHER', 'HOD', 'SUPER_ADMIN')
        def my_endpoint(): ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            identity = get_jwt_identity()
            user = User.query.get(identity)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            if user.role not in roles:
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'This endpoint requires one of: {", ".join(roles)}',
                    'your_role': user.role
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_api_user():
    """Helper to get current user from JWT identity."""
    identity = get_jwt_identity()
    return User.query.get(identity)
