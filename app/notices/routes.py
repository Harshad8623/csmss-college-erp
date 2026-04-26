from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Notice, Class, User, Roles
from app.utils.decorators import role_required
from app.utils.helpers import send_notification

notices_bp = Blueprint('notices', __name__, url_prefix='/notices')

@notices_bp.route('/')
@login_required
def index():
    role = current_user.role
    if role == Roles.STUDENT:
        notices = Notice.query.filter(
            (Notice.target_role == None) | (Notice.target_role == Roles.STUDENT)
        ).order_by(Notice.created_at.desc()).all()
    elif role == Roles.TEACHER:
        notices = Notice.query.filter(
            (Notice.target_role == None) | (Notice.target_role == Roles.TEACHER)
        ).order_by(Notice.created_at.desc()).all()
    else:
        notices = Notice.query.order_by(Notice.created_at.desc()).all()

    return render_template('notices/index.html', notices=notices)

@notices_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER, Roles.CR)
def create():
    classes = Class.query.all()
    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        content  = request.form.get('content', '').strip()
        target   = request.form.get('target_role') or None
        cls_id   = request.form.get('target_class_id') or None
        urgent   = bool(request.form.get('is_urgent'))

        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('notices/create.html', classes=classes)

        notice = Notice(title=title, content=content, target_role=target,
                        target_class_id=cls_id, posted_by=current_user.id, is_urgent=urgent)
        db.session.add(notice)
        db.session.commit()

        # Notify relevant users
        if target:
            users = User.query.filter_by(role=target, status='active').all()
        else:
            users = User.query.filter_by(status='active').all()
        for u in users:
            send_notification(u.id, f'📢 New Notice: {title}', 'info' if not urgent else 'warning',
                              url_for('notices.index'))

        flash('Notice posted successfully!', 'success')
        return redirect(url_for('notices.index'))

    return render_template('notices/create.html', classes=classes, roles=[
        ('', 'All Users'), (Roles.STUDENT, 'Students Only'),
        (Roles.TEACHER, 'Teachers Only'), (Roles.CLASS_TEACHER, 'Class Teachers'),
    ])

@notices_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD)
def delete(id):
    notice = Notice.query.get_or_404(id)
    db.session.delete(notice)
    db.session.commit()
    flash('Notice deleted.', 'info')
    return redirect(url_for('notices.index'))
