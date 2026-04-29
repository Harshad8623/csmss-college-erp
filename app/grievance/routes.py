from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Grievance, Student, User, Roles, ApprovalStatus, GrievanceType
from app.utils.decorators import role_required
from app.utils.helpers import send_notification

grievance_bp = Blueprint('grievance', __name__, url_prefix='/grievance')


@grievance_bp.route('/')
@login_required
def index():
    if current_user.role == Roles.STUDENT:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            return render_template('grievance/student_view.html', grievances=[])
        grievances = Grievance.query.filter_by(student_id=student.id) \
            .order_by(Grievance.created_at.desc()).all()
        return render_template('grievance/student_view.html', grievances=grievances)
    else:
        # Admin/HOD see all; Class Teacher sees grievances from their class students
        if current_user.role in [Roles.SUPER_ADMIN, Roles.HOD]:
            grievances = Grievance.query.order_by(Grievance.created_at.desc()).all()
        elif current_user.role == Roles.CLASS_TEACHER:
            # Grievances from students in the class this teacher manages
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

        pending_count = sum(1 for g in grievances if g.status == ApprovalStatus.PENDING)
        return render_template('grievance/staff_view.html',
                               grievances=grievances, pending_count=pending_count)


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

    if request.method == 'POST':
        gtype       = request.form.get('type', GrievanceType.OTHER)
        description = request.form.get('description', '').strip()
        if not description:
            flash('Please describe your grievance.', 'danger')
            return render_template('grievance/create.html', types=types)

        grievance = Grievance(
            student_id=student.id,
            type=gtype,
            description=description,
            status=ApprovalStatus.PENDING,
        )
        db.session.add(grievance)

        # Notify class teacher if exists — add notification to same session
        if student.class_ and student.class_.class_teacher_id:
            send_notification(
                student.class_.class_teacher_id,
                f'New grievance from {current_user.name}: {gtype}',
                'warning',
                url_for('grievance.index'),
            )

        db.session.commit()   # single commit saves grievance + notification
        flash('Grievance submitted successfully! Your class teacher will be notified.', 'success')
        return redirect(url_for('grievance.index'))

    return render_template('grievance/create.html', types=types)


@grievance_bp.route('/<int:id>', methods=['GET', 'POST'])
@login_required
def detail(id):
    grievance = Grievance.query.get_or_404(id)
    student   = grievance.student

    # Authorization: students can only see their own grievances
    if current_user.role == Roles.STUDENT and student.user_id != current_user.id:
        flash('You are not authorised to view this grievance.', 'danger')
        return redirect(url_for('grievance.index'))

    if request.method == 'POST':
        # Only staff can act on grievances
        if current_user.role == Roles.STUDENT:
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

        # Notify student
        status_label = new_status.title()
        msg = (f'Your grievance has been {status_label}.'
               + (f' Comment: {comment}' if comment else ''))
        send_notification(
            student.user_id,
            msg,
            'success' if new_status == 'approved' else 'danger',
            url_for('grievance.detail', id=id),
        )

        db.session.commit()   # saves status update + notification together
        flash(f'Grievance marked as {status_label}.', 'success')
        return redirect(url_for('grievance.index'))

    return render_template('grievance/detail.html', grievance=grievance)
