from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db, bcrypt
from app.models import (
    User, Student, Teacher, Department, Class, Subject,
    Roles, Status, ApprovalStatus
)
from app.utils.decorators import role_required
from app.utils.helpers import get_dept_for_hod, get_class_for_ct

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ── Helpers ──────────────────────────────────────────────────────────────────
def _hod_dept_id():
    """Return department_id for the current HOD, or None."""
    return get_dept_for_hod(current_user.id)

def _ct_class():
    """Return Class object for the current Class Teacher, or None."""
    return get_class_for_ct(current_user.id)

# ── User Management ─────────────────────────────────────────────────────────
@admin_bp.route('/users')
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD)
def users():
    filter_role   = request.args.get('role', '')
    filter_status = request.args.get('status', '')
    query = User.query

    # HOD sees only teachers/staff in their own department
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        if dept_id:
            teacher_user_ids = [
                t.user_id for t in Teacher.query.filter_by(department_id=dept_id).all()
            ]
            query = query.filter(User.id.in_(teacher_user_ids))
        else:
            query = query.filter(User.id == 0)  # No dept → empty

    if filter_role:
        query = query.filter_by(role=filter_role)
    if filter_status:
        query = query.filter_by(status=filter_status)

    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, roles=Roles.ALL,
                           filter_role=filter_role, filter_status=filter_status)


