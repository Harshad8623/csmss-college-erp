from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import (
    Student, Teacher, Department, Class, Subject,
    Attendance, Marks, Grievance, User, Roles, ApprovalStatus, AbsenteeReason
)
from app.extensions import db
from sqlalchemy import func
from datetime import date, timedelta, datetime
from app.utils.helpers import get_dept_for_hod, get_class_for_ct, get_tg_student_ids

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@analytics_bp.route('/')
@login_required
def index():
    if current_user.role == Roles.STUDENT:
        return render_template('errors/403.html'), 403

    departments = []
    classes = []
    selected_dept_id = request.args.get('department_id', type=int)
    selected_class_id = request.args.get('class_id', type=int)
    
    # Default to today
    selected_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()

    # RBAC logic
    if current_user.role in [Roles.PRINCIPAL, Roles.ADMIN]:
        departments = Department.query.all()
        if selected_dept_id:
            classes = Class.query.filter_by(department_id=selected_dept_id).all()
    elif current_user.role == Roles.HOD:
        hod_dept_id = get_dept_for_hod(current_user.id)
        selected_dept_id = hod_dept_id
        if hod_dept_id:
            departments = [Department.query.get(hod_dept_id)]
            classes = Class.query.filter_by(department_id=hod_dept_id).all()
    elif current_user.role == Roles.CLASS_TEACHER:
        ct_class = get_class_for_ct(current_user.id)
        if ct_class:
            selected_class_id = ct_class.id
            selected_dept_id = ct_class.department_id
            departments = [Department.query.get(selected_dept_id)]
            classes = [ct_class]
    elif current_user.role == Roles.TEACHER:
        # TGs or regular teachers can only see their TG students or their subject classes (for simplicity, they can see analytics but maybe limited)
        pass 

    # Fetch Attendance for the selected date
    attendance_records = []
    if selected_class_id:
        student_ids = [s.id for s in Student.query.filter_by(class_id=selected_class_id).all()]
        attendance_records = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date == selected_date
        ).all()
    elif selected_dept_id:
        classes_in_dept = Class.query.filter_by(department_id=selected_dept_id).all()
        class_ids = [c.id for c in classes_in_dept]
        student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]
        attendance_records = Attendance.query.filter(
            Attendance.student_id.in_(student_ids),
            Attendance.date == selected_date
        ).all()

    # Separate present and absent
    present_students = []
    absent_students = []
    
    # We want to group by student or just show the records
    # If a student was absent for *any* subject that day, they might be marked absent.
    # Usually, daily attendance is tracked per subject. Let's group by student_id to show if they were present/absent for the day.
    student_daily_status = {}
    for a in attendance_records:
        if a.student_id not in student_daily_status:
            student_daily_status[a.student_id] = {'student': a.student, 'present_count': 0, 'absent_count': 0, 'records': []}
        student_daily_status[a.student_id]['records'].append(a)
        if a.status:
            student_daily_status[a.student_id]['present_count'] += 1
        else:
            student_daily_status[a.student_id]['absent_count'] += 1

    for s_id, data in student_daily_status.items():
        if data['absent_count'] > 0:
            absent_students.append(data)
        else:
            present_students.append(data)

    return render_template('analytics/index.html',
                           departments=departments,
                           classes=classes,
                           selected_dept_id=selected_dept_id,
                           selected_class_id=selected_class_id,
                           selected_date=selected_date,
                           present_students=present_students,
                           absent_students=absent_students)

@analytics_bp.route('/request-reason/<int:attendance_id>', methods=['POST'])
@login_required
def request_reason(attendance_id):
    if current_user.role != Roles.TEACHER:
        # Assuming Teacher here is the Teacher Guardian
        pass # In a real app we might restrict this further
    
    attendance = Attendance.query.get_or_404(attendance_id)
    
    # Check if a reason already exists
    if attendance.absentee_reason:
        return jsonify({'status': 'error', 'message': 'Reason already requested.'}), 400

    new_reason = AbsenteeReason(
        attendance_id=attendance.id,
        requested_by=current_user.id,
        status='REQUESTED'
    )
    db.session.add(new_reason)
    db.session.commit()
    
    from flask import flash, redirect, url_for
    flash('Absentee reason requested successfully.', 'success')
    return redirect(request.referrer or url_for('analytics.index'))

# ── API endpoints for Chart.js ──────────────────────────────────────────────

@analytics_bp.route('/api/attendance-overview')
@login_required
def attendance_overview():
    """Department-wise average attendance."""
    departments = Department.query.all()
    labels, data = [], []
    for dept in departments:
        classes = Class.query.filter_by(department_id=dept.id).all()
        class_ids = [c.id for c in classes]
        student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()]
        if not student_ids:
            labels.append(dept.name)
            data.append(0)
            continue
        total = Attendance.query.filter(Attendance.student_id.in_(student_ids)).count()
        present = Attendance.query.filter(Attendance.student_id.in_(student_ids), Attendance.status==True).count()
        pct = round((present / total) * 100, 2) if total else 0
        labels.append(dept.name)
        data.append(pct)
    return jsonify({'labels': labels, 'data': data})

@analytics_bp.route('/api/defaulters')
@login_required
def defaulters():
    """Count defaulters per class."""
    classes = Class.query.all()
    labels, counts = [], []
    for c in classes:
        students = Student.query.filter_by(class_id=c.id, approval_status=ApprovalStatus.APPROVED).all()
        d_count = sum(1 for s in students if s.attendance_percentage() < 75)
        labels.append(c.name)
        counts.append(d_count)
    return jsonify({'labels': labels, 'data': counts})

@analytics_bp.route('/api/marks-distribution/<int:subject_id>')
@login_required
def marks_distribution(subject_id):
    marks = Marks.query.filter_by(subject_id=subject_id).all()
    ranges = {'0-40': 0, '40-60': 0, '60-75': 0, '75-90': 0, '90-100': 0}
    for m in marks:
        p = m.percentage
        if p < 40: ranges['0-40'] += 1
        elif p < 60: ranges['40-60'] += 1
        elif p < 75: ranges['60-75'] += 1
        elif p < 90: ranges['75-90'] += 1
        else: ranges['90-100'] += 1
    return jsonify({'labels': list(ranges.keys()), 'data': list(ranges.values())})

@analytics_bp.route('/api/attendance-trend')
@login_required
def attendance_trend():
    """Last 30 days attendance trend."""
    today = date.today()
    labels, present_data, absent_data = [], [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        total = Attendance.query.filter_by(date=d).count()
        present = Attendance.query.filter_by(date=d, status=True).count()
        absent = total - present
        labels.append(d.strftime('%d %b'))
        present_data.append(present)
        absent_data.append(absent)
    return jsonify({'labels': labels, 'present': present_data, 'absent': absent_data})

@analytics_bp.route('/api/summary')
@login_required
def summary():
    """Quick summary stats."""
    total_students = Student.query.filter_by(approval_status=ApprovalStatus.APPROVED).count()
    total_teachers = Teacher.query.count()
    pending_grievances = Grievance.query.filter_by(status=ApprovalStatus.PENDING).count()
    total_departments = Department.query.count()
    return jsonify({
        'students': total_students,
        'teachers': total_teachers,
        'grievances': pending_grievances,
        'departments': total_departments,
    })
