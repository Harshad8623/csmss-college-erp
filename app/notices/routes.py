from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db, limiter
from app.models import Notice, Class, User, Roles, Student, AuditLog
from app.utils.decorators import role_required
from app.utils.helpers import send_notification
from datetime import datetime

notices_bp = Blueprint('notices', __name__, url_prefix='/notices')

def get_user_class_id():
    student = Student.query.filter_by(user_id=current_user.id).first()
    return student.class_id if student else None

@notices_bp.route('/')
@login_required
def index():
    role = current_user.role
    query = Notice.query.filter_by(is_deleted=False)

    if role == Roles.STUDENT:
        # Students see approved notices targeted to all or students, and class-specific notices
        class_id = get_user_class_id()
        query = query.filter(
            Notice.status == 'APPROVED',
            (Notice.target_role == None) | (Notice.target_role == Roles.STUDENT),
            (Notice.target_class_id == None) | (Notice.target_class_id == class_id)
        )
    elif role == Roles.CR:
        class_id = get_user_class_id()
        # CR sees approved notices + their own pending/rejected notices
        query = query.filter(
            ((Notice.status == 'APPROVED') & ((Notice.target_role == None) | (Notice.target_role == Roles.STUDENT) | (Notice.target_role == Roles.CR)) & ((Notice.target_class_id == None) | (Notice.target_class_id == class_id))) |
            (Notice.posted_by == current_user.id)
        )
    elif role == Roles.TEACHER:
        # Teachers see their own notices + approved notices targeted to teachers
        query = query.filter(
            ((Notice.status == 'APPROVED') & ((Notice.target_role == None) | (Notice.target_role == Roles.TEACHER))) |
            (Notice.posted_by == current_user.id)
        )
    elif role == Roles.CLASS_TEACHER:
        # Class Teachers also need to see PENDING notices for their class to approve them
        from app.utils.helpers import get_class_for_ct
        cls = get_class_for_ct(current_user.id)
        cls_id = cls.id if cls else -1
        query = query.filter(
            ((Notice.status == 'APPROVED') & ((Notice.target_role == None) | (Notice.target_role == Roles.TEACHER) | (Notice.target_role == Roles.CLASS_TEACHER))) |
            (Notice.posted_by == current_user.id) |
            (Notice.target_class_id == cls_id) # Can see all notices targeted at their class
        )
    else:
        # HOD / SUPER_ADMIN see all
        pass

    notices = query.order_by(Notice.created_at.desc()).all()
    return render_template('notices/index.html', notices=notices)


@notices_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER, Roles.CR)
@limiter.limit("5 per day")
def create():
    # Scope class list by role
    if current_user.role == Roles.SUPER_ADMIN:
        classes = Class.query.all()
    elif current_user.role == Roles.HOD:
        from app.utils.helpers import get_dept_for_hod
        dept_id = get_dept_for_hod(current_user.id)
        classes = Class.query.filter_by(department_id=dept_id).all() if dept_id else []
    elif current_user.role == Roles.CLASS_TEACHER:
        from app.utils.helpers import get_class_for_ct
        cls = get_class_for_ct(current_user.id)
        classes = [cls] if cls else []
    else:  # CR
        class_id = get_user_class_id()
        classes = [Class.query.get(class_id)] if class_id else []
    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        content  = request.form.get('content', '').strip()
        target   = request.form.get('target_role') or None
        cls_id   = request.form.get('target_class_id') or None
        urgent   = bool(request.form.get('is_urgent'))

        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('notices/create.html', classes=classes)

        # Enforce CR Restrictions
        status = 'APPROVED'
        if current_user.role == Roles.CR:
            class_id = get_user_class_id()
            if not class_id:
                flash('CR Profile incomplete. Cannot post notice.', 'danger')
                return redirect(url_for('notices.index'))
            cls_id = class_id # Force class ID
            target = Roles.STUDENT # Force target to students
            status = 'PENDING'

        notice = Notice(title=title, content=content, target_role=target,
                        target_class_id=cls_id, posted_by=current_user.id, 
                        is_urgent=urgent, status=status)
        db.session.add(notice)
        # Audit log goes in the SAME transaction as the notice
        db.session.flush()  # get notice.id
        db.session.add(AuditLog(user_id=current_user.id, action=f"Created notice {notice.id}",
                                module="Notices",
                                ip_address=request.remote_addr))
        db.session.commit()

        # Notification Workflow (send_notification only flushes, commit at end)
        if status == 'PENDING':
            # Notify Class Teacher
            cls = Class.query.get(cls_id)
            if cls and cls.class_teacher_id:
                send_notification(cls.class_teacher_id, f'🔔 Pending Notice Approval: {title} by CR', 'warning', url_for('notices.index'))
            db.session.commit()
            flash('Notice submitted for Class Teacher approval.', 'info')
        else:
            # Notify immediately
            if target:
                users = User.query.filter_by(role=target, status='active').all()
            else:
                users = User.query.filter_by(status='active').all()
            
            # Filter by class if applicable
            if cls_id:
                student_user_ids = [s.user_id for s in Student.query.filter_by(class_id=cls_id).all()]
                users = [u for u in users if u.id in student_user_ids or u.role != Roles.STUDENT]

            for u in users:
                send_notification(u.id, f'📢 New Notice: {title}', 'info' if not urgent else 'warning', url_for('notices.index'))
            db.session.commit()
            flash('Notice posted successfully!', 'success')

        return redirect(url_for('notices.index'))

    return render_template('notices/create.html', classes=classes, roles=[
        ('', 'All Users'), (Roles.STUDENT, 'Students Only'),
        (Roles.TEACHER, 'Teachers Only'), (Roles.CLASS_TEACHER, 'Class Teachers'),
    ])