@admin_bp.route('/users/<int:id>/activate', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def activate_user(id):
    user = User.query.get_or_404(id)
    # HOD can only activate users from own department
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        if not teacher or teacher.department_id != dept_id:
            abort(403)
    user.status = Status.ACTIVE
    db.session.commit()
    flash(f'{user.name} activated.', 'success')
    return redirect(request.referrer or url_for('admin.users'))


@admin_bp.route('/users/<int:id>/block', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN)
def block_user(id):
    user = User.query.get_or_404(id)
    user.status = Status.BLOCKED
    db.session.commit()
    flash(f'{user.name} blocked.', 'warning')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:id>/change-role', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN)
def change_role(id):
    user = User.query.get_or_404(id)
    new_role = request.form.get('role')
    if new_role in Roles.ALL:
        user.role = new_role
        db.session.commit()
        flash(f'{user.name} role changed to {new_role}.', 'success')
    return redirect(url_for('admin.users'))


# ── Student Approvals ────────────────────────────────────────────────────────
@admin_bp.route('/students/approve/<int:id>', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def approve_student(id):
    student = Student.query.get_or_404(id)

    # Scope check
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        cls = Class.query.get(student.class_id)
        if not cls or cls.department_id != dept_id:
            abort(403)
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = _ct_class()
        if not cls or student.class_id != cls.id:
            abort(403)

    action = request.form.get('action', 'approve')
    student.approval_status = ApprovalStatus.APPROVED if action == 'approve' else ApprovalStatus.REJECTED
    student.approved_by = current_user.id
    student.user.status = Status.ACTIVE if action == 'approve' else Status.BLOCKED
    db.session.commit()
    flash(f'Student {student.user.name} {student.approval_status}.', 'success')
    from app.utils.helpers import send_notification
    msg = '✅ Your account has been approved! You can now login.' if action == 'approve' else '❌ Your registration was rejected.'
    send_notification(student.user_id, msg, 'success' if action == 'approve' else 'danger')
    return redirect(request.referrer or url_for('dashboard.index'))


# ── Assign TG to Students (Bulk) ─────────────────────────────────────────────
@admin_bp.route('/students/bulk-assign-tg', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def bulk_assign_tg():
    student_ids_str = request.form.get('student_ids', '')
    tg_id = request.form.get('tg_id') or None
    if not student_ids_str:
        flash('No students selected.', 'warning')
        return redirect(request.referrer or url_for('admin.students'))

    student_ids = [int(s.strip()) for s in student_ids_str.split(',') if s.strip().isdigit()]
    if not student_ids:
        flash('Invalid students selected.', 'warning')
        return redirect(request.referrer or url_for('admin.students'))

    students = Student.query.filter(Student.id.in_(student_ids)).all()
    count = 0
    for student in students:
        # Scope check per student
        if current_user.role == Roles.HOD:
            dept_id = _hod_dept_id()
            cls = Class.query.get(student.class_id)
            if not cls or cls.department_id != dept_id:
                continue # Skip out-of-scope students
        elif current_user.role == Roles.CLASS_TEACHER:
            cls = _ct_class()
            if not cls or student.class_id != cls.id:
                continue

        student.tg_id = int(tg_id) if tg_id else None
        count += 1

    db.session.commit()
    flash(f'Teacher Guardian updated for {count} student(s).', 'success')
    return redirect(request.referrer or url_for('admin.students'))


# ── Departments ──────────────────────────────────────────────────────────────
@admin_bp.route('/departments')
@login_required
@role_required(Roles.SUPER_ADMIN)
def departments():
    depts    = Department.query.all()
    teachers = User.query.filter(User.role.in_([Roles.HOD, Roles.TEACHER, Roles.CLASS_TEACHER])).all()
    return render_template('admin/departments.html', departments=depts, teachers=teachers)


@admin_bp.route('/departments/create', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN)
def create_department():
    name   = request.form.get('name', '').strip()
    code   = request.form.get('code', '').strip()
    hod_id = request.form.get('hod_id') or None
    if name:
        dept = Department(name=name, code=code, hod_id=hod_id)
        db.session.add(dept)
        if hod_id:
            user = User.query.get(hod_id)
            if user and user.role != Roles.SUPER_ADMIN:
                user.role = Roles.HOD
        db.session.commit()
        flash(f'Department "{name}" created.', 'success')
    return redirect(url_for('admin.departments'))


@admin_bp.route('/departments/edit/<int:id>', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN)
def edit_department(id):
    dept = Department.query.get_or_404(id)
    dept.name = request.form.get('name', dept.name).strip()
    dept.code = request.form.get('code', dept.code).strip()
    new_hod_id = request.form.get('hod_id') or None

    if str(new_hod_id) != str(dept.hod_id):
        dept.hod_id = new_hod_id
        if new_hod_id:
            user = User.query.get(new_hod_id)
            if user and user.role != Roles.SUPER_ADMIN:
                user.role = Roles.HOD

    db.session.commit()
    flash(f'Department "{dept.name}" updated.', 'success')
    return redirect(url_for('admin.departments'))


# ── Classes ──────────────────────────────────────────────────────────────────
@admin_bp.route('/classes')
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD)
def classes():
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        classes_list = Class.query.filter_by(department_id=dept_id).all() if dept_id else []
        departments  = Department.query.filter_by(id=dept_id).all() if dept_id else []
    else:
        classes_list = Class.query.all()
        departments  = Department.query.all()

    # Teachers eligible to be CT (includes TEACHER role so HOD can promote them)
    teachers = User.query.filter(User.role.in_(
        [Roles.CLASS_TEACHER, Roles.TEACHER, Roles.HOD]
    )).all()
    return render_template('admin/classes.html', classes=classes_list,
                           departments=departments, teachers=teachers)


@admin_bp.route('/classes/create', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD)
def create_class():
    name    = request.form.get('name', '').strip()
    year    = request.form.get('year', 1)
    section = request.form.get('section', 'A')
    dept_id = request.form.get('department_id')
    ct_id   = request.form.get('class_teacher_id') or None

    # HOD can only create classes in their own department
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()

    if name:
        cls = Class(name=name, year=year, section=section,
                    department_id=dept_id, class_teacher_id=ct_id)
        db.session.add(cls)
        # Promote Class Teacher role
        if ct_id:
            ct_user = User.query.get(ct_id)
            if ct_user and ct_user.role == Roles.TEACHER:
                ct_user.role = Roles.CLASS_TEACHER
        db.session.commit()
        flash(f'Class "{name}" created.', 'success')
    return redirect(url_for('admin.classes'))


@admin_bp.route('/classes/edit/<int:id>', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD)
def edit_class(id):
    cls = Class.query.get_or_404(id)

    # HOD can only edit classes in their own department
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        if cls.department_id != dept_id:
            abort(403)

    cls.name    = request.form.get('name', cls.name).strip()
    cls.year    = request.form.get('year', cls.year)
    cls.section = request.form.get('section', cls.section)
    new_ct_id   = request.form.get('class_teacher_id') or None
    cls.class_teacher_id = new_ct_id

    # Promote new Class Teacher
    if new_ct_id:
        ct_user = User.query.get(new_ct_id)
        if ct_user and ct_user.role == Roles.TEACHER:
            ct_user.role = Roles.CLASS_TEACHER

    db.session.commit()
    flash(f'Class "{cls.name}" updated.', 'success')
    return redirect(url_for('admin.classes'))


# ── Subjects ──────────────────────────────────────────────────────────────────
@admin_bp.route('/subjects')
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def subjects():
    if current_user.role == Roles.HOD:
        dept_id  = _hod_dept_id()
        class_ids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()] if dept_id else []
        subjects_list = Subject.query.filter(Subject.class_id.in_(class_ids)).all()
        classes_list  = Class.query.filter_by(department_id=dept_id).all() if dept_id else []
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = _ct_class()
        subjects_list = Subject.query.filter_by(class_id=cls.id).all() if cls else []
        classes_list  = [cls] if cls else []
    else:
        subjects_list = Subject.query.all()
        classes_list  = Class.query.all()

    teachers = User.query.filter(User.role.in_(
        [Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD]
    )).all()
    return render_template('admin/subjects.html', subjects=subjects_list,
                           classes=classes_list, teachers=teachers)


@admin_bp.route('/subjects/create', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def create_subject():
    name       = request.form.get('name', '').strip()
    code       = request.form.get('code', '').strip()
    class_id   = request.form.get('class_id')
    teacher_id = request.form.get('teacher_id') or None
    credits    = int(request.form.get('credits', 3))

    # Scope check
    if current_user.role == Roles.CLASS_TEACHER:
        cls = _ct_class()
        if not cls or str(cls.id) != str(class_id):
            abort(403)
    elif current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        cls = Class.query.get(class_id)
        if not cls or cls.department_id != dept_id:
            abort(403)

    if name:
        sub = Subject(name=name, code=code, class_id=class_id,
                      teacher_id=teacher_id, credits=credits)
        db.session.add(sub)
        db.session.commit()
        flash(f'Subject "{name}" created.', 'success')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subjects/edit/<int:id>', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def edit_subject(id):
    sub = Subject.query.get_or_404(id)

    # Scope check
    if current_user.role == Roles.CLASS_TEACHER:
        cls = _ct_class()
        if not cls or sub.class_id != cls.id:
            abort(403)
    elif current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        cls = Class.query.get(sub.class_id)
        if not cls or cls.department_id != dept_id:
            abort(403)

    sub.name       = request.form.get('name', sub.name).strip()
    sub.code       = request.form.get('code', sub.code).strip()
    sub.class_id   = request.form.get('class_id', sub.class_id)
    sub.teacher_id = request.form.get('teacher_id') or None
    sub.credits    = int(request.form.get('credits', sub.credits))
    db.session.commit()
    flash(f'Subject "{sub.name}" updated.', 'success')
    return redirect(url_for('admin.subjects'))


# ── Audit Logs ───────────────────────────────────────────────────────────────
@admin_bp.route('/audit-logs')
@login_required
@role_required(Roles.SUPER_ADMIN)
def audit_logs():
    from app.models import AuditLog
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('admin/audit_logs.html', logs=logs)


# ── Student List ──────────────────────────────────────────────────────────────
@admin_bp.route('/students')
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER, Roles.TEACHER)
def students():
    search        = request.args.get('search', '').strip()
    category      = request.args.get('category', '')
    gender        = request.args.get('gender', '')
    blood         = request.args.get('blood', '')
    dept_filter   = request.args.get('department_id', type=int)
    class_filter  = request.args.get('class_id', type=int)
    page          = request.args.get('page', 1, type=int)

    query = Student.query.join(User, Student.user_id == User.id)

    available_depts = []
    available_classes = []

    # ── Row-Level Access Controls & Dropdown Data ──────────────────────────
    if current_user.role == Roles.SUPER_ADMIN:
        available_depts = Department.query.all()
        if dept_filter:
            available_classes = Class.query.filter_by(department_id=dept_filter).all()
            query = query.join(Class, Student.class_id == Class.id).filter(Class.department_id == dept_filter)
            if class_filter:
                query = query.filter(Student.class_id == class_filter)
        elif class_filter:
            available_classes = Class.query.all()
            query = query.filter(Student.class_id == class_filter)
        else:
            available_classes = Class.query.all()

    elif current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        dept_filter = dept_id  # Force lock dept
        available_classes = Class.query.filter_by(department_id=dept_id).all()
        if dept_id:
            query = query.join(Class, Student.class_id == Class.id).filter(Class.department_id == dept_id)
            if class_filter:
                query = query.filter(Student.class_id == class_filter)
        else:
            query = query.filter(Student.id == 0)

    elif current_user.role == Roles.CLASS_TEACHER:
        cls = _ct_class()
        if cls:
            class_filter = cls.id # Force lock class
            query = query.filter(Student.class_id == cls.id)
        else:
            query = query.filter(Student.id == 0)

    elif current_user.role == Roles.TEACHER:
        # TG sees only their assigned students
        tg_ids = [s.id for s in Student.query.filter_by(tg_id=current_user.id).all()]
        if tg_ids:
            query = query.filter(Student.id.in_(tg_ids))
        else:
            query = query.filter(Student.id == 0)

    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                Student.prn.ilike(f'%{search}%'),
                Student.roll_no.ilike(f'%{search}%'),
            )
        )
    if category:
        query = query.filter(Student.category == category)
    if gender:
        query = query.filter(Student.gender == gender)
    if blood:
        query = query.filter(Student.blood_group == blood)

    pagination = query.order_by(Student.roll_no).paginate(page=page, per_page=20, error_out=False)
    students_list = pagination.items

    total     = query.count()
    male_ct   = query.filter(Student.gender == 'M').count()
    female_ct = query.filter(Student.gender == 'F').count()

    categories   = db.session.query(Student.category).filter(
        Student.category != None).distinct().order_by(Student.category).all()
    blood_groups = db.session.query(Student.blood_group).filter(
        Student.blood_group != None).distinct().order_by(Student.blood_group).all()

    # Teachers for TG assignment dropdown
    teachers = User.query.filter(
        User.role.in_([Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD])
    ).all()

    return render_template('admin/students.html',
        students=students_list, pagination=pagination,
        search=search, category=category, gender=gender, blood=blood,
        dept_filter=dept_filter, class_filter=class_filter,
        available_depts=available_depts, available_classes=available_classes,
        total=total, male_ct=male_ct, female_ct=female_ct,
        categories=[c[0] for c in categories],
        blood_groups=[b[0] for b in blood_groups],
        teachers=teachers,
    )


@admin_bp.route('/students/<int:id>')
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER, Roles.TEACHER)
def student_detail(id):
    student = Student.query.get_or_404(id)

    # Scope check
    if current_user.role == Roles.HOD:
        dept_id = _hod_dept_id()
        cls = Class.query.get(student.class_id)
        if not cls or cls.department_id != dept_id:
            abort(403)
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = _ct_class()
        if not cls or student.class_id != cls.id:
            abort(403)
    elif current_user.role == Roles.TEACHER:
        if student.tg_id != current_user.id:
            abort(403)

    teachers = User.query.filter(
        User.role.in_([Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD])
    ).all()
    return render_template('admin/student_detail.html', student=student, teachers=teachers)
