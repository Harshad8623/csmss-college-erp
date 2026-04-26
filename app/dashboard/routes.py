from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import (
    User, Student, Teacher, Department, Class, Subject,
    Attendance, Marks, Grievance, Certificate, Notice,
    Assignment, Notification, Roles, Status, ApprovalStatus, AbsenteeReason
)
from app.extensions import db
from sqlalchemy import func
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('landing.html')

@dashboard_bp.route('/dashboard')
@login_required
def index():
    if current_user.status != Status.ACTIVE:
        return redirect(url_for('auth.pending'))

    role = current_user.role
    if role == Roles.SUPER_ADMIN:
        return super_admin_dashboard()
    elif role == Roles.HOD:
        return hod_dashboard()
    elif role == Roles.CLASS_TEACHER:
        return class_teacher_dashboard()
    elif role == Roles.TEACHER:
        return teacher_dashboard()
    elif role in [Roles.CR]:
        return cr_dashboard()
    else:
        return student_dashboard()

def super_admin_dashboard():
    stats = {
        'total_students': Student.query.count(),
        'total_teachers': Teacher.query.count(),
        'total_departments': Department.query.count(),
        'total_classes': Class.query.count(),
        'pending_users': User.query.filter_by(status=Status.PENDING).count(),
        'pending_grievances': Grievance.query.filter_by(status=ApprovalStatus.PENDING).count(),
        'pending_certs': Certificate.query.filter_by(status=ApprovalStatus.PENDING).count(),
    }
    # Attendance today
    today = date.today()
    total_att = Attendance.query.filter_by(date=today).count()
    present_att = Attendance.query.filter_by(date=today, status=True).count()
    stats['today_attendance'] = f"{present_att}/{total_att}" if total_att else "0/0"

    departments = Department.query.all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_grievances = Grievance.query.order_by(Grievance.created_at.desc()).limit(5).all()
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(5).all()

    return render_template('dashboard/super_admin.html',
        stats=stats, departments=departments,
        recent_users=recent_users, recent_grievances=recent_grievances,
        notices=notices)

def hod_dashboard():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    dept_id = teacher.department_id if teacher else None
    dept = Department.query.get(dept_id) if dept_id else None

    classes = Class.query.filter_by(department_id=dept_id).all() if dept_id else []
    class_ids = [c.id for c in classes]
    student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]

    stats = {
        'dept_students': len(student_ids),
        'dept_classes': len(classes),
        'dept_teachers': Teacher.query.filter_by(department_id=dept_id).count() if dept_id else 0,
        'pending_approvals': Student.query.filter(
            Student.class_id.in_(class_ids),
            Student.approval_status == ApprovalStatus.PENDING
        ).count() if class_ids else 0,
    }

    pending_students = Student.query.filter(
        Student.class_id.in_(class_ids),
        Student.approval_status == ApprovalStatus.PENDING
    ).all() if class_ids else []

    return render_template('dashboard/hod.html',
        stats=stats, dept=dept, classes=classes, pending_students=pending_students)

def class_teacher_dashboard():
    class_ = Class.query.filter_by(class_teacher_id=current_user.id).first()
    students = Student.query.filter_by(class_id=class_.id).all() if class_ else []
    student_ids = [s.id for s in students]

    pending = [s for s in students if s.approval_status == ApprovalStatus.PENDING]

    # Defaulters
    defaulters = []
    for s in students:
        pct = s.attendance_percentage()
        if pct < 75:
            defaulters.append({'student': s, 'pct': pct})

    stats = {
        'total_students': len(students),
        'pending_approvals': len(pending),
        'defaulters': len(defaulters),
        'active_grievances': Grievance.query.filter(
            Grievance.student_id.in_(student_ids),
            Grievance.status == ApprovalStatus.PENDING
        ).count() if student_ids else 0,
    }

    return render_template('dashboard/class_teacher.html',
        stats=stats, class_=class_, students=students,
        pending=pending, defaulters=defaulters[:5])

def teacher_dashboard():
    # Get subjects taught by this teacher
    subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
    today = date.today()

    tg_students_count = Student.query.filter_by(tg_id=current_user.id).count()

    stats = {
        'total_subjects': len(subjects),
        'total_students': sum(s.class_.students.filter_by(
            approval_status=ApprovalStatus.APPROVED).count() for s in subjects if s.class_),
        'pending_assignments': Assignment.query.filter_by(created_by=current_user.id).count(),
        'today_marked': Attendance.query.filter_by(
            marked_by=current_user.id, date=today).count(),
        'tg_students_count': tg_students_count,
    }

    recent_submissions = []
    for sub in subjects:
        for asgn in sub.assignments:
            recent_submissions.extend(asgn.submissions.all())

    return render_template('dashboard/teacher.html',
        stats=stats, subjects=subjects, recent_submissions=recent_submissions[:10])

def student_dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student or student.approval_status != ApprovalStatus.APPROVED:
        return redirect(url_for('auth.pending'))

    # Attendance summary
    subjects = Subject.query.filter_by(class_id=student.class_id).all() if student.class_id else []
    attendance_data = []
    for sub in subjects:
        pct = student.attendance_percentage(sub.id)
        attendance_data.append({'subject': sub, 'percentage': pct})

    # Marks summary
    marks_data = Marks.query.filter_by(student_id=student.id)\
        .order_by(Marks.created_at.desc()).limit(10).all()

    overall_pct = student.attendance_percentage()
    stats = {
        'overall_attendance': overall_pct,
        'is_defaulter': overall_pct < 75,
        'total_grievances': student.grievances.count(),
        'pending_certs': student.certificates.filter_by(status=ApprovalStatus.PENDING).count(),
        'pending_assignments': 0,
    }

    notices = Notice.query.filter(
        (Notice.target_role == Roles.STUDENT) | (Notice.target_role == None)
    ).order_by(Notice.created_at.desc()).limit(5).all()

    # Pending absentee reasons
    # Get all attendance records for this student
    student_att_ids = [a.id for a in student.attendance.all()]
    pending_reasons = []
    if student_att_ids:
        pending_reasons = AbsenteeReason.query.filter(
            AbsenteeReason.attendance_id.in_(student_att_ids),
            AbsenteeReason.status == 'REQUESTED'
        ).all()

    return render_template('dashboard/student.html',
        student=student, stats=stats, attendance_data=attendance_data,
        marks_data=marks_data, notices=notices, pending_reasons=pending_reasons)

@dashboard_bp.route('/submit-absentee-reason/<int:reason_id>', methods=['POST'])
@login_required
def submit_absentee_reason(reason_id):
    from flask import request, flash
    reason = AbsenteeReason.query.get_or_404(reason_id)
    if reason.attendance.student.user_id != current_user.id:
        return redirect(url_for('dashboard.index'))
    
    reason_text = request.form.get('reason_text')
    if reason_text:
        reason.reason_text = reason_text
        reason.status = 'SUBMITTED'
        db.session.commit()
        flash('Absentee reason submitted successfully.', 'success')
    return redirect(url_for('dashboard.index'))


def cr_dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(10).all()
    class_ = Class.query.get(student.class_id) if student else None
    students_in_class = Student.query.filter_by(class_id=student.class_id).all() if student else []

    return render_template('dashboard/cr.html',
        student=student, notices=notices, class_=class_,
        students=students_in_class)