@notices_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
@role_required(Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def approve(id):
    notice = Notice.query.get_or_404(id)
    
    # Scope Check: Class Teacher can only approve notices for their class
    if current_user.role == Roles.CLASS_TEACHER:
        from app.utils.helpers import get_class_for_ct
        cls = get_class_for_ct(current_user.id)
        if not cls or notice.target_class_id != cls.id:
            abort(403)

    notice.status = 'APPROVED'
    notice.approved_by = current_user.id
    notice.approved_at = datetime.utcnow()
    
    db.session.add(AuditLog(user_id=current_user.id, action=f"Approved notice {notice.id}", module="Notices"))
    
    # Notify CR and Students
    send_notification(notice.posted_by, f'✅ Your notice "{notice.title}" was approved.', 'success', url_for('notices.index'))
    students = Student.query.filter_by(class_id=notice.target_class_id).all()
    for s in students:
        send_notification(s.user_id, f'📢 New Notice: {notice.title}', 'info', url_for('notices.index'))

    db.session.commit()
    flash('Notice approved and published.', 'success')
    return redirect(url_for('notices.index'))


@notices_bp.route('/<int:id>/reject', methods=['POST'])
@login_required
@role_required(Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def reject(id):
    notice = Notice.query.get_or_404(id)
    
    if current_user.role == Roles.CLASS_TEACHER:
        from app.utils.helpers import get_class_for_ct
        cls = get_class_for_ct(current_user.id)
        if not cls or notice.target_class_id != cls.id:
            abort(403)

    notice.status = 'REJECTED'
    notice.approved_by = current_user.id
    notice.approved_at = datetime.utcnow()
    
    db.session.add(AuditLog(user_id=current_user.id, action=f"Rejected notice {notice.id}", module="Notices"))
    send_notification(notice.posted_by, f'❌ Your notice "{notice.title}" was rejected.', 'danger', url_for('notices.index'))
    
    db.session.commit()
    flash('Notice rejected.', 'warning')
    return redirect(url_for('notices.index'))


@notices_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def delete(id):
    notice = Notice.query.get_or_404(id)
    
    if current_user.role == Roles.CLASS_TEACHER:
        from app.utils.helpers import get_class_for_ct
        cls = get_class_for_ct(current_user.id)
        if not cls or notice.target_class_id != cls.id:
            abort(403)

    notice.is_deleted = True
    db.session.add(AuditLog(user_id=current_user.id, action=f"Soft deleted notice {notice.id}", module="Notices"))
    db.session.commit()
    
    flash('Notice deleted.', 'info')
    return redirect(url_for('notices.index'))
