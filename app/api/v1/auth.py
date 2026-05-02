"""
/api/v1/auth — Mobile authentication endpoints
POST /api/v1/auth/login      → Access + Refresh tokens
POST /api/v1/auth/refresh    → New access token
POST /api/v1/auth/logout     → Invalidate (client-side token deletion)
GET  /api/v1/auth/me         → Current user profile
PATCH /api/v1/auth/me        → Update profile (name, phone)
POST /api/v1/auth/change-password
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from app.extensions import db, bcrypt
from app.models import User, Student, Status, Roles
from app.api.decorators import get_current_api_user

auth_api_bp = Blueprint('auth_api', __name__)


@auth_api_bp.route('/login', methods=['POST'])
def login():
    """
    Mobile Login — returns JWT access + refresh tokens
    ---
    tags: [Auth]
    parameters:
      - in: body
        name: body
        schema:
          required: [email, password]
          properties:
            email: {type: string, example: "student@csmss.edu"}
            password: {type: string, example: "MyPass@123"}
    responses:
      200:
        description: Login successful
        schema:
          properties:
            access_token: {type: string}
            refresh_token: {type: string}
            user:
              properties:
                id: {type: integer}
                name: {type: string}
                email: {type: string}
                role: {type: string}
                must_change_password: {type: boolean}
      401:
        description: Invalid credentials
      403:
        description: Account blocked or pending
    """
    data = request.get_json(silent=True) or {}
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if user.status == Status.BLOCKED:
        return jsonify({'error': 'Account blocked. Contact administrator.'}), 403

    if user.status == Status.PENDING:
        return jsonify({'error': 'Account pending approval. Please wait for admin activation.'}), 403

    access_token  = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    # Build user profile payload
    profile = _build_user_profile(user)

    return jsonify({
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'user': profile
    }), 200


@auth_api_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using refresh token
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: New access token
    """
    identity     = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({'access_token': access_token}), 200


@auth_api_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout — client should delete stored tokens
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: Logged out
    """
    # JWT is stateless — actual invalidation requires a blocklist (Redis).
    # For now client deletes the tokens. Add JWT blocklist if needed.
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_api_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """
    Get current user profile
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    responses:
      200:
        description: User profile with role-specific data
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': _build_user_profile(user)}), 200


@auth_api_bp.route('/me', methods=['PATCH'])
@jwt_required()
def update_profile():
    """
    Update current user profile (name, phone)
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          properties:
            name: {type: string}
            phone: {type: string}
    responses:
      200:
        description: Profile updated
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'name' in data and data['name'].strip():
        user.name = data['name'].strip()[:120]
    if 'phone' in data:
        user.phone = (data['phone'] or '').strip()[:15]

    db.session.commit()
    return jsonify({'message': 'Profile updated', 'user': _build_user_profile(user)}), 200


@auth_api_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change password (also clears must_change_password flag)
    ---
    tags: [Auth]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          required: [new_password, confirm_password]
          properties:
            current_password: {type: string, description: "Required if not first-login"}
            new_password: {type: string}
            confirm_password: {type: string}
    responses:
      200:
        description: Password changed
      400:
        description: Validation error
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data       = request.get_json(silent=True) or {}
    new_pw     = (data.get('new_password') or '').strip()
    confirm_pw = (data.get('confirm_password') or '').strip()
    current_pw = (data.get('current_password') or '').strip()

    if len(new_pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if new_pw != confirm_pw:
        return jsonify({'error': 'Passwords do not match'}), 400
    if new_pw in ('csmss@123', 'csmss123', 'password', '12345678'):
        return jsonify({'error': 'Please choose a stronger password'}), 400

    # If NOT a forced first-login change, verify current password
    if not user.must_change_password:
        if not current_pw:
            return jsonify({'error': 'Current password is required'}), 400
        if not bcrypt.check_password_hash(user.password_hash, current_pw):
            return jsonify({'error': 'Current password is incorrect'}), 401

    user.password_hash       = bcrypt.generate_password_hash(new_pw).decode('utf-8')
    user.must_change_password = False
    db.session.commit()
    return jsonify({'message': 'Password changed successfully'}), 200


@auth_api_bp.route('/forgot-password-api', methods=['POST'])
def forgot_password_api():
    """
    Mobile forgot password — sends OTP email
    ---
    tags: [Auth]
    parameters:
      - in: body
        name: body
        schema:
          required: [email]
          properties:
            email: {type: string}
    responses:
      200:
        description: OTP sent (or silently skipped if email not found)
    """
    import secrets
    from datetime import datetime, timedelta
    from app.models import OTPRequest
    from app.utils.email_utils import send_otp_email

    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        otp_code = str(secrets.randbelow(900000) + 100000)
        otp_hash = bcrypt.generate_password_hash(otp_code).decode('utf-8')
        OTPRequest.query.filter_by(user_id=user.id).delete()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        db.session.add(OTPRequest(user_id=user.id, otp_hash=otp_hash, expires_at=expires_at))
        db.session.commit()
        send_otp_email(user.email, otp_code, user.name)

    # Always return same message (don't reveal if email exists)
    return jsonify({'message': 'If your email is registered, an OTP has been sent.'}), 200




# ── Internal helper ──────────────────────────────────────────────────────────
def _build_user_profile(user):
    """Build a consistent user profile dict for API responses."""
    profile = {
        'id':                   user.id,
        'name':                 user.name,
        'email':                user.email,
        'role':                 user.role,
        'phone':                user.phone,
        'profile_pic':          user.profile_pic,
        'must_change_password': user.must_change_password,
        'status':               user.status,
    }

    # Role-specific additions
    if user.role in (Roles.STUDENT, Roles.CR):
        sp = user.student_profile
        if sp:
            profile['student'] = {
                'id':         sp.id,
                'roll_no':    sp.roll_no,
                'prn':        sp.prn,
                'batch':      sp.batch,
                'class_id':   sp.class_id,
                'class_name': sp.class_.name if sp.class_ else None,
                'tg_id':      sp.tg_id,
                'year':       sp.current_year,
                'semester':   sp.semester,
            }

    if user.role in (Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD):
        tp = user.teacher_profile
        if tp:
            profile['teacher'] = {
                'id':            tp.id,
                'designation':   tp.designation,
                'department_id': tp.department_id,
                'department':    tp.department.name if tp.department else None,
            }

    return profile
