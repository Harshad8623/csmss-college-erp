"""
/api/v1/dashboard — Role-aware dashboard data
Returns stats + quick-access data for the mobile home screen.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func, cast, Integer, and_
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    User, Student, Teacher, Subject, Attendance, Marks,
    Notice, Assignment, AssignmentSubmission, Notification,
    Timetable, Class, Department, Grievance,
    Roles, ApprovalStatus, Status, ExamType
)
from app.api.decorators import get_current_api_user

dashboard_api_bp = Blueprint('dashboard_api', __name__)


@dashboard_api_bp.route('/', methods=['GET'])
@jwt_required()
def dashboard():
    """
    Role-aware dashboard data
    ---
    tags: [Dashboard]
    security: [{Bearer: []}]
    responses:
      200:
        description: Dashboard stats and quick-access data (varies by role)
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    today = date.today()

    if user.role in (Roles.STUDENT, Roles.CR):
        return _student_dashboard(user, today)
    elif user.role == Roles.TEACHER:
        return _teacher_dashboard(user, today)
    elif user.role == Roles.CLASS_TEACHER:
        return _ct_dashboard(user, today)
    elif user.role == Roles.HOD:
        return _hod_dashboard(user, today)
    elif user.role == Roles.SUPER_ADMIN:
        return _admin_dashboard(user, today)
    else:
        return jsonify({'role': user.role, 'message': 'Dashboard not implemented for this role'}), 200


# ── Role dashboards ──────────────────────────────────────────────────────────

def _student_dashboard(user, today):
    sp = user.student_profile
    if not sp:
        return jsonify({'error': 'Student profile not found'}), 404

    # Overall attendance
    att_pct = sp.attendance_percentage()
    is_defaulter = att_pct < 75

    # Subject-wise attendance (top 5 for quick view)
    subjects = Subject.query.filter_by(class_id=sp.class_id).limit(5).all()
    subject_att = []
    for sub in subjects:
        pct = sp.attendance_percentage(subject_id=sub.id)
        subject_att.append({'subject': sub.name, 'code': sub.code, 'percentage': pct})

    # Unread notifications
    notif_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()

    # Today's timetable
    weekday = today.strftime('%A')
    timetable = Timetable.query.filter_by(
        class_id=sp.class_id, day=weekday
    ).order_by(Timetable.period_no).all()

    # Pending assignments
    assignments = Assignment.query.join(Subject).filter(
        Subject.class_id == sp.class_id,
        Assignment.deadline >= today
    ).order_by(Assignment.deadline).limit(3).all()

    # Recent marks (last 3)
    recent_marks = Marks.query.filter_by(student_id=sp.id)\
        .order_by(Marks.updated_at.desc()).limit(3).all()

    return jsonify({
        'role': user.role,
        'student_id': sp.id,
        'class': sp.class_.name if sp.class_ else None,
        'roll_no': sp.roll_no,
        'attendance': {
            'overall_percentage': att_pct,
            'is_defaulter': is_defaulter,
            'subjects': subject_att
        },
        'notifications_unread': notif_count,
        'today_timetable': [_tt_to_dict(t) for t in timetable],
        'pending_assignments': [_assign_brief(a) for a in assignments],
        'recent_marks': [_mark_brief(m) for m in recent_marks],
    })


def _teacher_dashboard(user, today):
    # Subjects taught
    subjects = Subject.query.filter_by(teacher_id=user.id).all()
    subject_ids = [s.id for s in subjects]

    # How many students marked today
    marked_today = Attendance.query.filter(
        Attendance.subject_id.in_(subject_ids),
        Attendance.date == today,
        Attendance.marked_by == user.id
    ).count() if subject_ids else 0

    # TG students (if TG role)
    tg_students = Student.query.filter_by(
        tg_id=user.id,
        approval_status=ApprovalStatus.APPROVED
    ).count()

    # Pending assignment submissions
    pending_subs = AssignmentSubmission.query.join(Assignment).filter(
        Assignment.subject_id.in_(subject_ids),
        AssignmentSubmission.grade == None
    ).count() if subject_ids else 0

    notif_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()

    return jsonify({
        'role': user.role,
        'subjects_count': len(subjects),
        'subjects': [{'id': s.id, 'name': s.name, 'code': s.code,
                      'class': s.class_.name if s.class_ else None} for s in subjects],
        'marked_today': marked_today,
        'tg_students': tg_students,
        'pending_submissions': pending_subs,
        'notifications_unread': notif_count,
    })


