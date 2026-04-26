from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    Attendance, Student, Subject, Class, User, Roles, ApprovalStatus
)
from app.utils.decorators import role_required
from app.utils.helpers import (
    send_notification, calculate_attendance_percentage, classes_needed_for_75,
    get_dept_for_hod, get_class_for_ct, get_tg_student_ids
)
from datetime import date

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


def _scoped_subjects():
    """Return subjects list scoped by current user's role."""
    role = current_user.role
    if role == Roles.SUPER_ADMIN:
        return Subject.query.all()
    elif role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        if dept_id:
            class_ids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
            return Subject.query.filter(Subject.class_id.in_(class_ids)).all()
        return []
    elif role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        return Subject.query.filter_by(class_id=cls.id).all() if cls else []
    else:
        # Regular teacher — only their assigned subjects
        return Subject.query.filter_by(teacher_id=current_user.id).all()


@attendance_bp.route('/')
@login_required
def index():
    if current_user.role in [Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN]:
        subjects = _scoped_subjects()
        subject_ids = [s.id for s in subjects]
        recent_sessions = []
        if subject_ids:
            sessions_query = db.session.query(Attendance.date, Attendance.subject_id).filter(
                Attendance.subject_id.in_(subject_ids)
            ).distinct().order_by(Attendance.date.desc()).limit(30).all()

            for session_date, sub_id in sessions_query:
                sub = Subject.query.get(sub_id)
                recent_sessions.append({'date': session_date, 'subject': sub})

        return render_template('attendance/teacher_view.html',
                               subjects=subjects, recent_sessions=recent_sessions)
    else:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            flash('Student profile not found.', 'danger')
            return redirect(url_for('dashboard.index'))
        return _student_attendance(student)


def _student_attendance(student):
    subjects = Subject.query.filter_by(class_id=student.class_id).all()
    attendance_summary = []
    for sub in subjects:
        records = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id)\
                    .order_by(Attendance.date.desc()).all()
        total   = len(records)
        present = sum(1 for r in records if r.status)
        pct     = round((present / total) * 100, 2) if total else 0
        needed  = classes_needed_for_75(present, total)
        attendance_summary.append({
            'subject':      sub,
            'total':        total,
            'present':      present,
            'absent':       total - present,
            'percentage':   pct,
            'is_defaulter': pct < 75,
            'classes_needed': needed,
            'records':      records[:30]
        })
    overall = student.attendance_percentage()
    return render_template('attendance/student_view.html',
        student=student, attendance_summary=attendance_summary, overall=overall)


@attendance_bp.route('/mark', methods=['GET', 'POST'])
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def mark():
    subjects = _scoped_subjects()

    selected_subject = None
    students = []
    selected_date = date.today()
    existing = {}

    subject_id = request.args.get('subject_id') or request.form.get('subject_id')
    att_date   = request.args.get('date') or request.form.get('date', str(date.today()))

    if subject_id:
        selected_subject = Subject.query.get(subject_id)

        # Verify this subject is in scope
        if selected_subject and selected_subject not in subjects:
            abort(403)

        if selected_subject:
            students = Student.query.filter_by(
                class_id=selected_subject.class_id,
                approval_status=ApprovalStatus.APPROVED
            ).all()
            selected_date = date.fromisoformat(att_date)
            existing_records = Attendance.query.filter_by(
                subject_id=subject_id, date=selected_date
            ).all()
            existing = {r.student_id: r.status for r in existing_records}

    if request.method == 'POST' and selected_subject:
        selected_date = date.fromisoformat(request.form.get('date', str(date.today())))
        present_ids = [int(x) for x in request.form.getlist('present')]

        for student in students:
            is_present = student.id in present_ids
            existing_record = Attendance.query.filter_by(
                student_id=student.id, subject_id=selected_subject.id, date=selected_date
            ).first()
            if existing_record:
                existing_record.status    = is_present
                existing_record.marked_by = current_user.id
            else:
                db.session.add(Attendance(
                    student_id=student.id,
                    subject_id=selected_subject.id,
                    date=selected_date,
                    status=is_present,
                    marked_by=current_user.id
                ))

        db.session.commit()

        # Notify defaulters
        for student in students:
            pct = calculate_attendance_percentage(student.id, selected_subject.id)
            if pct < 75:
                send_notification(
                    student.user_id,
                    f'⚠️ Your attendance in {selected_subject.name} is {pct}% — below 75%!',
                    'warning',
                    url_for('attendance.index')
                )

        flash(f'Attendance saved — {selected_date.strftime("%d %b %Y")} · {selected_subject.name}', 'success')
        return redirect(url_for('attendance.mark',
            subject_id=selected_subject.id, date=str(selected_date)))

    return render_template('attendance/mark.html',
        subjects=subjects, selected_subject=selected_subject,
        students=students, selected_date=selected_date,
        existing=existing, att_date=att_date)


@attendance_bp.route('/report/<int:class_id>')
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def class_report(class_id):
    class_ = Class.query.get_or_404(class_id)

    # Scope check
    if current_user.role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        if class_.department_id != dept_id:
            abort(403)
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        if not cls or cls.id != class_id:
            abort(403)

    students = Student.query.filter_by(class_id=class_id, approval_status=ApprovalStatus.APPROVED).all()
    subjects = Subject.query.filter_by(class_id=class_id).all()

    report = []
    for student in students:
        row = {'student': student, 'subjects': {}}
        overall_total = overall_present = 0
        for sub in subjects:
            total   = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id).count()
            present = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id, status=True).count()
            pct     = round((present / total) * 100, 2) if total else 0
            row['subjects'][sub.id] = {'total': total, 'present': present, 'pct': pct}
            overall_total   += total
            overall_present += present
        row['overall_pct']  = round((overall_present / overall_total) * 100, 2) if overall_total else 0
        row['is_defaulter'] = row['overall_pct'] < 75
        report.append(row)

    return render_template('attendance/class_report.html',
        class_=class_, students=students, subjects=subjects, report=report)


@attendance_bp.route('/api/chart/<int:student_id>')
@login_required
def chart_data(student_id):
    student  = Student.query.get_or_404(student_id)
    subjects = Subject.query.filter_by(class_id=student.class_id).all()
    labels, data = [], []
    for sub in subjects:
        pct = calculate_attendance_percentage(student_id, sub.id)
        labels.append(sub.name)
        data.append(pct)
    return jsonify({'labels': labels, 'data': data})
