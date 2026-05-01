from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import (
    User, Student, Teacher, Department, Class, Subject,
    Attendance, Marks, Grievance, Certificate, Notice,
    Assignment, Notification, Roles, Status, ApprovalStatus, AbsenteeReason,
    ExamType, EventRecord, EventSession
)
from app.extensions import db
from sqlalchemy import func
from datetime import date, timedelta, datetime

dashboard_bp = Blueprint('dashboard', __name__)

def get_bulk_attendance_percentages(student_ids, class_id):
    if not student_ids:
        return {}
    
    # Theory
    theory_stats = db.session.query(
        Attendance.student_id,
        db.func.count(Attendance.id).label('total'),
        db.func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(student_ids)).group_by(Attendance.student_id).all()
    
    # Events
    event_stats = db.session.query(
        EventRecord.student_id,
        db.func.count(EventRecord.id).label('total'),
        db.func.sum(db.case((EventRecord.status == True, 1), else_=0)).label('present')
    ).join(EventSession).filter(
        EventRecord.student_id.in_(student_ids),
        EventSession.class_id == class_id
    ).group_by(EventRecord.student_id).all()
    
    # Combine
    results = {sid: {'total': 0, 'present': 0} for sid in student_ids}
    for row in theory_stats:
        results[row.student_id]['total'] += row.total
        results[row.student_id]['present'] += (row.present or 0)
    for row in event_stats:
        results[row.student_id]['total'] += row.total
        results[row.student_id]['present'] += (row.present or 0)
        
    percentages = {}
    for sid, data in results.items():
        if data['total'] == 0:
            percentages[sid] = 0
        else:
            percentages[sid] = round((data['present'] / data['total']) * 100, 2)
            
    return percentages

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
        'pending_grievances': Grievance.query.filter(
            Grievance.status.in_(['pending', 'escalated'])
        ).count(),
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
    if not class_:
        return render_template('dashboard/class_teacher.html',
            stats={'total_students': 0, 'pending_approvals': 0, 'defaulters': 0, 'active_grievances': 0},
            class_=None, students=[], pending=[], defaulters=[])

    students = Student.query.filter_by(class_id=class_.id).all()
    student_ids = [s.id for s in students]

    pending = [s for s in students if s.approval_status == ApprovalStatus.PENDING]

    # Bulk defaulter calculation — avoids N+1 query per student
    if student_ids:
        att_stats = db.session.query(
            Attendance.student_id,
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(Attendance.student_id.in_(student_ids)).group_by(Attendance.student_id).all()
        pct_map = {
            r.student_id: round((r.present or 0) / r.total * 100, 1) if r.total > 0 else 0
            for r in att_stats
        }
    else:
        pct_map = {}

    defaulters = [
        {'student': s, 'pct': pct_map.get(s.id, 0)}
        for s in students if pct_map.get(s.id, 0) < 75
    ]

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
    subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
    today = date.today()
    tg_students_count = Student.query.filter_by(tg_id=current_user.id).count()
    subject_ids = [s.id for s in subjects]

    stats = {
        'total_subjects': len(subjects),
        'total_students': sum(
            s.class_.students.filter_by(approval_status=ApprovalStatus.APPROVED).count()
            for s in subjects if s.class_
        ),
        'pending_assignments': Assignment.query.filter_by(created_by=current_user.id).count(),
        'today_marked': Attendance.query.filter_by(marked_by=current_user.id, date=today).count(),
        'tg_students_count': tg_students_count,
    }

    # Single query for recent submissions instead of nested N+1 loops
    from app.models import AssignmentSubmission
    asgn_ids = [a.id for s in subjects for a in s.assignments]
    recent_submissions = AssignmentSubmission.query.filter(
        AssignmentSubmission.assignment_id.in_(asgn_ids)
    ).order_by(AssignmentSubmission.submitted_at.desc()).limit(10).all() if asgn_ids else []

    return render_template('dashboard/teacher.html',
        stats=stats, subjects=subjects, recent_submissions=recent_submissions)

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

    # -------------------------------------------------------------
    # Leaderboards and Ranks Logic
    # -------------------------------------------------------------
    cr_users = User.query.join(Student, User.id == Student.user_id).filter(
        User.role == Roles.CR,
        Student.class_id == student.class_id
    ).all()

    class_students = Student.query.filter_by(
        class_id=student.class_id, 
        approval_status=ApprovalStatus.APPROVED
    ).all()
    class_student_ids = [s.id for s in class_students]
    total_class_students = len(class_students)

    # Attendance Leaderboard
    bulk_pcts = get_bulk_attendance_percentages(class_student_ids, student.class_id)
    attendance_leaderboard = []
    for s in class_students:
        attendance_leaderboard.append({'student': s, 'percentage': bulk_pcts.get(s.id, 0)})
    attendance_leaderboard.sort(key=lambda x: x['percentage'], reverse=True)
    
    attendance_rank = next((i + 1 for i, item in enumerate(attendance_leaderboard) if item['student'].id == student.id), None)

    # Marks Leaderboard (CT1, CT2, MSE)
    marks_aggs = db.session.query(
        Marks.student_id,
        Marks.exam_type,
        func.sum(Marks.marks).label('total_marks'),
        func.sum(Marks.max_marks).label('total_max_marks')
    ).filter(
        Marks.student_id.in_(class_student_ids),
        Marks.exam_type.in_([ExamType.CT1, ExamType.CT2, ExamType.MSE])
    ).group_by(Marks.student_id, Marks.exam_type).all()

    student_marks_map = {ExamType.CT1: {}, ExamType.CT2: {}, ExamType.MSE: {}}
    for agg in marks_aggs:
        sid, etype, t_marks, t_max = agg
        if t_max and t_max > 0:
            student_marks_map[etype][sid] = round((t_marks / t_max) * 100, 2)

    marks_leaderboards = {}
    marks_ranks = {}
    for etype in [ExamType.CT1, ExamType.CT2, ExamType.MSE]:
        lb = []
        for s in class_students:
            if s.id in student_marks_map[etype]:
                lb.append({'student': s, 'percentage': student_marks_map[etype][s.id]})
        lb.sort(key=lambda x: x['percentage'], reverse=True)
        marks_leaderboards[etype] = lb
        marks_ranks[etype] = next((i + 1 for i, item in enumerate(lb) if item['student'].id == student.id), None)

    return render_template('dashboard/student.html',
        student=student, stats=stats, attendance_data=attendance_data,
        marks_data=marks_data, notices=notices, pending_reasons=pending_reasons,
        cr_users=cr_users, total_class_students=total_class_students,
        attendance_leaderboard=attendance_leaderboard[:5], attendance_rank=attendance_rank,
        marks_leaderboards={k: v[:5] for k, v in marks_leaderboards.items()},
        marks_ranks=marks_ranks, ExamType=ExamType)

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
    if not student:
        from flask import flash, redirect, url_for
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.login'))

    class_id = student.class_id
    class_ = Class.query.get(class_id)
    students_in_class = Student.query.filter_by(class_id=class_id, approval_status=ApprovalStatus.APPROVED).all()
    
    # Strictly scoped notices
    notices = Notice.query.filter(
        (Notice.is_deleted == False),
        ((Notice.status == 'APPROVED') & ((Notice.target_role == None) | (Notice.target_role == Roles.STUDENT) | (Notice.target_role == Roles.CR)) & ((Notice.target_class_id == None) | (Notice.target_class_id == class_id))) |
        (Notice.posted_by == current_user.id)
    ).order_by(Notice.created_at.desc()).limit(10).all()

    # Analytics: Attendance
    student_ids = [s.id for s in students_in_class]
    bulk_pcts = get_bulk_attendance_percentages(student_ids, class_id)
    
    total_attendance = 0
    low_attendance_students = []
    
    for s in students_in_class:
        pct = bulk_pcts.get(s.id, 0)
        s.bulk_pct = pct # Cache it for the template
        total_attendance += pct
        if pct < 75:
            low_attendance_students.append({'student': s, 'pct': pct})
            
    avg_attendance = round(total_attendance / len(students_in_class), 1) if students_in_class else 0
    low_attendance_students.sort(key=lambda x: x['pct'])

    # Active Assignments
    from app.models import Subject, Assignment
    subject_ids = [s.id for s in Subject.query.filter_by(class_id=class_id).all()]
    active_assignments = Assignment.query.filter(
        Assignment.subject_id.in_(subject_ids),
        Assignment.deadline >= datetime.utcnow()
    ).count()

    # Today's Attendance Overview
    today_date = date.today()
    
    todays_attendance_query = Attendance.query.join(Subject).filter(
        Subject.class_id == class_id,
        Attendance.date == today_date
    ).all()
    
    todays_subject_attendance = {}
    for att in todays_attendance_query:
        if att.subject not in todays_subject_attendance:
            todays_subject_attendance[att.subject] = {'present': [], 'absent': []}
        if att.status:
            todays_subject_attendance[att.subject]['present'].append(att.student)
        else:
            todays_subject_attendance[att.subject]['absent'].append(att.student)
            
    todays_event_query = EventRecord.query.join(EventSession).filter(
        EventSession.class_id == class_id,
        EventSession.date == today_date
    ).all()
    
    todays_event_attendance = {}
    for rec in todays_event_query:
        if rec.session not in todays_event_attendance:
            todays_event_attendance[rec.session] = {'present': [], 'absent': []}
        if rec.status:
            todays_event_attendance[rec.session]['present'].append(rec.student)
        else:
            todays_event_attendance[rec.session]['absent'].append(rec.student)

    return render_template('dashboard/cr.html',
        student=student, notices=notices, class_=class_,
        students=students_in_class, avg_attendance=avg_attendance,
        low_attendance_students=low_attendance_students,
        active_assignments=active_assignments,
        todays_subject_attendance=todays_subject_attendance,
        todays_event_attendance=todays_event_attendance)
