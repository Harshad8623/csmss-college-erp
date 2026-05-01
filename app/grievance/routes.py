import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Grievance, GrievanceReply, Student, User, Roles, ApprovalStatus, GrievanceType, GrievancePriority
from app.utils.decorators import role_required
from app.utils.helpers import send_notification
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

grievance_bp = Blueprint('grievance', __name__, url_prefix='/grievance')

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
UPLOAD_SUBDIR = 'grievances'


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_attachment(file):
    """Save uploaded file and return filename, or None."""
    if not file or file.filename == '':
        return None
    if not _allowed_file(file.filename):
        return None
    fname = secure_filename(file.filename)
    upload_dir = os.path.join(current_app.static_folder, 'uploads', UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, fname)
    file.save(filepath)
    return fname


def _priority_order(priority):
    return {'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}.get(priority, 2)


# ── Index ──────────────────────────────────────────────────────────────────────
@grievance_bp.route('/')
@login_required
def index():
    # FIX 2: Include CR role in student view
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            return render_template('grievance/student_view.html', grievances=[])
        grievances = Grievance.query.filter_by(student_id=student.id) \
            .order_by(Grievance.created_at.desc()).all()
        return render_template('grievance/student_view.html', grievances=grievances)

    # Staff view
    if current_user.role in [Roles.SUPER_ADMIN, Roles.HOD]:
        grievances = Grievance.query.order_by(Grievance.created_at.desc()).all()
    elif current_user.role == Roles.CLASS_TEACHER:
        from app.models import Class
        cls = Class.query.filter_by(class_teacher_id=current_user.id).first()
        if cls:
            student_ids = [s.id for s in cls.students.all()]
            grievances = Grievance.query.filter(
                Grievance.student_id.in_(student_ids)
            ).order_by(Grievance.created_at.desc()).all()
        else:
            grievances = Grievance.query.filter_by(
                assigned_to=current_user.id
            ).order_by(Grievance.created_at.desc()).all()
    else:
        grievances = Grievance.query.filter_by(
            assigned_to=current_user.id
        ).order_by(Grievance.created_at.desc()).all()

    # FIX 3: Sort — escalated first, then by priority, then by date
    grievances = sorted(
        grievances,
        key=lambda g: (
            0 if g.status == 'escalated' else 1,
            -_priority_order(g.priority or 'medium'),
            -(g.updated_at or g.created_at).timestamp(),
        )
    )

    pending_count   = sum(1 for g in grievances if g.status == ApprovalStatus.PENDING)
    escalated_count = sum(1 for g in grievances if g.status == 'escalated')
    return render_template('grievance/staff_view.html',
                           grievances=grievances,
                           pending_count=pending_count,
                           escalated_count=escalated_count)


# ── Create ─────────────────────────────────────────────────────────────────────
@grievance_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(Roles.STUDENT, Roles.CR)
def create():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found. Contact your administrator.', 'danger')
        return redirect(url_for('dashboard.index'))

    types = [
        (GrievanceType.MARKS,      'Marks Related'),
        (GrievanceType.ATTENDANCE, 'Attendance Related'),
        (GrievanceType.FACULTY,    'Faculty Related'),
        (GrievanceType.FACILITY,   'Facility Related'),
        (GrievanceType.OTHER,      'Other'),
    ]
    priorities = [
        (GrievancePriority.LOW,    '🟢 Low'),
        (GrievancePriority.MEDIUM, '🟡 Medium'),
        (GrievancePriority.HIGH,   '🔴 High'),
        (GrievancePriority.URGENT, '🚨 Urgent'),
    ]

    if request.method == 'POST':
        gtype       = request.form.get('type', GrievanceType.OTHER)
        description = request.form.get('description', '').strip()
        priority    = request.form.get('priority', GrievancePriority.MEDIUM)

        if not description:
            flash('Please describe your grievance.', 'danger')
            return render_template('grievance/create.html', types=types, priorities=priorities)

        # File attachment
        attachment = None
        if 'attachment' in request.files:
            attachment = _save_attachment(request.files['attachment'])

        # SLA: 3 days for high/urgent, 5 days for medium, 7 for low
        sla_days = {'urgent': 2, 'high': 3, 'medium': 5, 'low': 7}.get(priority, 5)
        deadline = datetime.utcnow() + timedelta(days=sla_days)

        grievance = Grievance(
            student_id=student.id,
            type=gtype,
            description=description,
            priority=priority,
            attachment=attachment,
            deadline=deadline,
            status=ApprovalStatus.PENDING,
        )
        db.session.add(grievance)

        # Notify class teacher
        if student.class_ and student.class_.class_teacher_id:
            priority_label = dict(priorities).get(priority, priority).replace('🟢 ', '').replace('🟡 ', '').replace('🔴 ', '').replace('🚨 ', '')
            send_notification(
                student.class_.class_teacher_id,
                f'📋 New [{priority_label}] grievance from {current_user.name}: {gtype}',
                'warning',
                url_for('grievance.index'),
            )

        db.session.commit()
        flash('Grievance submitted! Your class teacher will be notified.', 'success')
        return redirect(url_for('grievance.index'))

    return render_template('grievance/create.html', types=types, priorities=priorities)


# ── Detail + Reply + Action ────────────────────────────────────────────────────
@grievance_bp.route('/<int:id>', methods=['GET', 'POST'])
@login_required
def detail(id):
    grievance = Grievance.query.get_or_404(id)
    student   = grievance.student

    # Authorization
    if current_user.role in [Roles.STUDENT, Roles.CR] and student.user_id != current_user.id:
        flash('You are not authorised to view this grievance.', 'danger')
        return redirect(url_for('grievance.index'))

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        # ── Reply thread ────────────────────────────────────────────
        if form_type == 'reply':
            msg = request.form.get('message', '').strip()
            if msg:
                reply = GrievanceReply(
                    grievance_id=grievance.id,
                    user_id=current_user.id,
                    message=msg,
                )
                db.session.add(reply)

                # Notify the other party
                if current_user.role in [Roles.STUDENT, Roles.CR]:
                    # Student replied → notify teacher
                    if student.class_ and student.class_.class_teacher_id:
                        send_notification(
                            student.class_.class_teacher_id,
                            f'💬 {current_user.name} replied on grievance #{grievance.id}',
                            'info', url_for('grievance.detail', id=id),
                        )
                else:
                    # Staff replied → notify student
                    send_notification(
                        student.user_id,
                        f'💬 Staff replied on your grievance #{grievance.id}',
                        'info', url_for('grievance.detail', id=id),
                    )
                db.session.commit()
                flash('Reply added.', 'success')
            return redirect(url_for('grievance.detail', id=id))

        # ── Status action (staff only) ──────────────────────────────
        if current_user.role in [Roles.STUDENT, Roles.CR]:
            flash('Students cannot update grievance status.', 'danger')
            return redirect(url_for('grievance.detail', id=id))

        action  = request.form.get('action')
        comment = request.form.get('comment', '').strip()

        status_map = {
            'approve':  'approved',
            'reject':   'rejected',
            'escalate': 'escalated',
        }
        new_status = status_map.get(action)
        if not new_status:
            flash('Invalid action.', 'danger')
            return redirect(url_for('grievance.detail', id=id))

        grievance.status      = new_status
        grievance.comment     = comment
        grievance.assigned_to = current_user.id

        # FIX 1: Escalation → notify HOD
        if new_status == 'escalated':
            hods = User.query.filter(
                User.role.in_([Roles.HOD, Roles.SUPER_ADMIN])
            ).all()
            for hod in hods:
                send_notification(
                    hod.id,
                    f'⬆️ Grievance #{grievance.id} escalated by {current_user.name}. Student: {student.user.name}',
                    'warning',
                    url_for('grievance.detail', id=grievance.id),
                )

        # Notify student of resolution
        status_label = new_status.title()
        msg = (f'Your grievance #{grievance.id} has been {status_label}.'
               + (f' Response: {comment}' if comment else ''))
        send_notification(
            student.user_id,
            msg,
            'success' if new_status == 'approved' else 'danger',
            url_for('grievance.detail', id=id),
        )

        db.session.commit()
        flash(f'Grievance marked as {status_label}.', 'success')
        return redirect(url_for('grievance.index'))

    replies = grievance.replies.all()
    days_pending = (datetime.utcnow() - grievance.created_at).days
    overdue = grievance.deadline and datetime.utcnow() > grievance.deadline

    return render_template('grievance/detail.html',
                           grievance=grievance,
                           replies=replies,
                           days_pending=days_pending,
                           overdue=overdue)
