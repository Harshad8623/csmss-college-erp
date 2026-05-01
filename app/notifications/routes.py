from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.models import Notification
from app.extensions import db

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def index():
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(50).all()
    # Only mark the SHOWN notifications as read — do not mark notifications
    # the user hasn't seen yet (beyond the 50 limit) as read
    shown_ids = [n.id for n in notifications if not n.is_read]
    if shown_ids:
        Notification.query.filter(Notification.id.in_(shown_ids))\
            .update({'is_read': True}, synchronize_session=False)
        db.session.commit()
    return render_template('notifications/index.html', notifications=notifications)

@notifications_bp.route('/mark-read/<int:id>', methods=['POST'])
@login_required
def mark_read(id):
    n = Notification.query.get_or_404(id)
    if n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    # Security: only redirect to relative paths to prevent open redirect
    target = n.link or url_for('dashboard.index')
    if target.startswith('http') or target.startswith('//'):
        target = url_for('dashboard.index')
    return redirect(target)

@notifications_bp.route('/api/unread')
@login_required
def unread_api():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    recent = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(5).all()
    return jsonify({
        'count': count,
        'notifications': [{'id': n.id, 'message': n.message, 'type': n.type,
                           'link': n.link, 'is_read': n.is_read} for n in recent]
    })
