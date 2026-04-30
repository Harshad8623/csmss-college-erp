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

        # Bulk load existing records
        existing_records = Attendance.query.filter_by(
            subject_id=selected_subject.id, date=selected_date
        ).all()
        existing_dict = {r.student_id: r for r in existing_records}

        for student in students:
            is_present = student.id in present_ids
            if student.id in existing_dict:
                record = existing_dict[student.id]
                record.status = is_present
                record.marked_by = current_user.id
            else:
                db.session.add(Attendance(
                    student_id=student.id,
                    subject_id=selected_subject.id,
                    date=selected_date,
                    status=is_present,
                    marked_by=current_user.id
                ))

        db.session.commit()

        # Bulk notification for defaulters
        student_ids = [s.id for s in students]
        if student_ids:
            stats = db.session.query(
                Attendance.student_id,
                db.func.count(Attendance.id).label('total'),
                db.func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
            ).filter(
                Attendance.subject_id == selected_subject.id,
                Attendance.student_id.in_(student_ids)
            ).group_by(Attendance.student_id).all()
            
            stats_dict = {r.student_id: {'total': r.total, 'present': r.present or 0} for r in stats}
            
            from app.models import Notification
            notifs = []
            for student in students:
                st = stats_dict.get(student.id)
                if st and st['total'] > 0:
                    pct = round((st['present'] / st['total']) * 100, 2)
                    if pct < 75:
                        notifs.append(Notification(
                            user_id=student.user_id,
                            message=f'⚠️ Your attendance in {selected_subject.name} is {pct}% — below 75%!',
                            type='warning',
                            link=url_for('attendance.index')
                        ))
            
            if notifs:
                db.session.bulk_save_objects(notifs)
                db.session.commit()

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

    student_ids = [s.id for s in students]
    subject_ids = [s.id for s in subjects]
    
    import collections
    stats_dict = collections.defaultdict(dict)
    if student_ids and subject_ids:
        stats = db.session.query(
            Attendance.student_id,
            Attendance.subject_id,
            db.func.count(Attendance.id).label('total'),
            db.func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(
            Attendance.student_id.in_(student_ids),
            Attendance.subject_id.in_(subject_ids)
        ).group_by(Attendance.student_id, Attendance.subject_id).all()
        
        for r in stats:
            stats_dict[r.student_id][r.subject_id] = {'total': r.total, 'present': r.present or 0}

    report = []
    for student in students:
        row = {'student': student, 'subjects': {}}
        overall_total = overall_present = 0
        for sub in subjects:
            st = stats_dict[student.id].get(sub.id, {'total': 0, 'present': 0})
            total = st['total']
            present = st['present']
            pct = round((present / total) * 100, 2) if total else 0
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


# ── Class Teacher: Full Date-wise Attendance View ────────────────────────────
@attendance_bp.route('/ct-view')
@login_required
@role_required(Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def ct_view():
    """Date-wise attendance view across all subjects for the class teacher's class."""
    from app.utils.helpers import get_class_for_ct, get_dept_for_hod

    # Resolve which class to show
    if current_user.role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        if not cls:
            flash('You are not assigned as a Class Teacher for any class.', 'warning')
            return redirect(url_for('attendance.index'))
    elif current_user.role == Roles.HOD:
        # HOD picks via query param, defaults to first class in dept
        dept_id = get_dept_for_hod(current_user.id)
        class_id_param = request.args.get('class_id', type=int)
        if class_id_param:
            cls = Class.query.get_or_404(class_id_param)
            if cls.department_id != dept_id:
                abort(403)
        else:
            cls = Class.query.filter_by(department_id=dept_id).first()
            if not cls:
                flash('No classes found in your department.', 'warning')
                return redirect(url_for('attendance.index'))
    else:  # SUPER_ADMIN
        class_id_param = request.args.get('class_id', type=int)
        if class_id_param:
            cls = Class.query.get_or_404(class_id_param)
        else:
            cls = Class.query.first()
            if not cls:
                flash('No classes found.', 'warning')
                return redirect(url_for('attendance.index'))

    subjects = Subject.query.filter_by(class_id=cls.id).order_by(Subject.name).all()
    students_count = Student.query.filter_by(
        class_id=cls.id, approval_status=ApprovalStatus.APPROVED
    ).count()

    # Build per-subject date-wise session data
    subject_data = []
    for sub in subjects:
        # All distinct dates this subject has attendance records
        sessions_raw = db.session.query(
            Attendance.date,
            db.func.count(Attendance.id).label('total'),
            db.func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(
            Attendance.subject_id == sub.id
        ).group_by(Attendance.date).order_by(Attendance.date.desc()).all()

        sessions = []
        for row in sessions_raw:
            absent = row.total - (row.present or 0)
            pct = round(((row.present or 0) / row.total) * 100) if row.total else 0
            sessions.append({
                'date': row.date,
                'total': row.total,
                'present': row.present or 0,
                'absent': absent,
                'pct': pct,
            })

        # Overall stats for this subject
        total_lectures = len(sessions)
        if sessions:
            all_total   = sum(s['total'] for s in sessions)
            all_present = sum(s['present'] for s in sessions)
            avg_pct = round((all_present / all_total) * 100) if all_total else 0
        else:
            avg_pct = 0

        subject_data.append({
            'subject': sub,
            'sessions': sessions,
            'total_lectures': total_lectures,
            'avg_pct': avg_pct,
            'teacher': User.query.get(sub.teacher_id) if sub.teacher_id else None,
        })

    # All classes (for HOD/SUPER_ADMIN switcher)
    if current_user.role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        all_classes = Class.query.filter_by(department_id=dept_id).all()
    elif current_user.role == Roles.SUPER_ADMIN:
        all_classes = Class.query.all()
    else:
        all_classes = [cls]

    return render_template('attendance/ct_attendance.html',
        cls=cls,
        subject_data=subject_data,
        students_count=students_count,
        all_classes=all_classes,
    )

