"""
/api/v1/marks, /api/v1/notices, /api/v1/notifications, /api/v1/timetable
Grouped together for conciseness — each gets its own Blueprint.
"""

# ── marks.py ────────────────────────────────────────────────────────────────
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import (
    Student, Subject, Marks, Notice, Notification, Timetable,
    Assignment, AssignmentSubmission, LeaveApplication, LeaveStatus,
    Grievance, Certificate, Class, Roles, ApprovalStatus,
    ExamType
)
from app.api.decorators import get_current_api_user

marks_api_bp        = Blueprint('marks_api',         __name__)
notices_api_bp      = Blueprint('notices_api',        __name__)
notifications_api_bp = Blueprint('notifications_api_v1', __name__)
timetable_api_bp    = Blueprint('timetable_api',      __name__)
assignments_api_bp  = Blueprint('assignments_api',    __name__)
leaves_api_bp       = Blueprint('leaves_api',         __name__)
grievances_api_bp   = Blueprint('grievances_api',     __name__)
certificates_api_bp = Blueprint('certificates_api',   __name__)


# ════════════════════════════════════════════════════════════════════════════
# MARKS
# ════════════════════════════════════════════════════════════════════════════
@marks_api_bp.route('/my', methods=['GET'])
@jwt_required()
def my_marks():
    """
    Student: get own marks across all subjects and exam types
    ---
    tags: [Marks]
    security: [{Bearer: []}]
    responses:
      200:
        description: Marks grouped by subject
    """
    user = get_current_api_user()
    if not user or user.role not in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Students only'}), 403
    sp = user.student_profile
    if not sp:
        return jsonify({'error': 'No student profile'}), 404

    all_marks = Marks.query.filter_by(student_id=sp.id)\
        .order_by(Marks.subject_id, Marks.exam_type).all()

    # Group by subject
    grouped = {}
    for m in all_marks:
        sid = m.subject_id
        if sid not in grouped:
            grouped[sid] = {
                'subject_id': sid,
                'subject':    m.subject.name if m.subject else 'Unknown',
                'code':       m.subject.code if m.subject else '',
                'exams': []
            }
        grouped[sid]['exams'].append({
            'exam_type':  m.exam_type,
            'exam_label': ExamType.LABELS.get(m.exam_type, m.exam_type),
            'marks':      m.marks,
            'max_marks':  m.max_marks,
            'percentage': m.percentage,
            'grade':      m.grade,
        })

    return jsonify({'marks': list(grouped.values())})


@marks_api_bp.route('/subject/<int:subject_id>/students', methods=['GET'])
@jwt_required()
def subject_student_marks(subject_id):
    """
    Teacher: get all students' marks for a subject and exam type
    ---
    tags: [Marks]
    security: [{Bearer: []}]
    parameters:
      - name: subject_id
        in: path
        type: integer
      - name: exam_type
        in: query
        type: string
    responses:
      200:
        description: Student marks list
    """
    user = get_current_api_user()
    if not user or user.role in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Staff only'}), 403

    sub = Subject.query.get_or_404(subject_id)
    exam_type = request.args.get('exam_type', ExamType.CT1)

    students = Student.query.filter_by(
        class_id=sub.class_id, approval_status=ApprovalStatus.APPROVED
    ).order_by(Student.roll_no).all()

    existing = {
        m.student_id: m
        for m in Marks.query.filter_by(subject_id=subject_id, exam_type=exam_type).all()
    }

    return jsonify({
        'subject':   {'id': sub.id, 'name': sub.name, 'code': sub.code},
        'exam_type': exam_type,
        'exam_label': ExamType.LABELS.get(exam_type, exam_type),
        'exam_types': ExamType.ALL,
        'exam_labels': ExamType.LABELS,
        'students': [
            {
                'student_id': s.id,
                'name':       s.user.name,
                'roll_no':    s.roll_no,
                'marks':      existing[s.id].marks if s.id in existing else None,
                'max_marks':  existing[s.id].max_marks if s.id in existing else 100,
                'grade':      existing[s.id].grade if s.id in existing else None,
            }
            for s in students
        ]
    })


