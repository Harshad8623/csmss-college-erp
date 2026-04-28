from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from app.extensions import db, bcrypt, limiter
from app.models import User, Student, Teacher, Department, Class, Roles, Status, ApprovalStatus
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
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
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
    return render_template('auth/pending.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    student = None
    if current_user.role == Roles.STUDENT:
        student = current_user.student_profile

    if request.method == 'POST':
        # ── User core fields ────────────────────────────────────────────────
        current_user.name  = request.form.get('name', current_user.name).strip()
        current_user.phone = request.form.get('phone', current_user.phone).strip()
        new_pw = request.form.get('new_password', '').strip()
        if new_pw and len(new_pw) >= 6:
            current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')

        # Handle Profile Picture Upload
        profile_file = request.files.get('profile_pic')
        if profile_file and profile_file.filename:
            # Use current_app.static_folder so the path matches what url_for('static') serves
            allowed_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            ext = os.path.splitext(profile_file.filename)[1].lower()
            if ext not in allowed_ext:
                flash('Only image files (JPG, PNG, WEBP, GIF) are allowed.', 'danger')
                return redirect(url_for('auth.profile'))
            filename = secure_filename(f"{current_user.id}_{profile_file.filename}")
            upload_folder = os.path.join(current_app.static_folder, 'uploads', 'profiles')
            os.makedirs(upload_folder, exist_ok=True)
            profile_file.save(os.path.join(upload_folder, filename))
            current_user.profile_pic = filename

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
