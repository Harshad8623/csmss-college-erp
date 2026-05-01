from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import LeaveApplication, Student, Class, Roles, LeaveType, LeaveStatus, ApprovalStatus
from app.utils.decorators import role_required
from datetime import datetime

leaves_bp = Blueprint('leaves', __name__, url_prefix='/leaves')

@leaves_bp.route('/')
@login_required
def index():
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            flash('Student profile not found.', 'danger')
            return redirect(url_for('dashboard.index'))
        leaves = LeaveApplication.query.filter_by(student_id=student.id).order_by(LeaveApplication.created_at.desc()).all()
        return render_template('leaves/student_history.html', leaves=leaves)
    else:
        # Staff view
        tg_leaves = []
        ct_leaves = []

        # Find if teacher is TG for any students
        tg_students = Student.query.filter_by(tg_id=current_user.id).all()
        if tg_students:
            tg_student_ids = [s.id for s in tg_students]
            tg_leaves = LeaveApplication.query.filter(LeaveApplication.student_id.in_(tg_student_ids)).order_by(LeaveApplication.created_at.desc()).all()

        # Find if teacher is CT for any class
        cls = Class.query.filter_by(class_teacher_id=current_user.id).first()
        if cls:
            # CT sees leaves that are already approved by TG
            ct_students = Student.query.filter_by(class_id=cls.id).all()
            ct_student_ids = [s.id for s in ct_students]
            ct_leaves = LeaveApplication.query.filter(
                LeaveApplication.student_id.in_(ct_student_ids),
                LeaveApplication.tg_status == ApprovalStatus.APPROVED
            ).order_by(LeaveApplication.created_at.desc()).all()

        return render_template('leaves/staff_review.html', tg_leaves=tg_leaves, ct_leaves=ct_leaves)


@leaves_bp.route('/apply', methods=['GET', 'POST'])
@login_required
@role_required(Roles.STUDENT)
def apply():
    if request.method == 'POST':
        student = Student.query.filter_by(user_id=current_user.id).first()
        leave_type = request.form.get('type')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        specific_lectures = request.form.get('specific_lectures', '')
        reason = request.form.get('reason', '').strip()

        if not reason:
            flash('Please provide a reason for your leave.', 'danger')
            return redirect(url_for('leaves.apply'))

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Invalid start date format.', 'danger')
            return redirect(url_for('leaves.apply'))

        if leave_type == LeaveType.SINGLE_DAY or leave_type == LeaveType.SPECIFIC_LECTURES:
            end_date = start_date
        else:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                flash('Invalid end date format.', 'danger')
                return redirect(url_for('leaves.apply'))

        if end_date < start_date:
            flash('End date cannot be before start date.', 'danger')
            return redirect(url_for('leaves.apply'))

        leave = LeaveApplication(
            student_id=student.id,
            type=leave_type,
            start_date=start_date,
            end_date=end_date,
            specific_lectures=specific_lectures,
            reason=reason,
            status=LeaveStatus.PENDING_TG
        )
        db.session.add(leave)
        db.session.commit()

        # Notify Teacher Guardian
        from app.utils.helpers import send_notification
        if student.tg_id:
            send_notification(
                student.tg_id,
                f'📋 {current_user.name} applied for leave ({leave_type}) from {start_date} to {end_date}.',
                'info', url_for('leaves.index')
            )
        
        flash('Leave application submitted successfully. Pending Teacher Guardian approval.', 'success')
        return redirect(url_for('leaves.index'))

    return render_template('leaves/apply.html')


@leaves_bp.route('/<int:leave_id>/review', methods=['POST'])
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def review(leave_id):
    leave = LeaveApplication.query.get_or_404(leave_id)
    action = request.form.get('action') # 'approve' or 'reject'
    comment = request.form.get('comment', '').strip()

    # Determine if action is taken as TG or CT
    student = leave.student
    is_tg = (student.tg_id == current_user.id)
    is_ct = False
    if student.class_id:
        cls = Class.query.get(student.class_id)
        if cls and cls.class_teacher_id == current_user.id:
            is_ct = True

    if is_tg and leave.tg_status == ApprovalStatus.PENDING:
        leave.tg_status = ApprovalStatus.APPROVED if action == 'approve' else ApprovalStatus.REJECTED
        leave.tg_approved_by = current_user.id
        leave.tg_comment = comment
        
        if action == 'approve':
            leave.status = LeaveStatus.PENDING_CT
        else:
            leave.status = LeaveStatus.REJECTED

    elif is_ct and leave.tg_status == ApprovalStatus.APPROVED and leave.ct_status == ApprovalStatus.PENDING:
        leave.ct_status = ApprovalStatus.APPROVED if action == 'approve' else ApprovalStatus.REJECTED
        leave.ct_approved_by = current_user.id
        leave.ct_comment = comment
        
        if action == 'approve':
            leave.status = LeaveStatus.APPROVED
        else:
            leave.status = LeaveStatus.REJECTED
    else:
        flash('You do not have permission to review this leave at this stage.', 'danger')
        return redirect(url_for('leaves.index'))

    db.session.commit()

    # Notify student of decision
    from app.utils.helpers import send_notification
    action_label = 'approved ✅' if action == 'approve' else 'rejected ❌'
    stage = 'Teacher Guardian' if is_tg else 'Class Teacher'
    send_notification(
        leave.student.user_id,
        f'Your leave application ({leave.type}) has been {action_label} by {stage}.',
        'success' if action == 'approve' else 'danger',
        url_for('leaves.index')
    )

    flash(f'Leave application {action}d successfully.', 'success')
    return redirect(url_for('leaves.index'))