@marks_api_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_marks():
    """
    Teacher: upload/update marks for multiple students
    ---
    tags: [Marks]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          required: [subject_id, exam_type, max_marks, records]
          properties:
            subject_id: {type: integer}
            exam_type: {type: string}
            max_marks: {type: number}
            records:
              type: array
              items:
                properties:
                  student_id: {type: integer}
                  marks: {type: number}
    responses:
      200:
        description: Marks saved
    """
    user = get_current_api_user()
    if not user or user.role in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Staff only'}), 403

    data       = request.get_json(silent=True) or {}
    subject_id = data.get('subject_id')
    exam_type  = data.get('exam_type', ExamType.CT1)
    max_marks  = float(data.get('max_marks', 100))
    records    = data.get('records', [])

    if not subject_id or not records:
        return jsonify({'error': 'subject_id and records are required'}), 400

    saved = 0
    for rec in records:
        sid   = rec.get('student_id')
        marks = rec.get('marks')
        if sid is None or marks is None:
            continue
        marks = float(marks)
        if marks < 0 or marks > max_marks:
            continue

        existing = Marks.query.filter_by(
            student_id=sid, subject_id=subject_id, exam_type=exam_type
        ).first()
        if existing:
            existing.marks      = marks
            existing.max_marks  = max_marks
            existing.uploaded_by = user.id
        else:
            db.session.add(Marks(
                student_id=sid, subject_id=subject_id,
                marks=marks, max_marks=max_marks,
                exam_type=exam_type, uploaded_by=user.id
            ))
        saved += 1

    db.session.commit()
    return jsonify({'message': f'Marks saved for {saved} students'}), 200


# ════════════════════════════════════════════════════════════════════════════
# NOTICES
# ════════════════════════════════════════════════════════════════════════════
@notices_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_notices():
    """
    Get paginated notices (scoped by role)
    ---
    tags: [Notices]
    security: [{Bearer: []}]
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
    responses:
      200:
        description: Paginated notices
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    page     = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 50)

    from sqlalchemy import or_
    q = Notice.query.filter_by(is_approved=True)

    # Scope notices by role/class
    if user.role in (Roles.STUDENT, Roles.CR):
        sp = user.student_profile
        if sp:
            q = q.filter(
                or_(
                    Notice.target_role == None,
                    Notice.target_role == 'student',
                    Notice.target_class_id == sp.class_id
                )
            )

    q = q.order_by(Notice.is_urgent.desc(), Notice.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'notices': [_notice_dict(n) for n in pagination.items],
        'total':   pagination.total,
        'pages':   pagination.pages,
        'page':    page,
    })


@notices_api_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_notice(id):
    """Get single notice detail"""
    notice = Notice.query.get_or_404(id)
    return jsonify({'notice': _notice_dict(notice)})


@notices_api_bp.route('/', methods=['POST'])
@jwt_required()
def create_notice():
    """
    Create a notice (staff/CR)
    ---
    tags: [Notices]
    security: [{Bearer: []}]
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.role == Roles.STUDENT:
        return jsonify({'error': 'Only staff and CR can post notices'}), 403

    data = request.get_json(silent=True) or {}
    title   = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400

    is_approved = user.role not in (Roles.CR,)  # CR notices need approval
    notice = Notice(
        title=title,
        content=content,
        posted_by=user.id,
        target_role=data.get('target_role'),
        target_class_id=data.get('target_class_id'),
        is_urgent=bool(data.get('is_urgent', False)),
        is_approved=is_approved,
    )
    db.session.add(notice)
    db.session.commit()

    msg = 'Notice posted.' if is_approved else 'Notice submitted for approval.'
    return jsonify({'message': msg, 'notice': _notice_dict(notice)}), 201


