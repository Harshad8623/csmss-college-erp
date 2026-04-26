from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from app.extensions import db, bcrypt
from app.models import User, Student, Teacher, Department, Class, Roles, Status, ApprovalStatus
from app.utils.helpers import send_notification

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
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
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    departments = Department.query.all()
    classes = Class.query.all()
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', Roles.STUDENT)
        class_id = request.form.get('class_id')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html', departments=departments, classes=classes)

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html', departments=departments, classes=classes)

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, email=email, phone=phone, password_hash=pw_hash,
                    role=role, status=Status.PENDING)
        db.session.add(user)
        db.session.flush()

        if role == Roles.STUDENT:
            prn = request.form.get('prn', '')
            roll = request.form.get('roll_no', '')
            student = Student(user_id=user.id, class_id=class_id if class_id else None,
                              prn=prn, roll_no=roll, approval_status=ApprovalStatus.PENDING)
            db.session.add(student)

        elif role in [Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD]:
            dept_id = request.form.get('department_id')
            designation = request.form.get('designation', '')
            teacher = Teacher(user_id=user.id, department_id=dept_id if dept_id else None,
                              designation=designation, teacher_type='subject')
            db.session.add(teacher)

        db.session.commit()
        flash('Registration successful! Your account is pending approval.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', departments=departments, classes=classes)

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
            filename = secure_filename(f"{current_user.id}_{profile_file.filename}")
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
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
