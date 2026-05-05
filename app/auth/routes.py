from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from app.extensions import db, bcrypt, limiter
from app.models import User, Student, Teacher, Department, Class, Roles, Status, ApprovalStatus, OTPRequest
from app.utils.helpers import send_notification

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')



@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")   # Prevents brute-force at scale
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            if user.status == Status.BLOCKED:
                flash('Your account has been blocked. Contact admin.', 'danger')
                return redirect(url_for('auth.login'))
            if user.status == Status.PENDING:
                flash('Your account is pending approval. Please wait for admin activation.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
            # Security: only allow relative paths to prevent open redirect
            if next_page and (next_page.startswith('http') or next_page.startswith('//')): 
                next_page = None
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    flash('Self-registration is disabled. Please contact your HOD or Principal to get login credentials.', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/pending')
@login_required
def pending():
    # SYSTEM_ADMIN has no student profile — redirect directly to their console
    if current_user.role == Roles.SYSTEM_ADMIN:
        return redirect(url_for('sysadmin.index'))
    return render_template('auth/pending.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    student = None
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        student = current_user.student_profile

    if request.method == 'POST':
        # ── User core fields ────────────────────────────────────────────────
        current_user.name  = request.form.get('name', current_user.name).strip()
        current_user.phone = (request.form.get('phone', '') or '').strip() or current_user.phone
        new_pw      = request.form.get('new_password', '').strip()
        confirm_pw  = request.form.get('confirm_password', '').strip()
        if new_pw:
            if len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'danger')
                return redirect(url_for('auth.profile'))
            if new_pw != confirm_pw:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('auth.profile'))
            if new_pw in ('csmss@123', 'csmss123', 'password', '12345678'):
                flash('Please choose a stronger password.', 'danger')
                return redirect(url_for('auth.profile'))
            current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')

        # Handle Profile Picture Upload
        profile_file = request.files.get('profile_pic')
        if profile_file and profile_file.filename:
            allowed_ext = {'.jpg', '.jpeg', '.png', '.webp'}  # must match cloudinary_upload.py allowlist
            ext = os.path.splitext(profile_file.filename)[1].lower()
            if ext not in allowed_ext:
                flash('Only image files (JPG, PNG, WEBP) are allowed.', 'danger')
                return redirect(url_for('auth.profile'))

            from app.utils.cloudinary_upload import upload_profile_picture
            result = upload_profile_picture(profile_file, current_user.id)
            if result:
                current_user.profile_pic = result
            else:
                flash('Photo upload failed. Please try again.', 'warning')

        # ── Student extended profile fields ─────────────────────────────────
        if student:
            student.dob         = request.form.get('dob',         student.dob)
            student.gender      = request.form.get('gender',      student.gender)
            student.category    = request.form.get('category',    student.category)
            student.blood_group = request.form.get('blood_group', student.blood_group)
            student.aadhar_no   = request.form.get('aadhar_no',   student.aadhar_no)
            student.mother_name = request.form.get('mother_name', student.mother_name)
            student.address     = request.form.get('address',     student.address)
            student.city        = request.form.get('city',        student.city)
            student.district    = request.form.get('district',    student.district)
            student.state       = request.form.get('state',       student.state)
            student.pincode     = request.form.get('pincode',     student.pincode)

        db.session.commit()
        flash('Profile updated successfully! ✅', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', student=student)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Mandatory password change for users created with default password."""
    if request.method == 'POST':
        new_pw     = request.form.get('new_password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()

        if len(new_pw) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/change_password.html')

        if new_pw != confirm_pw:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/change_password.html')

        # Don't allow keeping the default password
        if new_pw in ('csmss@123', 'csmss123', 'password', '12345678'):
            flash('Please choose a stronger password — do not use the default.', 'danger')
            return render_template('auth/change_password.html')

        current_user.password_hash       = bcrypt.generate_password_hash(new_pw).decode('utf-8')
        current_user.must_change_password = False
        db.session.commit()
        flash('Password changed successfully! Welcome to CSMSS ERP.', 'success')
        # SYSTEM_ADMIN goes directly to their console, not the regular dashboard
        if current_user.role == Roles.SYSTEM_ADMIN:
            return redirect(url_for('sysadmin.index'))
        return redirect(url_for('dashboard.index'))

    return render_template('auth/change_password.html')


# ── Forgot Password (Email OTP) ────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        user = User.query.filter_by(email=email).first()
        if user:
            import secrets
            from datetime import datetime, timedelta
            from flask import session
            from app.utils.email_utils import send_otp_email

            # Generate cryptographically secure 6-digit OTP
            otp_code = str(secrets.randbelow(900000) + 100000)
            otp_hash = bcrypt.generate_password_hash(otp_code).decode('utf-8')

            # Delete existing OTP requests for this user first
            OTPRequest.query.filter_by(user_id=user.id).delete()

            # Save new OTP valid for 10 minutes
            expires_at = datetime.utcnow() + timedelta(minutes=10)
            req = OTPRequest(user_id=user.id, otp_hash=otp_hash, expires_at=expires_at)
            db.session.add(req)
            db.session.commit()

            if send_otp_email(user.email, otp_code, user.name):
                session['reset_user_id'] = user.id
                flash('A 6-digit OTP has been sent to your email. Please check your inbox.', 'info')
                return redirect(url_for('auth.verify_otp'))
            else:
                OTPRequest.query.filter_by(user_id=user.id).delete()
                db.session.commit()
                flash('Email could not be sent. Please contact your administrator.', 'danger')
        else:
            # Safe message — doesn't reveal if email exists
            flash('If an account with that email exists, an OTP has been sent.', 'info')

    return render_template('auth/forgot_password.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_otp():
    from flask import session
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    user_id = session.get('reset_user_id')
    if not user_id:
        flash('Session expired. Please request a new OTP.', 'warning')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        otp_entered = request.form.get('otp', '').strip()
        if not otp_entered:
            flash('Please enter the OTP code.', 'danger')
            return redirect(url_for('auth.verify_otp'))

        from datetime import datetime
        req = OTPRequest.query.filter_by(user_id=user_id).first()

        if not req:
            flash('OTP not found. Please request a new one.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        if datetime.utcnow() > req.expires_at:
            db.session.delete(req)
            db.session.commit()
            session.pop('reset_user_id', None)
            flash('OTP has expired. Please request a new one.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        if bcrypt.check_password_hash(req.otp_hash, otp_entered):
            # OTP is valid — consume it and allow password reset
            db.session.delete(req)
            db.session.commit()
            session['reset_verified'] = True
            flash('OTP verified! Please set your new password.', 'success')
            return redirect(url_for('auth.reset_password'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')

    return render_template('auth/verify_otp.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    from flask import session
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    user_id  = session.get('reset_user_id')
    verified = session.get('reset_verified')

    if not user_id or not verified:
        flash('Unauthorized. Please complete OTP verification first.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_pw     = request.form.get('new_password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()

        if len(new_pw) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('auth.reset_password'))

        if new_pw != confirm_pw:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.reset_password'))

        if new_pw in ('csmss@123', 'csmss123', 'password', '12345678'):
            flash('Please choose a stronger password.', 'danger')
            return redirect(url_for('auth.reset_password'))

        user = db.session.get(User, user_id)
        if user:
            user.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')
            db.session.commit()
            # Clean up reset session keys
            session.pop('reset_user_id', None)
            session.pop('reset_verified', None)
            flash('✅ Password reset successfully! Please log in with your new password.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('User not found. Please try again.', 'danger')
            return redirect(url_for('auth.forgot_password'))

    return render_template('auth/reset_password.html')