def _notice_dict(n):
    return {
        'id':        n.id,
        'title':     n.title,
        'content':   n.content,
        'is_urgent': n.is_urgent,
        'posted_by': n.author.name if hasattr(n, 'author') and n.author else None,
        'created_at': n.created_at.isoformat(),
        'target_role': getattr(n, 'target_role', None),
    }


# ════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ════════════════════════════════════════════════════════════════════════════
@notifications_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_notifications():
    """
    Get paginated notifications for current user
    ---
    tags: [Notifications]
    security: [{Bearer: []}]
    responses:
      200:
        description: Notifications list with unread count
    """
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    page     = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 50)

    q = Notification.query.filter_by(user_id=user.id)\
        .order_by(Notification.created_at.desc())

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()

    return jsonify({
        'unread_count': unread,
        'notifications': [
            {
                'id':         n.id,
                'message':    n.message,
                'type':       n.type,
                'link':       n.link,
                'is_read':    n.is_read,
                'created_at': n.created_at.isoformat(),
            }
            for n in pagination.items
        ],
        'total': pagination.total,
        'pages': pagination.pages,
        'page':  page,
    })


@notifications_api_bp.route('/mark-read', methods=['POST'])
@jwt_required()
def mark_all_read():
    """Mark all notifications as read"""
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    Notification.query.filter_by(user_id=user.id, is_read=False)\
        .update({'is_read': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({'message': 'All notifications marked as read'}), 200


@notifications_api_bp.route('/fcm-token', methods=['POST'])
@jwt_required()
def save_fcm_token():
    """
    Save FCM token for mobile push notifications
    ---
    tags: [Notifications]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          required: [fcm_token]
          properties:
            fcm_token: {type: string}
    responses:
      200:
        description: Token saved
    """
    from app.models import PushSubscription
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data      = request.get_json(silent=True) or {}
    fcm_token = (data.get('fcm_token') or '').strip()
    if not fcm_token:
        return jsonify({'error': 'fcm_token is required'}), 400

    # Upsert: store FCM token using endpoint field with 'fcm:' prefix
    endpoint = f'fcm:{fcm_token}'
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub:
        sub.user_id = user.id
    else:
        sub = PushSubscription(
            user_id=user.id,
            endpoint=endpoint,
            p256dh='fcm',
            auth='fcm',
            user_agent=request.headers.get('User-Agent', '')[:300]
        )
        db.session.add(sub)

    db.session.commit()
    return jsonify({'message': 'FCM token saved'}), 200


# ════════════════════════════════════════════════════════════════════════════
# TIMETABLE
# ════════════════════════════════════════════════════════════════════════════
@timetable_api_bp.route('/', methods=['GET'])
@jwt_required()
def my_timetable():
    """
    Get timetable for current user's class (students) or all classes taught (teachers)
    ---
    tags: [Timetable]
    security: [{Bearer: []}]
    parameters:
      - name: day
        in: query
        type: string
        description: "e.g. Monday (default: today)"
    responses:
      200:
        description: Timetable entries
    """
    from datetime import datetime
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    day = request.args.get('day', datetime.now().strftime('%A'))

    if user.role in (Roles.STUDENT, Roles.CR):
        sp = user.student_profile
        if not sp:
            return jsonify({'error': 'No student profile'}), 404
        entries = Timetable.query.filter_by(
            class_id=sp.class_id, day=day
        ).order_by(Timetable.period_no).all()
    else:
        # Teacher: timetable across all their subjects' classes
        from app.models import Subject as Sub
        subjects = Sub.query.filter_by(teacher_id=user.id).all()
        class_ids = list({s.class_id for s in subjects})
        entries = Timetable.query.filter(
            Timetable.class_id.in_(class_ids),
            Timetable.day == day
        ).order_by(Timetable.class_id, Timetable.period_no).all()

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    return jsonify({
        'day': day,
        'days': days,
        'entries': [
            {
                'id':         e.id,
                'period':     e.period_no,
                'subject':    e.subject.name if e.subject else 'Free',
                'code':       e.subject.code if e.subject else None,
                'teacher':    e.subject.teacher_user.name if e.subject and e.subject.teacher_user else None,
                'class_name': e.class_.name if e.class_ else None,
                'entry_type': getattr(e, 'entry_type', 'theory'),
                'batch':      getattr(e, 'batch', None),
            }
            for e in entries
        ]
    })


# ════════════════════════════════════════════════════════════════════════════
# ASSIGNMENTS
# ════════════════════════════════════════════════════════════════════════════
@assignments_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_assignments():
    """List assignments for current user's class or subjects taught"""
    from datetime import date
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    page     = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 50)

    if user.role in (Roles.STUDENT, Roles.CR):
        sp = user.student_profile
        if not sp:
            return jsonify({'assignments': []}), 200
        from sqlalchemy import or_
        from app.models import Subject as Sub
        q = Assignment.query.join(Sub).filter(Sub.class_id == sp.class_id)
    else:
        from app.models import Subject as Sub
        subjects = Sub.query.filter_by(teacher_id=user.id).all()
        sids = [s.id for s in subjects]
        q = Assignment.query.filter(Assignment.subject_id.in_(sids)) if sids else Assignment.query.filter_by(id=0)

    q = q.order_by(Assignment.due_date.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    sp = user.student_profile if user.role in (Roles.STUDENT, Roles.CR) else None

    def _assign_dict(a):
        submitted = False
        if sp:
            submitted = AssignmentSubmission.query.filter_by(
                assignment_id=a.id, student_id=sp.id
            ).first() is not None
        return {
            'id':          a.id,
            'title':       a.title,
            'description': a.description,
            'subject':     a.subject.name if a.subject else None,
            'due_date':    a.due_date.isoformat() if a.due_date else None,
            'is_overdue':  a.due_date < date.today() if a.due_date else False,
            'submitted':   submitted,
        }

    return jsonify({
        'assignments': [_assign_dict(a) for a in pagination.items],
        'total': pagination.total, 'pages': pagination.pages, 'page': page
    })


# ════════════════════════════════════════════════════════════════════════════
# LEAVES
# ════════════════════════════════════════════════════════════════════════════
@leaves_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_leaves():
    """Student: own leave applications"""
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.role in (Roles.STUDENT, Roles.CR):
        sp = user.student_profile
        if not sp:
            return jsonify({'leaves': []}), 200
        leaves = LeaveApplication.query.filter_by(student_id=sp.id)\
            .order_by(LeaveApplication.created_at.desc()).limit(20).all()
    else:
        # TG sees their students' pending leaves
        leaves = LeaveApplication.query.join(Student).filter(
            Student.tg_id == user.id,
            LeaveApplication.status == LeaveStatus.PENDING_TG
        ).order_by(LeaveApplication.created_at.desc()).limit(20).all()

    return jsonify({'leaves': [_leave_dict(l) for l in leaves]})


@leaves_api_bp.route('/apply', methods=['POST'])
@jwt_required()
def apply_leave():
    """Student: apply for leave"""
    user = get_current_api_user()
    if not user or user.role not in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Students only'}), 403
    sp = user.student_profile
    if not sp:
        return jsonify({'error': 'No student profile'}), 404

    data = request.get_json(silent=True) or {}
    from datetime import datetime as dt
    try:
        start = dt.strptime(data['start_date'], '%Y-%m-%d').date()
        end   = dt.strptime(data['end_date'],   '%Y-%m-%d').date()
    except (KeyError, ValueError):
        return jsonify({'error': 'start_date and end_date required (YYYY-MM-DD)'}), 400

    leave = LeaveApplication(
        student_id=sp.id,
        leave_type=data.get('leave_type', 'multi_day'),
        start_date=start,
        end_date=end,
        reason=data.get('reason', '').strip()[:500],
        status=LeaveStatus.PENDING_TG,
    )
    db.session.add(leave)
    db.session.commit()
    return jsonify({'message': 'Leave application submitted', 'leave': _leave_dict(leave)}), 201


def _leave_dict(l):
    return {
        'id':         l.id,
        'leave_type': l.leave_type,
        'start_date': l.start_date.isoformat() if l.start_date else None,
        'end_date':   l.end_date.isoformat() if l.end_date else None,
        'reason':     l.reason,
        'status':     l.status,
        'created_at': l.created_at.isoformat(),
    }


# ════════════════════════════════════════════════════════════════════════════
# GRIEVANCES
# ════════════════════════════════════════════════════════════════════════════
@grievances_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_grievances():
    """Student: own grievances. Staff: all grievances in scope"""
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.role in (Roles.STUDENT, Roles.CR):
        sp = user.student_profile
        if not sp:
            return jsonify({'grievances': []}), 200
        grievances = Grievance.query.filter_by(student_id=sp.id)\
            .order_by(Grievance.created_at.desc()).limit(20).all()
    else:
        grievances = Grievance.query.order_by(Grievance.created_at.desc()).limit(30).all()

    return jsonify({'grievances': [_grievance_dict(g) for g in grievances]})


@grievances_api_bp.route('/create', methods=['POST'])
@jwt_required()
def create_grievance():
    """Student: submit a grievance"""
    user = get_current_api_user()
    if not user or user.role not in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Students only'}), 403
    sp = user.student_profile
    if not sp:
        return jsonify({'error': 'No student profile'}), 404

    data = request.get_json(silent=True) or {}
    g = Grievance(
        student_id=sp.id,
        type=data.get('type', 'other'),
        description=(data.get('description') or '').strip(),
        priority=data.get('priority', 'medium'),
        status=ApprovalStatus.PENDING,
    )
    db.session.add(g)
    db.session.commit()
    return jsonify({'message': 'Grievance submitted', 'grievance': _grievance_dict(g)}), 201


def _grievance_dict(g):
    return {
        'id':          g.id,
        'type':        g.type,
        'description': g.description,
        'priority':    g.priority,
        'status':      g.status,
        'created_at':  g.created_at.isoformat(),
        'comment':     g.comment,
    }


# ════════════════════════════════════════════════════════════════════════════
# CERTIFICATES
# ════════════════════════════════════════════════════════════════════════════
@certificates_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_certificates():
    """Student: own certificate applications"""
    user = get_current_api_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.role not in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Students only'}), 403
    sp = user.student_profile
    if not sp:
        return jsonify({'certificates': []}), 200

    certs = Certificate.query.filter_by(student_id=sp.id)\
        .order_by(Certificate.created_at.desc()).all()
    return jsonify({'certificates': [
        {
            'id':            c.id,
            'type':          c.type,
            'purpose':       getattr(c, 'purpose', None),
            'status':        c.status,
            'created_at':    c.created_at.isoformat(),
        }
        for c in certs
    ]})


@certificates_api_bp.route('/apply', methods=['POST'])
@jwt_required()
def apply_certificate():
    """Student: apply for a certificate"""
    user = get_current_api_user()
    if not user or user.role not in (Roles.STUDENT, Roles.CR):
        return jsonify({'error': 'Students only'}), 403
    sp = user.student_profile
    if not sp:
        return jsonify({'error': 'No student profile'}), 404

    data = request.get_json(silent=True) or {}
    cert_type = data.get('type', 'bonafide')
    purpose   = (data.get('purpose') or '').strip()

    cert = Certificate(
        student_id=sp.id,
        type=cert_type,
        purpose=purpose,
        status=ApprovalStatus.PENDING,
    )
    db.session.add(cert)
    db.session.commit()
    return jsonify({'message': 'Certificate application submitted'}), 201
