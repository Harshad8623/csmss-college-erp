"""
/api/v1/attendance — Attendance endpoints for mobile
GET  /api/v1/attendance/my              → Student: own attendance per subject
GET  /api/v1/attendance/subjects        → Teacher: list subjects to mark
POST /api/v1/attendance/mark            → Teacher: mark attendance for a subject+date
GET  /api/v1/attendance/report/<class_id> → CT/HOD: class attendance report
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, cast, Integer
from datetime import date, datetime
import pytz

from app.extensions import db
from app.models import (
    Student, Subject, Attendance, Class,
    Roles, ApprovalStatus
)
from app.api.decorators import get_current_api_user, jwt_role_required

attendance_api_bp = Blueprint('attendance_api', __name__)

IST = pytz.timezone('Asia/Kolkata')


def _today_ist():
    return datetime.now(IST).date()


@attendance_api_bp.route('/my', methods=['GET'])
@jwt_required()
def my_attendance():
    """
    Student: own attendance per subject with percentage
    ---
    tags: [Attendance]
    security: [{Bearer: []}]
    responses:
      200:
        description: List of subjects with attendance stats
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.role not in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Students only'}), 403

    sp = user.student_profile
    if not sp:
        return jsonify({'error': 'Student profile not found'}), 404

    subjects = Subject.query.filter_by(class_id=sp.class_id).all()
    result = []
    for sub in subjects:
        rows = Attendance.query.filter_by(
            student_id=sp.id, subject_id=sub.id
        ).order_by(Attendance.date.desc()).all()

        total   = len(rows)
        present = sum(1 for r in rows if r.status)
        pct     = round((present / total) * 100, 2) if total > 0 else 0

        result.append({
            'subject_id':   sub.id,
            'subject':      sub.name,
            'code':         sub.code,
            'total':        total,
            'present':      present,
            'absent':       total - present,
            'percentage':   pct,
            'is_safe':      pct >= 75,
            'is_defaulter': pct < 75 and total > 0,
        })

    overall = sp.attendance_percentage()
    return jsonify({
        'overall_percentage': overall,
        'is_defaulter': overall < 75,
        'subjects': result
    })


@attendance_api_bp.route('/subjects', methods=['GET'])
@jwt_required()
def teacher_subjects():
    """
    Teacher: list subjects available to mark attendance
    ---
    tags: [Attendance]
    security: [{Bearer: []}]
    responses:
      200:
        description: Subjects with last-marked date
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.role not in (Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN):
        return jsonify({'error': 'Staff only'}), 403

    subjects = Subject.query.filter_by(teacher_id=user.id).all()
    today = _today_ist()

    result = []
    for sub in subjects:
        last = Attendance.query.filter_by(subject_id=sub.id)\
            .order_by(Attendance.date.desc()).first()
        marked_today = Attendance.query.filter_by(
            subject_id=sub.id, date=today
        ).count() > 0

        result.append({
            'id':            sub.id,
            'name':          sub.name,
            'code':          sub.code,
            'class_id':      sub.class_id,
            'class_name':    sub.class_.name if sub.class_ else None,
            'last_marked':   last.date.isoformat() if last else None,
            'marked_today':  marked_today,
        })

    return jsonify({'subjects': result})


@attendance_api_bp.route('/mark', methods=['POST'])
@jwt_required()
def mark_attendance():
    """
    Teacher: mark attendance for a subject on a date
    ---
    tags: [Attendance]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          required: [subject_id, date, records]
          properties:
            subject_id: {type: integer}
            date: {type: string, example: "2024-05-01"}
            records:
              type: array
              items:
                properties:
                  student_id: {type: integer}
                  present: {type: boolean}
    responses:
      200:
        description: Attendance saved
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.role not in (Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN):
        return jsonify({'error': 'Staff only'}), 403

    data       = request.get_json(silent=True) or {}
    subject_id = data.get('subject_id')
    date_str   = data.get('date')
    records    = data.get('records', [])

    if not subject_id or not date_str or not records:
        return jsonify({'error': 'subject_id, date, and records are required'}), 400

    # Validate date
    try:
        att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if att_date > _today_ist():
        return jsonify({'error': 'Cannot mark attendance for future dates'}), 400

    # Verify subject belongs to this teacher
    sub = Subject.query.get(subject_id)
    if not sub:
        return jsonify({'error': 'Subject not found'}), 404
    if sub.teacher_id != user.id and user.role not in (Roles.SUPER_ADMIN, Roles.HOD):
        return jsonify({'error': 'Not your subject'}), 403

    saved = 0
    for rec in records:
        sid     = rec.get('student_id')
        present = bool(rec.get('present', False))
        if not sid:
            continue

        existing = Attendance.query.filter_by(
            student_id=sid, subject_id=subject_id, date=att_date
        ).first()

        if existing:
            existing.status    = present
            existing.marked_by = user.id
        else:
            db.session.add(Attendance(
                student_id=sid,
                subject_id=subject_id,
                date=att_date,
                status=present,
                marked_by=user.id
            ))
        saved += 1

    db.session.commit()
    return jsonify({'message': f'Attendance saved for {saved} students', 'date': date_str}), 200


@attendance_api_bp.route('/students/<int:subject_id>', methods=['GET'])
@jwt_required()
def students_for_subject(subject_id):
    """
    Teacher: get students for a subject + existing attendance for a date
    ---
    tags: [Attendance]
    security: [{Bearer: []}]
    parameters:
      - name: subject_id
        in: path
        type: integer
        required: true
      - name: date
        in: query
        type: string
        description: "YYYY-MM-DD (default: today)"
    responses:
      200:
        description: Student list with existing attendance status
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    sub = Subject.query.get_or_404(subject_id)
    date_str = request.args.get('date', _today_ist().isoformat())
    try:
        att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    students = Student.query.filter_by(
        class_id=sub.class_id,
        approval_status=ApprovalStatus.APPROVED
    ).order_by(Student.roll_no).all()

    # Bulk-fetch existing attendance for this subject+date
    existing = {
        a.student_id: a.status
        for a in Attendance.query.filter_by(subject_id=subject_id, date=att_date).all()
    }

    return jsonify({
        'subject': {'id': sub.id, 'name': sub.name, 'code': sub.code},
        'date': date_str,
        'students': [
            {
                'id':       s.id,
                'name':     s.user.name,
                'roll_no':  s.roll_no,
                'prn':      s.prn,
                'batch':    s.batch,
                'present':  existing.get(s.id, None),  # None = not marked yet
            }
            for s in students
        ]
    })
