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
        grievances = Grievance.query.filter_by(student_id=student.id)\
            .order_by(Grievance.created_at.desc()).all() if student else []
        return render_template('grievance/student_view.html', grievances=grievances)
    else:
        # Staff sees grievances they're assigned to or all (for admin)
        if current_user.role in [Roles.SUPER_ADMIN, Roles.HOD]:
            grievances = Grievance.query.order_by(Grievance.created_at.desc()).all()
        else:
            grievances = Grievance.query.filter_by(assigned_to=current_user.id)\
                .order_by(Grievance.created_at.desc()).all()
        pending_count = sum(1 for g in grievances if g.status == ApprovalStatus.PENDING)
        return render_template('grievance/staff_view.html',
            grievances=grievances, pending_count=pending_count)

@grievance_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(Roles.STUDENT, Roles.CR)
def create():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        gtype = request.form.get('type', GrievanceType.OTHER)
        description = request.form.get('description', '').strip()
        if not description:
            flash('Please describe your grievance.', 'danger')
            return render_template('grievance/create.html')

        grievance = Grievance(
            student_id=student.id,
            type=gtype,
            description=description,
            status=ApprovalStatus.PENDING
        )
        db.session.add(grievance)
        db.session.commit()

        # Notify class teacher if exists
        if student.class_ and student.class_.class_teacher:
            send_notification(
                student.class_.class_teacher_id,
                f'📨 New grievance from {current_user.name}: {gtype}',
                'warning',
                url_for('grievance.detail', id=grievance.id)
            )

        flash('Grievance submitted successfully! It will be reviewed shortly.', 'success')
        return redirect(url_for('grievance.index'))

    return render_template('grievance/create.html', types=[
        (GrievanceType.MARKS, 'Marks Related'),
        (GrievanceType.ATTENDANCE, 'Attendance Related'),
        (GrievanceType.FACULTY, 'Faculty Related'),
        (GrievanceType.FACILITY, 'Facility Related'),
        (GrievanceType.OTHER, 'Other'),
    ])

@grievance_bp.route('/<int:id>', methods=['GET', 'POST'])
@login_required
def detail(id):
    grievance = Grievance.query.get_or_404(id)
    student = grievance.student

    # Authorization check
    if current_user.role == Roles.STUDENT and student.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('grievance.index'))

    if request.method == 'POST' and current_user.role != Roles.STUDENT:
        action = request.form.get('action')
        comment = request.form.get('comment', '').strip()
        if action == 'approve':
            grievance.status = 'approved'
        elif action == 'reject':
            grievance.status = 'rejected'
        elif action == 'escalate':
            grievance.status = 'escalated'

        grievance.comment = comment
        grievance.assigned_to = current_user.id
        db.session.commit()

        # Notify student
        send_notification(
            student.user_id,
            f'📋 Your grievance has been {grievance.status}: {comment[:50]}...' if comment else
            f'📋 Your grievance status updated to: {grievance.status}',
            'info' if grievance.status == 'approved' else 'warning',
            url_for('grievance.detail', id=id)
        )
        flash(f'Grievance {grievance.status}.', 'success')
        return redirect(url_for('grievance.index'))

    return render_template('grievance/detail.html', grievance=grievance)