def _ct_dashboard(user, today):
    cls = Class.query.filter_by(class_teacher_id=user.id).first()
    if not cls:
        return jsonify({'role': user.role, 'message': 'No class assigned'}), 200

    total_students = Student.query.filter_by(
        class_id=cls.id, approval_status=ApprovalStatus.APPROVED
    ).count()

    pending_students = Student.query.filter_by(
        class_id=cls.id, approval_status=ApprovalStatus.PENDING
    ).count()

    # Attendance summary for today
    subjects_in_class = Subject.query.filter_by(class_id=cls.id).all()
    marked_subjects_today = 0
    for sub in subjects_in_class:
        count = Attendance.query.filter_by(subject_id=sub.id, date=today).count()
        if count > 0:
            marked_subjects_today += 1

    notif_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()

    return jsonify({
        'role': user.role,
        'class': {'id': cls.id, 'name': cls.name, 'year': cls.year},
        'total_students': total_students,
        'pending_approvals': pending_students,
        'subjects_count': len(subjects_in_class),
        'subjects_marked_today': marked_subjects_today,
        'notifications_unread': notif_count,
    })


def _hod_dashboard(user, today):
    from app.utils.helpers import get_dept_for_hod
    dept_id = get_dept_for_hod(user.id)

    dept_students = db.session.query(func.count(Student.id)).join(
        Class, Student.class_id == Class.id
    ).filter(
        Class.department_id == dept_id,
        Student.approval_status == ApprovalStatus.APPROVED
    ).scalar() or 0

    dept_teachers = Teacher.query.filter_by(department_id=dept_id).count()
    dept_classes  = Class.query.filter_by(department_id=dept_id).count()

    pending_grievances = Grievance.query.join(Student).join(Class).filter(
        Class.department_id == dept_id,
        Grievance.status == ApprovalStatus.PENDING
    ).count()

    notif_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()

    return jsonify({
        'role': user.role,
        'department_id': dept_id,
        'dept_students': dept_students,
        'dept_teachers': dept_teachers,
        'dept_classes': dept_classes,
        'pending_grievances': pending_grievances,
        'notifications_unread': notif_count,
    })


def _admin_dashboard(user, today):
    total_students = Student.query.filter_by(approval_status=ApprovalStatus.APPROVED).count()
    total_teachers = Teacher.query.count()
    total_classes  = Class.query.count()
    pending_students = Student.query.filter_by(approval_status=ApprovalStatus.PENDING).count()
    pending_grievances = Grievance.query.filter_by(status=ApprovalStatus.PENDING).count()
    notif_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()

    return jsonify({
        'role': user.role,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'pending_students': pending_students,
        'pending_grievances': pending_grievances,
        'notifications_unread': notif_count,
    })


# ── Serializers ──────────────────────────────────────────────────────────────
def _tt_to_dict(t):
    return {
        'period': t.period_no,
        'subject': t.subject.name if t.subject else 'Free',
        'teacher': t.subject.teacher_user.name if t.subject and t.subject.teacher_user else None,
        'entry_type': getattr(t, 'entry_type', 'theory'),
        'batch': getattr(t, 'batch', None),
    }

def _assign_brief(a):
    return {
        'id': a.id,
        'title': a.title,
        'subject': a.subject.name if a.subject else None,
        'due_date': a.deadline.isoformat() if a.deadline else None,
    }

def _mark_brief(m):
    return {
        'subject': m.subject.name if m.subject else None,
        'exam_type': ExamType.LABELS.get(m.exam_type, m.exam_type),
        'marks': m.marks,
        'max_marks': m.max_marks,
        'grade': m.grade,
        'percentage': m.percentage,
    }
